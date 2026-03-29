import uuid
from flask import jsonify
from src.trmeric_api.logging.AppLogger import appLogger
import traceback
from src.trmeric_services.integration.IntegrationService import IntegrationService
from src.trmeric_database.dao import CronDao, IntegrationDao, JobDAO, TangoDao, TenantDao, CommonDao, db_instance
from datetime import datetime, timezone, timedelta
from src.trmeric_services.agents.precache import PortfolioReview, RoadmapInsightsCache
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from threading import Lock
from src.trmeric_services.agents_v2.actions import Creator
from src.trmeric_services.journal.ActivityEndpoints import session_summary, tango_session_summary
from src.trmeric_utils.knowledge.TangoMemory import TangoMem
from src.trmeric_ml.models.training import start_training
from src.trmeric_services.agents_v2.actions.alerts import AlertCreator
from src.trmeric_utils.helper.common import allowed_tenants



PROJECT_ALERT_TENANTS = allowed_tenants(dev=[],qa=[], prod=[227])
DAILY_DIGEST_TENANTS = allowed_tenants(dev=[776],qa=[237], prod=[2, 198])

# ── ADD this constant alongside the others at the top ──────────────────────
FY27_DEMAND_TENANTS = allowed_tenants(dev=[776], qa=[], prod=[227])
# ── ADD these 2 entries to JOB_CONFIGS ─────────────────────────────────────
JOB_CONFIGS = {
    "rl-xgboost-training": {
        "threshold": 2,
        "allowed_tenants": None,
        "run_id_prefix": "rl-xgboost",
    },
    "project-status-alert": {
        "threshold": 1,
        "allowed_tenants": PROJECT_ALERT_TENANTS,
        "run_id_prefix": "project-status-alert",
    },
    "daily_digest": {
        "threshold": 1,
        "allowed_tenants": DAILY_DIGEST_TENANTS,
        "run_id_prefix": "daily_digest_update",
    },
    # ── NEW ──
    "emails:fy27-demand-kickoff": {
        "threshold": 1,
        "allowed_tenants": FY27_DEMAND_TENANTS,
        "run_id_prefix": "fy27-demand-kickoff",
    },
    "emails:fy27-zero-demand-nudge": {
        "threshold": 1,
        "allowed_tenants": FY27_DEMAND_TENANTS,
        "run_id_prefix": "fy27-zero-demand-nudge",
    },
}

def get_integration_state(tenant_id, total, state="integration"):
    _map = {}
    state_key = f"TENANT_LEVEL_INTEGRATION_INFO_"
    if state == 'create-project':
        state_key = f"TENANT_LEVEL_PROJECT_CREATION_INFO_"
    if state == 'create-roadmap':
        state_key = f"TENANT_LEVEL_ROADMAP_CREATION_INFO_"
    if state == 'update-project':
        state_key = f"TENANT_LEVEL_PROJECT_UPDATE_INFO_"

    state = TangoDao.fetchLatestTangoStatesForTenant(tenant_id, state_key)
    if state:
        print("yes run id not in counter map and state found")
        state_value = json.loads(state["value"])
        print("yes run id not in counter map and state found ", state_value)
        if "success" not in state_value:
            _map = {"done": 0, "failed": 0, "total": total}
        else:
            _map = state_value
    else:
        _map = {"done": 0, "failed": 0, "total": total}
    return _map


