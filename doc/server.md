# Data Collection Server & Web App Interaface

The server side of the platform is composed of a WepApp, written in Python with Flask, and a database (mySQL or MariaDb). Docker images and a compose file are available.

## Run the Code
### With Docker Compose
Docker images for both the mySQL database and the webapp itself are provided, and can be easily deployed using docker compose. The following script does it for you:
```bash
    ./launch-server.sh
```
### Manually
- Have mySQL/MariaDB installed and configured (see below); Python version >=3.10
- In the server's directory, do the following:
    - Create a python virtal environment (venv): `python -m venv <path to venv>`, and active it, ie `source <path to venv>/bin/activate`
    - Install runtime dependancies with pip: `pip install -r requirements.txt`
    - Launch the app: `python main.py`

## Configuration
In the `seuveur/config.conf` file, one can set:
- the database settings (endpoint, authentication)
- connection with *The Things Network* (endpoint, authentication)

## Usage
The workflow is as follow:
- Create an accout
- Login into your account
- Register a device (_don't forget the LoRa DevEUI if using LoRaWANN_)
- Consult the data live with the Visualize and Map page
- Download the data
    
### API
Command-line usage example, with HTTPie:
```sh
# get request
http <url>/api/deviceData/<deviceid> key==<your api key> start_date=="2025-01-01 00:00:00"
```
TODO: list and doc of all endpoints
