import datetime
import io

import argparse
import os
import sys
import time

import numpy
from PIL import Image
import PIL
import aiohttp
import asyncio
import async_frames_cv as af
import configparser
import base64

from pathlib import Path
import argparse

# the tensorrt_demos directory, please build this first
sys.path.append('/home/jetsonman/tensorrt_demos/utils')

import cv2
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


def loop_and_detect(image, trt_yolo, conf_th, vis, channel):
    img = image
    boxes, confs, clss = trt_yolo.detect(img, conf_th)
    img = vis.draw_bboxes(img, boxes, confs, clss)
    idx = 0
    for cococlass in clss:
        # print(f"{channel} : {cococlass}")
        # person classID in COCO is 1
        # confs
        if cococlass == 0 and confs[idx] >= 0.7:
            now = datetime.datetime.now()
            print(f">>>>{channel} - {now.strftime('%H:%M:%S.%f')}_person found - {confs[idx]}")
            imgdir = "frames/" + now.strftime('%Y-%m-%d') + "/" + f"{channel}" + "/"
            wd = os.path.join(cwdpath, imgdir)
            print(wd)
            try:
                os.makedirs(wd)
            except FileExistsError:
                # directory already exists
                pass
            # fast file save...
            cv2.imwrite(wd + f"{now.strftime('%H_%M_%S.%f')}_person_frame.jpg", img)
        idx += 1


async def main():
    authkey = f"{config.get('DVR', 'username')}:{config.get('DVR', 'password')}"
    auth_bytes = authkey.encode('ascii')
    base64_bytes = base64.b64encode(auth_bytes)
    auth = base64_bytes.decode('ascii')
    headers = {"Authorization": f"Basic {auth}"}
    async with aiohttp.ClientSession(headers=headers) as session:
        while True:
            start = time.time()
            channel_frames = await af.get_frames(session, config.get('DVR', 'ip'), config.get('DVR', 'channels'))
            for channel, frame in channel_frames:
                # detect objects in the image
                loop_and_detect(frame, trt_yolo, 0.3, vis, channel)
            end = time.time()
            print(f"Full loop - {end - start}")


if __name__ == '__main__':
    cwd = os.path.dirname(os.path.abspath(__file__))
    settings = os.path.join(cwd, 'settings.ini')
    config = configparser.ConfigParser()
    config.read(settings)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(main())
