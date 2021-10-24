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
import os
from pathlib import Path
import pytz
import sys
import threading
import time

# the tensorrt_demos directory, please build this first
sys.path.append('../tensorrt_demos/utils')

import pycuda.autoinit  # This is needed for initializing CUDA driver

from yolo_classes import get_cls_dict
from display import open_window, set_display, show_fps
from visualization import BBoxVisualization
from yolo_with_plugins import TrtYOLO


def parse_args():
    """Parse input arguments."""
    desc = ('Capture and display live camera video, while doing '
            'real-time object detection with TensorRT optimized '
            'YOLO model on Jetson')
    parser = argparse.ArgumentParser(description=desc)
    # parser = add_camera_args(parser)
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

# load the object detection network
# net = jetson.inference.detectNet(opt.network, sys.argv, opt.threshold)
cls_dict = get_cls_dict(args.category_num)
vis = BBoxVisualization(cls_dict)
trt_yolo = TrtYOLO(args.model, args.category_num, args.letter_box)

# determine user home directory for saving detection frames
home = str(Path.home())
cwdpath = os.path.join(home, "Pictures/SecVision/")


class SecVisionJetson:
    channel_frames = []
    channel_event = {}

    def __init__(self, cfg) -> None:
        self.config = cfg

    @staticmethod
    def recorder_thread(event: threading.Event, obj, time: float) -> None:
        while not event.isSet():
            garbage_collector = []
            event_is_set = event.wait(time)
            if event_is_set:
                logging.debug('processing event')
            else:
                cpu_temp = os.popen("cat /sys/devices/virtual/thermal/thermal_zone0/temp").read()
                gpu_temp = os.popen("cat /sys/devices/virtual/thermal/thermal_zone1/temp").read()
                pwm = os.popen("cat /sys/devices/pwm-fan/hwmon/hwmon1/cur_pwm").read()
                rpm = int(pwm) * (2000 / 256)
                if len(obj.channel_event) > 0:
                    # result = lopey.run_until_complete(SecVisionJetson.get_data(sesh)).result()
                    # obj.channel_frames.append(result)
                    for channel in obj.channel_event:
                        # if (datetime.now() - value) > 20:
                        # logging.debug(f"Human detected on {event.channel} more than 20s ago")
                        # del obj.channel_event[i] 
                        if float(obj.channel_event[channel]) > 0:
                            elapsed = datetime.datetime.now() - datetime.datetime.fromtimestamp(
                                obj.channel_event[channel])
                            logging.info(
                                f"{str(datetime.datetime.utcnow().replace(tzinfo=pytz.utc))} : {channel} Person found {elapsed}s ago")
                            logging.info(
                                f"{str(datetime.datetime.utcnow().replace(tzinfo=pytz.utc))} : CPU {int(cpu_temp) / 1000:.2f}°C / GPU {int(gpu_temp) / 1000:.2f}°C / FAN {rpm:.2f}RPM")
                            if elapsed > datetime.timedelta(seconds=30):
                                logging.info(
                                    f"{str(datetime.datetime.utcnow().replace(tzinfo=pytz.utc))} : {channel} Stop recording")
                                garbage_collector.append(channel)
                    for channel in garbage_collector:
                        obj.channel_event.pop(channel, None)
                else:
                    logging.info(
                        f"{str(datetime.datetime.utcnow().replace(tzinfo=pytz.utc))} : CPU {int(cpu_temp) / 1000:.2f}°C / GPU {int(gpu_temp) / 1000:.2f}°C / FAN {rpm}")

    async def loop_and_detect(self, image, trt_yolo, conf_th, vis, channel):
        img = image
        boxes, confs, clss = trt_yolo.detect(img, conf_th)
        img = vis.draw_bboxes(img, boxes, confs, clss)
        idx = 0
        for cococlass in clss:
            # print(f"{channel} : {cococlass}")
            # person classID in COCO is 1
            # confs
            if cococlass == 0 and confs[idx] >= 0.85:
                now = datetime.datetime.now()
                logging.info(
                    f"{str(datetime.datetime.utcnow().replace(tzinfo=pytz.utc))} : {channel} Person found - Start recording")
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
                # fast file save...
                cv2.imwrite(wd + f"{now.strftime('%H_%M_%S.%f')}_person_frame.jpg", img)
            idx += 1

    async def main(self):
        authkey = f"{config.get('DVR', 'username')}:{config.get('DVR', 'password')}"
        auth_bytes = authkey.encode('ascii')
        base64_bytes = base64.b64encode(auth_bytes)
        auth = base64_bytes.decode('ascii')
        headers = {"Authorization": f"Basic {auth}"}
        async with aiohttp.ClientSession(headers=headers) as session:
            while True:
                start = time.time()
                channel_frames, timer = await af.get_frames(session, self.config.get('DVR', 'ip'),
                                                            self.config.get('DVR', 'channels'))
                for channel, frame in channel_frames:
                    # detect objects in the image
                    await self.loop_and_detect(frame, trt_yolo, 0.5, vis, channel)
                end = time.time()
                logging.info(
                    f"{str(datetime.datetime.utcnow().replace(tzinfo=pytz.utc))} : Network {8 / (end - start - timer):.2f}fps")
                # logging.info(f"Inference loop - {end - start - timer} - {8/(end - start - timer)}fps")

    @staticmethod
    def initworkers(obj) -> None:
        e = threading.Event()
        heartbeatworker = threading.Thread(name='heartbeat-daemon', target=SecVisionJetson.recorder_thread,
                                           args=(e, obj, 5))
        heartbeatworker.setDaemon(True)
        heartbeatworker.start()


if __name__ == '__main__':
    cwd = os.path.dirname(os.path.abspath(__file__))
    settings = os.path.join(cwd, 'settings.ini')
    config = configparser.ConfigParser()
    config.read(settings)
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
    app = SecVisionJetson(config)
    SecVisionJetson.initworkers(app)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(app.main())
