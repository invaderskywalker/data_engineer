
from src.trmeric_services.agents.functions.onboarding.creation_tools.AutonomousCreateProject import AutomousProjectAgent
from src.trmeric_services.project.projectService import ProjectService
from src.trmeric_services.journal.Activity import activity_log, detailed_activity
import traceback
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
import re
import requests, json
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.trmeric_database.dao import RoadmapDao, TenantDao, TenantDaoV2, CustomerDao, ProjectsDao
from src.trmeric_services.chat_service.utils import roadmapPersona, get_consolidated_persona_context_utils
from src.trmeric_services.chat_service.Prompts import ideationCanvasPromptTrucible
from src.trmeric_ml.llm.Types import ModelOptions, ChatCompletion
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_utils.json_parser import extract_json_after_llm
import pandas as pd
from src.trmeric_services.agents.apis.service_assurance import ServiceAssuranceApis
from src.trmeric_database.Database import db_instance
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.trmeric_services.agents.functions.graphql_v2.analysis.roadmap_inference import infer_roadmap
from src.trmeric_services.agents.functions.graphql_v2.utils.tenant_helper import is_knowledge_integrated
from src.trmeric_utils.constants.project_status import PROJECT_STATUS_TYPE_TO_CODE, PROJECT_STATUS_VALUE_TO_CODE




def clean_text(text):
    """Clean text by replacing problematic characters."""
    if isinstance(text, str):
        text = re.sub(r'[^\x00-\x7F]+', ' ', text)  # Replace non-ASCII characters
        text = text.replace('¬†', ' ').replace('‚Äã', '')  # Replace specific artifacts
        return text.strip()
    return text

from datetime import date, datetime

def create_project_mapping_prompt(project_names, project_mapping):
    """
    Create an LLM prompt to map project names to IDs using fuzzy matching.
    
    Args:
        project_names: List of project names to resolve
        project_mapping: List of dicts with 'id', 'title', and optionally 'portfolio'
    
    Returns:
        ChatCompletion prompt for LLM
    """
    
    # Format the available projects for the prompt
    available_projects = ""
    for project in project_mapping:
        portfolio_info = f" (Portfolio: {project.get('portfolio', 'N/A')})" if project.get('portfolio') else ""
        available_projects += f"- ID: {project['id']}, Title: \"{project['title']}\"{portfolio_info}\n"
    
    # Format the project names to resolve
    names_to_resolve = ""
    for i, name in enumerate(project_names, 1):
        names_to_resolve += f"{i}. \"{name}\"\n"
    
    system_prompt = f"""You are a project name resolution assistant. Your job is to match project names to their correct IDs from a list of available projects.

Available Projects:
{available_projects}

Project Names to Resolve:
{names_to_resolve}

Instructions:
1. For each project name, find the best matching project from the available list
2. Use fuzzy matching - handle variations in spelling, spacing, capitalization, abbreviations
3. Consider partial matches and common variations (e.g., "Project Alpha" matches "Alpha Project", "Proj Alpha", etc.)
4. If no reasonable match can be found, set the ID to null
5. Return a JSON array with the resolved IDs in the same order as the input names

Output Format:
{{
  "resolved_projects": [
    {{"project_name": "original name 1", "project_id": 123}},
    {{"project_name": "original name 2", "project_id": 456}},
    {{"project_name": "original name 3", "project_id": null}}
  ]
}}

Be generous with partial matches but conservative with uncertain matches. When in doubt, return null for the project_id."""

    return ChatCompletion(
        messages=[
            {"role": "system", "content": system_prompt}
        ]
    )

def resolve_project_names_to_ids(project_names, project_mapping, llm, model_options, log_info):
    """
    Use LLM to resolve a list of project names to their corresponding IDs.
    
    Args:
        project_names: List of unique project names to resolve
        project_mapping: List of dicts with project info from ProjectsDao
        llm: ChatGPTClient instance
        model_options: ModelOptions for LLM
        log_info: Logging context
    
    Returns:
        Dict mapping project_name -> project_id (or None if not found)
    """
    if not project_names:
        return {}
    
    try:
        prompt = create_project_mapping_prompt(project_names, project_mapping)
        response = llm.run(prompt, model_options, "resolve_project_names", log_info)
        
        # Parse the JSON response
        result_json = extract_json_after_llm(response)
        
        # Create the mapping dict
        name_to_id = {}
        if result_json and "resolved_projects" in result_json:
            for resolved in result_json["resolved_projects"]:
                name = resolved.get("project_name")
                project_id = resolved.get("project_id")
                if name:
                    name_to_id[name] = project_id
        
        return name_to_id
        
    except Exception as e:
        appLogger.error({
            "function": "resolve_project_names_to_ids",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "project_names": project_names
        })
        # Return empty mapping on error
        return {}

class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()  # Converts to 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM:SS'
        return super().default(obj)

DEFAULT_MODEL = "gpt-4.1"
DEFAULT_MAX_TOKENS = 15000
DEFAULT_TEMPERATURE = 0.1

PRIMARY_SKILLS = ["ERP", "Data & Analytics", "AI", "CRM", "Cloud & DevOps", "Infrastructure Management",
"Automation", "Integration", "Security", "Business Apps", "Project Management", "Quality Assurance",
"Business Analyst", "App Development", "UX","Other"
]


def group_resources_by_skills(resources):
    grouped_resources = {}
    # print("--debug group_resources_by_skills------", resources[:2])
    
    for resource in resources:
        # Ensure primary_skill and id exist in the resource
        if 'primary_skill' not in resource or 'id' not in resource:
            print(f"Warning: Skipping resource due to missing primary_skill or id: {resource}")
            continue
        
        primary_skill = resource['primary_skill']
        resource_id = resource['id']
        
        # Initialize the skill group if it doesn't exist
        if primary_skill not in grouped_resources:
            grouped_resources[primary_skill] = []
        
        # Only add the resource if its ID hasn't been seen for this primary_skill
        if all(r['id'] != resource_id for r in grouped_resources[primary_skill]):
            grouped_resources[primary_skill].append({
                'id': resource['id'],  # Include id to avoid downstream issues
                'name': f"{resource['first_name']} {resource['last_name']}",
                'role': resource['role'],
                'experience': resource['experience'],
                'availability': resource['availability_time'],
                'allocation': resource['allocation'],
                'skills': resource['skills'],
                'external': resource['is_external']
            })
    
    # Limit each group to 40 resources
    result = {primary_skill: group[:40] for primary_skill, group in grouped_resources.items()}
    # print("---debug skill_group-----", result)
    return result


