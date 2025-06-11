import logging
import threading
from bluedot.btcomm import BluetoothServer, BluetoothAdapter

logger = logging.getLogger(__name__)

from enum import Enum


class BluetoothMsgType(Enum):
    STATUS_UPDATE = 1

def handleMessage(message):
    logger.info("handleMessage with msg: "+message)
    type = BluetoothMsgType(int(message[0]))
    print(type)
    content = message[1:]
    if type == BluetoothMsgType.STATUS_UPDATE:
        logger.info("handleMessage STUB !!")
        data = content.split(",")
        return type, data
    else:
        logger.warning("Unkown message type for message " + message)

class BluetoothService:

    def __init__(self, Q_in, Q_out):
        self.q_in = Q_in
        self.q_out = Q_out
        self.s = BluetoothServer(self.__data_received, auto_start=False, when_client_connects=self.__client_connectd,
                                 when_client_disconnects=self.__client_disconnected)

    def run(self):
        logger.info("Launching BL service")
        self.a = BluetoothAdapter()
        logger.info("Allowing pairing indefinitly")
        self.a.allow_pairing(None)
        logger.info("Awaiting bluetooth connection")
        self.s.start()
        self.sender_thread = threading.Thread(target=self.__sender)
        self.sender_thread.start()

    def __client_connectd(self):
        logger.info("Client connected : " + self.s.client_address)

    def __client_disconnected(self):
        logger.info("Client disconnected")

    def __data_received(self, data):
        logger.info("received " + str(data).removesuffix("\n"))
        self.q_out.put(data)

    def __sender(self):
        while True:
            if self.s.client_connected:
                msg = self.q_in.get(block=True, timeout=None)
                self.__send_data(msg)
        
    def __send_data(self, data):
        logger.info("sending " + str(data))
        self.s.send(data)