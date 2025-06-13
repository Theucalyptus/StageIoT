import mysql.connector.abstracts
import base64
import json
from queue import Queue
import time
import utils
import datetime
import requests

db : mysql.connector.MySQLConnection
db_cursor : mysql.connector.abstracts.MySQLCursorAbstract
Config = {}

def save_sample_DB(data):
    global db, db_cursor
    try :
        print("TODO: save_DB", data)
        return 

        query = ""
        data['timestamp']=datetime.datetime.fromtimestamp(data['timestamp'])

        match id :
            case 2 :
                table = "Data"
                db_cursor.execute("SELECT * FROM "+table+" WHERE timestamp = %(timestamp)s",data)
                if db_cursor.rowcount >= 1:
                    print("WARNING: inserting a conflicting data !!!!")
                    utils.print_SQL_response(db_cursor)
                else :
                    query = "INSERT INTO "+ table +" (timestamp, temperature, humidity, luminosity,\
                            presence, pressure, longitude, latitude, altitude, angle, \
                            vitesse_angulaire_X, vitesse_angulaire_Y, vitesse_angulaire_Z,\
                            acceleration_X, acceleration_Y,acceleration_Z,\
                            azimuth, distance_recul, source) \
                            VALUES (%(timestamp)s, %(temperature)s, %(humidite)s, %(luminosity)s,\
                            %(presence)s, %(pressure)s, %(longitude)s, %(latitude)s, %(altitude)s, %(angle)s,\
                            %(vitesse_angulaire_X)s, %(vitesse_angulaire_Y)s, %(vitesse_angulaire_Z)s,%(acceleration_X)s,\
                            %(acceleration_Y)s,%(acceleration_Z)s, %(azimuth)s, %(distance_recul)s, %(eui)s)"
                
            case 3 :
                table = "Obstacles"
                # Ajouter les données à la base de données
                query = "INSERT INTO Objets (timestamp, eui, latitude, longitude, label) VALUES (%(timestamp)s, %(eui)s, %(latitude)s, %(longitude)s, %(label)s)"
                
        if query != "":
            db_cursor.execute(query,data)
            db.commit()
    except ValueError as e :
        print(e)

def data_LoRa_handler(message,device):
    requests.post("http://"+Config['server_host']+":"+Config['server_port']+"/post_data",data=message)


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
                #print("uplink message received")
                data = message['uplink_message']['frm_payload']
                data = base64.b64decode(data.encode())
                try :
                    data = data.decode()
                except UnicodeDecodeError :
                    data = data.hex()

                data_LoRa_handler(data, device)
    except (RuntimeError,KeyError) as e :
        print("ERROR", msg.playload, e)

def IP_msg_handler(data_sample):

    # data = data_format
    # for key in msg.keys():
    #     data[key]=msg[key]
    # data['timestamp']= int(data['timestamp'])/1000
    # assert(data['timestamp']<=datetime.datetime.now().timestamp())
    
    
    db=mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    cursor=db.cursor(buffered=True)

    device = data_sample["device-id"]
    query = "SELECT * FROM Device WHERE `device-id`=%s"
    cursor.execute(query,(device,))
    res = cursor.fetchall()
    if len(res)!=0:
        save_sample_DB(data_sample)
    else:
        print("device "+device+" not registered, ignoring.")
    
    


def Ifnode(Q_Lora : Queue, Q_web : Queue, Config_):
    global db, db_cursor, Config
    print("Starting Interface node")
    Config=Config_
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"])
    db_cursor = db.cursor(buffered=True)
    db_query = "USE "+ utils.sql_var(Config["db_name"])
    db_cursor.execute(db_query)
    
    while True:
        while Q_Lora.empty() and Q_web.empty():
            time.sleep(0.002)
        if not Q_Lora.empty():
            message = Q_Lora.get()
            LoRa_msg_handler(message)
        if not Q_web.empty():
            message = Q_web.get()
            IP_msg_handler(message)

