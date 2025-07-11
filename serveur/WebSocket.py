from queue import Queue
from websockets.sync.server import serve
from websockets.exceptions import *
import logging

logger = logging.getLogger(__name__)

Q_output=None
stopVar=False



def conn_handler(websocket):
    print("Connection opened")
    
    global stopVar
    try:
        while not stopVar:
            try:
                data = websocket.recv(timeout=None)
                Q_output.put(data)
            except TimeoutError:
                pass
        websocket.close()
    except ConnectionClosedError:
        logger.info("connection closed unexpectedly")
    except ConnectionClosedOK:
        logger.info("connection closed by pair ok")
    except TimeoutError:
        logger.info("connection timeout")


    print("Connection ended")

def WSnode(config, Q_out : Queue):
    
    print("Starting WebSocket node")
    global Q_output
    Q_output = Q_out
    
    try:
        p = int(config["ws_port"])
        server =  serve(conn_handler, "0.0.0.0", p)
        server.serve_forever()
    except Exception as e:
        logger.critical("config error for ws_port " + str(e))