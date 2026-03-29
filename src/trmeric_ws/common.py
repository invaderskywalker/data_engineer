import jwt
from src.controller.tango import TangoController
from src.controller.agents import AgentsController
# from src.controller.agents_v2 import AgentsV2Controller
from src.controller.super_agent import SuperAgentController

# Store active connections with user identifier as the key
active_connections = {}
all_connections = {}

# Controllers
controller = TangoController()
agentController = AgentsController()
# agentsV2Controller = AgentsV2Controller()
superAgentController = SuperAgentController()

def decodeAuthToken(token):
    try:
        decoded = jwt.JWT().decode(token, do_verify=False) 
        return decoded
    except Exception as e:
        return None