# Skill group
SKILL_MAP = {
  "ERP": ["SAP (FI/CO, MM, SD, PP, HCM)","Oracle ERP (E-Business Suite, Fusion, NetSuite)","Microsoft Dynamics 365 Finance & Operations","ERP Implementation & Customization","ERP Reporting & Data Migration"],
  "Data & Analytics": ["Data Engineering (ETL, Data Pipelines, Warehousing)","Business Intelligence (Power BI, Tableau, Qlik)","Advanced Analytics & Forecasting","Big Data Platforms (Databricks, Hadoop, Spark)","Data Governance & Master Data Management"],
  "AI": ["Machine Learning (ML) Engineering","Natural Language Processing (NLP)","Computer Vision","Generative AI (LLMs, Prompt Engineering, Fine-tuning)","MLOps & Model Deployment"],
  "CRM": ["Salesforce (Sales, Service, Marketing Clouds)","Microsoft Dynamics 365 CRM","SAP Customer Experience (C4C, Hybris)","CRM Integration & Customization","CRM Analytics & Customer Journey Mapping"],
  "Cloud & DevOps": ["Cloud Platforms (AWS, Azure, GCP)","CI/CD & Release Management","Infrastructure as Code (Terraform, Ansible, ARM)","Containerization & Orchestration (Docker, Kubernetes)","Monitoring & Observability (Prometheus, Grafana, ELK)"],
  
  "Infrastructure Management": ["Network Administration (LAN, WAN, VPN, Firewalls)","Server & Storage Management","Virtualization (VMware, Hyper-V)","End-User Computing & Device Management","IT Service Management (ITIL, ServiceNow)"],
  "Automation": ["RPA (UiPath, Automation Anywhere, Blue Prism)","IT Process Automation (Ansible, Puppet, Chef)","Test Automation (Selenium, Cypress, Playwright)","Workflow Automation (Power Automate, Zapier)","Infrastructure Automation (Terraform, CloudFormation)"],
  "Integration": ["API Management (MuleSoft, Apigee, Kong)","ESB (Dell Boomi, TIBCO, IBM Integration Bus)","Event Streaming & Messaging (Kafka, RabbitMQ)","Cloud Integration (iPaaS, Azure Logic Apps)","B2B/EDI Integration"],
  "Security": ["Identity & Access Management (Okta, Azure AD, Ping)","Application Security (AppSec, DevSecOps)","Network & Infrastructure Security","Cloud Security & Compliance","Threat Detection & Incident Response (SIEM, SOC)"],
  "Business Apps": ["CPQ Platforms (Salesforce CPQ, Apttus, Oracle CPQ)","HR & HCM Apps (Workday, SuccessFactors)","Finance & Accounting Apps (BlackLine, Coupa)","Collaboration Apps (O365, Google Workspace)","Supply Chain & Procurement Apps"],
  "Project Management": ["Agile (Scrum, Kanban, SAFe)","Waterfall & Hybrid Methodologies","PM Tools (Jira, MS Project, Smartsheet)","Portfolio & Program Management (PPM)","Risk & Change Management"],
  
  "Quality Assurance": ["Manual Testing (Functional, Regression, UAT)","Test Automation Frameworks","Performance & Load Testing (JMeter, LoadRunner)","Security Testing","QA Tools & Management (TestRail, Zephyr)"],
  "Business Analyst": ["Requirements Gathering & Documentation","Process Modeling & Mapping (BPMN, Visio)","Functional Specification & User Stories","Data Analysis & Reporting","Domain-Specific BA (ERP, CRM, Finance, Supply Chain)"],
  "App Development": ["Frontend Development (React, Angular, Vue)","Backend Development (Java, .NET, Python, Node.js)","Mobile Development (iOS, Android, Flutter, React Native)","Full Stack Development","API & Microservices Development"],
  "UX": ["UX Research & User Testing","Wireframing & Prototyping (Figma, Sketch, XD)","Interaction Design","UI Development & Design Systems","Accessibility & Usability Standards"],
  "Other": [
    "Blockchain & Distributed Ledger Technology",
    "Internet of Things (IoT) Development & Integration",
    "Augmented Reality (AR) & Virtual Reality (VR) Development",
    "Low-Code/No-Code Platforms (OutSystems, Mendix, Appian)",
    "Geographic Information Systems (GIS) & Spatial Analysis",
    "Digital Twin Technology",
    "Quantum Computing Fundamentals",
    "Robotics & Embedded Systems",
    "Change Management & Organizational Transformation",
    "Sustainability & ESG (Environmental, Social, Governance) Analytics"
  ]
  
}

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

