from queue import Queue
from machine import UART
from network import LoRa, WLAN
import pycom
import time
import socket
import ubinascii
import struct
import _thread
import uos

uos.dupterm(None)

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

## LOPY 10
app_eui = '70B3D57ED003A322'
app_key = '3072E1FA34B866583697F768C9F9BA13'
dev_eui = '70b3d5499809d4ea'


app_eui_unhex = ubinascii.unhexlify(app_eui)
app_key_unhex = ubinascii.unhexlify(app_key)
dev_eui_unhex = ubinascii.unhexlify(dev_eui)

####### LoRa Service #######
def LoRa_service(Q_out, Q_in):
    lora = LoRa(mode=LoRa.LORAWAN, region=LoRa.EU868) # Initialize LoRa in LORAWAN mode.
    lora.join(activation=LoRa.OTAA, auth=(dev_eui_unhex, app_eui_unhex, app_key_unhex), timeout=0) # Start LoRaWA connection
    while not lora.has_joined():        # Waiting on LoRaWAN connectivity
        Q_in.put('LoRa: not yet joined...\n')
        pycom.rgbled(0x110A00)          # Blinking orange LED
        time.sleep(0.2)
        pycom.rgbled(0x000000)
        time.sleep(1.8)

    # joined
    Q_in.put('LoRa: up\n')
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
            Q_in.put("LoRa: tx :" + str(data) + "\n")
            __send(data)

####### UART Service #######
def UART_service(Q_out, Q_in):
    uart = UART(0, baudrate=115200) # default = USB on expansion board
    oldTimer = time.time() # uart heartbeat timer
    while True:
        time.sleep(1)
        data = uart.readline()
        if data != None and len(data)>1:
            Q_in.put("UART: rx : " + str(data) + "\n")
            if Q_out.full():
                Q_out.get()
            Q_out.put(data)

        if not Q_in.empty():
            msg = Q_in.get()
            uart.write(msg)

        if (time.time() > oldTimer + 10):
            msg = "heartbeat "+dev_eui.lower()+"\n"
            uart.write(msg)
            oldTimer = time.time()
            pycom.rgbled(0x111111) # white blinking LED = uart Tx
            time.sleep(0.1)
            pycom.rgbled(0x000000)

####### MAIN #######

# network output queue
Q_out = Queue(4)
Q_in = Queue(4)

_thread.start_new_thread(LoRa_service, (Q_out,Q_in))
UART_service(Q_out, Q_in) # could be in a thread as well
    

print("main: program exit")