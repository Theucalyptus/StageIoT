from queue import Queue
from machine import UART
from network import LoRa
import pycom
import time
import socket
import ubinascii
import struct
import _thread

def isfloat(num):
    try:
        float(num)
        return True
    except ValueError:
        return False

dataFromUart = ""
oldTimer = time.time() # timer pour le uart heartbeat
Q_out = Queue(2)
Q_outObj = Queue(1)

print("initialisation")

####### Initialisation LED #######
pycom.heartbeat(False) # Desactivation du mode led clignotante
pycom.rgbled(0x000011) # Couleur led bleue pour signaler le démarrage

####### Initialisation UART #######
uart = UART(1, baudrate=115200) # Tx : P3, Rx : P4

####### Initialisation LoRa #######
lora = LoRa(mode=LoRa.LORAWAN, region=LoRa.EU868) # Initialise LoRa en mode LORAWAN.

app_eui = '70B3D57ED003A322'
app_key = '3072E1FA34B866583697F768C9F9BA13'
dev_eui = '70b3d5499809d4ea'

app_eui_unhex = ubinascii.unhexlify(app_eui)
app_key_unhex = ubinascii.unhexlify(app_key)
dev_eui_unhex = ubinascii.unhexlify(dev_eui)

####### Connexion LoRa #######
lora.join(activation=LoRa.OTAA, auth=(dev_eui_unhex, app_eui_unhex, app_key_unhex), timeout=0) # Connexion au réseau LoRaWAN

while not lora.has_joined():        # Attente de connexion au réseau LoRaWAN
    time.sleep(2.5)
    pycom.rgbled(0x110000)          # Couleur led rouge pour signaler la non connexion
    uart.write("01"+dev_eui.lower()+"\n") 
    #print("envoi eui")
    print('Not yet joined...')

pycom.rgbled(0x001100)              # Couleur led verte pour signaler la connexion
print('Joined')

####### Initialisation socket LoRa #######
s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
s.setsockopt(socket.SOL_LORA, socket.SO_DR, 5) # fixer le débit de données LoRaWAN
s.setblocking(True)

def send():
    """
    Envoie via LoRa les éléments de la queue
    """
    while True:
        if not Q_out.empty():
            data = Q_out.get()
            print("sending sensor data", data)
            pycom.rgbled(0x110011)
            s.send(data)
            time.sleep(0.1)
            pycom.rgbled(0x000000)

        if not Q_outObj.empty():
            data = Q_outObj.get()
            print("sending objects data", data)
            s.send(data)


_thread.start_new_thread(send, ())
####### Programme principal #######

dataFromUart = uart.read(uart.any()).decode('utf-8').split('\n') # flush uart


while 1 :
    #dataFromUart = ""
    dataFromUart = ["2"+str(time.time()) + ",43.6,1.4,245.3,70.5,0.1,0.2,0.3,1005.22,0.4,0.5,0.6,90.1,91.2,15.7,45.0,21.3"]

    #while uart.any() != 0:
    if True:
        time.sleep(0.1)
        print("trying to read from uart")
        #dataFromUart = uart.read(uart.any()).decode('utf-8').split('\n')

        for msg in dataFromUart:
            if len(msg)>2:
                a = msg[0]
                if a == '2':
                    if Q_out.full():
                        Q_out.get()
                    Q_out.put(msg)
                elif a == '3':
                    if Q_outObj.full():
                        Q_outObj.get()
                    Q_outObj.put(msg)
            time.sleep(3)
                    
    if (time.time() > oldTimer + 5):
        print("writing to uart")
        uart.write("01"+dev_eui.lower()+"\n")
        oldTimer = time.time()
        pycom.rgbled(0x111111)
        time.sleep(0.1)
        pycom.rgbled(0x000000)


