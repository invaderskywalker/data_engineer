from src.trmeric_services.chat_service.ChatManager import ChatManager
from src.trmeric_database.dao.chat import ChatDao
from src.trmeric_api.logging.AppLogger import appLogger


class DiscoveryChatService:
    def __init__(self):
        self.manager = ChatManager()

    def postDiscoveryAnswer(self, sessionId, decoded, message):
        try:
            chatInstance = self.manager.getInstance(
                int(sessionId),
                decoded,
                1
            )
            chatInstance.addUserMessage(message)
            response = chatInstance.generate_next_question()
            chatInstance.addAssistantMessage(response)
            chats = ChatDao.fetchChatBySessionId(sessionId)
            chat = chats[0]
            update_fields = {
                "msg_text": chatInstance.getMessages()
            }
            ChatDao.updateChat(chat["id"], update_fields)
            listOfFormattedQnA = chatInstance.parseMessagesAndReturn()
            result = listOfFormattedQnA[-1]
            if result["question"]["question_progress"] == "1000%":
                result["no_next_question"] = True
            return result
        except Exception as e:
            appLogger.error({
                "function": "projectChat",
                "error": str(e)
            })
            raise e

    def fetchDiscoveryChat(self, session_id, decoded):
        chat_instance = self.manager.getInstance(
            int(session_id),
            decoded,
            1
        )
        listOfFormattedQnA = chat_instance.parseMessagesAndReturn()
        return listOfFormattedQnA

    def createProjectBrief(self, session_id, decoded, project_data):
        chat_instance = self.manager.getInstance(
            int(session_id),
            decoded,
            1
        )
        company_name = project_data["customer_name"]
        projectBrief = chat_instance.createProjectBrief(company_name)
        return projectBrief
    
    def fetchFirstQuestionAndAnswer(self, session_id, decoded):
        chat_instance = self.manager.getInstance(
            int(session_id),
            decoded,
            1
        )
        listOfFormattedQnA = chat_instance.parseMessagesAndReturn()
        print("debug --- ", listOfFormattedQnA[0])
        item = listOfFormattedQnA[0]
        result = {
            "question": item.get("question").get("question"),
            "options": item.get("question").get("options", "") or "",
            "hint": item.get("question").get("hint", "") or "",
            "answer": item.get("answer", "") or "",
        }
        # print("debug ---", result)
        return result
        
        # company_name = project_data["customer_name"]
        # projectBrief = chat_instance.createProjectBrief(company_name)
        # return projectBrief
