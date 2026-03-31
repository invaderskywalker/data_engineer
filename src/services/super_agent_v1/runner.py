
# from .classes import ALL_AGENTS_V2
from src.api.logging.AppLogger import debugLogger
from .config import CONFIG_MAP
from .core import SuperAgent
from src.ml.llm.models.OpenAIClient import ChatGPTClient
from src.services.tango.types.TangoConversation import TangoConversation
from src.database.dao import AgentRunDAO
import uuid





class AgentsRunner():
    def __init__(self, tangoDataInserter, log_info, socketio, client_id):
        self.tangoDataInserter = tangoDataInserter
        self.socketio = socketio
        self.client_id = client_id
        self.log_info = log_info
        self.user_id = self.log_info.get("user_id")
        self.tenant_id = self.log_info.get("tenant_id")
        self.conversation = TangoConversation(
            user_id=self.user_id, 
            tenant_id=self.tenant_id,
            session_id=self.log_info.get("session_id"),
        )
        self.llm = ChatGPTClient(self.user_id, self.tenant_id)
        
    def run(self, agent_name: str, query: str, meta = None):
        from datetime import datetime, timedelta, timezone
        ist_time = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
        print("Incoming runner run (IST):", ist_time.strftime("%Y-%m-%d %H:%M:%S.%f"))
        
        # self.tangoDataInserter.addUserMessage(message=query)
        
        print("run agents runner run ", agent_name, query)
        debugLogger.info(f"started agent runner run fn - wuth agent: {agent_name} and {query}")
        # agent = ALL_AGENTS_V2.get(agent_name) or None
        agent = SuperAgent or None
        config = CONFIG_MAP.get("deep_research") or None
        response = ""
        self.run_id = uuid.uuid4().hex
        if not agent or not config:
            msg = "Triggered wrong agent, CLIENT ERROR super agent"
            response += msg
            # ✅ structured streaming event
            self.socketio.emit(
                "assistant_token",
                {"token": msg},
                room=self.client_id
            )
            
            # self.socketio.emit("super_agent_response", "<end>", room=self.client_id)
            # self.socketio.emit("super_agent_response", "<<end>>", room=self.client_id)
            
            # ✅ structured end event
            self.socketio.emit(
                "assistant_end",
                {"run_id": self.run_id},
                room=self.client_id
            )
            # self.tangoDataInserter.addTangoCode("")
            # self.tangoDataInserter.addTangoData("")
            # self.tangoDataInserter.addTangoResponse(response)
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
            session_id=session_id,
            agent_name=agent_name,
            run_id=self.run_id,
        )
        self.socketio.emit(
            "assistant_process_start",
            {"run_id": self.run_id},
            room=self.client_id
        )
        
        for chunk in agent_class_inst.run(query=query, meta=meta):
            response += chunk
            # self.socketio.emit("super_agent_response", chunk, room=self.client_id)
            # ✅ structured streaming event
            self.socketio.emit(
                "assistant_token",
                {"token": chunk},
                room=self.client_id
            )


            
        # self.socketio.emit("super_agent_response", "<end>", room=self.client_id)
        # self.socketio.emit("super_agent_response", "<<end>>", room=self.client_id)
        
        # ✅ structured end event
        self.socketio.emit(
            "assistant_end",
            {"run_id": self.run_id},
            room=self.client_id
        )
        self.socketio.emit("agentic_timeline", {"event": "stop_show_timeline", "agent": agent_name}, room=self.client_id)
        
        output_payload = {
            "narrative": response
        }
        if agent_class_inst.charts:
            output_payload["charts"] = agent_class_inst.charts
        if agent_class_inst.exports:
            output_payload["exports"] = agent_class_inst.exports
        
        AgentRunDAO.create_run_step(
            session_id=session_id,
            tenant_id=str(self.tenant_id),
            user_id=str(self.user_id),
            agent_name=agent_name,
            run_id=self.run_id,
            step_type=AgentRunDAO.FINAL_RESPONSE,
            step_index=agent_class_inst.step_index,
            step_payload=output_payload,
            status=AgentRunDAO.COMPLETED
        )
        # self.tangoDataInserter.addTangoCode(agent_class_inst.plans)
        # execution_trace = agent_class_inst.get_execution_trace()
        # self.tangoDataInserter.addTangoCode(
        #     MyJSON.dumps(execution_trace)
        # )
        # self.tangoDataInserter.addTangoData("")
        # self.tangoDataInserter.addTangoResponse(response)
        # title_thread = threading.Thread(target=self.generate_chat_title, args=(self.log_info.get("session_id"), self.log_info, agent_name))
        # title_thread.start()
        return
