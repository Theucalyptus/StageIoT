import struct
import json
import logging

logger = logging.getLogger(__name__)


class MissingDataField(Exception):
    pass

# This module's purpose is to serialize the usual json messages into a smaller format
# suited for transmission over the LoRa network

# This list of data fields must be a subset of fields available through the client's sensors
# !! THIS LIST SHOULD BE IDENTICAL IN BOTH THE CLIENT AND THE SERVER !!
SENSORS_MSG = ['type', 'timestamp', 'latitude', 'longitude', 'altitude', 'azimuth', 'pitch', 'roll', 'speed']

# must contain the same elements as `LABELS` in client/spatial_object_perso
OBJECTS_LABELS = ["background","aeroplane","bicycle","bird","boat","bottle","bus","car",
                "cat","chair","cow","diningtable","dog","horse","motorbike","person",
                "pottedplant","sheep","sofa","train","tvmonitor"] + ['unkown']
OBJECT_MSG_HEADER = ['type', 'timestamp']
OBJECT_ITEM_MSG = ['latitude', 'longitude', 'label']

FIELDS_TYPES = {'type':'H',
                'timestamp':'d',
                'latitude':'f', 
                'longitude':'f',
                'speed':'f',
                'pitch':'f',
                'roll':'f',
                'azimuth':'f',
                'altitude':'f',
                'label':'H' # object label are transformed into unsigned short, using the table provided above for label/number correspondance
                } 

def data_to_lora(data):
    if data['type'] == 1:
        return sample_to_lora(data)
    elif data['type'] == 2:
        return objects_to_lora(data)
    else:
        raise ValueError()

def sample_to_lora(data):
    """
        Transform a status update/sensors data message into a minified format suited for the LoRa network
    """
    try:
        bin = b""
        for field in SENSORS_MSG:
            d = struct.pack(FIELDS_TYPES[field], data[field])
            bin += d
        return bin
    except KeyError:
        raise MissingDataField()

def lora_to_sample(binary):
    """
        Reverse operation of sample_to_lora. Transform a LoRa message into a easy to use python dict.
    """
    data = {}
    index=0
    for f in SENSORS_MSG:
        t = FIELDS_TYPES[f]
        size = struct.calcsize(t)
        data[f] = struct.unpack(t, binary[index:index+size])[0]
        index+=size
    return data

def objects_to_lora(data):
    try:
        # preparation
        for o in data['objects']:
            try:
                o['label'] = OBJECTS_LABELS.index(o['label']) # encode object label
            except ValueError:
                logger.warning("Tried to encode an unknown object label")
                o['label'] = OBJECTS_LABELS.index('unkown')

        # minimization
        bin = b'';
        for field in OBJECT_MSG_HEADER:
            bin += struct.pack(FIELDS_TYPES[field], data[field])
        for object in data['objects']:
            for f in OBJECT_ITEM_MSG:
                bin += struct.pack(FIELDS_TYPES[f], object[f])
        return bin
    except KeyError:
        raise MissingDataField()

def lora_to_objects(binary):
    
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

def get_message_type(binary):
    return struct.unpack(FIELDS_TYPES['type'], binary[0:struct.calcsize(FIELDS_TYPES['type'])])[0]

if __name__=="__main__":
    object_test_data = json.loads(open("../object.json", 'r').read())
    sensors_test_data = json.loads(open("../sensors.json", 'r').read())

    binary = sample_to_lora(sensors_test_data)
    print(binary, "size", len(binary), type(binary))

    data = lora_to_sample(binary)
    print(data, len(binary), len(bytes(json.dumps(sensors_test_data), 'utf-8')))
    print(get_message_type(binary))

    bin2 = objects_to_lora(object_test_data)
    print(get_message_type(bin2))
    print(bin2, len(bin2), len(bytes(json.dumps(object_test_data), 'utf-8')))
    print(lora_to_objects(bin2))