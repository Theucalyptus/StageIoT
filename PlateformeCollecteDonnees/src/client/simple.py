import serial

DEVICE="ACM1"
BAUDS=115200


uartPyCom= serial.Serial("/dev/tty"+DEVICE, BAUDS)



def newlineSuffix(str):
    """
    Appends the newline character at the end of a string if it is not already present
    """
    return str if str[-1] == '\n' else str.join('\n')

while True:
    msg = uartPyCom.readline()
    print("msg received from sensors via uart:", msg)

    response = "ma super reponse"
    uartPyCom.write(bytes(newlineSuffix(response), "utf-8"))
