from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session, flash
from flask_cors import CORS
from flask_httpauth import HTTPTokenAuth
from flask_restful import Api
from queue import Queue
import base64
import bcrypt
import csv
import io
import json
import logging
import math
import mysql.connector
import mysql.connector.abstracts
import uuid
from common.msgTypes import MessageTypes
import time

import Interface
from web.forms import *

class NoLocationDataException(Exception):
    pass


app = Flask(__name__)
CORS(app)
api = Api(app)
auth = HTTPTokenAuth(scheme='Bearer')
app._static_folder = './static/'
app.secret_key = 'your_secret_key'
Q_out: Queue
data_storage = {}
objects_storage = {}
Config = {}

### AUXILIARY FUNCTIONS

def __queryAvailableFields(deviceID):
    """
        Returns a list of strings of all available data fields for a given device.
    """
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], database = Config["db_name"])
    cursor = db.cursor()

    query = "SHOW COLUMNS FROM " + deviceID + ";"
    cursor.execute(query)
    res = cursor.fetchall()
    excluded = ['id']
    return [c[0] for c in res if c[0] not in excluded]

def __getDeviceData(device, fields: list[str], startTime:datetime, endTime:datetime):
    """
        Retrives the sensors data of the provided data fields for a particular device between to timestamps, from the databse.
        Args:
            deviceid : str
            fields : list[str] : names of the data fields (all if empty or null)
            startTime, endTime : datetime objects
    """

    # Connect to the DB
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    cursor = db.cursor()
    
    # Retrieve data from the database based on the selected criteria
    fieldsStr = (', '.join(fields)) if fields != None and fields != [] else '*'
    query = f"SELECT {fieldsStr} FROM " + device + " WHERE timestamp BETWEEN %s AND %s"
    cursor.execute(query, (startTime, endTime))
    data = cursor.fetchall()

    return data

def __editDevice(deviceid,name,password,description,lora):
    """
    Edit the device and its association with the user.

    Args:
        deviceid (str): The device id to be edited.
        name (str): The new name of the device
        password (str): The hash of the new password
        description (str): The new description for the device

    """
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    cursor = db.cursor()
    
    data = {}
    if name not in [None, ""]:
        data['name']= name
    if password not in [None, ""]:
        data['password']= password.decode("utf-8")

    data['description'] = description
    data['lora-dev-eui'] = lora
    fields = ""
    values=[]
    for d in data:
        fields+="`"+ d+"`=%s ,"
        values.append(str(data[d]))
    fields=fields[:-2]
    query = "UPDATE Device SET "+ fields +" WHERE `device-id` = %s"
    values.append(deviceid)
    cursor.execute(query, values)
    db.commit()

def __delete_device(deviceid,username):
    """
    Deletes the device and its association with the user.
    Also deletes all sensor data !
    
    Args:
        deviceid (str): The device EUI to be deleted.
        username (str): The name of the user you want to delete the device from.

    """
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    cursor = db.cursor()
    # Supprimer la liaison entre l'appareil et l'utilisateur
    cond =(check_link_device(deviceid,username) == 1)
    if cond:
        query = "DELETE FROM DeviceOwners WHERE device = %s AND owner = %s"
        cursor.execute(query, (deviceid, username))
        db.commit()
    # supprimer la table contenant les données
    cursor.execute("DELETE FROM Device WHERE `device-id` = %s", (deviceid,))
    cursor.execute("DROP TABLE IF EXISTS " + deviceid)
    db.commit()
    return cond

def __getDeviceLatestLocation(cursor, deviceid):
    """
        Retrieves the latest known location for a device. Search in the cache first, and if not found querry the database.
        Raises NoLocationDataException if no location could be found.
    """

    if deviceid in data_storage:
        try:
            lat = data_storage[deviceid][-1]["latitude"]
            long = data_storage[deviceid][-1]["longitude"]
            return (lat, long)
        except KeyError:
            print(data_storage[deviceid][-1])
            raise NoLocationDataException
    else:
        query = "SELECT latitude, longitude FROM {0} ORDER BY id DESC LIMIT 1;".format(deviceid) # could cause some issues if we 
        cursor.execute(query)
        device_location = cursor.fetchone()
        if device_location[0] == None or device_location[1] == None:
            raise NoLocationDataException
        return device_location

def __getNearbyObjects(deviceid, seuil):
    """
    Get the list of all objects detected **by other devices** in the specified range around the requested device.

    Args:
    - deviceid: str
    - seuil: number: the radius of the search zone
    """

    # TODO: improve this function, as it will most certainly end up being a huge bottleneck when having many clients and objects !!!

    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    cursor = db.cursor()
    
    try:
        latitude, longitude = __getDeviceLatestLocation(cursor, deviceid)
        # Récupération de la liste des appareils dans le périmètre
        neighbours = []
        for device in __queryAllDeviceIDs():
            if device != deviceid:
                try:
                    # lat2, long2 = __getDeviceLatestLocation(cursor, device)
                    # d = calculate_distance(latitude, longitude, lat2, long2)
                    d = 0
                    if d < seuil:
                        neighbours.append(device)

                except NoLocationDataException:
                    pass #if __getDeviceLatestLocation failed, because we don't have any location data yet


        # recuperer les objets vus/détectés par ces appareils
        objects = {}
        distances = {}
        for neighbour in neighbours:
            if neighbour in objects_storage:
                temp = objects_storage[neighbour]
                objects[neighbour] = []
                distances[neighbour] = []
                for (_, objData) in temp.items():
                    distance = calculate_distance(latitude, longitude, objData['latitude'], objData['longitude'])
                    if distance < seuil:
                        objects[neighbour].append(objData)
                        distances[neighbour].append(distance)
            # else:
            #     print("no objects close enough for neighbour", neighbour)

        return objects, distances
    
    except NoLocationDataException:
        print(deviceid, "has no known live-location (in cache, not DB).")
        return {}, {}

