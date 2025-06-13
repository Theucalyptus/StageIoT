from queue import Queue
import logging
import threading
import time
import json

from entities import Vehicule, Object, ObjectSet
from buffer import Buffer
import network
import sensors

import detection_oakd

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
### Object Dpassetection
q_object = Queue()
#t = threading.Thread(target=detection_oakd.ObjectDetection, args=[q_object])
#t.start()
### Can Bus
q_can_out = Buffer()
canbus = sensors.CANBus(q_can_out)

sensorsList = [phone, canbus]

## NETWORK
### LoRa
q_uart_out, q_uart_in = Queue(), Buffer()
#uart_service = network.UartService(UART_DEVICE, UART_SPEED, q_uart_in, q_uart_out)
#uart_service.run()

canbus.run()
phone.run()

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
    q_uart_in.put(json.dumps(message))

    # DEBUG
    print(q_uart_in.get())
    