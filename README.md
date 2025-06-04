# Plateforme IoT pour véhicules

## Description du projet
Ce projet vise à développer une plateforme IoT pour collecter et transmettre des données de véhicules en utilisant un réseau de capteurs et en les transmettant via le réseau mobile ou LoRa.

## Fonctionnalités principales
- Collecte de données de véhicules via des capteurs
- Transmission des données via réseau mobile ou LoRa
- Visualisation des données depuis un site web
- Recuperation des données via une API

## Materiel utilisé

### Jetson Orin Nano
La jetson Orin Nano est l'ordinateur central a notre projet. Elle va gérer le traitement des données mais aussi servir à faire toutes les opérations de traitement de l'image.

### ESP32
La carte ESP32 sert de carte d'aquisition à la fois pour récupérer les données des capteurs mais aussi pour se connecter facilement en bluetooth à un appareil mobile.

### LoPy4
La carte LoPy4 sert comme émetteur/récepteur Lora. Elle pourrait être remplacé par un limple émetteur/recepteur

### Camera OAK-D
La caméra OAK-D permet de facilement faire de la reconnaissance d'image (avec la jetson, il serait possible d'uiliser une camera basique grace aux connecteurs csi)

## Technologies utilisées
### Transmission de données : 
- Internet (IP) (2G, 3G, 4G, 5G)
- LoRaWan via TTN

## Installation
### Docker Compose
```bash
    ./launch.sh
```
### Manuellement
- Avoir mySQL/mariaDB installé, root nopassword, màj config.conf en conséquence
- Avoir Python >=3.11 installé, installer les dépendances: `pip install -r requirements.txt`
- Lancer mySQL/mariaDB, manuellement ou via systemctl
- Dans le dossier PlatformeCollecteDonnees/src/serveur, lancer la commande `python main.py`

## Configuration
Dans `PlatformeCollecteDonnees/src/{client ou serveur}/config.conf`, il est possible de configurer les endpoints réseaux

## Utilisation Client
1. Brancher une esp et téléverser son programme 
2. Brancher une lopy4 et téléverser son programme (!! Vérifier les informations de connexion au réseau LoRa !!)
3. Installer l'application mobile
4. lancer l'application mobile et se connecter a la plateforme en bluetooth