def __queryUserDeviceList(username):
    """
    Returns the list of all device id and device names associated with a user.

    Args:
    - username: str
    """
    
    
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    cursor = db.cursor()
    query = """
    SELECT Device.`device-id`, Device.name 
    FROM Device
    JOIN DeviceOwners ON Device.`device-id` = DeviceOwners.device
    WHERE DeviceOwners.owner = %s
    """ 
    
    cursor.execute(query, (username,))
    devices = cursor.fetchall()
    
    result = [{"device-id": device[0], "name": device[1]} for device in devices]
    return result

def __queryAllDeviceIDs():
    """
    Retrieves the list of all registed device id's from the database.

    Returns: list[str]
    """

    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    cursor = db.cursor()
    query = """
    SELECT Device.`device-id` 
    FROM Device
    """ 
    cursor.execute(query, ())
    devices = cursor.fetchall()
    devlist = [device[0] for device in devices]

    return devlist


## AUTHENTICATION

def hash_password(password):
    """
    Hashes the given password using bcrypt.

    Args:
        password (str): The password to be hashed.

    Returns:
        bytes: The hashed password.

    """
    if password != None and len(password)>0:
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password_bytes, salt)
        return hashed_password

def check_password(hashed_password, user_password):
    """
    Check if the provided user password matches the hashed password.

    Args:
        hashed_password (bytes): The hashed password stored in the database.
        user_password (str): The user's input password.

    Returns:
        bool: True if the user password matches the hashed password, False otherwise.
    """
    password_bytes = user_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_password)

@auth.verify_token
def verify_token(t):
    """
    Verify the authenticity of a token.

    Parameters:
    t (str): The token to be verified.

    Returns:
    bool: True if the token is valid, False otherwise.
    """
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], database = Config["db_name"])
    cursor = db.cursor()
    token=session.get('token')
    query = "SELECT * FROM Auth_Token WHERE token = %s AND `date-exp` > %s"
    cursor.execute(query, (token, datetime.now()))
    result = cursor.fetchall()
    return len(result) > 0

@auth.error_handler
def err_handler(error):
    """
    Error handler function for authentication errors.

    Parameters:
    - error: The error code.

    Returns:
    - A redirect response based on the error code.
    """
    match (error):
        case 401 :
            flash('You must be logged in to view this page.', 'danger')
            return redirect(url_for('login'))
        case 404 :
            return redirect(url_for('/'))
        case 302 :
            flash('You must be logged in to view this page.', 'danger')
            return redirect(url_for('login'))

def check_user_token():
    """
    Checks if the user token is valid and returns the corresponding username.

    Returns:
        str: The username associated with the token if it is valid.
        None: If the token is invalid or not found in the database.
    """
    token = session.get('token')
    
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    cursor = db.cursor()

    query = "SELECT user FROM Auth_Token WHERE token=%s"
    cursor.execute(query, (token,))
    res = cursor.fetchall()
    if cursor.rowcount==1:
        username = res[0][0]
        return username
    else:
        return None

## WUI Routes
@app.route('/')
def accueil():
    """
    Renders the index.html template with the appropriate variables.

    Returns:
        The rendered template with the 'is_authenticated' and 'username' variables.
    """
    is_authenticated = False
    username=''
    if session :
        is_authenticated = 'token' in session
        username = check_user_token()
    return render_template('index.html', is_authenticated=is_authenticated, username=username)

@app.route('/objects', methods=['GET', 'POST'])
def objects():
    return render_template('objects.html')

@app.route('/connectivityCheck', methods=['GET'])
def connCheck():
    return jsonify(time.time()), 200

@app.route('/post_data', methods=['POST'])
def post_data():
    """
    Endpoint for receiving and processing data sent via POST request.
    
    Returns:
        JSON response: A JSON response indicating the status of the request.
    """

    if request.method == 'POST': 
        # récupérer les données de la requête
        raw_data = request.get_data().decode('utf-8')
        raw_data= raw_data.removesuffix("\n")
        try:
            data = json.loads(raw_data)
            if data['type'] == MessageTypes.DEVICE_UPDATE:
                # device status update
                Q_out.put(data.copy()) #copy because we edit the message before DB insertion
                add_data_to_cache(data)
            elif data['type'] == MessageTypes.OBJECT_REPORT:
                # object observation
                for object in data['objects']:
                    object["tempId"] = object.pop("id") # move id as temp id
                    object["timestamp"]=data['timestamp']
                    object['seenby']=data['device-id']
                    if data['device-id'] in objects_storage:
                        if object["tempId"] in objects_storage[data['device-id']]:
                            object["id"] = objects_storage[data['device-id']][object["tempId"]]["id"]
                    # Ajouter les données à la base de données, donne un Id permanent si pas déjà connu
                    Interface.save_object_DB(object)
                    if not "id" in object:
                        return jsonify({"status": "error", "message": "Unknown/Unregistered device"}), 200
                    # Ajouter les données à la liste d'objets
                    if data['device-id'] in objects_storage:
                        objects_storage[data['device-id']][object['tempId']] = object
                    else:
                        objects_storage[data['device-id']] = {object['tempId']:object}
            else:
                logging.error("Not Implemented message type " + str(data['type']))

            return jsonify({"status": "success"}), 200
        except json.JSONDecodeError:
            print("Received malformed json data")
    else:
        return jsonify({"status": "error", "message": "Invalid method"}), 400 # not a POST request
            
def add_data_to_cache(data):
    """
    Add data to the cache based on the 'eui' value in the data dictionary.

    Parameters:
    - data (dict): The data to be added to the cache.

    Returns:
    - None
    """
   
    global data_storage

    # Verifier si l'eui est déjà dans le cache
    if data['device-id'] not in data_storage:
        # Ajourter l'eui au cache
        data_storage[data['device-id']] = [data]
    else:
        # Ajouter les données au cache lié à l'eui
        data_storage[data['device-id']].append(data)

    # Supprimer les données de plus d'une heure (amélioration: ne pas faire tous les devices a chaque fois)
    for device in data_storage:
        seuil=0
        while (data_storage[device][-1]['timestamp']-data_storage[device][seuil]['timestamp']) > 3600:
            seuil+=1

        data_storage[device]=data_storage[device][seuil:] 

