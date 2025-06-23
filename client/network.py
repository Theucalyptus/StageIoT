import serial
import logging
import threading
import requests
from config import config
from requests.exceptions import ConnectionError
import json
import time
from common import lora

logger = logging.getLogger(__name__)

class UartService:

    def __init__(self, q_in, q_out):
        global config
        device = config.get('network.uart', 'device')
        speed = int(config.get('network.uart', 'speed'))

        logger.info("uart setup using device " + device + " bauds " + str(speed))
        self.serial = serial.Serial(device, speed)
        self.outBuffer = ""
        self.q_in = q_in
        self.q_out = q_out

    def run(self):
        logger.info("uart service running")
        self.worker = threading.Thread(target=self.__run)
        self.worker.start()

    def __run(self):
        while True:
            self.__recv()
            if not self.q_in.empty():
                self.__send(self.q_in.get())
            
    def __send(self, msg):
        logger.info("uart sending " + str(msg))
        try:
            self.serial.write(lora.data_to_lora(msg))
        except lora.MissingDataField:
            logger.error("uart lora serializer failed with missing data (can happen before all sensors provided their first sample)")
    def __recv(self):
        try:
            msg = self.serial.read_all().decode("utf-8")
            if msg:
                msgl = msg.split('\n')
                if len(msgl) == 1:
                    self.outBuffer += msg
                elif len(msgl) > 1:
                    self.outBuffer += msgl[0]
                    logger.info("uart received " + self.outBuffer)
                    self.q_out.put(self.outBuffer)
                    for t in msgl[1:-1]:
                        logger.info("uart received " + t)
                        self.q_out.put(t)
                    self.outBuffer = msgl[-1]
        except UnicodeDecodeError as e:
            logger.warning('uart message invalid ' + str(e))
                
class HTTPService:

    host = config.get('network.http', 'host')
    port = config.get('network.http', 'port')

    baseUrl = "http://"+host+":"+port
    pushUrl = baseUrl+"/post_data"
    connCheckUrl = baseUrl + "/connectivityCheck"

    def __init__(self, q_in, q_out):

        self.q_in = q_in
        self.q_out = q_out

        self.isUp = False
        self.lastConnCheck = None

    def run(self):
        logger.info("http service running with endpoint " + HTTPService.pushUrl)
        self.worker = threading.Thread(target=self.__run)
        self.worker.start()

    def __run(self):
        while True:
            # check for connectivity
            while not self.isUp:
                try:
                    # perform conn check
                    r = requests.get(HTTPService.connCheckUrl)
                    print("todo: process time response !")
                    self.isUp = True
                except:                    
                    logger.info('http service awaiting for internet')
                    time.sleep(5)


            # connection is UP
            if not self.q_in.empty():
                self.__send(json.dumps(self.q_in.get()) + "\n")
                

    def __send(self, msg):
        logger.info("http sending " + msg.removesuffix("\n"))
        try:
            requests.post(HTTPService.pushUrl, data=msg)
        except ConnectionError:
            self.isUp = False # connection seems to be down
            self.q_in.put(msg) # re-adding the message to the queue
            logger.warning("http send failed. Network may be down")
