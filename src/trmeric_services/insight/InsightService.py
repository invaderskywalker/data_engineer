from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_services.insight.Prompts import createInsightForProjectUpdatePrompt
from src.trmeric_utils.json_parser import extract_json_after_llm
import json
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.insight.ProjectsSpaceInsightCreator import ProjectsSpaceInsightCreator
# import threading
import traceback
from src.trmeric_services.insight.Digest import DigestService
import threading
from datetime import datetime
from src.trmeric_database.dao import JobDAO, ProjectsDaoV2



class InsightService:
    def __init__(self):
        self.llm = ChatGPTClient()

    def createInsightForProjectUpdate(self, data, project_id):
        prompt = createInsightForProjectUpdatePrompt(data)
        modelOptions = ModelOptions(
            model="gpt-4o",
            max_tokens=1000,
            temperature=0
        )
        response = self.llm.run(prompt, modelOptions, None)
        insightJson = extract_json_after_llm(response)
        # try:
        #     ProjectsSpaceInsightCreator().process_update(project_id)
        # except Exception as e:
        #     appLogger.error({
        #         "function": "_error",
        #         "event": "failed to create insights for measure -> projects -> project, portfolio, provider",
        #         "traceback": traceback.format_exc(),
        #         "error": e
        #     })
            
        def async_process():
            try:
                run_id = f"insight-{project_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                payload = {
                    "job_type": "insight-project-update",
                    "name": "insight-project-update",
                    "payload": {
                        "job_type": "insight-project-update",
                        "run_id": run_id,
                        "session_id": "",
                        "project_id": project_id
                    }
                }
                job_dao = JobDAO
                ## get tenant id and user id from project id 
                info = ProjectsDaoV2.fetchTenantIdAndCreatedByIDForProjectId(project_id)
                job_dao.create(
                    tenant_id=info["tenant_id"],
                    user_id=info["user_id"],
                    schedule_id=None,
                    job_type=payload["job_type"],
                    payload=payload["payload"]
                )
            except Exception as e:
                pass
            # try:
            #     ProjectsSpaceInsightCreator().process_update(project_id)
            # except Exception as e:
            #     appLogger.error({
            #         "function": "_error",
            #         "event": "failed to create insights for measure -> projects -> project, portfolio, provider",
            #         "traceback": traceback.format_exc(),
            #         "error": e
            #     })

        # # Start the background thread
        threading.Thread(target=async_process).start()
        return insightJson["insight"]
    
    
    def createDailyDigest(self, tenant_id):
        print("here ")
        try:
            DigestService().createDailyDigest(tenant_id)
        except Exception as e:
            appLogger.error({
                "event": "createDailyDigest",
                "traceback": traceback.format_exc(),
                "error": str(e)
            })
