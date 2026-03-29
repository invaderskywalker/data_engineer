from src.trmeric_database.dao import ProjectsDao, TangoDao, RoadmapDao
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_utils.json_parser import *
from .caching_users import CachingUsers
from src.trmeric_services.tango.functions.integrations.internal.GetIntegrationData import get_jira_data, get_smartsheet_data
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
from src.trmeric_services.summarizer.SummarizerService import SummarizerService
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from .review_prompt import *
from datetime import datetime, date, timedelta
from src.trmeric_database.Database import db_instance
from datetime import datetime, timedelta, timezone
from src.trmeric_services.integration.IntegrationService import IntegrationService



class PortfolioReview:
    def __init__(self, tenant_id, user_id, init=True):
        print("init PortfolioReview", tenant_id, user_id)

        self.tenant_id = tenant_id
        self.user_id = user_id
        self.data = None
        self.init = init
        self.llm = ChatGPTClient(self.user_id, self.tenant_id)
        self.modelOptions = ModelOptions(
            model="gpt-4.1",
            max_tokens=10000,
            temperature=0.1
        )
        self.dev_env = os.getenv("ENVIRONMENT") == "dev"
        # if init and not self.dev_env:
        
        # check = CachingUsers.checkUser(user_id)
        # print("check ", os.getenv("ENVIRONMENT"), user_id, check)
        # if (not check and self.dev_env and (tenant_id == "625" or tenant_id == 625) and (user_id == "436" or user_id == 436)):
        if init and not self.dev_env:
            # CachingUsers.addUser(user_id)
            
            
            try:
                # print("--debug running for ----", user_id, tenant_id)
                self.initializeData()
            except Exception as e:
                print("error ", e ,traceback.format_exc())
                    
            try:
                self.initializeArchivedData()
            except Exception as e:
                print("error ", e ,traceback.format_exc())
        
                
            try:
                self.initializeRoadmapData()
            except Exception as e:
                print("error ", e ,traceback.format_exc())
                
        print("leaving ", user_id)
        
            
            
    #for Ongoing projects
    def initializeData(self):
        debugLogger.info(f"Portfolio Review Cache begin")
        projects = ProjectsDao.FetchAvailableProject(tenant_id=self.tenant_id, user_id=self.user_id)
        debugLogger.info(f"Portfolio Review Cache begin with : {projects}")
        items = ProjectsDao.getDataForPortfolioReview(projects)
        
        current_date = datetime.now().date()  # Get current date
        previous_date = (current_date - timedelta(days=14)).isoformat()  # Get n days before

        def process_item(item):
            try:
                project_id = item.get("project_id")
                debugLogger.info(f"Portfolio Review Cache {project_id}")
                if project_id is None:
                    return      
                if not self.checkIfInitializeData(project_id):
                    return
                
                debugLogger.info(f"Portfolio Progressing Review Cache {project_id}")
                
                project_datas = ProjectsDao.fetch_project_details_for_service_assurance(project_id=project_id)
                project_data = None
                if len(project_datas) > 0:
                    project_data = project_datas[0]
                if project_data is None:
                    return
                
                previous_week_status_updates = ProjectsDao.fetchStatusUpdatesBetweenTimes(
                    project_id=project_id, start_date=previous_date)
                risksData = ProjectsDao.fetchProjectsRisksV2([project_id])
                project_data["risk_and_mitigation"] = risksData
                # item["more_data"] = project_data
                integration_data = IntegrationService().fetchProjectDataforIntegration(tenant_id =self.tenant_id, project_id=project_id )
                new_summary = json.dumps(integration_data, indent=2)
                item["integration_info"] = new_summary
                
                milestone_data = ProjectsDao.fetchProjectMilestonesV2(project_id=project_id)
                current_project_status = ProjectsDao.fetchProjectLatestStatusUpdateV2(project_id)
                prompt = generatePortfolioReviewInsights(project_data, current_project_status, previous_week_status_updates, milestone_data, integration_data=integration_data)
                # print("prompt -- ", prompt.formatAsString())

                response = self.llm.run(
                    prompt,
                    self.modelOptions,
                    "PortfolioReviewCache::ongoing_projects",
                    logInDb={
                        "tenant_id": self.tenant_id,
                        "user_id": self.user_id
                    }
                )
                response_json = extract_json_after_llm(response)
                self.cacheDataForThisUser(project_id, response)
            except Exception as e:
                print("some error hapepend .,,., ", e, traceback.format_exc())

        max_workers = 4
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_item, item) for item in items]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    debugLogger.error(f"Error processing item: {e}")

        debugLogger.info("Portfolio Review Cache completed")

    def checkIfInitializeData(self, project_id, tag="ongoing"):
        debugLogger.info(f"Checking if should Initialize for project_id: {project_id}")
        cache_key = f"PROJECT_REVIEW_DATA_FOR_PROJECT_{project_id}"
        if tag == "archive":
            cache_key = f"PROJECT_REVIEW_DATA_FOR_ARCHIVED_PROJECT_{project_id}"
        
        existing_cache = TangoDao.fetchLatestTangoStatesTenant(self.tenant_id, cache_key)
        
        debugLogger.info(f"Checking existing cache should Initialize for project_id: {len(existing_cache)}")
        current_date = datetime.now().date()
        
        if existing_cache:
            latest_cache = existing_cache[0]
            cache_created_date = latest_cache.get("created_date")
            
            if cache_created_date:
                cache_datetime = datetime.fromisoformat(cache_created_date)
                now = datetime.now(timezone.utc)
                if cache_datetime.tzinfo is None:
                    cache_datetime = cache_datetime.replace(tzinfo=timezone.utc)
                cache_date = cache_datetime.date()
                if tag == "archive":
                    # For archive, check if cache is older than 7 days
                    if cache_date <= now - timedelta(days=7):
                        debugLogger.info(
                            f"Archive mode: Cache exists for project_id: {project_id}, key: {cache_key}, "
                            f"and is older than 7 days (created {cache_date}). Proceeding with initialization."
                        )
                        return True
                    else:
                        debugLogger.info(
                            f"Archive mode: Cache exists for project_id: {project_id}, key: {cache_key}, "
                            f"and is only { (current_date - cache_date).days } days old. Skipping initialization."
                        )
                        return False
                    
                # ---------------------------------
                # SPECIAL RULE: Tenant 227 (30 mins)
                # ---------------------------------
                if self.tenant_id == 227 and tag == "ongoing":
                    if cache_datetime <= now - timedelta(minutes=720):
                        debugLogger.info(
                            f"Tenant 227: Cache older than 3 hours for project_id {project_id}. Rebuilding."
                        )
                        return True
                    else:
                        debugLogger.info(
                            f"Tenant 227: Cache still fresh (<30 mins) for project_id {project_id}. Skipping."
                        )
                        return False
                    
                if cache_date == current_date:
                    debugLogger.info(
                        f"Cache already exists for project_id: {project_id}, key: {cache_key}, "
                        f"and was created today ({cache_date}). Skipping initialization."
                    )
                    return False
                else:
                    debugLogger.info(
                        f"Cache exists for project_id: {project_id}, key: {cache_key}, "
                        f"but is from {cache_date}, not today ({current_date}). Proceeding with initialization."
                    )
            else:
                debugLogger.warning(
                    f"Cache exists for project_id: {project_id}, key: {cache_key}, "
                    f"but created_date is missing. Proceeding with initialization."
                )
        
        debugLogger.info(
            f"No cache found for project_id: {project_id}, key: {cache_key}, "
            f"or cache is outdated. Proceeding with initialization."
        )
        return True


    def checkIfInitializeRoadmapData(self, roadmap_id):
        debugLogger.info(f"Checking if should Initialize for roamdap_id: {roadmap_id}")
        cache_key = f"PROJECT_REVIEW_DATA_FOR_ROADMAP_{roadmap_id}"
        
        existing_cache = TangoDao.fetchLatestTangoStatesTenant(self.tenant_id, cache_key)
        
        debugLogger.info(f"Checking existing cache should Initialize for roadmap_id: {len(existing_cache)}")
        current_date = datetime.now().date()
        
        if existing_cache:
            latest_cache = existing_cache[0]
            cache_created_date = latest_cache.get("created_date")
            
            if cache_created_date:
                cache_datetime = datetime.fromisoformat(cache_created_date)
                cache_date = cache_datetime.date()
                if cache_date == current_date:
                    debugLogger.info(
                        f"Cache already exists for roadmap_id: {roadmap_id}, key: {cache_key}, "
                        f"and was created today ({cache_date}). Skipping initialization."
                    )
                    return False
                else:
                    debugLogger.info(
                        f"Cache exists for roadmap_id: {roadmap_id}, key: {cache_key}, "
                        f"but is from {cache_date}, not today ({current_date}). Proceeding with initialization."
                    )
            else:
                debugLogger.warning(
                    f"Cache exists for roadmap_id: {roadmap_id}, key: {cache_key}, "
                    f"but created_date is missing. Proceeding with initialization."
                )
        
        debugLogger.info(
            f"No cache found for roadmap_id: {roadmap_id}, key: {cache_key}, "
            f"or cache is outdated. Proceeding with initialization."
        )
        return True


    def cacheDataForThisUser(self, project_id, project_json_data):
        TangoDao.insertTangoState(
            self.tenant_id,
            self.user_id,
            f"PROJECT_REVIEW_DATA_FOR_PROJECT_{project_id}",
            project_json_data,
            ""
        )

    #for Closed (Archived) projects
    def initializeArchivedData(self):
        debugLogger.info("Portfolio Review Cache (Archived) begin")
        projects = ProjectsDao.FetchArchivedProjects(tenant_id=self.tenant_id)
        debugLogger.info(f"Portfolio Review Cache (Archived) begin with: {projects}")
        items = ProjectsDao.getDataForPortfolioReviewArchived(projects)
    

        def process_item(item):
            project_id = item.get("project_id")
            debugLogger.info(f"Archived Portfolio Review Cache {project_id}")
            if project_id is None:
                return
            if not self.checkIfInitializeData(project_id, "archive"):
                return

            debugLogger.info(f"Archived Portfolio Progressing Review Cache {project_id}")

            project_data = ProjectsDao.fetchProjectDetailsForServiceAssuranceReview(project_id=project_id)
            if project_data is None:
                return

            all_status_updates = ProjectsDao.fetchAllStatusUpdates(project_id=project_id)
            risks_data = ProjectsDao.fetchProjectsRisksV2([project_id])
            project_data["risks_data"] = risks_data
            item["more_data"] = project_data

            milestone_data = ProjectsDao.fetchProjectMilestonesV2(project_id=project_id)
            current_project_status = ProjectsDao.fetchProjectLatestStatusUpdateV2(project_id)
            retro_data = ProjectsDao.getRetroAnalysisForProject(project_id)

            value_realization_data = db_instance.retrieveSQLQueryOld(f"""
                WITH parsed_json AS (
                    SELECT 
                        wpr.id               AS value_realization_id,
                        wpr.project_id,
                        (elem ->> 'id')::bigint   AS kpi_id,
                        elem ->> 'title'         AS key_result,
                        elem ->> 'baseline_value' AS baseline_value_raw,
                        elem ->> 'target_value'   AS planned_value_raw,
                        elem ->> 'actual_value'   AS achieved_value_raw,
                        elem -> 'key_learnings'   AS key_learnings
                    FROM workflow_projectvaluerealization wpr
                        , jsonb_array_elements(wpr.key_result_analysis::jsonb) elem
                    WHERE
                        wpr.tenant_id  = {self.tenant_id}
                        AND wpr.project_id = {project_id}
                        AND elem ->> 'id' IS NOT NULL
                    )
                    SELECT
                    p.title               AS project_title,
                    p.objectives          AS project_objectives,
                    kpi.name              AS kpi_name,
                    pj.key_result,
                    -- strip non-numeric characters, then cast
                    NULLIF(regexp_replace(pj.baseline_value_raw, '[^0-9\.]', '', 'g'), '')::numeric
                        /
                        CASE WHEN pj.baseline_value_raw LIKE '%\%%' THEN 100 ELSE 1 END
                        AS baseline_value,
                    NULLIF(regexp_replace(pj.planned_value_raw, '[^0-9\.]', '', 'g'), '')::numeric
                        /
                        CASE WHEN pj.planned_value_raw LIKE '%\%%' THEN 100 ELSE 1 END
                        AS planned_value,
                    NULLIF(regexp_replace(pj.achieved_value_raw, '[^0-9\.]', '', 'g'), '')::numeric
                        /
                        CASE WHEN pj.achieved_value_raw LIKE '%\%%' THEN 100 ELSE 1 END
                        AS achieved_value,
                    pj.key_learnings::jsonb AS key_learnings,
                    port.title             AS portfolio_title
                    FROM parsed_json pj
                    LEFT JOIN workflow_projectkpi       kpi  ON kpi.id = pj.kpi_id
                    LEFT JOIN workflow_project          p    ON p.id   = pj.project_id
                    LEFT JOIN workflow_projectportfolio pport ON p.id = pport.project_id
                    LEFT JOIN projects_portfolio        port ON pport.portfolio_id = port.id;

            """)

            prompt = generateArchivedProjectReviewInsights(
                item, all_status_updates, milestone_data, retro_data, value_realization_data
            )
            # print("prompt (archived) -- ", prompt.formatAsString())

            response = self.llm.run(
                prompt,
                self.modelOptions,
                "PortfolioReviewCache::archive_projects",
                logInDb={"tenant_id": self.tenant_id, "user_id": self.user_id}
            )
            print("response -- ", response)
            response_json = extract_json_after_llm(response)
            # self.cacheDataForThisUser(project_id, response)
            self.cacheArchivedDataForThisUser(project_id, response)

        max_workers = 4
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_item, item) for item in items]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    debugLogger.error(f"Error processing item: {e}")

        debugLogger.info("Portfolio Review Cache (Archived) completed")

    def cacheArchivedDataForThisUser(self, project_id, project_json_data):
        TangoDao.insertTangoState(
            self.tenant_id,
            self.user_id,
            f"PROJECT_REVIEW_DATA_FOR_ARCHIVED_PROJECT_{project_id}",
            project_json_data,
            ""
        )
        
    
    def cacheFutureDataForThisUser(self, project_id, project_json_data):
        TangoDao.insertTangoState(
            self.tenant_id,
            self.user_id,
            f"PROJECT_REVIEW_DATA_FOR_ROADMAP_{project_id}",
            project_json_data,
            ""
        )
        

    def fetchPortfolioReviewForProjects(self, project_ids, archived_ids, roadmap_ids):
        debugLogger.info(f"Fetching portfolio review data for projects: {project_ids}")
        if not project_ids:
            debugLogger.info("No project IDs provided. Returning empty result.")
            return {}
        
        print("length of data --- ", len(project_ids), len(archived_ids), len(roadmap_ids) )

        ongoing_cache_keys = [
            f"PROJECT_REVIEW_DATA_FOR_PROJECT_{pid}" for pid in project_ids
        ]
        
        archived_keys = [
            f"PROJECT_REVIEW_DATA_FOR_ARCHIVED_PROJECT_{pid}" for pid in archived_ids
        ]
        
        roamdap_cache_keys = [
            f"PROJECT_REVIEW_DATA_FOR_ROADMAP_{pid}" for pid in roadmap_ids
        ]
        
        # print("kongoing_cache_keyseys -- ", ongoing_cache_keys)
        # print("archived_keys -- ", archived_keys)
        # print("roamdap_cache_keys -- ", roamdap_cache_keys)
                
        results = TangoDao.fetchLatestTangoStatesTenantMultiple(ongoing_cache_keys)
        debugLogger.info(f"Fetched ongoing portfolio review data for {len(results)} projects")

        project_data = {}
        for record in results:
            key = record.get("key")
            project_id = key.replace("PROJECT_REVIEW_DATA_FOR_PROJECT_", "").replace("PROJECT_REVIEW_DATA_FOR_ROADMAP_", "")
            value = record.get("value")
            try:
                parsed_json = extract_json_after_llm(value)
                project_data[project_id] = parsed_json
            except Exception as e:
                debugLogger.error(f"Failed to parse JSON for project_id {project_id}, key {key}: {e}")
                project_data[project_id] = None


        results = TangoDao.fetchLatestTangoStatesTenantMultiple(archived_keys)
        debugLogger.info(f"Fetched archived portfolio review data for {len(results)} projects")
        

        archived_data = {}
        for record in results:
            key = record.get("key")
            project_id = key.replace("PROJECT_REVIEW_DATA_FOR_PROJECT_", "").replace("PROJECT_REVIEW_DATA_FOR_ROADMAP_", "").replace("PROJECT_REVIEW_DATA_FOR_ARCHIVED_PROJECT_", "")
            value = record.get("value")
            try:
                parsed_json = extract_json_after_llm(value)
                archived_data[project_id] = parsed_json
            except Exception as e:
                debugLogger.error(f"Failed to parse JSON for project_id {project_id}, key {key}: {e}")
                archived_data[project_id] = None

        
        results = TangoDao.fetchLatestTangoStatesTenantMultiple(roamdap_cache_keys)
        debugLogger.info(f"Fetched roadmap portfolio review data for {len(results)} projects")
        
        future_data = {}
        for record in results:
            key = record.get("key")
            project_id = key.replace("PROJECT_REVIEW_DATA_FOR_PROJECT_", "").replace("PROJECT_REVIEW_DATA_FOR_ROADMAP_", "")
            value = record.get("value")
            try:
                parsed_json = extract_json_after_llm(value)
                future_data[project_id] = parsed_json
            except Exception as e:
                debugLogger.error(f"Failed to parse JSON for project_id {project_id}, key {key}: {e}")
                future_data[project_id] = None

        debugLogger.info(f"Fetched portfolio review data for {len(archived_data)} projects")
        
        result = {
            "future": future_data,
            "ongoing": project_data,
            "archived": archived_data
        }
        
        
        return result
    
    #for Future projects
    def initializeRoadmapData(self):
        debugLogger.info("Portfolio Review Cache (Roadmap) begin")
        items = RoadmapDao.fetchRoadmapDetailsV2FOrPortfolioReview(tenant_id=self.tenant_id)

        def process_item(item):
            project_id = item.get("id")
            debugLogger.info(f"Archived Portfolio Review Cache {project_id}")
            if project_id is None:
                return
            if not self.checkIfInitializeRoadmapData(project_id):
                return

            debugLogger.info(f"Archived Portfolio Progressing Review Cache {project_id}")

            prompt = generateRoadmapsReviewInsights(
                item
            )
            # print("prompt (Roadmap) -- ", prompt.formatAsString())

            response = self.llm.run(
                prompt,
                self.modelOptions,
                "PortfolioReviewCache::roadmaps",
                logInDb={"tenant_id": self.tenant_id, "user_id": self.user_id}
            )
            # print("response -- ", response)
            response_json = extract_json_after_llm(response)
            self.cacheFutureDataForThisUser(project_id, response)

        max_workers = 4
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_item, item) for item in items]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    debugLogger.error(f"Error processing item: {e}")

        debugLogger.info("Portfolio Review Cache (Roadmap) completed")

