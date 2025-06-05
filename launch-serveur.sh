#!/usr/bin/bash


if ! systemctl -q is-active docker; then
    echo "Docker is not running, launching with systemctl"; 
    sudo systemctl start docker
else 
echo "Docker is running OK" 
fi

cd PlateformeCollecteDonnees/src/ || exit

echo "Lancemement du serveur (mySQL + Web UI/API via Docker Compose)"
docker compose up --build --remove-orphans

cd ../..
pwd
