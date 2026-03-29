from flask import request, jsonify
from src.trmeric_api.logging.AppLogger import appLogger
import traceback
import threading
from src.trmeric_services.integration.IntegrationService import IntegrationService
from src.trmeric_services.insight.InsightService import InsightService
from src.trmeric_database.dao.tenant import TenantDao
from src.trmeric_services.internal.knowledge import ProjectsKnowledge
from src.trmeric_database.dao import CronDao, IntegrationDao
from datetime import datetime, timezone, timedelta

from src.trmeric_services.agents.notify.agents.service_assurance import TriggerServiceAssuranceNotify
from src.trmeric_services.knowledge import KnowledgeV1, KnowledgeV2

from src.trmeric_services.agents.precache import ServiceAssurancePrecache
import os


class CronController:
    def __init__(self):
        self.integrationService = IntegrationService()
        self.insightService = InsightService()

    def integrationDataUpdate(self):
        thread = threading.Thread(target=self.integration_update_worker)
        thread.start()
        return jsonify({"message": "Cron started running"}), 202

    def cronIntegrationSummaryUpdate(self):
        tenant_id = request.json.get("tenant_id")
        user_id = request.json.get("user_id")
        thread = threading.Thread(target=self.integrationSummaryUpdate, args=(tenant_id, user_id))
        thread.start()
        return jsonify({"message": "Cron started running"}), 202

    def integrationSummaryUpdate(self, tenant_id, user_id):

        appLogger.info({"event": "integrationSummaryUpdateStart"})
        try:
            self.integrationService.jiraSummaryCreate(
                tenant_id,
                user_id,
                # project_id
            )
        except Exception as e:
            appLogger.error({"event": "integrationSummaryUpdate", "tenant_id": tenant_id, "user_id": user_id, "error": e, "traceback": traceback.format_exc()})
            print("error while running integrationSummaryUpdate ", tenant_id, e, traceback.format_exc())

    def integrationDataUpdateUser(self):
        appLogger.info({"event": "integrationDataUpdateUser_triggered", "payload": request.json})
        user_id = request.json.get("user_id")
        thread = threading.Thread(target=self.integration_update_worker_user, args=(user_id,))
        thread.start()
        return jsonify({"message": "Cron started running"}), 202

    def integration_update_worker_user(self, request_user_id):
        result = IntegrationDao.fetchAllIntegratinoMappingForUser(user_id=request_user_id)
        print("debug --", result)
        appLogger.info({"event": "integration_update_worker_start"})
        for res in result:
            try:
                # print("Integration Cron Running for ", res)
                tenant_id = res['tenant_id']
                user_id = res["user_id"]
                project_id = res["trmeric_project_id"]
                if request_user_id == user_id:
                    print("Integration Cron 2 Running for ", res)
                    self.integrationService.updateIntegrationData(tenant_id, user_id, project_id, daily=True)
            except Exception as e:
                appLogger.error({"event": "integration_update_worker", "tenant_id": tenant_id, "user_id": user_id, "project_id": project_id, "error": e, "traceback": traceback.format_exc()})
                print("error while running integration_update_worker ", tenant_id, user_id, project_id, e, traceback.format_exc())

    def integration_update_worker(self):
        result = self.integrationService.getActiveProjectMappings()
        # print("debug --", result)
        appLogger.info({"event": "integration_update_worker_start"})
        for res in result:
            try:
                print("Integration Cron Running for ", res)
                tenant_id = res['tenant_id']
                user_id = res["user_id"]
                project_id = res["trmeric_project_id"]

                # if res.get("integration_type") == "jira" or res.get("integration_type") == "smartsheet":
                #     continue

                appLogger.info(
                    {
                        "event": "integration_update_worker",
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "project_id": project_id,
                        "integration_type": res.get("integration_type"),
                    }
                )
                self.integrationService.updateIntegrationData(tenant_id, user_id, project_id, daily=True)

            except Exception as e:
                appLogger.error({"event": "integration_update_worker", "tenant_id": tenant_id, "user_id": user_id, "project_id": project_id, "error": e, "traceback": traceback.format_exc()})
                print("error while running integration_update_worker ", tenant_id, user_id, project_id, e, traceback.format_exc())

            try:
                self.integrationService.jiraSummaryCreate(tenant_id, user_id)
            except Exception as e:
                appLogger.error({"event": "jiraSummaryCreate_error", "tenant_id": tenant_id, "user_id": user_id, "error": e, "traceback": traceback.format_exc()})

    def integration_update_worker_hourly(self):
        appLogger.info({"event": "integration_update_worker_hourly"})
        result = self.integrationService.getActiveProjectMappingsV2()
        appLogger.info({"event": "integration_update_worker_hourly_2"})
        for res in result:
            try:
                tenant_id = res['tenant_id']
                user_id = res["user_id"]
                project_id = res["trmeric_project_id"]
                integration_mapping_id = res["id"]
                if tenant_id == 71 or tenant_id == "71":
                    continue

                print("Integration Cron Running for ", res, res.get("integration_type") == "jira" or res.get("integration_type") == "smartsheet")

                if res.get("integration_type") == "jira" or res.get("integration_type") == "smartsheet":
                    appLogger.info({
                        "event": "integration_update_worker_hourly_3",
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "project_id": project_id,
                        "integration_mapping_id": integration_mapping_id,
                        "integration_type": res.get("integration_type"),
                    })
                    try:
                        self.integrationService.updateIntegrationDataV3(
                            project_id, 
                            tenant_id, 
                            user_id, 
                            integration_mapping_id,
                            True
                        )
                    except Exception as e1:
                        appLogger.error({
                            "event": "integration_update_worker_hourly",
                            "tenant_id": tenant_id,
                            "user_id": user_id,
                            "project_id": project_id,
                            "error":  e1,
                            "traceback": traceback.format_exc()
                        })

            except Exception as e:
                appLogger.error({"event": "integration_update_worker_hourly", "tenant_id": tenant_id, "user_id": user_id, "project_id": project_id, "error": e, "traceback": traceback.format_exc()})
                print("error while running integration_update_worker_hourly ", tenant_id, user_id, project_id, e, traceback.format_exc())

            # try:
            #     appLogger.info({
            #         "event": "integration_update_worker_hourly_summary",
            #         "tenant_id": tenant_id,
            #         "user_id": user_id,
            #         "project_id": project_id,
            #         "integration_mapping_id": integration_mapping_id
            #     })
            #     self.integrationService.jiraSummaryCreate(tenant_id, user_id)
            # except Exception as e:
            #     appLogger.error({
            #         "event": "jiraSummaryCreate_error",
            #         "tenant_id": tenant_id,
            #         "user_id": user_id,
            #         "error":  e,
            #         "traceback": traceback.format_exc()
            #     })

    def signalCreate(self):
        print("signalCreate", request.json)
        tenant_id = request.json.get("tenant_id")
        thread = threading.Thread(target=self.insightService.createDailyDigest, args=(tenant_id,))

        # thread = threading.Thread(target=self.insightService.createDailyDigest(tenant_id))
        thread.start()
        return jsonify({"message": "Cron started running"}), 200

    def dailyCronRun(self):
        appLogger.info({"event": "dailyCronRun running"})
        should_run = False

        last_run_time = CronDao.FetchTangoLastCronRunTime()
        if last_run_time == None:
            should_run = True
        else:
            if isinstance(last_run_time, str):
                # Use the appropriate format if needed
                last_run_time = datetime.fromisoformat(last_run_time)

            current_date = datetime.now(timezone.utc).date()
            current_time = datetime.now(timezone.utc)
            # Check if 24 hours have passed since the last run
            if current_time - last_run_time >= timedelta(hours=24):
                should_run = True
                appLogger.info(
                    {"event": "dailyCronRun - 24 hours have passed since the last run. Cron will run.", "last_run_time": last_run_time, "current_time": current_time, "should_run": should_run}
                )
            else:
                appLogger.info(
                    {
                        "event": "dailyCronRun - Less than 24 hours since the last run. Skipping.",
                        "last_run_time": last_run_time,
                        "current_time": current_time,
                        "time_difference": str(current_time - last_run_time),
                        "should_run": should_run,
                    }
                )

        if not should_run:
            return

        print("should run ----= ", should_run)

        current_time = datetime.now(timezone.utc)
        CronDao.UpdateTangoLastCronRunTime(current_time)

        # return

        # steps
        # 1. update jira of all mapingss
        # 2. create digest for al tenants
        # self.integration_update_worker()
        # try:
        #     self.integration_update_worker()
        # except Exception as e:
        #     appLogger.error({
        #         "event": "dailyCronRun error",
        #         "error": str(e),
        #         "traceback": traceback.format_exc()
        #     })

        # fetch all tenants
        all_tenants = TenantDao.FetchAllTenants()
        all_tenants_id = []
        for tenant in all_tenants:
            try:
                all_tenants_id.append(tenant["id"])
                self.insightService.createDailyDigest(tenant["id"])
            except Exception as e:
                appLogger.error(
                    {
                        "event": "dailyCronRun",
                        "part": "insightService",
                        "error": str(e),
                    }
                )
        # print("debug al;l tenants ")
        appLogger.info({"event": "dailyCronRun done", "all_tenants_id": all_tenants_id})

        return "Done"

    def precache_force(self):
        tenant_id = request.json.get("tenant_id")
        user_id = request.json.get("user_id")
        ServiceAssurancePrecache(tenant_id=tenant_id, user_id=user_id, init=True, force=True)
        return {"done": "success"}

    def hourlyCronRun(self):
        if os.getenv("ENVIRONMENT") == "dev":
            return
        appLogger.info({"event": "hourlyCronRun running"})
        should_run = False

        last_run_time = CronDao.FetchTangoLastCronRunTime("tango_hourly_cron_run")
        appLogger.info({"event": "hourlyCronRun running checking", "last_run_time": last_run_time})
        if last_run_time == None:
            should_run = True
        else:
            if isinstance(last_run_time, str):
                last_run_time = datetime.fromisoformat(last_run_time)

            current_date = datetime.now(timezone.utc).date()
            current_time = datetime.now(timezone.utc)
            if current_time - last_run_time >= timedelta(hours=24):
                should_run = True
                appLogger.info(
                    {"event": "hourlyCronRun - 6 hours have passed since the last run. Cron will run.", "last_run_time": last_run_time, "current_time": current_time, "should_run": should_run}
                )
            else:
                appLogger.info(
                    {
                        "event": "hourlyCronRun - Less than 6 hours since the last run. Skipping.",
                        "last_run_time": last_run_time,
                        "current_time": current_time,
                        "time_difference": str(current_time - last_run_time),
                        "should_run": should_run,
                    }
                )

        if not should_run:
            return

        appLogger.info({"event": "hourlyCronRun running ", "last_run_time": last_run_time})

        print("should run hourlyCronRun ----= ", should_run)

        current_time = datetime.now(timezone.utc)
        CronDao.UpdateTangoLastCronRunTime(current_time, "tango_hourly_cron_run", "hourly")

        try:
            self.integration_update_worker_hourly()
        except Exception as e:
            appLogger.error({"event": "hourlyCronRun error", "error": str(e), "traceback": traceback.format_exc()})

        appLogger.info(
            {
                "event": "hourlyCronRun done",
            }
        )

        return "Done"

    def createKnowledge(self):
        # tenant_id = request.json.get("tenant_id")
        # # roadmap_knowledge = RoadmapKnowledge()
        # project_knowledge = ProjectsKnowledge()
        # thread = threading.Thread(
        #     target=project_knowledge.extract_project_knowledge, args=(tenant_id,))
        # thread.start()

        # project_id = request.json.get("project_id")
        # v1_service = KnowledgeV1()
        # v1_service.create(project_id=project_id)

        tenant_id = request.json.get("tenant_id")
        v2_service = KnowledgeV2(tenant_id=tenant_id)
        v2_service.create()

        return jsonify({"message": "Knowledge Created"}), 202

    def trigger_notif_mail(self):
        tenant_id = request.json.get("tenant_id")
        user_id = request.json.get("user_id")
        mail_type = request.json.get("mail_type")
        if mail_type == "execution_update":
            TriggerServiceAssuranceNotify().send_execution_update(tenant_id, user_id)
            
        return jsonify({"message": "trigger_notif_mail"}), 202
    
    
    
