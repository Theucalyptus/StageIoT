from queue import Queue, Empty
from websockets.sync.server import serve
from websockets.exceptions import *
import time
import json



Q_output, Q_in_dict=None, None
stopVar=False

next_connection_id=0

def conn_handler(websocket):
    global next_connection_id

    id = next_connection_id
    next_connection_id+=1
    print("connection opened id " + str(id))
    global stopVar
    
    Q_in_dict[id] = Queue()
    
    try:
        while not stopVar:
            try:
                data = websocket.recv(timeout=0)
                t = time.time()
                data = json.loads(data)
                # if we have a sending timestamp, compute network delay
                if "timestamp" in data: 
                    data["netDelay"] = (t - data["timestamp"]) * 1000
                Q_output.put((id, data))
            except TimeoutError:
                pass
            try:
                if not Q_in_dict[id].empty():
                    data = Q_in_dict[id].get_nowait()
                    websocket.send(data, text=True)
            except Empty:
                pass # Q_ing.empty() does not guarentee that .get() will instantly return
                     # so we use get_nowait and catch, as we don't want to stall the thread
        websocket.close()
    except ConnectionClosedError:
        print("connection closed unexpectedly")
    except ConnectionClosedOK:
        print("connection closed by pair ok")
    except TimeoutError:
        print("connection timeout")


    print("Connection ended id " + str(id))

def WSnode(config, Q_out : Queue, Q_in):
    
    print("Starting WebSocket node")
    global Q_output
    global Q_in_dict
    Q_output = Q_out
    Q_in_dict = Q_in
    
    try:
        p = int(config["ws_port"])
        server =  serve(conn_handler, "0.0.0.0", p)
        server.serve_forever()
    except Exception as e:
        logger.critical("config error for ws_port " + str(e))