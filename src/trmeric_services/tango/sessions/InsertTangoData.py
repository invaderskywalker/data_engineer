from src.trmeric_services.tango.sessions.TangoConversationRetriever import (
    TangoConversationRetriever,
)
import datetime


class TangoDataInserter:

    def __init__(self, user_id, session_id):
        self.user_id = user_id
        self.session_id = session_id

    def addUserMessage(self, message):
        TangoConversationRetriever().insertChat(
            chatData={
                "type": 1,
                "message": message,
                "created_by_id": self.user_id,
                "created_date": datetime.datetime.now(),
                "session_id": self.session_id + "combined",
                "chat_mode": 1,
            }
        )

    def addTangoCode(self, code=None):
        if not code:
            return
        TangoConversationRetriever().insertChat(
            chatData={
                "type": 5,
                "message": code,
                "created_by_id": self.user_id,
                "created_date": datetime.datetime.now(),
                "session_id": self.session_id + "combined",
                "chat_mode": 1,
            }
        )

    def addTangoData(self, data=None):
        if not data:
            return
        TangoConversationRetriever().insertChat(
            chatData={
                "type": 6,
                "message": data,
                "created_by_id": self.user_id,
                "created_date": datetime.datetime.now(),
                "session_id": self.session_id + "combined",
                "chat_mode": 1,
            }
        )
        
    def addMiniData(self, data=None):
        if not data:
            return
        TangoConversationRetriever().insertChat(
            chatData={
                "type": 8,
                "message": data,
                "created_by_id": self.user_id,
                "created_date": datetime.datetime.now(),
                "session_id": self.session_id + "combined",
                "chat_mode": 1,
            }
        )

    def addTangoResponse(self, response):
        if not response:
            return
        TangoConversationRetriever().insertChat(
            chatData={
                "type": 3,
                "message": response,
                "created_by_id": self.user_id,
                "created_date": datetime.datetime.now(),
                "session_id": self.session_id + "combined",
                "chat_mode": 1,
            }
        )
        
    def addTangoSummary(self, summary):
        if not summary:
            return
        TangoConversationRetriever().insertChat(
            chatData={
                "type": 7,
                "message": summary,
                "created_by_id": self.user_id,
                "created_date": datetime.datetime.now(),
                "session_id": self.session_id + "combined",
                "chat_mode": 1,
            }
        )