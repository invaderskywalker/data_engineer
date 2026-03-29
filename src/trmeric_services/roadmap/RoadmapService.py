import json
import time
import traceback
import concurrent.futures
from src.trmeric_s3.s3 import S3Service
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_services.roadmap.Prompts import *
from src.trmeric_ws.helper import SocketStepsSender
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.integration.Drive_v2 import DriveV2
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_utils.json_parser import extract_json_after_llm,save_as_json
from src.trmeric_services.phoenix.nodes.web_search import WebSearchNode
from src.trmeric_services.integration.prompts.drive import driveRoadmapScopePrompt
from src.trmeric_services.integration.RefreshTokenService import RefreshTokenService
from src.trmeric_services.agents.functions.onboarding.utils.core import OnboardingAgentUtils
from src.trmeric_services.agents.prompts.agents.resource_planning_agent import suggest_project_role_promptV2,suggest_project_role_promptV3
from src.trmeric_database.dao import FileDao,PortfolioDao,CustomerDao,ProjectsDao,RoadmapDao,TenantDao,TangoDao
from src.trmeric_services.summarizer.SummarizerService import SummarizerService
from src.trmeric_services.roadmap.utils import *
from src.trmeric_services.journal.Activity import activity, record
from datetime import datetime, timezone
from src.trmeric_services.agents_v2.helper.file_analyser import FileAnalyzer
from src.trmeric_services.chat_service.utils import process_uploaded_files, get_consolidated_persona_context_utils, _process_solutions
from src.trmeric_services.agents.functions.graphql_v2.analysis.roadmap_inference import (
    infer_roadmap, 
    format_guidance_for_canvas_stages,
    format_basic_stage_prompt_section,
)
from src.trmeric_services.agents.functions.graphql_v2.utils.tenant_helper import is_knowledge_integrated