class Creator:
    def __init__(self, tenant_id: int, user_id: int):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.logInfo = {"tenant_id": tenant_id, "user_id": user_id}
        self.llm = ChatGPTClient(self.user_id, self.tenant_id)
        self.modelOptions = ModelOptions(
            model=DEFAULT_MODEL,
            max_tokens=DEFAULT_MAX_TOKENS,
            temperature=DEFAULT_TEMPERATURE
        )

    def project_updates_(self, updates_json):
        """Apply multiple project updates via HTTP API.

        Uses LLM to resolve project names to IDs as a preprocessing step, following the sheet_mapper_v2.py style.
        """
        # print("project_updates ",updates_json )
        # return
        results = []
        service = ServiceAssuranceApis()

        # Get project mapping for this tenant
        try:
            from src.trmeric_database.dao import ProjectsDao
            eligible_projects = ProjectsDao.FetchAvailableProject(tenant_id=self.tenant_id, user_id=self.user_id)
            project_mapping = ProjectsDao.fetchProjectIdTitleAndPortfolio(
                tenant_id=self.tenant_id,
                project_ids=eligible_projects
            )
        except Exception as e:
            appLogger.error({
                "function": "project_updates_mapping",
                "error": f"Failed to fetch project mapping: {str(e)}",
                "tenant_id": self.tenant_id,
            })
            return [{"status": "failed", "reason": f"Failed to fetch project mapping: {str(e)}"}]

        # Prepare LLM prompt context
        project_names = [(update.get("data") or {}).get("project_name") for update in updates_json if (update.get("data") or {}).get("project_name")]
        only_data = [update.get("data") or {} for update in updates_json]
        llm_context = {
            "project_names": project_names,
            "project_mapping": project_mapping,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "updates_json": only_data
        }
        user_prompt = f"""{json.dumps(llm_context)} . Output in proper JSON. """
        model_options = self.modelOptions
        system_prompt = """
            You are an expert assistant for normalizing project status updates.

            ### Rules:
            1. **Mapping to Status Types**
            - "Project health" updates → must update **scope** and **schedule**.
            - "Budget" updates → must update **spend**.

            2. **Update Values**
            - Map user-provided health terms (on_track, at_risk, compromised) into `update_value`:

            3. **Comments**
            - If the user provided a comment → keep it.
            - If no comment → auto-generate a short comment based on status:
                - on_track → "Project is progressing as planned."
                - amber → "Project requires attention, some risks identified."
                - red → "Project is in critical condition, immediate action required."

            4. **Output Format**
            - Always output valid JSON with this structure:
            ```json
            {
                "project_id": "",
                "project_name": "",
                "status_updates": [
                    {
                        "update_type": "scope | schedule | spend",
                        "update_value": "on_track | at_risk | compromised",
                        "comment": "string"
                    },...
                ]
            }
            ```
            5. General
                Do not invent updates for projects not mentioned.
                If input is unclear, still generate a JSON with an explanatory comment.
                Use correct mapping even if spelling or casing varies (e.g., "greeen" → green).
        """

        chat_completion = ChatCompletion(
            system=system_prompt,
            prev=[],
            user=user_prompt
        )
        result_json = []
        try:
            response = self.llm.run(
                chat_completion,
                model_options,
                'creator::project_name_mapping',
                logInDb={"tenant_id": self.tenant_id, "user_id": self.user_id}
            )
            print("creator up[date ..***", response)
            result_json = extract_json_after_llm(response)
            # name_to_id = {}
            # if result_json and "resolved_projects" in result_json:
            #     for resolved in result_json["resolved_projects"]:
            #         name = resolved.get("project_name")
            #         project_id = resolved.get("project_id")
            #         if name:
            #             name_to_id[name] = project_id
        except Exception as e:
            appLogger.error({
                "function": "project_updates_llm_resolution",
                "error": f"Failed to resolve project names with LLM: {str(e)}",
                "tenant_id": self.tenant_id,
            })
            name_to_id = {}
            

        # Process each update
        for update in result_json:
            print("creator up[date .. ]", update)
            # update = _update.get("")
            # return
            try:
                project_id = update.get("project_id")
                project_name = update.get("project_name")
                status_updates = update.get("status_updates", [])

                # Basic field presence check
                if not project_name:
                    results.append({
                        "project_name": project_name,
                        "status": "failed",
                        "reason": "Missing project_name",
                    })
                    continue

                # project_id = name_to_id.get(project_name)

                if project_id is None:
                    results.append({
                        "project_name": project_name,
                        "status": "failed",
                        "reason": f"Project '{project_name}' could not be resolved to a valid project ID",
                    })
                    continue

                # Check if there are any status_updates to process
                if not status_updates:
                    results.append({
                        "project_name": project_name,
                        "project_id": project_id,
                        "status": "skipped",
                        "reason": "No status updates found for this project"
                    })
                    continue

                # Iterate over status_updates for this project
                for status_update in status_updates:
                    status_type = status_update.get("status_type")  # int
                    status_value = status_update.get("status_value")  # int
                    comment = status_update.get("comment") or ""

                    payload = {
                        "tenant_id": self.tenant_id,
                        "user_id": self.user_id,
                        "type": int(status_type),
                        "value": int(status_value),
                        "comments": comment,
                        "actual_percentage": 0,
                    }

                    resp = service.update_status(project_id, payload)

                    if getattr(resp, "status_code", None) == 201:
                        results.append({
                            "project_name": project_name,
                            "project_id": project_id,
                            "status_type": status_type,
                            "status_value": status_value,
                            "status": "success"
                        })
                    else:
                        results.append({
                            "project_name": project_name,
                            "project_id": project_id,
                            "status_type": status_type,
                            "status_value": status_value,
                            "status": "failed",
                            "reason": f"HTTP {getattr(resp, 'status_code', 'unknown')}".strip(),
                        })
            except Exception as e:
                appLogger.error({
                    "function": "project_updates",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "tenant_id": self.tenant_id,
                })
                results.append({
                    "project_name": update.get("project_name"),
                    "status": "failed",
                    "reason": str(e),
                })
        return results
        
    
    def project_updates(self, updates_json):
        """Apply multiple project updates via HTTP API in batches of 10 with threading."""
        results = []
        service = ServiceAssuranceApis()
        print("updating project")

        # 1. Fetch project mapping once
        try:
            from src.trmeric_database.dao import ProjectsDao
            eligible_projects = ProjectsDao.FetchAvailableProject(
                tenant_id=self.tenant_id, user_id=self.user_id
            )
            project_mapping = ProjectsDao.fetchProjectIdTitleAndPortfolio(
                tenant_id=self.tenant_id, project_ids=eligible_projects
            )
        except Exception as e:
            appLogger.error({
                "function": "project_updates_mapping",
                "error": f"Failed to fetch project mapping: {str(e)}",
                "tenant_id": self.tenant_id,
            })
            return [{"status": "failed", "reason": f"Failed to fetch project mapping: {str(e)}"}]

        # 2. Worker function to process a single batch
        def process_batch(batch):
            # project_names = [(update.get("data") or {}).get("project_name") for update in batch if (update.get("data") or {}).get("project_name")]
            # only_data = [update.get("data") or {} for update in batch]
            # orig_data = [update.get("original_used_data") or {} for update in batch]
            # _data = [ (update.get("data") or {}) + (update.get("original_used_data") or {}) for update in batch ]
            _data = [
                {**(update.get("data") or {})}
                for update in batch
            ]

            project_names = [d.get("project_name") for d in _data if d.get("project_name")]
            print("project names ", project_names)
            llm_context = {
                "project_names": project_names,
                "project_mapping": project_mapping,
                "user_id": self.user_id,
                "tenant_id": self.tenant_id,
                "updates_json": _data,
            }

            # Send to LLM
            user_prompt = f"""{json.dumps(llm_context)} . Output in proper JSON."""
            model_options = self.modelOptions
            system_prompt = """
                You are an expert assistant for normalizing project status updates.

                ### Rules:
                1. **Mapping to Status Types**
                - "Project health" updates → must update **scope** and **schedule**.
                - "Budget" updates → must update **spend**. if something is present budget related then you should update spend too

                2. **Update Values**
                - Map user-provided health terms (on_track, at_risk, compromised) into `update_value`:

                3. **Comments**
                - If the user provided a comment → use it and create a sensible and meaningful sentence with all understanding of the data provided for this project.
                - If no comment → auto-generate a short comment based on status
                
                4. For scope also write actual percentage. if there is understanding of scope completion of the project
                
                Also see actual_data_used_from_sheet so that you understand what parts of data came from which col

                4. **Output Format**
                - Always output valid JSON with this structure:
                ```json
                {
                    "updates": [
                        {
                            "project_id": "",
                            "project_name": "",
                            "status_updates": [
                                {
                                    "update_type": "scope | schedule | spend",
                                    "update_value": "on_track | at_risk | compromised",
                                    "comment": "string", // a sensible and meaningful sentence
                                    "actual_percentage": <int>,
                                },...
                            ],
                        },...
                    ]
                }
                ```
                5. General
                    Do not invent updates for projects not mentioned.
                    If input is unclear, still generate a JSON with an explanatory comment.
                    Use correct mapping even if spelling or casing varies.
                    
                    
                Important--
                1. if for scope, schediule , or spend the data says No Spend, No tracking.. then do not create startus for that type. this is important so careful
            """

            

            try:
                chat_completion = ChatCompletion(system=system_prompt, prev=[], user=user_prompt)
                response = self.llm.run(
                    chat_completion,
                    model_options,
                    'creator::project_status_batch',
                    logInDb={"tenant_id": self.tenant_id, "user_id": self.user_id}
                )
                print("project_updates_llm_batch", response)
                res = extract_json_after_llm(response)
                batch_result = res.get("updates")
            except Exception as e:
                appLogger.error({
                    "function": "project_updates_llm_batch",
                    "error": str(e),
                    "tenant_id": self.tenant_id,
                })
                batch_result = []

            # 3. Apply results to API
            batch_results = []
            for update in batch_result:
                print("batch update -- ", update)
                try:
                    project_id = update.get("project_id")
                    project_name = update.get("project_name")
                    status_updates = update.get("status_updates", [])

                    if not project_name:
                        batch_results.append({
                            "project_name": project_name,
                            "status": "failed",
                            "reason": "Missing project_name",
                        })
                        continue

                    if project_id is None:
                        batch_results.append({
                            "project_name": project_name,
                            "status": "failed",
                            "reason": f"Could not resolve project '{project_name}'"
                        })
                        continue

                    if not status_updates:
                        batch_results.append({
                            "project_name": project_name,
                            "project_id": project_id,
                            "status": "skipped",
                            "reason": "No status updates found for this project"
                        })
                        continue

                    for status_update in status_updates:
                        status_type = status_update.get("update_type")
                        status_value = status_update.get("update_value")
                        comment = status_update.get("comment") or ""
                        actual_percentage = status_update.get("actual_percentage") or 0

                        _type = PROJECT_STATUS_TYPE_TO_CODE.get(status_type) or None
                        _value = PROJECT_STATUS_VALUE_TO_CODE.get(status_value) or None
                        if not _type  or not _value:
                            continue
                        
                        if _type is not 1:
                            actual_percentage = 0

                        payload = {
                            "tenant_id": self.tenant_id,
                            "user_id": self.user_id,
                            "type": _type,
                            "value": _value,
                            "comments": comment,
                            "actual_percentage": actual_percentage,
                        }

                        resp = service.update_status(project_id, payload)
                        print("resp", resp)
                        if getattr(resp, "status_code", None) == 201:
                            batch_results.append({
                                "project_name": project_name,
                                "project_id": project_id,
                                "status_type": status_type,
                                "status_value": status_value,
                                "status": "success"
                            })
                        else:
                            batch_results.append({
                                "project_name": project_name,
                                "project_id": project_id,
                                "status_type": status_type,
                                "status_value": status_value,
                                "status": "failed",
                                "reason": f"HTTP {getattr(resp, 'status_code', 'unknown')}".strip(),
                            })
                except Exception as e:
                    batch_results.append({
                        "project_name": update.get("project_name"),
                        "status": "failed",
                        "reason": str(e),
                    })

            return batch_results

        # 4. Threaded batching execution
        def batch_iterable(iterable, size=10):
            for i in range(0, len(iterable), size):
                yield iterable[i:i + size]

        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_batch, batch) for batch in batch_iterable(updates_json, 10)]
            for f in as_completed(futures):
                try:
                    results.extend(f.result())
                except Exception as e:
                    results.append({"status": "failed", "reason": str(e)})

        return results

     
    def create_project(self, item, additional_data, socket_id=None):
        results = []
        row_additional_data = additional_data or {}
        
        project_name = item.get("project_title") or ""
        project_description = clean_text(json.dumps(item))
        project_name = clean_text(project_name)
        
        # Prepare input data for activity logging
        input_data = {
            "mapped_sheet_data": item,
            "additional_data": row_additional_data,
            "project_name": project_name
        }
        
        try:
            project_result = ProjectService().createProjectV2(
                tenant_id=self.tenant_id,
                project_name=project_name,
                project_description=project_description,
                is_provider=False,
                log_input=self.logInfo
            )
            project_result = organize_thought_process(project_result)
            
            # Filter out portfolio == 0
            project_result["portfolio_list"] = [p for p in project_result.get("portfolio_list", []) if p.get("portfolio") != 0]


            print("project data created ", project_result)
            project_result["tango_analysis"]["creation_source"] = "trucible"
            if row_additional_data:
                project_result["tango_analysis"]["extra_fields_from_sheet"] = row_additional_data
                
            project_result["risk_list"] = []
            project_result["title"] = project_name
            project_result["ref_project_id"] = item.get("ref_project_id")

            # Process project result with AutomousProjectAgent
            mapping_data = AutomousProjectAgent().only_request_creation(
                request_data=project_result,
                tenantId=self.tenant_id,
                userId=self.user_id
            )
            
            # Check if the creation was actually successful
            if mapping_data and isinstance(mapping_data, dict) and mapping_data.get('status') != 'error':
                # SUCCESS: Log complete project creation transformation
                activity_log(
                    agent_or_workflow_name="trucible_project_creation",
                    input_data=input_data,  # Complete Excel sheet data used for creation
                    output_data=mapping_data.get("data", {}),  # Just the data field from the creation response
                    user_id=self.user_id,
                    tenant_id=self.tenant_id,
                    socket_id=socket_id,  # Pass socket_id from cronV2
                    description=f"Complete project creation from Excel data: {project_name}",
                    status="success",
                    metrics={
                        "creation_source": "trucible",
                        "has_additional_data": bool(row_additional_data),
                        "project_id": mapping_data.get("project_id")
                    }
                )
                results.append(f"Name- {project_name} created")
                print(f"SUCCESS: Project {project_name} created successfully")
            else:
                error_msg = mapping_data.get('message', 'Unknown error') if isinstance(mapping_data, dict) else 'Unknown error'
                # Log failed creation
                activity_log(
                    agent_or_workflow_name="trucible_project_creation",
                    input_data=input_data,
                    output_data={"error": error_msg},  # Simple error message
                    user_id=self.user_id,
                    tenant_id=self.tenant_id,
                    socket_id=socket_id,  # Pass socket_id from cronV2
                    description=f"Failed project creation from Excel data: {project_name}",
                    status="error",
                    metrics={"creation_source": "trucible", "error_type": "creation_failed"}
                )
                results.append(f"Name- {project_name} creation failed: {error_msg}")
                print(f"FAILED: Project {project_name} creation failed: {error_msg}")
            
            print("\n\n\n------debug results------", results)
            return results
        except Exception as e:  # Add 'as e' to capture the exception
            appLogger.error({
                "function": "creation_agent_project",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            results.append(f"Name- {project_name} creation failed")
            raise e
            
        # return results
    
    def create_roadmap(self, item, additional_data, original_used_data, socket_id=None):
        # prompt = combined_roadmap_creation_prompt()
        # cpc=None
        # okr=None
        # basic_info=None
        # roadmap_canvas = {}
        
        # stages = ["basic", "okr", "cpc"]
        res_message = ""
        
        # Prepare input data for activity logging
        input_data = {
            "mapped_sheet_data": item,
            # "additional_data": additional_data or {},
            "roadmap_title": item.get("roadmap_title", "")
        }
        
        try:
            from src.trmeric_services.roadmap.RoadmapService import RoadmapService
            roadmapService = RoadmapService()
            from src.trmeric_services.roadmap.Prompts import combined_roadmap_creation_prompt
            roadmapContext = roadmapPersona(tenant_id = self.tenant_id, user_id = self.user_id)
            org_strategy = roadmapContext.get("org_strategy", [])
            all_portfolios = RoadmapDao.fetchAllPortfolioOfTenant(tenant_id=self.tenant_id)
            internal_knowledge = roadmapContext.get("knowledge") or []
            tenantOrgInfo = CustomerDao.FetchCustomerOrgDetailInfo(self.tenant_id)[0]['org_info']
            all_roadmap_titles = RoadmapDao.FetchRoadmapNames(tenant_id=self.tenant_id)
            
            # Call roadmap inference to get pattern-based guidance
            inference_guidance = None
            graphname = is_knowledge_integrated(self.tenant_id)
            
            if graphname:
                try:
                    # Prepare minimal roadmap data for inference
                    roadmap_for_inference = {
                        "name": item.get("roadmap_title", ""),
                        "description": item.get("roadmap_description", ""),
                        "category": item.get("category", ""),
                        "objectives": item.get("objectives", ""),
                        "tenant_id": self.tenant_id
                    }
                    
                    appLogger.info({
                        "event": "create_roadmap_inference",
                        "tenant_id": self.tenant_id,
                        "roadmap_name": roadmap_for_inference.get("name"),
                        "graphname": graphname
                    })
                    
                    # Run inference to match against patterns
                    inference_result = infer_roadmap(
                        roadmap_data=roadmap_for_inference,
                        llm=self.llm,
                        graphname=graphname,
                        tenant_id=self.tenant_id
                    )
                    
                    # Extract guidance if successful
                    if inference_result.get("inference_status") == "success":
                        inference_guidance = {
                            "pattern_reference": inference_result.get("pattern_reference", {}),
                            "solution_guidance": inference_result.get("solution_guidance", ""),
                            "dimension_guidance": inference_result.get("dimension_guidance", {})
                        }
                        
                        appLogger.info({
                            "event": "create_roadmap_inference_success",
                            "tenant_id": self.tenant_id,
                            "pattern_id": inference_guidance["pattern_reference"].get("pattern_id"),
                            "roadmap_count": inference_guidance["pattern_reference"].get("roadmap_count", 0)
                        })
                    else:
                        appLogger.warning({
                            "event": "create_roadmap_inference_no_match",
                            "tenant_id": self.tenant_id,
                            "status": inference_result.get("inference_status")
                        })
                except Exception as inference_error:
                    appLogger.error({
                        "event": "create_roadmap_inference_error",
                        "tenant_id": self.tenant_id,
                        "error": str(inference_error),
                        "traceback": traceback.format_exc()
                    })
                    # Continue without inference guidance
                    inference_guidance = None
            else:
                appLogger.info({
                    "event": "create_roadmap_knowledge_not_integrated",
                    "tenant_id": self.tenant_id,
                    "using_default_flow": True
                })
            
            
            prompt = combined_roadmap_creation_prompt(
                json.dumps(item), 
                persona=None, 
                org_info=tenantOrgInfo, 
                org_strategy=org_strategy, 
                portfolios=all_portfolios, 
                internal_knowledge=internal_knowledge, 
                all_roadmap_titles=all_roadmap_titles, 
                demand_type=None,
                tenant_id = self.tenant_id,
                inference_guidance=inference_guidance
            )
            
            response = self.llm.run(
                prompt,
                self.modelOptions, 
                f'creator::roadmap', 
                logInDb=self.logInfo
            )
            print("response ----", response)
            
            
            res_json = extract_json_after_llm(response)
            output = organize_thought_process(res_json)
            
            transformed_kpi = [
                {"name": item["key_result"], "baseline_value": item["baseline_value"]}
                for item in res_json.get("key_results") or []
            ]
            
            business_unit_name = output["business_unit_name"]
            transformed_business_sponsors = [
                {
                    "sponsor_first_name": item.get("sponsor_first_name") or "",
                    "sponsor_last_name": item.get("sponsor_last_name") or "",
                    # "sponsor_role": item.get("sponsor_role") or "",
                    "bu_name": business_unit_name
                }
                for item in res_json.get("business_sponsors") or []
            ]
            
            solution_insights = roadmapService.creatDemandInsights(res_json,self.tenant_id,self.user_id)
            ####
            # roadmap_canvas["insights"] = solution_insights
            # print("response ----", json.dumps(output))
            
            output["tenant_id"] = self.tenant_id
            output["user_id"] = self.user_id
            output["kpi"] = transformed_kpi
            output["title"] = item.get("roadmap_title")
            output["ref_id"] = item.get("ref_id")
            output["rank"] = 0
            
            output["portfolio_business_data"] = transformed_business_sponsors
            output["tango_analysis"]["solution_insights"] = solution_insights
            output["tango_analysis"]["business_value_question"] = res_json.get("business_value_question") or ""
            del output["key_results"]
            
            import copy
            new_output = copy.deepcopy(output)

            
            output["tango_analysis"]["extra_data_from_sheet"] = additional_data or {}
            output["tango_analysis"]["original_used_data"] = original_used_data or {}
            output["tango_analysis"]["creation_source"] = "trucible"
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            print("json input to roadmap creation ", json.dumps(output, indent=2))
            import os
            self.create_roadmap_url = os.getenv("DJANGO_BACKEND_URL") + "api/roadmap/tango/create"
            
            response = requests.post(
                self.create_roadmap_url, 
                headers=headers, 
                json=output, 
                timeout=4
            )

            # Print the response (status code and content)
            print("Status Code:", response.status_code)
            
            if response.status_code == 201:
                json_ = response.json()
                print("Response JSON:", json_)
                res_message = f"""
                    Created Roadmap:
                    id: {(json_.get("data") or  {}).get("id")}, 
                    title: {(json_.get("data") or  {}).get("title")}
                """
                roadmapService.updateRoadmapCreationTrackUtility(
                    tenantID=self.tenant_id,
                    userID=self.user_id,
                    roadmap_id = (json_.get("data") or  {}).get("id"),
                    newly_completed_items=[
                        "roadmap_name_description",
                        "objective_orgStrategy_keyResult",
                        "constraints_portfolio_category"
                    ]
                )
                
                # SUCCESS: Log complete roadmap creation transformation
                activity_log(
                    agent_or_workflow_name="trucible_roadmap_creation",
                    input_data=input_data,  # Complete Excel sheet data used for creation
                    output_data=new_output,  # The complete roadmap data sent for creation
                    user_id=self.user_id,
                    tenant_id=self.tenant_id,
                    socket_id=socket_id,  # Pass socket_id from cronV2
                    description=f"Complete roadmap creation from Excel data: {input_data['roadmap_title']}",
                    status="success",
                    metrics={
                        "creation_source": "trucible",
                        "roadmap_id": (json_.get("data") or {}).get("id"),
                        "kpi_count": len(transformed_kpi)
                    }
                )
            else:
                print("Response Content:", response.text)
                res_message = f"Failed  to create Roadmap: {response.text}"
                
                # FAILURE: Log failed roadmap creation
                activity_log(
                    agent_or_workflow_name="trucible_roadmap_creation",
                    input_data=input_data,
                    output_data={"error": response.text, "status_code": response.status_code},  # Simple error info
                    user_id=self.user_id,
                    tenant_id=self.tenant_id,
                    socket_id=socket_id,  # Pass socket_id from cronV2
                    description=f"Failed roadmap creation from Excel data: {input_data['roadmap_title']}",
                    status="error",
                    metrics={
                        "creation_source": "trucible",
                        "error_type": "api_creation_failed",
                        "status_code": response.status_code
                    }
                )
            
            return res_message
        except Exception as e:
            raise e


    def resourceSkillMappingPrompt(self, batch) -> ChatCompletion:
        prompt = f"""
            You are an expert Resource planner, given an array of resources data where each entry is a json having resource's unique id,role and skills.
            Understanding their role & skills, you need to create a categorization for each one of them as their primary_skill and secondary_skill
            looking at the {SKILL_MAP}
            
            ##Input
            Batch resource data: {json.dumps(batch)}
            
            ##Output: Return in JSON format:
            ```json
            {{
                "resource_data": [
                    {{  
                        "id": "<integer, same as input>",
                        "role":"<same as input>",
                        "primary_skill_group": "",
                        "secondary_skill_group": ""
                    }}...
                ]
            }}
            ```
        """
        return ChatCompletion(system=prompt,prev=[],user='')

    def process_batch(self,batch, **kwargs):
        """Processes a single batch of project entries."""
        # print(f"--processing batch-- {batch} for tenant {tenant_id} & user {user_id}\n")
        try:
            debugLogger.info(f"Starting process_batch")
            prompt = self.resourceSkillMappingPrompt(batch)
            result = self.llm.run(
                prompt, 
                self.modelOptions, 
                "potential::upload_data", 
                logInDb=self.logInfo
            )
            debugLogger.info(f"Done process_batch")
            
            data = extract_json_after_llm(result)
            return data.get("resource_data", [])
        
        except Exception as e:
            appLogger.error({"event":"potential::process_batch","error":str(e),"traceback":traceback.format_exc()})

    def create_potential(self, data_array, batch_size=20, socket_id=None):
        """
            Process resources from a spreadsheet file (e.g., CSV) row by row, assign primary/secondary skills via LLM, and insert into DB.
            List of results for each processed row, including success or error details.
        """
        results = []
        msg = f"Processing {len(data_array)} rows from sheet"
        print("--debug process_items_from_sheet length------", msg)

        # Prepare input data for activity logging
        input_data = {
            "total_rows": len(data_array),
            "batch_size": batch_size,
            "raw_sheet_data": data_array[:5] if len(data_array) > 5 else data_array,  # Sample first 5 rows
            "data_summary": {
                "total_count": len(data_array),
                "sample_fields": list(data_array[0].get("data", {}).keys()) if data_array else []
            }
        }

        # Step 2: Collect row data
        rows = []
        for index, item in enumerate(data_array):
            row = item.get("data") or {}
            extra_data = item.get("extra_data") or {}
            row_data = {
                'temp_id': index,
                'first_name': clean_text(row.get('first_name', '')),
                'last_name': clean_text(row.get('last_name', '')),
                'country': clean_text(row.get('country', '')),
                'email': clean_text(row.get('email', '')),
                'role': clean_text(row.get('role', '')),
                'skills': clean_text(row.get('skills', '')),
                'allocation': row.get('allocation', ''),
                'experience_years': row.get('experience_years', ''),
                'experience': clean_text(row.get('experience', '')),
                'projects': clean_text(row.get('projects', '')),
                'is_active': row.get('is_active') or 'True',
                'is_external': row.get('is_external') or 'False',
                'availability_time': row.get('availability_time', '') or '',
            }
            rows.append(row_data)
            results.append({"row": index + 1, "status": "processed", "data": row_data})
        
        debugLogger.info(f"Rows created length: {len(rows)}")
        
        # Track processing statistics
        processing_stats = {
            "total_rows": len(rows),
            "batches_processed": 0,
            "llm_calls": 0,
            "successful_inserts": 0,
            "failed_inserts": 0,
            "duplicate_emails": 0
        }
        
        if rows:
            futures = []
            with ThreadPoolExecutor(max_workers=4) as executor:
                for i in range(0, len(rows), batch_size):
                    batch = rows[i:i + batch_size]
                    llm_batch = [{"id": r['temp_id'], "role": r['role'], "skills": r['skills']} for r in batch]
                    futures.append(executor.submit(self.process_batch, llm_batch))
                    processing_stats["batches_processed"] += 1
                    processing_stats["llm_calls"] += 1

            all_mappings = []
            for future in as_completed(futures):
                try:
                    mappings = future.result()
                    all_mappings.extend(mappings)
                except Exception as e:
                    print(f"Error in batch processing: {e}")
                    results.append({"error": str(e)})

            # Apply mappings to rows
            for mapping in all_mappings:
                for row in rows:
                    if row['temp_id'] == mapping['id']:
                        row['primary_skill'] = mapping['primary_skill_group']
                        row['secondary_skill'] = mapping['secondary_skill_group']

        insert_query = """
            INSERT INTO public.capacity_resource (
                first_name, 
                last_name, 
                country, 
                email, 
                role, 
                skills, 
                allocation, 
                experience_years, 
                experience, 
                projects,
                is_active, 
                is_external,
                created_on, 
                updated_on, 
                created_by_id, 
                updated_by_id, 
                tenant_id,
                trmeric_provider_tenant_id, 
                external_provider_id,
                availability_time, 
                location, 
                rate, 
                primary_skill, 
                secondary_skill
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        inserted_resources = []
        for row in rows:
            try:
                is_active = True if str(row['is_active']).lower() == 'true' else False
                is_external = True if str(row['is_external']).lower() == 'true' else False
                allocation = int(row['allocation']) if row['allocation'] else 0
                experience_years = int(row['experience_years']) if row['experience_years'] else 0
                availability_time = int(row['availability_time']) if row['availability_time'] else None
                location = row.get('location', None) or None
                rate = float(row.get('rate')) if row.get('rate') else None
                params = (
                    row['first_name'], 
                    row['last_name'], 
                    row['country'], 
                    row['email'], 
                    row['role'], 
                    row['skills'],
                    allocation, 
                    experience_years, 
                    row['experience'], 
                    row['projects'],
                    is_active, 
                    is_external, 
                    datetime.now(), 
                    datetime.now(), 
                    self.user_id, 
                    None, 
                    self.tenant_id,
                    None, 
                    None, 
                    availability_time, 
                    location, 
                    rate, 
                    row.get('primary_skill', ''), 
                    row.get('secondary_skill', '')
                )
                ## check if email (unique) exists in this tenant or not
                # TenantDao.getResourceCapacityBasicInfo()
                email = row.get("email") or ""
                query = f"""
                    select email from capacity_resource
                    where tenant_id = {self.tenant_id}
                    and LOWER(email) = '{email.lower()}'
                """
                res = db_instance.retrieveSQLQueryOld(query)
                if len(res) > 0:
                    debugLogger.info(f"Failed to insert resource: {row['first_name']} {row['last_name']} coz email already exist")
                    results.append({"row": row['temp_id'] + 1, "status": "already exist"})
                    processing_stats["duplicate_emails"] += 1
                    continue
                db_instance.executeSQLQuery(insert_query, params)
                debugLogger.info(f"Inserted resource: {row['first_name']} {row['last_name']}")
                results.append({"row": row['temp_id'] + 1, "status": "inserted"})
                processing_stats["successful_inserts"] += 1
                
                # Track successfully inserted resource
                inserted_resources.append({
                    "name": f"{row['first_name']} {row['last_name']}",
                    "email": row['email'],
                    "role": row['role'],
                    "primary_skill": row.get('primary_skill', ''),
                    "secondary_skill": row.get('secondary_skill', ''),
                    "allocation": allocation,
                    "experience_years": experience_years
                })
                
            except Exception as e:
                error_msg = f"Error inserting row {row['temp_id'] + 1}: {str(e)}"
                appLogger.error({"event": "Insert failed", "error": error_msg})
                results.append({"error": error_msg})
                processing_stats["failed_inserts"] += 1
        
        # Log complete potential creation transformation
        activity_log(
            agent_or_workflow_name="trucible_potential_creation",
            input_data=input_data,  # Complete Excel sheet data used for creation
            output_data=inserted_resources,  # Just the successfully created resources data
            user_id=self.user_id,
            tenant_id=self.tenant_id,
            socket_id=socket_id,  # Pass socket_id from cronV2
            description=f"Complete potential resources creation from Excel data: {processing_stats['successful_inserts']} resources created",
            status="success" if processing_stats["successful_inserts"] > 0 else "partial_success",
            metrics={
                "creation_source": "trucible",
                "total_rows": len(rows),
                "successful_inserts": processing_stats["successful_inserts"],
                "failed_inserts": processing_stats["failed_inserts"],
                "duplicate_emails": processing_stats["duplicate_emails"]
            }
        )
        
        return results


    def create_idea(self, item, additional_data, original_used_data, socket_id=None):
        res_message = ""
        
        input_data = {
            "mapped_sheet_data": item,
            # "roadmap_title": item.get("roadmap_title", "")
        }
        
        try:
            from src.trmeric_services.idea_pad.IdeaPadService import IdeaPadService
            idea_service = IdeaPadService()
            context = get_consolidated_persona_context_utils(tenant_id = self.tenant_id, user_id = self.user_id, chat_type= 6)
            
            prompt = ideationCanvasPromptTrucible(
                idea_input_json=item,
                org_info=context.get("customer_info", {}) or {},
                persona=context.get("persona", {}) or {},
                org_strategy=context.get("org_alignment"),
                portfolios=context.get("all_portfolios"),
                internal_knowledge = "",
                files = None,
            )
            
            response = self.llm.run(
                prompt,
                self.modelOptions, 
                f'creator::idea', 
                logInDb=self.logInfo
            )
            print("response ----", response)
            
                        
            output = extract_json_after_llm(response)
            print("\n\n--debug response------ ", output)
            thought_process = {
                "tp_description": output.get("thought_process_behind_description","") or None,
                "tp_key_results": output.get("thought_process_behind_keyresults","") or None,
                "tp_constraints": output.get("thought_process_behind_constraints","") or None,
                "tp_category": output.get("thought_process_behind_category","") or None,
                "tp_org_strategy": output.get("thought_process_behind_org_strategy","") or None,
                "tp_objectives": output.get("thought_process_behind_objectives","") or None,
                "tp_complexity": output.get("thought_process_behind_complexity_impact") or None,
                "complexity_impact_evaluation": output.get("complexity_impact_evaluation") or None
            }

            output.pop("thought_process_behind_description",None)
            output.pop("thought_process_behind_keyresults",None)
            output.pop("thought_process_behind_constraints",None)
            output.pop("thought_process_behind_category",None)
            output.pop("thought_process_behind_org_strategy",None)
            output.pop("thought_process_behind_objectives",None)
            output.pop("thought_process_behind_complexity_impact", None)
            
            ideation_canvas = {}
            ideation_canvas["details"] = output
            ideation_canvas["tango_analysis"] = thought_process
            
            solution_insights = idea_service.createIdeationInsights(
                output,
                tenant_id=self.tenant_id,
                user_id = self.user_id,
                language=context.get("user_language"),
                step_sender=None
            )
            ideation_canvas["insights"] = solution_insights.get("insights",{}) or None
            
            #  
            headers = {
                'Content-Type': 'application/json'
            }
            
            print("json input to roadmap creation ", json.dumps(output, indent=2))
            import os
            self.create_roadmap_url = os.getenv("DJANGO_BACKEND_URL") + "api/idea/tango/create"
            
            response = requests.post(
                self.create_roadmap_url, 
                headers=headers, 
                json=output, 
                timeout=4
            )

            # Print the response (status code and content)
            print("Status Code:", response.status_code)
            
            if response.status_code == 201:
                json_ = response.json()
                print("Response JSON:", json_)
                res_message = f"""
                    Created Roadmap:
                    id: {(json_.get("data") or  {}).get("id")}, 
                    title: {(json_.get("data") or  {}).get("title")}
                """
                
                # SUCCESS: Log complete roadmap creation transformation
                # activity_log(
                #     agent_or_workflow_name="trucible_roadmap_creation",
                #     input_data=input_data,  # Complete Excel sheet data used for creation
                #     output_data=new_output,  # The complete roadmap data sent for creation
                #     user_id=self.user_id,
                #     tenant_id=self.tenant_id,
                #     socket_id=socket_id,  # Pass socket_id from cronV2
                #     description=f"Complete roadmap creation from Excel data: {input_data['roadmap_title']}",
                #     status="success",
                #     metrics={
                #         "creation_source": "trucible",
                #         "roadmap_id": (json_.get("data") or {}).get("id"),
                #     }
                # )
            else:
                print("Response Content:", response.text)
                res_message = f"Failed  to create Roadmap: {response.text}"
                
                # FAILURE: Log failed roadmap creation
                activity_log(
                    agent_or_workflow_name="trucible_roadmap_creation",
                    input_data=input_data,
                    output_data={"error": response.text, "status_code": response.status_code},  # Simple error info
                    user_id=self.user_id,
                    tenant_id=self.tenant_id,
                    socket_id=socket_id,  # Pass socket_id from cronV2
                    description=f"Failed roadmap creation from Excel data: {input_data['roadmap_title']}",
                    status="error",
                    metrics={
                        "creation_source": "trucible",
                        "error_type": "api_creation_failed",
                        "status_code": response.status_code
                    }
                )
            
            return res_message
        except Exception as e:
            raise e


# def run():
#     results = process_items_from_sheet(file_path="Solutions.csv", tenant_id=776, user_id=86)
#     for result in results:
#         if "error" in result:
#             print(f"Error: {result['error']}")
#         else:
#             print(f"Processed/Inserted row {result.get('row')}: {result.get('status')}")
            

