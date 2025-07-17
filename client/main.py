from queue import Queue
import logging
import threading
import time
import json
from buffer import Buffer
from recorder import CSVWriter
import network
import sensors
from config import config
import signal
from common.msgTypes import MessageTypes

from spatial_object_perso import Camera

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# networking queues and buffers
q_netMain_out, q_netMain_in = Queue(), Buffer()
q_netAlt_out, q_netAlt_in = Queue(), Buffer()

## SENSORS 
sensorsList = []
### Phone
if config.getboolean('sensors', 'phone'):
    q_phone_out, q_phone_in = Buffer(), Buffer()
    phone = sensors.Phone(q_phone_in, q_phone_out)
    sensorsList.append(phone)
    phone.run()


### Can Bus
if config.getboolean('sensors', 'canbus'):
    q_can_out = Buffer()
    canbus = sensors.CANBus(q_can_out)
    sensorsList.append(canbus)
    canbus.run()

### Static values override
static = sensors.Static()
sensorsList.append(static)


### Object Detection
cam = None
if config.getboolean('sensors', 'camera'):
    cam = Camera()
    cam.run(q_netMain_in)

#Save stat
statWriter = CSVWriter("statnetwork")
statWriter.prepare(['timestamp','device-id', 'networkLatency', 'failedMsgTX', 'totalMsgTX', 'failedMsgRX', 'totalMsgRX'])

objDevWriter = CSVWriter("objects_devices")
objDevWriter.prepare(['timestamp', 'device', 'object', 'netDelay'])

## NETWORK
MAIN_NET = None
ALT_NET = None
def __enableNetInterface(interface, q_in, q_out):
    if interface != '':
        if interface == "uart":
            ### UART (LoRa)
            uart_service = network.UartService(q_in, q_out)
            uart_service.run()
            return uart_service
        elif interface == "http":
            ### HTTP (WiFi, Ethernet, LTE/5G)
            http_service = network.HTTPService(q_in, q_out)
            http_service.run()
            return http_service
        elif interface=="websocket":
            ws_service = network.WebSocketService(q_in, q_out)
            ws_service.run()
            return ws_service
        else:
            logger.critical("config: invalide network interface:", interface)
            exit(1)
    else:
        return None

main = config.get('network', 'main_interface')
alternative = config.get('network', 'alt_interface')
MAIN_NET = __enableNetInterface(main, q_netMain_in, q_netMain_out)
ALT_NET = __enableNetInterface(alternative, q_netAlt_in, q_netAlt_out)

message = {'device-id':config.get('general', 'device_id'), 'type':MessageTypes.DEVICE_UPDATE, 'latitude':0.0, 'longitude':0.0, 'azimuth':0.0}


exit = False