@app.route('/get_data', methods=['GET'])
@auth.login_required
def get_data():

    # Récupérer les paramètres de la requête
    duration = request.args.get('duration')
    device = request.args.get('dev')

    data = {}
    
    # Se connecter à la base de données
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], database = Config["db_name"])
    cursor = db.cursor()

    # Vérifier si l'utilisateur est connecté
    username = check_user_token()

    # Récuperer la liste des devices associés à l'utilisateur
    query = "SELECT device FROM DeviceOwners WHERE owner = %s;"
    cursor.execute(query,(username,))
    result= cursor.fetchall()
    # Si l'utilisateur a des devices associés, récupérer les données de ces devices
    if len(result) !=0:
        for device in result[:][0]:
            # Récupérer les données de la base de données
            if duration != None and float(duration) > 60:
                duration = float(duration)
                if (device in data_storage) and len(data_storage[device])>0:
                    # on prend la période à partir de la dernière donnée connue
                    args = (datetime.fromtimestamp(data_storage[device][-1]['timestamp']-duration-1),)
                else : 
                    # sinon on prend à partir du temps courant
                    args = (datetime.fromtimestamp(datetime.now().timestamp()-duration-1),)
                
                # Récupérer les données de la base de données
                query = "SELECT * FROM " + device + " WHERE timestamp > %s"
                cursor.execute(query,args)
                result = cursor.fetchall()
                data[device]=data_labels_to_json(result,device)

            # Si possible récupérer les données de la mémoire cache
            else:
                data[device]=[]
                if device in data_storage:
                    if duration != None:
                        # on prend les infos de la durée demandée
                        duration = float(duration)
                        info = data_storage[device]
                        seuil = 0
                        while (info[-1]['timestamp']-info[seuil]['timestamp']) > duration+1:
                            seuil+=1
                        data[device]+=info[seuil:]
                    else :
                        # on prend tout
                        data[device]+=data_storage[device]
    return jsonify(data) 

@app.route('/get_latest_data', methods=['GET'])
@auth.login_required
def get_latest_data():
    """
    Retrieves the most recent data from the data storage for each devices.

    Returns:
        A JSON response containing the most recent data from the data storage, with convenient name added.
    """

    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], database = Config["db_name"])
    cursor = db.cursor()
    temp = {}

    for k in data_storage.keys():
        temp[k] = data_storage[k][-1] # get last data for device k
        query = "SELECT name FROM Device WHERE `device-id` = %s;"
        cursor.execute(query, [temp[k]['device-id']])
        try:
            res = cursor.fetchall()[0][0]
            temp[k]['name'] = res
        except IndexError:
            temp[k]['name'] = "unkown"
    
    # debug
    for k in data_storage.keys():
        temp[k] = data_storage[k][-1]


    return jsonify(temp)

def data_labels_to_json(data,table):
    result = []

    # Connexion à la base de données
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], database = Config["db_name"])
    cursor = db.cursor()

    # Récupérer les labels des données
    query = "DESC "+table
    cursor.execute(query)
    desc = cursor.fetchall()
    label = [desc[i][0] for i in range(len(desc))]
    for d in data:
        mesure={}
        mesure['timestamp']=d[1].timestamp()*1000
        for i in range(2,len(d)-1):
            mesure[label[i]]=d[i]
        result.append(mesure)
    return result

@app.route('/get_objects', methods=['GET'])
@auth.login_required
def get_objects():
    """
    Retrieves and returns the objects stored in the objects_storage.

    Returns:
        A JSON response containing the objects stored in the objects_storage.
    """
    return jsonify(objects_storage)

@app.route('/getDeviceList', methods=['GET', 'POST'])
@auth.login_required
def getDeviceList():
    """
    Retrieves a list of eui associated with the logged-in user.

    Returns:
        A JSON response containing the list of devices eui.
    """
    # Récupérer le nom d'utilisateur de la session
    username = session.get('username')
    
    # Se connecter à la base de données
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    cursor = db.cursor()

    # Récupérer la liste des devices associés à l'utilisateur
    query = "SELECT device FROM DeviceOwners WHERE owner = %s;"
    cursor.execute(query,(username,))
    result= cursor.fetchall()
    
    devices=[]
    length = len(result[:])

    # Si l'utilisateur a des devices associés, récupérer les eui de ces devices
    if length != None and length > 0:
        for device in result:
            # Récupérer les eui des devices associés à l'utilisateur
            query = "SELECT `device-id`, name FROM Device WHERE `device-id` = %s;"
            cursor.execute(query,(device[0],))
            res = cursor.fetchall()
            devices+=res
        # Retourner la liste des eui des devices associés à l'utilisateur en JSON
        return jsonify(devices)  
    return jsonify([])

@app.route('/visualize')
@auth.login_required
def visualize():
    """
    Renders the visualize.html template.

    Returns:
        The rendered visualize.html template.
    """

    selectedDevice = request.args.get('dev', None)
    if selectedDevice==None or selectedDevice == "":
        devices = __queryUserDeviceList(session.get('username'))
        defaultDevice = devices[0]['device-id']
        return redirect("/visualize?dev="+defaultDevice)
    else:
        fields = __queryAvailableFields(selectedDevice)
        try:
            fields.remove("timestamp")
        except ValueError:
            pass
        return render_template('visualize.html', selectedDevice=selectedDevice, fields=fields)

