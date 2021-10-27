import aiofiles
import aiohttp
import argparse
import asyncio
import async_frames_cv as af
import base64
import configparser
import cv2
import datetime
import io
import json
import logging
import numpy as np
import os
from pathlib import Path
import pytz
import sys
import threading
import time
from turbojpeg import TurboJPEG

# the tensorrt_demos directory, please build this first
sys.path.append('../../tensorrt_demos/utils')

import pycuda.autoinit  # This is needed for initializing CUDA driver

from yolo_classes import get_cls_dict
from display import open_window, set_display, show_fps
from visualization import BBoxVisualization
from yolo_with_plugins import TrtYOLO

LOG_LEVEL = logging.INFO
LOGFORMAT = "  %(log_color)s%(levelname)-8s%(reset)s | %(log_color)s%(message)s%(reset)s"
from colorlog import ColoredFormatter

# logging.basicConfig(filename='detections.log')
logging.root.setLevel(LOG_LEVEL)
formatter = ColoredFormatter(LOGFORMAT)
stream = logging.StreamHandler()
stream.setLevel(LOG_LEVEL)
stream.setFormatter(formatter)
log = logging.getLogger('pythonConfig')
log.setLevel(LOG_LEVEL)
log.addHandler(stream)


def parse_args():
    """Parse input arguments."""
    desc = ('Detect persons on HTTP pictures from HikVision DVR')
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument(
        '-c', '--category_num', type=int, default=80,
        help='number of object categories [80]')
    parser.add_argument(
        '-m', '--model', type=str, required=False, default='yolov4-416',
        help=('[yolov3-tiny|yolov3|yolov3-spp|yolov4-tiny|yolov4|'
              'yolov4-csp|yolov4x-mish]-[{dimension}], where '
              '{dimension} could be either a single number (e.g. '
              '288, 416, 608) or 2 numbers, WxH (e.g. 416x256)'))
    parser.add_argument(
        '-l', '--letter_box', action='store_true',
        help='inference with letterboxed image [False]')
    args = parser.parse_args()
    return args


args = parse_args()
if args.category_num <= 0:
    raise SystemExit('ERROR: bad category_num (%d)!' % args.category_num)
if not os.path.isfile('yolo/%s.trt' % args.model):
    raise SystemExit('ERROR: file (yolo/%s.trt) not found!' % args.model)

# determine user home directory for saving detection frames
home = str(Path.home())
cwdpath = os.path.join(home, "Pictures/SecVision/")
xml_on = "<IOPortData version=\"1.0\" xmlns=\"http://www.hikvision.com/ver20/XMLSchema\"><outputState>high</outputState></IOPortData>"
xml_off = "<IOPortData version=\"1.0\" xmlns=\"http://www.hikvision.com/ver20/XMLSchema\"><outputState>low</outputState></IOPortData>"


