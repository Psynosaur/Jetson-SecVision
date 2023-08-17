import asyncio
import logging
import time
import traceback
import simplejpeg


async def one_frame(session, ch, url, fetch_time, decode_time, jpeg):
    # start_one_frame = time.time()
    semaphore = asyncio.Semaphore(8)
    try:
        async with semaphore:
            async with session.get(url) as response:
                if response.status == 200:
                    fetch_start = time.time()
                    img = await response.read()
                    fetch_time.append(time.time() - fetch_start)
                    # img_np = cv2.imdecode(numpy.frombuffer(img, numpy.uint8), -1)
                    decode_start = time.time()
                    # img_np = jpeg.decode(img, 1)
                    img_np = simplejpeg.decode_jpeg(img, colorspace='BGR')
                    decode_time.append(time.time() - decode_start)
                    return f"{ch}01", img_np
            # HTTPX
            # r = await session.get(url)
            # img = r.content
            # img_np = jpeg.decode(img, 1)
            # return f"{ch}01", img_np
    except Exception as ex:
        # we don't really care if it breaks, just try again...
        logging.error(f" Fetch crash => {ex} {traceback.format_exc()}")
        pass


async def get_frames(session, ip, channels, jpeg):
    channel_frames = []
    start = time.time()
    tasks = []
    fetch_time = []
    decode_time = []

    # task_start = time.time()
    for channel in range(1, int(channels) + 1):
        url = f"http://{ip}/ISAPI/Streaming/channels/{channel}01/picture?videoResolutionWidth=1920" \
              f"&videoResolutionHeight=1080&snapShotImageType=JPEG"
        tasks.append(asyncio.ensure_future(one_frame(session, channel, url, fetch_time, decode_time, jpeg)))
    # logging.info(f" TL => {time.time() - task_start:.3f}s ")

    # logging.info(f" JUST BEFORE GATHER - {time.time() - start:.3f}s")
    channel_frames = await asyncio.gather(*tasks, return_exceptions=True)
    # logging.info(f" JUST AFTER GATHER  - {time.time() - start:.3f}s")
    # logging.info(f" FT => {sum(fetch_time):.3f}s")
    # logging.info(f" DT => {sum(decode_time):.3f}s")
    end = time.time()
    # gather_time = (end - start)-sum(fetch_time)-sum(decode_time)
    # logging.info(f" GT => {gather_time:.3f}s")
    # logging.info(f" Sum {gather_time + sum(fetch_time)+sum(decode_time):.3f}")

    # logging.info(f" GetData => {end - start:.3f}s, FT {sum(fetch_time):.3f}s, DT {sum(decode_time):.3f}s")
    return channel_frames, end - start

