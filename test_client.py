import time 
import json
import requests
from requests.exceptions import ConnectionError as connErr
import random
from math import cos, sin, pi

# this script simulates a client/device using the HTTP endpoint of the web app
# it send periodically new device status update (ie sensors data)
# and object detection

URL = "http://localhost:5000/post_data"
RANDOM_PACKET_LOSS = False
PACJET_LOSS_CHANCE = 10 # percentage

delta = 0.0005

try:
    i=0
    while True:
        start = time.time()
        
        try:
            data = {}
            data['device-id'] = "simu1"
            data['type'] = 1
            data['timestamp'] = time.time()
            data['speed'] = 8.33
            data['latitude'] = 43.602120
            data['longitude'] = 1.454893
            data['altitude'] = 205.34
            data['pitch'] = 0.0
            data['roll'] = 0.0
            data['azimuth'] = 5
            data['msgNumber'] = i
            jsonData = json.dumps(data)
            x = requests.post(URL, data=jsonData)
            
            time.sleep(0.5)

            data = {}
            data['device-id'] = "simu2"
            data['type'] = 1
            data['timestamp'] = time.time()
            data['speed'] = 8.33
            data['latitude'] = -0.0004
            data['longitude'] = 0.0004
            data['altitude'] = 205.34
            data['pitch'] = 0.0
            data['roll'] = 0.0
            data['azimuth'] = 5
            data['msgNumber'] = i
            jsonData = json.dumps(data)
            x = requests.post(URL, data=jsonData)

            time.sleep(0.5)
        
        except connErr:
            print("host not up")

        i+=1

        try:
            dataObjet = {}
            dataObjet["msgNumber"] = i
            dataObjet['device-id'] = "simu1"
            dataObjet['type'] = 2
            dataObjet['timestamp'] = time.time()
            dataObjet['objects'] = []
            o = {}
            o['latitude'] = 43.602214 + delta*(1-2*random.random())
            o['longitude'] = 1.455175 + delta*(1-2*random.random())
            o['label'] = "bus"
            o['id'] = 5
            dataObjet['objects'].append(o)
            jsonData = json.dumps(dataObjet)
            x = requests.post(URL, data=jsonData)

            time.sleep(0.5)

            o = {}
            dataObjet['device-id'] = "simu2"
            dataObjet['timestamp'] = time.time()
            o['latitude'] = 0.00003 # + delta*(1-2*random.random())
            o['longitude'] = 0.00003 # + delta*(1-2*random.random())
            o['label'] = "boat"
            o['id'] = 3
            dataObjet['objects'] = [o]
            jsonData = json.dumps(dataObjet)
            x = requests.post(URL, data=jsonData)
            

        except connErr:
            print("host not up")
            time.sleep(3)

        if RANDOM_PACKET_LOSS:
            r = random.randint(0, 99) 
            if r < PACJET_LOSS_CHANCE: #10% de chande de créer des pertes de paquets
                nbPacketLoss = random.randint(1, 20)
                print("simulating a loss of", nbPacketLoss, "packets")
                i+=nbPacketLoss
        i = (i+1)%256

except KeyboardInterrupt:
    print("exit")