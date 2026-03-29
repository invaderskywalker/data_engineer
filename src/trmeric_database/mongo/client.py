## src.trmeric_database/mongo/MongoDBClient.py


import os
from pymongo import MongoClient
import urllib.parse
from dotenv import load_dotenv
import threading

# Load env variables early
load_dotenv()


MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
MONGO_USER = os.getenv("MONGO_USER")
MONGO_DATABASE = os.getenv("MONGO_DATABASE")

encoded_username = urllib.parse.quote(MONGO_USER)
encoded_password = urllib.parse.quote(MONGO_PASSWORD)
MONGO_URL = f"mongodb+srv://{encoded_username}:{encoded_password}@trmericnosql.myolrr.mongodb.net/?retryWrites=true&w=majority&appName=trmericnosql"


import warnings
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    module="pymongo.ocsp_cache"
)
from cryptography.utils import CryptographyDeprecationWarning

warnings.filterwarnings(
    "ignore",
    category=CryptographyDeprecationWarning,
    module="pymongo.ocsp_support"
)
warnings.filterwarnings(
    "ignore",
    category=CryptographyDeprecationWarning,
    module="pymongo.ocsp_cache"
)


class MongoBaseClient:
    _instance = None
    _lock = threading.Lock()  # Ensures thread-safety for first init

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:  # Double-checked locking
                    cls._instance = super(MongoBaseClient, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return  # Avoid reinitializing
        self.connection_string = MONGO_URL
        if not self.connection_string:
            raise ValueError("MONGO_URL environment variable not set")

        self.client = MongoClient(self.connection_string)
        self.db = self.client[MONGO_DATABASE]
        print("listing all collections ---", self.db.list_collection_names())

        self._initialized = True

    def get_collection(self, collection_name):
        return self.db[collection_name]

    def create_collection(self, collection_name):
        if collection_name not in self.db.list_collection_names():
            self.db.create_collection(collection_name)
            return True
        return False

    def drop_collection(self, collection_name):
        self.db[collection_name].drop()
        return True

    def close(self):
        self.client.close()


mongo_client = MongoBaseClient()