class SecVisionJetson:
    channel_frames = []
    channel_event = {}
    gc = []
    jpeg = TurboJPEG()
    cls_dict = get_cls_dict(args.category_num)
    vis = BBoxVisualization(cls_dict)
    trt_yolo = TrtYOLO(args.model, args.category_num, args.letter_box)

    def __init__(self, cfg) -> None:
        self.config = cfg

    def session_auth(self):
        authkey = f"{self.config.get('DVR', 'username')}:{self.config.get('DVR', 'password')}"
        auth_bytes = authkey.encode('ascii')
        base64_bytes = base64.b64encode(auth_bytes)
        auth = base64_bytes.decode('ascii')
        headers = {"Authorization": f"Basic {auth}"}
        return headers

    @staticmethod
    def initworkers(obj) -> None:
        e = threading.Event()
        heartbeatworker = threading.Thread(name='heartbeat-daemon', target=SecVisionJetson.recorder_thread,
                                           args=(e, obj, 5))
        heartbeatworker.setDaemon(True)
        heartbeatworker.start()

    @staticmethod
    def recorder_thread(event: threading.Event, obj, time: float) -> None:
        while not event.isSet():
            garbage_collector = []
            event_is_set = event.wait(time)
            if event_is_set:
                logging.debug('processing event')
            else:
                ao_temp, cpu_temp, gpu_temp, pll_temp, rpm, thermal = SecVisionJetson.jetson_metrics()
                if len(obj.channel_event) > 0:
                    for channel in obj.channel_event:
                        if float(obj.channel_event[channel]) > 0:
                            elapsed = datetime.datetime.now() - datetime.datetime.fromtimestamp(
                                obj.channel_event[channel])
                            logging.warning(
                                f" {channel} Person found {elapsed.total_seconds()}s ago")
                            SecVisionJetson.log_metrics(ao_temp, cpu_temp, gpu_temp, pll_temp, rpm, thermal)
                            if elapsed > datetime.timedelta(seconds=30):
                                garbage_collector.append(channel)
                    for channel in garbage_collector:
                        obj.channel_event.pop(channel, None)
                        obj.gc.append(channel)
                else:
                    SecVisionJetson.log_metrics(ao_temp, cpu_temp, gpu_temp, pll_temp, rpm, thermal)

    @staticmethod
    def log_metrics(ao_temp, cpu_temp, gpu_temp, pll_temp, rpm, thermal):
        logging.info(
            f" CPU {int(cpu_temp) / 1000:.2f}°C / GPU {int(gpu_temp) / 1000:.2f}°C /"
            f" PLL {int(pll_temp) / 1000:.2f}°C")
        logging.info(
            f" AO {int(ao_temp) / 1000:.2f}°C / THERM {int(thermal) / 1000:.2f}°C / FAN {round(rpm, 0)}RPM ")

    @staticmethod
    def jetson_metrics():
        # Jetson thermal sensors
        ao_temp = os.popen("cat /sys/devices/virtual/thermal/thermal_zone0/temp").read()
        cpu_temp = os.popen("cat /sys/devices/virtual/thermal/thermal_zone1/temp").read()
        gpu_temp = os.popen("cat /sys/devices/virtual/thermal/thermal_zone2/temp").read()
        pll_temp = os.popen("cat /sys/devices/virtual/thermal/thermal_zone3/temp").read()
        pmic_temp = os.popen("cat /sys/devices/virtual/thermal/thermal_zone4/temp").read()
        thermal = os.popen("cat /sys/devices/virtual/thermal/thermal_zone5/temp").read()
        # Fan PWM reading
        pwm = os.popen("cat /sys/devices/pwm-fan/hwmon/hwmon1/cur_pwm").read()
        rpm = int(pwm) * (2000 / 256)
        return ao_temp, cpu_temp, gpu_temp, pll_temp, rpm, thermal

    # DVR has 4 Alarm Output ports, they are electrically connected like so :
    # => Output 1 to Inputs 1 and 2
    # => Output 2 to Inputs 3 and 4
    # => Output 3 to Inputs 5 and 6
    # => Output 4 to Inputs 7 and 8
    def determine_zone(self, channel):
        zone = 1
        if int(channel) <= 201:
            zone = 1
        elif 201 < int(channel) <= 401:
            zone = 2
        elif 401 < int(channel) <= 601:
            zone = 3
        else:
            zone = 4
        return zone

    # Starts a recording for a zone when triggered.
    # TODO : Trigger per channel directly, would negate the surveillance center notification...
    async def trigger_zone(self, session, zone, high):
        url = f"http://{self.config.get('DVR', 'ip')}/ISAPI/System/IO/outputs/{zone}/trigger"
        data = ""
        if high:
            data = xml_on
        else:
            data = xml_off
        async with session.put(url, data=data) as response:
            if response.status == 200:
                if high:
                    logging.warning(
                        f" Zone {zone} triggered on")
                else:
                    logging.warning(
                        f" Zone {zone} triggered off")

    # Network detection
    async def detect(self, image, trt_yolo, conf_th, vis, channel, session):
        img = image
        boxes, confs, clss = trt_yolo.detect(img, conf_th)
        idx = 0
        zone = 0
        for cococlass in clss:
            if cococlass == 0 and confs[idx] >= 0.85:
                now = datetime.datetime.now()
                zone = self.determine_zone(channel)
                logging.info(
                    f" {channel} Person found - Zone {zone} start recording")
                await self.trigger_zone(session, zone, True)
                # if self.channel_event[channel]:
                # Over write latest human timestamp on a given channel
                self.channel_event[channel] = datetime.datetime.timestamp(datetime.datetime.now())
                # do request for DVR recording stuff here 
                imgdir = "frames/" + now.strftime('%Y-%m-%d') + "/" + f"{channel}" + "/"
                wd = os.path.join(cwdpath, imgdir)
                try:
                    os.makedirs(wd)
                except FileExistsError:
                    # directory already exists
                    pass
                # Save data
                drawing = False
                if drawing:
                    img = vis.draw_bboxes(img, boxes, confs, clss)
                else:
                    pass
                np.save(wd + f"{now.strftime('%H_%M_%S.%f')}_person_boxes", boxes)
                np.save(wd + f"{now.strftime('%H_%M_%S.%f')}_person_confs", confs)
                np.save(wd + f"{now.strftime('%H_%M_%S.%f')}_person_clss", clss)
                cv2.imwrite(wd + f"{now.strftime('%H_%M_%S.%f')}_person_frame.jpg", img,
                            [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            idx += 1

    # The main loop
    async def main(self):
        async with aiohttp.ClientSession(headers=self.session_auth()) as session:
            while True:
                start = time.time()
                channel_frames, timer = await af.get_frames(session, self.config.get('DVR', 'ip'),
                                                            self.config.get('DVR', 'channels'), self.jpeg)
                for channel, frame in channel_frames:
                    # detect objects in the image
                    await self.detect(frame, self.trt_yolo, 0.5, self.vis, channel, session)
                end = time.time()
                # logging.info(
                #     f" Network {8 / (end - start - timer):.2f}fps")
                for channel in self.gc:
                    await self.trigger_zone(session, self.determine_zone(channel), False)
                self.gc = []
                logging.info(f" Inference loop - {(end - start - timer):.2f} - {8 / (end - start - timer):.2f}fps")


if __name__ == '__main__':
    cwd = os.path.dirname(os.path.abspath(__file__))
    settings = os.path.join("../", cwd, 'settings.ini')
    config = configparser.ConfigParser()
    config.read(settings)
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
    app = SecVisionJetson(config)
    SecVisionJetson.initworkers(app)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(app.main())
