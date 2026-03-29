# socket_initializer.py
from flask_socketio import SocketIO

class SocketInitializer:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SocketInitializer, cls).__new__(cls)
            cls._instance.socketio = SocketIO(cors_allowed_origins="*")
        return cls._instance

    def get_socketio(self):
        return self.socketio


    
