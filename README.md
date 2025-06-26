# IoT Platform for automotive applications

## Description
This project aims at creating a platform for collecting and sending vehicule's data using the mobile network or LoRa. It is divided in two main components: the server (composed of a web server, a web app and a database) and the client (running on an embedded system, also called a device, connected to sensors).
We also provide a Android app allowing a phone to be used as a sensor by the client (for GPS, acceleration, etc).

## Main features
- Data collection with an embedded system and external sensors
- Cooperative Perception*: systems can signal obstacles, and others can query for nearby obstacles
- Data transmission to a server using mobile network or LoRa
- Data visualization through a web portal/app.
- Data access API*

## Hardware

### Jetson Orin Nano
The Nvidia Jetson Orin Nano is the main computer of the project. It is used for data collection, processing and logging. It can also perform spatial object detection and classification for the cooperative perception of obstacles.

### LoPy4
The LoPy4 board is our LoRa transcievers. It could be replaced by any other LoRa capable equipement.
The LoPy4 is used with the Jetson, communicating via UART, and sending the data on the LoRa Network. The code is in the `lopy4` folder of this repository.

### OAK-D Camera 
The OAK-D camera allows us to easily perform object detection and classification. With the Jetson, we could also use a pair of cameras using the two CSI connectors.

## Network

- Internet (IP) on 2G, 3G, 4G, 5G (via HTTP)
- LoRaWan,  via The Things Network (and MQTT-api)
- For sensor communications:
    - WiF (using Websockets)
    - Bluetooth

By default, we send JSON-serialized messages for greater flexibility, ease of use and interpretability, as network bandwith is not a big concern on WiFi and LTE/5G. This allows to include a description of what data is being sent, allowing the database to automatically update if a client introduces new sensors/data field.
However, when using LoRa, using JSON is *strongly* discouraged, as very inefficient.
Thus, when using the LoRa network, we switch to a **fixed, minimal message format** for some huge gains: a obstacle report message containing 2 objects goes from 212 bytes down to 30. For a sensor data message with 8 user data field, we see a reduction from 182 down to 38 bytes.
Please note however that because LoRa *is not design for real-time data*, one may need to *significantly* reduce the upload frequency to stay under the legal duty cycle utilization limit (1% in Europe). If this quota is exceeded, the transmission will cease with no warning.
The details of this serialization can be found in the `common/lora.py` file. It requires both the client and the server to know the message format in advance, which is inpractical, but we still went with it as network bandwith and usage is the biggest concern when using the LoRa network.

The client allows for two networks to be used: one main and a backup/alternative. If the main network is down*, the client switches to the backup. In case both networks are down, the data is still being logged localy. When a network is down, we periodicaly check if its back up and switch accordingly.

* NOTE: only the http network service can detect if it's online or not. LoRaWAN doesn't provide an easy way for us to now if the network is up, as this would require the use of downlink/ack'd messages, which are heavily restricted (~10 per day per device). We assume that LoRa is always up.

## Usage
### Data Collection Server & Web App Interaface
#### With Docker Compose
Docker images for both the mySQL database and the webapp itself are provided, and can be easily deployed using docker compose. The following script does it for you:
```bash
    ./launch-server.sh
```
#### Manually
- Have mySQL/mariaDB installed and configured (see below); Python version >=3.10
- In the server's directory, do the following:
    - Create a python virtal environment (venv): `python -m venv <path to venv>`, and active it, ie `source <path to venv>/bin/activate`
    - Install runtime dependancies with pip: `pip install -r requirements.txt`
    - Launch the app: `python main.py`

#### Configuration
In the `seuveur/config.conf` file, one can set:
- the database settings (endpoint, authentication)
- connection with *The Things Network* (endpoint, authentication)

### Client
The client is indented to be used on an mobile/embedded computer, like a NVidia Jetson or a Raspberry Pi. It collectes data from sensors, logs the data locally and periodicaly sends it over the network.
Additional sensors can be implemented by simply inheriting the `Sensor` class. It is **mandatory** for each client to have a GPS and provide the `latitude` and `longitude` values when syncing with the network.

- All sensors are registered in `sensorsList`. The order is significant: if multiple sensors provide the same data field, the data from the latest one will override the others. 
- objects detected by the cameras are approximatly located using a combination of the GPS coordinates and Azimuth provided by the phone, and the position of objects relative to the camera (with the condition that the camera is oriented the same way as the phone, i.e the top of the screen of the phone is ponting the same way as the lenses)

#### Configuration
See `client/config.conf` for all available options. You can enable/disable sensors, and set networking options.

#### How to Add a new sensor / data field
- If adding a completly new sensor, in `client/sensors.py` create a new class inheriting the 'Sensor' class, and instance it in main. Add this instance to the `sensorsList`. 
- To declare a new data field (for both a new or existing sensor), add a new line like `self.data.setdefault("my_data_field")` in the `__registerDataField` function of your sensor class.
- The two steps above are enough to have your new sensor (and/or) data field logged localy. For sending the data onto the network, please see below.
- If using LoRaWAN, you must also edit `common/lora.py`. Add the data field's name in `SENSOR_MSG` to add your new data field to the network messages. You also need to specify the data type of the field in `FIELDS_TYPE` (see [here](https://docs.python.org/3/library/struct.html#format-characters) for more informations on available data types). **These modifications must be made on both the server and the client. [see TODO#2]**
- For any other networking options using the JSON message format, no additional step is required, as the platform will recognize the new data field and adapt accordingly.

#### Fixing permission for the camera.
If you run into errors with the camera, try the `fix-udev.sh` script for setting permissions allowing the program to access the camra (and only the camera) instead of launching as root.

#### UART permissions
If you run into permission issues with UART, you should check which group has read/write permission on the serial interface, and add the user running the program to this group. The group is usually `dialout` or `uucp`. You can see the group with `stat -C "%G" /dev/<your serial interface>`. To add a user to a group, check your distribution's wiki (but often its `sudo usermod -a -G <user> <group>`, you need to logout and login again for changes to apply). Running the program as root is *not recommanded*.


## Improvements / TODO:
1. ~~Redo device edit/list page to show lora eui if present~~ DONE (31008e87991f8ac9bcb3403117db5f9f2508782d)
2. Multiple LoRa message structure for different devices (for now they must all use the same) UPDATE: can be done quite easily by editing the common/lora functions server side to take the deviceid, and provide a list of format.