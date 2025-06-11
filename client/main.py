from queue import Queue
import logging
import tcp as net
import uart
import logging
import threading
import time

from entities import Device, Object, ObjectSet
import detection_oakd

logging.basicConfig(level=logging.DEBUG)

### BLUETOOTH
q_net_out, q_net_in = Queue(), Queue()
net_service = net.TCPServer(q_net_in, q_net_out)
net_service.run()


### UART
UART_device = "THS1"
UART_speed = 115200
q_uart_out, q_uart_in = Queue(), Queue()
#uart_service = uart.UartService(UART_device, UART_speed, q_uart_in, q_uart_out)
#uart_service.run()

## Object Detection
q_object = Queue()
#t = threading.Thread(target=detection_oakd.ObjectDetection, args=[q_object])
#t.start()

### MAIN
device = Device()
objSet = ObjectSet()

while True:
    # process all incoming wifi msg
    while not q_net_out.empty():
        data = q_net_out.get()
        msg = data.decode('utf-8').removesuffix('\n')
        print("wifi recv", msg)
        typ, content = int(msg[0]), msg[1:]
        if typ == 1:
            lat, long = content.split(',')

        print("sending to lopy via uart")
        q_uart_in.put(data)

    # process all observed objects
    while not q_object.empty():
        obj = q_object.get()
        new = objSet.addNew(obj)
        if new:
            print("new objectd detected", obj)

    time.sleep(1)
    objSet.printShort()