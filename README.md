# IoT Platform

## Description
This project aims at creating a platform for collecting and sending vehicule's data using the mobile network or LoRa. It is divided in two main components: the server (composed of a web server, a web app and a database) and the client (running on an embedded system, also called a device, connected to sensors).
Both the server and client are written in Python.
We also provide a Android app allowing a phone to be used as a sensor by the client (for GPS, acceleration, etc).

![Architectural diagram of the platform](doc/diag.png)

## Main features
- Data collection with an embedded system and external sensors
- Cooperative Perception*: systems can signal obstacles, and others can query for nearby obstacles
- Data transmission to a server using mobile network or LoRa
- Live data visualization through a web app.
- Data access API
- Benchmarking & measures: the platform measure all sorts of things about itself and its performance, like network usage, latency and reliability

## Setup & Usage
This section contains information on how to setup, deploy and use both the software and the hardware.

### Hardware
See [hardware.md](doc/client_hardware.md) for more information about the hardware we used.

### Client
See [client.md](doc/client.md.md) for information on how to setup, configure and debug the client software.

### Server
See [server.md](doc/server.md) for information about the server's software, how to install, configure and run it.


## Benchmarking
- Client: 
    - measures the Network latency when sending data via http (from client to server), when pulling data from the server (total round-trip time of the request)
    - The client measures the percentage of succes of a network (rx/tx) (i.e packet loss) (only for Http, see below for more info on LoRa)
- Platform: 
    - measures the network delay for all type of messages, and saves it in the database for device update messages (`netDelay` column in the database)
    - packet loss for each device (total packet loss, combination of all networks* and for all messages), and logged in the device data (total number of lost packets between two successful device update messages) (`packetLoss` column in the database)

Note: because we use a message number (modulo 256) to detect package loss, if using multiple network simultaneously, packets may arrive out-of-order and would be counted as packet-loss, even though they have been received and processed.

## Details

### Sessions
The server uses a database for long-term storage, but also uses an intern cache. This cache as a default duration of 10 minutes (but this can be configured). This creates an implicit notion of "session", as many features of the platform will only use the data cache. 
For example, the platform will measure network packet loss while the device is in cache. So if a device is offline longer than the cache duration, once it reconnects the statistics would have been removed. 
Because the cache is only purged when inserting new data, if there is only one device, the new data upon reconnection will be inserted before the purge, so the session will continue.
This cache is *not saved when stopping the server*.
The 'Visualize' page also pulls data from the cache if the selected duration is shorter than the cache duration. This means, however, that if the platform was recently restarted, selecting a duration shorter than the cache size will return no data, as they are expected to be in cache, while the data is actually available in the databse (see Improvement 8)

### Network messages
By default, we send JSON-serialized messages for greater flexibility, ease of use and interpretability, as network bandwith is not a big concern on WiFi and LTE/5G, espcially in an experimental context with a limited number of devices. This allows us to include a description of what data is being sent, so the database can automatically update if a client introduces new sensors/data field. This is suboptimal for performance, but very helpful when experimenting with different types of sensors.
However, when using LoRa, using JSON is *strongly* discouraged.
Thus, when using the LoRa network, we switch to a **fixed, minimal message format** for some huge gains: a obstacle report message containing 2 objects goes from 212 bytes down to 30. For a sensor data message with 8 user data field, we see a reduction from 182 down to 38 bytes.
Please note however that because LoRa *is not design for real-time data*, one may need to *significantly* reduce the upload frequency to stay under the legal duty cycle utilization limit (1% in Europe). If this quota is exceeded, the transmission will cease with no warning.
The details of this serialization can be found in the `common/lora.py` file. It requires both the client and the server to know the message format in advance, which is inpractical, but we still went with it as network bandwith and usage is the biggest concern when using the LoRa network. In our test, we could get away with sending messages every ~10 seconds using LoRa for a limited period of time.

The client allows for two networks to be used: one main and a backup/alternative. If the main network is down*, the client switches to the backup. In case both networks are down, the data is still being logged localy. When a network is down, we periodicaly check if its back up and switch accordingly.

* NOTE: only the http network service can detect if it's online or not. LoRaWAN doesn't provide an easy way to now if the network is up, as we would need to use confirmed messages, which are limited in number because they required downlink communication. We assume that LoRa is always up, as a "best effort" backup solution.

For static devices, LoRa could would be suitable for infrequent status update, while a more capable network could be used for important, real-time data.

### Android Application
The provided Android app is used to gather data from the smartphone's sensors (GPS location, orientation data) and send them to the 

## Possible Improvements:
1. ~~Redo device edit/list page to show lora eui if present~~ DONE (31008e87991f8ac9bcb3403117db5f9f2508782d)
2. Multiple LoRa message structure for different devices (for now they must all use the same) UPDATE: can be done quite easily by editing the common/lora functions server side to take the deviceid, and provide a list of format.
3. As of now, clients are polling to API to retrieve le list of nearby objects reported by other devices. This could be improved by using a messaging system, so clients only receive the necessary information without polling (would improve latency and network usage)
4. ~~Provide a way to configure a client/device as a stationnary equipement, removing the need for a GPS~~ DONE (7e3b40cd3bfc5fb7e548b04d559a451b1b762fdd)
5. ~~Live Data persistence: device live data are removed from cache after 1 hour, objects are stored in cache until the app is stopped.~~ DONE (bb2eff6fbd39b616300e1c3c1c5d836a7ba44d3e)
6. Re-use more code between to WUI and the API (in progress)
7. Create sub-categories of messages for various level or importance, and select which network to use
8. Merge cache and database sources for data visualisation