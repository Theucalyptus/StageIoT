import json
import time

from websockets.sync.client import connect


with connect("ws://localhost:6789") as websocket:
        while True:            
            data = dict()
            data["timestamp"] = time.time()
            data["latitude"] = 45.3
            data["longitude"] = 1.3
            data["altitude"] = 195.3
            data["speed"] = 34.5
            data["pitch"] = 195.3
            data["roll"] = 34.5

            serialized = json.dumps(data)

            with open("message.json", 'w') as f:
                  f.write(serialized)

            websocket.send(serialized)
            time.sleep(5)

