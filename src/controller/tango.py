from src.services.tango.sessions.InsertTangoData import TangoDataInserter
from src.services.tango.sessions.SessionManager import TangoSessionManager
from src.services.tango.sessions.TangoConversationRetriever import TangoConversationRetriever
from src.services.summarizer.SummarizerService import SummarizerService

from src.api.logging.AppLogger import appLogger
from src.api.logging.CreateLogResponse import createLogResponseBody
from flask import Response, jsonify, request
from src.api.logging.LogResponseInfo import logResponseInfo
import time
import threading
import traceback
from src.ml.llm.models.OpenAIClient import ChatGPTClient
from src.ml.llm.models.OpenAIClient import ModelOptions
from src.utils.json_parser import extract_json_after_llm
from src.services.tango.prompts.CompanyDetails import getCompanyDetailsPrompt
from src.database.dao import TangoDao
from src.services.agents.functions.onbaording_v2 import fetch_uploaded_file
from src.services.journal.ActivityEndpoints import summarize_user_activity

from src.services.reinforcement.core import ReinforcementLearning
from src.services.agents.functions.businesscase_agent.controller import BusinessTemplateAgent
from src.services.agents.functions.solution_agent.controller import SolutionAgent
from threading import Lock


class TangoController:
    def __init__(self):
        self.tangoSessionManager = TangoSessionManager()
        self.llm = ChatGPTClient()
        self.rl = ReinforcementLearning()
        self.modelOptions = ModelOptions(
            model="gpt-4o",
            max_tokens=4096,
            temperature=0.4
        )

    def fetchCollaborationChats(self, session_id):
        try:
            tenant_id = request.decoded.get("tenant_id")
            response = TangoDao.fetchCollaborativeChatsForClient(
                session_id, tenant_id=tenant_id)
            return jsonify({"status": "success", "data": response}), 200
        except Exception as e:
            appLogger.error({
                "event": "fetchCollaborationChats",
                "error": e,
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500

    def fetchTangoOnboardingKnowledge(self):
        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")
            response = fetch_uploaded_file(
                user_id=user_id, tenant_id=tenant_id)
            return jsonify({"status": "success", "data": response}), 200
        except Exception as e:
            appLogger.error({
                "event": "fetchTangoOnboardingKnowledge",
                "error": e,
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500

    def fetchCollaborationChats(self, session_id):
        try:
            tenant_id = request.decoded.get("tenant_id")
            response = TangoDao.fetchCollaborativeChatsForClient(
                session_id, tenant_id=tenant_id)
            return jsonify({"status": "success", "data": response}), 200
        except Exception as e:
            appLogger.error({
                "event": "fetchCollaborationChats",
                "error": e,
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500

    def fetchTangoOnboardingKnowledge(self):
        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")
            response = fetch_uploaded_file(
                user_id=user_id, tenant_id=tenant_id)
            ## fetch template now
            
            busienss_agent = BusinessTemplateAgent(tenant_id, user_id, 0)
            business_data = busienss_agent.fetch_business_case_template_files()
            response.update(business_data)
            
            
            sol_agent = SolutionAgent(tenant_id, user_id, 0)
            sol_data = sol_agent.fetch_solution_tempaltes()
            response.update(sol_data)
            
            
            return jsonify({"status": "success", "data": response}), 200
        except Exception as e:
            appLogger.error({
                "event": "fetchTangoOnboardingKnowledge",
                "error": e,
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500

    def fetchChatTitlesForUser(self):
        try:
            user_id = request.decoded.get("user_id")
            response = TangoDao.fetchChatTitlesForUser(user_id)
            return jsonify({"status": "success", "data": response}), 200
        except Exception as e:
            appLogger.error({
                "event": "fetchChatTitlesForUser",
                "error": e,
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500
        
        
    @staticmethod
    def deleteChatTitle(chat_id):
        try:
            user_id = request.decoded.get("user_id")
            TangoDao.deleteChatTitle(user_id, chat_id)
            return jsonify({"status": "success", "message": f"Chat title with ID {chat_id} deleted successfully"}), 200
        except Exception as e:
            appLogger.error({
                "event": "deleteChatTitle",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": str(e)}), 500
        

    def some_other_function(self, userId, sessionId):
        print("start  some_other_function")
        # Simulate a delay by sleeping for 5 seconds
        time.sleep(5)
        print("end  some_other_function")
        # Add whatever logic you want to run after the delay here
        print(f"Function completed for user {userId} and session {sessionId}.")

    def tangoChat(self):
        try:
            sessionId = request.json.get("session_id")
            tenantId = request.decoded.get("tenant_id")
            userId = request.decoded.get("user_id")
            message = request.json.get("message")

            tangoConversation = self.tangoSessionManager.getInstance(
                sessionId, tenantId, userId, {}
            )
            startTime = time.time()
            responseInfo = createLogResponseBody()

            def generate_and_log(userMessage):
                stringData = ""
                for chunk in tangoConversation.chat(userMessage, sessionId):
                    stringData += chunk
                    yield chunk
                dataInsertionInstance = TangoDataInserter(userId, sessionId)
                dataInsertionInstance.addTangoResponse(stringData)

                threading.Thread(target=self.summarizeChats, args=(
                    sessionId, userId, tenantId)).start()

                responseInfo["duration"] = time.time() - startTime
                threading.Thread(target=logResponseInfo,
                                 args=(responseInfo,)).start()
                threading.Thread(target=self.some_other_function,
                                 args=(userId, sessionId)).start()

            return Response(
                generate_and_log(message),
                content_type="text/plain; charset=utf-8",
                status=200,
                headers={"Transfer-Encoding": "chunked"},
            )
        except Exception as e:
            appLogger.error({"event": "trmeric_ai_v2_chat",
                            "error": e, "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error"}), 500

    def summarizeChats(self, sessionID, userID, tenantID, summarizer_rate=2):
        try:
            query = (
                TangoConversationRetriever.select()
                .where(
                    (TangoConversationRetriever.session_id == sessionID+"combined")
                    & (TangoConversationRetriever.created_by_id == userID)
                )
                .order_by(TangoConversationRetriever.created_date.desc())
            )
            query = list(query.dicts())
        except Exception as e:
            query = []

        user_messages_count = 0
        query_filtered = []
        for row in query:
            if row["type"] == 1:
                user_messages_count += 1
            if user_messages_count <= (summarizer_rate+1):
                if row["type"] == 1:
                    query_filtered.append(row["message"])
                if row["type"] == 3:
                    query_filtered.append(row["message"])
                if row["type"] == 5:
                    query_filtered.append(row["message"])

        summary = None
        found_summary = False
        for row in query:
            if row["type"] == 7:
                summary = row["message"]
                found_summary = True
            if found_summary:
                break

        print("--number of user messages", user_messages_count)
        if user_messages_count % summarizer_rate == 0 and user_messages_count > 0:
            print(b"---summarizing---")
            print(f'tenant_id: {tenantID}, user_id: {userID}')
            # create large data using all of the last 5 user message, tango message, tango code and tango data
            try:
                large_data = "\n".join([str(x) for x in query_filtered[::-1]])

                if not summary:
                    new_summary = SummarizerService(logInfo={"tenant_id": tenantID, "user_id": userID}).summarizer(
                        large_data=large_data,
                        message='''You will be provided a conversation between chatbot and user.
                                It will include user query, chatbot reply, chatbot generated code and chatbot retrieved data.
                                Your job is to summarize this conversation and only keep important points from the chat
                                and it will be used for the chatbot to make further decisions.
                                ''',
                        identifier='chat'
                    )

                else:
                    new_summary = SummarizerService(logInfo={"tenant_id": tenantID, "user_id": userID}).summarizer(
                        large_data=large_data,
                        message=f'''You will be provided a conversation between chatbot and user.
                                It will include user query, chatbot reply, chatbot generated code and chatbot retrieved data.
                                The previous conversation before the 2 most recent chats that you are being shown had already been summarized here: {summary}. 
                                Your job is to modify the currently existing summary just provided and include the new conversation that you are being shown.
                                Your job is to summarize this conversation and only keep important points from the chat
                                and it will be used for the chatbot to make further decisions.
                                ''',
                        identifier='chat'
                    )
            except Exception as e:
                import traceback
                print(traceback.format_exc())
                new_summary = None

            print("finished summarizing")
            summary = new_summary

            # use insert chat to add summary
            dataInsertionInstance = TangoDataInserter(userID, sessionID)
            dataInsertionInstance.addTangoSummary(summary)

    def tangoPinboard(self):
        try:
            sessionId = request.json.get("session_id")
            tenantId = request.decoded.get("tenant_id")
            userId = request.decoded.get("user_id")
            userMessage = request.json.get("message")
            questionId = request.json.get("question_id")
            answerId = request.json.get("answer_id")

            appLogger.info(
                {
                    "event": "start",
                    "function": "trmeric_ai_pin_chat_start",
                    "session_id": sessionId,
                    "query": request.json.get("message"),
                }
            )

            tangoChatInstance = self.tangoSessionManager.getInstance(
                sessionId, tenantId, userId, {})
            tangoChatInstance = self.tangoSessionManager.getInstanceForPin(
                sessionId)

            startTime = time.time()
            responseInfo = createLogResponseBody()

            def generate_and_log(user_message):
                string_data = ""
                dataInsertionInstance = TangoDataInserter(userId, sessionId)
                # dataInsertionInstance.addUserMessage(user_message)
                for chunk in tangoChatInstance.runPinnedChat(
                    user_message, questionId, answerId, sessionId
                ):
                    string_data += chunk
                    yield chunk

                dataInsertionInstance.addTangoResponse(string_data)

                responseInfo["duration"] = time.time() - startTime
                threading.Thread(target=logResponseInfo,
                                 args=(responseInfo,)).start()

            return Response(
                generate_and_log(userMessage),
                content_type="text/plain; charset=utf-8",
                status=200,
                headers={"Transfer-Encoding": "chunked"},
            )
        except Exception as e:
            appLogger.error({"event": "trmeric_ai_pin_chat_start", "error": e})
            return jsonify({"error": "Internal Server Error"}), 500

    def tangoChatIO(self, socketio, client_id, sessionId, tenantId, userId, message, mode='text'):
        try:
            
            socket_lock = Lock()
            tangoConversation = self.tangoSessionManager.getInstance(
                sessionId, tenantId, userId, {}
            )
            startTime = time.time()
            responseInfo = createLogResponseBody()
            eventToSend = "tango_chat_assistant"
            
            if mode == "audio":
                eventToSend = "tango_chat_assistant_audio"

            def generate_and_log(userMessage):
                stringData = ""
                # Buffer for accumulating chunks
                chunk_buffer = []
                buffer_size = 0
                min_chunk_size = 30  # Minimum characters to emit

                for chunk in tangoConversation.chat(userMessage, sessionId, None, socketio, client_id):
                    stringData += chunk
                    # with socket_lock:
                    chunk_buffer.append(chunk)
                    buffer_size += len(chunk)
                    
                    # Check if buffer has enough characters to emit
                    if buffer_size >= min_chunk_size:
                        buffered_data = ''.join(chunk_buffer)
                        try:
                            # client_id_new = UserSocketMap.get_client_id(user_id=userId)
                            # print(f"Emitting buffered chunk to client_id={client_id_new}, size={buffer_size}")
                            socketio.emit(eventToSend, buffered_data, room=client_id)
                            socketio.sleep(0.01)  # Small delay to prevent overwhelming client
                        except Exception as e:
                            print(f"Error emitting buffered chunk to client_id={client_id_new}: {type(e).__name__}: {e}")
                            return  # Stop if emission fails
                        # Clear buffer
                        chunk_buffer = []
                        buffer_size = 0
                        
                # Emit any remaining buffered data
                if chunk_buffer:
                    buffered_data = ''.join(chunk_buffer)
                    try:
                        # client_id_new = UserSocketMap.get_client_id(user_id=userId)
                        print(f"Emitting final buffered chunk to client_id={client_id}, size={len(buffered_data)}")
                        socketio.emit(eventToSend, buffered_data, room=client_id)
                    except Exception as e:
                        print(f"Error emitting final buffered chunk to client_id={client_id}: {type(e).__name__}: {e}")
                        return
                try:   
                    # client_id_new = UserSocketMap.get_client_id(user_id=userId)
                    print("debug 2-- ", client_id)
                    socketio.emit(eventToSend, "<end>", room=client_id)
                    socketio.emit(eventToSend, "<<end>>", room=client_id)
                except Exception as e:
                    print("error occured", e)
                            
                dataInsertionInstance = TangoDataInserter(userId, sessionId)
                dataInsertionInstance.addTangoResponse(stringData)
                responseInfo["duration"] = time.time() - startTime
                threading.Thread(target=logResponseInfo,
                                 args=(responseInfo,)).start()

            generate_and_log(message)
        except Exception as e:
            appLogger.error({"event": "trmeric_ai_v2_chat",
                            "error": e, "traceback": traceback.format_exc()})
            socketio.emit("tango_chat_assistant_failed", {
                          "error": "Internal Server Error"}, room=client_id)

    def convertAudioToText(self, audio_file_path):
        with open(audio_file_path, "rb") as audio_file:
            transcript = self.llm.openai.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
            return transcript.text

    def tangoCompanyInfo(self):
        """For tenant_customer table to populate org_info and persona json based on company's info"""
        try:
            # sessionId = request.json.get("session_id")
            tenantId = request.json.get("tenant_id")
            userId = request.json.get("user_id")

            company_name = request.json.get("company_name")
            company_website = request.json.get("company_website")

            prompt = getCompanyDetailsPrompt(
                company_name=company_name, company_website=company_website)
            response = self.llm.run(prompt, self.modelOptions, 'fetchCompanyDetails',
                                    logInDb={"tenant_id": tenantId,
                                             "user_id": userId}
                                    )

            result = extract_json_after_llm(response)
            # print("--debug companydetails: ", result)
            return jsonify({"status": "success", "data": result}), 200
        except Exception as e:
            appLogger.log({
                "event": "fetchcompanyDetails",
                "error": e,
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500

    # Reinforcement Learning Layer

    def tangoRLLayer(self):
        
        method = request.method
        print("--debug tangoRLLayer methodType: ", method)

        match method:
            case "GET":
                try:
                    tenantId = request.decoded.get("tenant_id")
                    userId = request.decoded.get("user_id")
                    featureName = request.json.get("feature_name")
                    agentName = request.json.get("agent_name")

                    if not tenantId:
                        return jsonify({"error": "tenant_id is required"}), 400

                    featureName = featureName.strip('"') if featureName else None
                    agentName = agentName.strip('"') if agentName else None

                    appLogger.info({"event": "tangoRLLayer_get", "tenant_id": tenantId,"user_id": userId, "agent_name": agentName, "feature_name": featureName})

                    response = self.rl.get_reinforcement_data(tenantId, agentName, featureName)
                    if "error" in response:
                        return jsonify({"error": response}), 400
                    return jsonify({"status": "success", "data": response}), 200

                except Exception as e:
                    appLogger.error({"event": "tangoRLLayer_get", "error": str(e), "traceback": traceback.format_exc()})
                    return jsonify({"error": "Internal Server Error"}), 500

            case "POST":
                try:
                    tenantId = request.decoded.get("tenant_id")
                    userId = request.decoded.get("user_id")

                    if not (tenantId and userId):
                        return jsonify({"error": "tenant_id and user_id are required"}), 400

                    agentName = request.json.get("agent_name")
                    featureName = request.json.get("feature_name")
                    sentiment = request.json.get("sentiment")
                    comment = request.json.get("comment")
                    feedbackMetadata = request.json.get("feedback_metadata")
                    section = request.json.get("section",None) or None
                    subsection = request.json.get("subsection",None) or None

                    if not all([agentName, featureName, sentiment is not None]):
                        return jsonify({"error": "agent_name, feature_name, and sentiment are required"}), 400
                    if not isinstance(sentiment, int) or sentiment not in [-1, 0, 1]:
                        return jsonify({"error": "Sentiment must be an integer (-1, 0, or 1)"}), 400

                    appLogger.info({"event": "tangoRLLayer_post", "tenant_id": tenantId,
                        "user_id": userId, "agent_name": agentName, "feature_name": featureName,
                        "section": section, "subsection": subsection
                    })
                    response = self.rl.post_reinforcement_data(
                        data={
                            "agent_name": agentName,
                            "feature_name": featureName,
                            "sentiment": sentiment,
                            "comment": comment,
                            "feedback_metadata": feedbackMetadata,
                            "tenant_id": tenantId,
                            "user_id": userId,
                            "section": section,
                            "subsection": subsection
                        }
                    )
                    if "error" in response:
                        return jsonify({"error": response}), 400
                    return jsonify({"status": "success", "data": response}), 200

                except Exception as e:
                    appLogger.error({"event": "tangoRLLayer_post", "error": str(e), "traceback": traceback.format_exc()})
                    return jsonify({"error": "Internal Server Error"}), 500

    def tangoRecentActivity(self):
        try:
            tenantId = request.decoded.get("tenant_id")
            userId = request.decoded.get("user_id")
            limit = request.args.get("limit", default=5, type=int)

            if not tenantId or not userId:
                return jsonify({"error": "tenant_id and user_id are required"}), 400

            appLogger.info({"event": "tangoRecentActivity", "tenant_id": tenantId,
                           "user_id": userId, "limit": limit})

            response = summarize_user_activity(
                userId, limit)

            return jsonify({"status": "success", "data": response}), 200

        except Exception as e:
            appLogger.error({"event": "tangoRecentActivity", "error": str(
                e), "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error"}), 500