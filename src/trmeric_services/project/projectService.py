import json
import time
import traceback
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_services.project.Prompts import *
from src.trmeric_services.project.ProviderPrompts import *
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_database.dao import PortfolioDao, ProjectsDaoV2, ProjectsDao, CustomerDao,TenantDao, RoadmapDao, TenantDaoV2
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_s3.s3 import S3Service
from src.trmeric_services.summarizer.SummarizerService import SummarizerService
from src.trmeric_services.integration.prompts.drive import driveRoadmapScopePrompt
from src.trmeric_services.journal.Activity import activity, record
from src.trmeric_services.agents.prompts.agents import resource_planning_agent
from src.trmeric_services.agents.functions.graphql_v2.analysis.project_inference import infer_project
import concurrent.futures
from src.trmeric_services.project.utils import *
from src.trmeric_services.agents.core.agent_functions import AgentFunction,AgentFnTypes
import threading
from src.trmeric_services.agents.functions.graphql_v2.utils.tenant_helper import is_knowledge_integrated


class ProjectService:
    def __init__(self):
        self.llm = ChatGPTClient()
        self.modelOptions = ModelOptions(
            model="gpt-4.1",
            max_tokens=15000,
            temperature=0.1
        )
        self.s3_service = S3Service()

    @activity('planning_agent_for_mission::project_insights')
    def createProjectInsights(self,project_canvas,tenant_id,user_id,step_sender=None):
        
        try:
            created_canvas = project_canvas
            existing_projects = ProjectsDaoV2.fetchProjectsDataWithProjectionAttrs(
                tenant_id = tenant_id,
                projection_attrs=['title','scope','start_date','end_date'],
            )
            prompt = projectInsightsPrompt(canvas = json.dumps(created_canvas,indent=2),existing_projects = json.dumps(existing_projects,indent=2))
            # print("\n--debug [createProjectInsights] prompt-----", prompt.formatAsString())
            response = self.llm.run(prompt, self.modelOptions,'agent::create_projectinsights', logInDb={"tenant_id":tenant_id,"user_id":user_id})
            result = extract_json_after_llm(response,step_sender=step_sender)
            
            # print("--debug result [createProjectInsights]---", result)        
            appLogger.info({"event": "createProjectInsights", "msg": "done","tenant_id":tenant_id,"user_id":user_id})
            return result
        
        except Exception as e:
            if step_sender:
                step_sender.sendError(key=f"Error generating project insights",function="createProjectInsights")
            appLogger.error({"event": "createProjectInsights", "error": e, "traceback": traceback.format_exc(),"tenant_id":tenant_id,"user_id":user_id})
            return None

    @activity("projectService::tangoAssistCreateKeyAccomplishments")
    def tangoAssistCreateKeyAccomplishments(
        self,
        tenant_id,
        project_id,
        log_input=None,
        user_id=None # user_id is used by the @activity decorator
    ):
        project_info = ProjectsDao.FetchProjectDetails(project_id)
        status_updates = ProjectsDao.FetchAllProjectStatusUpdates(
            project_id=project_id
        )
        # Record input after fetching necessary data
        record("input_data", f"project_id: {project_id}, project_info_fetched: {project_info is not None}, status_updates_count: {len(status_updates) if status_updates else 0}")
        record("description", "Tango creates key accomplishments for a project based on its status updates.")
        prompt = createKeyAccomplishmentPrompt(
            project_status_updates=status_updates)
        response = self.llm.run(
            prompt,
            self.modelOptions,
            "tangoAssistCreateKeyAccomplishments",
            logInDb=log_input
        )
        result = extract_json_after_llm(response)
        record("output_data", result)
        return result

    @activity("projectService::enchanceDescription")
    def enhanceDescription(
        self,
        tenant_id,
        project_name,
        project_description,
        is_provider,
        log_input=None,
        user_id=None
    ):
        # print("---debug claling  enhanceDescription-------", project_name, tenant_id)
        org_strategy = RoadmapDao.fetchAllOrgstategyAlignmentTitles(tenant_id)[:80]

        if (is_provider):
            prompt = enhanceDescriptionPromptProvider(
                name=project_name,
                desc=project_description,
                org_strategy = org_strategy
            )
            response = self.llm.run(prompt, self.modelOptions, "enhanceDescription", logInDb=log_input)
            return extract_json_after_llm(response)

        tenantPersona = CustomerDao.FetchCustomerPersona(tenant_id=tenant_id)[0]['persona']
        tenantOrgInfo = CustomerDao.FetchCustomerOrgDetailInfo(tenant_id=tenant_id)[0]['org_info']

        # portfolio_project_mapping = PortfolioDao.fetchPortfoliosOfProjectsForTenant(
        #     tenant_id=tenant_id, projects_list=False
        # )
        # portfolio_id_response = self.llm.run(
        #     portfolioSelectorPrompt(project_name=project_name, portfolios=portfolio_project_mapping),
        #     self.modelOptions,
        #     "createProject::enhanceDescription::portfolio::classifier",
        #     logInDb=log_input
        # )
        # print("------------------debug-----------")
        # print(portfolio_id_response)
        # extracted_portfolio_id = extract_json_after_llm(portfolio_id_response).get("selected_portfolio_id")
        # print("extracted_portfolio_id ", extracted_portfolio_id)
        # print(extract_json_after_llm(response))
        # print("------------------debug-----------")

        # portfolio_level_knowledge = KnowledgeDao.FetchProjectPortfolioKnowledge(tenant_id, extracted_portfolio_id)

        # portfolio_level_knowledge = None
        prompt = enhanceDescriptionPrompt(
            name=project_name,
            desc=project_description,
            org_details=tenantOrgInfo,
            org_persona=tenantPersona,
            context_of_projects_in_portfolio="",
            org_strategy = org_strategy
            # context_of_projects_in_portfolio=portfolio_level_knowledge
        )

        # print("prompt -- ", prompt.formatAsString())
        # return
        record("input_data", f"project_name: {project_name}, project_description: {project_description}, org_details: {tenantOrgInfo}, org_persona: {tenantPersona}")
        record("description", "Tango enhances a given project's description based on the provided details and tenant information in the input data.")
        response = self.llm.run(
            prompt,
            self.modelOptions,
            "enhanceDescription",
            logInDb=log_input
        )
        record("output_data", extract_json_after_llm(response))
        res = extract_json_after_llm(response)
        # print("--debug res-------", res)
        return res

    @activity("projectService::enhanceProjectObjective")
    def enhanceProjectObjective(
        self,
        tenant_id,
        project_name,
        project_description,
        project_objective,
        is_provider,
        log_input=None,
        user_id=None # user_id is used by the @activity decorator
    ):
        if (is_provider):
            record("input_data", f"project_name: {project_name}, project_description: {project_description}, project_objective: {project_objective}, is_provider: {is_provider}")
            record("description", "Tango enhances a given project's objective based on the provided details and tenant information in the input data.")
            prompt = enhanceProjectObjectivePromptProvider(
                name=project_name,
                desc=project_description,
                project_objective=project_objective
            )
            response = self.llm.run(
                prompt,
                self.modelOptions,
                "enhanceProjectObjective",
                logInDb=log_input
            )
            result = extract_json_after_llm(response)
            record("output_data", result)
            return result

        tenantPersona = CustomerDao.FetchCustomerPersona(tenant_id=tenant_id)[
            0]['persona']
        tenantOrgInfo = CustomerDao.FetchCustomerOrgDetailInfo(
            tenant_id=tenant_id)[0]['org_info']
        
        record("input_data", f"project_name: {project_name}, project_description: {project_description}, project_objective: {project_objective}, org_details: {tenantOrgInfo}, org_persona: {tenantPersona}, is_provider: {is_provider}")

        prompt = enhanceProjectObjectivePrompt(name=project_name, desc=project_description, org_details=tenantOrgInfo, org_persona=tenantPersona, project_objective=project_objective)

        response = self.llm.run(
            prompt,
            self.modelOptions,
            "enhanceProjectObjective",
            logInDb=log_input
        )
        result = extract_json_after_llm(response)
        record("output_data", result)
        return result

    @activity("projectService::createKeyResults")
    def createKeyResults(
        self,
        tenant_id,
        project_name,
        project_description,
        project_objective,
        is_provider,
        log_input=None,
        user_id=None, # user_id is used by the @activity decorator
        web = False
    ):
        if (is_provider):
            record("input_data", f"project_name: {project_name}, project_description: {project_description}, project_objective: {project_objective}, is_provider: {is_provider}")
            record("description", "Tango creates key results for a project based on its description and objectives.")
            prompt = createKeyResultsPromptProvider(
                name=project_name,
                desc=project_description,
                project_objective=project_objective
            )
            response = self.llm.run(
                prompt,
                self.modelOptions,
                "createKeyResults_provider",
                logInDb=log_input,
                web=web
            )
            result = extract_json_after_llm(response)
            record("output_data", result)
            return result
            
        tenantPersona = CustomerDao.FetchCustomerPersona(tenant_id=tenant_id)[
            0]['persona']
        tenantOrgInfo = CustomerDao.FetchCustomerOrgDetailInfo(
            tenant_id=tenant_id)[0]['org_info']

        record("input_data", f"project_name: {project_name}, project_description: {project_description}, project_objective: {project_objective}, org_details: {tenantOrgInfo}, org_persona: {tenantPersona}, is_provider: {is_provider}")

        prompt = createKeyResultsPrompt(
            name=project_name,
            desc=project_description,
            org_details=tenantOrgInfo,
            org_persona=tenantPersona,
            project_objective=project_objective
        )

        response = self.llm.run(
            prompt,
            self.modelOptions,
            "createKeyResults",
            web=web,
            logInDb=log_input
        )
        result = extract_json_after_llm(response)
        record("output_data", result)
        return result

    @activity("projectService::createProjectCapabilities")
    def createProjectCpabilities( # Typo in original method name, decorator uses corrected name
        self,
        tenant_id,
        project_name,
        project_description,
        project_objective,
        project_key_results,
        is_provider,
        log_input=None,
        user_id=None # user_id is used by the @activity decorator
    ):
        if (is_provider):
            record("input_data", f"project_name: {project_name}, project_description: {project_description}, project_objective: {project_objective}, project_key_results: {project_key_results}, is_provider: {is_provider}")
            record("description", "Tango creates project capabilities for a project based on its description, objectives, and key results.")
            prompt = createProjectCapabilitiesPromptProvider(
                name=project_name,
                desc=project_description,
                project_objective=project_objective,
                project_key_results=project_key_results
            )
            response = self.llm.run(
                prompt,
                self.modelOptions,
                "createProjectCpabilities_provider", # Keeping original LLM call name
                logInDb=log_input
            )
            result = extract_json_after_llm(response)
            record("output_data", result)
            return result

        tenantPersona = CustomerDao.FetchCustomerPersona(tenant_id=tenant_id)[
            0]['persona']
        tenantOrgInfo = CustomerDao.FetchCustomerOrgDetailInfo(
            tenant_id=tenant_id)[0]['org_info']

        record("input_data", f"project_name: {project_name}, project_description: {project_description}, project_objective: {project_objective}, project_key_results: {project_key_results}, org_details: {tenantOrgInfo}, org_persona: {tenantPersona}, is_provider: {is_provider}")

        prompt = createProjectCapabilitiesPrompt(
            name=project_name, desc=project_description, org_details=tenantOrgInfo, org_persona=tenantPersona, project_objective=project_objective, project_key_results=project_key_results
        )

        response = self.llm.run(
            prompt,
            self.modelOptions,
            "createProjectCpabilities", # Keeping original LLM call name
            logInDb=log_input
        )
        result = extract_json_after_llm(response)
        record("output_data", result)
        return result

    @activity("projectService::findTechStackRequired")
    def findTechStackRequired(
        self,
        tenant_id,
        project_name,
        project_description,
        project_objective,
        project_key_results,
        project_capabilities,
        is_provider,
        log_input=None,
        user_id=None # user_id is used by the @activity decorator
    ):
        if (is_provider):
            record("input_data", f"project_name: {project_name}, project_description: {project_description}, project_objective: {project_objective}, project_key_results: {project_key_results}, project_capabilities: {project_capabilities}, is_provider: {is_provider}")
            record("description", "Tango finds the tech stack required for a project based on its description, objectives, key results, and capabilities.")
            prompt = findTechStackPromptProvider(
                name=project_name, desc=project_description, project_objective=project_objective, project_key_results=project_key_results, project_capabilities=project_capabilities
            )
            response = self.llm.run(
                prompt,
                self.modelOptions,
                "findTechStackRequired_provider",
                logInDb=log_input
            )
            result = extract_json_after_llm(response)
            record("output_data", result)
            return result

        tenantPersona = CustomerDao.FetchCustomerPersona(tenant_id=tenant_id)[
            0]['persona']
        tenantOrgInfo = CustomerDao.FetchCustomerOrgDetailInfo(
            tenant_id=tenant_id)[0]['org_info']

        record("input_data", f"project_name: {project_name}, project_description: {project_description}, project_objective: {project_objective}, project_key_results: {project_key_results}, project_capabilities: {project_capabilities}, org_details: {tenantOrgInfo}, org_persona: {tenantPersona}, is_provider: {is_provider}")

        prompt = findTechStackPrompt(
            name=project_name,
            desc=project_description,
            org_details=tenantOrgInfo,
            org_persona=tenantPersona,
            project_objective=project_objective,
            project_key_results=project_key_results,
            project_capabilities=project_capabilities,
        )

        response = self.llm.run(
            prompt,
            self.modelOptions,
            "findTechStackRequired",
            logInDb=log_input
        )
        result = extract_json_after_llm(response)
        record("output_data", result)
        return result

    def createProjectV2(
        self,
        tenant_id,
        project_name,
        project_description,
        is_provider = False,
        log_input=None,
        step_sender = None,
        enable_inference = True
    ):
        try:
            # print("---deubg in createProjectV2", tenant_id, project_name, project_description)
            start = time.time()
            
            tenantPersona = None
            tenantOrgInfo = None
            portfoliosOfTenant = None
            org_strategy_alignment = None
            customerInfo = None
            inference_guidance = None
            enable_inference = False # Turn off for now - only roadmaps
            
            if is_provider == False:
                try:
                    tenantPersona = CustomerDao.FetchCustomerPersona(tenant_id=tenant_id)[0]['persona']
                except Exception as e:
                    print("error ", e, traceback.format_exc())
                
                try:
                    tenantOrgInfo = CustomerDao.FetchCustomerOrgDetailInfo(tenant_id=tenant_id)[0]['org_info']
                except Exception as e:
                    print("error ", e, traceback.format_exc())
                    
                try:
                    customerInfo = TenantDaoV2.fetch_trucible_customer_context(tenant_id=tenant_id)
                except Exception as e:
                    print("error fetching trucible context --- ", e, traceback.format_exc())
                    
                try:
                    portfoliosOfTenant = PortfolioDao.fetchPortfoliosOfTenant(tenant_id)
                except Exception as e:
                    print("error ", e, traceback.format_exc())
                    
                try:
                    org_strategy_alignment = RoadmapDao.fetchAllOrgstategyAlignmentTitles(tenant_id=tenant_id)
                except Exception as e:
                    print("error ", e, traceback.format_exc())
                
                graphname = is_knowledge_integrated(tenant_id=tenant_id)
                if enable_inference and graphname:
                    try:

                        print("--debug Running project inference...")
                        inference_result = infer_project(
                            project_name=project_name,
                            project_description=project_description,
                            tenant_id=tenant_id,
                            is_provider=False,
                            model_options=ModelOptions(model="gpt-4o", max_tokens=2000, temperature=0.3),
                            graphname=graphname,
                        )
                        
                        if inference_result.get("matching_templates") or inference_result.get("matching_patterns"):
                            inference_guidance = {
                                "matching_templates": inference_result.get("matching_templates", []),
                                "matching_patterns": inference_result.get("matching_patterns", []),
                                "inference_guidance": inference_result.get("inference_guidance", ""),
                                "delivery_themes": inference_result.get("delivery_themes", []),
                                "delivery_approaches": inference_result.get("delivery_approaches", []),
                                "delivery_success_criteria": inference_result.get("delivery_success_criteria", []),
                            }
                            print(f"--debug Inference complete - matched {len(inference_result.get('matching_templates', []))} templates")
                    except Exception as e:
                        print(f"--debug Inference failed: {e}")
                        appLogger.error({
                            "event": "createProjectV2::inference",
                            "error": str(e),
                            "traceback": traceback.format_exc()
                        })
                        # Continue without inference - it's optional
                
            prompt = createProjectDataV2(
                name=project_name,
                desc=project_description,
                org_details=tenantOrgInfo,
                org_persona=tenantPersona,
                portfoliosOfTenant=portfoliosOfTenant,
                org_strategy_alignment=org_strategy_alignment,
                is_provider = is_provider,
                customerInfo=customerInfo,
                inference_guidance=inference_guidance
            )
            modelOptions = ModelOptions(
                model="gpt-4.1",
                max_tokens=15000,
                temperature=0.1
            )
            
            # print("prompt createProjectDataV2-- ", prompt.formatAsString())        
            response = self.llm.run(prompt,self.modelOptions,"createProjectV2",logInDb=log_input)
            result = extract_json_after_llm(response)
            
            elapsed_time = int(time.time() - start)
            print("\n--debug Time taken-------", elapsed_time)
            return result
        except Exception as e:
            appLogger.error({"event": "createProjectV2", "error": e, "traceback": traceback.format_exc()})
            if step_sender:
                step_sender.sendError(key=f"{str(e)}",function="createProjectV2")
            return {}
    
    
    def fetchScopeFromIntegration(
        self,
        tenant_id = None,
        user_id = None,
        project_id = None,
        socketio = None,
        client_id = None,
        logInfo = None,
        # key= None,
        **kwargs
    ):
        data = kwargs.get("data", {})
        project_id = data.get("project_id", None)
        key = data.get("key", None)
        tenant_id = tenant_id
        step_sender = kwargs.get("steps_sender", None)
        try:
            print("--debug [Project Scope] generation---------", project_id)
            project_scope = []

            if key:
                print("\ndebug -- s3key --- ", key)

                file_content = self.s3_service.download_file_as_text(s3_key=key)
                if file_content is None:
                    print(f"Skipping file {key} due to download error.")
                    step_sender.sendError(key=f"Skipping file due to download error.",function="fetchScopeFromIntegration")
                    # socketio.emit("roadmap_creation_agent",{"event":"fetchScopeFromIntegration","data":"No data","project_id":project_id},room=client_id)
                
                summarizer_service = SummarizerService(logInfo=logInfo)
                document = summarizer_service.summarizer(
                    large_data=file_content, message="This is a document to generate the Project scope fetch all the necessary details.", identifier="files_uploaded"
                )

                # with open("scope_doc.json", 'w') as file:
                #         json.dump(document, file, indent=4)

                customer_context = CustomerDao.getCustomerProfileDetails(tenant_id)
                project_details = ProjectsDao.fetchProjectDetailsForIssueCreation(project_id)

                if document:
                    prompt = driveRoadmapScopePrompt(customer_context=customer_context, roadmap_details=project_details, document=document)

                    print("\n--debug calling LLM for Scope===")
                    response = self.llm.run(prompt, self.modelOptions,'agent::project_scope', logInDb = logInfo)
                    result = extract_json_after_llm(response,step_sender=step_sender)
                    # print("\n\n--debug scope result----", result)

                    # with open("project_scope.json", 'w') as file:
                    #     json.dump(result, file, indent=4)

                    scope = result.get("scope_item", {})
                    transformed_scope = {"scope": {"name": f"""{scope.get("name")}\n {scope.get("combined_details_out_of_scope_in_markdown_format")}"""}}
                    project_scope.append(transformed_scope)

            print("\n\n [Project Scope]------", project_scope)
            socketio.emit(
                "roadmap_creation_agent",
                {
                    "event":"fetchScopeFromIntegration",
                    "data":project_scope if len(project_scope)>0 else [{'scope': {'name':"No data found"}}],
                    "project_id":project_id
                },
                room=client_id,
            )
            appLogger.info({"event": "fetchScopeFromIntegration", "message": "Project Scope done", "project_id": project_id})

        except Exception as e:
            print("--debug error in fetchScopeFromIntegration", e)
            appLogger.error({"event": "fetchScopeFromIntegration","error": e,"traceback": traceback.format_exc()})
            step_sender.sendError(key=f"{str(e)}",function="fetchScopeFromIntegration")
        
            


    def updateProjectCanvas(
        self,
        tenantID=None,
        userID=None,
        # project_id =None,
        socketio=None,
        client_id=None,
        model_opts = None,
        logInfo =None,
        # step_sender=None,
        **kwargs
    ):
        data = kwargs.get("data", {})
        step_sender = kwargs.get("steps_sender", None)
        project_id = data.get("project_id", None)
        print("\n\n--debug [Project Canvas] update request for project_id: ", project_id,tenantID, userID)
        tenant_id = tenantID
        try:
            start = time.time()
            step_sender.sendSteps("Fetching Customer Persona", False)
            step_sender.sendSteps("Fetching Organization Details", False)
            step_sender.sendSteps("Fetching Project Details", False)

            tenantPersona = CustomerDao.FetchCustomerPersona(tenant_id=tenant_id)[0]['persona']
            tenantOrgInfo = CustomerDao.FetchCustomerOrgDetailInfo(tenant_id=tenant_id)[0]['org_info']
            portfoliosOfTenant = PortfolioDao.fetchPortfoliosOfTenant(tenant_id)

            tenant_config = TenantDao.getTenantInfo(tenant_id=tenant_id)
            tenant_config_res = tenant_config[0]['configuration']
            tenant_formats = {}
            if tenant_config_res is not None:
                tenant_formats["currency_format"] = tenant_config_res.get("currency", {})
                tenant_formats["date_format"] = tenant_config_res.get("date_time", {})

            appLogger.info({"event": "tenant_config", "data": tenant_formats, "tenant_id": tenant_id})

            project_details = ProjectsDao.fetch_project_details_for_service_assurance_old(project_id)
            project_scope = ProjectsDao.getProjectScope(project_id)

            # print("\n\n --debug [Scope]-----", project_scope)

            step_sender.sendSteps("Fetching Customer Persona", True)
            step_sender.sendSteps("Fetching Organization Details", True)
            step_sender.sendSteps("Fetching Project Details", True)

            # project_name = project_details[0]['title']
            # project_desc = project_details[0]['description']

            # print("\n--debug [Project]", project_name, project_desc)

            step_sender.sendSteps("Updating Project Canvas", False)
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                # 1. Update Project Canvas
                future_canvas = executor.submit(self._update_canvas_task, project_details, project_scope, tenantOrgInfo, tenantPersona, portfoliosOfTenant, logInfo, step_sender, model_opts)
                # 2. Update Roles Estimation
                future_roles = executor.submit(self._update_roles_estimation_task, project_details, tenant_formats, logInfo, step_sender)

                canvas_result = future_canvas.result()
                roles_result = future_roles.result()

            # response
            canvas_data = canvas_result
            roles_data = roles_result
            updated_project_json = format_project_json(canvas_data, roles_data)

            elapsed_time = int(time.time() - start)
            print("\n--debug Time taken-------", elapsed_time)
            step_sender.sendSteps("Updating Project Canvas", True)

            socketio.emit("project_creation_agent", {"event": "updateProjectCanvas", "data": updated_project_json, "project_id": project_id}, room=client_id)

            # with open("project_canvas.json", 'w') as file:
            #     json.dump(updated_project_json, file, indent=4)

            appLogger.info({"event": "updateProjectCanvas", "message": "Project Canvas done", "project_id": project_id})

        except Exception as e:
            appLogger.error({"event": "updateProjectCanvas", "error": e, "traceback": traceback.format_exc()})
            step_sender.sendError(key=f"{str(e)}",function="updateProjectCanvas")
            return {}

    def _update_canvas_task(self, project_details, project_scope, tenantOrgInfo, tenantPersona, portfoliosOfTenant, logInfo, step_sender, model_opts):
        """Task to update roadmap canvas."""
        try:
            step_sender.sendSteps("Updating Key Results", False)
            step_sender.sendSteps("Generating the Constraints", False)
            step_sender.sendSteps("Mapping the Timeline", False)

            prompt = updateProjCanvasPrompt(project_details=project_details, project_scope=project_scope, org_details=tenantOrgInfo, org_persona=tenantPersona, portfoliosOfTenant=portfoliosOfTenant)
            # print("--debug proj update prompt", prompt.formatAsString())
            
            response = self.llm.run(prompt,model_opts,"updateProjectCanvas",logInDb=logInfo)
            result = extract_json_after_llm(response,step_sender=step_sender)
            
            # with open("project_canvas111.json", 'w') as file:
            #     json.dump(result, file, indent=4)

            step_sender.sendSteps("Updating Key Results", True)
            step_sender.sendSteps("Generating the Constraints", True)
            step_sender.sendSteps("Mapping the Timeline", True)

            return result
        except Exception as e:
            appLogger.error({"event": "_update_canvas_task", "error": str(e), "traceback": traceback.format_exc()})
            step_sender.sendError(key=f"{str(e)}",function="_update_canvas_task")
            return {}

    def _update_roles_estimation_task(self, project_details, tenant_formats, logInfo, step_sender):
        """Task to estimate roles."""

        try:
            step_sender.sendSteps("Analysing suitable roles", False)

            prompt = resource_planning_agent.suggest_project_role_prompt(project_details=project_details, data_format=tenant_formats.get("currency_format", None))
            # print("--planner", prompt.formatAsString())
            # response = self.llm.run(prompt, self.modelOptions, 'agent::resource_planning_agent', logInfo)
            response = self.llm.run_rl(chat=prompt, options=self.modelOptions, agent_name='resource_planning_agent', function_name='capacity_planner::capacity_planner', logInDb=logInfo)

            # print("--debug capacity_planner-----------", response)
            suggested_roles_json = extract_json_after_llm(response,step_sender=step_sender)

            step_sender.sendSteps("Analysing suitable roles", True)
            # # Process roles
            # processed_roles = []
            # for role in suggested_roles:
            #     processed_roles.extend(OnboardingAgentUtils().transform_role_data(role))
            return suggested_roles_json

        except Exception as e:
            appLogger.error({"event": "_update_roles_estimation_task", "error": str(e), "traceback": traceback.format_exc()})
            step_sender.sendError(key=f"{str(e)}",function="_update_roles_estimation_task")
            return {"suggested_roles": [], "processed_roles": [], "roadmap_role_thought": ""}


    def createProjectV3(
        self,
        tenant_id,
        conversation,
        log_input=None
    ):
        tenantPersona = ""
        tenantOrgInfo = ""
        try:
            
            tenantPersona = CustomerDao.FetchCustomerPersona(tenant_id=tenant_id)[
                0]['persona']
            tenantOrgInfo = CustomerDao.FetchCustomerOrgDetailInfo(
                tenant_id=tenant_id)[0]['org_info']

        except Exception as e:
            print("error", e)
            
        # tenantPersona = CustomerDao.FetchCustomerPersona(tenant_id=tenant_id)[0]['persona']
        # tenantOrgInfo = CustomerDao.FetchCustomerOrgDetailInfo(tenant_id=tenant_id)[0]['org_info']
        portfoliosOfTenant = PortfolioDao.fetchPortfoliosOfTenant(tenant_id)
        
        ## pull org strategies.
        org_strategy_alignment = RoadmapDao.fetchAllOrgstategyAlignmentTitles(tenant_id=tenant_id)

        # portfolio_level_knowledge = None
        prompt = createProjectDataV3(
            conversation=conversation,
            org_details=tenantOrgInfo,
            org_persona=tenantPersona,
            portfoliosOfTenant=portfoliosOfTenant,
            org_strategy_alignment=org_strategy_alignment
        )

        modelOptions = ModelOptions(
            model="gpt-4.1",
            max_tokens=15000,
            temperature=0.1
        )
        
        response = self.llm.run(
            prompt,
            modelOptions,
            "createProjectV2",
            logInDb=log_input
        )
        return extract_json_after_llm(response)
    
    
    
    def tangoAssistProject(
        self,
        tenantID=None,
        userID=None,
        socketio=None,
        client_id=None,
        model_opts = None,
        logInfo =None,
        **kwargs
    ):
        data = kwargs.get("data", {})
        steps_sender_class = kwargs.get("steps_sender", None)
        
        def run_create_project():
            result = self.createProjectV2(
                tenant_id=tenantID,
                project_name=data.get("project_name", "Project"),
                project_description=data.get("project_description", "Desc"),
                is_provider = data.get("is_provider",False),
                log_input=logInfo,
                step_sender = steps_sender_class
            )
            socketio.emit("project_creation_agent", {"event": "tango_assist", "data": result}, room=client_id)
            return

        thread = threading.Thread(target=run_create_project)
        thread.start()

        # Send periodic timelines while the thread runs
        step_counter = 0
        stages = ["Creating Overview", "Fetching Configuration"]
        for stage in stages:
            steps_sender_class.sendSteps(f"{stage}", False)
            socketio.sleep(seconds=8)
            step_counter += 1
            
        while thread.is_alive() and step_counter<len(stages):
            steps_sender_class.sendSteps(f"{stages[step_counter % len(stages)]}", False)
            socketio.sleep(seconds = 8)
            step_counter += 1    
    


    def fetch_project_chat_prefill(self,socketio, client_id, metadata, **kwargs):
        """
        Wrapper method to call QnaController.fetchQnaChatPrefillSocketIO with _type="portfolio".
        """
        from src.controller.qna import QnaController
        return QnaController().fetchQnaChatPrefillSocketIO(
            socketio=socketio,
            client_id=client_id,
            metadata=metadata,
            _type="project"
        )


QNA_CHAT_PREFILL_PROJECT = AgentFunction(
    name="qnaChatPrefillProject",
    description="This function is used to create project from conv",
    args=[],
    return_description="",
    function=ProjectService.fetch_project_chat_prefill,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)



UPDATE_PROJECT_CANVAS= AgentFunction(
    name="updateProjectCanvas",
    description="""
        This function is used to update the project canvas with the latest data.
    """,
    args=[],
    return_description="",
    function=ProjectService.updateProjectCanvas,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)


CREATE_PROJECT_SCOPE = AgentFunction(
    name="fetchScopeFromIntegration",
    description="""
        This function fetches the project scope from an integration, such as a document in S3.
    """,
    args=[],
    return_description="",
    function=ProjectService.fetchScopeFromIntegration,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)
    

TANGO_ASSIST_PROJECT = AgentFunction(
    name= "tangoAssistProject",
    description = "To create project attributes using tango assist",
    args = [],
    return_description = "",
    function = ProjectService.tangoAssistProject,
    type_of_func = AgentFnTypes.ACTION_TAKER_UI.name
)