from flask import jsonify, request  # type: ignore
from src.trmeric_api.logging.AppLogger import appLogger
import traceback
from src.trmeric_services.roadmap.RoadmapService import RoadmapService
from src.trmeric_services.agents.precache import RoadmapInsightsCache
from src.trmeric_services.agents.functions.integration_agent.job_roadmap_creator import RoadmapCreator



class RoadmapController:
    def __init__(self):
        self.roadmapService = RoadmapService()

    def businessCaseTemplateCreate(self):
        try:
            roadmap_id = request.json.get("roadmap_id")
            # tenant_id = request.decoded.get("tenant_id")
            response = self.roadmapService.businessCaseTemplateCreate(roadmap_id, request.decoded)
            print("response -- business_case -- ", response)
            return jsonify({"status": "success", "data": response}), 200
        except Exception as e:
            appLogger.error({"event": "businessCaseTemplateCreate", "error": e, "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error"}), 500

    def businessCaseTemplateCreateFinanial(self):
        try:
            business_data = request.json.get("business_data")
            response = self.roadmapService.businessCaseTemplateCreateFinancial(business_data, request.decoded)
            print("response -- businessCaseTemplateCreateFinanial -- ", response)
            return jsonify({"status": "success", "data": response}), 200
        except Exception as e:
            appLogger.error({"event": "businessCaseTemplateCreateFinanial", "error": e, "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error"}), 500

    def roadmapCreationFlowTracker(self, roadmap_id):
        try:
            # roadmap_id = request.get("roadmap_id")
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")

            # print("--debug values : ", tenant_id, user_id, roadmap_id,"--------------")
            appLogger.info({"event": "roadmapCreationFlowTracker", "tenant_id": tenant_id, "user_id": user_id, "roadmap_id": roadmap_id})
            response = self.roadmapService.getRoadmapCreationTrackUtility(tenantID=tenant_id, userID=user_id, roadmap_id=roadmap_id)

            # if response is not None:
            # always call backend
            # if response none : backend call
            # else: tango api call first step : True or False

            return jsonify({"status": "success", "data": response}), 200

        except Exception as e:
            appLogger.error({"event": "createRoadmapSplitFlow", "error": e, "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error"}), 500

    def fetchRoadmapInsights(self):
        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")
            appLogger.info({"event": "fetchRoadmapInsights", "tenant_id": tenant_id, "user_id": user_id})
            response = RoadmapInsightsCache(tenant_id=tenant_id, user_id=user_id, session_id="", init=False).fetch_insights()
            return jsonify({"status": "success", "data": response}), 200
        except Exception as e:
            appLogger.error({"event": "fetchRoadmapInsights", "error": e, "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error", "error": str(e)}), 500


    def autoCreateRoadmaps(self):
        """
        API endpoint to automatically create projects from eligible epics and issues.
        
        Expects JSON payload with tenant_id, user_id, and optional session_state.
        Returns JSON response with creation results or error message.
        """
        try:
            # Extract request data
            data = request.get_json()
            if not data:
                appLogger.error({
                    "function": "autoCreateRoadmaps",
                    "error": "No JSON data provided in request"
                })
                return jsonify({"error": "No JSON data provided"}), 400

            print("__autoCreateRoadmaps__", data)
            tenant_id = data.get("tenant_id")
            user_id = data.get("user_id")
            mode = data.get("mode")
            

            if not tenant_id or not user_id:
                appLogger.error({
                    "function": "autoCreateRoadmaps",
                    "tenant_id": tenant_id or "unknown",
                    "user_id": user_id or "unknown",
                    "error": "Missing tenant_id or user_id in request"
                })
                return jsonify({"error": "tenant_id and user_id are required"}), 400


            job_creator = RoadmapCreator(
                tenant_id=tenant_id,
                user_id=user_id            
            )
            results = job_creator.process_issues_for_roadmaps(mode)

         
            appLogger.info({
                "function": "autoCreateRoadmaps",
                "tenant_id": tenant_id,
                "user_id": user_id,
                "message": f"Successfully processed {len(results)} items"
            })
            return jsonify({
                "status": "success",
                "message": f"Successfully processed {len(results)} items",
                "results": results
            }), 200

        except Exception as e:
            appLogger.error({
                "function": "autoCreateRoadmaps",
                "tenant_id": tenant_id or "unknown",
                "user_id": user_id or "unknown",
                "error": f"Unexpected error: {str(e)}",
                "traceback": traceback.format_exc()
            })
            return jsonify({
                "status": "error",
                "error": f"Unexpected error: {str(e)}"
            }), 500
     