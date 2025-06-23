import logging
import threading
import json
import time
import csv
import datetime
from os.path import isfile
from queue import Empty
import can
from config import config
from websockets.sync.server import serve
from websockets.exceptions import *
from buffer import Buffer
from recorder import CSVWriter

logger = logging.getLogger(__name__)

class  NoSampleAvailable(Exception):
    pass

class Sensor:
    
    def __init__(self, name, dataRecorder):
        self.name = name
        self.data = {}
        self.data.setdefault("timestamp")
        self.outbuffer = Buffer()
        self.recorder = dataRecorder(self.name)

    def __registerDataFields(self):
        raise NotImplementedError

    def newSampleHandler(self, sample):
        present = set()
        for field in self.data:
            if field in sample:
                self.data[field] = sample[field]
                present.add(field)
        
        for field in self.data:
            if not field in present:
                logger.warning("data field " + field + " was not present in sample.")
        for field in sample:
            if not field in present:
                logger.warning("data field " + field + " was in sample and was unexpected.")

        self.recorder.saveSample(self.data)
        self.outbuffer.put(self.data)

    def getLatestSample(self):
        try:
            return self.outbuffer.get()
        except Empty:
            raise NoSampleAvailable

    def __run(self):
        raise NotImplementedError

    def run(self):
        raise NotImplementedError

class Phone(Sensor):

    PORT = 6789

    def __init__(self, Q_in, Q_out, name="phone", dataRecorder=CSVWriter):
        super().__init__(name, dataRecorder)
        self.q_in = Q_in
        self.q_out = Q_out
        self.__registerDataFields()
        self.recorder.prepare(self.data.keys())

    def __registerDataFields(self):
        """
            Registers all data fields provided by the sensor
        """
        self.data.setdefault("latitude")
        self.data.setdefault("longitude")
        self.data.setdefault("altitude")
        self.data.setdefault("speed")
        self.data.setdefault("roll")
        self.data.setdefault("pitch")
        self.data.setdefault("azimuth")
        
    def __conn_handler(self, websocket):
        try:
            while True:
                if not self.q_in.empty():
                    data = self.q_in.get()
                    logger.info("sending " + str(data))
                    websocket.send(data)
                try:
                    data = websocket.recv(timeout=0)
                    logger.info("received " + str(data))
                    try:
                        deserialized = json.loads(data)
                        self.newSampleHandler(deserialized)
                    except json.JSONDecodeError as e:
                        logger.warning("received malformed data " + str(e))


                except TimeoutError:
                    pass
        
        except ConnectionClosedError:
            logger.info("connection closed")
        except TimeoutError:
            logger.info("connection timeout")

    def __run(self):
        logger.info("websocket server listening on port " + str(Phone.PORT))
        with serve(self.__conn_handler, "0.0.0.0", Phone.PORT) as server:
            server.serve_forever()

    def run(self):
        self.thread = threading.Thread(target=self.__run, args=())
        self.thread.start()

class CANBus(Sensor):

    def __init__(self, Q_out, name="canbus", dataRecorder=CSVWriter):
        super().__init__(name, dataRecorder)
        self.q_out = Q_out
        
        interface = config.get('sensors.canbus', 'interface')
        channel = config.get('sensors.canbus', 'channel')
        bitrate = config.getint('sensors.canbus', 'bitrate')        
        self.bus = can.Bus(interface=interface, channel=channel, bitrate=bitrate)

    def __registerDataFields(self):
        raise NotImplementedError

    def __send(self, data):
        msg = can.Message(arbitration_id=0xC0FFEE, data=data, is_extended_id=True)
        try:
            self.bus.send(msg)
            print(f"Message sent on {self.bus.channel_info}")
        except can.CanError:
            print("Message NOT sent")

    def __deserialize(self, data):
        raise NotImplementedError

    def __recv(self):
        # filters = [
        #     {"can_id": 0x451, "can_mask": 0x7FF, "extended": False},
        #     {"can_id": 0xA0000, "can_mask": 0x1FFFFFFF, "extended": True},
        # ]

        for msg in self.bus:
            data = msg.data
            logger.info("CAN recv " + str(data))
            deserialized = self.deserialize(data)
            self.newSampleHandler(deserialized)

    def __run(self):
        logger.info("CAN bus monitor started")                     
        if not self.q_in.empty():
            data = self.q_in.get()
            logger.info("CAN sending " + str(data))
            self.__send(data)
        self.__recv()

    def run(self):
        self.thread = threading.Thread(target=self.__run, args=())
        self.thread.start()