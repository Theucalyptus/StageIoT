import mysql.connector.abstracts
import base64
import json
from queue import Queue
import time
import utils
import datetime
import requests
from common.msgTypes import MessageTypes
from common import lora

Config = {}

# long-lived DB connction, one per thread
db1, c1 = None, None # for data sample (used by Web_msg_handler & save_sample_DB)
db2, c2 = None, None # for objects 

def __getSQLDataType(value):
    if type(value) == int:
        return "int"
    elif type(value) == float: 
        return "float"
    elif type(value) == str:
        return "varchar(255)"
    else:
        raise TypeError

def __checkColumnExists(c, tablename, column):
    query = "SHOW COLUMNS FROM " + tablename +  " LIKE %s;"
    c.execute(query, (column,))
    r = c.fetchall()
    return len(r)>= 1

def __getDeviceIDFromEUI(lora_eui: str):
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])

    if lora_eui == "" or lora_eui == None:
        return None
    
    c = db.cursor()
    query = "SELECT `device-id` FROM Device WHERE `lora-dev-eui` = %s;"
    c.execute(query, (lora_eui.lower().strip(),))
    res = None
    try:
        res = c.fetchone()[0]
    except (IndexError, TypeError):
        pass
    return res

def save_sample_DB(data):
    db = db1 #mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    c = c1 #db.cursor()

    try :
        request_type = data.pop('type', None)
        assert(request_type == 1)
        deviceid = data.pop('device-id', None)
        data['timestamp']=datetime.datetime.fromtimestamp(data['timestamp'])
        for field in data.keys():
            if field != "timestamp":
                if not __checkColumnExists(c, deviceid, field):
                    add_col_query = "ALTER TABLE " + deviceid + " ADD COLUMN "+ field + " " + str(__getSQLDataType(data[field])) + " DEFAULT NULL;"
                    c.execute(add_col_query, ())
                db.commit()               

        # insert data
        query = "INSERT INTO "+ deviceid +" ("
        for field in data.keys():
            query += field + ", "
        query = query.removesuffix(", ")
        query += ") VALUES ("
        for field in data.keys():
            query += "%({0})s, ".format(field)
        query = query.removesuffix(", ")
        query += ")"

        if query != "":
            c.execute(query,data)
            db.commit()               
    except Exception as e :
        print("DB insertion failed with exception", e)

def save_object_DB(object):
    db = db2
    db.ping(reconnect=True)
    c = c2

    table = "Objects"
    temp = object.copy()
    temp['timestamp']=datetime.datetime.fromtimestamp(object['timestamp'])
    

    device = object["seenby"]
    query = "SELECT * FROM Device WHERE `device-id`=%s"
    c.execute(query,(device,))
    res = c.fetchall()
    if len(res)==0:
        print("object seen by unkown device, ignoring")
        return


    # if object already has a permanent id, it should be in the DB and we have to update its record
    if "id" in object:
        #print("Update existing object record")
        fields = ""
        values=[]
        id = temp.pop('id') # remove id
        for d in temp:
            fields+="`"+ d+"`=%s ,"
            values.append(temp[d])
        fields=fields[:-2]
        values.append(id)
        query = "UPDATE " + table + " SET " + fields + " WHERE id=%s"
        c.execute(query, (values))
        db.commit()               

    else:
        # the object is new, so assign it a permanent id and create a new record in the table
        #print("inserting new object in DB")
        query = "INSERT INTO " + table +" (timestamp, seenby, latitude, longitude, label, tempId) VALUES (%(timestamp)s, %(seenby)s, %(latitude)s, %(longitude)s, %(label)s, %(tempId)s)"
        c.execute(query, (temp))
        db.commit()               

        # get the record for the newly added record
        query = "SELECT id FROM " + table + " WHERE seenby=%s AND tempId=%s ORDER BY timestamp DESC LIMIT 1;"
        c.execute(query, ([temp['seenby'], temp['tempId']]))
        res = c.fetchone() # should only ever match one object
        object["id"] = res[0]


def data_LoRa_handler(message,device):
    deviceid = __getDeviceIDFromEUI(device)
    if deviceid != None:
        type = lora.get_message_type(message)
        if type == MessageTypes.DEVICE_UPDATE:
            message = lora.lora_to_sample(message)
        elif type == MessageTypes.OBJECT_REPORT:
            message = lora.lora_to_objects(message)
        else:
            print("Unknown message type")
            raise NotImplementedError
        message['device-id'] = deviceid
        requests.post("http://"+Config['server_host']+":"+Config['server_port']+"/post_data",data=json.dumps(message))
    else:
        print("unkown lora EUI ({0}), ignoring message".format(device))

def LoRa_msg_handler(msg):
    try :
        message = json.loads(msg.payload)
        #print(message)
        device = message['end_device_ids']['dev_eui'] #  EUI
        device_ttn_name = message['end_device_ids']['device_id'] # Device's name as registered in TTN
        type = msg.topic.split("/")[-1]
        match type : 
            case "join":
                print(device_ttn_name, "("+device+")", "join msg received")
            case "up":
                data = message['uplink_message']['frm_payload']
                data = base64.b64decode(data.encode())
                data_LoRa_handler(data, device)
    except (RuntimeError,KeyError) as e :
        print("ERROR", msg.payload, e)

def Web_msg_handler(data_sample):
    global db1, c1
    cursor= c1

    db1.ping(reconnect=True) # keep the connection alive

    # check if the device exists
    device = data_sample["device-id"]
    query = "SELECT * FROM Device WHERE `device-id`=%s"
    cursor.execute(query,(device,))
    res = cursor.fetchall()
    if len(res)!=0:
        save_sample_DB(data_sample)
    else:
        print("device "+device+" not registered, ignoring.")
    
def WS_msg_handler(message):
    requests.post("http://"+Config['server_host']+":"+Config['server_port']+"/post_data",data=message)


def Ifnode(Q_Lora : Queue, Q_web : Queue, Q_websocket: Queue, Config_):
    global Config, db1, c1, db2, c2
    print("Starting Interface node")
    Config=Config_
    
    # for use by save sample (1 thread only so OK)
    db1 = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    c1 = db1.cursor()

    # for use by object save (called from flask request handlers, 1 at a time at most, because flask is monothreaded)
    db2 = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    c2 = db2.cursor()

    while True:
        try:
            while Q_Lora.empty() and Q_web.empty() and Q_websocket.empty():
                time.sleep(0.002)
            if not Q_Lora.empty():
                LoRa_msg_handler(Q_Lora.get())
            if not Q_web.empty():
                Web_msg_handler(Q_web.get())
            if not Q_websocket.empty():
                WS_msg_handler(Q_websocket.get())
        except Exception as e:
            print("Interface: ERROR:", e)

