import uos
from network import LoRa
import socket
import time
import ubinascii
import pycom
import utime
from machine import Timer

# create an OTAA authentication parameters, change them to the provided credentials

## LOPY 9
app_eui = '70B3D57ED003A324'
app_key = '7F94B66B572B110BA2C9622D430B9EDA'
dev_eui = '70b3d5499f211d32'

		

app_eui_unhex = ubinascii.unhexlify(app_eui)
app_key_unhex = ubinascii.unhexlify(app_key)
dev_eui_unhex = ubinascii.unhexlify(dev_eui)


pycom.heartbeat(False)
print("=================== Starting program =======================")
print("edited by antleb (dyn timestamp, sensor+objs) fix1")

def loraWAN():
    def rx_callback(lora):
        lora.events()
        data = s.recv(64)
        if data :
            print(data)

    lora = LoRa(mode=LoRa.LORAWAN, region=LoRa.EU868)
    lora.callback(LoRa.RX_PACKET_EVENT,rx_callback)
    lora.join(activation=LoRa.OTAA, auth=(dev_eui_unhex, app_eui_unhex, app_key_unhex), timeout=0)

    # wait until the module has joined the network
    while not lora.has_joined():
        pycom.rgbled(0x101000)
        time.sleep(0.3)
        pycom.rgbled(0x000000)
        time.sleep(0.3)
        
    print('Joined')
    pycom.rgbled(0x001000)
    # create a LoRa socket
    s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)

    # set the LoRaWAN data rate
    s.setsockopt(socket.SOL_LORA, socket.SO_DR, 5)

    # make the socket blocking
    # (waits for the data to be sent and for the 2 receive windows to expire)
    s.setblocking(True)
    
    # send some data
    while 1:
        print("sending sensor bytes")
        # msg type                       #timestamp,                         #lat   #long #altit #lumi angVx, y,  z      pressure  accX accY  accZ  angle azimu disrec humi  temp                      
        sendData = bytes("2", "utf-8") + bytes(str(time.time()), "utf-8") + bytes(",43.59, 1.41, 133.3, 14.5, 10.1, 10.2, 10.3, 1013.07, 10.4, 10.5, 10.6, 90.1, 91.2, 15.7, 45.0, 21.3".strip(), "utf-8")
        s.send(sendData)
        time.sleep(10)
        
        print("sending objects bytes")
        # msg type                      #timestamp,                                 #lati #longi #label
        sendData = bytes("3", "utf-8") + bytes(str(time.time()), "utf-8") + bytes(";43.591,1.4099,bus", "utf-8")
        s.send(sendData)
        time.sleep(10)

loraWAN()

    
