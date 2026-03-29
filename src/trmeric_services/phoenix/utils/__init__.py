from src.trmeric_database.dao import TangoDao
from src.trmeric_database.Database import db_instance
from ..constants import *


class PhoenixUtils:
    @staticmethod
    def checkIfAgentSwitch(session_id, user_id):
        key = AGENT_INITIATE_SWITCH_OCCURED
        items = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id, user_id, key)
        if (len(items) > 0):
            return True
        return False
    
    @staticmethod
    def deleteAgentSwitch(session_id, user_id):
        key = AGENT_INITIATE_SWITCH_OCCURED
        TangoDao.deleteTangoStatesForSessionIdAndUserAndKey(session_id, user_id, key)
    
    @staticmethod
    def checkCurrentAgent(session_id, user_id):
        key = CURRENT_ACTIVE_AGENT
        items = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id, user_id, key)
        if (len(items) > 0):
            return items[0]["value"]
        return ORION_ID
    
    @staticmethod
    def sendCurrentAgentInfoToUser(socketio, client_id, current_agent):
        socketio.emit("agentv4", 
            {
                "event": "current_agent", "agent":  {"id": current_agent, "name": PhoenixUtils.convert_to_title(current_agent)} 
            }, 
            room=client_id
        )
        
    @staticmethod
    def convert_to_title(text):
        return text.replace("_", " ").title()

