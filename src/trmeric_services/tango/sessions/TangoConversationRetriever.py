from peewee import (
    CharField,
    TextField,
    IntegerField,
    DateTimeField,
    SmallIntegerField,
)
import traceback
from src.trmeric_services.tango.types.TangoConversation import TangoConversation
from src.trmeric_database.BaseModel import BaseModel
class TangoConversationRetriever(BaseModel):
    id = IntegerField(primary_key=True)
    session_id = CharField(max_length=100)
    type = (
        SmallIntegerField()
    )  # 1 for user , 2 for sql created, 3 for assistant message, ##### 4 for classification done
    message = TextField()
    created_date = DateTimeField()
    created_by_id = SmallIntegerField()
    chat_mode = SmallIntegerField()

    class Meta:
        table_name = "tango_tangoconversations"

    @staticmethod
    def fetchChatBySessionAndUserID(sessionID, userID):
        print("fetching chat by session and user id ", sessionID, userID)
        try:
            query = (
                TangoConversationRetriever.select()
                .where(
                    (TangoConversationRetriever.session_id == sessionID)
                    & (TangoConversationRetriever.created_by_id == userID)
                )
                .order_by(TangoConversationRetriever.created_date.asc())
            )
            conversation = TangoConversationRetriever.formatQueryDicts(
                list(query.dicts()), sessionID, userID
            )
            return conversation
        except Exception as e:
            print("error in fetchChatBySessionAndUserID", e, traceback.format_exc())
            conversation = TangoConversation(userID, sessionID, 1)
            return conversation

    @staticmethod
    def insertChat(chatData):
        # db = TrmericDatabase()
        try:
            # db.connect()
            TangoConversationRetriever.create(**chatData)
        except:
            traceback.print_exc()
        # finally:
        #     db.closeDatabase()
        return []

    # Modify the part where the conversation is saved to JSON
    @staticmethod
    def save_conversation_to_json(conversation):
        file_path = "conversation.json"
        # Add the new conversation to the existing data
        existing_data = (conversation.format_conversation())
        # Write the updated data back to the file
        with open(file_path, 'w') as file:
            data = existing_data.split("\n")
            for row in data:
                file.write(row) 
                file.write("\n")

    @staticmethod
    def formatQueryDicts(query, sessionID, userID):
        # 1 is a user # 2 is the code generated and 3 is the tango
        conversation = TangoConversation(userID, sessionID, 1)
        found_summary = False
        summary = ''
        for row in query:
            if row["type"] == 7:
                summary = row["message"]
                found_summary = True
        if found_summary:
            conversation.add_summary(summary) 
            
        for row in query:
            # print("debug row -- ", row)
            if row["type"] == 1:
                conversation.add_user_message(
                    row["message"], row["created_date"])
            elif row["type"] == 5:
                conversation.add_tango_code(row["message"], row["created_date"])
            elif row["type"] == 6:
                conversation.add_tango_data(row["message"])
            elif row["type"] == 3:
                conversation.add_tango_message(row["message"])
        return conversation
    
    @staticmethod
    def formatQueryDictsSimple(query, sessionID, userID):
        # 1 is a user # 2 is the code generated and 3 is the tango
        conversation = TangoConversation(userID, 1, 1)
        for row in query:
            if row["type"] == 1:
                conversation.add_user_message(
                    row["message"], row["created_date"])
            elif row["type"] == 3:
                conversation.add_tango_message(row["message"])
        return conversation

    @staticmethod
    def fetchLastNMessagesByUserID(userID, n):
        print(f"Fetching last {n} messages for user ID {userID} with types 1 and 3")
        try:
            # Query to filter by userID, type (1 or 3), and order by descending creation date
            query = (
                TangoConversationRetriever.select()
                .where(
                    (TangoConversationRetriever.created_by_id == userID)
                    & (TangoConversationRetriever.type.in_([1, 3]))
                )
                .order_by(TangoConversationRetriever.created_date.desc())  # Most recent first
                .limit(n)  # Limit to 'n' messages
            )
            
            # Get the results and sort them chronologically
            results = list(query.dicts())
            print(f"Found {len(results)} messages")
            
            # Reverse the order to ensure chronological order
            results.reverse()
            if len(results)>0 and results[0]["type"] == 3:
                results = results[1:]
            
            # Format query results into a dictionary
            conversation = TangoConversationRetriever.formatQueryDicts(
                results, None, userID
            )
            return conversation
        except Exception as e:
            print("Error in fetchLastNMessagesByUserID", e, traceback.format_exc())
            return None
        
    @staticmethod
    def fetchMessagesByUserIDAndSessionID(userID, sessionID):
        try:
            # Query to filter by userID, type (1 or 3), and order by descending creation date
            sessionID = sessionID + "combined"
            query = (
                TangoConversationRetriever.select()
                .where(
                    (TangoConversationRetriever.created_by_id == userID)
                    & (TangoConversationRetriever.session_id == sessionID)
                    & (TangoConversationRetriever.type.in_([1, 3]))
                )
                .order_by(TangoConversationRetriever.created_date.desc())  # Most recent first
            )
            
            # Get the results and sort them chronologically
            results = list(query.dicts())
            if len(results) == 0:
                print(f"No messages found for user ID {userID} in session {sessionID}")
                return None
            print(f"Found {len(results)} messages")
            
            # Reverse the order to ensure chronological order
            results.reverse()
            if results[0]["type"] == 3:
                results = results[1:]
            
            # Format query results into a dictionary
            conversation = TangoConversationRetriever.formatQueryDicts(
                results, sessionID, userID
            )
            print(conversation)
            return conversation
        except Exception as e:
            print("Error in fetchLastNMessagesByUserID", e, traceback.format_exc())
            return None
        
    @staticmethod
    def fetchLastMessageIDByUserID(userID):
        try:
            # Query to filter by userID, type (1 or 3), and order by descending creation date
            query = (
                TangoConversationRetriever.select()
                .where(
                    (TangoConversationRetriever.created_by_id == userID)
                    & (TangoConversationRetriever.type.in_([1,3]))
                )
                .order_by(TangoConversationRetriever.created_date.desc())  # Most recent first
                .limit(1)  # Limit to 'n' messages
            )
            
            # Get the results and sort them chronologically
            results = list(query.dicts())
            return results[0]["id"]
        except Exception as e:
            print("Error in fetchLastNMessagesByUserID", e, traceback.format_exc())
            return None
        
    @staticmethod
    def CheckLastNmessagesByUserID(userID, N, id):
        try:
            # Query to filter by userID, type (1 or 3), and order by descending creation date
            query = (
                TangoConversationRetriever.select()
                .where(
                    (TangoConversationRetriever.created_by_id == userID)
                    & (TangoConversationRetriever.type.in_([1, 3]))
                )
                .order_by(TangoConversationRetriever.created_date.desc())  # Most recent first
                .limit(N) 
            )
            
            # Get the results and sort them chronologically
            results = list(query.dicts())
            i = 0
            for result in results:
                i = i + 1
                if result["id"] == id:
                    return i
            return -1
        except Exception as e:
            print("Error in fetchLastNMessagesByUserID", e, traceback.format_exc())
            return None

    @staticmethod
    def fetchChatBetweenIndeces(index1: int, index2: int):
        try:
            query = (
                TangoConversationRetriever.select()
                .where(
                    (TangoConversationRetriever.id >= index1)
                    & (TangoConversationRetriever.id < index2)
                )
                .order_by(TangoConversationRetriever.id.asc())
            )
            return list(query.dicts())
        except Exception as e:
            print("Error fetching chats between IDs: ", e)
        return []