import aiohttp
from aiohttp import web
import argparse
import asyncio
import async_frames_cv_v2 as af
import base64
import configparser
import cv2
from dateutil import parser
import datetime
import io
import json
import logging
import numpy as np
import os
from pathlib import Path
from PIL import Image
from tinydb import TinyDB, Query
import pytz
from secvision_web import aiohttp_server, run_server
import sys
import threading
import time
from turbojpeg import TurboJPEG

# determine user home directory
home = str(Path.home())

# the tensorrt_demos directory, please build this first
tensorRT = os.path.join(home, "tensorrt_demos/utils")
sys.path.append(tensorRT)

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

cwdpath = os.path.join(home, "Pictures/SecVision/")

xml_on = "<IOPortData version=\"1.0\" xmlns=\"http://www.hikvision.com/ver20/XMLSchema\"><outputState>high</outputState></IOPortData>"
xml_off = "<IOPortData version=\"1.0\" xmlns=\"http://www.hikvision.com/ver20/XMLSchema\"><outputState>low</outputState></IOPortData>"

channel_names = {
    '101': 'Front lawn',
    '201': 'Front door',
    '301': 'Driveway',
    '401': 'Side gate',
    '501': 'Courtyard',
    '601': 'Garage gate',
    '701': 'Back Lawn',
    '801': 'Pool'
}

thresholds = {
    '101': 0.78,
    '201': 0.78,
    '301': 0.82,
    '401': 0.86,
    '501': 0.92,
    '601': 0.92,
    '701': 0.78,
    '801': 0.78
}

draw = {
    '101': True,
    '201': True,
    '301': True,
    '401': True,
    '501': True,
    '601': True,
    '701': True,
    '801': True
}
fan_rpm = 2000


