# (c) adarsh-goel
import os
from os import getenv, environ
from dotenv import load_dotenv



load_dotenv()

class Var(object):
    MULTI_CLIENT = False
    API_ID = int(getenv('API_ID', '25090882'))
    API_HASH = str(getenv('API_HASH', '6aa9d30c71be8b8c3d74f5541318b201'))
    BOT_TOKEN = str(getenv('BOT_TOKEN', '8108956872:AAFL7_Ka3Opad0zpWAC3u67H3E5YzoIcjUY'))
    name = str(getenv('name', 'filetolinkbot'))
    SLEEP_THRESHOLD = int(getenv('SLEEP_THRESHOLD', '60'))
    WORKERS = int(getenv('WORKERS', '4'))
    BIN_CHANNEL = int(getenv('BIN_CHANNEL', '-1003189494068'))
    PORT = int(getenv('PORT', '8091'))
    BIND_ADRESS = str(getenv('WEB_SERVER_BIND_ADDRESS', '0.0.0.0'))
    PING_INTERVAL = int(environ.get("PING_INTERVAL", "1200"))  # 20 minutes
    OWNER_ID = set(int(x) for x in os.environ.get("OWNER_ID", "7676516456").split())  
    NO_PORT = bool(getenv('NO_PORT', False))
    APP_NAME = None
    OWNER_USERNAME = str(getenv('OWNER_USERNAME', 'inevitable1433'))
    if 'DYNO' in environ:
        ON_HEROKU = True
        APP_NAME = str(getenv('APP_NAME'))
    
    else:
        ON_HEROKU = False
    FQDN = str(getenv('FQDN', '144.24.147.39:8091')) if not ON_HEROKU or getenv('FQDN', '144.24.147.39:8091') else APP_NAME+'.herokuapp.com'
    HAS_SSL=bool(getenv('HAS_SSL',False))
    if HAS_SSL:
        URL = "https://{}/".format(FQDN)
    else:
        URL = "http://{}/".format(FQDN)
    DATABASE_URL = str(getenv('DATABASE_URL', 'mongodb+srv://rxalinks:rxalinks@rxalinks.u1sxsgv.mongodb.net/?appName=rxalinks'))
    UPDATES_CHANNEL = str(getenv('UPDATES_CHANNEL', 'imgoogboy99b'))
    BANNED_CHANNELS = list(set(int(x) for x in str(getenv("BANNED_CHANNELS", "")).split())) 
