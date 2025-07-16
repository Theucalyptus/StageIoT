from queue import Queue, Empty
from websockets.sync.server import serve
from websockets.exceptions import *
import logging
import time
import json

logger = logging.getLogger(__name__)

Q_output, Q_ing=None, None
stopVar=False

def conn_handler(websocket):
    print("Connection opened")
    
    global stopVar
    try:
        while not stopVar:
            try:
                data = websocket.recv(timeout=0)
                t = time.time()
                data = json.loads(data)
                # if we have a sending timestamp, compute network delay
                if "timestamp" in data: 
                    data["netDelay"] = (t - data["timestamp"]) * 1000
                Q_output.put(data)
            except TimeoutError:
                pass
            try:
                if not Q_ing.empty():
                    data = Q_ing.get_nowait()
                    websocket.send(data, text=True)
            except Empty:
                pass # Q_ing.empty() does not guarentee that .get() will instantly return
                     # so we use get_nowait and catch, as we don't want to stall the thread
        websocket.close()
    except ConnectionClosedError:
        logger.info("connection closed unexpectedly")
    except ConnectionClosedOK:
        logger.info("connection closed by pair ok")
    except TimeoutError:
        logger.info("connection timeout")


    print("Connection ended")

def WSnode(config, Q_out : Queue, Q_in: Queue):
    
    print("Starting WebSocket node")
    global Q_output
    global Q_ing
    Q_output = Q_out
    Q_ing = Q_in
    
    try:
        p = int(config["ws_port"])
        server =  serve(conn_handler, "0.0.0.0", p)
        server.serve_forever()
    except Exception as e:
        logger.critical("config error for ws_port " + str(e))