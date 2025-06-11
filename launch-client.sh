#!/usr/bin/bash


echo "THIS SCRIPT ONLY LAUNCHES THE CLIENT. A MYSQL SERVER MUST BE AVAILABLE"
echo "One option is to use the mysql docker container provided with the server"



cd client || exit

if [[ "$VIRTUAL_ENV" != "" ]]
then
  echo "In a VENV, continuing... (if deps are missing, it's up to you to install them in a venv, or delete the venv for the program to recreate one automatically and install all requirements for you)"
else
  echo "Not in a venv, searching for one.."
  if [ ! -f ./venv/bin/activate ]; then
    echo "No venv was found in $(pwd), creating one"
    # creating venv
    python -m venv venv
    # activating venv
    source ./venv/bin/activate
    # installing deps
    pip install -r requirements.txt
  else
    echo "A venv was found, activating..."
    source ./venv/bin/activate
  fi
fi

# should be in a venv now, sanity check 
which python

## Network Setup
echo -e "If not running for debug, remember to uncomment the network config !"
#sudo cp hotspot.nmconnection /etc/NetworkManager/system-connections/hotspot.nmconnection
#sudo nmcli radio wifi on
#sudo nmcli connection up Hotspot # now the wifi hotspot should be enabled, allowing for ssh and more

# launching the main program
python main.py