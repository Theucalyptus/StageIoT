import struct
import json
import logging
from common.msgTypes import MessageTypes

logger = logging.getLogger(__name__)


class MissingDataField(Exception):
    pass

class MalformedLoraMessage(Exception):
    pass

class UnregisteredDeviceFormat(Exception):
    pass

# This module's purpose is to serialize the json messages into a smaller format
# suited for transmission over the LoRa network

# data fields that are required in all LoRa messages
MANDATORY_FIELDS = ['type', 'timestamp','msgNumber']

# This dictionnary is a list of message formats that can be used by LoRa clients
# !! THIS DICT MUST BE IDENTICAL IN BOTH THE CLIENT AND THE SERVER !!
#    (or at least the values associated with the format being used)
MSG_DATA = {1: ['latitude', 'longitude', 'altitude', 'azimuth', 'pitch', 'roll', 'speed']}

# This dictionnary is the mapping between devices and the message format they use.
DEVICE_MSG_TYPES = {"jetson1": 1,
                    "test1": 1,
                    }

# must contain the same elements as `LABELS` in client/spatial_object_perso
OBJECTS_LABELS = ["background","aeroplane","bicycle","bird","boat","bottle","bus","car",
                "cat","chair","cow","diningtable","dog","horse","motorbike","person",
                "pottedplant","sheep","sofa","train","tvmonitor"] + ['unknown']


# Same as for device objects, but 
OBJECT_MSG_HEADER = MANDATORY_FIELDS
OBJECT_ITEM_MSG = ['latitude', 'longitude', 'label', 'id']


FIELDS_TYPES = {'type':'H',
                'msgNumber':'H',
                'timestamp':'d',
                'latitude':'f', 
                'longitude':'f',
                'speed':'f',
                'pitch':'f',
                'roll':'f',
                'azimuth':'f',
                'altitude':'f',
                'label':'H', # object label are transformed into unsigned short, using the table provided above for label/number correspondance
                'id':'i'
                } 

def getMessageFormat(deviceid):
    """
        Returns the list of expected data fields for a particular device
    """

    message_content_type = DEVICE_MSG_TYPES.get(deviceid, 1)
    if not message_content_type:
        message_content_type = 1
        logger.warning("Unknown message format for LoRa device " + deviceid + ". Using 1 but may be incorrect !")

    return MANDATORY_FIELDS + MSG_DATA[message_content_type]


def data_to_lora(data):
    """
        Serializes some data to the binary representation to be sent with LoRa.
    """

    if data['type'] == MessageTypes.DEVICE_UPDATE:
        return sample_to_lora(data)
    elif data['type'] == MessageTypes.OBJECT_REPORT:
        return objects_to_lora(data)
    else:
        raise ValueError()

def sample_to_lora(data):
    """
        Transforms a status update/sensors data message into a minified format suited for the LoRa network
    """

    msg_data_fields = getMessageFormat(data['device-id'])
    try:
        bin = b""
        for field in msg_data_fields:
            d = struct.pack(FIELDS_TYPES[field], data[field])
            bin += d
        return bin
    except KeyError:
        raise MissingDataField()


def lora_to_sample(binary, deviceid):
    """
        Reverse operation of sample_to_lora. Transforms a LoRa message into a python dictionary.

        Args:
        - the binary data : bytes, bytearray
        - deviceid: str -> the device that sent the message
    """

    msg_expected_fields = getMessageFormat(deviceid)
    try:
        data = {}
        index=0
        for f in msg_expected_fields:
            t = FIELDS_TYPES[f]
            size = struct.calcsize(t)
            #print(f, t, size, binary[index:index+size])
            data[f] = struct.unpack(t, binary[index:index+size])[0]
            index+=size
        return data
    except Exception as e:
        logger.error("Lora sample message decoder failed")
        raise MalformedLoraMessage(e)

def objects_to_lora(data):
    """
        Converts a object report message into its LoRa binary representation

        Args:
        - data: dict -> the data to be serialized
    """
    try:
        # preparation
        for o in data['objects']:
            try:
                o['label'] = OBJECTS_LABELS.index(o['label']) # encode object label
            except ValueError:
                logger.warning("Tried to encode an unknown object label")
                o['label'] = OBJECTS_LABELS.index('unknown')

        # minimization
        bin = b''
        for field in OBJECT_MSG_HEADER:
            bin += struct.pack(FIELDS_TYPES[field], data[field])
        for object in data['objects']:
            for f in OBJECT_ITEM_MSG:
                bin += struct.pack(FIELDS_TYPES[f], object[f])
        return bin
    except KeyError:
        raise MissingDataField()

def lora_to_objects(binary):
    """
        Reverse operation of objects_to_lora
    """
    try:
        data = {}
        index=0
        for f in OBJECT_MSG_HEADER:
            t = FIELDS_TYPES[f]
            size = struct.calcsize(t)
            data[f] = struct.unpack(t, binary[index:index+size])[0]
            index+=size

        objSize=0
        for f in OBJECT_ITEM_MSG:
            objSize+=struct.calcsize(FIELDS_TYPES[f])
        data['objects'] = []
        while index < len(binary):
            o = {}
            for f in OBJECT_ITEM_MSG:
                t = FIELDS_TYPES[f]
                size = struct.calcsize(t)
                o[f] = struct.unpack(t, binary[index:index+size])[0]
                index +=size
            data['objects'].append(o)
        # post-processing
        for o in data['objects']:
            o['label'] = OBJECTS_LABELS[o['label']] # decode object label
        return data
    except Exception as e:
        logger.error("Lora Object message decoder failed")
        raise MalformedLoraMessage(e)
    
def get_message_type(binary):
    """
        Returns the message type from a binary LoRa message
    """
    return struct.unpack(FIELDS_TYPES['type'], binary[0:struct.calcsize(FIELDS_TYPES['type'])])[0]

# if __name__=="__main__":
#     object_test_data = json.loads(open("../object.json", 'r').read())
#     sensors_test_data = json.loads(open("../sensors.json", 'r').read())

#     binary = sample_to_lora(sensors_test_data)
#     print(binary, "size", len(binary), type(binary))

#     data = lora_to_sample(binary)
#     print(data, len(binary), len(bytes(json.dumps(sensors_test_data), 'utf-8')))
#     print(get_message_type(binary))

#     bin2 = objects_to_lora(object_test_data)
#     print(get_message_type(bin2))
#     print(bin2, len(bin2), len(bytes(json.dumps(object_test_data), 'utf-8')))
#     print(lora_to_objects(bin2))