@app.route('/downloadall')
@auth.login_required
def downloadall():
    """
    Downloads all data from the data storage as a CSV file.

    Returns:
        Flask Response: Response object containing the CSV file as an attachment.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    header = ["timestamp", "latitude", "longitude", "altitude", "luminosity", 
              "vitesse_angulaire_X", "vitesse_angulaire_Y", "vitesse_angulaire_Z", 
              "pressure", "acceleration_X", "acceleration_Y", "acceleration_Z", 
              "angle", "azimuth"]
    #### Ajouts capteurs ####
    # ajouter les labels de vos capteurs au header
    
    #### Fin Ajouts capteurs ####
    writer.writerow(header)
    
    # Write data
    for device_id, datas in data_storage.items():
        for data in datas:
            writer.writerow([data[field] for field in header])
    
    output.seek(0)
    
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'iot_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

@app.route('/download', methods=['GET', 'POST'])
@auth.login_required
def download():
    """
    Handle the download route for retrieving data from the database and generating a CSV file.

    Returns:
        Response: Flask response object containing the generated CSV file as an attachment.
    """
    
    # DEVICE
    deviceid = request.args.get('dev', None)
    username = session.get('username')


    # Demande de donnée de l'utilisateur
    if request.method == 'POST':
        assert(deviceid != None)

        # Récupérer les paramètres de la requête
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        selected_fields = []
        for field in request.form.getlist('fields'):
            field = field.split(" ")
            for f in field:
                selected_fields.append(f)
        
        fmt='%Y-%m-%dT%H:%M'
        start_time = datetime.strptime(start_time, fmt)
        end_time = datetime.strptime(end_time, fmt)
        data = __getDeviceData(deviceid, selected_fields, start_time, end_time)

        # Generate CSV file
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(selected_fields)
        for row in data:
            writer.writerow(row)
        output.seek(0)

        return send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'data_{start_time.strftime("%Y%m%d_%H%M%S")}_to_{end_time.strftime("%Y%m%d_%H%M%S")}.csv'
        )
    
    else:
        devices = __queryUserDeviceList(username)
        if deviceid==None or deviceid == "" or deviceid=="undefined":
            deviceid = devices[0]['device-id']
            return redirect("/download?dev="+deviceid)
        else:
            fields = __queryAvailableFields(deviceid)
            return render_template('download.html', selectedDevice=deviceid, devices=devices, fields=fields)
       
@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Function to handle user login.

    Deletes expired authentication tokens from the database.
    Validates the login form submitted by the user.
    Checks the username and password against the database records.
    Generates a new authentication token and stores it in the database.
    Sets the session variables for the logged-in user.
    Redirects the user to the home page if login is successful.
    Displays an error message if login is unsuccessful.

    Returns:
        If login is successful, redirects to the home page.
        If login is unsuccessful, renders the login page with an error message.
    """
    # Connexion à la base de données
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    cursor = db.cursor()

    # Supprimer les tokens expirés
    query = "DELETE FROM Auth_Token WHERE `date-exp` < %s "
    cursor.execute(query,(datetime.now(),))
    
    form = LoginForm()
    if form.validate_on_submit():
        # Recuperation des données rentrées dans le formulaire
        username = form.username.data
        password = form.password.data
        cursor.fetchall()
        # Verification du username/password avec ce qui est enregistré dans la db
        query = "SELECT (password) FROM Users WHERE username = %s;"
        cursor.execute(query,(username,))
        result= cursor.fetchall()
        if cursor.rowcount == 1:
            pwdhash=result[0][0].encode("utf-8")
            # Verification du mot de passe
            if check_password(pwdhash,password):
                session['username'] = username
                query = "INSERT INTO Auth_Token (token, user, `date-exp`) VALUES (%s, %s, %s)"
                token = bcrypt.gensalt()
                cursor.execute(query, (token, username, (datetime.now() + timedelta(hours=2))))
                db.commit()
                session['token']=token
                url = request.args.get("next", '/')
                print("LOGIN SUCCESSFUL, REDIRECTING", url)
                return redirect(url)
        flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Register a new user.

    This function handles the registration process for a new user. It validates the registration form,
    checks if the username already exists in the database, and inserts the new user into the database
    if the username is unique. It also displays flash messages to indicate the status of the registration
    process and redirects the user to the appropriate page.

    Returns:
        A redirect response to the login page if the registration is successful, or the registration page
        with the registration form if there are validation errors or the username already exists.
    """

    # Connexion à la base de données
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    cursor = db.cursor()

    form = RegistrationForm()
    if form.validate_on_submit():
        # Recuperation des données rentrées dans le formulaire
        username = form.username.data
        password = hash_password(form.password.data)

        # Verification du username pour éviter que 2 personnes aient le même
        query = "SELECT (username) FROM Users WHERE username = %s;"
        cursor.execute(query,(username,))
        result= cursor.fetchall()

        # Si le username existe déjà dans la base de données afficher un message d'erreur
        if len(result) > 0:
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        else:
            # Ajout a la base de donnée
            query = "INSERT INTO Users (username,password) VALUES (%s,%s)"
            cursor.execute(query,(username,password))
            db.commit()
        flash('Account created successfully', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/help')
def help():
    """
    Renders the help.html template.

    Returns:
        The rendered help.html template.
    """
    return render_template('help.html')

@app.route('/logout')
def logout():
    """
    Logs out the user by removing the 'username' and 'token' from the session.
    Displays a flash message to inform the user that they have been logged out.
    Redirects the user to the login page.
    """
    # Supprimer les variables de session
    session.pop('username', None)
    session.pop('token')
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/map')
@auth.login_required
def map_view():
    """
    Renders the map view page.

    Returns:
        The rendered map.html template.
    """
    
    return render_template('map.html')

@app.route('/register_device', methods=['GET', 'POST'])
@auth.login_required
def register_device():
    """
    Register a device and associate it with a user.

    This function handles the registration of a device and its association with a user account.
    It first checks if the device is already registered. If not, it adds the device to the database
    and associates it with the currently logged-in user. If the device is already registered, it
    checks if it is already associated with the user. If not, it associates the device with the user.

    Returns:
        A redirect response to the 'register_device' page.

    """

    form_associate = DeviceAssociationForm()
    # Vérifier si le formulaire a été soumis et validé
    if form_associate.submit.data and form_associate.validate():
        # Recuperation des données du formulaire
        deviceid = form_associate.deviceid.data
        password = form_associate.password.data

        # Verifier si l'appareil est déjà enregistré
        if check_device_DB(deviceid,password)>0:
            # Verifier l'utilisateur
            username = check_user_token()
            if username:
                add_device_user_DB(deviceid,username) 
                flash('Device added successfully', 'success')
                return redirect(url_for('register_device'))
            else:
                flash('User not logged in', 'danger')
                return redirect(url_for('login'))
        else :
            flash('This device is not registered yet', 'danger')
            return redirect(url_for('register_device'))

    form = DeviceRegistrationForm()
    # print(form.validate_on_submit())
    # print(form.submit2.data)
    # print(form.validate())
    if form.submit2.data and form.validate():
        # Recuperation des données du formulaire
        deviceid = form.deviceid.data
        name = form.name.data
        hashed_password = hash_password(form.password.data)
        loraDevEui = form.lora_dev_eui.data
        if loraDevEui == "":
            loraDevEui=None

        # Verifier si l'appareil existe déjà
        
        if check_device_DB(deviceid) > 0:
            flash('Device already exists', 'danger')
            return redirect(url_for('register_device'))

        if loraDevEui != None:
            loraDevEui = loraDevEui.lower()
            temp = Interface.__getDeviceIDFromEUI(loraDevEui)
            if temp != None:
                flash('Provided LoRa EUI is already assigned to device ' + temp, 'danger')
                return redirect(url_for('register_device'))

        username = check_user_token()
        
        # Ajouter l'appareil a la base
        if username:
            add_device_DB(deviceid, name, hashed_password, loraDevEui)

            # TODO: Ajout a TTN via http ou via l'api
            # appid="stm32lora1"
            # requests.post(Config['APP_hostname']+"/applications/"+appid+"/devices/"+deviceid)

            # Assicier un utilisateur à l'appareil
            add_device_user_DB(deviceid, username, 1)
            flash('Device added successfully', 'success')
            return redirect(url_for('register_device'))
        else:
            flash('User not logged in', 'danger')
            return redirect(url_for('login'))

    return render_template('register_device.html', form_associate=form_associate, form=form)

def check_device_DB(deviceid,password=None):
    """
    Check the device in the database.

    Args:
        deviceid (str): The device EUI.
        password (str, optional): The device password. Defaults to None.

    Returns:
        int: Returns 1 if the device is found and the password is correct,
             -1 if the device is found but the password is incorrect,
             the number of devices found if no password is provided,
             or 0 if the device is not found in the database.
    """

    # Connexion à la base de données
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], database = Config["db_name"])
    cursor= db.cursor()

    if password != None:
        # Verification du username/password avec ce qui est enregistré dans la db
        query = "SELECT (password) FROM Device WHERE `device-id` = %s;"
        cursor.execute(query,(deviceid,))
        result= cursor.fetchall()
        if cursor.rowcount == 1:
            pwdhash=result[0][0].encode("utf-8")
            if check_password(pwdhash,password):
                return 1
            else :
                return -1
    else :
        query = "SELECT `device-id` FROM Device WHERE `device-id` = %s;"
        cursor.execute(query, (deviceid,))
        res = cursor.fetchall()
    if cursor.rowcount>0:
        return len(res)
    else :
        return 0

def check_link_device(deviceid, username):
    """
    Check if a device is linked to a specific user.

    Args:
        deviceid (str): The device EUI.
        username (str): The username of the user.

    Returns:
        int: The number of rows returned by the query.

    """

    # Connexion à la base de données
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], database = Config["db_name"])
    cursor= db.cursor()

    # Vérifier si l'appareil est associé à l'utilisateur
    query = "SELECT * FROM DeviceOwners WHERE device = %s AND owner=%s"
    cursor.execute(query, (deviceid, username))
    return len(cursor.fetchall())

def add_device_DB(deviceid, name, hashed_password, loraDevEui):
    """
    Add a device to the database.

    Args:
        deviceid (str): The device EUI.
        name (str): The name of the device.
        hashed_password (str): The hashed password of the device.

    Returns:
        None
    """

    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    cursor = db.cursor()
    query = "INSERT INTO Device (`device-id`, name, password, `lora-dev-eui`) VALUES (%s, %s, %s, %s)"
    cursor.execute(query, (deviceid, name, hashed_password, loraDevEui))  # Ensure password is hashed
    db.commit()

    table_create_query = "CREATE TABLE IF NOT EXISTS " + deviceid + \
    "(`id` int NOT NULL AUTO_INCREMENT PRIMARY KEY, `timestamp` DATETIME(3) NOT NULL," + \
    "`longitude` float DEFAULT NULL, `latitude` float DEFAULT NULL)" + \
    " ENGINE=InnoDB DEFAULT CHARSET=utf8"
    cursor.execute(table_create_query)
    db.commit()

def add_device_user_DB(deviceid, username, superowner=0):
    """
    Add a device user to the database.

    Args:
        deviceid (str): The device EUI.
        username (str): The username of the device owner.
        superowner (int, optional): The super-owner flag. Defaults to 0.

    Returns:
        None
    """
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    cursor = db.cursor()
    query = "INSERT INTO DeviceOwners (device, owner, `super-owner`) VALUES (%s, %s, %s)"
    cursor.execute(query, (deviceid, username, superowner))
    db.commit()

@app.route('/deviceList')
@auth.login_required
def deviceList():
    """
    Retrieves the list of devices associated with the logged-in user.

    Returns:
        A rendered template 'deviceList.html' with the following variables:
        - username: The username of the logged-in user.
        - devices: A list of devices associated with the user.
        - names: A list of names corresponding to the devices.
        
    Redirects:
        - If the user is not logged in, redirects to the 'login' page.
    """
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    cursor = db.cursor()
    username = session.get('username')
    if username:
        #selectionner les appareils de l'utilisateur
        query = "SELECT `device`, `super-owner` FROM DeviceOwners WHERE owner = %s"
        cursor.execute(query, (username,))
        res = cursor.fetchall()
        
        devices= [res[i][0] for i in range(len(res))]
        superowner = [res[i][1] for i in range(len(res))]

        names = []
        desc = []
        lora = []
        for i in devices:
            query = "SELECT `name`, `description`, `lora-dev-eui` FROM Device WHERE `device-id` = %s"
            cursor.execute(query, (i,))
            res = cursor.fetchall()
            names += [j[0] for j in res]
            desc += [j[1] for j in res]
            lora += [j[2] for j in res]

        devices = [i for i in devices]
        return render_template('deviceList.html', username=username, devices=devices, names = names, superowner=superowner, description=desc, lora=lora)
    else:
        flash('User not logged in', 'danger')
        return redirect(url_for('login'))
    
@app.route('/edit_device/<deviceid>', methods=['GET', 'POST'])
@auth.login_required
def edit_device(deviceid):
    """
    Deletes the device and its association with the user.

    Args:
        deviceid (str): The device id to be edited.

    Returns:
        redirect: A redirect response to the device list page.
    """
    
    username = check_user_token()

    if username:
        form = DeviceEditForm()
        
        db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
        cursor = db.cursor()
        query = "SELECT name, description, `lora-dev-eui` FROM Device WHERE `device-id` = %s"
        cursor.execute(query,(deviceid,))
        res = cursor.fetchall()
        
        if form.is_submitted():
            name = form.name.data
            password = form.password.data
            if password == None:
                flash('Please enter the password', 'danger')
                return redirect(url_for('edit_device', deviceid=deviceid))
            new_password = hash_password(form.new_password.data)
            description = form.description.data
            lora = form.lora.data.strip().lower()

            match check_device_DB(deviceid,password):
                case 1:
                    if check_superowner(deviceid,username):
                        check = Interface.__getDeviceIDFromEUI(lora) 
                        if check != None and check != deviceid:
                            flash('The provided LoRa EUI is already assigned', 'danger')
                            return redirect(url_for('edit_device'))        
                        else:
                            res = True
                            try:
                                __editDevice(deviceid,name,new_password,description,lora)
                            except Exception as e:
                                res = False
                                print("__editDevice failed with exception", e)
                            if res:
                                flash('The device was edited successfully.', "success")
                            else:
                                flash("Oops. Something went wrong while editing the device.", "info")
                            return redirect(url_for('deviceList'))
                    else:
                        flash('You are not the super user of this device', 'danger')
                        return redirect(url_for('deviceList'))
                case 0:
                
                    flash('This device is not registered yet', 'danger')
                    return redirect(url_for('deviceList'))
                case -1 :
                    flash('Wrong password', 'danger')
                    return redirect(url_for('edit_device', deviceid=deviceid))
        else:
            if len(res) != 0:
                curent_name=res[0][0]
                curent_description=res[0][1]
                form.name.data = curent_name
                form.description.data = curent_description
                form.lora.data = res[0][2]
            return render_template("edit_device.html", device=deviceid, form=form)
    
    else :
        flash('User not logged in', 'danger')
        return redirect(url_for('login'))

def check_superowner(deviceid, username):
    """
    Check if the given device and owner combination has super-owner privileges.

    Args:
        deviceid (str): The device identifier.
        username (str): The owner's username.

    Returns:
        bool: True if the device and owner combination has super-owner privileges, False otherwise.
    """
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    cursor = db.cursor()
    query = "SELECT `super-owner` FROM DeviceOwners WHERE device = %s AND owner=%s"
    cursor.execute(query, (deviceid, username))
    res = cursor.fetchall()
    return res[0][0]

@app.route('/delete_device/<deviceid>', methods=['GET', 'POST'])
@auth.login_required
def delete_dev(deviceid):
    """
    Deletes the device and its association with the user.

    Args:
        deviceid (str): The device EUI to be deleted.

    Returns:
        redirect: A redirect response to the device list page.
    """
    username = check_user_token()
    res = __delete_device(deviceid,username)
    if res==False:
        return jsonify({"status": "error"}), 400 
    return redirect(url_for('deviceList'))

@app.route('/profile', methods=['GET', 'POST'])
@auth.login_required
def profile():
    """
    Displays the user profile page.

    Returns:
        The rendered profile.html template with the 'username' variable.
    """
    username=''
    if 'token' in session :
        username = check_user_token()

    return render_template('profile.html', username=username)

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calcule la distance entre deux points sur la Terre spécifiés par leurs latitudes et longitudes.
    Utilise la formule de Haversine pour calculer la distance en kilomètres.
    
    :param lat1: Latitude du premier point
    :param lon1: Longitude du premier point
    :param lat2: Latitude du deuxième point
    :param lon2: Longitude du deuxième point
    :return: Distance entre les deux points en mètres
    """
    # Rayon de la Terre en kilomètres
    R = 6371000

    # Convertir les degrés en radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Différences des coordonnées
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    # Formule de Haversine
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Distance en mètres
    distance = R * c
    return distance

