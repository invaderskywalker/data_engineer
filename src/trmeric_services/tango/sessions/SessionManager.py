# from src.trmeric_services.tango.Types import TangoConversation
import os
from src.trmeric_services.tango.Tango import Tango
from typing import Dict
from src.trmeric_services.tango.sessions.TangoConversationRetriever import (
    TangoConversationRetriever,
)


class TangoSessionManager:

    def __init__(self):
        self.instances: Dict[str, Tango] = {}

    def createInstance(self, sessionID, tenantID, userID, metadata):
        conversation = Tango(userID, tenantID, sessionID)
        self.instances[sessionID] = conversation
        return conversation

    def getInstance(self, sessionID, tenantID, userID, metadata) -> Tango:
        self.deleteInstance(sessionID)
        chatInstance = self.createSessionInstance(
            sessionID, tenantID, userID, metadata)
        print(chatInstance)
        chats = TangoConversationRetriever().fetchChatBySessionAndUserID(
            sessionID + "combined", userID
        )
        chatInstance.setConversation(chats)
        return chatInstance

    def deleteInstance(self, sessionID):
        removedInstance = self.instances.pop(sessionID, None)
        return removedInstance

    def createSessionInstance(self, sessionID, tenantID, userID, metadata) -> Tango:
        chatInstance = Tango(userID, tenantID, sessionID)
        self.instances[sessionID] = chatInstance
        return chatInstance

    def getInstanceForPin(self, sessionId):
        return self.instances.get(sessionId)