class CronControllerV2:
    def __init__(self):
        self.integrationService = IntegrationService()
        self.jobDao = JobDAO
        self.batch_size = 4
        self.counter_lock = Lock()

    def v2Run(self):
        """
        Orchestrates cron jobs:
        1. Find tenants due for cron.
        2. Enqueue their project jobs in PostgreSQL.
        3. Process pending jobs in batch.
        """
        appLogger.info({"event": "incoming v2Run"})
        print("running cron")
        # return

        try:
            # ----------------------------------------------------
            # Phase 1: Enqueue jobs for tenants due for cron
            # ----------------------------------------------------
            due_tenants = CronDao.fetch_due_tenant_schedules()
            print(f"Tenants due for cron: {due_tenants}")

            for tenant in due_tenants:
                tenant_id = tenant["tenant_id"]
                schedule_id = tenant["id"]

                # Step 1: Generate run_id
                run_id = f"{schedule_id}-{tenant_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

                # Step 2: Mark scheduled
                CronDao.update_last_scheduled(
                    schedule_id, datetime.utcnow(), f"Run {run_id} scheduled")

                # Step 3: Get active projects
                projects = IntegrationDao.fetchActiveProjectMappingsFortenant(
                    tenant_id=tenant_id)
                total_count = len(projects)

                # Step 4: Enqueue integration jobs
                for res in projects:
                    payload = {
                        "job_type": "integration-job",
                        "project_id": res["trmeric_project_id"],
                        "integration_mapping_id": res["id"],
                        "schedule_id": schedule_id,
                        "run_id": run_id,
                        "total_count": total_count
                    }
                    job_id = self.jobDao.create(
                        tenant_id=tenant_id,
                        user_id=res["user_id"],
                        schedule_id=schedule_id,
                        job_type="integration-job",
                        payload=payload
                    )
                    print(
                        f"✅ Enqueued job for tenant {tenant_id}, project {res['trmeric_project_id']} (run {run_id})")

                CronDao.update_progress(
                    schedule_id, f"Enqueued {total_count} jobs for run {run_id}")

            # try:
            #     # ----------------------------------------------------
            #     # Phase 3: Enqueue portfolio-review jobs for tenants without existing entries
            #     # ----------------------------------------------------
            #     tenants = TenantDao.FetchAllTenantIDs()

            #     # Fetch all recent portfolio-review jobs in one query
            #     time_threshold = datetime.utcnow() - timedelta(hours=24)
            #     job_type = "portfolio-review"
            #     time_threshold_str = time_threshold.strftime("%Y-%m-%d %H:%M:%S")
            #     recent_jobs_query = f"""
            #         SELECT tenant_id FROM cron_jobstracker
            #         WHERE job_type = '{job_type}' AND created_at >= '{time_threshold_str}'
            #     """
            #     print("recent_jobs_query ", recent_jobs_query)
            #     recent_jobs = db_instance.retrieveSQLQueryOld(recent_jobs_query)
            #     tenants_with_recent_jobs = {job["tenant_id"] for job in recent_jobs}
            #     print("tenants_with_recent_jobs", tenants_with_recent_jobs)

            #     for tenant in tenants:
            #         tenant_id = tenant["id"]  # Assuming 'id' is the tenant_id field from tenant_tenant table

            #         if tenant_id not in tenants_with_recent_jobs:
            #             # No portfolio-review job exists, create a new one
            #             run_id = f"portfolio-{tenant_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            #             payload = {
            #                 "job_type": "portfolio-review",
            #                 "run_id": run_id,
            #                 "total_count": 1  # Single job for portfolio-review
            #             }
            #             # roadmap-insights-cache
            #             users = TenantDao.FetchUsersOfTenant(tenant_id)
            #             if not users:
            #                 continue

            #             print("tenant id -- ", tenant_id)

            #             user_id = users[0]["user_id"]

            #             job_id = self.jobDao.create(
            #                 tenant_id=tenant_id,
            #                 user_id=user_id,
            #                 schedule_id=None,
            #                 job_type="portfolio-review",
            #                 payload=payload
            #             )
            #             print(f"✅ Enqueued portfolio-review job for tenant {tenant_id} (run {run_id})")
            #             run_id = f"roadmap-{tenant_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            #             payload = {
            #                 "job_type": "roadmap-insights-cache",
            #                 "run_id": run_id,
            #                 "total_count": 1  # Single job for portfolio-review
            #             }
            #             job_id = self.jobDao.create(
            #                 tenant_id=tenant_id,
            #                 user_id=user_id,
            #                 schedule_id=None,
            #                 job_type="portfolio-review",
            #                 payload=payload
            #             )
            #             print(f"✅ Enqueued portfolio-review job for tenant {tenant_id} (run {run_id})")
            #         else:
            #             print(f"Skipping tenant {tenant_id}: portfolio-review job already exists")
            # except Exception as e:
            #     print("error ", e)

            try:
                # ----------------------------------------------------
                # Enqueue ML model training jobs for tenants due for reinforcement
                self.model_training_scheduler()
            except Exception as e:
                print("error ", e)
                appLogger.error({"event": "model_training_scheduler","error": str(e),"traceback": traceback.format_exc()})

            ###### Create Project Status Alert service ##########
            try:
                self.project_status_alerts_service()
            except Exception as e:
                appLogger.error({"event": "project_status_alerts_service","error": str(e),"traceback": traceback.format_exc()})


            try:
                self.daily_digest_update()
            except Exception as e:
                appLogger.error({"event": "daily_digest_update","error": str(e),"traceback": traceback.format_exc()})


            # try:
            #     self._run_scheduled_job("emails:fy27-demand-kickoff")
            # except Exception as e:
            #     appLogger.error({"event": "fy27_demand_kickoff_scheduler", "error": str(e), "traceback": traceback.format_exc()})
            
            # try:
            #     self._run_scheduled_job("emails:fy27-zero-demand-nudge")
            # except Exception as e:
            #     appLogger.error({"event": "fy27_zero_demand_nudge_scheduler", "error": str(e), "traceback": traceback.format_exc()})
                    

            # Phase 2: Process jobs in PostgreSQL (batch execution with threading)
            jobs = self.jobDao.read_by_status(status="pending", limit=self.batch_size)
            processed_jobs = []
            run_id_counters = {}

            def process_job(job):
                """Helper function to process a single job and return its ID and status."""
                job_id = job["id"]
                # print(f"Processing job: {job}")

                try:
                    # Step 1: Mark in-progress
                    self.jobDao.update_status(job_id, "in-progress")

                    # Step 2: Process job based on type
                    payload = job["payload"]
                    job_type = payload.get("job_type")
                    run_id = payload.get("run_id") or None
                    schedule_id = payload.get("schedule_id") or None
                    total = payload.get("total_count") or 0

                    if run_id not in run_id_counters and (job_type == "user_request_cron" or job_type == "integration-job"):
                        run_id_counters[run_id] = get_integration_state(
                            tenant_id=job["tenant_id"], total=total)

                    if run_id not in run_id_counters and (job_type == "create-project"):
                        run_id_counters[run_id] = get_integration_state(
                            tenant_id=job["tenant_id"], total=total, state="create-project")

                    if run_id not in run_id_counters and (job_type == "create-roadmap"):
                        run_id_counters[run_id] = get_integration_state(
                            tenant_id=job["tenant_id"], total=total, state="create-roadmap")

                    if run_id not in run_id_counters and (job_type == "update-project"):
                        run_id_counters[run_id] = get_integration_state(
                            tenant_id=job["tenant_id"], total=total, state="update-project")

                    print("run counter mapping ", run_id_counters)
                    if job_type == "portfolio-review":
                        PortfolioReview(
                            tenant_id=job["tenant_id"],
                            user_id=job["user_id"],
                            init=True
                        )
                    if job_type == "daily_digest":
                        from src.trmeric_services.insight.Digest import DigestService
                        print("000", job)
                        DigestService().createDailyDigest(
                            tenant_id=job["tenant_id"], 
                            user_id=job["user_id"],
                        )
                    elif job_type == "create-project":
                        try:
                            print("run create project ")
                            creator = Creator(
                                tenant_id=job["tenant_id"],
                                user_id=job["user_id"]
                            )
                            creator.create_project(
                                item=payload.get("data"),
                                additional_data=payload.get(
                                    "extra_data") or [],
                                # Pass socket_id from payload
                                socket_id=payload.get("socket_id")
                            )
                            run_id_counters[run_id]["done"] += 1
                        except Exception as e:
                            appLogger.error({
                                "event": "cronV2",
                                "function": "updateIntegrationDataV3",
                                "error": str(e),
                                "traceback": traceback.format_exc()
                            })
                            run_id_counters[run_id]["failed"] += 1

                        state_value = {
                            "success": run_id_counters[run_id]["done"],
                            "done": run_id_counters[run_id]["done"],
                            "failed": run_id_counters[run_id]["failed"],
                            "total": run_id_counters[run_id]["total"],
                            "message": f"{run_id_counters[run_id]['done']}/{run_id_counters[run_id]['total']} Done, {run_id_counters[run_id]['failed']}/{run_id_counters[run_id]['total']} Failed"
                        }
                        TangoDao.insertTangoState(
                            tenant_id=job["tenant_id"],
                            user_id=job["user_id"],
                            key=f"TENANT_LEVEL_PROJECT_CREATION_INFO_{run_id}",
                            value=json.dumps(state_value),
                            session_id=""
                        )

                    elif job_type == "create-roadmap":
                        try:
                            print("run create roadmap ")
                            creator = Creator(
                                tenant_id=job["tenant_id"],
                                user_id=job["user_id"]
                            )
                            result = creator.create_roadmap(
                                item=payload.get("data"),
                                additional_data=payload.get(
                                    "extra_data") or {},
                                original_used_data=payload.get(
                                    "original_used_data") or {},
                                # Pass socket_id from payload
                                socket_id=payload.get("socket_id")
                            )
                            run_id_counters[run_id]["done"] += 1
                        except Exception as e:
                            appLogger.error({
                                "event": "cronV2",
                                "function": "updateIntegrationDataV3",
                                "error": str(e),
                                "traceback": traceback.format_exc()
                            })
                            run_id_counters[run_id]["failed"] += 1

                        state_value = {
                            "success": run_id_counters[run_id]["done"],
                            "done": run_id_counters[run_id]["done"],
                            "failed": run_id_counters[run_id]["failed"],
                            "total": run_id_counters[run_id]["total"],
                            "message": f"{run_id_counters[run_id]['done']}/{run_id_counters[run_id]['total']} Done, {run_id_counters[run_id]['failed']}/{run_id_counters[run_id]['total']} Failed"
                        }
                        TangoDao.insertTangoState(
                            tenant_id=job["tenant_id"],
                            user_id=job["user_id"],
                            key=f"TENANT_LEVEL_ROADMAP_CREATION_INFO_{run_id}",
                            value=json.dumps(state_value),
                            session_id=""
                        )

                    elif job_type == "create-idea_creation_schema":
                        try:
                            print("run create-idea_creation_schema ")
                            creator = Creator(
                                tenant_id=job["tenant_id"],
                                user_id=job["user_id"]
                            )
                            result = creator.create_roadmap(
                                item=payload.get("data"),
                                additional_data=payload.get(
                                    "extra_data") or {},
                                original_used_data=payload.get(
                                    "original_used_data") or {},
                                # Pass socket_id from payload
                                socket_id=payload.get("socket_id")
                            )
                            run_id_counters[run_id]["done"] += 1
                        except Exception as e:
                            appLogger.error({
                                "event": "cronV2",
                                "function": "create-idea_creation_schema",
                                "error": str(e),
                                "traceback": traceback.format_exc()
                            })
                            run_id_counters[run_id]["failed"] += 1

                        state_value = {
                            "success": run_id_counters[run_id]["done"],
                            "done": run_id_counters[run_id]["done"],
                            "failed": run_id_counters[run_id]["failed"],
                            "total": run_id_counters[run_id]["total"],
                            "message": f"{run_id_counters[run_id]['done']}/{run_id_counters[run_id]['total']} Done, {run_id_counters[run_id]['failed']}/{run_id_counters[run_id]['total']} Failed"
                        }
                        TangoDao.insertTangoState(
                            tenant_id=job["tenant_id"],
                            user_id=job["user_id"],
                            key=f"TENANT_LEVEL_IDEA_CREATION_INFO_{run_id}",
                            value=json.dumps(state_value),
                            session_id=""
                        )

                    elif job_type == "update-project":
                        try:
                            print("run update project ")
                            creator = Creator(
                                tenant_id=job["tenant_id"],
                                user_id=job["user_id"]
                            )
                            results = creator.project_updates(
                                updates_json=payload.get("mapped_data", [])
                            )

                            # Count successful vs failed updates
                            successful_count = sum(
                                1 for r in results if r.get("status") == "success")
                            failed_count = len(results) - successful_count

                            print(
                                f"Project updates completed: {successful_count} successful, {failed_count} failed")

                            if run_id:
                                run_id_counters[run_id]["done"] += successful_count
                                run_id_counters[run_id]["failed"] += failed_count

                        except Exception as e:
                            appLogger.error({
                                "event": "cronV2",
                                "function": "update_project",
                                "error": str(e),
                                "traceback": traceback.format_exc()
                            })
                            if run_id:
                                run_id_counters[run_id]["failed"] += 1

                        if run_id:
                            state_value = {
                                "success": run_id_counters[run_id]["done"],
                                "done": run_id_counters[run_id]["done"],
                                "failed": run_id_counters[run_id]["failed"],
                                "total": run_id_counters[run_id]["total"],
                                "message": f"{run_id_counters[run_id]['done']}/{run_id_counters[run_id]['total']} Done, {run_id_counters[run_id]['failed']}/{run_id_counters[run_id]['total']} Failed"
                            }
                            TangoDao.insertTangoState(
                                tenant_id=job["tenant_id"],
                                user_id=job["user_id"],
                                key=f"TENANT_LEVEL_PROJECT_UPDATE_INFO_{run_id}",
                                value=json.dumps(state_value),
                                session_id=""
                            )

                    elif job_type == "create-potential":
                        try:
                            print("run create potential ")
                            creator = Creator(
                                tenant_id=job["tenant_id"],
                                user_id=job["user_id"]
                            )
                            results = creator.create_potential(
                                data_array=payload.get("data"),
                                # Pass socket_id from payload
                                socket_id=payload.get("socket_id")
                            )
                            # save this result log
                            # run_id_counters[run_id]["done"] += 1
                        except Exception as e:
                            appLogger.error({
                                "event": "cronV2",
                                "function": "updateIntegrationDataV3",
                                "error": str(e),
                                "traceback": traceback.format_exc()
                            })
                            # run_id_counters[run_id]["failed"] += 1

                        # state_value = {
                        #     "success": run_id_counters[run_id]["done"],
                        #     "done": run_id_counters[run_id]["done"],
                        #     "failed": run_id_counters[run_id]["failed"],
                        #     "total": run_id_counters[run_id]["total"],
                        #     "message": f"{run_id_counters[run_id]['done']}/{run_id_counters[run_id]['total']} Done, {run_id_counters[run_id]['failed']}/{run_id_counters[run_id]['total']} Failed"
                        # }
                        # TangoDao.insertTangoState(
                        #     tenant_id=job["tenant_id"],
                        #     user_id=job["user_id"],
                        #     key=f"TENANT_LEVEL_ROADMAP_CREATION_INFO_{run_id}",
                        #     value=json.dumps(state_value),
                        #     session_id=""
                        # )

                    elif job_type == "roadmap-insights-cache":
                        RoadmapInsightsCache(
                            tenant_id=job["tenant_id"],
                            user_id=job["user_id"],
                            session_id=payload.get("session_id", ""),
                            init=True
                        )
                    elif job_type == "insight-project-update":
                        from src.trmeric_services.insight.ProjectsSpaceInsightCreator import ProjectsSpaceInsightCreator
                        ProjectsSpaceInsightCreator().process_update(payload.get("project_id", ""))
                    elif job_type == "user_request_cron" or job_type == "integration-job":
                        try:
                            self.integrationService.updateIntegrationDataV3(
                                payload["project_id"],
                                job["tenant_id"],
                                job["user_id"],
                                payload["integration_mapping_id"],
                                True
                            )
                            run_id_counters[run_id]["done"] += 1
                        except Exception as e:
                            appLogger.error({
                                "event": "cronV2",
                                "function": "updateIntegrationDataV3",
                                "error": str(e),
                                "traceback": traceback.format_exc()
                            })
                            run_id_counters[run_id]["failed"] += 1

                        state_value = {
                            "state": 1,
                            "success": run_id_counters[run_id]["done"],
                            "done": run_id_counters[run_id]["done"],
                            "failed": run_id_counters[run_id]["failed"],
                            "total": run_id_counters[run_id]["total"],
                            "message": f"{run_id_counters[run_id]['done']}/{run_id_counters[run_id]['total']} Done, {run_id_counters[run_id]['failed']}/{run_id_counters[run_id]['total']} Failed"
                        }
                        if run_id_counters[run_id]["done"] + run_id_counters[run_id]["failed"] == run_id_counters[run_id]["total"]:
                            state_value["state"] = 2
                        TangoDao.insertTangoState(
                            tenant_id=job["tenant_id"],
                            user_id=job["user_id"],
                            key=f"TENANT_LEVEL_INTEGRATION_INFO_{run_id}",
                            value=json.dumps(state_value),
                            session_id=""
                        )

                    elif job_type == "session-summary":
                        try:
                            user_id = payload.get("user_id")
                            socket_id = payload.get("socket_id")
                            session_ids = payload.get("session_ids", [])

                            if not user_id:
                                appLogger.error(
                                    f"Cannot run session summary for job {job_id}: user_id is missing.")
                                return job_id, "failed"

                            print(
                                f"Starting session summary for job {job_id}, User ID: {user_id}, Socket ID: {socket_id}")

                            # Call session_summary with user_id and socket_id
                            summary = session_summary(
                                socket_id=socket_id, user_id=user_id)
                            print(
                                f"Session summary completed for job {job_id}, User ID: {user_id}: {summary}")

                        except Exception as e:
                            appLogger.error({
                                "event": "session_summary_job_failed",
                                "error": str(e),
                                "traceback": traceback.format_exc(),
                                "job_id": job_id
                            })
                            print(
                                f"Error in session summary job {job_id}: {e}")
                            raise

                    elif job_type == "tango-session-summary":
                        try:
                            user_id = payload.get("user_id")
                            session_id = payload.get("session_id")

                            if not user_id or not session_id:
                                appLogger.error(
                                    f"Cannot run tango session summary for job {job_id}: user_id or session_id missing.")
                                return job_id, "failed"

                            print(
                                f"Starting tango session summary for job {job_id}, User ID: {user_id}, Session ID: {session_id}")

                            # Call tango_session_summary
                            tango_session_summary(
                                user_id=user_id, session_id=session_id)
                            print(
                                f"Tango session summary completed for job {job_id}, User ID: {user_id}, Session ID: {session_id}")

                        except Exception as e:
                            appLogger.error({
                                "event": "tango_session_summary_job_failed",
                                "error": str(e),
                                "traceback": traceback.format_exc(),
                                "job_id": job_id
                            })
                            print(
                                f"Error in tango session summary job {job_id}: {e}")
                            raise

                    elif job_type == "memory-refresh":
                        try:
                            user_id = payload.get("user_id")
                            session_id = payload.get("session_id")

                            if not user_id or not session_id:
                                appLogger.error(
                                    f"Cannot run memory refresh for job {job_id}: user_id or session_id missing.")
                                return job_id, "failed"

                            print(
                                f"Starting memory refresh for job {job_id}, User ID: {user_id}, Session ID: {session_id}")

                            # Create TangoMem instance and call refresh_memory_session
                            tango_mem = TangoMem(user_id)
                            tango_mem.refresh_memory_session(session_id)
                            print(
                                f"Memory refresh completed for job {job_id}, User ID: {user_id}, Session ID: {session_id}")

                        except Exception as e:
                            appLogger.error({
                                "event": "memory_refresh_job_failed",
                                "error": str(e),
                                "traceback": traceback.format_exc(),
                                "job_id": job_id
                            })
                            print(f"Error in memory refresh job {job_id}: {e}")
                            raise

                    elif job_type == "rl-xgboost-training":
                        print("--debug here------", job_type)
                        try:
                            tenant_id = job["tenant_id"]
                            print(
                                f"Starting RL XGBoost training for job {job_id}, Tenant ID: {tenant_id}")

                            start_training(tenant_id=tenant_id)
                            print(
                                f"RL XGBoost training completed for job {job_id}, Tenant ID: {tenant_id}")

                        except Exception as e:
                            print(
                                f"Error in RL XGBoost training job {job_id}: {e}")
                            appLogger.error({"event": "rl_xgboost_training_job_failed", "error": str(
                                e), "traceback": traceback.format_exc(), "job_id": job_id})
                            raise

                    elif job_type == "project-status-alert":
                        print("--debug here------", job_type)
                        try:
                            tenant_id = job["tenant_id"]
                            print(f"Starting project status alert for job {job_id}, Tenant ID: {tenant_id}")
                            
                            alert_service = AlertCreator(tenant_id=tenant_id)
                            # alert_service.generate_alerts()
                            alert_service.generate_alerts2()
                            print(f"Project status alert completed for job {job_id}, Tenant ID: {tenant_id}")
                            
                        except Exception as e:
                            print(f"Error in project status alert job {job_id}: {e}")
                            appLogger.error({"event": "project_status_alert_job_failed","error": str(e),"traceback": traceback.format_exc(),"job_id": job_id,'tenant_id': tenant_id})
                            raise

                    elif job_type in ["emails:fy27-demand-kickoff", "emails:fy27-zero-demand-nudge"]:
                        print("--debug here------", job_type)
                        try:
                            tenant_id = job["tenant_id"]
                            print(f"Starting {job_type} for job {job_id}, Tenant ID: {tenant_id}")
                            alert_service = AlertCreator(tenant_id=tenant_id)
                            alert_service.generate_demand_alerts_seagate(job_type=job_type)
                            print(f"{job_type} completed for job {job_id}, Tenant ID: {tenant_id}")
                        except Exception as e:
                            print(f"Error in {job_type} job {job_id} {job_type}: {e}")
                            appLogger.error({"event": "project_status_alert_job_failed","error": str(e),"traceback": traceback.format_exc(),"job_id": job_id, "job_type": job_type,'tenant_id': tenant_id})
                            raise


                    elif job_type == "email-trigger":
                        print("--debug here1111111111111111111------", job_type)
                        try:
                            tenant_id = job["tenant_id"]
                            user_id = payload.get('user_id')
                            project_id = payload.get('project_id')
                            print(f"Starting {job_type} for job {job_id}, Tenant ID: {tenant_id}, User: {user_id} & project: {project_id}")
                            
                            alert_service = AlertCreator(tenant_id=tenant_id)
                            alert_service._send_email(
                                user_id = payload.get('user_id'),
                                user_name = payload.get('user_name'),
                                user_email = payload.get('user_email'),
                                project_name = payload.get('project_name'),
                                update_message = payload.get('pending_text'),
                            )
                            print(f"Completed {job_type} for job {job_id}, Tenant ID: {tenant_id}, User: {user_id} & project: {project_id}")
                            
                        except Exception as e:
                            print(f"Error in email-trigger job {job_id}: {e}")
                            appLogger.error({"event": "email_trigger_job_failed","error": str(e),"traceback": traceback.format_exc(),"job_id": job_id,'tenant_id': tenant_id})
                            raise


                    
                    # Step 3: Mark done
                    self.jobDao.update_status(job_id, "done")
                    print(f"Completed job {job_id} ({job_type})")
                    return job_id, "done"

                except Exception as e:
                    appLogger.error({
                        "event": f"{job_type}_job_failed",
                        "error": str(e),
                        "traceback": traceback.format_exc()
                    })
                    self.jobDao.update_status(job_id, "failed")
                    print(f"Error processing {job_type} job {job_id}: {e}")
                    return job_id, "failed"

            # Process jobs in parallel using ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=self.batch_size) as executor:
                future_to_job = {executor.submit(
                    process_job, job): job for job in jobs}
                for future in as_completed(future_to_job):
                    job_id, status = future.result()
                    if status == "done":
                        processed_jobs.append(job_id)

                    # Update progress log
                    job = future_to_job[future]
                    payload = job["payload"]
                    run_id = payload["run_id"]
                    schedule_id = payload.get("schedule_id") or None
                    total = payload.get("total_count")
                    completed = self.jobDao.count_completed_jobs(run_id)

                    CronDao.update_progress(
                        schedule_id, f"Run {run_id} progress {completed}/{total}")

                    # If all done, update last_run_date
                    if completed == total and schedule_id:
                        CronDao.update_last_run(schedule_id, datetime.utcnow())
                        CronDao.update_progress(
                            schedule_id, f"Run {run_id} completed ✅")

            return jsonify({
                "message": f"{len(processed_jobs)} jobs processed this cycle",
                "jobs": processed_jobs
            }), 200

        except Exception as e:
            appLogger.error({
                "event": "v2Run_error",
                "error": str(e),
                "trace": traceback.format_exc()
            })
            return jsonify({"error": "Internal server error"}), 500


