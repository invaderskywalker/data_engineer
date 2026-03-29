import jwt
from src.controller.super_agent import SuperAgentController

# Store active connections with user identifier as the key
active_connections = {}
all_connections = {}
superAgentController = SuperAgentController()

def decodeAuthToken(token):
    try:
        decoded = jwt.JWT().decode(token, do_verify=False) 
        return decoded
    except Exception as e:
        return None

