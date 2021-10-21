import asyncio
import io
import numpy
from PIL import Image
import aiohttp
import time
import jetson.utils


async def main(authkey, channels):
    channel_frames = []
    start = time.time()
    headers = {"Authorization": f"Basic {authkey}"}
    async with aiohttp.ClientSession(headers=headers) as session:
        async def one_iteration(i):
            i += 1
            # lower resolution version of the images
            # request_url = f"http://192.168.1.102/ISAPI/Streaming/channels/{i}01/picture"
            request_url = f"http://192.168.1.102/ISAPI/Streaming/channels/{i}01/picture?videoResolutionWidth=1920&videoResolutionHeight=1080&snapShotImageType=JPEG"
            async with session.get(request_url) as response:
                if response.status == 200:
                    img = await response.read()
                    img_arr = numpy.array(Image.open(io.BytesIO(img)))
                    np_image = jetson.utils.cudaFromNumpy(img_arr)
                    channel_frames.append((f"{i}01", np_image))

        coros = [one_iteration(_) for _ in range(int(channels))]
        await asyncio.gather(*coros)
        # end = time.time()
        # print(f"GET DATA - {end - start}")
        return channel_frames
