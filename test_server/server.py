import asyncio
import aiohttp_jinja2
import jinja2
import pathlib
import time
import os
import aiohttp.web
import threading
from aiohttp import WSCloseCode
import janus
from timetable_logic import next_buses,create_ptv_api
import json
import logging
import datetime

# debug level, can be debug, error, info, ...
loglevel = "debug"
log = logging.getLogger()

HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 8080))
BASE_DIR = pathlib.Path(__file__).parent

""" this is kept simple, some opportunities to generalise are deliberately skipped.
However, I pass app as a parameter to functions even though it is a global, which is silly 
"""

#
loop = asyncio.get_event_loop()
app = aiohttp.web.Application(loop=loop) #type: aiohttp.web.Application
app['websockets'] = []


def init_logging(conf=None):
    log_level_conf = "debug"
    if conf and "loglevel" in conf:
        log_level_conf = conf['loglevel']
    numeric_level = getattr(logging, log_level_conf.upper(), None)
    logging.basicConfig(level=numeric_level, format='%(message)s')
    log.error("Logging level: {}".format(log_level_conf))


def setup_static_routes(app):
    app.router.add_static('/static/',
                          path=BASE_DIR / 'static',
                          name='static')


@aiohttp_jinja2.template('index.html')
async def homepage_handler(request):
    return {'msg':'Hello world!'}


async def websocket_handler(request):
    # this is a consumer, it reacts to websocket connections
    #print('Websocket connection starting')
    ws = aiohttp.web.WebSocketResponse()
    await ws.prepare(request)
    print('Websocket connection ready')
    app['websockets'].append(ws)

    try:
        wakeup_event = app.get('send_blocking_messages_wakeup_event',None)
        if wakeup_event:
            wakeup_event.set()
            print ("Sent wakeup")
    except Exception as e:
        raise


    async for msg in ws: #incoming messages, we just wait for messages that may appear
        print(msg)
        if msg.type == aiohttp.WSMsgType.TEXT:
            print(msg.data)
            if msg.data == 'close':
                await ws.close()
            else:
                await ws.send_str(msg.data + '/answer')

    # we exited the loop...
    app['websockets'].remove(ws)
    print('Websocket connection closed')
    return ws


async def send_websocket_messages():
    """ runs in the background and sends messages to all clients.
    This is asyncio code; in this app, we send messages from a queue populated by non-async code using janus"""
    try:
        while True:
            await asyncio.sleep(60)
            for subscriber in app['websockets']:
                pass
                #await subscriber.send_str("Hello!")
                #print ("sent simple message")
    except asyncio.CancelledError:
        pass
    finally:
        print("Cleanup")


async def send_websocket_messages_from_queue():
    """ runs in the background and sends messages to all clients.
    This is a janus queue, so it can be filled by sync code"""
    try:
        while True:
            item = await app['message_queue'].async_q.get()
            if len (app['websockets']) == 0:
                log.debug(f"{datetime.datetime.now()}: there is message to send but no clients")
            for subscriber in app['websockets']:
                await subscriber.send_str(item) #assume is it json.dumps already
                log.info (f"{datetime.datetime.now()}: sent message from queue ")
    except asyncio.CancelledError:
        pass
    finally:
        print("Cleanup 2")



def blocking_put_messages_in_queue(app:aiohttp.web.Application, kill_event:threading.Event,wakeup_event:threading.Event):
    """ Uses a janus queue to put messages into a queue that an async function will fetch and process
    this will fetch timetable info and put into int"""
    while True:
        wakeup_event.clear()
        if kill_event.is_set():
            log.info("Killing the blocking task")
            return
        log.info(f"{datetime.datetime.now()}: update bus data in blocking background task")
        msg = format_next_bus_message(ptv_client=app.ptv_client)
        log.debug(f"{datetime.datetime.now()}: putting updated bus data in janus queue")
        app['message_queue'].sync_q.put(msg)
        log.debug(f"{datetime.datetime.now()}: put updated bus data in janus queue")
        wakeup_event.wait(60)


def one_time_put_message_in_queue():
    msg = format_next_bus_message()
    app['message_queue'].sync_q.put(msg)
    print("one time put messaage in queue")


def format_next_bus_message(ptv_client)->dict:
    para_departures = next_buses(ptv_client=ptv_client,stop_name="Para")
    para_departures_str = [dt.strftime("%H:%M") for dt in para_departures]
    time.sleep(1)
    lawson_departures = next_buses(ptv_client=ptv_client,stop_name="Lawson")
    lawson_departures_str = [dt.strftime("%H:%M") for dt in lawson_departures]
    return json.dumps({'Para':para_departures_str,'Lawson':lawson_departures_str})


async def start_background_tasks(app): #no await in here
    #app['send_messages'] = app.loop.create_task(send_websocket_messages())
    app['send_messages_from_queue'] = app.loop.create_task(send_websocket_messages_from_queue())

    kill_event = threading.Event()
    wakeup_event = threading.Event()
    app['send_blocking_messages'] = app.loop.run_in_executor(None, blocking_put_messages_in_queue, app, kill_event,wakeup_event)
    app['send_blocking_messages_kill_event'] = kill_event #used to send a signal to kill
    app['send_blocking_messages_wakeup_event'] = wakeup_event  # used to send a signal to kill


async def cleanup_background_tasks(app):
    #app is passed by the library
    app['send_messages'].cancel()
    await app['send_messages']
    app['send_messages_from_queue'].cancel()
    await app['send_messages_from_queue']


async def on_shutdown(app):
    """ the server won't exit if open websocket connections are not stopped"""
    for subscriber in app['websockets']:
        await subscriber.close(code=WSCloseCode.GOING_AWAY,
                       message='Server shutdown')

    print('cancelling')
    print(app['send_blocking_messages'].cancel())
    app['send_blocking_messages_kill_event'].set()
    app['send_blocking_messages_wakeup_event'].set()


def main():
    init_logging()
    setup_static_routes(app=app)
    aiohttp_jinja2.setup(
        app, loader=jinja2.PackageLoader('test_server', 'templates')) #see also FilesSstemLoader
    app.ptv_client = create_ptv_api()
    app.router.add_route('GET', '/', homepage_handler)
    app.router.add_route('GET', '/ws', websocket_handler)
    app['message_queue'] = janus.Queue(loop=loop) #janus is a sync/async queue
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    app.on_shutdown.append(on_shutdown)
    aiohttp.web.run_app(app, host=HOST, port=PORT)


if __name__ == '__main__':
    main()