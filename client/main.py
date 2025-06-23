from queue import Queue
import logging
import threading
import time
import json
from buffer import Buffer
import network
import sensors
from config import config

from spatial_object_perso import Camera

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# networking queues and buffers
q_net_out, q_net_in = Queue(), Buffer()


## SENSORS 
sensorsList = []
### Phone
if config.getboolean('sensors', 'phone'):
    q_phone_out, q_phone_in = Buffer(), Queue()
    phone = sensors.Phone(q_phone_in, q_phone_out)
    sensorsList.append(phone)
    phone.run()


### Can Bus
if config.getboolean('sensors', 'canbus'):
    q_can_out = Buffer()
    canbus = sensors.CANBus(q_can_out)
    sensorsList.append(canbus)
    canbus.run()

### Object Detection
if config.getboolean('sensors', 'camera'):
    cam = Camera()
    t = threading.Thread(target=cam.ObjectDetection, args=(q_net_in,))
    t.start()


## NETWORK
int = config.get('network', 'interface')
if int == "uart":
    ### UART (LoRa)
    uart_service = network.UartService(q_net_in, q_net_out)
    uart_service.run()
elif int == "http":
    ### HTTP (WiFi, Ethernet, LTE/5G)
    http_service = network.HTTPService(q_net_in, q_net_out)
    http_service.run()
else:
    print("config error: invalide network interface")
    exit(1)


message = {'device-id':config.get('general', 'device_id'), 'type':1}

def __sendWorker():
    while True:
        waitTime = float(config.get('network', 'time_between_send'))
        time.sleep(waitTime)
        lastSent = {}
        # only send a new status update if latest sensor data changed (except timestamp)
        if lastSent != message:
            lastSent = message.copy()
            q_net_in.put(lastSent)
            
threading.Thread(target=__sendWorker).start()

## Polling all sensors and update the dict containing all the information
while True:
    message['timestamp'] = time.time()
    coordChanged=False
    for sensor in sensorsList:
        try:
            sample = sensor.getLatestSample()
            for key, value in sample.items():
                if key != "timestamp":
                    if key not in message or value != message[key]:
                        message[key] = value
                    if key in ['latitude', 'longitude', 'azimuth']:
                        coordChanged = True
        except sensors.NoSampleAvailable:
            pass
    
    if coordChanged:
        cam.setCoordinates(message['latitude'], message['longitude'], message['azimuth'])