class RoadmapService:
    def __init__(self):
        self.llm = ChatGPTClient()
        self.modelOptions = ModelOptions(model="gpt-4.1",max_tokens=20384,temperature=0.1)
        self.modelOptions1 = ModelOptions(model="gpt-4.1",max_tokens=5012,temperature=0)
        self.refreshTokenService = RefreshTokenService()
        self.web_search = WebSearchNode()
        self.s3_service = S3Service()  

    _ROADMAP_STEPS = [
        "roadmap_name_description","objective_orgStrategy_keyResult","scope_timeline","constraints_portfolio_category","roles_budget"
    ]   

    def getRoadmapCreationTrackUtility(self,tenantID,userID,roadmap_id):
        """Fetches the roadmap creation tracking state, returning a default if not found."""
        # default_state = {step: False for step in self._ROADMAP_STEPS}
        try:
            print('--debug in getRoadmapCreationTrackUtility---', roadmap_id, userID)
            
            data = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id='', user_id=userID, key=f"roadmap_creation_tracker_{roadmap_id}")
            json_string = data[0]['value']
           
            # print("--debug getRoadmapCreationTrackUtility: Found state string: ", json_string)
            current_state = extract_json_after_llm(json_string) 

            for step in self._ROADMAP_STEPS:
                if step not in current_state:
                    current_state[step] = False
                    
            # print("--debug getRoadmapCreationTrackUtility: Parsed state: ", current_state)
            appLogger.info({"event": "getRoadmapCreationTrackUtility", "data": current_state})
            return current_state

        except Exception as e:
            default_state = {step: True for step in self._ROADMAP_STEPS}
            self.updateRoadmapCreationTrackUtility(tenantID, userID, roadmap_id, self._ROADMAP_STEPS)
            # print(f"Error in getRoadmapCreationTrackUtility for roadmap {roadmap_id}: {e}", traceback.format_exc())
            appLogger.error({"event": "getRoadmapCreationTrackUtility", "error": e, "traceback": traceback.format_exc()})
            return default_state 
    
    def updateRoadmapCreationTrackUtility(self, tenantID, userID, roadmap_id, newly_completed_items=[]):
        """Fetches the current state, updates it with newly completed items, and saves it back."""
        
        print("--debug in updateRoadmapCreationTrackUtility---", newly_completed_items, roadmap_id, userID)
        # current_state = self.getRoadmapCreationTrackUtility(tenantID=tenantID, userID=userID, roadmap_id=roadmap_id)
        
        # current_state = None
        current_state = {}
        # default_state = {step: False for step in self._ROADMAP_STEPS}
        data = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id='', user_id=userID, key=f"roadmap_creation_tracker_{roadmap_id}")
        
        if len(data)>0:
            try:
                json_string = data[0]['value']
                current_state = extract_json_after_llm(json_string) 
                
            except Exception as e:
                # current_state = default_state
                appLogger.error({"event":"updateRoadmapCreationTrackUtility","error":e,"traceback":traceback.format_exc()})
        # else:
        #     current_state = default_state
            
        # print(f"--debug updateRoadmapCreationTrackUtility: Fetched state: {current_state}")
        
        # for step in self._ROADMAP_STEPS:
        #         if step not in current_state:
        #             current_state[step] = False
        
        for item in newly_completed_items:
            if item in self._ROADMAP_STEPS:
                current_state[item] = True
            else:
                print(f"Warning: Item '{item}' not found in expected roadmap steps.")

        # print(f"--debug updateRoadmapCreationTrackUtility: Updated state: {current_state}")
        TangoDao.insertTangoState(
            tenant_id=tenantID, 
            user_id=userID,
            key=f"roadmap_creation_tracker_{roadmap_id}", 
            value=json.dumps(current_state), 
            session_id=''
        )
    
    
    def businessCaseTemplateCreate(self, roadmap_id, log_input=None):
        try:
            roadmap_data = RoadmapDao.fetchRoadmapDataForBusinessPlan(roadmap_id)
            team_data = RoadmapDao.fetchTeamDataRoadmap(roadmap_id=roadmap_id)
            
            labor_cost_analysis = calculateTotalLaborCost(team_data)
            non_labor_cost_analysis = calculateTotalNonLaborCost(team_data)
            
            print("debug businessCaseTemplateCreate-- ", roadmap_data, )
            print("debug businessCaseTemplateCreate-- labor_cost_analysis ",  labor_cost_analysis)
            print("debug businessCaseTemplateCreate-- non_labor_cost_analysis", non_labor_cost_analysis)

            prompt = businessCaseTemplateCreatePrompt(
                roadmap_data=roadmap_data[0],
                labor_cost_analysis=labor_cost_analysis,
                non_labor_cost_analysis=non_labor_cost_analysis
            )

            print("debug prompt -- ", prompt.formatAsString())

            response = self.llm.run(
                prompt,
                self.modelOptions,
                "businessCaseTemplateCreate",
                logInDb=log_input
            )
            print("response --- ", response)
            output = extract_json_after_llm(response)

            # npv_calc_prompt = businessCaseTemplateFinancialCalculationPrompt(business_case_data=response)

            # print("debug prompt -- ", npv_calc_prompt.formatAsString())

            # npv_response = self.llm.run(npv_calc_prompt, self.modelOptions, None)
            # print("response --- ", npv_response)
            # output2 = extract_json_after_llm(npv_response)
            # output.update(output2)

            return output
        except Exception as e:
            appLogger.error({
                "event": "businessCaseTemplateCreate",
                "error":  e,
                "traceback": traceback.format_exc()
            })
            print("error in businessCaseTemplateCreate",
                  e, traceback.format_exc())
            return {}

    def businessCaseTemplateCreateFinancial(self, business_data, log_input=None):
        try:
            print("debug --businessCaseTemplateCreateFinancial- ",
                  type(business_data))

            # important data points
            # revenue_uplift_cashflow for revenue incoming
            # operational_efficiency_gains cause of savings
            # overall_cost_breakdown for total cost

            data = {
                "revenue_uplift_cashflow": business_data.get("revenue_uplift_cashflow", []),
                "operational_efficiency_gains": business_data.get("operational_efficiency_gains", []),
                "overall_cost_breakdown": business_data.get("overall_cost_breakdown", [])
            }

            npv_calc_prompt = businessCaseTemplateFinancialCalculationPrompt(
                business_case_data=data
            )

            print("debug prompt -- ", npv_calc_prompt.formatAsString())

            # modelOptions = ModelOptions(
            #     model="gpt-4o",
            #     max_tokens=4096,
            #     temperature=0.3
            # )

            npv_response = self.llm.run(
                npv_calc_prompt,
                self.modelOptions,
                "businessCaseTemplateCreateFinancial",
                logInDb=log_input
            )
            print("response --- ", npv_response)
            output = extract_json_after_llm(npv_response)
            # output.update(output2)
            return output
        except Exception as e:
            appLogger.error({
                "event": "businessCaseTemplateCreate_financial",
                "error":  e,
                "traceback": traceback.format_exc()
            })
            print("error in businessCaseTemplateCreate financial",
                  e, traceback.format_exc())
            return {}


    ## roles & budget
    @activity("roadmap_estimation_update")
    def updateRoadmapEstimation(self,tenant_id,user_id,roadmap_id,llm,logInfo,model_opts,socketio,client_id,step_sender):
        try:
            start = time.time()
            # Record essential tracking data
            record("user_id", user_id)
            record("tenant_id", tenant_id)
            record("roadmap_id", roadmap_id)
            record("description", "Updates roadmap with role recommendations and budget estimations. Analyzes available roles, suggests optimal team composition, calculates labor and non-labor costs. Input: roadmap details, available roles, tenant configuration. Output: recommended roles, team composition, detailed budget breakdown, and thought process analysis.")
            
            output = {}
            steps_sender_class = step_sender
            if roadmap_id is None:
                record("status", "error")
                record("error_message", "No roadmap_id provided")
                step_sender.sendError(key=f"Couldn't fetch roadmap details",function="updateRoadmapEstimation")
                return

            steps_sender_class.sendSteps("Fetching Roadmap Details", False)
            
            roadmap_details_ = RoadmapDao.fetchRoadmapDetails(roadmap_id=roadmap_id)
            roadmap_inputs = {
                "title": roadmap_details_[0].get("roadmap_title",""),
                "scope": roadmap_details_[0].get("roadmap_scope",""),
                "solution": roadmap_details_[0].get("roadmap_solution",""),
                "type": roadmap_details_[0].get("roadmap_type",""),
                "category": roadmap_details_[0].get("roadmap_category",""),
                "description": roadmap_details_[0].get("roadmap_description",""),
                "roadmap_start_date": roadmap_details_[0].get("roadmap_start_date"),
                "roadmap_end_date": roadmap_details_[0].get("roadmap_end_date"),
                "roadmap_objectives": roadmap_details_[0].get("roadmap_objectives"),
                "roadmap_portfolios": roadmap_details_[0].get("roadmap_portfolios"),
                "roadmap_state": roadmap_details_[0].get("roadmap_state")
            } if len(roadmap_details_) > 0 else {}
            # print("--debug parssed roadmap_details----------- 1", roadmap_inputs)
            # save_as_json(roadmap_details_, f"roadmap_details1_{roadmap_id}.json")

            roadmap_details = parse_roadmap_details(roadmap_inputs)
            # print("\n\n\n--debug parssed roadmap_details----------- 2", roadmap_details)
            # save_as_json(roadmap_details, f"roadmap_details2_{roadmap_id}.json")
            # return

            context = get_consolidated_persona_context_utils(tenant_id=tenant_id, user_id=user_id)

            tenant_formats = context.get("tenant_format",{}) or {}
            language = context.get("user_language","English") or "English"
            roadmapContext = {
                "customer_info": context.get("customer_info",{}) or {},
                "user_portfolios": context.get("user_portfolios",[]) or [],
                # "solutions_knowledge": context.get("solutions_knowledge",[]) or [],
            } 
            print("--debug Tenant Config: ", tenant_formats)             
            steps_sender_class.sendSteps("Fetching Roadmap Details", True)
            

            steps_sender_class.sendSteps("Analysing suitable roles", False)

            roadmap_portfolios = roadmap_details.get("roadmap_portfolios")
            roadmap_start_date = roadmap_details.get("roadmap_start_date")
            roadmap_end_date =  roadmap_details.get("roadmap_end_date")
            roadmap_state = roadmap_details.get("roadmap_state")
           
            role_inputs = compute_demand_estimation_inputs(
                tenant_id=tenant_id,
                roadmap_id=roadmap_id,
                roadmap_start_date=roadmap_start_date,
                roadmap_end_date=roadmap_end_date,
                roadmap_portfolios=roadmap_portfolios
            )
            # return
            available_roles = role_inputs.get("truly_available_roles",[])
            similar_portfolio_roles = role_inputs.get("roles_in_similar_portfolio",{})
            different_portfolio_roles = role_inputs.get("roles_in_different_portfolio",{})

            # all_roles = TenantDao.getDistinctAvailableRoles(tenant_id=tenant_id)
            # all_roles_count_master_data = TenantDao.getRoleCountForTenant(tenant_id=tenant_id)
            # all_roles_consumed_for_tenant = TenantDao.getAllRoadmapsRoleCountForTenant(tenant_id=tenant_id)
            # available_roles = OnboardingAgentUtils().calculate_available_roles(all_roles_count_master_data, all_roles_consumed_for_tenant)
            # # print("--debug available_roles---", available_roles, "\nAll roles: ", len(all_roles),"\nAll roles consumed: ", all_roles_consumed_for_tenant)
            # role_prompt = suggest_project_role_promptV2(
            #     project_details = json.dumps(roadmap_details),
            #     available_roles_details = json.dumps(all_roles),
            #     available_roles=json.dumps(available_roles),
            #     data_format = tenant_formats.get("currency_format",None) or None,
            #     language = language,
            #     context=roadmapContext
            # )

            role_prompt = suggest_project_role_promptV3(
                project_details = json.dumps(roadmap_details),
                available_roles = json.dumps(available_roles),
                similar_portfolio_roles = json.dumps(similar_portfolio_roles),
                other_portfolio_roles = json.dumps(different_portfolio_roles),
                data_format = tenant_formats.get("currency_format",None) or None,
                language = language,
                context=roadmapContext,
                demand_stage = roadmap_state,
            )
            # print("\n\n\n--debug [Role]prompt-----", role_prompt.formatAsString())
            # return
            # Record input data for role analysis
            input_data = {
                "roadmap_details_count": len(roadmap_details) if roadmap_details else 0,
                "available_roles_count": len(available_roles) if available_roles else 0,
                "currency_format": tenant_formats.get("currency_format", "Not specified"),
                "prompt_preview": role_prompt.formatAsString()[:500] + "..." if hasattr(role_prompt, 'formatAsString') else str(role_prompt)[:500] + "..."
            }
            record("input_data", input_data)
            
            response = llm.run_rl(role_prompt,self.modelOptions,"resource_planning_agent",
                'updateRoadmapEstimation::capacity_planner',logInDb = logInfo,socketio=socketio,client_id=client_id
            ) 
            suggested_roles_json = extract_json_after_llm(response,step_sender=steps_sender_class)
            for item in suggested_roles_json.get("recommended_project_roles",[]):
                item["labour_type"] = 1
                
            # print("\n--debug suggested_roles_json---", suggested_roles_json)
            steps_sender_class.sendSteps("Analysing suitable roles", True)
            
            roadmap_role_thought = suggested_roles_json.get("thought_process_behind_the_above_list", "")
            suggested_roles_json = suggested_roles_json.get("recommended_project_roles", []) or []
            
            appLogger.info({"event": "updateRoadmapEstimation:roles:done","data": len(suggested_roles_json),"roadmap_id": roadmap_id,"tenant_id": tenant_id,"user_id": user_id})
            
            roadmap_type = roadmap_details.get("type","")
            # print("\n\n--debug [RoadmapType]----------", roadmap_type)
            non_labour_team = []
            roadmap_timeline_thought = ""
            roadmap_non_labour_thought = ""
            
            if "Enhancement" in roadmap_type:
                print(f"--debug skipping non-labour estimation-----for roadmap {roadmap_id} & type: {roadmap_type}")
                pass
            else:
                steps_sender_class.sendSteps("Updating Roadmap Estimation", False)
                estimate_update_prompt = updateRoadmapEstimationPrompt(
                    json.dumps(roadmap_details),
                    tenant_formats.get("currency_format",None),
                    # user_id=user_id,
                    language = language,
                    context=roadmapContext
                )
                # print("--debug estimate_update_prompt---", estimate_update_prompt.formatAsString())
                # updated_estimate = self.llm.run(estimate_update_prompt, self.modelOptions , 'agent::roadmap_creation_agent', logInfo)
                updated_estimate = self.llm.run_rl(estimate_update_prompt, self.modelOptions ,'resource_planning_agent','agent::capacity_planner', logInfo,socketio=socketio,client_id=client_id)
                updated_estimate_json = extract_json_after_llm(updated_estimate,step_sender=steps_sender_class)
                print("response -- ", updated_estimate_json)
                
                non_labour_team = updated_estimate_json.get("non_labour_team",[])
                roadmap_timeline_thought = updated_estimate_json.get("thought_process_behind_timeline", "")
                roadmap_non_labour_thought = updated_estimate_json.get("thought_process_behind_non_labor_team", "")

                steps_sender_class.sendSteps("Updating Roadmap Estimation", True)
                
            appLogger.info({"event":"updateRoadmapEstimation:nonLabor:done,", "data": len(non_labour_team),"roadmap_id":roadmap_id})
            
            tango_analysis = {
                "thought_process_behind_labor_team": roadmap_role_thought,
                "thought_process_behind_non_labor_team": roadmap_non_labour_thought,
                "thought_process_behind_timeline": roadmap_timeline_thought,
            }

            output["tango_analysis"] = tango_analysis
            processed_roles = []
            for role in suggested_roles_json:
                processed_roles.extend(OnboardingAgentUtils().transform_role_data(role))
            
            team = non_labour_team + processed_roles if len(non_labour_team)>0 else processed_roles
            output["team"] = team
            
            #budget calculation
            steps_sender_class.sendSteps("Calculating budget", False)
            
            labour_budget = OnboardingAgentUtils().calculate_labour_budget_from_roles(suggested_roles_json)
            non_labour_budget = OnboardingAgentUtils().calculate_non_labour_budget_from_team(team)
            budget = labour_budget + non_labour_budget
            
            output["budget"] = budget
            steps_sender_class.sendSteps("Calculating budget", True)
             
            # Record output data for activity tracking
            output_data = {
                "suggested_roles_count": len(suggested_roles_json) if suggested_roles_json else 0,
                "team_members_count": len(output.get("team", [])),
                "budget_calculated": output.get("budget", 0),
                "labour_budget": labour_budget,
                "non_labour_budget": non_labour_budget,
                "tango_analysis_generated": bool(output.get("tango_analysis")),
                "processing_completed": True
            }
            record("output_data", output_data)
            
            self.updateRoadmapCreationTrackUtility(tenantID=tenant_id,userID=user_id,roadmap_id=roadmap_id,
                newly_completed_items = ["roles_budget"]               
            )
            
            elapsed_time = int(time.time() - start)
            socketio.emit("roadmap_creation_agent",{"event":"update_roadmap_estimation","data":output},room=client_id)
            appLogger.info({"event": "updateRoadmapEstimation::done","roadmap_id": roadmap_id,"tenant_id": tenant_id,"user_id": user_id,"time":elapsed_time})
            
            # with open("roadmap_estimation.json",'w') as file:
            #     json.dump(output,file,indent=4)
            return output
    
        except Exception as e:
            record("status", "error")
            record("error_message", str(e))
            step_sender.sendError(key=f"Error in estimation: {str(e)}",function="updateRoadmapEstimation")
            appLogger.error({"event":"updateRoadmapEstimation","error":e,"traceback":traceback.format_exc(),"roadmap_id":roadmap_id,"tenant_id":tenant_id,"user_id":user_id})            
    

    ### For EY demo    
    def create_roadmap_canvas(
        self,
        tenant_id:int,
        user_id:int,
        roadmap_stage: str = None,
        conversation=None,
        persona=None,
        org_info=None,
        org_alignment=None,
        portfolios=None,
        internal_knowledge=None,
        socketio=None,
        client_id=None,
        step_sender=None,
        guidance=None,
        **kwargs
    ):
        
        prompt = None
        start = time.time() 
        files_content = kwargs.get("files_content",None) or None
        quarter_tags = kwargs.get('quarter_tags',[]) or [] 
        # print("--debug create_roadmap_canvas------",quarter_tags)
        
        appLogger.info({"received_guidance": guidance, "tenant_id": tenant_id, "user_id": user_id, "stage": roadmap_stage})
        if roadmap_stage == "basic":
            if step_sender:
                step_sender.sendSteps("Gathering Demand Intake", False)
            all_roadmap_titles = RoadmapDao.FetchRoadmapNames(tenant_id)
            
            prompt = roadmapBasicInfoPrompt(
                conversation=conversation,
                persona=persona,
                org_info=org_info,
                org_alignment=org_alignment,
                portfolios=portfolios,
                quarter_tags=quarter_tags,
                all_roadmap_titles=all_roadmap_titles,
                tenant_id = tenant_id,
                user_id=user_id,
                files = files_content,
                guidance=guidance
            )
            # print("\n\n--debug [Basic] prompt-----", prompt.formatAsString())

        elif roadmap_stage == "okr":
            if step_sender:
                step_sender.sendSteps("Aligning with Company OKR(s)", False)
            
            prompt = roadmapObjOrgStrategyKeyResultsPrompt(
                roadmap_details=None,
                conversation=conversation,
                internal_knowledge=internal_knowledge,
                org_strategy=org_alignment,
                user_id=user_id,
                files = files_content,
                guidance=guidance
            )
            
        elif roadmap_stage == "cpc":
            if step_sender:
                step_sender.sendSteps("Analyzing Constraints & Categories", False)
            
            prompt = roadmapConstraintsPortfolioCategoryPrompt_ey(
                roadmap_details=None,
                internal_knowledge=internal_knowledge,
                portfolios=portfolios,
                conversation=conversation,
                persona=persona,
                tenant_id = tenant_id,
                user_id=user_id,
                files = files_content,
                guidance=guidance
            )
        if prompt:
            try:
                response = self.llm.run(prompt, self.modelOptions, 'agent::create_roadmap', logInDb={"tenant_id":tenant_id,"user_id":user_id},
                                socketio=socketio,client_id=client_id)
                with open(f"roadmap_canvas_{roadmap_stage}_{tenant_id}_{user_id}.txt",'w') as file:
                    file.write(prompt.formatAsString())
                    file.write("\n\n")
                    file.write(response)
                # print("response --- ", roadmap_stage, response)
                result = extract_json_after_llm(response,step_sender=step_sender)
                elapsed_time = int(time.time() - start)
                
                match roadmap_stage:
                    case "basic":
                        if step_sender:
                            step_sender.sendSteps("Gathering Demand Intake", True)
                    case "okr":
                        if step_sender:
                            step_sender.sendSteps("Aligning with Company OKR(s)",True)
                    case "cpc":
                        if step_sender:
                            step_sender.sendSteps("Analyzing Constraints & Categories", True)
                        
                print(f"\n\n--debug Time taken for {roadmap_stage}: ", elapsed_time)
                appLogger.info({"event":"create_roadmap_canvas","stage": roadmap_stage,"time": elapsed_time,"tenant_id":tenant_id,"user_id":user_id})
                return result
            except Exception as e:
                appLogger.error({"event":"create_roadmap_canvas","stage": roadmap_stage,"tenant_id":tenant_id,"user_id":user_id,"error":e,"traceback":traceback.format_exc()})
                return {}
        else:
            appLogger.info({"event":"create_roadmap_canvas","stage": roadmap_stage,"msg": "no prompt found"})
            return None
    

    
    
    def createRoadmap2_ey(self,tenantID, userID,roadmap_id,socketio,client_id,llm,model_opts,logInfo,step_sender,session_id=None):
        #for scope & timeline
        try:
            start = time.time()  # Record start time
            steps_sender_class = step_sender
            steps_sender_class.sendSteps("Gathering Roadmap Information", False)
            
            solutions = TenantDao.listCustomerSolutions(tenant_id=tenantID)
            
            roadmap_details =RoadmapDao.fetchRoadmapDetails(roadmap_id=roadmap_id)
            roadmap_portfolio = roadmap_details[0].get("roadmap_portfolios",[]) if len(roadmap_details)>0 else []

            print("--debug roadmap_portoflio----", roadmap_portfolio)

            solution_context = []
            for sol in solutions:
                new_sol = {k: v for k, v in sol.items() if k not in ["additional_details","id","tenant_id","application_type","service_line"]}
                new_sol["type"] = sol["application_type"] if "application_type" in sol else "NA"
                new_sol["portfolio"] = sol["service_line"] if "service_line" in sol else "NA"

                if len(roadmap_portfolio)>0:
                    for portfolio in roadmap_portfolio:
                        service_line = sol.get("service_line") or ""
                        if len(service_line)>0 and portfolio.lower() in service_line.lower():
                            solution_context.append(new_sol)
                else:
                    continue

            conv_ = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id=session_id, user_id=userID, key="create_roadmap_conv")
            conv = conv_[0].get("value","") if len(conv_)>0 else {}

            uploaded_files = FileDao.s3ToOriginalFileMapping(sessionID =session_id,userID=userID, file_type='DEMAND_FILE_UPLOAD') 
            file_content = process_uploaded_files(FileAnalyzer(tenant_id=tenantID),uploaded_files,step_sender=steps_sender_class,source='scope')    

            steps_sender_class.sendSteps("Gathering Roadmap Information", True)
            print("--debug createRoadmap2_ey_context------ Conv: ", len(conv), uploaded_files)

            # Get pattern inference for scope guidance
            try:
                # Build roadmap_data dict for inference
                roadmap_dict = roadmap_details[0] if roadmap_details else {}
                roadmap_data = {
                    "name": roadmap_dict.get('roadmap_name', ''),
                    "description": roadmap_dict.get('roadmap_description', ''),
                    "roadmap_type": roadmap_dict.get('roadmap_type', 'New Development'),
                    "priority": roadmap_dict.get('priority', 'High'),
                    "portfolios": roadmap_portfolio,
                    "conversation": conv,
                    "business_problem": roadmap_dict.get('business_problem', ''),
                    "success_criteria": roadmap_dict.get('success_criteria', '')
                }
                
                # Check if knowledge is integrated for this tenant
                scope_guidance = None
                graphname = is_knowledge_integrated(tenantID)
                print("--debug knowledge graph for tenant---", graphname)
                if graphname:
                    try:
                        inference_result = infer_roadmap(
                            roadmap_data=roadmap_data,
                            graphname=graphname,
                            tenant_id=tenantID
                        )
                        print("--debug inference_result for scope guidance---", inference_result)
                        
                        if inference_result and inference_result.get('inference_status') == 'success':
                            stage_guidance = format_guidance_for_canvas_stages(inference_result)
                            # For scope, use basic stage guidance (timeline, business value)
                            scope_guidance = stage_guidance.get("basic", {})
                            scope_guidance["prompt_section"] = format_basic_stage_prompt_section(scope_guidance)
                            print("--debug scope_guidance---", scope_guidance)
                    except Exception as e:
                        appLogger.warning({
                            "event": "roadmap_scope_inference_error",
                            "tenant_id": tenantID,
                            "error": str(e)
                        })
                        scope_guidance = None
                else:
                    appLogger.info({
                        "event": "roadmap_knowledge_not_integrated",
                        "tenant_id": tenantID,
                        "using_default_flow": True
                    })
            except Exception as e:
                appLogger.error({
                    "event": "roadmap_scope_guidance_error",
                    "tenant_id": tenantID,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
                scope_guidance = None

            steps_sender_class.sendSteps("Analyzing Scope Requirements", False)                
            prompt = roadmapScopeTimelinePrompt(
                roadmap_details = roadmap_details,
                conversation = json.dumps(conv,indent=2),
                files= json.dumps(file_content,indent=2),
                user_id=userID,
                solution_context = json.dumps(solution_context,indent=2),
                guidance=scope_guidance
            )
            
            # print("\n--debug [Scope] prompt-----", prompt.formatAsString())

            response = self.llm.run(prompt, self.modelOptions,'agent::create_roadmap', logInDb = logInfo,socketio=socketio,client_id=client_id)
            
            result = extract_json_after_llm(response,step_sender=steps_sender_class)
            
            #Remove timeline data 
            result.pop('start_date',None)
            result.pop('end_date',None)
            result.pop('min_time_value',None)
            result.pop('min_time_value_type',None)
            result.pop('thought_process_behind_timeline',None)

            
            # print("--debug result scope---", result)
            steps_sender_class.sendSteps("Analyzing Scope Requirements", True)
            # steps_sender_class.sendSteps("Building Roadmap Timeline", True)
            
            elapsed_time = int(time.time() - start)  # Calculate time taken
            print("--debug time taken createRoadmap2_ey----", elapsed_time)
            self.updateRoadmapCreationTrackUtility(tenantID=tenantID,userID=userID,roadmap_id=roadmap_id,
                    newly_completed_items = ["scope_timeline"]
            )
            
            socketio.emit("roadmap_creation_agent",{"event":"roadmap_scope","data":result,"session_id":session_id,"roadmap_id": roadmap_id},room=client_id)
            appLogger.info({"event": "createRoadmap2_ey","roadmap_id": roadmap_id, "msg": "done", "time": elapsed_time})
        except Exception as e:
            step_sender.sendError(key=f"Error generating scope: {str(e)}",function="createRoadmap2_ey")
            appLogger.error({"event": "createRoadmap2_ey", "error": e,"roadmap_id": roadmap_id, "traceback": traceback.format_exc()})
            
        return
    
    
    
    def createDemandInsights(self,roadmap_canvas,tenant_id,user_id,step_sender=None):
        
        try:
            portfolios = (roadmap_canvas.get("cpc") or {}).get("portfolio") or [] or roadmap_canvas.get("portfolio_list") or [{"name":"none"}]
            print("----debug canvas_portfolios------", portfolios)
            
            # 4 dimensions: Scope overlaps,# . Soln dimension, # . Business value, #Others
            existing_roadmaps = RoadmapDao.fetchRoadmapDetailsV2FOrPortfolioReview(tenant_id=tenant_id)
            ey_solutions_ = TenantDao.listCustomerSolutions(tenant_id)
            ey_solutions = _process_solutions(ey_solutions_)
            created_canvas = roadmap_canvas
            
            ey_sols_delivered = TenantDao.listCustomerSolutionsDelivered(tenant_id)
            #fetch delivered sols for portfolio gen now in the canvas
            grp_delivered_sols = groupSolutionsDeliveredByPortfolio(ey_sols_delivered,portfolios) or {}
            appLogger.info({"event":"grp_delivered_sols","data": next(iter(grp_delivered_sols), None),"tenant_id":tenant_id,"user_id":user_id})
            # print("\n\n--deubg ey_sols------", grp_delivered_sols)
            
            prompt = demandInsightsPrompt(
                roadmap_canvas = json.dumps(created_canvas,indent=4),
                solutions = json.dumps(ey_solutions,indent=2),
                existing_roadmaps = json.dumps(existing_roadmaps,indent=2),
                delivered_solutions = json.dumps(grp_delivered_sols,indent=2),
                user_id=user_id
            )
            # print("\n--debug [Scope] prompt-----", prompt.formatAsString())

            response = self.llm.run(prompt, self.modelOptions,'agent::create_roadmapinsights', logInDb={"tenant_id":tenant_id,"user_id":user_id})
            result = extract_json_after_llm(response,step_sender=step_sender)
            
            # print("--debug result [sol insights]---", result)        
            appLogger.info({"event": "createSolutionInsights", "msg": "done","tenant_id":tenant_id,"user_id":user_id})
            return result
        
        except Exception as e:
            if step_sender:
                step_sender.sendError(key=f"Error generating demand insights",function="createSolutionInsights")
            appLogger.error({"event": "createSolutionInsights", "error": e, "traceback": traceback.format_exc(),"tenant_id":tenant_id,"user_id":user_id})
            return None
    


    ### Create History view or Audit Log for Demand change
    def createDemandAuditHistory(self,tenant_id,user_id,roadmap_id,socketio,client_id,step_sender=None,cache_seconds=86400*10):

        if not roadmap_id:
            return {}
        try:
            insights = TangoDao.fetchTangoStatesTenant(tenant_id=tenant_id, key=f"roadmap_auditlog_{roadmap_id}", _limit=1)
            if len(insights)==0 or (len(insights)>0 and insights[0]["created_date"] is not None and (datetime.now(timezone.utc) - datetime.fromisoformat(insights[0]["created_date"])).seconds > cache_seconds):
            
                audit_logs = TenantDao.fetchAuditLogData(
                    projection_attrs=["model_name","action","changes","timestamp","user_id"],
                    object_id=roadmap_id,
                    model_name = "Roadmap",
                    tenant_id = tenant_id
                )
                # print("\n\n--debug audit_logs------", audit_logs[:2])

                if not audit_logs:
                    socketio.emit("roadmap_creation_agent",{"event":"roadmap_logs","data":"No data found","roadmap_id": roadmap_id},room=client_id)
                    return

                for log in audit_logs:
                    user_id = log.get('user_id')
                    timestamp = log.get('timestamp',"")
                    changes = json.dumps(log.get('changes',{}) or {})
                    log.pop("user_id",None)
                    log.pop("changes",None)
                    log.pop("timestamp",None)
                    
                    user_info = UsersDao.fetchUserInfoWithId(user_id)
                    user_name = (user_info["first_name"] + " " + user_info.get("last_name","")) if user_info else "Unknown"
                    log["changes"] = changes
                    log["user_name"] = user_name
                    log["timestamp"] = datetime.fromisoformat(timestamp.rstrip('Z')).strftime("%Y-%m-%d %H:%M:%S") if timestamp else ""
                    # print("---debug log---", log["user_name"],log["timestamp"],log["action"])
                
                insights_val = json.loads(insights[0]["value"]) if len(insights)>0 else []
                all_users = TenantDao.FetchUsersOfTenant(tenant_id=tenant_id)
                user_mapping = {}
                for user in all_users:
                    user_mapping[user["user_id"]] = user["first_name"]

                # print("\n\n--debug user_mapping-------", user_mapping)

                prompt = changeHistoryPrompt(
                    audit_logs = json.dumps(audit_logs),
                    user_id=user_id, 
                    existing_insights = insights_val,
                    user_mapping = user_mapping
                )
                response = self.llm.run(prompt, self.modelOptions1,'agent::roadmap_logs', logInDb={"tenant_id":tenant_id,"user_id":user_id})

                # print("\n\n--debug response changelog---", response)
                result = extract_json_after_llm(response,step_sender=step_sender)

                data = result.get("change_logs",[]) or []
                data =  data + insights_val
                TangoDao.upsertTangoState(
                    tenant_id=tenant_id, user_id=None, key=f"roadmap_auditlog_{roadmap_id}",
                    value=json.dumps(data), session_id=None
                )
            else:
                insights_val = insights[0]["value"]
                created_date = insights[0]["created_date"]
                print("--debug insight already there------", len(insights_val))
                
                appLogger.info({"event":"create_auditLog","msg":"Insights present","created_date":created_date,"roadmap_id":roadmap_id,"tenant_id":tenant_id})
                data = json.loads(insights_val) or []

            logs = parse_auditlog_response(data)
            socketio.emit("roadmap_creation_agent",{"event":"roadmap_logs","data":logs,"roadmap_id": roadmap_id},room=client_id)
            return
        except Exception as e:
            step_sender.sendError(key="Error creating changelogs",function="createDemandAuditHistory")
            appLogger.error({"event": "createDemandHistory","error": str(e),"traceback":traceback.format_exc()})
            
    
        
    def fetchScopeDriveIntegration(self,tenant_id,user_id,roadmap_id,docs,socketio,client_id,logInfo,key,step_sender=None):
        try:
            # print("--debug values : ", tenant_id, user_id, roadmap_id,"--------------", docs)
            # appLogger.info({"event": "fetchScopeDriveIntegration", "data": len(docs)})
            if key:
                print("\ndebug -- s3key --- ", key)
                
                file_content = self.s3_service.download_file_as_text(s3_key=key)
                if file_content is None:
                    print(f"Skipping file {key} due to download error.")
                    step_sender.sendError(key=f"Error downloading the file.",function="fetchScopeDriveIntegration")
                    # socketio.emit("roadmap_creation_agent",{"event":"fetchScopeDriveIntegration","data":"No data","roadmap_id":roadmap_id},room=client_id)
                
                summarizer_service = SummarizerService(logInfo=logInfo)
                document = summarizer_service.summarizer(
                    large_data = file_content,
                    message = "This is a document to generate the Project scope fetch all the necessary details.",
                    identifier = "files_uploaded"
                )
                
                # with open("scope_doc.json", 'w') as file:
                #         json.dump(document, file, indent=4)
                
                customer_context = CustomerDao.getCustomerProfileDetails(tenant_id)
                roadmap_details = RoadmapDao.fetchRoadmapDetails(roadmap_id) 
                
                roadmap_scope = []
                if document:        
                    prompt = driveRoadmapScopePrompt(
                        customer_context = customer_context,
                        roadmap_details = roadmap_details,
                        document = document
                    )
                    
                    print("\n--debug calling LLM for Scope===")
                    response = self.llm.run(prompt, self.modelOptions,'agent::roadmap_scope', logInDb = logInfo,socketio=socketio,client_id=client_id)
                    result = extract_json_after_llm(response,step_sender=step_sender)
                    # print("\n\n--debug scope result----", result)
                    
                    # with open("roadmap_scope.json", 'w') as file:
                    #     json.dump(result, file, indent=4)
                    
                    
                    scope = result.get("scope_item",{})
                    transformed_scope = {
                        "scope" : {"name": f"""{scope.get("name")}\n {scope.get("combined_details_out_of_scope_in_markdown_format")}"""}
                    }
                    roadmap_scope.append(transformed_scope)
                
                print("\n\n [Roadmap Scope]------", roadmap_scope)
                socketio.emit("roadmap_creation_agent",{"event":"fetchScopeDriveIntegration","data":roadmap_scope,"roadmap_id":roadmap_id},room=client_id)
                    
                
            else:
                refresh_token =self.refreshTokenService.refreshIntegrationAccessToken(tenantId=tenant_id,userId=user_id,integrationType="drive")
                appLogger.info({"event": "fetchScopeDriveIntegration", "data": refresh_token})
                
                scope = DriveV2(user_id = user_id,tenant_id = tenant_id,project_id=roadmap_id,
                    metadata= {'refresh_token': refresh_token.get("refresh_token",None)},access_token =None
                ).generateInsights(
                    file_type="docs",
                    docs = docs,
                    slides = None
                )
                # print("debug -- scope --- ", scope)
                
                socketio.emit("roadmap_creation_agent",{"event":"fetchScopeDriveIntegration","data":scope,"roadmap_id":roadmap_id},room=client_id)
            appLogger.info({"event": "fetchScopeDriveIntegration", "msg": "done"})
            
        except Exception as e:
            step_sender.sendError(key=f"Error generating scope: {str(e)}",function="fetchScopeDriveIntegration")
            appLogger.error({"event": "fetchScopeDriveIntegration","error":  e,"traceback": traceback.format_exc()})
            return {}



    ###Old roadmap flow below: 

















































    ##Old create roadmap flow: split stages    
    def getCreateRoadmapSessionID(self,tenantID,userID,roadmap_id):
    
        sessionID_data = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id='', user_id=userID, key="create_roadmap_sessionID")
        if len(sessionID_data) > 0:
            
            sessionID = sessionID_data[0]['value']
            # print("--debug values : ", sessionID, userID, roadmap_id)
            
            TangoDao.insertTangoState(tenant_id=tenantID, user_id=userID,
                key=f"create_roadmap_sessionID_{roadmap_id}", value= sessionID,
                session_id=''
            )
        
            return sessionID
        else:
            return ""
    
    
    def fetchCreateRoadmapInfo(self,sessionID,userID):
        
        # create_roadmap_basicInfo : name , desc, internal knowledge
        # create_roadmap_personaPortfolioOrgStrategy : persona, portfolio, org strategy
        # create_roadmap_conv: roadmap create conv
        try:
            print("--debug insidefetchCreateRoadmapInfo----------", sessionID,userID)
            conv = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id=sessionID, user_id=userID, key="create_roadmap_conv")
            
            basic_info = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id=sessionID, user_id=userID, key="create_roadmap_basicInfo")
            basic_info_data = json.loads(basic_info[0]['value'])
            # print("--debug [Basic Info]---", basic_info_data,'\n\n')
            
            
            others = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id=sessionID, user_id=userID, key="create_roadmap_personaPortfolioOrgStrategy")
            others_data = json.loads(others[0]['value'])
            # print("--debug others info---", others_data)
            
            roadmap_info = {
                "create_roadmap_conv": conv,
                "roadmap_name_description": f"""" Roadmap : {basic_info_data["basic_info"].get('RoadmapName')}\n Description: {basic_info_data["basic_info"].get('Description')}""",
                "internal_knowledge": basic_info_data.get("internal_knowledge",[]),
                "customer_persona": others_data.get("customer_persona",{}),
                "portfolio": others_data.get("portfolios",[]),
                "org_strategy": others_data.get("org_strategy",[])
            }
            
            # print("\n\n--debug roadmap_info111111---", roadmap_info)
            
            appLogger.info({"event":"fetchCreateRoadmapInfo","msg": "done","user_id": userID})
            return roadmap_info
        
        except Exception as e:
            appLogger.error({"event": "fetchCreateRoadmapInfo", "error": e, "traceback": traceback.format_exc()})
            return {"create_roadmap_conv":[],"roadmap_name_description":"","internal_knowledge":[],"customer_persona":{},"portfolio":[],"org_strategy":[]}
    
    
    @activity("roadmap_creation_stage1")
    def createRoadmap1(self,tenantID, userID,roadmap_id,socketio,client_id,llm,model_opts,logInfo,step_sender):
        #for get objective + org strategy + key result + thought process
        try:
            # Record essential tracking data
            record("description", "Stage 1 of roadmap creation: Generates project objectives, organizational strategy alignment, and key results based on user conversations and internal knowledge. Input: basic roadmap info, Q&A conversations, org strategy. Output: structured objectives, key results, and strategy alignment analysis.")
            record("session_id", self.getCreateRoadmapSessionID(tenantID,userID,roadmap_id))
            record("user_id", userID)
            record("tenant_id", tenantID)
            record("roadmap_id", roadmap_id)
            
            start = time.time()  # Record start time
            sessionID = self.getCreateRoadmapSessionID(tenantID,userID,roadmap_id)
            steps_sender_class = step_sender
            
            steps_sender_class.sendSteps("Gathering Roadmap Information", False)
            roadmap_info = self.fetchCreateRoadmapInfo(sessionID, userID)
            # print("--debug roadmap info---", roadmap_info)
            
            basic_info = roadmap_info.get("roadmap_name_description",{})
            conv = roadmap_info.get("create_roadmap_conv",[])
            internal_knowledge = roadmap_info.get("internal_knowledge",[])
            org_strategy = roadmap_info.get("org_strategy",[])
            steps_sender_class.sendSteps("Gathering Roadmap Information", True)
            
            appLogger.info({"event": "createRoadmap1", "msg": "start","roadmap_id": roadmap_id})
            # portfolios = roadmap_info.get("portfolio",[])
            # persona = roadmap_info.get("customer_persona",{})
            # all_portfolios = RoadmapDao.fetchAllPortfolioOfTenant(tenant_id=tenantID)
            
            steps_sender_class.sendSteps("Defining Project Objectives", False)
            steps_sender_class.sendSteps("Thinking Through Key Results", False)
            
            steps_sender_class.sendSteps("Aligning with Company Strategy", False)
                
            prompt = roadmapObjOrgStrategyKeyResultsPrompt(
                roadmap_details = basic_info,
                conversation = conv,
                internal_knowledge = internal_knowledge,
                org_strategy = org_strategy,
                user_id=userID
            )
            # print("\n--debug prompt1-----", prompt.formatAsString())

            # Record input data for activity tracking
            input_data = {
                "roadmap_details": basic_info,
                "conversation_length": len(conv) if conv else 0,
                "internal_knowledge_count": len(internal_knowledge) if internal_knowledge else 0,
                "org_strategy_count": len(org_strategy) if org_strategy else 0,
                "prompt_preview": prompt.formatAsString()[:500] + "..." if hasattr(prompt, 'formatAsString') else str(prompt)[:500] + "..."
            }
            record("input_data", input_data)

            response = self.llm.run(prompt, self.modelOptions,'agent::create_roadmap', logInDb = logInfo,socketio=socketio,client_id=client_id)
            
            result = extract_json_after_llm(response,step_sender=steps_sender_class)
            
            # Record output data for activity tracking
            output_data = {
                "objectives_generated": len(result.get("objectives", [])) if isinstance(result, dict) and result.get("objectives") else 0,
                "key_results_generated": len(result.get("key_results", [])) if isinstance(result, dict) and result.get("key_results") else 0,
                "org_strategy_alignment": result.get("org_strategy_align", "") if isinstance(result, dict) else "",
                "result_preview": str(result)[:500] + "..." if result else "No result generated"
            }
            record("output_data", output_data)
            
            # print("--debug result scope---", result)
            steps_sender_class.sendSteps("Defining Project Objectives", True)
            steps_sender_class.sendSteps("Thinking Through Key Results", True)
            
            steps_sender_class.sendSteps("Aligning with Company Strategy", True)
            
            elapsed_time = int(time.time() - start)  # Calculate time taken
            record("processing_time_seconds", elapsed_time)
            
            # print("--debug time taken roadmapObjOrgStrategyKeyResults----", elapsed_time)
            steps_sender_class.sendSteps(f"Time taken:{elapsed_time} seconds", False, elapsed_time)
            steps_sender_class.sendSteps(f"Time taken:{elapsed_time} seconds", True, elapsed_time)
            
            self.updateRoadmapCreationTrackUtility(tenantID=tenantID,userID=userID,roadmap_id=roadmap_id,
                    newly_completed_items = ["roadmap_name_description","objective_orgStrategy_keyResult"]               
            )
            
            socketio.emit("roadmap_creation_agent",{"event":"roadmap_ObjOrgStrategyKeyResults","data":result,"session_id":sessionID,"roadmap_id": roadmap_id},room=client_id)
            appLogger.info({"event": "createroadmap1", "msg": "done", "time": elapsed_time})
        except Exception as e:
            record("status", "error")
            record("error_message", str(e))
            print("error in createRoadmap1", e, traceback.format_exc())
            step_sender.sendError(key=f"Error creating roadmap: {str(e)}",function="createRoadmap1")
            appLogger.error({"event": "createRoadmap1", "error": e, "traceback": traceback.format_exc()})
                    
        return 
    
    
    
    @activity("roadmap_creation_stage2")
    def createRoadmap2(self,tenantID, userID,roadmap_id,socketio,client_id,llm,model_opts,logInfo,step_sender):
        #for scope & timeline
        
        try:
            # Record essential tracking data
            record("description", "Stage 2 of roadmap creation: Defines project scope and timeline based on user requirements, internal knowledge, customer personas, and portfolio context. Input: roadmap details, conversations, personas, portfolios. Output: detailed scope items, project timeline with start/end dates, and deliverables breakdown.")
            record("session_id", self.getCreateRoadmapSessionID(tenantID,userID,roadmap_id))
            record("user_id", userID)
            record("tenant_id", tenantID)
            record("roadmap_id", roadmap_id)
            
            start = time.time()  # Record start time
            sessionID = self.getCreateRoadmapSessionID(tenantID,userID,roadmap_id)
            steps_sender_class = step_sender
            
            steps_sender_class.sendSteps("Gathering Roadmap Information", False)
            roadmap_info = self.fetchCreateRoadmapInfo(sessionID, userID)
            # print("--debug roadmap info---", roadmap_info)
            
            conv = roadmap_info.get("create_roadmap_conv",[])
            basic_info = roadmap_info.get("roadmap_name_description",{})
            internal_knowledge = roadmap_info.get("internal_knowledge",[])
            portfolios = roadmap_info.get("portfolio",[])
            # org_strategy = roadmap_info.get("org_strategy",[])
            persona = roadmap_info.get("customer_persona",{})
            steps_sender_class.sendSteps("Gathering Roadmap Information", True)
            
            
            steps_sender_class.sendSteps("Analyzing Scope Requirements", False)
            steps_sender_class.sendSteps("Building Roadmap Timeline", False)
                
            prompt = roadmapScopeTimelinePrompt(
                roadmap_details = basic_info,
                internal_knowledge = internal_knowledge,
                persona = persona,
                portfolios = portfolios,
                conversation = conv,
                user_id=userID
            )
            # print("\n--debug [Scope] prompt-----", prompt.formatAsString())

            # Record input data for activity tracking
            input_data = {
                "roadmap_details": basic_info,
                "conversation_length": len(conv) if conv else 0,
                "internal_knowledge_count": len(internal_knowledge) if internal_knowledge else 0,
                "portfolios_count": len(portfolios) if portfolios else 0,
                "persona_provided": bool(persona),
                "prompt_preview": prompt.formatAsString()[:500] + "..." if hasattr(prompt, 'formatAsString') else str(prompt)[:500] + "..."
            }
            record("input_data", input_data)
            response = self.llm.run(prompt, self.modelOptions,'agent::create_roadmap', logInDb = logInfo,socketio=socketio,client_id=client_id)
            
            result = extract_json_after_llm(response,step_sender=steps_sender_class)
            
            # Record output data for activity tracking
            output_data = {
                "scope_items_generated": len(result.get("scope", [])) if isinstance(result, dict) and result.get("scope") else 0,
                "timeline_defined": bool(result.get("start_date") and result.get("end_date")) if isinstance(result, dict) else False,
                "start_date": result.get("start_date", "") if isinstance(result, dict) else "",
                "end_date": result.get("end_date", "") if isinstance(result, dict) else "",
                "deliverables_count": len(result.get("deliverables", [])) if isinstance(result, dict) and result.get("deliverables") else 0,
                "result_preview": str(result)[:500] + "..." if result else "No result generated"
            }
            record("output_data", output_data)
            
            # print("--debug result scope---", result)
            steps_sender_class.sendSteps("Analyzing Scope Requirements", True)
            steps_sender_class.sendSteps("Building Roadmap Timeline", True)
            
            elapsed_time = int(time.time() - start)  # Calculate time taken
            record("processing_time_seconds", elapsed_time)
            
            steps_sender_class.sendSteps(f"""Time taken:{elapsed_time} seconds""", False, elapsed_time)
            steps_sender_class.sendSteps(f"""Time taken:{elapsed_time} seconds""", True, elapsed_time)
            
            
            self.updateRoadmapCreationTrackUtility(tenantID=tenantID,userID=userID,roadmap_id=roadmap_id,
                    newly_completed_items = ["scope_timeline"]
            )
            
            socketio.emit("roadmap_creation_agent",{"event":"roadmap_scope","data":result,"session_id":sessionID,"roadmap_id": roadmap_id},room=client_id)
            appLogger.info({"event": "createroadmap2", "msg": "done", "time": elapsed_time})
        except Exception as e:
            record("status", "error")
            record("error_message", str(e))
            print("error in createRoadmap2", e, traceback.format_exc())
            step_sender.sendError(key=f"Error creating roadmap: {str(e)}",function="createRoadmap2")
            appLogger.error({"event": "createRoadmap2", "error": e, "traceback": traceback.format_exc()})
            
        return
    
    @activity("roadmap_creation_stage3")
    def createRoadmap3(self,tenantID, userID,roadmap_id,socketio,client_id,llm,model_opts,logInfo,step_sender):
        """#constraints + portfolio + category + thought process"""
        
        try:
            # Record essential tracking data
            record("description", "Stage 3 of roadmap creation: Analyzes project constraints, portfolio alignment, and categorization. Input: roadmap details, conversations, internal knowledge, portfolios, personas. Output: identified constraints, portfolio item mappings, project categories, and strategic thought process analysis.")
            record("session_id", self.getCreateRoadmapSessionID(tenantID,userID,roadmap_id))
            record("user_id", userID)
            record("tenant_id", tenantID)
            record("roadmap_id", roadmap_id)
            
            start = time.time()  # Record start time
            sessionID = self.getCreateRoadmapSessionID(tenantID,userID,roadmap_id)
            steps_sender_class = step_sender
            
            roadmap_info = self.fetchCreateRoadmapInfo(sessionID, userID)
            # print("--debug roadmap info---", roadmap_info)
            
            steps_sender_class.sendSteps("Analyzing Roadmap Constraints", False)
            conv = roadmap_info.get("create_roadmap_conv",[])
            basic_info = roadmap_info.get("roadmap_name_description",{})
            internal_knowledge = roadmap_info.get("internal_knowledge",[])
            # org_strategy = roadmap_info.get("org_strategy",[])
            portfolios = roadmap_info.get("portfolio",[])
            persona = roadmap_info.get("customer_persona",{})
            
            steps_sender_class.sendSteps("Analyzing Roadmap Constraints", True)
            
            # web_search,samay = self.roadmapWebSearch(roadmap_info,llm,model_opts,logInfo)
            samay = 0
            # print("--debug websearch time", samay)
            
            steps_sender_class.sendSteps("Reviewing Portfolio Details", False)
            steps_sender_class.sendSteps("Organizing Roadmap Categories", False)
                
            prompt = roadmapConstraintsPortfolioCategoryPrompt(
                roadmap_details = basic_info,
                # web_search = web_search,
                internal_knowledge = internal_knowledge,
                portfolios = portfolios,
                conversation = conv,
                persona = persona
            )
            # print("--debug prompt3-----", prompt.formatAsString())

            # Record input data for activity tracking
            input_data = {
                "roadmap_details": basic_info,
                "conversation_length": len(conv) if conv else 0,
                "internal_knowledge_count": len(internal_knowledge) if internal_knowledge else 0,
                "portfolios_count": len(portfolios) if portfolios else 0,
                "persona_provided": bool(persona),
                "prompt_preview": prompt.formatAsString()[:500] + "..." if hasattr(prompt, 'formatAsString') else str(prompt)[:500] + "..."
            }
            record("input_data", input_data)

            response = self.llm.run(prompt, self.modelOptions,'agent::create_roadmap', logInDb = logInfo,socketio=socketio,client_id=client_id)
            result = extract_json_after_llm(response,step_sender=steps_sender_class)
            # print("--debug result constriantsPortfolioCategory--------", result)
            
            # Record output data for activity tracking
            output_data = {
                "constraints_generated": len(result.get("constraints", [])) if isinstance(result, dict) and result.get("constraints") else 0,
                "portfolio_items_generated": len(result.get("portfolio_items", [])) if isinstance(result, dict) and result.get("portfolio_items") else 0,
                "categories_generated": len(result.get("categories", [])) if isinstance(result, dict) and result.get("categories") else 0,
                "result_preview": str(result)[:500] + "..." if result else "No result generated"
            }
            record("output_data", output_data)
            
            steps_sender_class.sendSteps("Reviewing Portfolio Details", True)
            steps_sender_class.sendSteps("Organizing Roadmap Categories", True)
            
            elapsed_time = int(time.time() - start)
            record("processing_time_seconds", elapsed_time)
            
            print("--debug time taken roadmapConstraintsPortfolioCategoryPrompt----", elapsed_time)
            steps_sender_class.sendSteps(f"Time taken:{elapsed_time} seconds", True, elapsed_time+samay)
            
            
            self.updateRoadmapCreationTrackUtility(tenantID=tenantID,userID=userID,roadmap_id=roadmap_id,
                newly_completed_items = ["constraints_portfolio_category"]               
            )
            
            socketio.emit("roadmap_creation_agent",{"event":"roadmap_constraintsPorfolioCategory","data":result,"session_id":sessionID,"roadmap_id": roadmap_id},room=client_id)
            appLogger.info({"event": "createroadmap3", "msg": "done", "time": elapsed_time})
        except Exception as e:
            record("status", "error")
            record("error_message", str(e))
            print("error in createRoadmap3", e, traceback.format_exc())
            step_sender.sendError(key=f"Error creating roadmap: {str(e)}",function="createRoadmap3")
            appLogger.error({"event": "createRoadmap3", "error": e, "traceback": traceback.format_exc()})
                    
        return 
    
    
    
    ## update roadmap canvas
    def updateRoadmapCanvas(self,tenant_id,user_id,roadmap_id,logInfo,llm,model_opts,socketio,client_id,step_sender):
        try:
            
            start = time.time()  # Record start time
            steps_sender_class = step_sender
            
            sessionID = self.getCreateRoadmapSessionID(tenant_id,user_id,roadmap_id)
            step_sender.sendSteps("Gathering Roadmap Information", False)
            
            create_roadmap_info = self.fetchCreateRoadmapInfo(sessionID, user_id)
            db_roadmap_info = RoadmapDao.fetchRoadmapDetails(roadmap_id=roadmap_id)
            
            tenant_config = TenantDao.getTenantInfo(tenant_id=tenant_id)
            tenant_config_res = tenant_config[0]['configuration']
            
            tenant_formats = {}
            if tenant_config_res is not None:
                tenant_formats["currency_format"] = tenant_config_res.get("currency",{})
                tenant_formats["date_format"] = tenant_config_res.get("date_time",{})
                
            appLogger.info({"event": "tenant_config", "data": tenant_formats,"tenant_id": tenant_id})
            step_sender.sendSteps("Bringing Internal Knowledge", False)
            
            internal_knowledge = create_roadmap_info.get("internal_knowledge",[])
            portfolios = create_roadmap_info.get("portfolio",[])
            org_strategy = create_roadmap_info.get("org_strategy",[])
            currency_format = tenant_formats.get("currency_format",None)
            
            step_sender.sendSteps("Gathering Roadmap Information", True)
            step_sender.sendSteps("Bringing Internal Knowledge", True)
            
            step_sender.sendSteps("Updating Roadmap Canvas", False)
            ## want to execute these two prompt in parallel using threadpool executor
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                #1. Update Roadmap Canvas
                future_canvas = executor.submit(
                    self._update_canvas_task,
                    db_roadmap_info, internal_knowledge, portfolios, org_strategy, currency_format,
                    logInfo, steps_sender_class
                )
                #2. Update Roles Estimation
                future_roles = executor.submit(
                    self._update_roles_estimation_task,
                    tenant_id, user_id, db_roadmap_info, tenant_formats, llm, model_opts, logInfo, steps_sender_class
                )

                canvas_result = future_canvas.result()
                roles_result = future_roles.result()

            # Budget calculation after both LLM
            steps_sender_class.sendSteps("Calculating budget", False)
            
            non_labour_team = canvas_result.get("non_labour_team", [])
            suggested_roles = roles_result.get("suggested_roles", [])
            processed_roles = roles_result.get("processed_roles", [])
            team = non_labour_team + processed_roles

            print("\n--debug [Team]---",team)
            labour_budget = OnboardingAgentUtils().calculate_labour_budget_from_roles(suggested_roles)
            non_labour_budget = OnboardingAgentUtils().calculate_non_labour_budget_from_team(non_labour_team)
            budget = labour_budget + non_labour_budget
            
            appLogger.info({"event": "updateRoadmapEstimation:budget:done", "data": budget})
            steps_sender_class.sendSteps("Calculating budget", True)

            ##final updated roadamp
            formatted_json = format_json_for_roadmap(canvas_result, roles_result, budget, team)
            
            elapsed_time = int(time.time() - start)
            step_sender.sendSteps("Updating Roadmap Canvas", True)
            
            # step_sender.sendSteps(f"Time taken: {elapsed_time} seconds", False)
            # step_sender.sendSteps(f"Time taken: {elapsed_time} seconds", True, elapsed_time)
            print("\n\n--debug [Update] time", elapsed_time)
            
            socketio.emit("roadmap_creation_agent", {"event": "update_roadmap_canvas", "data": formatted_json,"roadmap_id":roadmap_id}, room=client_id)
            appLogger.info({"event": "updateRoadmapCanvas", "msg": "done","roadmap_id":roadmap_id,"tenant_id":tenant_id,"user_id":user_id})

            # Update tracking
            # self.updateRoadmapCreationTrackUtility(tenantID=tenant_id, userID=user_id, roadmap_id=roadmap_id,
            #         newly_completed_items=["roles_budget"]
            # )
            # with open('updated_roadmap.json', 'w') as file:
            #     json.dump(formatted_json, file, indent=4)
            return

        except Exception as e:
            print(f"--debug error in updateRoadmapCanvas--- {e}")
            step_sender.sendError(key=f"Error in updateRoadmapCanvas: {str(e)}",function="updateRoadmapCanvas")
            appLogger.error({"event": "updateRoadmapCanvas", "error": str(e), "traceback": traceback.format_exc()})

    
    
    def _update_canvas_task(self, db_roadmap_info, internal_knowledge, portfolios, org_strategy, currency_format,logInfo,step_sender):
        """Task to update roadmap canvas."""
        step_sender.sendSteps("Updating Roadmap Canvas", False)
        step_sender.sendSteps("Redefining Key Results", False)
        step_sender.sendSteps("Generating the Constraints", False)
        step_sender.sendSteps("Mapping the Timeline", False)

        prompt = updateRoadmapCanvasPrompt(db_roadmap_info, internal_knowledge, portfolios, org_strategy, currency_format)
        # print("\n\n--debug update prompt---", prompt.formatAsString())
        
        response = self.llm.run(prompt, self.modelOptions, 'agent::roadmap_creation', logInDb=logInfo)
        result = extract_json_after_llm(response,step_sender=step_sender)
        
        # with open('roadmap_canvas.json', 'w') as file:
        #     json.dump(result, file, indent=4)
        

        step_sender.sendSteps("Updating Roadmap Canvas", True)
        step_sender.sendSteps("Redefining Key Results", True)
        step_sender.sendSteps("Generating the Constraints", True)
        step_sender.sendSteps("Mapping the Timeline", True)

        return result

    def _update_roles_estimation_task(self, tenant_id, user_id, db_roadmap_info, tenant_formats, llm, model_opts, logInfo, step_sender):
        
        """Task to estimate roles."""
        
        try:
            step_sender.sendSteps("Analysing suitable roles", False)

            all_roles = TenantDao.getDistinctAvailableRoles(tenant_id=tenant_id)
            all_roles_count_master_data = TenantDao.getRoleCountForTenant(tenant_id=tenant_id)
            all_roles_consumed = TenantDao.getAllRoadmapsRoleCountForTenant(tenant_id=tenant_id)
            available_roles = OnboardingAgentUtils().calculate_available_roles(all_roles_count_master_data, all_roles_consumed)

            role_prompt = suggest_project_role_promptV2(
                project_details=db_roadmap_info, 
                available_roles_details=all_roles,
                available_roles=available_roles, 
                data_format=tenant_formats.get("currency_format", None),
                user_id = user_id
            )
            response = llm.run(role_prompt, model_opts, "agent::roadmap_creation", logInDb=logInfo)
            suggested_roles_json = extract_json_after_llm(response,step_sender=step_sender)

            step_sender.sendSteps("Analysing suitable roles", True)

            suggested_roles = suggested_roles_json.get("recommended_project_roles", []) or []
            roadmap_role_thought = suggested_roles_json.get("thought_process_behind_the_above_list", "")

            # Process roles
            processed_roles = []
            for role in suggested_roles:
                processed_roles.extend(OnboardingAgentUtils().transform_role_data(role))

            return {
                "suggested_roles": suggested_roles,
                "processed_roles": processed_roles,
                "roadmap_role_thought": roadmap_role_thought
            }
        except Exception as e:
            appLogger.error({"event": "_update_roles_estimation_task", "error": str(e), "traceback": traceback.format_exc()})
            return {"suggested_roles": [], "processed_roles": [], "roadmap_role_thought": ""}
  

    def creatDemandInsights(self,roadmap_canvas,tenant_id,user_id,step_sender=None):
        
        try:
            portfolios = (roadmap_canvas.get("cpc") or {}).get("portfolio",[]) or roadmap_canvas.get("portfolio_list") or ["none"]
            print("----debug canvas_portfolios------", portfolios)
            
            # 4 dimensions: Scope overlaps,# . Soln dimension, # . Business value, #Others
            existing_roadmaps = RoadmapDao.fetchRoadmapDetailsV2FOrPortfolioReview(tenant_id=tenant_id)
            ey_solutions = TenantDao.listCustomerSolutions(tenant_id)
            created_canvas = roadmap_canvas
            
            ey_sols_delivered = TenantDao.listCustomerSolutionsDelivered(tenant_id)
            #fetch delivered sols for portfolio gen now in the canvas
            grp_delivered_sols = groupSolutionsDeliveredByPortfolio(ey_sols_delivered,portfolios) or {}
            appLogger.info({"event":"grp_delivered_sols","data": next(iter(grp_delivered_sols), None),"tenant_id":tenant_id,"user_id":user_id})
            # print("\n\n--deubg ey_sols------", grp_delivered_sols)
            
            prompt = demandInsightsPrompt(
                roadmap_canvas = json.dumps(created_canvas,indent=4),
                solutions = json.dumps(ey_solutions,indent=2),
                existing_roadmaps = json.dumps(existing_roadmaps,indent=2),
                delivered_solutions = json.dumps(grp_delivered_sols,indent=2),
                user_id=user_id
            )
            # print("\n--debug [Scope] prompt-----", prompt.formatAsString())

            response = self.llm.run(prompt, self.modelOptions,'agent::create_roadmap', logInDb={"tenant_id":tenant_id,"user_id":user_id})
            result = extract_json_after_llm(response,step_sender=step_sender)
            
            # print("--debug result [sol insights]---", result)        
            appLogger.info({"event": "createSolutionInsights", "msg": "done","tenant_id":tenant_id,"user_id":user_id})
            return result
        
        except Exception as e:
            if step_sender:
                step_sender.sendError(key=f"Error generating demand insights",function="createSolutionInsights")
            appLogger.error({"event": "createSolutionInsights", "error": e, "traceback": traceback.format_exc(),"tenant_id":tenant_id,"user_id":user_id})
            return None
        
    

    ### Create History view or Audit Log for Demand change
    def createDemandAuditHistory(self,tenant_id,user_id,roadmap_id,socketio,client_id,step_sender=None,cache_seconds=900):

        if not roadmap_id:
            return {}
        try:
            insights = TangoDao.fetchTangoStatesTenant(tenant_id=tenant_id, key=f"roadmap_auditlog_{roadmap_id}", _limit=1)
            if len(insights)==0 or (len(insights)>0 and insights[0]["created_date"] is not None and (datetime.now(timezone.utc) - datetime.fromisoformat(insights[0]["created_date"])).seconds > cache_seconds):
            
                audit_logs = TenantDao.fetchAuditLogData(
                    projection_attrs=["model_name","action","changes","timestamp","user_id"],
                    object_id=roadmap_id,
                    model_name = "Roadmap",
                    tenant_id = tenant_id
                )
                # print("\n\n--debug audit_logs------", audit_logs[:2])

                if not audit_logs:
                    socketio.emit("roadmap_creation_agent",{"event":"roadmap_logs","data":"No data found","roadmap_id": roadmap_id},room=client_id)
                    return

                # audit_logs = sorted(audit_logs, key=lambda x: datetime.fromisoformat(x['timestamp'].rstrip('Z')),reverse=True)
                for log in audit_logs:
                    user_id = log.get('user_id')
                    timestamp = log.get('timestamp',"")
                    changes = json.dumps(log.get('changes',{}) or {})
                    log.pop("user_id",None)
                    log.pop("changes",None)
                    log.pop("timestamp",None)
                    
                    user_info = UsersDao.fetchUserInfoWithId(user_id)
                    user_name = (user_info["first_name"] + " " + user_info.get("last_name","")) if user_info else "Unknown"
                    log["changes"] = changes
                    log["user_name"] = user_name
                    log["timestamp"] = datetime.fromisoformat(timestamp.rstrip('Z')).strftime("%Y-%m-%d %H:%M:%S") if timestamp else ""
                    # print("---debug log---", log["user_name"],log["timestamp"],log["action"])
                
                insights_val = json.loads(insights[0]["value"]) if len(insights)>0 else []
                all_users = TenantDao.FetchUsersOfTenant(tenant_id=tenant_id)
                user_mapping = {}
                for user in all_users:
                    user_mapping[user["user_id"]] = user["first_name"]

                # print("\n\n--debug user_mapping-------", user_mapping)

                prompt = changeHistoryPrompt(
                    audit_logs = json.dumps(audit_logs),
                    user_id=user_id, 
                    existing_insights = insights_val,
                    user_mapping = user_mapping
                )
                response = self.llm.run(prompt, self.modelOptions1,'agent::roadmap_logs', logInDb={"tenant_id":tenant_id,"user_id":user_id})

                # print("\n\n--debug response changelog---", response)
                result = extract_json_after_llm(response,step_sender=step_sender)

                data = result.get("change_logs",[]) or []
                data =  data + insights_val
                TangoDao.upsertTangoState(
                    tenant_id=tenant_id, user_id=None, key=f"roadmap_auditlog_{roadmap_id}",
                    value=json.dumps(data), session_id=None
                )
            else:
                insights_val = insights[0]["value"]
                created_date = insights[0]["created_date"]
                print("--debug insight already there------", len(insights_val))
                
                appLogger.info({"event":"create_auditLog","msg":"Insights present","created_date":created_date,"roadmap_id":roadmap_id,"tenant_id":tenant_id})
                data = json.loads(insights_val) or []

            socketio.emit("roadmap_creation_agent",{"event":"roadmap_logs","data":data,"roadmap_id": roadmap_id},room=client_id)
            return
        except Exception as e:
            step_sender.sendError(key="Error creating changelogs",function="createDemandAuditHistory")
            appLogger.error({"event": "createDemandHistory","error": str(e),"traceback":traceback.format_exc()})
            
    










    # def fetchCreateRoadmapInfo_V2(self,sessionID,userID):
        
    #     print("--debug insidefetchCreateRoadmapInfo----------", sessionID,userID)
    #     conv = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id=sessionID, user_id=userID, key="create_roadmap_conv")
        
    #     try:
    #         roadmap_info = {}
    #         basic_info = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id=sessionID, user_id=userID, key="create_roadmap_context")
    #         basic_info_data = json.loads(basic_info[0]['value']) if len(basic_info)>0 else {}
    #         print("--debug [Basic Info]---", len(basic_info_data))
        
    #         #     "role": "",
    #         #     "customer_context": {},
    #         #     "portfolio": {},
    #         #     "org_strategy": "",
    #         #     "knowledge": "" //ey_sols has been added but not used
            
    #         roadmap_info = {
    #             "create_roadmap_conv": conv,
    #             "internal_knowledge": basic_info_data.get("knowledge",[]) or [],
    #             "customer_persona": basic_info_data.get("customer_context",{}) or {},
    #             "portfolio": basic_info_data.get("portfolio",[]) or [],
    #             "org_strategy": basic_info_data.get("org_strategy",[]) or []
    #         }
            
    #         # print("\n\n--debug roadmap_info111111---", roadmap_info)
            
    #         appLogger.info({"event":"fetchCreateRoadmapInfo","msg": "done","user_id":userID})
    #         return roadmap_info
    #     except Exception as e:
    #         print("error in fetchCreateRoadmapInfo", e, traceback.format_exc())
    #         appLogger.error({"event":"fetchCreateRoadmapInfo","error":e,"traceback":traceback.format_exc(),"user_id":userID})
    #         return {}