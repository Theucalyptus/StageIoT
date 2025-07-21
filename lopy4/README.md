# Lopy 4 Program
This program is designed to be run on a Lopy 4 wireless module. This program is a simple uart-to-LoRa bridge. It receives messages on a UART-interface and relays them via LoRa.
Two version of this program are provided: 
- the GPIO that uses GPIO pins for UART communication
- the USB variant that uses the USB port on the Expansion Board to communicate with the client
The GPIO is intended to be used with an embedded device like a Nvidia Jetson or a Raspberry Pi, while the USB version is more intended for testing with a computer.

## Status LED Colors 
- Blue fixed: booting
- Orange blinking: awaiting LoRa connectivity
- Green fixed: LoRa connected
- Violet fixed: LoRa TX
- White blinking: UART Tx