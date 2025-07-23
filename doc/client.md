# Client
The client is indented to be used on an mobile/embedded computer, like a NVidia Jetson or a Raspberry Pi. It collectes data from sensors, logs the data locally and periodicaly sends it over the network.

## Sensors
The two main sensors intended to be used are a (stereoscopic) camera for object detection and a phone (for GPS and orientation). Due to early desing consideration and materiel limitiation, we designed to Phone sensor to be connected using WiFi. The WiFi network can be hosted by both the client or the phone. Hosting the wifi hotspot on the phone allows for 4/5G connectiviy without needing another device.

Data from the sensors are stored in csv files (one per sensor), named after the time of recording and name of the sensor. We also save some additional performance metrics in `statnetwork` (network reliability and neighbourhood requests duration) and `objects_devices` (total system latency, i.e time between a device sending new data to the platfom and this data being received; for earch device and object, for each request)

Each sensor as a thread dedicated to sampling and logging its own data. A main thread gathers data from all sensors and prepares messages to be sent other the network on a periodic basis (the periode can be set in the config file; only if the data has changed since the last upload). In case the main network is down, we try the alternative network.
Objects report messages are handled separatly. For now, objects report messages are sent *only sent via the main network* (as we assume the use of LoRa as the backup, which doesn't offer enough bandwith for it to be practical). 
We filter the main types of objects that we want (like car, person, motocycle...) and periodically send object report messages, containing all tracked objects.

## Camera
Objects detected by the camera are approximatly located using a combination of the GPS coordinates and azimuth provided by the phone, and the position of objects relative to the camera. This means that the phone should point in the same direction as the camera (i.e the top of the screen of the phone is ponting the same way as the lens)

You can also save pictures of detected objects by enabling the `capture_img` option in the client's configuration file. This will export one image per second maximum (if any object is detected), with detection boxes drawn on top. One image is around ~150kB to ~200kB, so expect a maxium of 720MB of data generated for an hour of observation when using this feature.

## Running the client
- Create a Python venv (Python >=3.10, tested on both 3.10.12 and 3.13.5)
- Enable the venv and install the requirements `pip install -r requirements.txt`
- Configure the client (check for all seral devices, uart, netowork endpoints, etc)
- Launch the client with `python main.py`

To run the client automaticaly on a embedded/headless device, see below for instruction on how to setup the client as a service.

## Configuration
See `client/config.conf` for all available options. 
__Don't forget do set the device id!__
You can enable/disable sensors, and set networking options (endpoint, frequency). This is also where you can set manual values, such as a fixed location for a static sensor for example.

## How to Add a new sensor / data field
Additional sensors can be implemented by inheriting the `Sensor` class. It is **required** for each client to have a GPS and provide the `latitude` and `longitude` values when syncing with the network, or many features of the platform wont be available. If using a camera for object detection, `azimuth` is also required. All sensors are registered in the `sensorsList` list. The order is significant: if multiple sensors provide the same data field, the data from the latest one will override the others. The last sensor should be `static`, so that manually provided values override all other sensors that may provide the same data field.

- If adding a completly new sensor, in `client/sensors.py` create a new class inheriting the 'Sensor' class, and instance it in main. Add this instance to the `sensorsList`. 
- To declare a new data field (for both a new or existing sensor), add a new line like `self._addDataField("<name>", <type>)` in the `__registerDataField` function of your sensor class. `<name>` is the name of the datafield, and `<type>` is the datatype (can be `int, float, str`)
- The two steps above are enough to have your new sensor (and/or) data field logged localy.
- If using LoRaWAN, you must also edit `common/lora.py`. Add the data field's name in `SENSOR_MSG` to add your new data field to the network messages. You also need to specify the data type of the field in `FIELDS_TYPE` (see [here](https://docs.python.org/3/library/struct.html#format-characters) for more informations on available data types). **These modifications must be made on both the server and the client. [see TODO#2]**
- For any other networking options using the JSON message format, no additional step is required, as the platform will recognize the new data field and adapt accordingly.

## Static Equipements
For static equipements, it is possible to manually and staticaly provide values like the GPS location and orientation. See the `sensor.static` field in the configuration file. As the client only sends data when they change, it does not increase the network load if all data is static (one update message will be sent once when the equipement powers on).
For such an equipement, we can set the device status update frequency to be very low (from minutes to hours), and use a different network, like LoRa for these messages.

## Fixing permission issues
### Camera OAK-D
If you run into errors with the camera, try the `fix-udev.sh` script for setting permissions allowing the program to access the camra (and only the camera) instead of launching as root. This script will add a udev exception for the camera usb vendor id and device id, so that normal users are allowed to interact with the device.

### UART device permissions
If you run into permission issues with UART, you should check which group has read/write permission on the serial interface, and add the user running the program to this group. The group is usually `dialout` or `uucp`. You can see the group with `stat -C "%G" /dev/<your serial interface>`. To add a user to a group, check your distribution's wiki (often `sudo usermod -a -G <user> <group>`. You will need to logout and login again for changes to apply). Running the program as root is also possible but *not recommanded*.

## Setup the client as a service
After installing and configuring the client, create a `/etc/systemd/system/platformeIoT.service` with the following content:
```
[Unit]
Description=plateformeIot: launch the client for the IoT platform
After=network.target

[Install]
WantedBy=multi-user.target

[Service]
ExecStart=/usr/local/bin/plateformeIot.sh
Restart=always
StartLimitInterval=10
RestartSec=10
```

Create a file named `plateformeIoT.sh` in `/usr/local/bin`, with the following content:
```bash
#!/usr/bin/bash
cd <path to installation> || exit -1
source launch-client.sh <nohotspot>
```
Add the `nohotspot` argument if you wish to prevent the launch script from trying to enable the WiFi hotspot on the client (for example if the client should instead connect to an existing network, like a network share from the phone, or you don't use wifi entirely)

To consult the logs when the app 

### WiFi Hotspot
If you plan on using the client's WiFi hotspot, the launch script can automatically enable it for you: you just have to provide a Network Manager connection named "Hotspot". This configuration is usually a file in `/etc/NetworkManager/system-connections` and should look somthing similar to this:
```
[connection]
id=Hotspot
uuid=84332941-9970-4a7d-959a-c799720bcc42
type=wifi
autoconnect=false
interface-name=<INTERFACE>

[wifi]
mode=ap
ssid=<SSID> 

[wifi-security]
group=ccmp;
key-mgmt=wpa-psk
pairwise=ccmp;
proto=rsn;
psk=<PASSWORD>

[ipv4]
method=shared

[ipv6]
addr-gen-mode=stable-privacy
method=auto

[proxy]
```
You could also not use this, and instead rely on NetworkManager and systemd to handle all of it for you.

