from flask import request
import json
import traceback
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_api.logging.TimingLogger import start_timer, stop_timer, log_event_start
from src.trmeric_api.logging.ProgramState import ProgramState
from .common import active_connections, agentController, controller, superAgentController
from src.trmeric_database.Redis import RedClient

def register_agent_events(socketio):
    @socketio.on("general_agent")
    def handle_general_agent(requestBody):
        # Get user_id from active_connections
        user_identifier = request.sid
        user_id = active_connections[user_identifier]['user_id']
        
        # Create/get program state for this user
        program_state = ProgramState.get_instance(user_id)
        
        agent_name = requestBody.get("agent", "unknown")
        if agent_name == "unknown":
            agent_name = requestBody.get("agent_name", "unknown")
        session_id = requestBody.get('session_id') or ''
        message = requestBody.get("message") or None
        
        # Set program state variables
        if message: program_state.set("current_prompt", message)
        program_state.set("current_agent", agent_name)
        program_state.set("session_id", session_id)
        
        log_event_start("GENERAL_AGENT", client_id=request.sid, agent=agent_name, session_id=session_id)
        timer_id = start_timer("general_agent_event_processing", client_id=request.sid)
        try:
            client_id = active_connections[user_identifier]['client_id']
            tenant_id = active_connections[user_identifier]['tenant_id']
            
            agent_timer = start_timer("general_agent_controller", 
                                     user_id=user_id, 
                                     tenant_id=tenant_id, 
                                     agent=agent_name,
                                     session_id=session_id)
            agentController.general_agent_conv(tenant_id, user_id, socketio, client_id, requestBody, session_id)
            stop_timer(agent_timer)
            
        except Exception as e:
            appLogger.error({"event": "general_agent", "error": e, "traceback": traceback.format_exc()})
            socketio.emit("general_agent", 'failed', room=client_id)
        finally:
            stop_timer(timer_id)

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
            program_state = ProgramState.get_instance(user_id)
            
            agent_name = requestBody.get("mode") or None
            session_id = requestBody.get('session_id') or ''
            message = requestBody.get("message") or None
            
            # Set program state variables
            if message: 
                program_state.set("current_prompt", message)
                
            program_state.set("current_agent", agent_name)
            program_state.set("session_id", session_id)
            
            log_event_start("general_agent_v2", client_id=request.sid, agent=agent_name, session_id=session_id)
            timer_id = start_timer("general_agent_v2_event_processing", client_id=request.sid)

            client_id = active_connections[user_identifier]['client_id']
            tenant_id = active_connections[user_identifier]['tenant_id']
            
            agent_timer = start_timer(
                "general_agent_v2_controller", 
                user_id=user_id,
                tenant_id=tenant_id,
                agent=agent_name, 
                session_id=session_id
            )
            
            superAgentController.handle_super_agent(
                tenant_id=tenant_id,
                user_id=user_id,
                socketio=socketio,
                client_id=client_id,
                requestBody=requestBody,
                session_id=session_id,
            )
            stop_timer(agent_timer)
            
        except Exception as e:
            appLogger.error({"event": "general_agent_v2", "error": e, "traceback": traceback.format_exc()})
            socketio.emit("general_agent_v2", 'failed', room=client_id)
        finally:
            stop_timer(timer_id)


    @socketio.on("tango_chat_onboarding")
    def handle_tango_chat_onboarding(requestBody):
        print("handle_tango_chat_onboarding came", requestBody)
        
        user_identifier = request.sid
        print("Received tango_chat_user event:", requestBody)

        session_id = requestBody.get("session_id")
        message = requestBody.get("message")
        metadata = requestBody.get("metaData")
        print("--debug handle_tango_chat_onboarding---", metadata)
        # Get user_id from active_connections
        user_id = active_connections[user_identifier]['user_id']
        
        # Create/get program state for this user
        program_state = ProgramState.get_instance(user_id)
        program_state.set("current_agent", "onboarding_agent")
        program_state.set("session_id", session_id)
        program_state.set("current_prompt", message)
        
        print("active_connections[user_identifier]", active_connections[user_identifier])
        tenant_id = active_connections[user_identifier]['tenant_id']
        client_id = active_connections[user_identifier]['client_id']


        agentController.onboarding_agents_chat_socket(socketio=socketio, client_id=client_id, 
                                                    session_id=session_id, tenant_id=tenant_id, 
                                                    user_id=user_id, message=message, metadata=metadata)
    
    @socketio.on("tango_onboarding_view")
    def handle_tango_onboarding_view(requestBody):
        # print("handle_tango_onboarding_view came", requestBody)
        
        user_identifier = request.sid
        print("Received tango_onboarding_view event:", requestBody)
        session_id = requestBody.get("session_id")
        message = requestBody.get("message")        
        metadata = requestBody.get("metaData")
        print("--debug tango_onboarding_view---------------", metadata)
        # Get user_id from active_connections
        user_id = active_connections[user_identifier]['user_id']
        
        # Create/get program state for this user
        program_state = ProgramState.get_instance(user_id)
        program_state.set("current_agent", "onboarding_agent")
        program_state.set("session_id", session_id)
        program_state.set("current_prompt", message)
        # print("active_connections[user_identifier]", active_connections[user_identifier])
        tenant_id = active_connections[user_identifier]['tenant_id']
        client_id = active_connections[user_identifier]['client_id']
        agentController.general_agent_conv(tenant_id, user_id, socketio, client_id, requestBody, session_id)
            
    @socketio.on("tango_chat_user")
    def handle_tango_chat_user(requestBody):
        print("handle_tango_chat_user came", requestBody)
        session_id = requestBody.get("session_id")
        message = requestBody.get("message")
        
        user_identifier = request.sid
        
        print("active_connections[user_identifier]", active_connections[user_identifier])
        tenant_id = active_connections[user_identifier]['tenant_id']
        user_id = active_connections[user_identifier]['user_id']
        client_id = active_connections[user_identifier]['client_id']
        
        program_state = ProgramState.get_instance(user_id)
        program_state.set("current_agent", "tango_chat_user")
        program_state.set("session_id", session_id)
        program_state.set("current_prompt", message)
        
        controller.tangoChatIO(socketio, client_id, sessionId=session_id, tenantId=tenant_id, userId=user_id, message=message)
        

    @socketio.on("stop_generation")
    def handle_stop_generation(data):
        # Get user from current connection
        user_identifier = request.sid
        user_id = active_connections.get(user_identifier, {}).get('user_id')
        
        if not user_id:
            return
        
        RedClient.setter(key_set=f"interrupt_requested::userID::{user_id}",value=True,expire=5)
        RedClient.publish(f"interrupt::{user_id}", True) #instant interrupt
        # program_state = ProgramState.get_instance(user_id)
        # program_state.set("interrupt_requested", True)
        
        # Optional: give immediate feedback (looks nicer)
        socketio.emit("tango_chat_assistant", "\n\n[Stopping...]", room=request.sid)
        # In the stop handler (add this line)
        socketio.emit("tango_chat_assistant", "<end>", room=request.sid)
        socketio.emit("tango_chat_assistant", "<<end>>", room=request.sid)