import serial
import logging
import threading

logger = logging.getLogger(__name__)

class UartService():

    def __init__(self, device, speed, q_in, q_out):
        logger.info("setup using device " + device + " bauds " + speed)
        self.serial = serial.Serial(device, speed)
        self.q_int = q_in
        self.q_out = q_out

    def run(self):
        logger.info("service running")
        self.worker = threading.Thread(target=self.__run)
        self.worker.start()

    def __run(self):
        while True:
            self.__recv()
            if not self.q_in.empty():
                self.__send(self.q_int.get())
            
    def __send(self, msg):
        logger.info("sending " + msg)
        self.serial.write(msg.join("\n").encode('utf-8'))
        
    def __recv(self):
        msg = self.serial.read_all()
        logger.info("received " + msg)