from queue import Queue
import logging
import threading
import time
import json

from entities import Vehicule, Object, ObjectSet
from buffer import Buffer
import network
import sensors

from spatial_object_perso import ObjectDetection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

## CONFIG
TIME_BETWEEN_SAMPLES=1 # in seconds
TIME_BETWEEN_NETWORK_SEND=10 # in seconds 

DEVICE_ID="jetson1"

UART_DEVICE = "/dev/ttyTHS1"
UART_SPEED = 115200


## SENSORS 
### Phone
q_phone_out, q_phone_in = Buffer(), Queue()
phone = sensors.Phone(q_phone_in, q_phone_out)


### Can Bus
q_can_out = Buffer()
canbus = sensors.CANBus(q_can_out)

sensorsList = [phone, canbus]

## NETWORK
q_net_out, q_net_in = Queue(), Buffer()
### LoRa
#uart_service = network.UartService(UART_DEVICE, UART_SPEED, q_net_in, q_net_out)
#uart_service.run()
### HTTP (WiFi, Ethernet, LTE/5G)
http_service = network.HTTPService("10.42.0.88", 5000, q_net_in, q_net_out)
http_service.run()

canbus.run()
phone.run()

### Object Detection
q_object = Queue()
t = threading.Thread(target=ObjectDetection, args=(q_net_in,))
#t.start()


message = {'device-id':DEVICE_ID, 'type':1}
while True:
    
    time.sleep(TIME_BETWEEN_NETWORK_SEND)
    message['timestamp'] = time.time()

    for sensor in sensorsList:
        try:
            sample = sensor.getLatestSample()
            for key, value in sample.items():
                if key != "timestamp":
                    message[key] = value
        except sensors.NoSampleAvailable:
            pass
    
    # network input queue
    q_net_in.put(json.dumps(message) + "\n")

    # DEBUG
    #print(q_net_in.get())
    
