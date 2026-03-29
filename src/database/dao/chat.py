from peewee import (
    CharField,
    TextField,
    IntegerField,
    DateTimeField,
    SmallIntegerField,
)
from src.trmeric_database.models.chat import ChatModel


class ChatDao:

    @staticmethod
    def fetchChatByProjectId(projectId):
        query = ChatModel.select().where(
            ChatModel.project_id == projectId
        )
        return list(query.dicts())

    @staticmethod
    def fetchChatBySessionId(sessionId):
        """
        Returns the entry of the questionarrer for a given session id.

        Returns:
            List[Dict]: List of all the entries of the questioniarre for a given session id
            in the format
        """
        query = ChatModel.select().where(
            ChatModel.session_id == sessionId
        )
        return list(query.dicts())

    @staticmethod
    def fetchChatBySessionIdAndType(project_id, chat_type):
        query = ChatModel.select().where(
            (ChatModel.session_id == project_id)
            & (ChatModel.type == chat_type)
        )
        return list(query.dicts())

    @staticmethod
    def insertChat(chatData):
        newChat = ChatModel.create(**chatData)
        return newChat.id

    @staticmethod
    def updateChat(chatId, updatedFields):
        query = ChatModel.update(**updatedFields).where(
            ChatModel.id == chatId
        )
        query.execute()
