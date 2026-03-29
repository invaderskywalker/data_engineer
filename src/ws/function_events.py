from flask import request
import json
import traceback
import datetime
from src.api.logging.AppLogger import appLogger
from src.api.logging.TimingLogger import start_timer, stop_timer, log_event_start
from src.services.agents.functions.spend.spend_roadmap import roadmap_spend_controller
from src.services.agents.prompts.response import response_prompt_of_specific_function
from .common import active_connections, agentController

# List of functions that can be called from the frontend
callable_functions = [roadmap_spend_controller]

def register_function_events(socketio):
    @socketio.on("call_function")
    def call_function(requestBody):
        log_event_start("CALL_FUNCTION", client_id=request.sid, function=requestBody.get("function"), session_id=requestBody.get("session_id"))
        timer_id = start_timer("call_function_execution", client_id=request.sid, function_name=requestBody.get("function"))
        print("call_function came", requestBody)
        user_identifier = request.sid

        session_id = requestBody.get("session_id")
        params = requestBody.get("params")
        function = requestBody.get("function")
        
        for func in callable_functions:
            if func.__name__ == function:
                function = func

        tenant_id = active_connections[user_identifier]['tenant_id']
        user_id = active_connections[user_identifier]['user_id']
        client_id = active_connections[user_identifier]['client_id']
        
        try:
            print("--debug requestBody", requestBody)

            agent_name = requestBody.get("agent")
            
            get_instance_timer = start_timer("get_agent_instance_for_function", 
                                            user_id=user_id, 
                                            tenant_id=tenant_id, 
                                            agent=agent_name)
            agent_conversation = agentController.agent_session_manager.get_instance(
                session_id, 
                tenant_id, 
                user_id,
                metadata='',
                agent=agent_name, 
                socketio=socketio, 
                client_id=client_id
            )
            stop_timer(get_instance_timer)

            message = requestBody.get("message")
        
            data = json.dumps(requestBody.get("data"))
        
            lmessage = f"""
                message: {message} 
                Data: {data}
            """

            add_message_timer = start_timer("add_user_message_for_function", user_id=user_id, session_id=session_id)
            agent_conversation.tangoDataInserter.addUserMessage(message=message) 
                
            if data:
                agent_conversation.base_agent.conversation.add_user_message(lmessage, datetime)
            else:
                agent_conversation.base_agent.conversation.add_user_message(message, datetime)  
            stop_timer(add_message_timer)
            
            params.update({
                "tenantID": tenant_id,
                "userID": user_id,
                "sessionID": session_id,
                "socketio": socketio,
            })
            
            function_timer = start_timer("function_call_execution", function=function.__name__, user_id=user_id)
            result = function(**params)
            stop_timer(function_timer)
            
            prompt_timer = start_timer("response_prompt_generation_for_function", user_id=user_id)
            prompt = response_prompt_of_specific_function(conv_history= agent_conversation.base_agent.conversation.format_conversation(), data = result)
            stop_timer(prompt_timer)
            
            string_response = ''
            llm_timer = start_timer("llm_response_streaming_for_function", user_id=user_id)
            for chunk in agent_conversation.base_agent.stream_llm_response(prompt):
                string_response+= chunk
                socketio.emit("agent_chat_user", chunk, room=client_id)
            stop_timer(llm_timer)
            
            insert_timer = start_timer("insert_tango_response_for_function", user_id=user_id)
            agent_conversation.tangoDataInserter.addTangoResponse(string_response)
            stop_timer(insert_timer)
            
            socketio.emit("agent_chat_user", "<end>", room=client_id)
            socketio.emit("agent_chat_user", "<<end>>", room=client_id)
        except Exception as e:
            print("error occured in roadmap call ", e)
            appLogger.error({
                "event": "roadmap_spend",
                "error": e,
                "traceback": traceback.format_exc()
            })
        finally:
            stop_timer(timer_id)
