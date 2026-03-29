from flask import request
from src.database.dao import TangoDao
from .common import active_connections, agentController
from src.api.logging.ProgramState import ProgramState

def register_state_events(socketio):
    @socketio.on("tango_state_upsert")
    def tango_state_upsert(requestBody):
        print("tango_state_upsert came", requestBody)
        user_identifier = request.sid
        print("Received tango_state_upsert event:", requestBody)
        
        # Create/get program state for this user
        program_state = ProgramState.get_instance(active_connections[user_identifier]['user_id'])

        session_id = requestBody.get("session_id")
        key = requestBody.get("key")
        value = requestBody.get("value")
        request_body = requestBody.get("request_body")
        
        program_state.set("session_id", session_id)
        program_state.set("current_prompt", f"Tango State Upsert: {key}:{value}")
    
        print("active_connections[user_identifier]", active_connections[user_identifier])
        tenant_id = active_connections[user_identifier]['tenant_id']
        user_id = active_connections[user_identifier]['user_id']
        client_id = active_connections[user_identifier]['client_id']
        program_state.set("socket_id", client_id)
        TangoDao.insertTangoState(tenant_id, user_id, key, value, session_id)
        agentController.general_agent_conv(socketio=socketio, client_id=client_id, session_id=session_id, tenant_id=tenant_id, user_id=user_id, requestBody=request_body)
