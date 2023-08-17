import aiohttp
import argparse
import asyncio
import async_frames_cv_v2 as af
import base64
import configparser
import cv2
import datetime as dt
import json
import logging
import numpy as np
import os
from pathlib import Path
import pytz
import redis
from secvision_static import initworkers, channel_names
import sys
import time
from turbojpeg import TurboJPEG
import traceback
import uvloop

# import clr

# determine user home directory
home = str(Path.home())

# the tensorrt_demos directory, please build this first
tensorRT = os.path.join(home, "tensorrt_demos/utils")
sys.path.append(tensorRT)

import pycuda.autoinit  # This is needed for initializing CUDA driver

from yolo_classes import get_cls_dict
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
    desc = 'Detect persons on HTTP pictures from HikVision DVR'
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
    '201': False,
    '301': True,
    '401': True,
    '501': True,
    '601': True,
    '701': True,
    '801': True
}


class SecVisionJetson:
    channel_frames = []
    cnt = 0
    sv_channel_event = {}
    sv_garbage_collector = []
    zone1 = {}
    zone2 = {}
    zone3 = {}
    zone4 = {}
    network_speed = []
    jpeg = TurboJPEG()
    cls_dict = get_cls_dict(args.category_num)
    vis = BBoxVisualization(cls_dict)
    trt_yolo = TrtYOLO(args.model, args.category_num, args.letter_box)
    front_door_img_path = ""
    telegramChannel = ""

    def __init__(self, cfg, redis) -> None:
        self.config = cfg
        self.redisDb = redis
        self.chcnt = self.config.get('DVR', 'channels')
        self.DVRip = self.config.get('DVR', 'ip')
        self.record_timeout = self.config.get('DVR', 'record_timeout')
        self.use_zones = False

    @staticmethod
    def session_auth(app_cfg):
        authkey = f"{app_cfg.get('DVR', 'username')}:{app_cfg.get('DVR', 'password')}"
        auth_bytes = authkey.encode('ascii')
        base64_bytes = base64.b64encode(auth_bytes)
        auth = base64_bytes.decode('ascii')
        headers = {"Authorization": f"Basic {auth}"}
        return headers

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

    # Starts a recording for a zone or channel when triggered.
    # TODO : Send surveillance center notification...
    async def trigger_zone(self, session, zone, high, channel="", record=False):
        url = ""
        # logging.info(f"TRIGGER ZONE => channel {channel} should I record : {record}")
        if channel != "":
            if record:
                url = f"http://{self.DVRip}/ISAPI/ContentMgmt/record/control/manual/start/tracks/{channel}"
            else:
                url = f"http://{self.DVRip}/ISAPI/ContentMgmt/record/control/manual/stop/tracks/{channel}"
            async with session.put(url) as response:
                if response.status == 200:
                    if record:
                        logging.info(f" {channel} started recording")
                    else:
                        logging.info(f" {channel} stopped recording")
        else:
            url = f"http://{self.DVRip}/ISAPI/System/IO/outputs/{zone}/trigger"
            data = ""
            if high:
                data = xml_on
            else:
                data = xml_off
            async with session.put(url, data=data) as response:
                if response.status == 200:
                    if high:
                        logging.info(
                            f" Zone {zone} triggered on")
                    else:
                        logging.info(
                            f" Zone {zone} triggered off")

    # This method discards top y coordinate when lower than some value, eg: 
    # person is high up in the frame                    
    @staticmethod
    def check_front_door(boxes, persons, channel):
        if channel == '201':
            count_of_boxes = len(boxes)
            for i in range(0, count_of_boxes - 1):
                # [0] , [1] , [2] , [3]
                if persons > 0 and (count_of_boxes - persons >= 0):
                    # logging.info(f" {channel} Boxes ({count_of_boxes})  => {boxes}")
                    # if coord_one[0] >= 725 and coord_one[1] >= 52 and persons > 0:
                    logging.info(f" {channel} {count_of_boxes} cnt => {boxes[i]}")
                    coord_one = []
                    coord_two = []
                    for coord in boxes[i]:
                        if len(coord_one) == 0:
                            coord_one.append(coord)
                            continue
                        if len(coord_one) == 1:
                            coord_one.append(coord)
                            continue
                        if len(coord_one) == 2 and len(coord_two) == 0:
                            coord_two.append(coord)
                            continue
                        if len(coord_one) == 2 and len(coord_two) == 1:
                            coord_two.append(coord)
                            continue
                    if coord_one[1] > 81:
                        logging.info(f" record => {coord_one[0]} , {coord_one[1]}")
                        return True
        return True

    # Network detection
    async def detect(self, image, trt_yolo, conf_th, vis, channel, session, tasks):
        img = image

        # measure detection time
        detection_timer = time.time()
        boxes, confs, clss = trt_yolo.detect(img, conf_th)
        end = time.time()
        # if end - detection_timer > 0.19:
        #     logging.info(f" {channel_names[channel]} Detection time slow - {(end - detection_timer):.2f}s")

        # count persons
        idx = 0
        persons = 0
        for cococlass in clss:
            if cococlass == 0 and confs[idx] >= thresholds[channel]:
                persons += 1

        # if channel == '201' and persons > 0:

        # Do work when person is found
        if persons > 0:
            for cococlass in clss:
                if cococlass == 0 and confs[idx] >= thresholds[channel]:
                    now = dt.datetime.now()
                    msg = ""
                    timenow = str(now.replace(tzinfo=pytz.utc))
                    zone = self.determine_zone(channel)
                    condition = SecVisionJetson.check_front_door(boxes, persons, channel)
                    if channel == '201' or channel == '101' or channel == '301':
                        logging.info(f" condition => {condition}")
                        if condition:
                            msg = await self.zone_activator(channel, session, tasks, zone, confs[idx], persons)
                        else:
                            break
                    else:
                        msg = await self.zone_activator(channel, session, tasks, zone, confs[idx], persons)

                    logging.info(msg)

                    logging.info(f" {channel} check channel")
                    if channel in self.sv_channel_event:
                        logging.info(f" {channel} event exists")
                        # Overwrite latest human timestamp on a given channel
                        self.sv_channel_event[channel] = dt.datetime.timestamp(dt.datetime.now())
                        break
                    else:
                        # Overwrite latest human timestamp on a given channel
                        logging.info(f" {channel} set channel event")
                        self.sv_channel_event[channel] = dt.datetime.timestamp(dt.datetime.now())
                        # Image saving
                        logging.info(f" {channel} Image saving")
                        imgdir = "frames/" + now.strftime('%Y-%m-%d') + "/" + f"{channel}" + "/"
                        wd = os.path.join("../", imgdir)
                        try:
                            os.makedirs(wd)
                        except FileExistsError:
                            # directory already exists
                            pass

                        # IO data saving
                        drawing = draw[channel]
                        if drawing:
                            img = vis.draw_bboxes(img, boxes, confs, clss)
                        else:
                            pass
                        filesave_timer = time.time()
                        savepath = wd + f"{now.strftime('%H_%M_%S.%f')}_person_"
                        # logging.info(f"Boxes : {type(boxes)}")
                        imgpath = home + "/JetsonSecVision/" + imgdir + f"{now.strftime('%H_%M_%S.%f')}_person_frame.jpg"

                        np.save(wd + f"{now.strftime('%H_%M_%S.%f')}_person_boxes", boxes)
                        np.save(wd + f"{now.strftime('%H_%M_%S.%f')}_person_confs", confs)
                        np.save(wd + f"{now.strftime('%H_%M_%S.%f')}_person_clss", clss)
                        low = 83
                        high = 95
                        quality = high if channel == "201" else low
                        cv2.imwrite(savepath + "frame.jpg", img,
                                    [int(cv2.IMWRITE_JPEG_QUALITY), quality])
                        end = time.time()
                        # logging.info(f" File save time{(end - filesave_timer):.2f}s")

                        # DB data saving
                        data = {
                            "time": f"{timenow}",
                            "persons": str(persons),
                            "channel": f"{channel}",
                            "path": f"{savepath}",
                            "confs": str(confs[idx])
                        }
                        start_time = time.time()
                        self.redisDb.rpush(data['channel'], json.dumps(data))
                        end_time = time.time()
                        # logging.info(f" Redis time {(end_time - start_time):.2f}s")
                        # Trigger front door messenger
                        if channel != '':
                            self.front_door_img_path = imgpath
                            self.telegramChannel = channel_names[channel]
                        break
                idx += 1

    # returns message and adds trigger_zone task to the task list
    async def zone_activator(self, channel, session, tasks, zone, confidence, persons):
        person_counter = f'{persons} persons' if persons > 1 else f'{persons} person'
        msg = f" {channel_names[channel]} - {confidence:.2f} - {person_counter} found in zone {zone} - recording"
        # logging.info(f"Zone Activator : ch {channel} z {zone} z1 {self.zone1} z2 {self.zone2} z3 {self.zone3} z4 {self.zone4} use zones : {bool(self.use_zones)}")
        if bool(self.use_zones):
            if zone == 1:
                if len(self.zone1) == 0:
                    msg = f" {channel_names[channel]} - {confidence:.2f} - {person_counter} found in zone {zone} - start recording"
                    tasks.append(asyncio.ensure_future(self.trigger_zone(session, zone, True)))
                self.zone1[channel] = channel
            elif zone == 2:
                if len(self.zone2) == 0:
                    msg = f" {channel_names[channel]} - {confidence:.2f} - {person_counter} found in zone {zone} - start recording"
                    tasks.append(asyncio.ensure_future(self.trigger_zone(session, zone, True)))
                self.zone2[channel] = channel
            elif zone == 3:
                if len(self.zone3) == 0:
                    msg = f" {channel_names[channel]} - {confidence:.2f} - {person_counter} found in zone {zone} - start recording"
                    tasks.append(asyncio.ensure_future(self.trigger_zone(session, zone, True)))
                self.zone3[channel] = channel
            else:
                if len(self.zone4) == 0:
                    msg = f" {channel_names[channel]} - {confidence:.2f} - {person_counter} found in zone {zone} - start recording"
                    tasks.append(asyncio.ensure_future(self.trigger_zone(session, zone, True)))
                self.zone4[channel] = channel
        else:
            if channel not in self.sv_channel_event:
                logging.info(f" ZONELESS TRIGGER channel {channel}")
                msg = f" {channel_names[channel]} - {confidence:.2f} - {person_counter} found in zone {zone} - start recording"
                tasks.append(asyncio.ensure_future(self.trigger_zone(session, zone, False, channel, True)))
        await asyncio.gather(*tasks)
        return msg

    # There might be some reason the triggers might be high?
    # so we start fresh and set them low
    async def cleanstart(self, session, zone):
        await self.trigger_zone(session, zone, False)

        # The main loop

    async def main(self):
        # conn = aiohttp.TCPConnector(limit=None, ttl_dns_cache=300)
        # async with aiohttp.ClientSession(headers=self.session_auth(), connector=conn) as session:
        # Client Session
        conn = aiohttp.TCPConnector(limit=None, ttl_dns_cache=300)
        session = aiohttp.ClientSession(headers=SecVisionJetson.session_auth(config), connector=conn)
        for i in range(1, 5):
            await self.cleanstart(session, i)
        while True:
            try:
                # logging.info("                    <o_O> Jetson Sec Vision <O_o>                   ")
                mainloop_timer = time.time()
                tasks = []

                # GET data frames
                channel_frames, timer = await af.get_frames(session, self.DVRip, self.chcnt, self.jpeg)

                # Inference tasks on received frames
                for channel, frame in channel_frames:
                    # detect objects in the image
                    await self.detect(frame, self.trt_yolo, 0.65, self.vis, channel, session, tasks)
                end = time.time()

                # See if there was any background work to be done if not resest the gc
                # logging.info(f" Ch Evt => {self.sv_channel_event}")
                # logging.info(f" GC => {self.sv_garbage_collector}")

                for channel in self.sv_garbage_collector:
                    await self.trigger_zone(session, self.determine_zone(channel), False, channel, False)
                self.sv_garbage_collector = []

                # Keep an average of our network speed and only use upto 128 values
                self.network_speed.append(int(self.chcnt) / (end - mainloop_timer - timer))
                if len(self.network_speed) > 128:
                    for i in range(0, 65):
                        self.network_speed.pop(0)

                mainloop_end_timer = time.time()
                # Logging for 
                logging.info(
                    f" InfLoop => {(end - mainloop_timer - timer):.2f}s @ {int(self.chcnt) / (end - mainloop_timer - timer):.2f}fps")
                logging.info(f" WrkLoop => {(mainloop_end_timer - mainloop_timer):.3f}s")
            except Exception as ex:
                # we don't really care if it breaks, just try again...
                logging.error(f" ML crash => {ex} {traceback.format_exc()}")
                pass


if __name__ == '__main__':
    cwd = os.path.dirname(os.path.abspath(__file__))
    # Settings
    settings = os.path.join(cwd, 'settings.ini')
    config = configparser.ConfigParser()
    config.read(settings)
    # Logging
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
    # DB
    redisDb = redis.Redis(host='localhost', port=6379, db=0)
    # App
    app = SecVisionJetson(config, redisDb)
    initworkers(app)
    loop = uvloop.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(app.main())
