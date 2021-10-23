import asyncio
import io
import numpy
from PIL import Image
import aiohttp
import time
import cv2
import logging

async def get_frames(session, ip, channels):
    channel_frames = []

    start = time.time()
    async def one_frame(ch):
        ch += 1
        # lower resolution version of the images
        # request_url_low =  f"http://{ip}/ISAPI/Streaming/channels/{ch}01/picture"
        # request_url_720p = f"http://{ip}/ISAPI/Streaming/channels/{ch}01/picture?videoResolutionWidth=1280&videoResolutionHeight=720&snapShotImageType=JPEG"
        request_url_1080p = f"http://{ip}/ISAPI/Streaming/channels/{ch}02/picture?videoResolutionWidth=1920&videoResolutionHeight=1080&snapShotImageType=JPEG"
        async with session.get(request_url_1080p) as response:
            if response.status == 200:
                img = await response.read()
                # nparr = numpy.fromstring(img, numpy.uint8)
                # img_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                img_np = cv2.imdecode(numpy.frombuffer(img, numpy.uint8), -1)
                channel_frames.append((f"{ch}01", img_np))

    coros = [one_frame(_) for _ in range(int(channels))]
    await asyncio.gather(*coros)
    end = time.time()
    logging.info(f"GET DATA - {end - start}")
    return channel_frames, end - start
