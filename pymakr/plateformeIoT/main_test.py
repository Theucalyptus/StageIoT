import uos
from network import LoRa
import socket
import time
import ubinascii
import pycom
import utime
from machine import Timer


# create an OTAA authentication parameters, change them to the provided credentials
app_eui = ubinascii.unhexlify('70B3D57ED003A322')
app_key = ubinascii.unhexlify('3072E1FA34B866583697F768C9F9BA13')
#uncomment to use LoRaWAN application provided dev_eui
dev_eui = ubinascii.unhexlify('70b3d5499809d4ea')
#parametres LoRa
sf = 7
coding_rate=LoRa.CODING_4_5

mode = 1 # 1 = LoRaWAN pour se connecter à la passerelle, 2 = LoRa pour se connecter à une autre carte

pycom.heartbeat(False)
print("=================== Starting program =======================")
print("edited by antleb (dyn timestamp, sensor+objs)")

nb = 0

def loraWAN():

    def rx_callback(lora):
        lora.events()
        data = s.recv(64)
        if data :
            print(data)

    lora = LoRa(mode=LoRa.LORAWAN, region=LoRa.EU868)
    
    lora.callback(LoRa.RX_PACKET_EVENT,rx_callback)
    lora.join(activation=LoRa.OTAA, auth=(dev_eui, app_eui, app_key), timeout=0)


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
    while 1 :
        print("sending sensor bytes")
        # msg type                       #timestamp,                                #lat#long#altitude#luminosity#angVx,y,z#pressure
        sendData = bytes("2", "utf-8") + bytes(str(time.time()), "utf-8") + bytes(",43.6,1.4,245.3,70.5,0.1,0.2,0.3,1005.22,0.4,0.5,0.6,90.1,91.2,15.7,45.0,21.3", "utf-8")
        s.send(sendData)
        time.sleep(10)
        
        print("sending objects bytes")
        # msg type                      #timestamp,                                 #X,#Y, #Z, #object label
        sendData = bytes("3", "utf-8") + bytes(str(time.time()), "utf-8") + bytes(";43.51,1.451,3,maison;4,5,6,obj_lbl2", "utf-8")
        s.send(sendData)
        time.sleep(10)

loraWAN()

    
