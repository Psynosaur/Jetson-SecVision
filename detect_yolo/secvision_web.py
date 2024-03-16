from aiohttp import web
import asyncio
from dateutil import parser
import json
import logging
import simplejpeg

# Configure logging
logging.basicConfig(level=logging.ERROR)


async def aiohttp_server(obj):
    headers = {
        'Cache-Control': 'no-cache, max-age=0, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '-1'
    }

    def index(request):
        return web.FileResponse("index.html", headers=headers)

    def channel_pics(request):
        return web.FileResponse("channel_info.html")

    def redis_keys(request):
        return web.FileResponse("redis_keys.html")

    def latest_data(request):
        try:
            latest = json.loads(obj.redisDb.lindex(f"101", -1))
            date = parser.parse(latest['time'])
            for i in range(1, 9):
                data = obj.redisDb.lindex(f"{i}01", -1)
                json_data = json.loads(data)
                if parser.parse(json_data['time']) > date:
                    date = parser.parse(json_data['time'])
                    latest = json_data
            return web.json_response(latest, headers=headers)
        except Exception as e:
            logging.error(f"Error in latest_data: {e}")
            return web.Response(text="An error occurred", status=500)

    def remove_key(request):
        try:
            key_id = request.rel_url.query['id']
            file_path = request.rel_url.query['path']
            channel = request.rel_url.query['channel']

            # Remove the key from the Redis database
            item = obj.redisDb.lindex(channel, f"-{key_id}")
            print(f"deleting {item}")
            # obj.redisDb.lrem(channel, 0, item)

            # # # Remove the associated files
            # extensions = ["boxes.npy", "clss.npy", "confs.npy", "frame.jpg"]
            # for ext in extensions:
            #     os.unlink(os.path.abspath(f"{file_path}{ext}"))

            return web.json_response({"success": True,
                                      "item": json.dumps(json.loads(item))})
        except Exception as e:
            logging.error(f"Error in remove_key: {e}")
            return web.json_response({"success": False})

    async def detect_person(request):
        data = await request.post()
        img = data['image'].file
        img_np = simplejpeg.decode_jpeg(img.read(), colorspace='BGR')
        return obj.detect_api_frame(img_np, obj.trt_yolo)

    def latest_pic(request):
        try:
            idx = request.rel_url.query['idx']
            idx = 1 if int(idx) == 0 else int(idx)
            latest = json.loads(obj.redisDb.lindex(f"101", (-1) * idx))
            latest_time = parser.parse(latest['time'])
            detections = []
            time_array = []
            for j in range(0, idx):
                for i in range(1, 9):
                    data = obj.redisDb.lindex(f"{i}01", (-1) * (j + 1))
                    json_data = json.loads(data)
                    detections.append(json_data)
                    time_array.append(parser.parse(json_data['time']))
                    if parser.parse(json_data['time']) > latest_time:
                        latest_time = parser.parse(json_data['time'])
                        latest = json_data
            if idx == 2:
                temp_list = set(time_array)
                temp_list.remove(max(temp_list))
                latest_time = max(temp_list)
                for detection in detections:
                    if parser.parse(detection['time']) == latest_time:
                        latest_time = parser.parse(detection['time'])
                        latest = detection

            return web.FileResponse(f"{latest['path']}frame.jpg", headers=headers)
        except Exception as e:
            logging.error(f"Error in latest_pic: {e}")
            return web.Response(text="An error occurred", status=500)

    def channel_info(request):
        try:
            ch = request.rel_url.query['id']
            page = request.rel_url.query['page']
            last_nine = []
            page = 1 if int(page) == 0 else int(page)
            pagesize = -9
            data = obj.redisDb.lrange(ch, page * pagesize, ((page - 1) * pagesize) - 1)
            for detection in reversed(data):
                last_nine.append(json.loads(detection))
            return web.json_response(last_nine)
        except KeyError:
            pass
        except Exception as e:
            logging.error(f"Error in channel_info: {e}")
            return web.Response(text="An error occurred", status=500)

    def channel_pic(request):
        try:
            ch = request.rel_url.query['id']
            data = obj.redisDb.lindex(ch, -1)
            json_data = json.loads(data)
            return web.FileResponse(f"{json_data['path']}frame.jpg", headers=headers)
        except Exception as e:
            logging.error(f"Error in channel_pic: {e}")
            return web.Response(text="An error occurred", status=500)

    webapp = web.Application()
    webapp.add_routes([web.static('/frames', "../frames", show_index=True, append_version=True)])
    webapp.add_routes([web.static('/static', "./", append_version=True)])
    webapp.add_routes([web.get('/', index)])
    webapp.add_routes([web.get('/latestdata', latest_data)])
    webapp.add_routes([web.get('/latestpic', latest_pic)])
    webapp.add_routes([web.get('/channel', channel_pic)])
    webapp.add_routes([web.get('/chaninfo', channel_info)])
    webapp.add_routes([web.get('/history', channel_pics)])
    webapp.add_routes([web.get('/redis', redis_keys)])
    webapp.add_routes([web.post('/detect_person', detect_person)])
    # Add the route for removing keys
    webapp.add_routes([web.delete('/removekey', remove_key)])
    runner = web.AppRunner(webapp)
    return runner


def run_server(runner):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    loop.run_until_complete(site.start())
    loop.run_forever()