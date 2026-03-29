from src.trmeric_services.agents.core import  BaseAgent
from .nodes import ToolNode, OutputNode
from src.trmeric_api.logging.AppLogger import appLogger
import traceback
from .utils import PhoenixUtils
import threading
from .prompts import ChatTitlePrompt
from src.trmeric_database.dao import TangoDao
from src.trmeric_utils.json_parser import extract_json_after_llm


class AgentV1Handler:
    def __init__(self, base_agent: BaseAgent, tangoDataInserter, log_info, socketio, client_id):
        self.base_agent = base_agent
        self.tangoDataInserter = tangoDataInserter
        self.socketio = socketio
        self.client_id = client_id
        self.log_info = log_info
        
        
    def generate_chat_title(self, session_id, meta):
        """Run title generation in a separate thread and emit result."""
        try:

            print("generate_chat_title 0 --- ", session_id , meta)
            session_id = session_id + "combined"
            current_title = TangoDao.fetchChatTitleForSession(session_id=session_id)
            print("generate_chat_title 1", current_title)
            if current_title:
                return
            
            conv = TangoDao.fetchChatsForSessionAndTypes(session_id=session_id, types=[1,3])
            print("generate_chat_title 2", len(conv))
            tenant_id = meta.get("tenant_id")
            user_id = meta.get("user_id")
            if (len(conv) < 2 and len(conv) > 10):
                TangoDao.insert_chat_title(
                    session_id=session_id, 
                    title="New Chat", 
                    tenant_id=tenant_id,
                    user_id=user_id
                )
                return 
            title_prompt = ChatTitlePrompt.generate_title(conv)
            title_response = self.base_agent.llm.run(
                title_prompt, 
                self.base_agent.modelOptions,
                "title::create", 
                logInDb= meta
            )
            chat_title = extract_json_after_llm(title_response)
            chat_title_string = chat_title.get("chat_title") or None
            if (chat_title_string):
                
                TangoDao.insert_chat_title(
                    session_id=session_id, 
                    title=chat_title_string, 
                    tenant_id=tenant_id,
                    user_id=user_id
                )
        except Exception as e:
            appLogger.error({
                "error": "ChatTitleGeneration",
                "exception": str(e),
                "traceback": traceback.format_exc()
            })
        
        
    def execute(self, agent_name, message='', sendMini=False):
        try:
            title_thread = threading.Thread(
                target=self.generate_chat_title,
                args=(self.log_info.get("session_id"), self.log_info)
            )
            title_thread.start()
            self.socketio.emit("custom_agent_v1_ui", {"event": "refresh_titles"}, room=self.client_id)
            
            
            # self.base_agent.refresh_conversation()
            current_agent = PhoenixUtils.checkCurrentAgent(session_id=self.log_info.get("session_id"), user_id=self.log_info.get("user_id"))
            PhoenixUtils.sendCurrentAgentInfoToUser(socketio=self.socketio, client_id=self.client_id, current_agent=current_agent)
            conv = self.base_agent.conversation.format_conversation()
            last_tango_message = self.base_agent.conversation.last_tango_message()
            last_user_message = self.base_agent.conversation.last_user_message()
            
            network_data = {
                "socketio": self.socketio,
                "client_id": self.client_id,
                "log_info": self.log_info,
                "conv": conv,
                "last_user_message": last_user_message,
                "tenant_id": self.log_info.get("tenant_id"),
                "user_id": self.log_info.get("user_id"),
                "session_id": self.log_info.get("session_id"),
            }
            self.socketio.emit("custom_agent_v1_ui", 
                {
                    "event": "show_timeline",
                }, 
                room=self.client_id
            )
            tool_node = ToolNode(network_data=network_data, base_agent=self.base_agent, agent_name=agent_name)
            analysis, data = tool_node.run(query=last_user_message)
            
            if PhoenixUtils.checkIfAgentSwitch(session_id=self.log_info.get("session_id"), user_id=self.log_info.get("user_id")):
                PhoenixUtils.deleteAgentSwitch(session_id=self.log_info.get("session_id"), user_id=self.log_info.get("user_id"))
                current_agent = PhoenixUtils.checkCurrentAgent(session_id=self.log_info.get("session_id"), user_id=self.log_info.get("user_id"))
                
                self.socketio.emit("custom_agent_v1_ui", 
                    {
                        "event": "stop_show_timeline",
                    }, 
                    room=self.client_id
                )
                self.base_agent.conversation.add_tango_code(analysis)
                self.execute(current_agent, '', sendMini)
                # self.tangoDataInserter.addTangoCode(analysis)
                # self.tangoDataInserter.addTangoData('')
                # self.tangoDataInserter.addTangoResponse("")
                return
            
            self.socketio.emit("custom_agent_v1_ui", 
                {
                    "event": "stop_show_timeline",
                }, 
                room=self.client_id
            )
                
                
            
            output_node = OutputNode(network_data=network_data, base_agent=self.base_agent, agent_name=agent_name)
            answer = ""
            for chunk in output_node.run(conv=conv, query=last_user_message, analysis=analysis, data=data):
                answer += chunk
                self.socketio.emit("custom_agent_v1", chunk, room=self.client_id)

            self.socketio.emit("custom_agent_v1", "<end>", room=self.client_id)
            self.socketio.emit("custom_agent_v1", "<<end>>", room=self.client_id)
            
            self.tangoDataInserter.addTangoCode(analysis)
            self.tangoDataInserter.addTangoData(data)
            self.tangoDataInserter.addTangoResponse(answer)
            
            # if sendMini:
            #     # if agent_name == "data_analyst":
            #     answer2 = ""
            #     for chunk in output_node.runMini(query=last_user_message, analysis=analysis, response=answer):
            #         answer2 += chunk
            #         self.socketio.emit("custom_agent_mini", chunk, room=self.client_id)

            #     self.socketio.emit("custom_agent_mini", "<end>", room=self.client_id)
            #     self.socketio.emit("custom_agent_mini", "<<end>>", room=self.client_id)
            #     self.tangoDataInserter.addMiniData(answer2)
            
            
            
            
            # Title Generation
            title_thread = threading.Thread(
                target=self.generate_chat_title,
                args=(self.log_info.get("session_id"), self.log_info)
            )
            title_thread.start()
            self.socketio.emit("custom_agent_v1_ui", {"event": "refresh_titles"}, room=self.client_id)
            
        
            
            
            
        except Exception as e:
            print("error -- ", e, traceback.format_exc())
            appLogger.error({
                "error": "AgentV1Handler",
                "error": e,
                "traceback": traceback.format_exc()
            })
            
