import asyncio
import logging
import time


async def get_frames(session, ip, channels, jpeg):
    channel_frames = []
    start = time.time()

    async def one_frame(ch):
        ch += 1
        request_url = f"http://{ip}/ISAPI/Streaming/channels/{ch}02/picture?videoResolutionWidth=1920" \
                      f"&videoResolutionHeight=1080&snapShotImageType=JPEG "
        async with session.get(request_url) as response:
            if response.status == 200:
                img = await response.read()
                # nparr = numpy.fromstring(img, numpy.uint8)
                # img_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                # img_np = cv2.imdecode(numpy.frombuffer(img, numpy.uint8), -1)
                img_np = jpeg.decode(img, 1)
                # height, width, channels = img_np.shape
                # logging.info(f"{width}x{height} {channels}")
                # img_np = numpy.array(Image.open(io.BytesIO(img)))
                channel_frames.append((f"{ch}01", img_np))

    coros = [one_frame(_) for _ in range(int(channels))]
    await asyncio.gather(*coros)
    end = time.time()
    logging.info(f" GET DATA - {end - start}")
    return channel_frames, end - start
