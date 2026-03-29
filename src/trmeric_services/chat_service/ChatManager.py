import json
import datetime
from typing import Dict
from src.trmeric_database.dao.chat import ChatDao
# from src.trmeric_services.chat_service.Chat import Chat
from src.trmeric_services.chat_service.controller import *
from src.trmeric_services.journal.Activity import detailed_activity


def init_chat_services():
    factory = ChatServiceFactory()
    factory.register_service(1, DiscoveryChat)
    factory.register_service(2, ProjectChat)
    factory.register_service(3, RoadmapChat)
    factory.register_service(5, PortfolioChat)
    factory.register_service(6, IdeationChat)
    factory.register_service(4, MissionChat) #changing Onboard to Mission

    return factory

class ChatManager:
    def __init__(self):
        self.sessions: Dict[int, Chat_V2] = {}
        self.factory = init_chat_services()

    def getInstance(self, sessionId, requestInfo, chatType,**kwargs:dict) -> Chat_V2:
        self.deleteSessionInstance(session_id=sessionId)
        chats = ChatDao.fetchChatBySessionId(sessionId)

        chatInstance = self.createSession(
            requestInfo=requestInfo,
            sessionId=sessionId,
            chatType=chatType
        )
        if len(chats) == 0:
            chatInstance.start_session(**kwargs)
            response = chatInstance.generate_next_question(**kwargs)
            print("----response ", response)
            
            chatInstance.addAssistantMessage(response)
            chatData = {
                "type": chatType,
                "msg_text": json.dumps(chatInstance.dbMessages),
                "updated_on": datetime.datetime.now().isoformat(),
                "session_id": sessionId,
                "project_id": None,
                "tenant_id": requestInfo.get("tenant_id"),
            }
            chats = ChatDao.insertChat(chatData=chatData)
        else:
            chatInstance.setMessagesFromDB(json.loads(chats[0]["msg_text"]))
        return chatInstance

    def createSession(self, sessionId, requestInfo, chatType) -> Chat_V2:
        chats = ChatDao.fetchChatBySessionId(sessionId)
        if len(chats) == 0 and chatType == 1:
            detailed_activity(
                user_id=requestInfo.get("user_id"),
                activity_name="discovery_session_initiation",
                activity_description="User started a new discovery session to find a provider.",
            )
        service = self.factory.get_service(chat_type=chatType, request_info=requestInfo, session_id=sessionId)

        chatInstance = Chat_V2(
            request_info=requestInfo,
            chat_type=chatType,
            session_id=sessionId,
            service=service
        )
        self.sessions[sessionId] = chatInstance
        return chatInstance

    def deleteSessionInstance(self, session_id):
        removedInstance = self.sessions.pop(session_id, None)
        return removedInstance



class ChatServiceFactory:
    def __init__(self):
        self._services = {}

    def register_service(self, chat_type, service_class):
        self._services[chat_type] = service_class

    def get_service(self, chat_type, request_info, session_id):
        service_class = self._services.get(chat_type)
        if not service_class:
            raise ValueError(f"No service registered for chat_type: {chat_type}")
        return service_class(request_info, session_id, chat_type)


