# from src.trmeric_services.chat_service import ChatManager
from src.trmeric_database.dao.chat import ChatDao
import time
from src.trmeric_services.chat_service.utils import ey_parseQnA


class QnaChatService:
    def __init__(self):
        from src.trmeric_services.chat_service.ChatManager import ChatManager
        self.manager = ChatManager()
        # self.manager = ChatManager()

    def postAnswer(self, session_id, decoded, chat_type, user_message, key={}):
        chatInstance = self.manager.getInstance(
            session_id,
            decoded,
            chat_type
        )
        chatInstance.addUserMessage(user_message)
        # response = chatInstance.generateNextQuestion()
        # print("---files-----------", chatInstance.getConvUploadedFiles())
        response = chatInstance.generate_next_question(key = key)
        # print("response here 1", response)
        chatInstance.addAssistantMessage(response)
        chats = ChatDao.fetchChatBySessionIdAndType(
            project_id=session_id,
            chat_type=chat_type
        )
        chat = chats[0]
        update_fields = {
            "msg_text": chatInstance.getMessages()
        }
        ChatDao.updateChat(chat["id"], update_fields)
        listOfFormattedQnA = chatInstance.parseMessagesAndReturn()
        
        listOfFormattedQnA = ey_parseQnA(decoded,chat_type,listOfFormattedQnA)
        
        result = listOfFormattedQnA[-1]
        if result["question"]["question_progress"] == "1000%":
            result["no_next_question"] = True
        return result

    def fetchQnaChat(self, session_id, decoded, chat_type, **kwargs:dict):
        # print("debug fetchQnaChat ", session_id, chat_type)
        start_time = time.time()
        chatInstance = self.manager.getInstance(
            session_id,
            decoded,
            chat_type,
            **kwargs
        )
        print("time taken  ----", time.time() - start_time)
        listOfFormattedQnA = chatInstance.parseMessagesAndReturn()
        # print("--debug list qna", listOfFormattedQnA)
        
        listOfFormattedQnA = ey_parseQnA(decoded,chat_type,listOfFormattedQnA)
        return listOfFormattedQnA

    def fetchQnaChatPrefill(self, session_id, decoded, chat_type):
        chatInstance = self.manager.getInstance(
            session_id, decoded, chat_type
        )
        narr = chatInstance.fetchPrefilledRoadmapOrProjectData()
        return narr
    
    def fetchQnaChatPrefillSocketIO(self, session_id, decoded, chat_type,socketio,client_id,**kwargs):
        chatInstance = self.manager.getInstance(
            session_id, decoded, chat_type
        )
        # print("---deubg in fetchQnaChatPrefillSocketIO 22-----", kwargs)
        narr = chatInstance.fetchPrefilledRoadmapOrProjectData(socketio,client_id,**kwargs)
        # print("--debug narr---", len(narr))
        return narr
