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


TIMEGAP = 0 # difference between client local time and server time (approx)
            # useful to correct timestamps because the nVidia jetson doesn't
            # a persistent RTC. Though for now works with networks that
            # allow for NTP so shouldn't be needed 

NEARBY_DEFAULT = [{}, {}]

class UartService:

    DELIMITER = bytes('\n\n\n\n', 'utf-8')

    time_between_send = config.getfloat('network.uart', 'time_between_send')

    def __init__(self, q_in, q_out):
        global config
        device = config.get('network.uart', 'device')
        speed = int(config.get('network.uart', 'speed'))
        self.stopVar = False


        logger.info("uart setup using device " + device + " bauds " + str(speed))
        self.serial = serial.Serial(device, speed)
        self.outBuffer = b''
        self.q_in = q_in
        self.q_out = q_out
        self.isUp = True # for LoRa, we don't really have a way to check  if the device has connectivity
                         # so we just assume that it is


        self.failedMsgTX = 0
        self.totalMsgTX = 0
        self.failedMsgRX = 0
        self.totalMsgRX = 0


    def run(self):
        logger.info("uart service running")
        self.thread = threading.Thread(target=self.__run)
        self.thread.start()

    def __run(self):
        while not self.stopVar:
            self.__recv()
            if not self.q_in.empty():
                self.__send(self.q_in.get())
            
    def __send(self, msg):
        logger.info("uart sending " + str(msg))
        try:
            data = lora.data_to_lora(msg)
            #logger.info("uart sending " + str(data))
            self.serial.write(data + UartService.DELIMITER)
        except lora.MissingDataField:
            logger.error("uart lora serializer failed with missing data (can happen before all sensors provided their first sample)")
    def __recv(self):
        msg = self.serial.read_all()
        if msg:
            msgl = msg.split(UartService.DELIMITER)
            if len(msgl) == 1:
                self.outBuffer += msg
            elif len(msgl) > 1:
                self.outBuffer += msgl[0]
                logger.info("uart received " + str(self.outBuffer))
                self.q_out.put(str(self.outBuffer))
                for t in msgl[1:-1]:
                    logger.info("uart received " + str(t))
                    self.q_out.put(str(t))
                self.outBuffer = msgl[-1]

    def getNearbyObjects(self):
        """ Returns a list of nearby objects detected by the device.
        This method is not implemented for UART service.
        """
        logger.warning("uart service does not support getNearbyObjects")
        return NEARBY_DEFAULT

    def stop(self):
        self.stopVar = True
        self.thread.join()

class HTTPService:

    host = config.get('network.http', 'host')
    port = config.get('network.http', 'port')

    baseUrl = "http://"+host+":"+port
    pushUrl = baseUrl+"/post_data"
    connCheckUrl = baseUrl + "/connectivityCheck"
    getObjURL= baseUrl + "/api/nearby_objects/" + config.get('general', 'device_id')

    timeout = config.getfloat('network.http', 'timeout')

    time_between_send = config.getfloat('network.http', 'time_between_send')


    def __init__(self, q_in, q_out):

        self.q_in = q_in
        self.q_out = q_out

        self.stopVar = False
        self.isUp = False
        self.lastConnCheck = None

        self.failedMsgTX = 0
        self.totalMsgTX = 0
        self.failedMsgRX = 0
        self.totalMsgRX = 0

        self.httpLatency=0
        

    def run(self):
        logger.info("http service running with endpoint " + HTTPService.pushUrl)
        self.thread = threading.Thread(target=self.__run)
        self.thread.start()

    def __run(self):
        while not self.stopVar:
            # check for connectivity
            while not self.isUp and not self.stopVar:
                try:
                    # perform conn check
                    r = requests.get(HTTPService.connCheckUrl, timeout=HTTPService.timeout) # sends back the current server time
                    serverTime = float(r.text)
                    print("time gap", abs(time.time() - serverTime))
                    self.isUp = True
                except:                    
                    logger.info('http service awaiting for internet')
                    time.sleep(5)


            # connection is UP
            if not self.q_in.empty():
                self.__send(self.q_in.get())
                

    def __send(self, msg):
        serialized = json.dumps(msg)
        logger.info("http sending " + serialized)
        try:
            self.totalMsgTX+=1
            resp = requests.post(HTTPService.pushUrl, data=serialized, timeout=HTTPService.timeout)
            logger.info("HTTP Tx latency {:.2f}".format(resp.json()['rxDate'] - msg['timestamp']) + "s")
        except ConnectionError:
            self.failedMsgTX+=1
            self.isUp = False # connection seems to be down
            self.q_in.put(msg) # re-adding the message to the queue
            logger.warning("http send failed. Network may be down")

    def getNearbyObjects(self):
        if not self.isUp:
            logger.warning("http service is down. Cannot receive data")
            return NEARBY_DEFAULT
        
        try:
            self.totalMsgRX += 1
            before = time.time()
            r = requests.get(HTTPService.getObjURL, timeout=HTTPService.timeout)
            after = time.time()
            self.httpLatency = after - before
            logger.info("HTTP Rx took {:.2f}".format(after - before) + "s")
            if r.status_code == 200:
                data = r.json()
                #logger.info("http received " + str(data))
                print(data)
                return data
            elif r.status_code == 204 or r.status_code == 404:
                return NEARBY_DEFAULT
            else:
                logger.warning("http received unexpected status code " + str(r.status_code))
        except ConnectionError as e:
            logger.error("http receive failed: " + str(e))
            self.isUp = False
            self.failedMsgRX+=1
            return NEARBY_DEFAULT

    def stop(self):
        if(not (self.totalMsgRX == 0 or self.totalMsgTX == 0)):
            rxSp = 100 * (1 - self.failedMsgRX / self.totalMsgRX)
            txSp = 100 * (1 - self.failedMsgRX / self.totalMsgRX)
            print("RX %: {:0.2f}".format(rxSp), "TX %: {:0.2f}".format(txSp))
        self.stopVar = True
        self.thread.join()