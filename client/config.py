import configparser

global config

config = configparser.ConfigParser()
config.read('config.conf')