@app.route('/nearby_objects/<deviceid>', methods=['GET']) 
@auth.login_required
def nearby_objects(deviceid):
    """
    Retrieve nearby objects based on the given device ID.

    Args:
        deviceid (str): The device ID.
        size: the search radius (in meters, default=100)

    Returns:
        A rendered HTML template with the nearby objects.

    """
    defSearchSize = 100

    size = request.args.get("size", defSearchSize) 
    try:
        size = float(size)
    except ValueError:
        size = defSearchSize
        print("request contained invalid size parameter, using default")
    
    data, distances = __getNearbyObjects(deviceid, size)
    return render_template('nearby_objects.html', data=data, distances=distances, size=size)


"""==============================================================="""
"""                             API                               """
"""==============================================================="""

# USED BY FRONTED
@app.route('/api/getObject/<deviceid>', methods=['GET'])
def apiGetObject(deviceid):
    """
    Retrieve all objects identified by a device from the objects_storage, based on the device id (eui).

    Args:
        deviceid (str): The deviceid of the device.

    Returns:
        tuple: A tuple containing the JSON response and the HTTP status code.
            The JSON response contains the object if found, otherwise an error message.
            The HTTP status code is 200 if the object is found, otherwise 404.
    """

    if deviceid in objects_storage:
        return jsonify(list(objects_storage[deviceid].values())), 200
    elif deviceid in __queryAllDeviceIDs():
         return jsonify(None), 200 # device exists, but no object is seen by this device
    else:
        return jsonify({"error": "Object not found"}), 404

