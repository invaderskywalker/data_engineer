
# from .classes import ALL_AGENTS_V2
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
from src.trmeric_database.dao import TangoDao
from src.trmeric_services.phoenix.prompts import ChatTitlePrompt
from .config import CONFIG_MAP
from src.trmeric_utils.json_parser import extract_json_after_llm
import threading
import traceback
from .core import BaseAgent


class AgentsRunner():
    def __init__(self, base_agent, tangoDataInserter, log_info, socketio, client_id):
        self.base_agent = base_agent
        self.tangoDataInserter = tangoDataInserter
        self.socketio = socketio
        self.client_id = client_id
        self.log_info = log_info
        
       
    def generate_chat_title(self, session_id, meta):
        """Run title generation in a separate thread and emit result."""
        try:

            print("generate_chat_title 0 --- ", session_id, meta)
            session_id = session_id + "combined"
            current_title = TangoDao.fetchChatTitleForSession(session_id=session_id)
            print("generate_chat_title 1", current_title, current_title == "New Chat" or current_title == None)
            if current_title == "New Chat" or current_title == None:
                pass
            else:
                return

            conv = TangoDao.fetchChatsForSessionAndTypes(session_id=session_id, types=[1, 3])
            print("generate_chat_title 2", len(conv))
            tenant_id = meta.get("tenant_id")
            user_id = meta.get("user_id")
            if len(conv) < 2 and len(conv) > 10:
                TangoDao.insert_chat_title(session_id=session_id, title="New Chat", tenant_id=tenant_id, user_id=user_id)
                return
            title_prompt = ChatTitlePrompt.generate_title(conv)
            title_response = self.base_agent.llm.run(title_prompt, self.base_agent.modelOptions, "title::create", logInDb=meta,socketio=self.socketio, client_id=self.client_id)
            print("title_response ", title_response)
            chat_title = extract_json_after_llm(title_response)
            chat_title_string = chat_title.get("chat_title") or None
            if chat_title_string:
                TangoDao.insert_chat_title(session_id=session_id, title=chat_title_string, tenant_id=tenant_id, user_id=user_id)
        except Exception as e:
            appLogger.error({"error": "ChatTitleGeneration", "exception": str(e), "traceback": traceback.format_exc()})
 
    
    def run(self, agent_name: str, query: str):
        print("run agents runner run ", agent_name)
        debugLogger.info(f"started agent runner run fn - wuth agent: {agent_name} and {query}")
        # agent = ALL_AGENTS_V2.get(agent_name) or None
        agent = BaseAgent or None
        config = CONFIG_MAP.get(agent_name) or None
        response = ""
        if not agent or not config:
            msg = "Triggered wrong agent, CLIENT ERROR"
            response += msg
            self.socketio.emit("tango_chat_assistant", msg, room=self.client_id)
            self.socketio.emit("tango_chat_assistant", "<end>", room=self.client_id)
            self.socketio.emit("tango_chat_assistant", "<<end>>", room=self.client_id)
        
            self.tangoDataInserter.addTangoCode("")
            self.tangoDataInserter.addTangoData("")
            self.tangoDataInserter.addTangoResponse(response)
            return
            
        tenant_id = self.log_info.get("tenant_id")
        user_id = self.log_info.get("user_id")
        session_id = self.log_info.get("session_id")
        agent_class_inst = agent(
            tenant_id = tenant_id,
            user_id = user_id,
            config=config,
            socketio=self.socketio,
            client_id=self.client_id,
            base_agent=self.base_agent,
            session_id=session_id,
            agent_name=agent_name
        )
        
        for chunk in agent_class_inst.process_combined_query(query=query):
            response += chunk
            self.socketio.emit("tango_chat_assistant", chunk, room=self.client_id)
            
            
        self.socketio.emit("tango_chat_assistant", "<end>", room=self.client_id)
        self.socketio.emit("tango_chat_assistant", "<<end>>", room=self.client_id)
        self.socketio.emit("agentic_timeline", {"event": "stop_show_timeline", "agent": agent_name}, room=self.client_id)
        
        self.tangoDataInserter.addTangoCode(agent_class_inst.plans)
        self.tangoDataInserter.addTangoData("")
        self.tangoDataInserter.addTangoResponse(response)
        
        title_thread = threading.Thread(target=self.generate_chat_title, args=(self.log_info.get("session_id"), self.log_info))
        title_thread.start()
            
        return
            
        