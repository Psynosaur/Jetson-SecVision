import asyncio
import logging
import time


async def get_frames(session, ip, channels, jpeg):
    channel_frames = []
    start = time.time()
    tasks = []

    async def one_frame(session, ch, url):
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    img = await response.read()
                    # img_np = cv2.imdecode(numpy.frombuffer(img, numpy.uint8), -1)
                    img_np = jpeg.decode(img, 1)
                    return f"{ch}01", img_np
        except asyncio.TimeoutError:
            logging.warning(' Request timedout !')
            pass

    for channel in range(1, int(channels)+1):
        url = f"http://{ip}/ISAPI/Streaming/channels/{channel}01/picture?videoResolutionWidth=1920" \
                      f"&videoResolutionHeight=1080&snapShotImageType=JPEG "
        tasks.append(asyncio.ensure_future(one_frame(session, channel, url)))

    channel_frames = await asyncio.gather(*tasks)
    end = time.time()
    # logging.info(f" GET DATA - {end - start:.2f}s")
    return channel_frames, end - start

