import pyrebase
import os
import firebase_admin
from firebase_admin import credentials
from dotenv import load_dotenv

def init_firebase():
    load_dotenv()

    config = {
        "databaseURL": os.getenv("databaseURL"),
        "apiKey": os.getenv("apiKey"),
        "authDomain": os.getenv("authDomain"),
        "projectId": os.getenv("projectId"),
        "storageBucket": os.getenv("storageBucket"),    
        "messagingSenderId": os.getenv("messagingSenderId"),
        "appId": os.getenv("appId"),
        "measurementId": os.getenv("measurementId")
    }

    firebase = pyrebase.initialize_app(config)
    return firebase


def init_firebase_admin():
    load_dotenv()

    cred = credentials.Certificate("./admin-cred.json")
    firebase_admin.initialize_app(cred)
    return firebase_admin