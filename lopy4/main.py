from queue import Queue
from machine import UART
from network import LoRa, WLAN
import pycom
import time
import socket
import ubinascii
import struct
import _thread


# Disable wifi to reduce interference with the Jetson's wifi
wlan = WLAN()
wlan.deinit()

def isfloat(num):
    try:
        float(num)
        return True
    except ValueError:
        return False

pycom.heartbeat(False) # Turning off LED heartbeat
pycom.rgbled(0x000011) # Blue LED indicating boot

## LOPY BOX JETSON
app_eui = '7532159875321598'
app_key = '11CBA1678ECF54273F5834C41D82E57F'
dev_eui = '70B3D54995284D61'


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
    s.setsockopt(socket.SOL_LORA, socket.SO_DR, 5) # set the LoRa bandwith
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
    DELIMITER = bytes('\n\n\n\n', 'utf-8')

    uart = UART(1, baudrate=115200, pins=["P11", "P10"]) # Tx (green): P11, Rx (yellow) : P10
    oldTimer = time.time() # uart heartbeat timer
    
    def __sendU(msgBytes):
        uart.write(msgBytes+DELIMITER)
    
    def __addQ(data):
        if Q_out.full():
            Q_out.get()
        Q_out.put(data)
        #__sendU(data) ## ECHO
    
    tempBuffer = b''
    while True:
        time.sleep(0.1)
        msg = uart.read()
        if msg:
            msgl = msg.split(DELIMITER)
            if len(msgl) == 1:
                tempBuffer += msg
            elif len(msgl) > 1:
                tempBuffer += msgl[0]
                __addQ(tempBuffer)
                for t in msgl[1:-1]:
                    __addQ(t)
                tempBuffer = msgl[-1]

        if (time.time() > oldTimer + 10):
            msg = "heartbeat "+dev_eui.lower()
            print("UART: tx :", msg, "len:", len(msg))
            __sendU(bytes(msg, 'utf-8'))
            pycom.rgbled(0x111111) # white blinking LED = uart Tx
            time.sleep(0.1)
            pycom.rgbled(0x000000)
            oldTimer = time.time()


####### MAIN #######

# network output queue
Q_out = Queue(4)
   
_thread.start_new_thread(LoRa_service, (Q_out,))
UART_service(Q_out) # could be in a thread as well
    

print("main: program exit")