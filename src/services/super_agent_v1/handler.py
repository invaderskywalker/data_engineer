from src.services.agents.core import AgentRegistry
from src.services.tango.sessions.InsertTangoData import TangoDataInserter
from .runner import AgentsRunner


class AgentsHandler:
    def __init__(self, session_id, tenant_id, user_id, metadata, socketio=None, client_id=None, **kwargs):
        self.agent_registry = AgentRegistry()
        self.metadata = metadata
        self.log_info = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "session_id": session_id,
            "metadata": metadata
        }
        self.tangoDataInserter = TangoDataInserter(user_id, session_id)
        self.socketio = socketio
        self.client_id = client_id
        self.sender = kwargs.get("socketSender") or None
        self.runner = AgentsRunner(
            self.tangoDataInserter, 
            self.log_info, 
            socketio=socketio, 
            client_id=client_id
        )
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.session_id = session_id


    def set_conversation(self, conversation):
        pass
        # self.runner.conversation = conversation


       
       