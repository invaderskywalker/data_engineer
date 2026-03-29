from flask import request, jsonify
import time
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.chat_service.DiscoveryChatService import DiscoveryChatService
from src.trmeric_services.journal.Activity import detailed_activity
import traceback


class DiscoveryQnAController:
    def __init__(self):
        self.discoveryQnaService = DiscoveryChatService()

    def postDiscoveryAnswer(self):
        """
        This is a post request, where the user is writing an answer to one of the questions in the project chat.

        Returns:
            the latest question entry in which the answer has not been provided.
        """
        try:
            session_id = request.json.get("session_id")
            user_message = request.json.get("message")
            start_time = time.time()
            appLogger.info({"event": "postDiscoveryAnswer",
                            "session_id": session_id})
            result = self.discoveryQnaService.postDiscoveryAnswer(
                session_id,
                request.decoded,
                user_message
            )
            appLogger.info({
                "event": "postDiscoveryAnswer",
                "session_id": session_id,
                "response": result,
                "duration": time.time() - start_time,
            })
            return jsonify(result), 200
        except Exception as e:
            appLogger.error({
                "event": "postDiscoveryAnswer",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"status": "error", "statusCode": 500, "message": "Something went wrong"}), 500

    def fetchDiscoveryChat(self, session_id):
        """
        This fetches all of the question answers for a specific project / session.

        Args:
            sessionId (int): The session id of the project.

        Returns:
            list: an array of objects, with each object having a question and answer.
        """
        try:
            appLogger.info(
                {
                    "function": "fetchDiscoveryChat",
                    "marker": "controller",
                    "session_id": session_id
                }
            )
            result = self.discoveryQnaService.fetchDiscoveryChat(
                int(session_id),
                request.decoded
            )
            return jsonify(result), 200
        except Exception as e:
            appLogger.error({
                "event": "fetchDiscoveryChat",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"status": "error", "statusCode": 500, "message": "Something went wrong"}), 500

    def createProjectBrief(self):
        """
        Based on a given project ID and it's corresponding conversation, this function
        creates a project brief for the user.

        Returns:
            dict: a dictionary with the following keys: title, value.

            the keys are the following: Project Title, Project Overview, Definition of Success, Technical Requirements, Domain Expertise Required, Geographic Consideration, Timeline & Budget, Key Criterias.
            { "Project Title": <>, ... }
        """
        try:
            detailed_activity(
                user_id=request.decoded.get("user_id"),
                activity_name="discovery_session_chat_complete",
                activity_description="The user has answered all topics in the discovery chat.",
            )
            appLogger.info(
                {"event": "create_project_brief_endpoint", "data": request.json}
            )
            project_data = {
                "project_id": request.json.get("project_id"),
                "project_title": request.json.get("project_title") or "",
                "customer_name": request.json.get("customer_name") or "",
            }
            session_id = request.json.get("project_id")
            appLogger.info(
                {"event": "create_project_brief_endpoint",
                    "project_data": project_data}
            )
            result = self.discoveryQnaService.createProjectBrief(
                session_id, request.json, project_data
            )
            return jsonify(result), 200
        except Exception as e:
            appLogger.error({
                "event": "create_project_brief_endpoint",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return (
                jsonify(
                    {
                        "status": "error",
                        "statusCode": 500,
                        "message": "Something went wrong",
                    }
                ),
                500,
            )