# USED BY CLIENTS
@app.route('/api/nearby_objects/<deviceid>', methods=['GET'])
def apinearby_objects(deviceid):
    """
    Retrieve nearby objects based on the given device ID.
    
    Antoine: retrieve objects seen by nearby devices (excluding the ones seen by ourselves)

    Args:
        deviceid (str): The device ID.

    Returns:
        list: A list of nearby objects.

    """
    
    # key= request.args.get('key')
    # username = get_user_from_api_key(key)
    # if username is None:
    #     return jsonify({"error": "Invalid API key"}), 401
    
    if deviceid not in __queryAllDeviceIDs():
        return jsonify({"error": "Device not found"}), 404
       

    defSearchSize = 100
    # recuperer les objets vus par ces appareils
    objects,_ = __getNearbyObjects(deviceid, defSearchSize) # Antoine: 100 is the default search size, can be changed by the user in the request

    #distances = {} 
    return jsonify(objects),200

@app.route('/api/getKey', methods=['GET'])
@auth.login_required
def get_api_keys():
    """
    Retrieves the API keys associated with the user.

    Returns:
        A JSON response containing the API keys.
    """
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    cursor = db.cursor()
    username = ''
    if 'token' in session:
        username = check_user_token()

    query = "SELECT `api-key` FROM Users WHERE username = %s"
    cursor.execute(query, (username,))
    api_keys = cursor.fetchall()
    return jsonify(api_keys[0][0])

