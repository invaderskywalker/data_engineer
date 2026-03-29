from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_database.Database import db_instance
from src.trmeric_services.agents.functions.onboarding.creation_tools.AutonomousCreateRoadmap import RoadmapAgent
import json
import traceback
from src.trmeric_database.dao import ProviderDao
from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_services.agents.functions.onboarding.creation_tools.AutonomousCreateProject import AutomousProjectAgent
from src.trmeric_services.project.projectService import ProjectService
from src.trmeric_services.agents.functions.service_assurance.update_status_milestone_risk_v2 import create_project_updates
import concurrent.futures


from .queries import *

class Analystactions:
    def __init__(self, tenant_id: int, user_id: int):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.llm = ChatGPTClient(self.user_id, self.tenant_id)
        self.logInfo = {"tenant_id": tenant_id, "user_id": user_id}

    def set_user_designation(self, designation: str):
        """Set or update the user's designation."""
        query = """
            UPDATE users_user
            SET position = %s
            WHERE id = %s
        """
        try:
            db_instance.executeSQLQuery(query, (designation, self.user_id))
            appLogger.info({
                "action": "set_user_designation",
                "user_id": self.user_id,
                "designation": designation
            })
        except Exception as e:
            appLogger.error({
                "action": "set_user_designation_failed",
                "error": str(e),
                "user_id": self.user_id
            })

    def set_company_context(self, org_info: str):
        """Set the organization info for the tenant (initial setup)."""
        query = """
            UPDATE tenant_customer
            SET org_info = %s
            WHERE tenant_id = %s
        """
        # print("set_company_context here in ", org_info)
        try:
            db_instance.executeSQLQuery(query, (org_info, self.tenant_id))
            appLogger.info({
                "action": "set_company_context",
                "tenant_id": self.tenant_id,
                "org_info": org_info
            })
        except Exception as e:
            appLogger.error({
                "action": "set_company_context_failed",
                "error": str(e),
                "tenant_id": self.tenant_id
            })


    def create_roadmaps(self, data: str, extra: dict = {}):
        """
        Entry point called by MasterAnalyst.
        data  – serialized conversation string
        extra – optional overrides (e.g. {"category": ["AI"]})
        idea_ids are resolved autonomously by the LLM from the conversation.
        """
        print("taking action create roadmap")
        try:
            return self._create_roadmap_from_text_input(
                input_data=data,
                extra_data=extra,
            )
        except Exception as e:
            appLogger.error({
                "event": "create_roadmaps_err",
                "error": str(e),
                "traceback": traceback.format_exc(),
            })
            return f"Error occurred in roadmap creation: {e}"

    def _create_roadmap_from_text_input(
        self,
        input_data: str,
        extra_data: dict = {},
    ) -> str:
        """
        Builds a full roadmap payload via combined_roadmap_creation_prompt and
        POSTs it to Django. The LLM autonomously resolves which ideas to link
        by matching conversation references against the all_ideas lookup table.
        """
        import os
        import requests as _requests
        from src.trmeric_services.roadmap.Prompts import combined_roadmap_creation_prompt
        from src.trmeric_database.dao import RoadmapDao, CustomerDao, IdeaDao
        from src.trmeric_services.chat_service.utils import roadmapPersona

        # ── 1. gather org context ────────────────────────────────────────────
        roadmap_context    = roadmapPersona(tenant_id=self.tenant_id, user_id=self.user_id)
        org_strategy       = roadmap_context.get("org_strategy", [])
        internal_knowledge = roadmap_context.get("knowledge") or []
        all_portfolios     = RoadmapDao.fetchAllPortfolioOfTenant(tenant_id=self.tenant_id)
        all_roadmap_titles = RoadmapDao.FetchRoadmapNames(tenant_id=self.tenant_id)
        tenant_org_info    = (
            CustomerDao.FetchCustomerOrgDetailInfo(self.tenant_id) or [{}]
        )[0].get("org_info", "")

        # ── 2. fetch lightweight idea lookup (id + title only) ───────────────
        all_ideas = []
        try:
            all_ideas = IdeaDao.fetchIdeasDataWithProjectionAttrs(
                projection_attrs=["id", "title"],
                tenant_id=self.tenant_id,
            ) or []
        except Exception as e:
            appLogger.error({
                "event": "_create_roadmap_idea_lookup_err",
                "error": str(e),
                "tenant_id": self.tenant_id,
            })

        # ── 3. build prompt ──────────────────────────────────────────────────
        prompt = combined_roadmap_creation_prompt(
            conversation=str(input_data),
            org_info=tenant_org_info,
            org_strategy=org_strategy,
            portfolios=all_portfolios,
            internal_knowledge=internal_knowledge,
            all_roadmap_titles=all_roadmap_titles,
            tenant_id=self.tenant_id,
            inference_guidance=None,
            all_ideas=all_ideas,
        )

        # ── 4. run LLM ───────────────────────────────────────────────────────
        raw = self.llm.run(
            prompt,
            ModelOptions(model="gpt-4.1", max_tokens=8000, temperature=0.3),
            "tango::create_roadmap_from_text",
            logInDb=self.logInfo,
        )

        request_data = extract_json_after_llm(raw)
        if not request_data:
            return "Error: LLM did not return valid JSON for roadmap creation."

        # ── 5. transform LLM output → API payload ────────────────────────────

        # key_results → kpi
        request_data["kpi"] = [
            {"name": kr["key_result"], "baseline_value": kr["baseline_value"]}
            for kr in request_data.pop("key_results", []) or []
        ]

        # business_sponsors + business_unit_name → portfolio_business_data
        business_unit_name = request_data.pop("business_unit_name", "")
        request_data["portfolio_business_data"] = [
            {
                "sponsor_first_name": s.get("sponsor_first_name", ""),
                "sponsor_last_name":  s.get("sponsor_last_name", ""),
                "bu_name": business_unit_name,
            }
            for s in request_data.pop("business_sponsors", []) or []
        ]

        # thought_process fields → nested inside tango_analysis
        request_data.setdefault("tango_analysis", {})
        for field in [
            "thought_process_behind_timeline",
            "thought_process_behind_objectives",
            "thought_process_behind_constraints",
            "thought_process_behind_portfolio",
            "thought_process_behind_category",
            "thought_process_behind_business_value",
            "thought_process_behind_key_results",
            "thought_process_behind_current_state",
        ]:
            val = request_data.pop(field, None)
            if val:
                request_data["tango_analysis"][field] = val

        # extra_data category override
        if extra_data.get("category"):
            extra_cats = ", ".join(extra_data["category"])
            existing   = request_data.get("category", "")
            request_data["category"] = f"{existing}, {extra_cats}".strip(", ")

        # idea_list: LLM returns list of ints — normalize to [{"idea": id}]
        raw_idea_list = request_data.get("idea_list") or []
        request_data["idea_list"] = [
            {"idea": i} if isinstance(i, int) else i
            for i in raw_idea_list
        ]

        # identity
        request_data["user_id"]   = self.user_id
        request_data["tenant_id"] = self.tenant_id
        from src.trmeric_services.roadmap.RoadmapService import RoadmapService
        roadmapService = RoadmapService()
        solution_insights = roadmapService.creatDemandInsights(request_data,self.tenant_id,self.user_id)
        request_data["tango_analysis"]["solution_insights"] = solution_insights
        request_data["tango_analysis"]["creation_source"] = "tango"
        request_data["tango_analysis"]["business_value_question"] = request_data.get("business_value_question") or ""

        # ── 6. POST to Django ────────────────────────────────────────────────
        create_roadmap_url = os.getenv("DJANGO_BACKEND_URL") + "api/roadmap/tango/create"
        print("debug --- roadmap final request data", json.dumps(request_data, indent=2))

        resp = _requests.post(
            create_roadmap_url,
            headers={"Content-Type": "application/json"},
            json=request_data,
            timeout=50,
        )
        print("Status Code:", resp.status_code)
        print("Response Content:", resp.text)

        return (
            f"Success or failure of this method\n"
            f"Response status: {resp.status_code}\n"
            f"Response text: {resp.text}\n\n"
            f"If there is an error, respond meaningfully to the user.\n"
            f"Highlight the roadmap title.\n"
            f"If success, provide the hyperlink:\n"
            f"link: /actionhub/edit-roadmap/<id from response>"
        )



    def create_projects(self, data: str):
        """Stub for project creation logic."""
        try:
            print("here in actions .. create_projects ")
            
            project_result = ProjectService().createProjectV3(
                tenant_id=self.tenant_id,
                conversation=data,
                log_input=self.logInfo
            )
            
            print("here in actions .. create_projects ", project_result)
            
            # Process project result with AutomousProjectAgent
            mapping_data = AutomousProjectAgent().only_request_creation(
                request_data=project_result,
                tenantId=self.tenant_id,
                userId=self.user_id
            )
            return json.dumps(mapping_data)
        except Exception as e:
            return "Error occured while creating project: " + str(e)


    def find_best_provider(self, data: str):
        """Find the top 3 service providers for a roadmap or project based on ID and tag."""
        try:
            # Parse input data (expecting JSON with roadmap_id or project_id and tag)
            input_data = json.loads(data)
            print("debug find_best_provider ", data)
            roadmap_id = input_data.get("roadmap_id")
            project_id = input_data.get("project_id")
            tag = (input_data.get("tag", "roadmap").lower() or "roadmap")

            if not roadmap_id and not project_id:
                raise ValueError("Either roadmap_id or project_id must be provided.")

            # Fetch roadmap or project details based on tag
            if tag == "roadmap" and roadmap_id:
                filter_string = f"AND rr.id = {roadmap_id}"
                query = get_roadmap_query(self.tenant_id, filter_string)
                roadmap_data = db_instance.retrieveSQLQueryOld(query)
                roadmap_data = roadmap_data[0]
                # context = {
                #     "description": roadmap_data.get("roadmap_description", ""),
                #     "objectives": roadmap_data.get("roadmap_objectives", ""),
                #     "scopes": json.loads(roadmap_data.get("roadmap_scopes", "[]")),
                #     "constraints": json.loads(roadmap_data.get("roadmap_constraints", "[]"))
                # }
                context = roadmap_data
            elif tag == "project" and project_id:
                # Placeholder for project query (to be implemented)
                raise NotImplementedError("Project-based provider matching not yet supported.")
            else:
                raise ValueError(f"Invalid tag '{tag}' or missing ID.")

            # Fetch all provider skills
            all_skills_of_providers = ProviderDao.fetchAllDataFromServiceProviderDetailsTable()
            providers_data = [
                {
                    "service_provider_id": provider.get("service_provider_id"),
                    "primary_skills": (provider.get("primary_skills") or "").lower(),
                    "secondary_skills": (provider.get("secondary_skills") or "").lower(),
                    "other_skills": (provider.get("other_skills") or "").lower()
                }
                for provider in all_skills_of_providers
            ]

            # Check for exact skill matches
            selected_provider_ids = []
            # context_skills = " ".join([context["description"], context["objectives"], " ".join(context["scopes"])]).lower()
            # for provider in providers_data:
            #     if (provider["primary_skills"] in context_skills or
            #         provider["secondary_skills"] in context_skills or
            #         provider["other_skills"] in context_skills):
            #         selected_provider_ids.append(provider["service_provider_id"])
            
            model_options = ModelOptions(
                model="gpt-4.1",
                max_tokens=15000,
                temperature=0.1
            )
            

            # If no exact matches, use LLM for intelligent matching
            if not selected_provider_ids:
                prompt = f"""
                    You are an expert in matching service providers to roadmap requirements based on their skills.
                    The roadmap requires expertise in the following context:
                    - {context}

                    Below is a list of service providers with their skills:
                    {json.dumps(providers_data, indent=2)}

                    Analyze the roadmap context and compare it with each provider's primary_skills, 
                    secondary_skills, and other_skills. Consider partial matches, synonyms, or related skills 
                    (e.g., 'Python' might relate to 'Django' or 'data science').

                    Return a JSON object with a list of up to 3 service provider IDs that are the best match, 
                    along with a brief justification for each:
                    ```json
                    {{
                        "recommended_providers": [
                            {{
                                "service_provider_id": "provider_id",
                                "justification": "Reason why this provider is a good match",
                                "rank": 0
                            }}
                        ]
                    }}
                    ```
                """
                
                chat_completion = ChatCompletion(system="", prev=[], user=prompt)
                output = self.llm.run(chat_completion, model_options, function_name="find_best_provider", logInDb={"tenant_id": self.tenant_id, "user_id": self.user_id})
                response_json = extract_json_after_llm(output)
                selected_provider_ids = [p["service_provider_id"] for p in response_json.get("recommended_providers", [])]

            # Fetch detailed provider info and generate summary
            if selected_provider_ids:
                provider_info = ProviderDao.fetchDataForRecomendation(service_provider_ids=selected_provider_ids)
                provider_summary = ProviderDao.createProviderSummary(provider_info)
            else:
                provider_summary = "No suitable providers found."

            # Generate final ranking with LLM
            prompt = f"""
                You are an expert in ranking service providers for a roadmap.
                Roadmap Context:
                - {context}

                Provider Details:
                {json.dumps(provider_summary, indent=2)}

                Rank up to 3 providers based on their relevance to the roadmap context.
                Return a JSON object with the ranked providers:
                ```json
                {{
                    "ranks": [
                        {{
                            "rank": 1,
                            "provider_id": "provider_id",
                            "justification": "Reason for ranking"
                        }}
                    ]
                }}
                ```
            """
            chat_completion = ChatCompletion(system="", prev=[], user=prompt)
            output = self.llm.run(chat_completion, model_options, function_name="rank_providers", logInDb={"tenant_id": self.tenant_id, "user_id": self.user_id})
            response_json = extract_json_after_llm(output)

            # Format result for action_results
            result = [
                {
                    "rank": int(item["rank"]),
                    "service_provider_id": item["provider_id"],
                    "justification": item["justification"]
                }
                for item in response_json.get("ranks", [])
            ]
            return json.dumps({"status": "success", "recommended_providers": result}, indent=2)

        except Exception as e:
            appLogger.error({
                "event": "find_best_provider_err",
                "function": "find_best_provider",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return f"Error finding providers: {str(e)}"


    def create_or_update_sa_agent(self, args, data: str):
        try:
            results = []

            # Step 1: collect unique update types per project
            project_updates = {}
            for d in args:
                project_id = d.get("project_id")
                update_type = d.get("update_type")
                if not project_id or not update_type:
                    continue
                if project_id not in project_updates:
                    project_updates[project_id] = set()
                project_updates[project_id].add(update_type)

            # Step 2: define function to process each update
            def process_update(project_id: str, update_type: str):
                try:
                    result = create_project_updates(
                        user_id=self.user_id,
                        tenant_id=self.tenant_id,
                        project_id=project_id,
                        update_type=update_type,
                        conversation=data
                    )
                    return result
                except Exception as e:
                    appLogger.error({
                        "event": f"AnalystActions_error_in_process_update_{project_id}_{update_type}",
                        "error": str(e),
                        "traceback": traceback.format_exc()
                    })
                    return {"project_id": project_id, "update_type": update_type, "error": str(e)}

            # Step 3: flatten project-update pairs and run concurrently
            tasks = [(pid, utype) for pid, types in project_updates.items() for utype in types]

            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                future_to_task = {executor.submit(process_update, pid, utype): (pid, utype) for pid, utype in tasks}
                for future in concurrent.futures.as_completed(future_to_task):
                    pid, utype = future_to_task[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        results.append({"project_id": pid, "update_type": utype, "error": f"Thread execution failed: {str(e)}"})

            return json.dumps(results, indent=2)

        except Exception as e:
            appLogger.error({
                "event": "AnalystActions_error_in_create_or_update_sa_agent",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return f"error occured {str(e)}"

