from aiohttp import web
import asyncio


def aiohttp_server(obj):
    headers = {
        'Cache-Control': 'no-cache, max-age=0, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '-1'
    }
    def index(request):
        return web.FileResponse("index.html", headers=headers)
    
    def channel_pics(request):
        return web.FileResponse("channel_info.html")

    def latest_data(request):
        data = obj.od[-1]
        return web.json_response(data, headers=headers)

    def latest_pic(request):
        data = obj.od[-1]
        return web.FileResponse(f"{data['path']}frame.jpg", headers=headers)

    def previous_pic(request):
        data = obj.od[-2]
        return web.FileResponse(f"{data['path']}frame.jpg", headers=headers)

    def channel_info(request):
        try:
            ch = '101'
            ch = request.rel_url.query['id']
            page = "1"
            page = request.rel_url.query['page']
            last_nine = []
            # obj.od(SecVision Class.od) is sorted by time,
            data = obj.od
            cnt = 1
            page = 1 if int(page) == 0 else int(page)
            for detection in reversed(data):
                if cnt > (9 * page):
                    break
                if detection['channel'] == ch:
                    last_nine.append(detection)
                    cnt += 1
            
            return web.json_response(last_nine[-9:])
        except KeyError:
            pass

    def channel_pic(request):
        ch = request.rel_url.query['id']
        lastpic = {}
        # obj.od(SecVision Class.od) is sorted by time,
        data = obj.od
        for detection in reversed(data):
            if detection['channel'] == ch:
                lastpic = detection
                break
        return web.FileResponse(f"{lastpic['path']}frame.jpg", headers=headers)

    webapp = web.Application()
    webapp.add_routes([web.static('/frames', "../frames", show_index=True, append_version=True)])
    # webapp.add_routes([web.static('/', "../")])
    webapp.add_routes([web.get('/', index)])
    webapp.add_routes([web.get('/latestdata', latest_data)])
    webapp.add_routes([web.get('/latestpic', latest_pic)])
    webapp.add_routes([web.get('/prevpic', previous_pic)])
    webapp.add_routes([web.get('/channel', channel_pic)])
    webapp.add_routes([web.get('/chaninfo', channel_info)])
    webapp.add_routes([web.get('/history', channel_pics)])
    runner = web.AppRunner(webapp)
    return runner

def run_server(runner):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    loop.run_until_complete(site.start())
    loop.run_forever()