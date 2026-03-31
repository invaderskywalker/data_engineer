from flask import request
import traceback
from src.api.logging.AppLogger import appLogger
from src.api.logging.TimingLogger import start_timer, stop_timer, log_event_start
# from src.api.logging.ProgramState import ProgramState
from .common import active_connections, superAgentController

def register_agent_events(socketio):

    @socketio.on("super_agent")
    def handle_super_agent(requestBody):
        try:
            from datetime import datetime, timedelta, timezone
            now = datetime.now()
            print("Incoming time:", now.strftime("%Y-%m-%d %H:%M:%S.%f"))
            ist_time = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
            print("Incoming time (IST):", ist_time.strftime("%Y-%m-%d %H:%M:%S.%f"))
            # Get user_id from active_connections
            user_identifier = request.sid
            user_id = active_connections[user_identifier]['user_id']
            
            # Create/get program state for this user
            # program_state = ProgramState.get_instance(user_id)
            # agent_name = requestBody.get("mode") or None
            session_id = requestBody.get('session_id') or ''
            # message = requestBody.get("message") or None
            # log_event_start("general_agent_v2", client_id=request.sid, agent=agent_name, session_id=session_id)
            # timer_id = start_timer("general_agent_v2_event_processing", client_id=request.sid)
            client_id = active_connections[user_identifier]['client_id']
            tenant_id = active_connections[user_identifier]['tenant_id']
            # agent_timer = start_timer(
            #     "general_agent_v2_controller", 
            #     user_id=user_id,
            #     tenant_id=tenant_id,
            #     agent=agent_name, 
            #     session_id=session_id
            # )
            superAgentController.handle_super_agent(
                tenant_id=tenant_id,
                user_id=user_id,
                socketio=socketio,
                client_id=client_id,
                requestBody=requestBody,
                session_id=session_id,
            )
            # stop_timer(agent_timer)
            
        except Exception as e:
            appLogger.error({"event": "general_agent_v2", "error": e, "traceback": traceback.format_exc()})
            socketio.emit("general_agent_v2", 'failed', room=client_id)
        # finally:
        #     stop_timer(timer_id)
