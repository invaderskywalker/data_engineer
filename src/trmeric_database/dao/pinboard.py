from src.trmeric_database.Database import db_instance,TrmericDatabase


class PinBoardDao:
    @staticmethod
    def listPinsHeaders(user_id):
        query = f"""
        select * from tango_tangopinboard where user_id = {user_id}
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def listPinsAnswerIdsForHeaderIds(header_id):
        query = f"""
            select * from tango_tangolikedislike
            where pin_board_id = {header_id}
            and type = 3
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def getTangoChatItem(id):
        query = f"""
            select * from tango_tangoConversations 
            where id = {id}
        """
        data = db_instance.retrieveSQLQueryOld(query)
        if len(data) > 0:
            return data[0]
        return None
    
    
    @staticmethod
    def fetchQuestionJustBeforeThisAnswer(session_id, answer_id):
        query = f"""
            SELECT * FROM tango_tangoconversations
            where session_id = '{session_id}' 
            and id < {answer_id}
            and type = 1
        """
        data = db_instance.retrieveSQLQueryOld(query)
        if len(data) > 0:
            return data[0]
        return None
        
    
    @staticmethod
    def listFullPinsDetails(user_id):
        headers = PinBoardDao.listPinsHeaders(user_id)
        result = []
        for header in headers:
            items = PinBoardDao.listPinsAnswerIdsForHeaderIds(header_id=header.get("id"))
            for item in items:
                _id = item["tangoChat_id"]
                answer_info = PinBoardDao.getTangoChatItem(_id)
                if not answer_info:
                    continue
                session_id = answer_info.get("session_id")
                question_info = PinBoardDao.fetchQuestionJustBeforeThisAnswer(session_id, _id)
                if not question_info:
                    continue
                data = {
                    "id": question_info.get("id"),
                    "question": question_info.get("message"),
                    "answer": answer_info.get("message"),
                    "header": header.get("label"),
                    "pin_text": item.get("pin_board_header"),
                    "category": header.get("label"),
                    "timestamp": question_info.get("created_date"),
                }
                result.append(data)
                
        return headers, result
                
                
                
                    
            
        