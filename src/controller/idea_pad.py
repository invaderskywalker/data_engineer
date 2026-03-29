import traceback
from flask import jsonify, request  # type: ignore
from src.trmeric_database.dao import IdeaDao
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.journal.Activity import detailed_activity
from src.trmeric_services.idea_pad.IdeaPadService import IdeaPadService


class IdeaPadController:
    def __init__(self):
        self.ideaPadService = IdeaPadService()

    def generateIdeas(self):
        try:
            user_id = request.decoded.get("user_id")
            tenant_id = request.decoded.get("tenant_id")
            idea_theme = request.json.get("idea_theme")
            
            # Log user initiation of idea generation process
            detailed_activity(
                activity_name="user_initiated_idea_generation",
                activity_description="User started the idea generation process",
                user_id=user_id
            )
            
            response = self.ideaPadService.generateIdeas(tenant_id, idea_theme, user_id=user_id)
            return jsonify({"status": "success", "data": response}), 200
        except Exception as e:
            appLogger.error({"event": "generateIdeas", "error": e})
            return jsonify({"error": "Internal Server Error"}), 500

    def enhanceIdea(self):
        try:
            user_id = request.decoded.get("user_id")
            tenant_id = request.decoded.get("tenant_id")
            idea = request.json.get("idea")
            
            # Log user initiation of idea enhancement process
            detailed_activity(
                activity_name="user_initiated_idea_enhancement",
                activity_description="User started the idea enhancement process",
                user_id=user_id
            )
            
            response = self.ideaPadService.enhanceIdea(
                tenant_id, 
                idea, 
                user_id=user_id,
                log_input=request.decoded
            )
            return jsonify({"status": "success", "data": response}), 200
        except Exception as e:
            appLogger.error({"event": "enhanceIdea", "error": str(
                e), "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error"}), 500

    def createRoadmapFromIdea(self):
        try:
            user_id = request.decoded.get("user_id")
            tenant_id = request.decoded.get("tenant_id")
            idea_id = request.json.get("idea_id")
            
            # Log user initiation of roadmap creation process
            detailed_activity(
                activity_name="user_initiated_roadmap_creation",
                activity_description="User started the roadmap creation from idea process",
                user_id=user_id
            )
            
            response = self.ideaPadService.createRoadmapFromIdea(
                tenant_id, 
                idea_id, 
                user_id=user_id,
                log_input=request.decoded
            )
            return jsonify({"status": "success", "data": response}), 200
        except Exception as e:
            appLogger.error({
                "event": "createRoadmapFromIdea",
                "error": str(e), 
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500


    def fetchUserIdeaChats(self):
        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")
            # print("--debug fetchUserIdeaChats--------",tenant_id, user_id)

            response = []
            # user_ideas = IdeaDao.fetchUserIdeaChats(tenant_id=tenant_id,user_id=user_id)
            user_ideas = IdeaDao.fetchIdeasDataWithProjectionAttrs(
                projection_attrs=['id','title','created_on','tango_analysis'],
                tenant_id= tenant_id,
                order_clause= "ORDER by id DESC",
                user_id= user_id,
            )

            for idea in user_ideas:
                response.append({
                    'id': idea.get('idea_id'),
                    'title': idea.get('idea_title'),
                    'created_on': idea.get('idea_created_on'),
                    'session_id': idea.get('idea_tango_analysis',{}).get('session_id') or None
                })
            # print("--debug fetchUserIdeaChatsresponse--------", response[:2], "\n\ntotal ideas: ", len(response))
            return jsonify({"status": "success", "data": response}), 200
        
        except Exception as e:
            appLogger.error({"event": "fetchUserIdeaChats","error": e,"traceback": traceback.format_exc()})
            return jsonify({"error": "Couldn't fetch idea chats, Internal server error!"}), 500