@app.route('/api/genKey', methods=['GET', 'POST'])
@auth.login_required
def generate_api_key():
    """
    Generates a new API key for the user and updates it in the database.

    Returns:
        A JSON response containing the generated API key.
    """
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    cursor = db.cursor()
    username = ''
    if 'token' in session:
        username = check_user_token()

    # Générer une nouvelle clé API
    api_key = uuid.uuid4().bytes + uuid.uuid4().bytes
    # Convertir la clé API en une chaîne de caractères encodée en base64
    api_key_str = base64.b64encode(api_key).decode('utf-8')
    query = "UPDATE Users SET `api-key` = %s WHERE username = %s"
    cursor.execute(query, (api_key_str, username))
    db.commit()
    api_key = {"api_key": api_key_str}
    
    return jsonify(api_key)

def __get_user_from_api_key(api_key):
    """
    Retrieve the username associated with the given API key.

    Args:
        api_key (str): The API key to be verified.

    Returns:
        str: The username associated with the API key if it is valid.
        None: If the API key is invalid or not found in the database.
    """
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    cursor = db.cursor()
    query = "SELECT username FROM Users WHERE `api-key` = %s"
    cursor.execute(query, (api_key,))
    result = cursor.fetchall()
    if len(result) == 1:
        return result[0][0]
    else:
        return None

@app.route('/api/deviceList', methods=['GET', 'POST'])
def apiDeviceList():
    """
    Retrieves a list of devices from the database.

    Returns:
        A JSON response containing the list of devices, where each device is represented as a dictionary with 'dev-eui' and 'name' keys.
    """
    key = request.args.get('key')
    username = __get_user_from_api_key(key)
    return jsonify(__queryUserDeviceList(username))

@app.route('/api/deviceData/<deviceid>', methods=['GET'])
def apiDevice_data(deviceid):
    """
    Retrieve data from the device data table based on the specified device ID and time range.

    Args:
        deviceid (str): The device ID.

        Optional:
        - start_time, end_time : formated string %Y-%M-%d %H-%m-%S
        - dataFields : list of data fields (ex: ['latitude', 'longitude'])

    Returns:
        flask.Response: A JSON response containing the retrieved data.

    """

    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    cursor = db.cursor()
    key = request.args.get('key')
    username = __get_user_from_api_key(key)
    # TODO: check if user is allowed to querry the data from this device

    start_date = request.args.get('start_date', default=(datetime.now() - timedelta(days=1)))
    end_date = request.args.get('end_date', default=datetime.now())
    
    fmt='%Y-%m-%d %H:%M:%S'
    if type(start_date) == str:
        start_date = datetime.strptime(start_date, fmt)
    if type(end_date) == str:
        end_date = datetime.strptime(end_date, fmt)       

    dataFields = request.args.get('dataType')

    data = __getDeviceData(deviceid, dataFields, start_date, end_date)
    return jsonify(data), 200
    
    # return jsonify({"error": "Invalid data type"})

    # query = f"""
    # SELECT * FROM Data
    # JOIN Device ON Data.source = Device.`device-id`
    # JOIN DeviceOwners ON Device.`device-id` = DeviceOwners.device
    # WHERE DeviceOwners.owner = %s 
    # AND Data.timestamp BETWEEN %s AND %s
    # AND Device.`device-id` = %s   
    # ORDER BY Data.timestamp DESC;
    # """

    # cursor.execute(query, (username, start_date, end_date, deviceid))
    # data = cursor.fetchall()
    # # print(data)
    # # print(datetime.timestamp(data[0][0]))
    
    # columns = [col[0] for col in cursor.description]
    # to_remove =[]
    # to_remove.append(columns.index('password'))
    # to_remove.append(columns.index('source'))
    # to_remove.append(columns.index('dev-eui'))
    # for col in range(len(columns)-1):
    #     if not (columns[col] in select_clause) and select_clause!="*":
    #         to_remove.append(col)
    
    # indexes = list(range(0,len(columns)-1))
    # to_remove.sort(reverse=True)
    # for i in to_remove:
    #     columns.pop(i)
    #     indexes.pop(i)
    # data = [[row[i] for i in indexes] for row in data]
    
    # result = [dict(zip(columns, row)) for row in data]
    # for i in range(len(result)):
    #     result[i]["timestamp"]=datetime.timestamp(result[i]["timestamp"])
    # return jsonify(result),200

