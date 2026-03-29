from flask import request, jsonify
import time
from src.trmeric_services.chat_service.QnaChatService import QnaChatService
import traceback
from src.trmeric_api.logging.AppLogger import appLogger


class QnaController:
    def __init__(self):
        self.qnaService = QnaChatService()

    def getChatType(self, _type):
        # return 2 if _type == "project" else 3 if _type == "roadmap" else 4 if _type == "onboard" else 5 if _type == "portfolio" else 0
        result = {
            "project": 2,
            "roadmap": 3,
            # "onboard": 4,
            "mission": 4,
            "portfolio": 5,
            "idea": 6
        }.get(_type, 0)
        return result

    def postQnaChat(self):
        try:
            session_id = request.json.get("session_id")
            _type = request.json.get("type")
            userAnswer = request.json.get("message")
            files = request.json.get("files",{}) or {}

            appLogger.info({"event": "postQnaChat","session_id": session_id,"type": _type})
            start_time = time.time()
            chat_type = self.getChatType(_type)
            result = self.qnaService.postAnswer(
                session_id,
                request.decoded,
                chat_type,
                userAnswer,
                key= files
            )
            appLogger.info({
                "event": "postQnaChat",
                "chat_type": chat_type,
                "session_id": session_id,
                "response": result,
                "duration": time.time() - start_time,
            })
            return jsonify(result), 200
        except Exception as e:
            appLogger.error({
                "event": "postQnaChat",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"status": "error", "statusCode": 500, "message": f"{str(e)}"}), 500

    def fetchQnaChat(self, session_id, _type, **kwargs:dict):
        try:
            appLogger.info({
                "event": "fetchQnaChat",
                "session_id": session_id,
                "type": _type
            })
            chat_type = self.getChatType(_type)
            result = self.qnaService.fetchQnaChat(
                session_id,
                request.decoded,
                chat_type,
                **kwargs
            )
            return jsonify(result), 200
        except Exception as e:
            appLogger.error({
                "event": "fetchQnaChat",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"status": "error", "statusCode": 500, "message": f"{str(e)}"}), 500

    def fetchQnaChatPrefill(self, session_id, _type):
        try:
            appLogger.info({"event": "qna_fetch","session_id": session_id,"type": _type})
            chat_type = self.getChatType(_type)
            result = self.qnaService.fetchQnaChatPrefill(session_id, request.decoded, chat_type)

            return jsonify(result), 200
        
        except Exception as e:
            appLogger.error({"event": "qna_fetch","error": str(e),"traceback": traceback.format_exc()})
            return jsonify({"status": "error", "statusCode": 500, "message": f"{str(e)}"}), 500
        
        
    def fetchQnaChatPrefillSocketIO(self, socketio,client_id,metadata, _type):
        try:
            print("--debug in fetchQnaChatPrefillSocketIO--",metadata, _type)
            session_id = metadata.get("session_id","")
            tenant_id = metadata.get("tenant_id","")
            user_id = metadata.get("user_id","")
            entity = metadata.get("request_body",{}).get('entity','') or None #for missions
            print("--debug in fetchQnaChatPrefillSocketIO-----", entity)
            
            appLogger.info({"event": f"{_type}:prefill:start","session_id": session_id,"type": _type,"client_id":client_id})
            
            chat_type = self.getChatType(_type)
            result = self.qnaService.fetchQnaChatPrefillSocketIO(
                session_id = session_id,
                decoded = {"username": "","user_id": user_id,"tenant_id": tenant_id},
                chat_type=chat_type,
                socketio=socketio,
                client_id = client_id,
                entity = entity
            )
            
            print("--debug fetchQnaChatPrefillSocketIO result--",len(result) if result else "No result")  
            socketio.emit(f"{_type}_creation_agent",{"event":f"{_type}_creation","data":result,"session_id":session_id},room=client_id)
            # print("--debug event gone---------------")
            appLogger.info({"event": f"{_type}:prefill:done","session_id": session_id,"type": _type,"client_id":client_id})
        except Exception as e:
            appLogger.error({
                "event": "qna_fetch",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"status": "error", "statusCode": 500, "message": f"{str(e)}"}), 500    
    
