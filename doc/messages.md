# Network Messages

When using a IP-capable network, we use JSON-formatted messages for greater flexibility, ease of use and interpretability, as network bandwith is not a big concern on WiFi and LTE/5G, espcially in an experimental context with a limited number of devices.
This allows us to include a description of what data is being sent, so the database can automatically update if a client introduces new sensors/data field. This is suboptimal for performance, but very helpful when experimenting with different types of sensors.
The messages are most often short enough (< 500 bytes) to be sent in a single packet (with a typical MSS > 1300).

However, when using LoRa, using JSON is *strongly* discouraged.
Thus, when using the LoRa network, we switch to a **fixed, minimal message format** for some significant size gains: a obstacle report message containing 2 objects goes from 212 bytes down to 30. For a sensor data message with 8 user data field, we see a reduction from 182 down to 38 bytes.
Please note however that because LoRa *is not design for real-time data*, one may need to *significantly* reduce the upload frequency to stay under the duty cycle utilization limit (1% in Europe). If this quota is exceeded, the transmission will be blocked by the gateway with no warning.
The details of this serialization can be found in the `common/lora.py` file. It requires both the client and the server to know the message format in advance, which is impractical, but we still went with it as network bandwith and usage is the biggest concern when using the LoRa network. In our test, we could get away with sending messages every ~10 seconds using LoRa for a limited period of time.

## WiFi/4G-5G

### Example Device update message
```json
{
    "device-id": "test1",
    "type": 1,
    "latitude": 0.0,
    "longitude": 0.0,
    "azimuth": 172.70120239257812,
    "timestamp": 1752648167.2902591,
    "altitude": 0,
    "speed": 0,
    "roll": 0.5218551158905029,
    "pitch": -0.49436989426612854,
    "msgNumber": 33
}
```

### Example Object message
```json
{
    "device-id": "test1",
    "type": 2,
    "timestamp": 1752648161.817387,
    "objects": [
        {
            "latitude": -3.557436875006223e-05,
            "longitude": 4.538725119933624e-06,
            "label": "bicycle",
            "id": 2
        },
        {
            "latitude": -5.295477026175563e-05,
            "longitude": 1.1642358615238306e-06,
            "label": "person",
            "id": 4
        }
    ],
    "msgNumber": 17
}

```

#### Explaination
- device-id: the device-id that sent the message
- type: the type of message (see [common/msgTypes.py](../common/msgTypes.py) for the list of all types)
- timestamp: the timestamp at which the message was _created_
- msgNumber: the message number, usefull for packet-loss detection

Device update messages then contain all sensor data.
Object report messages have a objects field, which is a list of objects, each with an id, a label, and gps coordinates.

