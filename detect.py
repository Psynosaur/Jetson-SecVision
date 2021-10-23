#!/usr/bin/python3
#
# Copyright (c) 2020, NVIDIA CORPORATION. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
#
import datetime
import io
import jetson.inference
import jetson.utils

import argparse
import os
import sys
import cv2
import time

import aiofiles
import numpy
from PIL import Image
import PIL
import aiohttp
import asyncio
import async_frames as af
import configparser
import base64

# parse the command line
parser = argparse.ArgumentParser(description="Locate objects in a live camera stream using an object detection DNN.",
                                 formatter_class=argparse.RawTextHelpFormatter)

parser.add_argument("--network", type=str, default="ssd-mobilenet-v2",
                    help="pre-trained model to load (see below for options)")
parser.add_argument("--overlay", type=str, default="none",
                    help="detection overlay flags (e.g. --overlay=box,labels,conf)\nvalid combinations are:  'box', 'labels', 'conf', 'none'")
parser.add_argument("--threshold", type=float, default=0.5, help="minimum detection threshold to use")

try:
    opt = parser.parse_known_args()[0]
except:
    print("")
    parser.print_help()
    sys.exit(0)

# load the object detection network
net = jetson.inference.detectNet(opt.network, sys.argv, opt.threshold)
cwdpath = os.getcwd()


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
            for channel, frame, bytes in channel_frames:
                # detect objects in the image (without overlay)
                detections = net.Detect(frame, overlay=opt.overlay)
                now = datetime.datetime.now()
                for detection in detections:
                    # person classID in COCO is 1
                    if detection.ClassID == 1 and detection.Confidence >= 0.80:
                        print(f">>>>{channel} - {now.strftime('%H:%M:%S.%f')}_person found - {detection.Confidence}")
                        imgdir = "frames/" + now.strftime('%Y-%m-%d') + "/" + f"{channel}" + "/"
                        wd = os.path.join(cwdpath, imgdir)
                        # print(wd)
                        try:
                            os.makedirs(wd)
                        except FileExistsError:
                            # directory already exists
                            pass
                        # slow file save...
                        # jetson.utils.saveImageRGBA(wd + f"{now.strftime('%H_%M_%S.%f')}_person_frame_{detection.Confidence}.jpg", frame, 1920, 1080)
                        # fast file save...
                        image = Image.open(io.BytesIO(bytes))
                        image.save(wd + f"{now.strftime('%H_%M_%S.%f')}_person_frame_{detection.Confidence}.jpg")
            end = time.time()
            print(f"Full loop - {end - start}")


if __name__ == '__main__':
    cwd = os.path.dirname(os.path.abspath(__file__))
    settings = os.path.join(cwd, 'settings.ini')
    config = configparser.ConfigParser()
    config.read(settings)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(main())
