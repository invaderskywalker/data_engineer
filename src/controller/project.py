from flask import jsonify, request  # type: ignore
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.project.projectService import ProjectService
import traceback
from src.trmeric_services.agents.functions.integration_agent import JobProjectCreator, JobOrgStrategyCreator


class ProjectController:
    def __init__(self):
        self.projectService = ProjectService()

    def tangoAssistCreateKeyAccomplishments(self, project_id):
        try:
            user_id = request.decoded.get("user_id")
            tenant_id = request.decoded.get("tenant_id")
            response = self.projectService.tangoAssistCreateKeyAccomplishments(
                tenant_id,
                project_id,
                log_input=request.decoded,
                user_id=user_id
            )
            return jsonify({"status": "success", "data": response}), 200
        except Exception as e:
            appLogger.error({
                "event": "tangoAssistCreateKeyAccomplishments",
                "error": e,
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500

    def enhanceProjectCreateData(self, assist_keyword):
        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")
            project_name = request.json.get("project_name")
            project_description = request.json.get("project_description")
            project_objective = request.json.get("project_objective") or None
            project_key_results = request.json.get(
                "project_key_results") or None
            project_capabilities = request.json.get(
                "project_capabilities") or None

            is_provider_string = request.json.get("is_provider") or None
            is_provider = False
            if (is_provider_string == "true"):
                is_provider = True

            if assist_keyword == "description":
                response = self.projectService.enhanceDescription(
                    tenant_id,
                    project_name,
                    project_description,
                    is_provider,
                    log_input=request.decoded,
                    user_id=user_id
                )
            elif assist_keyword == "objective":
                response = self.projectService.enhanceProjectObjective(
                    tenant_id,
                    project_name,
                    project_description,
                    project_objective,
                    is_provider,
                    log_input=request.decoded,
                    user_id=user_id
                )
            elif assist_keyword == "key_results":
                response = self.projectService.createKeyResults(
                    tenant_id,
                    project_name,
                    project_description,
                    project_objective,
                    is_provider,
                    log_input=request.decoded,
                    user_id=user_id
                )
                
            elif assist_keyword == "project_capabilities":
                response = self.projectService.createProjectCpabilities(
                    tenant_id=tenant_id,
                    project_name=project_name,
                    project_description=project_description,
                    project_objective=project_objective,
                    project_key_results=project_key_results,
                    is_provider=is_provider,
                    log_input=request.decoded,
                    user_id=user_id       
                )
            elif assist_keyword == "tech_stack":
                response = self.projectService.findTechStackRequired(
                    tenant_id=tenant_id,
                    project_name=project_name,
                    project_description=project_description,
                    project_objective=project_objective,
                    project_key_results=project_key_results,
                    project_capabilities=project_capabilities,
                    is_provider=is_provider,
                    log_input=request.decoded,
                    user_id=user_id
                )
            return jsonify({"status": "success", "data": response}), 200
        except Exception as e:
            appLogger.error({
                "event": "enhanceDescription_Project",
                "error": e,
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500


    def autoCreateProjects(self):
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
                    "function": "autoCreateProjects",
                    "error": "No JSON data provided in request"
                })
                return jsonify({"error": "No JSON data provided"}), 400

            print("__autoCreateProjects__", data)
            tenant_id = data.get("tenant_id")
            user_id = data.get("user_id")
            mode = data.get("mode")
            file_name = data.get("file_name")
            session_state = data.get("session_state", {}) or {}

            if not tenant_id or not user_id:
                appLogger.error({
                    "function": "autoCreateProjects",
                    "tenant_id": tenant_id or "unknown",
                    "user_id": user_id or "unknown",
                    "error": "Missing tenant_id or user_id in request"
                })
                return jsonify({"error": "tenant_id and user_id are required"}), 400


            job_creator = JobProjectCreator(
                tenant_id=tenant_id,
                user_id=user_id            
            )
            results = job_creator.process_eligible_items_2(session_state=session_state, mode=mode, file_name=file_name)

            # # Check if any results contain errors
            # errors = [result for result in results if "error" in result]
            # if errors:
            #     appLogger.warning({
            #         "function": "autoCreateProjects",
            #         "tenant_id": tenant_id,
            #         "user_id": user_id,
            #         "message": f"Processed with {len(errors)} errors",
            #         "errors": errors
            #     })
            #     return jsonify({
            #         "status": "partial_success",
            #         "message": f"Processed with {len(errors)} errors",
            #         "results": results
            #     }), 207  # Multi-Status for partial success

            appLogger.info({
                "function": "autoCreateProjects",
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
                "function": "autoCreateProjects",
                "tenant_id": tenant_id or "unknown",
                "user_id": user_id or "unknown",
                "error": f"Unexpected error: {str(e)}",
                "traceback": traceback.format_exc()
            })
            return jsonify({
                "status": "error",
                "error": f"Unexpected error: {str(e)}"
            }), 500
            
            
    def update_projects_attributes_for_tenant(self):
        try:
            data = request.get_json()
            print("update_projects_attributes_for_tenant", data)
            tenant_id = data.get("tenant_id")
            user_id = data.get("user_id")

            if not tenant_id or not user_id:
                appLogger.error({
                    "function": "update_projects_attributes_for_tenant",
                    "tenant_id": tenant_id or "unknown",
                    "user_id": user_id or "unknown",
                    "error": "Missing tenant_id or user_id in request"
                })
                return jsonify({"error": "tenant_id and user_id are required"}), 400


            job_creator = JobOrgStrategyCreator(
                tenant_id=tenant_id,
                user_id=user_id            
            )
            results = job_creator.process_projects()
            return jsonify({
                "status": "success",
                "message": f"Successfully processed {len(results)} items",
                "results": results
            }), 200

        except Exception as e:
            appLogger.error({
                "function": "update_projects_attributes_for_tenant",
                "tenant_id": tenant_id or "unknown",
                "user_id": user_id or "unknown",
                "error": f"Unexpected error: {str(e)}",
                "traceback": traceback.format_exc()
            })
            return jsonify({
                "status": "error",
                "error": f"Unexpected error: {str(e)}"
            }), 500
            