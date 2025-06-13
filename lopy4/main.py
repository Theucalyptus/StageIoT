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

pycom.heartbeat(False) # Desactivation du mode led clignotante
pycom.rgbled(0x000011) # Couleur led bleue pour signaler le démarrage

## LOPY 10
app_eui = '70B3D57ED003A322'
app_key = '3072E1FA34B866583697F768C9F9BA13'
dev_eui = '70b3d5499809d4ea'

## LOPY 9
# app_eui = '70B3D57ED003A324'
# app_key = '7F94B66B572B110BA2C9622D430B9EDA'
# dev_eui = '70b3d5499f211d32'

## LOPY BOX JETSON
# app_eui = '7532159875321598'
# app_key = '11CBA1678ECF54273F5834C41D82E57F'
# dev_eui = '70B3D57ED0068A6F'


app_eui_unhex = ubinascii.unhexlify(app_eui)
app_key_unhex = ubinascii.unhexlify(app_key)
dev_eui_unhex = ubinascii.unhexlify(dev_eui)

####### LoRa Service #######
def LoRa_service(Q_out):
    lora = LoRa(mode=LoRa.LORAWAN, region=LoRa.EU868) # Initialize LoRa in LORAWAN mode.
    lora.join(activation=LoRa.OTAA, auth=(dev_eui_unhex, app_eui_unhex, app_key_unhex), timeout=0) # Start LoRaWA connection
    while not lora.has_joined():        # Waiting on LoRaWAN connectivity
        print('LoRa: not yet joined...')
        pycom.rgbled(0x110A00)          # Blinking orange LED
        time.sleep(0.2)
        pycom.rgbled(0x000000)
        time.sleep(1.8)

    # joined
    print('LoRa: up')
    pycom.rgbled(0x002200)              # Green LED upon succesfull connection


    ###### LoRa Socket Initialisation #######
    s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
    s.setsockopt(socket.SOL_LORA, socket.SO_DR, 5) # fixer le débit de données LoRaWAN
    s.setblocking(True)

    def __send(data):
        pycom.rgbled(0x110011) # violet light to indicate lora tx
        s.send(data)
        pycom.rgbled(0x000000)

    ### Infinite send loop
    while True:
        if not Q_out.empty():
            data = Q_out.get()
            print("LoRa: tx :", data)
            __send(data)

####### UART Service #######
def UART_service(Q_out):
    uart = UART(1, baudrate=115200, pins=["P11", "P10"]) # Tx (green): P11, Rx (yellow) : P10
    oldTimer = time.time() # timer pour le uart heartbeat
    while True:
        time.sleep(5)
        try:
            data = uart.read(uart.any()).decode('utf-8').split('\n')
            print("UART: rx :", data)
            for msg in data:
                if len(msg)>1:
                    if Q_out.full():
                        Q_out.get()
                    Q_out.put(msg)
        except UnicodeError:
            print("UART: rx UnicodeError")

        if (time.time() > oldTimer + 10):
            msg = "heartbeat "+dev_eui.lower()+"\n"
            print("UART: tx :", msg)
            uart.write(msg)
            oldTimer = time.time()
            pycom.rgbled(0x111111) # white blinking LED = uart Tx
            time.sleep(0.1)
            pycom.rgbled(0x000000)

####### MAIN #######

# inter-service communication queues
Q_out = Queue(4)

_thread.start_new_thread(LoRa_service, (Q_out,))
UART_service(Q_out) # could be in a thread as well
    

print("main: program exit")