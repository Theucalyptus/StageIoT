from queue import Queue
import paho.mqtt.client as mqtt

Q_output : Queue

def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Connected with result code {reason_code}")

def on_message(client, userdata, msg):
    print("MQTT on_message: received from LoRa")
    Q_output.put(msg)
    

def on_subscribe(mqttc, obj, mid, granted_qos, arg):
    print("\nSubscribe: " + str(mid) + " " + str(granted_qos))

def on_disconnect(mqttc, userdata, rc):
    print("\nDisconnect with result code %s", rc)
    print("\nTODO: try to reconnect")

def MQTTnode(input,Q_LoRa : Queue):
    print("Starting MQTT node")
    global Q_output
    Q_output = Q_LoRa
    mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqttc.on_connect = on_connect
    mqttc.on_message = on_message
    mqttc.on_subscribe = on_subscribe
    mqttc.on_disconnect = on_disconnect
    mqttc.username_pw_set(username=input['mqtt_username'], password=input['password'])
    # secure connection between TTN server and this server (MQTT client)
    mqttc.tls_set()	# default certification authority of the system
    mqttc.connect(input['hostname'],input['port'],60)
    mqttc.subscribe("#", 0)	# all device uplinks
    
    mqttc.loop_forever()
    