def __sendWorker():

    waitTime = MAIN_NET.time_between_send
    if ALT_NET:
        waitTime = min(MAIN_NET.time_between_send, ALT_NET.time_between_send)

    lastSentData = {}
    lastSendTime = 0.0
    
    global exit
    while not exit:
        time.sleep(waitTime)
        # only send a new status update if latest sensor data changed (except timestamp)
        if lastSentData != message:
            now = time.time() 
            message['timestamp'] = now
            if MAIN_NET.isUp and now >= lastSendTime+MAIN_NET.time_between_send-1:
                lastSentData = message.copy() # copy to compare with next message
                q_netMain_in.put(lastSentData.copy()) # send a copy, because aliasing + the network service may edit the message
                lastSendTime = now
            elif ALT_NET != None and ALT_NET.isUp:
                if now >= lastSendTime+ALT_NET.time_between_send-1:
                    lastSentData = message.copy()
                    q_netAlt_in.put(lastSentData.copy())
                    lastSendTime = now
                else:
                    pass
            else:
                logger.info("all networks are down. the data is still logged localy.")

        if MAIN_NET.isUp:
            near_things = MAIN_NET.getNearbyObjects()
            now = time.time()
            nearObjs, nearDevs = near_things
            latencyObj= 0
            latencyDev = 0
            for lo in nearObjs.values():
                for o in lo:
                    d={}
                    latencyObj = now - o['timestamp']
                    d['timestamp'] = o['timestamp']
                    d['device']= o['seenby']
                    d['object'] = o['id']
                    d['netDelay'] = latencyObj
                    objDevWriter.saveSample(d)
                    print("object (seen by " + o["seenby"] + ") total latency", latencyObj)
            for d in nearDevs.values():
                latencyDev = now - d['timestamp']
                da={}
                da['timestamp'] = d['timestamp']
                da['device']=d['device-id']
                da['object'] = ""
                da['netDelay'] = latencyDev
                objDevWriter.saveSample(da)
                print("device " + d["device-id"] + " total latency", latencyDev)

            stat_data = {'networkLatency': MAIN_NET.networkLatency,'failedMsgTX': MAIN_NET.failedMsgTX, 'totalMsgTX': MAIN_NET.totalMsgTX,
                         'failedMsgRX': MAIN_NET.failedMsgRX, 'totalMsgRX': MAIN_NET.totalMsgRX}
            near_things.append(stat_data)

            data_network= {}
            data_network['timestamp'] = now
            data_network['device-id'] = config.get('general', 'device_id')
            data_network['networkLatency'] = stat_data['networkLatency']
            data_network['failedMsgTX'] = stat_data['failedMsgTX']
            data_network['totalMsgTX'] = stat_data['totalMsgTX']
            data_network['failedMsgRX'] = stat_data['failedMsgRX']
            data_network['totalMsgRX'] = stat_data['totalMsgRX']
            serialized_objects = json.dumps(near_things)
            statWriter.saveSample(data_network)
            q_phone_in.put(serialized_objects)


t = threading.Thread(target=__sendWorker)
t.start()

def stop(*args):
    logger.info("Graceful exit. Stopping all workers and saving data (can take a few seconds)")
    global exit
    if exit:
        return # function was already called.
    exit = True
    for sensor in sensorsList:
        logger.debug("waiting for sensor " + sensor.name + " to stop...")
        sensor.stop()
    
    if cam:
        logger.debug("Waiting for camera worker to stop...")
        cam.stop()
    
    logger.debug("Waiting for main network to stop ...")
    MAIN_NET.stop()
    if ALT_NET:
        logger.debug("Waiting for alt network to stop...")
        ALT_NET.stop()
    statWriter.end()
    objDevWriter.end()
    logger.debug("Waiting for send worker to stop...")
    t.join()

signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)

## Polling all sensors and update the dict containing all the information
def run():

    MAIN_FREQUENCY = 10 # Hz (ie all sensor will be sampled at this frequency.)
    samplePeriod_ns = 1_000_000_000 / MAIN_FREQUENCY

    global exit
    while not exit:
        start = time.perf_counter_ns()
        coordChanged=False
        for sensor in sensorsList:
            try:
                sample = sensor.getLatestSample()
                for key, value in sample.items():
                    if key != "timestamp":
                        if key not in message or value != message[key]:
                            message[key] = value
                        if key in ['latitude', 'longitude', 'azimuth']:
                            coordChanged = True
            except sensors.NoSampleAvailable:
                pass
        
        if coordChanged and cam:
            try:
                cam.setCoordinates(message['latitude'], message['longitude'], message['azimuth'])
            except KeyError as k:
                logger.warning("Trying to set coordinates but missing value for" + str(k.args))

        d = time.perf_counter_ns() - start
        if d < samplePeriod_ns:
            time.sleep((samplePeriod_ns-d) / 1_000_000_000)
        else:
            logger.warning("main loop is behind schedule. Maybe try to reduce the sampling frequency (or optimize my slow code)")
        
if __name__=="__main__":
    try:
        run()
    except KeyboardInterrupt:
        stop()