from typing import Dict, Any, Generator, List
from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_utils.enums import AgentFnTypes, AgentReturnTypes
from src.trmeric_database.dao import TangoDao, IntegrationDao
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_ml.llm.models.OpenAIClient import ModelOptions
import json
import requests
import traceback
import re
import threading
from src.trmeric_services.agents.functions.onboarding.creation_tools.AutonomousCreateProject import AutomousProjectAgent
from src.trmeric_services.project.projectService import ProjectService
from src.trmeric_services.integration.IntegrationService import IntegrationService
from datetime import datetime
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
from src.trmeric_services.integration.Jira import Jira
from src.trmeric_services.integration.RefreshTokenService import RefreshTokenService
import pandas as pd
import os


def clean_text(text):
    """Clean text by replacing problematic characters."""
    if isinstance(text, str):
        # Replace non-ASCII characters
        text = re.sub(r'[^\x00-\x7F]+', ' ', text)
        text = text.replace('¬†', ' ').replace(
            '‚Äã', '')  # Replace specific artifacts
        return text.strip()
    return text


def organize_thought_process(data: dict) -> dict:
    """
    Takes a roadmap JSON dict with separate 'thought_process_behind_*' fields
    and consolidates them into a single 'thought_process' dict.
    """
    thought_process = {}

    for key in list(data.keys()):
        if key.startswith("thought_process_behind_"):
            # extract the field name after "thought_process_behind_"
            # new_key = key.replace("thought_process_behind_", "")
            thought_process[key] = data.pop(key)

    # add consolidated dict
    data["tango_analysis"] = thought_process
    return data


