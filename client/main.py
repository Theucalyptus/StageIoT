import logging.config
from queue import Queue
from signal import pause
import logging

import time
import tcp as net
import uart

from device import Device

logging.basicConfig(level=logging.DEBUG)

### BLUETOOTH
q_net_out, q_net_in = Queue(), Queue()
net_service = net.TCPServer(q_net_in, q_net_out)
net_service.run()


### UART
UART_device = "THS1"
UART_speed = 115200
q_uart_out, q_uart_in = Queue(), Queue()
uart_service = uart.UartService(UART_device, UART_speed, q_uart_in, q_uart_out)
uart_service.run()

device = Device()
objects = []

### MAIN
while True:
    # process all incoming bluetooth msg
    while not q_net_out.empty():
        data = q_net_out.get()
        print("wifi recv", data)
        print("sending to lopy via uart")
        q_uart_in.put(data)

