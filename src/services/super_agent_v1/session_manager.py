# pylint: disable=missing-function-docstring
# pylint: disable=missing-module-docstring

from typing import Dict
from src.trmeric_services.tango.sessions.TangoConversationRetriever import (
    TangoConversationRetriever,
)
from src.ws.helper import SocketStepsSender
from .handler import AgentsHandler

class AgentSessionManager:
    def __init__(self):
        self.instances: Dict[str, AgentsHandler] = {}

    def get_instance(self, session_id, tenant_id, user_id, metadata, agent=None, socketio=None, client_id=None) -> AgentsHandler:
        self.delete_instance(session_id)
        self.sender = SocketStepsSender(agent_name=agent, socketio=socketio, client_id=client_id)
        chat_instance = self.create_session_instance(
            session_id, 
            tenant_id, 
            user_id,
            metadata,
            agent,
            socketio=socketio, client_id=client_id,
            socketSender = self.sender
        )
        print('created session instance ', session_id)
        if not session_id:
            session_id = ""
        # chats = TangoConversationRetriever().fetchChatBySessionAndUserID(
        #     session_id+"combined", 
        #     user_id
        # )
        # chat_instance.set_conversation(chats)
        return chat_instance

    def delete_instance(self, session_id):
        self.instances.pop(session_id, None)

    def create_session_instance(self, session_id, tenant_id, user_id, metadata, agent, socketio=None, client_id=None, **kwargs) -> AgentsHandler:
        chat_instance = AgentsHandler(session_id=session_id, tenant_id=tenant_id, user_id=user_id, metadata=metadata, agent_name=agent, socketio=socketio, client_id=client_id, **kwargs)
        self.instances[session_id] = chat_instance
        return chat_instance
