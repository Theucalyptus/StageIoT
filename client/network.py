import serial
import logging
import threading

logger = logging.getLogger(__name__)

class UartService:

    def __init__(self, device, speed, q_in, q_out):
        logger.info("setup using device " + device + " bauds " + str(speed))
        self.serial = serial.Serial(device, speed)
        self.outBuffer = ""
        self.q_in = q_in
        self.q_out = q_out

    def run(self):
        logger.info("service running")
        self.worker = threading.Thread(target=self.__run)
        self.worker.start()

    def __run(self):
        while True:
            self.__recv()
            if not self.q_in.empty():
                self.__send(self.q_in.get())
            
    def __send(self, msg):
        logger.info("sending " + msg)
        self.serial.write(bytes(msg, 'utf-8'))
        
    def __recv(self):
        msg = self.serial.read_all().decode("utf-8")
        if msg:
            msgl = msg.split('\n')
            if len(msgl) == 1:
                self.outBuffer += msg
            elif len(msgl) > 1:
                self.outBuffer += msgl[0]
                logger.info("received " + self.outBuffer)
                self.q_out.put(self.outBuffer)
                for t in msgl[1:-1]:
                    logger.info("received " + t)
                    self.q_out.put(t)
                self.outBuffer = msgl[-1]
                