@app.route('/api/publicDeviceData/<deviceid>', methods=['GET'])
def publicApiDevice_data(deviceid):
    """
    Retrieve data from the 'Data' table based on the specified device EUI and time range.

    Args:
        deviceid (str): The device EUI.

    Returns:
        flask.Response: A JSON response containing the retrieved data.

    """
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    cursor = db.cursor()

    key = request.args.get('key')
    username = __get_user_from_api_key(key)

    start_date = request.args.get('start_date', default=(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'))
    end_date = request.args.get('end_date', default=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    dataType = str(request.args.get('dataType', default='*'))

    if dataType in data_format.keys():
        select_clause = dataType
    elif dataType == "*":
        select_clause = "*"
    else:
        return jsonify({"error": "Invalid data type"})

    query = f"""
    SELECT * FROM Data
    JOIN Device ON Data.source = Device.`device-id`
    JOIN DeviceOwners ON Device.`device-id` = DeviceOwners.device
    WHERE Data.timestamp BETWEEN %s AND %s
    AND Device.`device-id` = %s   
    AND Device.status = 'public'
    ORDER BY Data.timestamp DESC;
    """
    
    cursor.execute(query, (username, start_date, end_date, deviceid))
    data = cursor.fetchall()
    
    columns = [col[0] for col in cursor.description]
    
    result = [dict(zip(columns, row)) for row in data]
    
    return jsonify(result)

@app.route('/api/registerDevice', methods=['POST'])
def apiRegisterDevice():
    """
    Register a device with the given parameters.

    Parameters:
    - deviceid (str): The device EUI.
    - name (str): The name of the device.
    - pwd (str): The password for the device.

    Returns:
    None
    """
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    cursor = db.cursor()

    deviceid = request.args.get('deviceid')
    name = request.args.get('name')
    password = request.args.get('pwd')
    key = request.args.get('key')
    username = __get_user_from_api_key(key)
    if  not (name and deviceid and password and key) :
        return jsonify({"status": "error", "message": 'Require Fields : deviceid, name, pwd, key'}), 400

    if username:

        query = "SELECT `device-id` FROM Device WHERE `device-id` = %s;"
        cursor.execute(query, (deviceid,))
        result = cursor.fetchall()
        if len(result) > 0:
            if check_link_device(deviceid,username):
                return jsonify({"status": "error", "message": 'Device already exists'}), 400 
            else:
                add_device_user_DB(deviceid,username)
                return jsonify({"status": "success", "message": "device lié au compte"}), 200        
        # Ajouter l'appareil a la base
        add_device_DB(deviceid,name,password)
        add_device_user_DB(deviceid,username)

        return jsonify({"status": "success"}), 200
    else :
        return jsonify({"status": "error", "message": 'API key not linked to any user'}), 401

@app.route('/api/deleteDevice', methods=['POST'])
def apiDeleteDevice():
    """
    API endpoint for deleting a device.

    Parameters:
    - deviceid (str): The device EUI.
    - key (str): The API key.

    Returns:
    - JSON response: A JSON response indicating the status of the deletion operation.
    """
    deviceid = request.args.get('deviceid')
    
    key = request.args.get('key')

    username = __get_user_from_api_key(key)
    if  not (deviceid and key) :
        return jsonify({"status": "error", "message": 'Require Fields : deviceid key'}), 400

    if username:
        if check_link_device(deviceid,username):
            __delete_device(deviceid,username)
            return jsonify({"status": "success"}), 200
        else:
            return jsonify({"status": "error", "message": 'no such linked Device was found'}), 400 
    else :
        return jsonify({"status": "error", "message": 'API key not linked to any user'}), 401

@app.route('/api/neighbourList/<deviceid>', methods=['GET'])
def apiNeighbourList(deviceid):
    """
    Retrieves the list of neighboring sources based on the given device EUI.

    Args:
        deviceid (str): The device EUI.

    Returns:
        list: A list of neighboring sources.

    """
    db = mysql.connector.connect(host=Config["SQL_host"], user=Config["SQL_username"], password=Config["SQL_password"], database=Config["db_name"])
    cursor = db.cursor()

    key = request.args.get('key')
    size = request.args.get('size', 0.001)
    username = __get_user_from_api_key(key)
    if username is None:
        return jsonify({"error": "Invalid API key"}), 401

    neighbours=[]
    if username:
        query = """
            SELECT latitude, longitude
            FROM Data
            WHERE source = %s
            ORDER BY timestamp DESC
            LIMIT 1;
        """
        cursor.execute(query, (deviceid,))
        device_location = cursor.fetchone()
        if device_location is None:
            return jsonify([])
        latitude, longitude = device_location

    query = """
        SELECT DISTINCT Device.`device-id`, Device.name
        FROM Data
        JOIN Device ON Data.source = Device.`device-id`
        JOIN DeviceOwners ON Device.`device-id` = DeviceOwners.device
        AND POWER(Data.latitude - %s, 2) + POWER(Data.longitude - %s, 2) <= POWER(%s, 2)
        AND Data.timestamp > %s;
        AND Device.`device-id` != %s;
    """
    cursor.execute(query, (latitude, longitude, size, datetime.now() - timedelta(seconds=15), deviceid))
    neighbours = cursor.fetchall()

    
    return jsonify(neighbours)


"""==============================================================="""
"""                          Lancement                            """
"""==============================================================="""


def IPnode(Q_output: Queue, config):
    """
    Starts the IP node server.

    Args:
        Q_output (Queue): The output queue for sending messages.
        config (dict): The configuration settings.

    Returns:
        None
    """
    global Q_out, Config
    Config=config
    Q_out=Q_output
    db = mysql.connector.connect(host=Config["SQL_host"], user=config["SQL_username"], password=Config["SQL_password"])
    app.app_context().push()
    with app.app_context():
        db_cursor = db.cursor()
        db_query = "USE "+ config["db_name"]
        db_cursor.execute(db_query)
        print(config['server_host'], config['server_port'])
        app.run(host=config['server_host'], port=int(config['server_port']), debug=False)

def IPnode_noconfig(Q_output: Queue):
    """
    Starts the IP node server without any configuration.

    Args:
        Q_output (Queue): The output queue for sending messages.

    Returns:
        None
    """
    global Q_out
    Q_out = Q_output
    
    app.run(host='0.0.0.0', port=5000, debug=True, ssl_context='adhoc')
    
if __name__ == '__main__':
    print("INFO: launching IP as main script")
    q = Queue()
    IPnode_noconfig(q)