class JobProjectCreator:
    def __init__(self, tenant_id: str, user_id: str):
        """
        Initialize JobProjectCreator with tenant_id, user_id, and ProjectCreator instance.

        Args:
            tenant_id (str): Tenant identifier.
            user_id (str): User identifier.
            project_creator (Any): Instance of ProjectCreator for fetching and analyzing Jira items.
        """
        self.tenant_id = tenant_id
        self.user_id = user_id

        try:
            token = RefreshTokenService().refreshIntegrationAccessToken(
                tenant_id, user_id, "jira")
        except Exception as e:
            print("error ", e)
            token = {"access_token": ""}

        accessToken = token.get("access_token") or "" if token else ""
        # module = metadata.get("module") or None
        try:
            self.jira_instance = Jira(project_id="", accessToken=accessToken, metadata={
            }, tenant_id=tenant_id, user_id=user_id)
        except Exception as e:
            print("error in initiating jira instance", e)
            self.jira_instance = None
        self.input_file_path = "fy26q1_eligible_items.json"
        self.logInfo = {"tenant_id": tenant_id, "user_id": user_id}

    def process_eligible_items(self, session_state: Dict[str, Any] = None, mode='jira', file_name='') -> List[Dict[str, Any]]:
        created_mappings = []
        mapping_file = f"created_projects_mapping_{self.tenant_id}.json"

        # determine input file
        input_path = file_name.strip()

        # helper to load mapping (resume-safe)
        def _load_mapping():
            if os.path.exists(mapping_file):
                try:
                    with open(mapping_file, "r", encoding="utf-8") as mf:
                        return json.load(mf)
                except Exception as e:
                    appLogger.error({"event": "load_mapping_error", "error": str(
                        e), "traceback": traceback.format_exc()})
                    return {"initiatives": {}, "features": {}, "epics": {}}
            return {"initiatives": {}, "features": {}, "epics": {}}

        def _save_mapping(m):
            try:
                with open(mapping_file, "w", encoding="utf-8") as mf:
                    json.dump(m, mf, indent=2)
            except Exception as e:
                appLogger.error({"event": "save_mapping_error", "error": str(
                    e), "traceback": traceback.format_exc()})

        # safe loader for JSON input file
        try:
            with open(input_path, "r", encoding="utf-8") as f:
                hierarchy = json.load(f)
        except Exception as e:
            appLogger.error({"event": "process_eligible_items_load_error", "file": input_path, "error": str(
                e), "traceback": traceback.format_exc()})
            return []



        initiatives = []
        epics = []

        # Case 1: Initiative hierarchy
        if isinstance(hierarchy, dict) and "initiatives" in hierarchy:
            initiatives = hierarchy.get("initiatives", []) or []

        # Case 2: Epic export format
        elif isinstance(hierarchy, dict) and "epics" in hierarchy:
            epics = hierarchy.get("epics", []) or []

        # Case 3: Flat list
        elif isinstance(hierarchy, list):
            initiatives = []
            for item in hierarchy:
                if isinstance(item, dict) and "features" in item:
                    initiatives.append(item)
                else:
                    initiatives.append({
                        "key": item.get("key", "") if isinstance(item, dict) else "",
                        "summary": item.get("summary", "") if isinstance(item, dict) else "",
                        "features": [item] if isinstance(item, dict) else []
                    })

        else:
            appLogger.warning({
                "event": "process_eligible_items_unrecognized_format",
                "info": "input JSON not recognized"
            })
            return []


        # load resume-safe mapping
        mapping = _load_mapping()
        agent = AutomousProjectAgent()
        project_service = ProjectService()

        # iterate
        for init in initiatives:
            try:
                init_key = init.get("key", "")
                # if init_key == "KPDP-4617":
                #     pass
                # else:
                #     continue
                init_summary = clean_text(init.get("summary", "") or "")
                init_title = f"{init_key} - {init_summary}" if init_key else init_summary or "Untitled Initiative"

                print("looping through initiative ", init_title)
                # Create initiative as project if not yet created
                if init_key and init_key not in mapping.get("initiatives", {}):
                    try:
                        appLogger.info({"event": "creating_initiative_project",
                                       "initiative": init_key, "tenant": self.tenant_id})
                        analysis_data = json.dumps(init, indent=2, default=str)

                        print("creating program ", init_key, init_title)
                        # Generate project JSON via LLM ProjectService
                        project_result = project_service.createProjectV2(
                            tenant_id=self.tenant_id, project_name=init_title, project_description=analysis_data, is_provider=False, log_input=self.logInfo
                        )
                        project_result = organize_thought_process(
                            project_result)
                        print("created project program by llm ", init_key)

                        if not project_result:
                            appLogger.error(
                                {"event": "createProjectV2_empty", "initiative": init_key})
                        else:
                            # Ensure title forced
                            try:
                                project_result["title"] = init_title
                            except Exception:
                                project_result = {
                                    **project_result, "title": init_title}

                            project_result["plan_type"] = 1
                            # Create project in system
                            mapping_data = agent.only_request_creation(
                                request_data=project_result, tenantId=self.tenant_id, userId=self.user_id)
                            print(
                                "success fully create initiative program project ", init_key)

                    except Exception as e:
                        print("failed to fully create initiative program project ", e)
                        appLogger.error({"event": "initiative_process_error", "initiative": init_key, "error": str(
                            e), "traceback": traceback.format_exc()})
                else:
                    appLogger.info(
                        {"event": "initiative_skip", "initiative": init_key})

                # Now process features inside this initiative
                features = init.get("features", []) or []
                for feat in features:
                    try:
                        feature_key = feat.get(
                            "key", "") if isinstance(feat, dict) else ""
                        # if feature_key == "KPDP-12584":
                        #     pass
                        # else:
                        #     continue
                        feature_summary = clean_text(
                            feat.get("summary", "") if isinstance(feat, dict) else "")
                        feature_title = f"{feature_key} - {feature_summary}" if feature_key else feature_summary or "Untitled Feature"

                        print("looping feature ", feature_key)
                        if feature_key and feature_key in mapping.get("features", {}):
                            appLogger.info(
                                {"event": "feature_skip", "feature": feature_key})
                            continue

                        appLogger.info(
                            {"event": "creating_feature_project", "feature": feature_key})
                        analysis_data = json.dumps(feat, indent=2, default=str)
                        print("creating project feature by llm ", feature_key)
                        project_result = project_service.createProjectV2(
                            tenant_id=self.tenant_id, project_name=feature_title, project_description=analysis_data, is_provider=False, log_input=self.logInfo
                        )
                        project_result = organize_thought_process(
                            project_result)
                        print("created project feature by llm ", feature_key)

                        if not project_result:
                            appLogger.error(
                                {"event": "createProjectV2_empty_feature", "feature": feature_key})
                            continue

                        # Force title and set pm_id on teams
                        try:
                            project_result["title"] = feature_title
                        except Exception:
                            project_result = {
                                **project_result, "title": feature_title}

                        project_created_data = agent.only_request_creation(
                            request_data=project_result, tenantId=self.tenant_id, userId=self.user_id)

                        # print("project_created_data -- ", project_created_data)

                        if project_created_data and project_created_data.get("project_id"):
                            appLogger.info(
                                {"event": "feature_project_created", "feature": feature_key})

                            # Insert Integration mapping for feature
                            try:
                                user_config = IntegrationDao.fetchIntegrationUserConfigId(
                                    user_id=self.user_id, integration="jira")
                                user_config_id = None
                                if isinstance(user_config, list) and len(user_config) > 0:
                                    user_config_id = user_config[0].get(
                                        "id") or user_config[0].get("user_config_id")
                                elif isinstance(user_config, dict):
                                    user_config_id = user_config.get(
                                        "id") or user_config.get("user_config_id")
                                elif user_config:
                                    user_config_id = user_config

                                print("user config ",
                                      feature_key, user_config_id)

                                if user_config_id:
                                    metadata = {"key": feature_key, "name": feature_summary,
                                                "module": "feature_on_prem", "project_type": "scrum"}
                                    IntegrationDao.insertEntryToIntegrationProjectMapping(
                                        tenant_id=self.tenant_id,
                                        user_id=self.user_id,
                                        user_config_id=user_config_id,
                                        integration_project_identifier=feature_key,
                                        integration_type="jira",
                                        trmeric_project_id=project_created_data.get(
                                            "project_id"),
                                        metadata=json.dumps(metadata),
                                    )
                                    appLogger.info(
                                        {"event": "integration_mapping_inserted", "feature": feature_key})
                            except Exception as e:
                                appLogger.error({"event": "integration_mapping_error", "feature": feature_key, "error": str(
                                    e), "traceback": traceback.format_exc()})
                        else:
                            appLogger.error(
                                {"event": "feature_creation_failed", "feature": feature_key})

                    except Exception as e:
                        appLogger.error({"event": "feature_process_error", "feature": feat.get("key") if isinstance(
                            feat, dict) else None, "error": str(e), "traceback": traceback.format_exc()})

            except Exception as e:
                appLogger.error({"event": "initiative_outer_loop_error", "error": str(
                    e), "traceback": traceback.format_exc()})



        # epics = init.get("epics", []) or []
        for epic in epics:
            try:
                epic_key = epic.get("key", "") if isinstance(epic, dict) else ""
                epic_summary = clean_text(
                    epic.get("name", "") or epic.get("summary", "")
                ) if isinstance(epic, dict) else ""

                epic_title = (
                    f"{epic_key} - {epic_summary}"
                    if epic_key else epic_summary or "Untitled Epic"
                )

                print("looping epic", epic_key)

                # Skip if already mapped
                if epic_key and epic_key in mapping.get("epics", {}):
                    appLogger.info({"event": "epic_skip", "epic": epic_key})
                    continue

                appLogger.info({
                    "event": "creating_epic_project",
                    "epic": epic_key
                })

                analysis_data = json.dumps(epic, indent=2, default=str)

                print("creating project epic by llm", epic_key)

                project_result = project_service.createProjectV2(
                    tenant_id=self.tenant_id,
                    project_name=epic_title,
                    project_description=analysis_data,
                    is_provider=False,
                    log_input=self.logInfo
                )

                project_result = organize_thought_process(project_result)

                print("created project epic by llm", epic_key)

                if not project_result:
                    appLogger.error({
                        "event": "createProjectV2_empty_epic",
                        "epic": epic_key
                    })
                    continue

                # Force title
                try:
                    project_result["title"] = epic_title
                except Exception:
                    project_result = {**project_result, "title": epic_title}

                project_created_data = agent.only_request_creation(
                    request_data=project_result,
                    tenantId=self.tenant_id,
                    userId=self.user_id
                )

                if project_created_data and project_created_data.get("project_id"):
                    appLogger.info({
                        "event": "epic_project_created",
                        "epic": epic_key
                    })

                    # -------- Integration Mapping --------
                    try:
                        user_config = IntegrationDao.fetchIntegrationUserConfigId(
                            user_id=self.user_id,
                            integration="jira"
                        )

                        user_config_id = None
                        if isinstance(user_config, list) and user_config:
                            user_config_id = user_config[0].get("id") or user_config[0].get("user_config_id")
                        elif isinstance(user_config, dict):
                            user_config_id = user_config.get("id") or user_config.get("user_config_id")
                        elif user_config:
                            user_config_id = user_config

                        print("user config", epic_key, user_config_id)

                        if user_config_id:
                            metadata = {
                                "key": epic_key,
                                "name": epic_summary,
                                "module": "epic_on_prem",
                                "project_type": "scrum"
                            }

                            IntegrationDao.insertEntryToIntegrationProjectMapping(
                                tenant_id=self.tenant_id,
                                user_id=self.user_id,
                                user_config_id=user_config_id,
                                integration_project_identifier=epic_key,
                                integration_type="jira",
                                trmeric_project_id=project_created_data.get("project_id"),
                                metadata=json.dumps(metadata),
                            )

                            appLogger.info({
                                "event": "integration_mapping_inserted",
                                "epic": epic_key
                            })

                    except Exception as e:
                        appLogger.error({
                            "event": "integration_mapping_error",
                            "epic": epic_key,
                            "error": str(e),
                            "traceback": traceback.format_exc()
                        })

                else:
                    appLogger.error({
                        "event": "epic_creation_failed",
                        "epic": epic_key
                    })

            except Exception as e:
                appLogger.error({
                    "event": "epic_process_error",
                    "epic": epic.get("key") if isinstance(epic, dict) else None,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })

        # final save
        _save_mapping(mapping)
        appLogger.info({"event": "process_eligible_items_complete",
                       "tenant": self.tenant_id, "created_count": len(created_mappings)})
        return created_mappings

    def process_eligible_items_2(self, session_state: Dict[str, Any] = None, mode='jira', file_name='') -> List[Dict[str, Any]]:
        if mode == "sheet":
            return self.process_items_from_sheet(file_name)

        print("process_eligible_items start")
        results = []
        session_state = session_state or {}
        # # Step 1: Read the initiative JSON file
        initiative_file_path = "onprem_jira_full_hierarchy2.json"
        initiative_file_path = file_name.strip() or "onprem_jira_full_hierarchy2.json"
        try:
            with open(initiative_file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            appLogger.error({"function": "process_eligible_items", "tenant_id": self.tenant_id,
                            "user_id": self.user_id, "error": f"Input file {initiative_file_path} not found"})
            return [{"error": f"Input file {initiative_file_path} not found"}]
        except json.JSONDecodeError as e:
            appLogger.error({"function": "process_eligible_items", "tenant_id": self.tenant_id,
                            "user_id": self.user_id, "error": f"Invalid JSON in {self.input_file_path}: {str(e)}"})
            return [{"error": f"Invalid JSON in {self.input_file_path}: {str(e)}"}]

        eligible_initiatives = data.get("initiatives") or []
        create_initiative = True
        create_project = True
        print("process_eligible_items_2 initiatives length -- ",
              len(eligible_initiatives))
        for initiative in eligible_initiatives:
            if create_initiative:
                name = initiative.get("key") + "  " + initiative.get("summary")
                description = {
                    "description": initiative.get("description"),
                    "total_features": initiative.get("total_features"),
                    "created_date": initiative.get("created_date"),
                    "portfolio": "CDTS"
                }
                print("creating initiative project ", name)
                project_result = ProjectService().createProjectV2(tenant_id=self.tenant_id, project_name=name,
                                                                  project_description=description, is_provider=False, log_input=self.logInfo)
                # Process project result with AutomousProjectAgent
                project_result["plan_type"] = 1
                project_result["is_program"] = True
                mapping_data = AutomousProjectAgent().only_request_creation(
                    request_data=project_result, tenantId=self.tenant_id, userId=self.user_id)
                print("output ", mapping_data)

            # feats = initiative.get("features")
            # print("process_eligible_items_2 feats length -- ", len(feats))
            # for f in feats:
            #     if create_project:
            #         key = f.get("key")
            #         name = f.get("key") + "  " + f.get("summary")
            #         description = {"description": f.get("description"), "total_features": initiative.get(
            #             "total_features"), "created_date": initiative.get("created_date"), "portfolio": "CDTS"}
            #         print("creating project ", name)
                # project_result = ProjectService().createProjectV2(tenant_id=self.tenant_id, project_name=name,
                #                                                   project_description=description, is_provider=False, log_input=self.logInfo)
                # # Process project result with AutomousProjectAgent
                # mapping_data = AutomousProjectAgent().only_request_creation(
                #     request_data=project_result, tenantId=self.tenant_id, userId=self.user_id)
                # print("output ", mapping_data)
                # if mapping_data and mapping_data.get("project_id"):
                #     project_id = mapping_data.get("project_id")
                #     user_config_id = IntegrationDao.fetchIntegrationUserConfigId(
                #         user_id=self.user_id, integration="jira")
                #     metadata = {
                #         "key": key, "name": name, "module": "feature_on_prem", "project_type": "scrum"}

                #     # Insert integration project mapping
                #     IntegrationDao.insertEntryToIntegrationProjectMapping(
                #         tenant_id=self.tenant_id,
                #         user_id=self.user_id,
                #         user_config_id=user_config_id,
                #         integration_project_identifier=key,
                #         integration_type="jira",
                #         trmeric_project_id=project_id,
                #         metadata=json.dumps(metadata),
                #     )
                # break
            # break

            # latest_mapping_id = IntegrationDao.fetchLatestIntegrationMappingOfUser(
            #     user_id=self.user_id,
            #     integration="jira"
            # )

            # threading.Thread(target=IntegrationService().updateIntegrationDataV2, args=(
            #     project_id,
            #     self.tenant_id,
            #     self.user_id,
            #     latest_mapping_id
            # )).start()



        # -------- Epic Mode --------
        if isinstance(data, dict) and data.get("epics"):
            eligible_epics = data.get("epics") or []

            print("process_eligible_items_2 epics length -- ", len(eligible_epics))

            for epic in eligible_epics:
                try:
                    key = epic.get("key")
                    name = epic.get("name") or epic.get("summary") or key

                    if not key:
                        appLogger.error({
                            "function": "process_eligible_items_2",
                            "error": f"Missing key for epic: {epic}"
                        })
                        continue

                    project_name = f"{key}  {name}"

                    description = {
                        "jira_epic": epic,
                        "portfolio": "Sales"
                    }

                    print("creating epic project", project_name)

                    project_result = ProjectService().createProjectV2(
                        tenant_id=self.tenant_id,
                        project_name=project_name,
                        project_description=description,
                        is_provider=False,
                        log_input=self.logInfo
                    )

                    project_result["plan_type"] = 2

                    mapping_data = AutomousProjectAgent().only_request_creation(
                        request_data=project_result,
                        tenantId=self.tenant_id,
                        userId=self.user_id
                    )

                    if mapping_data and mapping_data.get("project_id"):
                        project_id = mapping_data.get("project_id")

                        # -------- Integration Mapping --------
                        user_config = IntegrationDao.fetchIntegrationUserConfigId(
                            user_id=self.user_id,
                            integration="jira"
                        )

                        user_config_id = None
                        if isinstance(user_config, list) and user_config:
                            user_config_id = user_config[0].get("id") or user_config[0].get("user_config_id")
                        elif isinstance(user_config, dict):
                            user_config_id = user_config.get("id") or user_config.get("user_config_id")
                        else:
                            user_config_id = user_config

                        if user_config_id:
                            metadata = {
                                "epics": [{
                                    "key": key,
                                    "name": name,
                                    "displayName": f"{key} ({name})"
                                }],
                                "module": "epic_on_prem",
                                "project_type": "scrum"
                            }

                            IntegrationDao.insertEntryToIntegrationProjectMapping(
                                tenant_id=self.tenant_id,
                                user_id=self.user_id,
                                user_config_id=user_config_id,
                                integration_project_identifier=key,
                                integration_type="jira",
                                trmeric_project_id=project_id,
                                metadata=json.dumps(metadata)
                            )

                        results.append({
                            "item_key": key,
                            "item_name": name,
                            "item_type": "epic",
                            "project_id": project_id,
                            "status": "success"
                        })

                    else:
                        results.append({
                            "item_key": key,
                            "item_name": name,
                            "item_type": "epic",
                            "error": "Project creation failed"
                        })

                except Exception as e:
                    appLogger.error({
                        "function": "process_eligible_items_2",
                        "item_key": epic.get("key"),
                        "error": str(e),
                        "traceback": traceback.format_exc()
                    })

            return results


        # eligible_initiatives = data.get("projects") or []
        # print(f"Processing {len(eligible_initiatives)} projects")
        # # Step 3: Process each initiative
        # for value in eligible_initiatives:
        #     key = value.get("key")
        #     name = value.get("name", key)
        #     print("proicessing ", key, name)
        #     if not key:
        #         appLogger.error({"function": "process_eligible_items", **self.logInfo, "error": f"Missing key for initiative: {key}"})
        #         results.append({"item_key": key or "unknown", "item_name": name, "error": "Missing key"})
        #         continue

        #     try:
        #         # Fetch and analyze epic using ProjectCreator
        #         item_input = {"key": key, "tag": "project", "name": name}
        #         analysis_result = self.jira_instance.fetchJiraProjectBasicInfo(key)
        #         # raise
        #         analysis_data = analysis_result

        #         # Create project
        #         project_result = ProjectService().createProjectV2(tenant_id=self.tenant_id, project_name=name, project_description=analysis_data, is_provider=False, log_input=self.logInfo)
        #         # project_result["plan_type"] = 4  # Unique plan type for initiatives
        #         appLogger.info({"function": "process_eligible_items", **self.logInfo, "item_key": key, "message": f"Project creation result: {project_result}"})

        #         # Process project result
        #         mapping_data = AutomousProjectAgent().only_request_creation(request_data=project_result, tenantId=self.tenant_id, userId=self.user_id)

        #         if mapping_data and mapping_data.get("project_id"):
        #             # project_id = mapping_data.get("project_id")
        #             # user_config_id = IntegrationDao.fetchIntegrationUserConfigId(
        #             #     user_id=self.user_id,
        #             #     integration="jira"
        #             # )
        #             # metadata = {
        #             #     "key": key,
        #             #     "name": name,
        #             #     "module": "v1",
        #             #     "resource": "bluvium",
        #             #     "project_type": "kanban"
        #             # }

        #             # # Insert integration project mapping
        #             # IntegrationDao.insertEntryToIntegrationProjectMapping(
        #             #     tenant_id=self.tenant_id,
        #             #     user_id=self.user_id,
        #             #     user_config_id=user_config_id,
        #             #     integration_project_identifier=key,
        #             #     integration_type="jira",
        #             #     trmeric_project_id=project_id,
        #             #     metadata=json.dumps(metadata)
        #             # )

        #             # latest_mapping_id = IntegrationDao.fetchLatestIntegrationMappingOfUser(
        #             #     user_id=self.user_id,
        #             #     integration="jira"
        #             # )

        #             # threading.Thread(target=IntegrationService().updateIntegrationDataV2, args=(
        #             #     project_id,
        #             #     self.tenant_id,
        #             #     self.user_id,
        #             #     latest_mapping_id
        #             # )).start()

        #             results.append({"item_key": key, "item_name": name, "item_type": "initiative", "project_id": project_id, "status": "success", "metadata": metadata})
        #         else:
        #             appLogger.error({"function": "process_eligible_items", **self.logInfo, "item_key": key, "error": f"Project creation failed: {mapping_data.get('error', 'No project_id returned')}"})
        #             results.append({"item_key": key, "item_name": name, "item_type": "initiative", "error": f"Project creation failed: {mapping_data.get('error', 'No project_id returned')}"})

        #     except Exception as e:
        #         appLogger.error({"function": "process_eligible_items", **self.logInfo, "item_key": key, "error": f"Error processing initiative {key}: {str(e)}", "traceback": traceback.format_exc()})
        #         results.append({"item_key": key, "item_name": name, "item_type": "initiative", "error": f"Error processing initiative: {str(e)}"})

        # return results

        # eligible_initiatives = data
        # print(f"Processing {len(eligible_initiatives)} initiatives")
        # # Step 3: Process each initiative
        # for key, value in eligible_initiatives.items():
        #     # key = initiative.get("key")
        #     name = value.get("issue_name", key)
        #     print("proicessing ", key, name)
        #     if not key:
        #         appLogger.error({
        #             "function": "process_eligible_items",
        #             **self.logInfo,
        #             "error": f"Missing key for initiative: {key}"
        #         })
        #         results.append({"item_key": key or "unknown", "item_name": name, "error": "Missing key"})
        #         continue

        #     try:
        #         # Fetch and analyze initiative
        #         # item_input = {"key": key, "tag": "initiative", "name": name}
        #         # analysis_result = self.jira_instance.fetch_and_analyze_kanban_item(item_input)
        #         # analysis_data = json.loads(analysis_result)
        #         # item_analysis = analysis_data.get("item_analysis", {})
        #         # item_data = item_analysis.get("data", {})

        #         # print(f"Fetched initiative: {key} ({name})")

        #         # item_data = value

        #         # Create project
        #         project_result = ProjectService().createProjectV2(
        #             tenant_id=self.tenant_id,
        #             project_name=name or "",
        #             project_description=value,
        #             is_provider=False,
        #             log_input=self.logInfo
        #         )
        #         # project_result["plan_type"] = 4  # Unique plan type for initiatives
        #         appLogger.info({
        #             "function": "process_eligible_items",
        #             **self.logInfo,
        #             "item_key": key,
        #             "message": f"Project creation result: {project_result}"
        #         })

        #         # Process project result
        #         mapping_data = AutomousProjectAgent().only_request_creation(
        #             request_data=project_result,
        #             tenantId=self.tenant_id,
        #             userId=self.user_id
        #         )

        #         if mapping_data and mapping_data.get("project_id"):
        #             project_id = mapping_data.get("project_id")
        #             user_config_id = IntegrationDao.fetchIntegrationUserConfigId(
        #                 user_id=self.user_id,
        #                 integration="jira"
        #             )
        #             metadata = {
        #                 "key": key,
        #                 "name": name,
        #                 "module": "v2",
        #                 "resource": "billcom"
        #             }

        #             # Insert integration project mapping
        #             IntegrationDao.insertEntryToIntegrationProjectMapping(
        #                 tenant_id=self.tenant_id,
        #                 user_id=self.user_id,
        #                 user_config_id=user_config_id,
        #                 integration_project_identifier=key,
        #                 integration_type="jira",
        #                 trmeric_project_id=project_id,
        #                 metadata=json.dumps(metadata)
        #             )

        #             latest_mapping_id = IntegrationDao.fetchLatestIntegrationMappingOfUser(
        #                 user_id=self.user_id,
        #                 integration="jira"
        #             )

        #             threading.Thread(target=IntegrationService().updateIntegrationDataV2, args=(
        #                 project_id,
        #                 self.tenant_id,
        #                 self.user_id,
        #                 latest_mapping_id
        #             )).start()

        #             results.append({
        #                 "item_key": key,
        #                 "item_name": name,
        #                 "item_type": "initiative",
        #                 "project_id": project_id,
        #                 "status": "success",
        #                 "metadata": metadata
        #             })
        #         else:
        #             appLogger.error({
        #                 "function": "process_eligible_items",
        #                 **self.logInfo,
        #                 "item_key": key,
        #                 "error": f"Project creation failed: {mapping_data.get('error', 'No project_id returned')}"
        #             })
        #             results.append({
        #                 "item_key": key,
        #                 "item_name": name,
        #                 "item_type": "initiative",
        #                 "error": f"Project creation failed: {mapping_data.get('error', 'No project_id returned')}"
        #             })

        #     except Exception as e:
        #         appLogger.error({
        #             "function": "process_eligible_items",
        #             **self.logInfo,
        #             "item_key": key,
        #             "error": f"Error processing initiative {key}: {str(e)}",
        #             "traceback": traceback.format_exc()
        #         })
        #         results.append({
        #             "item_key": key,
        #             "item_name": name,
        #             "item_type": "initiative",
        #             "error": f"Error processing initiative: {str(e)}"
        #         })

        # return results

        # # Step 2: Extract eligible epics and issues
        # eligible_epics = data.get("eligible_epics", [])
        # eligible_standalone_issues = data.get("issues", [])

        # print("eligible_epics ", len(eligible_epics))
        # print("eligible_standalone_issues ", len(eligible_standalone_issues))

        # # Step 3: Process each epic
        # counter = 0
        # to_select = 14
        # for epic in eligible_epics:
        #     # counter += 1
        #     # if counter <=3 :
        #     #     continue
        #     # if counter > to_select+1:
        #     #     break
        #     key = epic.get("key")
        #     name = epic.get("name", key)
        #     if not key:
        #         appLogger.error({
        #             "function": "process_eligible_items",
        #             "tenant_id": self.tenant_id,
        #             "user_id": self.user_id,
        #             "error": f"Missing key for epic: {epic}"
        #         })
        #         results.append({"item_key": key or "unknown", "item_name": name, "error": "Missing key"})
        #         continue

        #     try:
        #         # Fetch and analyze epic using ProjectCreator
        #         item_input = {"key": key, "tag": "epic", "name": name}
        #         analysis_result = self.jira_instance.fetch_and_analyze_kanban_item(item_input)
        #         analysis_data = json.loads(analysis_result)

        #         # Extract relevant data for project creation
        #         item_analysis = analysis_data.get("item_analysis", {})
        #         item_data = item_analysis.get("data", {})

        #         print("fetched for ", key, name)
        #         # Create project using ProjectService
        #         project_result = ProjectService().createProjectV2(
        #             tenant_id=self.tenant_id,
        #             project_name=name or "",
        #             project_description=item_data,
        #             is_provider=False,
        #             log_input=self.logInfo
        #         )

        #         project_result["plan_type"] = 2
        #         appLogger.info({
        #             "function": "process_eligible_items",
        #             "tenant_id": self.tenant_id,
        #             "user_id": self.user_id,
        #             "item_key": key,
        #             "message": f"Project creation result: {project_result}"
        #         })

        #         # Process project result with AutomousProjectAgent
        #         mapping_data = AutomousProjectAgent().only_request_creation(
        #             request_data=project_result,
        #             tenantId=self.tenant_id,
        #             userId=self.user_id
        #         )

        #         if mapping_data and mapping_data.get("project_id"):
        #             project_id = mapping_data.get("project_id")
        #             draft_key = key

        #             # Fetch user config ID for Jira integration
        #             user_config_id = IntegrationDao.fetchIntegrationUserConfigId(
        #                 user_id=self.user_id,
        #                 integration="jira"
        #             )
        #             metadata = {
        #                 "epics": [{
        #                     "key": draft_key,
        #                     "name": name,
        #                     "displayName": f"{draft_key} ({name})"
        #                 }],
        #                 "issues": [],
        #                 "module": "v4",
        #                 "resource": session_state.get("selectd_resource_name", self.jira_instance.resources.get("name", "billcom")),
        #                 "project_type": "scrum"
        #             }

        #             # Insert integration project mapping
        #             IntegrationDao.insertEntryToIntegrationProjectMapping(
        #                 tenant_id=self.tenant_id,
        #                 user_id=self.user_id,
        #                 user_config_id=user_config_id,
        #                 integration_project_identifier=draft_key,
        #                 integration_type="jira",
        #                 trmeric_project_id=project_id,
        #                 metadata=json.dumps(metadata)
        #             )

        #             latest_mapping_id = IntegrationDao.fetchLatestIntegrationMappingOfUser(
        #                 user_id=self.user_id,
        #                 integration='jira'
        #             )

        #             threading.Thread(target=IntegrationService().updateIntegrationDataV2, args=(
        #                 project_id,
        #                 self.tenant_id,
        #                 self.user_id,
        #                 latest_mapping_id
        #             )).start()

        #             results.append({
        #                 "item_key": key,
        #                 "item_name": name,
        #                 "item_type": "epic",
        #                 "project_id": project_id,
        #                 "status": "success",
        #                 "metadata": {
        #                     "module": "v1",
        #                     "resource": session_state.get("selectd_resource_name", self.jira_instance.resources.get("name", "billcom"))
        #                 }
        #             })
        #         else:
        #             appLogger.error({
        #                 "function": "process_eligible_items",
        #                 "tenant_id": self.tenant_id,
        #                 "user_id": self.user_id,
        #                 "item_key": key,
        #                 "error": f"Project creation failed: {mapping_data.get('error', 'No project_id returned')}"
        #             })
        #             results.append({
        #                 "item_key": key,
        #                 "item_name": name,
        #                 "item_type": "epic",
        #                 "error": f"Project creation failed: {mapping_data.get('error', 'No project_id returned')}"
        #             })

        #     except Exception as e:
        #         appLogger.error({
        #             "function": "process_eligible_items",
        #             "tenant_id": self.tenant_id,
        #             "user_id": self.user_id,
        #             "item_key": key,
        #             "error": f"Error processing epic {key}: {str(e)}",
        #             "traceback": traceback.format_exc()
        #         })
        #         results.append({
        #             "item_key": key,
        #             "item_name": name,
        #             "item_type": "epic",
        #             "error": f"Error processing epic: {str(e)}"
        #         })

        # counter = 0
        # # Step 4: Process each standalone issue
        # for issue in eligible_standalone_issues:
        #     # if counter >= 1:
        #     #     break
        #     counter += 1
        #     # if counter <=to_select :
        #     #     continue
        #     # if counter > to_select+1:
        #     #     break
        #     key = issue.get("key")
        #     name = issue.get("name", key)
        #     if not key:
        #         appLogger.error({"function": "process_eligible_items", "tenant_id": self.tenant_id, "user_id": self.user_id, "error": f"Missing key for issue: {issue}"})
        #         results.append({"item_key": key or "unknown", "item_name": name, "error": "Missing key"})
        #         continue

        #     try:
        #         # Fetch and analyze issue using ProjectCreator
        #         # item_input = {"key": key, "tag": "issue", "name": name}
        #         # analysis_result = self.jira_instance.fetch_and_analyze_kanban_item(item_input)
        #         # analysis_data = json.loads(analysis_result)

        #         # Extract relevant data for project creation
        #         # item_analysis = analysis_data.get("item_analysis", {})
        #         # item_data = item_analysis.get("data", {})

        #         # Create project using ProjectService
        #         project_result = ProjectService().createProjectV2(tenant_id=self.tenant_id, project_name=name or "", project_description=json.dumps(issue), is_provider=False, log_input=self.logInfo)
        #         project_result["plan_type"] = 3
        #         project_result["risk_list"] = []
        #         appLogger.info({"function": "process_eligible_items", "tenant_id": self.tenant_id, "user_id": self.user_id, "item_key": key, "message": f"Project creation result: {project_result}"})

        #         # Process project result with AutomousProjectAgent
        #         mapping_data = AutomousProjectAgent().only_request_creation(request_data=project_result, tenantId=self.tenant_id, userId=self.user_id)
        #         print("mapaing data -- project_id", mapping_data)

        #         if mapping_data and mapping_data.get("project_id"):
        #             project_id = mapping_data.get("project_id")
        #             draft_key = key

        #             # Fetch user config ID for Jira integration
        #             user_config_id = IntegrationDao.fetchIntegrationUserConfigId(user_id=self.user_id, integration="jira")
        #             print("user_config_id ", user_config_id)

        #             metadata = {"issues": [{"key": draft_key, "name": name, "displayName": f"{draft_key} ({name})"}], "epics": [], "module": "v5", "resource": "", "project_type": "kanban"}

        #             # Insert integration project mapping
        #             IntegrationDao.insertEntryToIntegrationProjectMapping(
        #                 tenant_id=self.tenant_id,
        #                 user_id=self.user_id,
        #                 user_config_id=user_config_id,
        #                 integration_project_identifier=draft_key,
        #                 integration_type="jira",
        #                 trmeric_project_id=project_id,
        #                 metadata=json.dumps(metadata),
        #             )

        #             latest_mapping_id = IntegrationDao.fetchLatestIntegrationMappingOfUser(user_id=self.user_id, integration='jira')

        #             threading.Thread(target=IntegrationService().updateIntegrationDataV2, args=(project_id, self.tenant_id, self.user_id, latest_mapping_id)).start()

        #             results.append(
        #                 {
        #                     "item_key": key,
        #                     "item_name": name,
        #                     "item_type": "issue",
        #                     "project_id": project_id,
        #                     "status": "success",
        #                     # "metadata": {
        #                     #     "module": "v2",
        #                     #     "resource": session_state.get("selectd_resource_name", self.jira_instance.resources.get("name", "billcom"))
        #                     # }
        #                 }
        #             )
        #         else:
        #             appLogger.error(
        #                 {
        #                     "function": "process_eligible_items",
        #                     "tenant_id": self.tenant_id,
        #                     "user_id": self.user_id,
        #                     "item_key": key,
        #                     "error": f"Project creation failed: {mapping_data.get('error', 'No project_id returned')}",
        #                 }
        #             )
        #             results.append({"item_key": key, "item_name": name, "item_type": "issue", "error": f"Project creation failed: {mapping_data.get('error', 'No project_id returned')}"})

        #     except Exception as e:
        #         appLogger.error(
        #             {
        #                 "function": "process_eligible_items",
        #                 "tenant_id": self.tenant_id,
        #                 "user_id": self.user_id,
        #                 "item_key": key,
        #                 "error": f"Error processing issue {key}: {str(e)}",
        #                 "traceback": traceback.format_exc(),
        #             }
        #         )
        #         results.append({"item_key": key, "item_name": name, "item_type": "issue", "error": f"Error processing issue: {str(e)}"})

        # return results



    def process_items_from_sheet(self, file_path='') -> List[Dict[str, Any]]:
        """
        Process projects from a spreadsheet file (e.g., Excel) row by row.

        Args:
            session_state (Dict[str, Any], optional): Session state with additional configuration.

        Returns:
            List[Dict[str, Any]]: List of results for each processed row, including success or error details.
        """
        results = []
        print("process item project-- job ", file_path)
        self.csv_file_path = file_path
        # Step 1: Load the CSV file
        try:
            df = pd.read_csv(self.csv_file_path, encoding='utf-8')
        except FileNotFoundError:
            appLogger.error({"function": "process_items_from_sheet", **self.logInfo,
                            "error": f"Input file {self.csv_file_path} not found"})
            return [{"error": f"Input file {self.csv_file_path} not found"}]
        except Exception as e:
            appLogger.error({"function": "process_items_from_sheet", **self.logInfo,
                            "error": f"Error reading {self.csv_file_path}: {str(e)}"})
            return [{"error": f"Error reading {self.csv_file_path}: {str(e)}"}]

        print(f"Processing {len(df)} rows from sheet")

        # 55, 379
        # Step 2: Process each row

        # curl -X POST https://production.tangotrmeric.com/trmeric_ai/project/auto_create_project -H "Content-Type: application/json" -d '{
        #     "tenant_id": "55",
        #     "user_id": "379",
        #     "mode": "sheet",
        #     "file_name": "projects_sheet.csv"
        # }'

        for index, row in df.iterrows():

            # issue_key = row.get('Issue key', '') or ''
            # summary = row.get('Summary')
            # description = row.get('Description', '')
            # portfolio = row.get('Termeric Portfolio', '')
            # roadmap_name = row.get('Roadmap Name', '')

            # Apply mappings
            project_type = row.get('Provisioning Type', '')
            # program = row.get('Program Name', '')
            # portfolio = row.get('Domain Abbreviation', '')
            desc = row.get('Request Description', '')
            proj_name = row.get('Project Name', '')
            start_date = row.get('Project Start Date', '')
            end_date = row.get('Project End Date', '')
            portfolio = row.get('Domain', '')

            # if "provisioned" in  project_type.lower():
            #     print("skipping row----------", project_type)
            #     continue

            # Combine summary and issue key for project name
            project_name = proj_name
            print("--debug proj_name0------", proj_name,
                  "\n\nportfolio--", portfolio)
            # if roadmap_name:
            #     project_name = f"{roadmap_name} - {issue_key}".strip()
            #     project_description = f"Summary: {summary} \n\n Description: {description} \n\n Portfolio - {portfolio} \n\n start date keep from last week and end date make it aug last "
            # else:
            #     project_name = f"{summary}".strip()
            #     project_description = f"Data: {row} for start date carefully check the data end date make it aug last "

            project_description = f"""Description: {desc} \n\n Portfolio - {portfolio} 
            \n\nStrictly keep the same start and end dates mentioned.
            Start Date : {start_date}
            \nEnd Date : {end_date}
            """
            project_description = clean_text(project_description)
            project_name = clean_text(project_name)

            print("creating project item ----- ",
                  project_name, project_description)

            try:
                project_result = ProjectService().createProjectV2(
                    tenant_id=self.tenant_id, project_name=project_name, project_description=project_description, is_provider=False, log_input=self.logInfo
                )
                print("project data created---summary ", project_name)

                # Special logic for provisioning type mapping
                if project_type.lower() in ['jira project', 'project']:
                    project_type = 'project'
                    project_result["plan_type"] = 2
                elif project_type.lower() == 'program':
                    project_type = 'program'
                    project_result["plan_type"] = 1
                elif project_type.lower() == 'small project':
                    project_type = 'enhancement'
                    project_result["plan_type"] = 3

                # Process project result with AutomousProjectAgent
                mapping_data = AutomousProjectAgent().only_request_creation(
                    request_data=project_result, tenantId=self.tenant_id, userId=self.user_id)

                results.append(f"Name- {project_name} created")
                print("\n\n\n------debug results------", results)

            except Exception as e:
                appLogger.error(
                    {
                        "function": "process_items_from_sheet",
                        **self.logInfo,
                        # "item_key": issue_key,
                        "error": f"Error processing row: {str(e)}",
                        # "error": f"Error processing row {index} with key {issue_key}: {str(e)}",
                        "traceback": traceback.format_exc(),
                    }
                )
                results.append(
                    {
                        # "item_key": issue_key,
                        "project_type": project_type,
                        "item_name": project_name,
                        "item_type": "sheet_project",
                        "error": f"Error processing row: {str(e)}",
                    }
                )

        return results