class SecVisionJetson:
    channel_frames = []
    cnt = 0
    class_channel_event = {}
    class_garbage_collector = []
    zone1 = {}
    zone2 = {}
    zone3 = {}
    zone4 = {}
    network_speed = []
    jpeg = TurboJPEG()
    cls_dict = get_cls_dict(args.category_num)
    vis = BBoxVisualization(cls_dict)
    trt_yolo = TrtYOLO(args.model, args.category_num, args.letter_box)
    

    def __init__(self, cfg, db) -> None:
        self.config = cfg
        self.database = db
        self.chcnt = self.config.get('DVR', 'channels')
        self.DVRip = self.config.get('DVR', 'ip')
        self.od = sorted(self.database.all(), key=lambda k: k['time'])

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

        webserver = threading.Thread(target=run_server, args=(aiohttp_server(obj),))
        webserver.start()


    @staticmethod
    def recorder_thread(event: threading.Event, obj, time: float) -> None:
        while not event.isSet():
            thread_zone_garbage_collector = []
            thread_channel_done_event = []

            event_is_set = event.wait(time)
            if event_is_set:
                logging.debug('processing event')
            else:
                obj.cnt += 1
                # Give us stats every minute or so . . .
                if obj.cnt == 12:
                    obj.cnt = 0
                    ao_temp, cpu_temp, gpu_temp, pll_temp, rpm, thermal = SecVisionJetson.jetson_metrics()
                    net_speed = sum(obj.network_speed) / len(obj.network_speed)
                    SecVisionJetson.log_metrics(ao_temp, cpu_temp, gpu_temp, pll_temp, rpm, thermal, net_speed)
                    data = obj.od[-1]
                    person = f"{data['persons']} persons" if int(data['persons']) > 1 else f"{data['persons']} person"
                    display_date = data['time'][11:22]

                    logging.info(
                        f" Last Detection : {display_date}: {channel_names[data['channel']]} -> {person} found")
                if len(obj.class_channel_event) > 0:
                    for channel in obj.class_channel_event:
                        if float(obj.class_channel_event[channel]) > 0:
                            elapsed = datetime.datetime.now() - datetime.datetime.fromtimestamp(
                                obj.class_channel_event[channel])
                            logging.warning(
                                f" {channel_names[channel]} person found {elapsed.total_seconds()}s ago")

                            if elapsed > datetime.timedelta(seconds=15):
                                zone = obj.determine_zone(channel)
                                if zone == 1:
                                    if len(obj.zone1) == 1:
                                        thread_zone_garbage_collector.append(channel)
                                    else:
                                        thread_channel_done_event.append(channel)
                                    obj.zone1.pop(channel, None)
                                elif zone == 2:
                                    if len(obj.zone2) == 1:
                                        thread_zone_garbage_collector.append(channel)
                                    else:
                                        thread_channel_done_event.append(channel)
                                    obj.zone2.pop(channel, None)
                                elif zone == 3:
                                    if len(obj.zone3) == 1:
                                        thread_zone_garbage_collector.append(channel)
                                    else:
                                        thread_channel_done_event.append(channel)
                                    obj.zone3.pop(channel, None)
                                else:
                                    if len(obj.zone4) == 1:
                                        thread_zone_garbage_collector.append(channel)
                                    else:
                                        thread_channel_done_event.append(channel)
                                    obj.zone4.pop(channel, None)

                    for channel in thread_channel_done_event:
                        obj.class_channel_event.pop(channel, None)

                    for channel in thread_zone_garbage_collector:
                        obj.class_channel_event.pop(channel, None)
                        obj.class_garbage_collector.append(channel)

    @staticmethod
    def log_metrics(ao_temp, cpu_temp, gpu_temp, pll_temp, rpm, thermal, net):
        logging.info(
            f" CPU {int(cpu_temp) / 1000:.2f}°C / GPU {int(gpu_temp) / 1000:.2f}°C /"
            f" PLL {int(pll_temp) / 1000:.2f}°C")
        logging.info(
            f" AO {int(ao_temp) / 1000:.2f}°C / THERM {int(thermal) / 1000:.2f}°C / FAN {round(rpm, 0)}RPM ")
        logging.info(
            f" NETWORK {net:.2f} FPS ")

    @staticmethod
    def jetson_metrics():
        # Jetson thermal sensors
        ao_temp = os.popen("cat /sys/devices/virtual/thermal/thermal_zone0/temp").read()
        cpu_temp = os.popen("cat /sys/devices/virtual/thermal/thermal_zone1/temp").read()
        gpu_temp = os.popen("cat /sys/devices/virtual/thermal/thermal_zone2/temp").read()
        pll_temp = os.popen("cat /sys/devices/virtual/thermal/thermal_zone3/temp").read()
        pmic_temp = os.popen("cat /sys/devices/virtual/thermal/thermal_zone4/temp").read()
        thermal = os.popen("cat /sys/devices/virtual/thermal/thermal_zone5/temp").read()
        # input_voltage = os.popen("cat /sys/bus/i2c/drivers/ina3221x/6-0040/iio\:device0/in_voltage0_input").read()
        # Fan PWM reading
        pwm = os.popen("cat /sys/devices/pwm-fan/hwmon/hwmon1/cur_pwm").read()
        rpm = int(pwm) * (fan_rpm / 256)
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
        url = f"http://{self.DVRip}/ISAPI/System/IO/outputs/{zone}/trigger"
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
    async def detect(self, image, trt_yolo, conf_th, vis, channel, session, tasks):
        img = image
        boxes, confs, clss = trt_yolo.detect(img, conf_th)
        idx = 0
        persons = 0
        # count persons
        for cococlass in clss:
            if cococlass == 0:
                persons += 1
        if persons > 0 :
            for cococlass in clss:
                if cococlass == 0 and confs[idx] >= thresholds[channel]:
                    now = datetime.datetime.now()
                    timenow = str(now.replace(tzinfo=pytz.utc))
                    zone = self.determine_zone(channel)
                    msg = await self.zone_activator(channel, session, tasks, zone, confs[idx], persons)
                    logging.warning(msg)

                    # Over write latest human timestamp on a given channel
                    self.class_channel_event[channel] = datetime.datetime.timestamp(datetime.datetime.now())
                    # Image saving
                    imgdir = "frames/" + now.strftime('%Y-%m-%d') + "/" + f"{channel}" + "/"
                    wd = os.path.join("../", imgdir)
                    try:
                        os.makedirs(wd)
                    except FileExistsError:
                        # directory already exists
                        pass
                    # Save data
                    drawing = draw[channel]
                    if drawing:
                        img = vis.draw_bboxes(img, boxes, confs, clss)
                    else:
                        pass
                    start = time.time()
                    savepath = wd + f"{now.strftime('%H_%M_%S.%f')}_person_"
                    np.save(wd + f"{now.strftime('%H_%M_%S.%f')}_person_boxes", boxes)
                    np.save(wd + f"{now.strftime('%H_%M_%S.%f')}_person_confs", confs)
                    np.save(wd + f"{now.strftime('%H_%M_%S.%f')}_person_clss", clss)
                    cv2.imwrite(savepath + "frame.jpg", img,
                                [int(cv2.IMWRITE_JPEG_QUALITY), 83])
                    end = time.time()
                    logging.info(f" File save time{(end - start):.2f}s")
                    start1 = time.time()
                    self.database.insert({
                        "time": f"{timenow}",
                        "persons": str(persons),
                        "channel": f"{channel}",
                        "path": f"{savepath}",
                        "confs": str(confs[idx])
                    })
                    end1 = time.time()
                    logging.info(f" Insert time {(end1 - start1):.2f}s")
                    self.od = self.database.all()

                    # image_file = Image.open(io.BytesIO(bytes))
                    # image_file.save(wd + f"{now.strftime('%H_%M_%S.%f')}_person_frame.jpg")
                    break
                idx += 1

    async def zone_activator(self, channel, session, tasks, zone, confidence, persons):
        person = f'{persons} persons' if persons > 1 else f'{persons} person'
        msg = f" {channel_names[channel]} - {confidence:.2f} - {person} found in zone {zone} - recording"
        if zone == 1:
            if len(self.zone1) == 0:
                msg = f" {channel_names[channel]} - {confidence:.2f} - {person} found in zone {zone} - start recording"
                tasks.append(asyncio.ensure_future(self.trigger_zone(session, zone, True)))
            self.zone1[channel] = channel
        elif zone == 2:
            if len(self.zone2) == 0:
                msg = f" {channel_names[channel]} - {confidence:.2f} - {person} found in zone {zone} - start recording"
                tasks.append(asyncio.ensure_future(self.trigger_zone(session, zone, True)))
            self.zone2[channel] = channel
        elif zone == 3:
            if len(self.zone3) == 0:
                msg = f" {channel_names[channel]} - {confidence:.2f} - {person} found in zone {zone} - start recording"
                tasks.append(asyncio.ensure_future(self.trigger_zone(session, zone, True)))
            self.zone3[channel] = channel
        else:
            if len(self.zone4) == 0:
                msg = f" {channel_names[channel]} - {confidence:.2f} - {person} found in zone {zone} - start recording"
                tasks.append(asyncio.ensure_future(self.trigger_zone(session, zone, True)))
            self.zone4[channel] = channel
        return msg

    async def cleanstart(self, session, zone):
        await self.trigger_zone(session, zone, False)

    # The main loop
    async def main(self):
        async with aiohttp.ClientSession(headers=self.session_auth()) as session:
            for i in range(1, 5):
                await self.cleanstart(session, i)
            while True:
                try:
                    start = time.time()
                    tasks = []
                    channel_frames, timer = await af.get_frames(session, self.config.get('DVR', 'ip'),
                                                                self.chcnt, self.jpeg)
                    
                    for channel, frame in channel_frames:
                        # detect objects in the image
                        await self.detect(frame, self.trt_yolo, 0.65, self.vis, channel, session, tasks)
                    end = time.time()
                    await asyncio.gather(*tasks)

                    for channel in self.class_garbage_collector:
                        await self.trigger_zone(session, self.determine_zone(channel), False)
                    self.class_garbage_collector = []
                    self.network_speed.append(int(self.chcnt) / (end - start - timer))
                    # keeps the network average array nice and small
                    if len(self.network_speed) > 128:
                        for i in range(0, 65):
                            self.network_speed.pop(0)

                    logging.info(f" Inference loop - {(end - start - timer):.2f}s @ {int(self.chcnt) / (end - start - timer):.2f}fps")
                except aiohttp.client_exceptions.ClientConnectorError:
                    logging.info(f" ClientConnectorError")
                    await asyncio.sleep(10)
                    pass


if __name__ == '__main__':
    cwd = os.path.dirname(os.path.abspath(__file__))
    settings = os.path.join("../", cwd, 'settings.ini')
    # print(settings)
    config = configparser.ConfigParser()
    config.read(settings)
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
    database = TinyDB('./db.json')
    app = SecVisionJetson(config, database)
    SecVisionJetson.initworkers(app)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(app.main())
