import serial
import logging
import threading
import requests
from config import config
from requests.exceptions import ConnectionError
import json

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

    def __init__(self, q_in, q_out):
        host = config.get('network.http', 'host')
        port = config.get('network.http', 'port')

        self.url = "http://"+host+":"+port+"/post_data"
        self.q_in = q_in
        self.q_out = q_out

    def run(self):
        logger.info("http service running with endpoint " + self.url)
        self.worker = threading.Thread(target=self.__run)
        self.worker.start()

    def __run(self):
        while True:
            if not self.q_in.empty():
                self.__send(json.dumps(self.q_in.get()) + "\n")
                

    def __send(self, msg):
        logger.info("http sending " + msg.removesuffix("\n"))
        try:
            requests.post(self.url, data=msg)
        except ConnectionError:
            logger.warning("http send failed. Please check internet access and network settings")
