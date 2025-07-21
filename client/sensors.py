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
from recorder import CSVWriter, NullWriter, DBWriter

logger = logging.getLogger(__name__)

class  NoSampleAvailable(Exception):
    pass

class Sensor:
    
    def __init__(self, name, dataRecorder=NullWriter):
        self.name = name
        self.data = {}
        self.datatypes = {}
        self._addDataField("timestamp", str)
        self.data["timestamp"] = "0.0"

        self.outbuffer = Buffer()
        self.recorder = dataRecorder(self.name)
        self.stopVar = False # indicates if the sensor should be logging or not

    def _addDataField(self, name, type):
        self.data.setdefault(name)
        self.datatypes[name] = type

    def __registerDataFields(self):
        raise NotImplementedError

    def newSampleHandler(self, sample):
        present = set()
        #if 'timestamp' in sample:
        #    if float(sample['timestamp']) < float(self.data['timestamp']):
        #                logger.warning('recevied an out-of-order sample, ignoring')
        #                return
            
        for field in self.data:
            if field in sample:            
                self.data[field] = self.datatypes[field](sample[field])
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

    def stop(self):
        self.stopVar = True
        self.thread.join()

class Phone(Sensor):

    PORT = 6789

    def __init__(self, Q_in, Q_out, name="phone"):
        if config.getboolean('sensors.phone', 'logData'):
            super().__init__(name, dataRecorder=CSVWriter)
        else:
            super().__init__(name)
        self.q_in = Q_in
        self.q_out = Q_out
        self.__registerDataFields()
        self.recorder.prepare(self.data.keys())

        self.isUp = False

    def __registerDataFields(self):
        """
            Registers all data fields provided by the sensor
        """
        self._addDataField("latitude", float)
        self._addDataField("longitude", float)
        self._addDataField("altitude", float)
        self._addDataField("speed", float)
        self._addDataField("roll", float)
        self._addDataField("pitch", float)
        self._addDataField("azimuth", float)
        
    def __conn_handler(self, websocket):
        try:
            self.isUp = True
            while not self.stopVar:
                if not self.q_in.empty():
                    data = self.q_in.get()
                    logger.info("sending " + str(data))
                    websocket.send(data)

                data = websocket.recv(timeout=None)
                #logger.info("received " + str(data))
                try:
                    deserialized = json.loads(data)
                    self.newSampleHandler(deserialized)
                except json.JSONDecodeError as e:
                    logger.warning("received malformed data " + str(e))
            websocket.close()
        except ConnectionClosedError:
            logger.info("connection closed unexpectedly")
        except ConnectionClosedOK:
            logger.info("connection closed by pair ok")
        except TimeoutError:
            logger.info("connection timeout")
        self.isUp = False

    def __run(self):
        logger.info("websocket server listening on port " + str(Phone.PORT))
        self.__server  = serve(self.__conn_handler, "0.0.0.0", Phone.PORT, ping_interval=5, ping_timeout=5)
        self.__server.serve_forever()

    def run(self):
        self.thread = threading.Thread(target=self.__run, args=())
        self.thread.start()

    def stop(self):
        logger.info("websocket server stoping")
        self.__server.shutdown()
        self.recorder.end()
        super().stop()


class CANBus(Sensor):

    def __init__(self, Q_out, name="canbus"):
        if config.getboolean('sensors.canbus', 'logData'):
            super().__init__(name, dataRecorder=CSVWriter)
        else:
            super().__init__(name)
        
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
        while not self.stop:
            if not self.q_in.empty():
                data = self.q_in.get()
                logger.info("CAN sending " + str(data))
                self.__send(data)
            self.__recv()
        print("TODO: can bus end")

    def run(self):
        self.thread = threading.Thread(target=self.__run, args=())
        self.thread.start()


class Static(Sensor):

    def __strToType(text):
        m = text[-1]
        if m == 'i':
            return int(text[:-1])
        elif m == 'f':
            return float(text[:-1])
        elif m == 's':
            return text[:-1]
        elif m == 'b':
            return bool(text)
        else:
            return None
    
    def __init__(self):
        super().__init__("static")
        self.data = {}
        dataRaw = config['sensors.static']
        for k in dataRaw:
            self.data[k] = Static.__strToType(dataRaw[k])

    def getLatestSample(self):
        # This function will always return data, as we want static variable to override all sensors
        # in case the user wants to log locally some values, but send another one instead
        sample = {}
        sample['timestamp'] = time.time()
        for (k, v) in self.data.items():
            sample[k] = v
        return sample
    
    def stop(self):
        pass # nothing to stop for static