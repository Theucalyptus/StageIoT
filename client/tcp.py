import socket
import logging

logger = logging.getLogger(__name__)

PORT = 6789

class TCPServer:

    

    def __init__(self, Q_in, Q_out):
        self.q_in = Q_in
        self.q_out = Q_out
        self.serveur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serveur.bind(('', PORT))
        self.serveur.listen(1)
        self.client = None
        self.client_addr = None


    def __recv_callback(self, data):
        logger.info("received : " + data)
        self.q_out.put(data)   

    def _send_worder(self):
        while True:
            if(self.client != None):
                msg = self.q_in.get(block=True, timeout=None)
                logger.info("sending " + msg)
                self.client.send(msg)

    def run(self):
        logger.info("tcp socket listening on port " + str(PORT))
        while True:
            client, addr = self.serveur.accept()
            logger.info("connected with " + addr)
            self.client = client
            self.client_addr = addr
            try:
                while True:
                    data = client.recv(1024)
                    self.__recv_callback(data)
            except Exception as e:
                logger.critical(str(e))