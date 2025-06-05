from queue import Queue
import sys
import threading
import time
import mysql.connector.abstracts
import dataCollector
import NetworkUnit
import Uart 
import spatial_object_detection


Config={"db_name":"capteurIoT","SQL_username":"root","db_init_file":"stageiot", "LoRaUartIF":None,"LTEUartIF":None,"SensorUartIF":None
        }
db : mysql.connector.MySQLConnection
db_cursor : mysql.connector.abstracts.MySQLCursorAbstract

def init_config():
    """
    Initialise the program Config
    The config file must be in the same folder/directory as the program
    It is not nessecary to enter evey field of the config file as there are default values
    """

    path = __file__.rsplit("/",1)[0]+"/config.conf"
    print(path)
    conf = open(path)
    
    # parsing each line
    for line in conf:
        # '=' is the center of the msg with the syntax : "<key>=<value>"
        if '=' in line:
            k,v=line.split('=')
            v= v.strip() # on retire les espaces
            v.lstrip('"')
            v.rstrip('"')
            for key in Config.keys():
                # if the key is in the Config keys we take it's value
                if k==key and v!="":
                    Config[key]=v
                
    print(Config)

def init_db():

    """
    Initialise the program local Database
    Select the db for the data collection plateform.
    """

    global db, db_cursor
    mydb = mysql.connector.connect(host="localhost", user=Config["SQL_username"])
    db = mydb
    cursor = mydb.cursor()
        
    # Seaching for DB
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{Config['db_name']}`")

    db_query = "USE "+ Config["db_name"]
    cursor.execute(db_query)
    db_cursor=cursor
  

def init_client():
    """
    Initialise the server config and database.
    """

    init_config()
    init_db()


def run_client():
    """
    Run the client nodes. A node is a thread with a functionality (it may create other threads that fulfill the same goal.).
    We link the diferents threads with Queues. Thoses represent the channels and we can determine the form of the data with it.
    """

    Q_data = Queue() # Queue for the data for devices
    Q_data_objects = Queue() # Queue for the objects data
    Q_send = Queue() # Queue of the data to send (through the NetworkUnit)
    Q_output = Queue() # Queue of the data output (same thing you send to the serer but you get an access for yourself in local)
    Q_ns= Queue(1) # Queue to update the network state   !!!! NOT USED YET !!!!

    threadMiddleware = threading.Thread(target=Uart.Uartnode,args=[Q_data,Config])
    threadDataCollecter = threading.Thread(target=dataCollector.dataCollectornode,args=[Q_data, Q_data_objects, Q_output,Q_send,Config, db, db_cursor])
    threadSend = threading.Thread(target=NetworkUnit.Sendnode,args=[Q_send,Q_ns,Config])
    #threadObjectDetection = threading.Thread(target=spatial_object_detection.ObjectDetection,args=[Q_data_objects])

    try:
        threadMiddleware.start()
        threadDataCollecter.start()
        threadSend.start()
        #threadObjectDetection.start()

        while threading.active_count()>1:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        sys.exit()
    


def main():
    """
    This is the main function of the Data Collecting plateform client.
    This program uses a MySQL database.
    You can modify some configuration settings in the config.conf file that is in the same folder/directory as this program.
    """

    init_client()
    run_client()


if __name__ == "__main__":
    main()

