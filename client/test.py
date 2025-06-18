import json
import time

from websockets.sync.client import connect

while True:
      try:
            with connect("ws://localhost:6789") as websocket:
                  while True:            
                        data = dict()
                        data["timestamp"] = time.time()
                        data["latitude"] = 43.59
                        data["longitude"] = 1.43333
                        data["azimuth"] = 90
                        data["altitude"] = 195.3
                        data["speed"] = 34.5
                        data["pitch"] = 195.3
                        data["roll"] = 34.5

                        serialized = json.dumps(data)

                        websocket.send(serialized)
                        time.sleep(5)

      except Exception:
            pass