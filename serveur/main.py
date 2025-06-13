import sys
import time
import threading
from queue import Queue
import mysql.connector
import Interface
import MQTT
import web.IP as IP
import utils
import os

Config={}

db : mysql.connector.MySQLConnection

def init_db():

    """
    Initialise the data base. Retreive config info from the dict Config
    Select the db for the data collection plateform.
    Beware that this might not be secure with respect to the config file 
    (cant do secure "USE db" or some other query but there is still a minimal check)
    """

    global db
    try : 
        #connect to mySQL

        mydb = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"])
        cursor = mydb.cursor()
        # Seaching for DB
        liste_db=[]
        cursor.execute("SHOW DATABASES LIKE %s", (Config["db_name"],))
        for i in cursor:
            liste_db+=i

        #print(liste_db)
        if len(liste_db)== 1:
            mydb.cmd_init_db(Config["db_name"])

        elif len(liste_db)==0:
            # DOCKER BYPASS ALWAYS CREATE EMPTY DB
            print("WARNING: Required database " + utils.sql_var(Config["db_name"]) + " not found. This could be an issue of persistent storage")
            print("INFO: If this is the first launch of the service, this is excepted behaviour and the database will be created automatically for you.")
            # Create DB
            query="CREATE database " + utils.sql_var(Config["db_name"])
            print(query)
            cursor.execute(query)
            db_query = "USE "+ utils.sql_var(Config["db_name"])
            cursor.execute(db_query)
            # print("Aucune base de données de ce nom n'a été trouvé. Voulez vous la créer ? ", end="")
            # valid = False
            # while not valid:
            #     ans = input("[y/n] : ")
            #     ans = ans.strip(" ")
            #     ans = ans.strip("-")
            #     ans = ans.lower()
            #     if ans in ["y","yes","ye","es"]:
            #         valid = True
            #         #Create DB
            #         query="CREATE database " + utils.sql_var(Config["db_name"])
            #         print(query)
            #         cursor.execute(query)
            #         db_query = "USE "+ utils.sql_var(Config["db_name"])
            #         cursor.execute(db_query)
            #     else :
            #         if ans in  ["n","no"]:
            #             # Dont create DB -> exit
            #             exit(0) 
            #         else :
            #             print("Veulliez respecter la syntaxe ", end="")
                        
        # Import tables (if they dont exist yet)
        
        path_setup_DB = os.path.join(__file__.rsplit(os.path.sep, 1)[0], Config['db_init_file']+".sql")
        print("DB setup file path", path_setup_DB)
        sql=open(path_setup_DB, 'r')
        cursor.execute(sql.read())
        
        db=mydb
        

    except mysql.connector.errors.ProgrammingError as e :
        print(e)
        exit(1)

def init_config():
    
    """
    Initialise the program Config
    The config file must be in the same folder/directory as the program
    It is not nessecary to enter evey field of the config file as there are default values
    """

    path = os.path.join(__file__.rsplit(os.path.sep, 1)[0], "config.conf")
    # print(path)
    conf = open(path)
    
    # parsing each line
    for line in conf:
        # '=' is the center of the msg with the syntax : "<key>=<value>"
        if '=' in line and line[0] != '#':
            k,v=line.split('=')
            v= v.strip() # on retire les espaces
            v.lstrip('"')
            v.rstrip('"')
            Config[k]=v
                
    #print(Config)

def run_server():

    """
    Run the server nodes. A node is a thread with a functionality (it may create other threads that fulfill the same goal.).
    We link the diferents threads with Queues. Thoses represent the channels and we can determine the form of the data with it.
    """

    #Queues and nodes parameters
    Q_Lora = Queue()
    Q_4G = Queue()
    coordsTTN = {
        'mqtt_username' :Config["APP_username"],
        'password' : Config["APP_password"],
        'hostname':Config["APP_hostname"],
        'port' : int(Config["APP_port"])
    }
    # création des threads
    threadMQTT = threading.Thread(target=MQTT.MQTTnode,args=[coordsTTN,Q_Lora])
    threadIf = threading.Thread(target=Interface.Ifnode,args=[Q_Lora,Q_4G,Config])
    threadIP = threading.Thread(target=IP.IPnode,args=[Q_4G,Config])

    # start les threads
    try:
        threadMQTT.start()
        threadIP.start()
        threadIf.start()

    except (KeyboardInterrupt, SystemExit):
        
        sys.exit()
    
def main():

    """
    This is the main function of the Data Collecting plateform server.
    This program uses a MySQL database.
    You can modify some configuration settings in the config.conf file that is in the same folder/directory as this program.
    DB auth not implemented yet, use a user with no password.
    """

    print("Starting Web Server")
    init_config()
    init_db()
    run_server()

if __name__ == "__main__":
    main()



