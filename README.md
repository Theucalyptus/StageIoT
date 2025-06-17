# Plateforme IoT pour véhicules

## Description du projet
Ce projet vise à développer une plateforme IoT pour collecter et transmettre des données de véhicules en utilisant un réseau de capteurs et en les transmettant via le réseau mobile ou LoRa.

## Fonctionnalités principales
- Collecte de données de véhicules via des capteurs
- Transmission des données via réseau mobile ou LoRa
- Visualisation des données depuis un site web
- Recuperation des données via une API

## Materiel

### Jetson Orin Nano
La jetson Orin Nano est l'ordinateur central a notre projet. Elle va gérer le traitement des données mais aussi servir à faire toutes les opérations de traitement de l'image.

### LoPy4
La carte LoPy4 sert comme émetteur/récepteur Lora. Elle pourrait être remplacé par un slimple émetteur/recepteur

### Camera OAK-D
La caméra OAK-D permet de facilement faire de la reconnaissance d'image (avec la jetson, il serait possible d'uiliser une camera basique grace aux connecteurs csi)

## Technologies utilisées
### Transmission de données : 
- Internet (IP) (2G, 3G, 4G, 5G)
- LoRaWan via TTN

## Usage
### Collecteur de données et Interface WEB
#### Via Docker Compose
Des images docket des différents composants de l'application web sont disponibles, et peuvent être simplement déployées à l'aide de docker compose, dont l'utilisation est scripté dans le fichier suivant:
```bash
    ./launch-serveur.sh
```
#### Manuellement
- Dépendances mySQL/mariaDB installé et configuré (voir plus bas); Python en version >=3.10
- Depuis le dossier `serveur`, faire les actions suivantes 
    - Si possible, créer un environnement python virtuel (venv), par exemple avec la commande `python -m venv venv`, et l'activer
    - Installer les dépendances: `pip install -r requirements.txt`
    - Lancer l'application avec `python main.py`

#### Configuration
Dans `seuveur/config.conf`, il est possible de configurer:
- la connexion à la base de donnée mySQL/mariaDB (addresse réseau, identifiants)
- les identifiants et addresses réseaux pour la connexion avec *The Things Network*

### Client
- all sensors are registered in `sensorsList`. if multiple sensors provide the same data field, the data from the latest one will override the others. 
- 