# create new job schedules for tenant only if they're not existing
# else for existing jobs it should update the status = 'pending' if the existing job entry's done_at is older than current date
# so that in phase2 while fetching all job status = 'pending' they will come & get processed.


    def model_training_scheduler(self, threshold=2):
        try:
            job_type = "rl-xgboost-training"
            current_date = datetime.now(timezone.utc)
            tenants = CommonDao.fetch_all_tenants()
            # print("--debug current_date-------", current_date)

            latest_jobs_query = f"""
                SELECT DISTINCT ON (tenant_id)
                id,tenant_id,done_at,status
                FROM cron_jobstracker
                WHERE job_type = '{job_type}'
                ORDER BY tenant_id, updated_at DESC;
            """
            latest_jobs = db_instance.retrieveSQLQueryOld(latest_jobs_query)
            jobs_map = {int(job["tenant_id"]): job for job in latest_jobs}
            print("model_training_scheduler  2", jobs_map)

            for tenant in tenants:
                tenant_id = int(tenant["id"])
                existing_job = jobs_map.get(tenant_id)

                if existing_job:
                    print("--debug existing_job---------", existing_job)
                    job_id = existing_job.get("id")
                    done_at_raw = existing_job.get("done_at") or None

                    if done_at_raw:
                        done_at = datetime.fromisoformat(done_at_raw)
                        diff_days = (current_date - done_at).days
                    else:
                        diff_days = threshold

                    # print("\n--debug existing_job 222---", done_at,diff_days)
                    # print(f"Found existing {job_type} entry for {tenant_id}, JobID: {job_id}, Days diff: {diff_days}")

                    if diff_days >= threshold and existing_job['status'] != 'pending':
                        print(
                            f"Updated {tenant_id} status to progress for {job_type}")
                        self.jobDao.update_status(
                            job_id=existing_job["id"], status="pending")
                        appLogger.info({"event": "model_training_scheduler", 'status': "updated",
                                       'job_id': job_id, 'tenant_id': tenant_id, "diff_days": diff_days})

                    # else: < threshold → do nothing
                    continue

                run_id = f"rl-xgboost-{tenant_id}-{current_date.strftime('%Y%m%d%H%M%S')}"
                payload = {
                    "job_type": job_type,
                    "run_id": run_id,
                    "total_count": 1
                }
                # users = TenantDao.FetchUsersOfTenant(tenant_id)
                users = CommonDao.fetch_all_tenant_users(tenant_id)
                if not users:
                    continue
                user_id = users[0]["user_id"]

                job_id = self.jobDao.create(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    schedule_id=None,
                    job_type="rl-xgboost-training",
                    payload=payload
                )
                appLogger.info({"event": "model_training_scheduler", 'status': "created",
                               'job_id': job_id, 'job_type': job_type, 'tenant_id': tenant_id})
                print(f"Enqueued RL training for tenant {tenant_id}")
        except Exception as e:
            print("error in model_training_scheduler---", e)   


    def project_status_alerts_service(self, threshold=1):
        try:
            job_type = "project-status-alert"
            current_date = datetime.now(timezone.utc)
            tenants = CommonDao.fetch_all_tenants()
            # print("--debug current_date-------", current_date)
        
            latest_jobs_query = f"""
                SELECT DISTINCT ON (tenant_id)
                id,tenant_id,done_at,status
                FROM cron_jobstracker
                WHERE job_type = '{job_type}'
                ORDER BY tenant_id, updated_at DESC;
            """
            latest_jobs = db_instance.retrieveSQLQueryOld(latest_jobs_query)
            jobs_map = {int(job["tenant_id"]): job for job in latest_jobs}
            print("project_status_alerts_service  2", jobs_map)

            for tenant in tenants:
                tenant_id = int(tenant["id"])
                existing_job = jobs_map.get(tenant_id)

                
                # if tenant_id not in [776,237,# 2]: #for dev ey and seagate qa and trmeric prod only
                if tenant_id not in PROJECT_ALERT_TENANTS:
                    continue

                if existing_job:
                    print("--debug existing_job---------", existing_job)
                    job_id = existing_job.get("id")
                    done_at_raw = existing_job.get("done_at") or None

                    if done_at_raw:
                        done_at = datetime.fromisoformat(done_at_raw)
                        diff_days = (current_date - done_at).days
                    else:
                        diff_days = threshold

                    # print("\n--debug existing_job 222---", done_at,diff_days)
                    # print(f"Found existing {job_type} entry for {tenant_id}, JobID: {job_id}, Days diff: {diff_days}")

                    if diff_days >= threshold and existing_job['status'] != 'pending':
                        print(f"Updated {tenant_id} status to progress for {job_type}")
                        self.jobDao.update_status(job_id=existing_job["id"],status="pending")
                        appLogger.info({"event":"project_status_alerts_service",'status':"updated",'job_id':job_id,'tenant_id':tenant_id, "diff_days": diff_days})

                    # else: < threshold → do nothing
                    continue
                
                run_id = f"project-status-alert-{tenant_id}-{current_date.strftime('%Y%m%d%H%M%S')}"
                payload = {
                    "job_type": job_type,
                    "run_id": run_id,
                    "total_count": 1
                }
                # users = TenantDao.FetchUsersOfTenant(tenant_id)
                users = CommonDao.fetch_all_tenant_users(tenant_id)
                if not users:
                    continue
                user_id = users[0]["user_id"]

                job_id = self.jobDao.create(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    schedule_id=None,
                    job_type=job_type,
                    payload=payload
                )
                appLogger.info({"event":"project_status_alerts_service",'status':"created",'job_id':job_id,'job_type': job_type,'tenant_id':tenant_id})
                print(f"Enqueued project status alerts for tenant {tenant_id}")
        except Exception as e:
            appLogger.error({"event": "project_status_alerts_service","error": str(e),"traceback": traceback.format_exc()})
            print("error in project_status_alerts_service---", e)  
            

    def daily_digest_update(self, threshold=1):
        try:
            job_type = "daily_digest"
            current_date = datetime.now(timezone.utc)
            tenants = CommonDao.fetch_all_tenants()
        
            latest_jobs_query = f"""
                SELECT DISTINCT ON (tenant_id)
                id,tenant_id,done_at,status
                FROM cron_jobstracker
                WHERE job_type = '{job_type}'
                ORDER BY tenant_id, updated_at DESC;
            """
            latest_jobs = db_instance.retrieveSQLQueryOld(latest_jobs_query)
            jobs_map = {int(job["tenant_id"]): job for job in latest_jobs}
            # print("daily_digest_update  2", jobs_map)

            for tenant in tenants:
                tenant_id = int(tenant["id"])
                existing_job = jobs_map.get(tenant_id)
                
                if tenant_id not in DAILY_DIGEST_TENANTS:
                    continue

                if existing_job:
                    # print("--debug existing_job---------", existing_job)
                    job_id = existing_job.get("id")
                    done_at_raw = existing_job.get("done_at") or None

                    if done_at_raw:
                        done_at = datetime.fromisoformat(done_at_raw)
                        diff_days = (current_date - done_at).days
                    else:
                        diff_days = threshold

                    # print("\n--debug existing_job 222---", done_at,diff_days)
                    # print(f"Found existing {job_type} entry for {tenant_id}, JobID: {job_id}, Days diff: {diff_days}")

                    if diff_days >= threshold and existing_job['status'] != 'pending':
                        print(f"Updated {tenant_id} status to progress for {job_type}")
                        self.jobDao.update_status(job_id=existing_job["id"],status="pending")
                        appLogger.info({"event":"daily_digest_update",'status':"updated",'job_id':job_id,'tenant_id':tenant_id, "diff_days": diff_days})
                    continue
                
                run_id = f"daily_digest_update-{tenant_id}-{current_date.strftime('%Y%m%d%H%M%S')}"
                users = CommonDao.fetch_all_tenant_users(tenant_id)
                if not users:
                    continue
                user_id = users[0]["user_id"]
                payload = {
                    "job_type": job_type,
                    "run_id": run_id,
                    "total_count": 1,
                    "tenant_id": tenant_id,
                    "user_id": user_id
                }

                job_id = self.jobDao.create(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    schedule_id=None,
                    job_type=job_type,
                    payload=payload
                )
                appLogger.info({"event":"daily_digest_update",'status':"created",'job_id':job_id,'job_type': job_type,'tenant_id':tenant_id})
                print(f"Enqueued project status alerts for tenant {tenant_id}")
        except Exception as e:
            appLogger.error({"event": "daily_digest_update","error": str(e),"traceback": traceback.format_exc()})
            print("error in daily_digest_update---", e)  
            
            

    def _run_scheduled_job(self, job_type: str):
        cfg = JOB_CONFIGS[job_type]
        threshold       = cfg["threshold"]
        allowed         = cfg["allowed_tenants"]
        run_id_prefix   = cfg["run_id_prefix"]

        try:
            current_date = datetime.now(timezone.utc)
            tenants      = CommonDao.fetch_all_tenants()

            latest_jobs = db_instance.retrieveSQLQueryOld(f"""
                SELECT DISTINCT ON (tenant_id) id, tenant_id, done_at, status
                FROM cron_jobstracker
                WHERE job_type = '{job_type}'
                ORDER BY tenant_id, updated_at DESC;
            """)
            jobs_map = {int(j["tenant_id"]): j for j in latest_jobs}

            for tenant in tenants:
                tenant_id = int(tenant["id"])

                if allowed is not None and tenant_id not in allowed:
                    continue

                existing_job = jobs_map.get(tenant_id)

                if existing_job:
                    job_id      = existing_job["id"]
                    done_at_raw = existing_job.get("done_at")
                    diff_days   = (
                        (current_date - datetime.fromisoformat(done_at_raw)).days
                        if done_at_raw else threshold
                    )

                    if diff_days >= threshold and existing_job["status"] != "pending":
                        self.jobDao.update_status(job_id=job_id, status="pending")
                        appLogger.info({
                            "event": f"{job_type}_scheduler", "status": "updated",
                            "job_id": job_id, "tenant_id": tenant_id, "diff_days": diff_days
                        })
                    continue   # existing entry handled — skip creation

                # ── No existing job: create one ──────────────────────────────────
                users = CommonDao.fetch_all_tenant_users(tenant_id)
                if not users:
                    continue
                user_id = users[0]["user_id"]

                run_id  = f"{run_id_prefix}-{tenant_id}-{current_date.strftime('%Y%m%d%H%M%S')}"
                payload = {
                    "job_type":    job_type,
                    "run_id":      run_id,
                    "total_count": 1,
                    "tenant_id":   tenant_id,
                    "user_id":     user_id,
                }

                job_id = self.jobDao.create(
                    tenant_id=tenant_id, user_id=user_id,
                    schedule_id=None, job_type=job_type, payload=payload
                )
                appLogger.info({
                    "event": f"{job_type}_scheduler", "status": "created",
                    "job_id": job_id, "job_type": job_type, "tenant_id": tenant_id
                })
                print(f"Enqueued {job_type} for tenant {tenant_id}")

        except Exception as e:
            appLogger.error({
                "event": f"{job_type}_scheduler",
                "error": str(e), "traceback": traceback.format_exc()
            })
            print(f"error in {job_type} scheduler ---", e)
