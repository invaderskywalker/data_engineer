import time
import time
import json
import traceback
from src.trmeric_s3.s3 import S3Service
from src.trmeric_utils.fuzzySearch import squeeze_text
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_ml.llm.Types import ModelOptions, ChatCompletion
from src.trmeric_database.dao import FileDao, RoadmapDao, TenantDao
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
from src.trmeric_services.roadmap.RoadmapService import RoadmapService
from src.trmeric_services.agents.functions.onboarding.utils.core import OnboardingAgentUtils
from src.trmeric_services.agents.functions.onboarding.utils.core import OnboardingAgentUtils
from .prompts import extract_solution_section_details_prompt, extract_labor_nonlabor_estimates_prompt, generate_solution_from_roadmap_prompt, top_matching_solutions_prompt,generate_solution_from_roadmap_prompt_v2,generate_solution_from_roadmap_prompt_v3

#Prod: 209
EXISTING_HLD_TENANTS = [234,"234",232,"232",209,"209"]


class SolutionAgent:
    def __init__(self, tenant_id: int, user_id: int, roadmap_id: int, socketio=None, client_id=None, session_id: str = None, log_info=None, llm=None, mode="default"):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.roadmap_id = roadmap_id
        self.socketio = socketio
        self.client_id = client_id
        self.session_id = session_id
        self.log_info = log_info
        self.s3_service = S3Service()
        self.llm = llm
        self.mode = mode
        self.model_options = ModelOptions(model="gpt-4.1", max_tokens=20384, temperature=0.2)
        self.roadmapService = RoadmapService()
        debugLogger.info(f"Initialized BusinessTemplateAgent with session_id: {self.session_id}")

    def read_template_file(self, file_id: str):
        """Read the content of a template file by its file_id (s3_key) and format it."""
        try:
            # Download file content from S3
            file_content = self.s3_service.download_file_as_text(file_id)
            debugLogger.info(f"Successfully read template file for file_id {file_id}")
            return {"status": "success", "file_id": file_id, "content": file_content}
        except Exception as e:
            appLogger.error({"event": "read_template_file", "error": str(e), "traceback": traceback.format_exc()})
            return {"status": "error", "file_id": file_id, "error": str(e), "traceback": traceback.format_exc()}


    def read_delivered_solutions(self,roadmap_info={},sender=None,limit=2):
        """Find the best matching% existing solutions to drive the solution generation"""
        try:
            if self.tenant_id not in EXISTING_HLD_TENANTS:
                return {}
            
            sender.sendSteps("Analyzing existing solutions", False)
            roadmap_portfolios = roadmap_info.get("roadmap_portfolios",[]) or []
            existing_sols = TenantDao.listCustomerSolutionsDeliveredForFiles(tenant_id=self.tenant_id)
            print("existing_sols", len(existing_sols))

            filtered_existing_sols = []
            # Compare all combinations, case-insensitive + partial match
            for rp in roadmap_portfolios:
                rp_str = str(rp).strip().lower() if rp else ""
                if not rp_str:
                    continue
                for existing_sol in existing_sols:
                    portfolio = existing_sol.get("portfoloio","")
                    portfolio_str = str(portfolio).strip().lower() if portfolio else ""
                    if not portfolio_str:
                        continue
                    if rp_str in portfolio_str or portfolio_str in rp_str:
                        filtered_existing_sols.append(existing_sol)

            print("--debug filtered_existing_sols----------1", len(filtered_existing_sols))

            if(len(filtered_existing_sols) == 0):
                filtered_existing_sols = existing_sols[:limit]

            print("--debug filtered_existing_sols----------2", len(filtered_existing_sols))
            
            ##Analyze the top2 best matching% sols for the demand
            input_existing_sols = []
            for data in filtered_existing_sols:
                input_existing_sols.append({
                    "business_requirements":data.get("functional_requirements",""),
                    # "high_level_solution_design":data.get("technical_requirements",""),
                    # "detailed_level_solution_design":data.get("solution_delivered",""),
                    "file_id":data.get("file_id",-1) or -1 
                })
            input_existing_sols = [i for i in input_existing_sols if i.get("file_id") !=-1]
            # print("\n--debug [Input existing sols] for matching in llm---", input_existing_sols)

            best_match_prompt = top_matching_solutions_prompt(
                roadmap_info= json.dumps(roadmap_info),
                existing_solutions=json.dumps(input_existing_sols),
            )
            # print("prompt --- ", best_match_prompt.formatAsString())
            best_match_res = self.llm.run(best_match_prompt,self.model_options, "best_sols_match_prompt",logInDb=self.log_info)
            print("--debug best_match_res sols------", best_match_res)
            top2_matching_sols = extract_json_after_llm(best_match_res)

            selection_reason = top2_matching_sols.get("thought_process_behind_selection","")
            print("--debug selection reason-----", selection_reason)

            solutions_fileids = top2_matching_sols.get("best_matching_solutions_for_demand",[])
            print("--deubg solutions_file ids---- ", solutions_fileids)
            if len(solutions_fileids) == 0:
                return {}

            sols_file_ids = solutions_fileids[:limit] #only top2
            file_details = FileDao.getfilesByID(file_ids = sols_file_ids)
            # print("\n---debug file_details-------", file_details)

            result = []
            for file in file_details:
                s3_key = file.get("s3_key") or None
                file_name = file.get("filename")

                if s3_key:
                    file_contents = self.read_template_file(file_id = s3_key)
                    processed_file_contents = squeeze_text(file_contents.get("content") or "")
                    result.append({"filename": file_name,"solution_hld":processed_file_contents})

            sender.sendSteps("Analyzing existing solutions", True)
            print("--debug read_delivered_solutions result---------", len(result))
            return {
                "top2_matched_sols": result,
                "selection_reason": selection_reason
            }

        except Exception as e:
            appLogger.error({"event": "read_delivered_solutions", "error": str(e), "traceback": traceback.format_exc()})
            return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}



    def create_solution_from_roadmap_data(self, sender=None):
        """Generate section details in Markdown, labor/non-labor estimates in JSON, and calculate budget from the template file."""
        from src.trmeric_services.chat_service.utils import get_consolidated_persona_context_utils
        try:
            socketSender = sender
            socketSender.sendSteps("Fetching company context", False)
            socketSender.sendSteps("Gathering knowledge", False)

            #Additional Context
            context = get_consolidated_persona_context_utils(tenant_id = self.tenant_id,user_id=self.user_id)
            customer_info = context.get("customer_info") or {}
            currency_format = context.get("tenant_format").get("currency_format") or None
            print("--debug context currency_format----", currency_format)
            
            roadmap_details = RoadmapDao.fetchRoadmapDetails(roadmap_id=self.roadmap_id)
            roadmap_inputs = {
                "title": roadmap_details[0].get("roadmap_title",""),
                "scope": roadmap_details[0].get("roadmap_scope",""),
                # "type": roadmap_details[0].get("roadmap_type",""),
                # "category": roadmap_details[0].get("roadmap_category",""),
                "description": roadmap_details[0].get("roadmap_description",""),
                # "roadmap_start_date": roadmap_details[0].get("roadmap_start_date"),
                # "roadmap_end_date": roadmap_details[0].get("roadmap_end_date"),
                # "roadmap_objectives": roadmap_details[0].get("roadmap_objectives"),
                "roadmap_portfolios": roadmap_details[0].get("roadmap_portfolios")
            } if len(roadmap_details) > 0 else {}

            socketSender.sendSteps("Fetching company context", True)
            socketSender.sendSteps("Gathering knowledge", True)

            loaded_solutions = self.read_delivered_solutions(roadmap_info=roadmap_inputs,sender=socketSender)
            # print("--debug top2_matched_sols------",loaded_solutions)

            # Step 2: Extract sections in Markdown
            socketSender.sendSteps(f"Creating Solution", False)
            if self.tenant_id in EXISTING_HLD_TENANTS:
                solution_prompt = generate_solution_from_roadmap_prompt_v3(
                    roadmap_inputs=roadmap_inputs,
                    customer_info=customer_info,
                    best_match_hld_solutions=loaded_solutions,
                    # tenant_id=self.tenant_id,
                    currency_format=currency_format
                )
            else:
                solution_prompt = generate_solution_from_roadmap_prompt(
                    # tenant_id=self.tenant_id,
                    currency_format=currency_format,
                    roadmap_inputs=roadmap_inputs,
                    knowledge=context.get("solutions_knowledge",[]) or [],
                    customer_info=customer_info
                )
            # print("--debug solution_prompt--------", solution_prompt.formatAsString())
            # return

            # solution_data = self.llm.run( solution_prompt,self.model_options, "generate_solution_from_roadmap_prompt",logInDb=self.log_info)
            solution_data = self.llm.run_rl(
                chat = solution_prompt, 
                options = self.model_options, 
                agent_name = 'roadmap_creation_agent', 
                function_name ="roadmap_solution::roadmap", 
                logInDb=self.log_info,
                socketio=self.socketio,
                client_id=self.client_id
            )
            print("solution_data ", solution_data)
            socketSender.sendSteps(f"Creating Solution", True)
            solution_markdown_data1 = extract_json_after_llm(solution_data)
            solution_markdown_data = solution_markdown_data1.get("solution_markdown") or ""
            thought_process = solution_markdown_data1.get("thought_process","") or ""

            # Step 6: Emit results via SocketIO
            output = {
                "solution_markdown": solution_markdown_data,
                "thought_process": thought_process
            }
            
            if self.socketio:
                self.socketio.emit("roadmap_agent", {
                    "event": "solution_and_estimate_data",
                    "data": output,
                    "session_id": self.session_id
                }, room=self.client_id)
                
            self.roadmapService.updateRoadmapCreationTrackUtility(
                tenantID=self.tenant_id, 
                userID=self.user_id,
                roadmap_id=self.roadmap_id,
                newly_completed_items=["roles_budget"]
            )
            
            with open("solution_output.md", "w") as f:
                f.write(solution_markdown_data)

            return {
                "status": "success",
                "sections_markdown": solution_markdown_data,
                "session_id": self.session_id
            }

        except Exception as e:
            sender.sendError(key="Error creating solution",function="create_solution_from_roadmap_data")
            appLogger.error({"event":"create_solution_from_roadmap_data","error":str(e),"traceback":traceback.format_exc()})
            return {"status": "error", "error": str(e), "traceback": traceback.format_exc(), "session_id": self.session_id}
       
    def create_scope_and_resources_data(self, file_id,sender=None):
        """Generate section details in Markdown, labor/non-labor estimates in JSON, and calculate budget from the template file."""
        from src.trmeric_services.chat_service.utils import roadmapPersona
        try:
            socketSender = sender
            start = time.time()

            # Step 1: Read and format the template file
            socketSender.sendSteps("Checking uploaded Template", False)
            key = f"SOLUTION_TEMPLATE_{self.tenant_id}_{self.roadmap_id}"
            files = FileDao.FilesUploadedInS3ForKey(key=key)
            print("file uploaded .. ", files)
            socketSender.sendSteps("Checking uploaded Template", True)

            if len(files) <= 0:
                socketSender.sendSteps(f"No file detected", False)
                socketSender.sendSteps(f"No file detected", True, 0, 0.1)
                return {"status": "error", "error": "No template file found", "session_id": self.session_id}

            template_file_id = None
            for f in files:
                if f.get("file_id") == file_id:
                    template_file_id = f.get("s3_key")
                    break

            if not template_file_id:
                socketSender.sendSteps(f"No matching template file found", False)
                socketSender.sendSteps(f"No matching template file found", True, 0, 0.1)
                return {"status": "error", "error": "No matching template file found", "session_id": self.session_id}

            socketSender.sendSteps(f"Reading template file", False)
            template_result = self.read_template_file(template_file_id)
            if template_result["status"] != "success":
                raise Exception(f"Failed to read template file: {template_result['error']}")
            template_content = template_result["content"]
            socketSender.sendSteps(f"Reading template file", True)

            #Additional Context
            solution_context = roadmapPersona(tenant_id=self.tenant_id,user_id=self.user_id).get("knowledge",{}) or {}
            roadmap_details = RoadmapDao.fetchRoadmapDetails(roadmap_id=self.roadmap_id)
            roadmap_inputs = {
                "title": roadmap_details[0].get("roadmap_title",""),
                "scope": roadmap_details[0].get("roadmap_scope",""),
                "type": roadmap_details[0].get("roadmap_type",""),
                "description": roadmap_details[0].get("roadmap_description","")
            } if len(roadmap_details) > 0 else {}

            # Step 2: Extract sections in Markdown
            socketSender.sendSteps(f"Extracting sections in Markdown", False)
            section_prompt = extract_solution_section_details_prompt(
                template_content=template_content,
                tenant_id=self.tenant_id,
                roadmap_inputs=roadmap_inputs,
                solution_context=solution_context
            )
            # section_data = self.llm.run(section_prompt, self.model_options, "extract_solution_section_details_prompt", logInDb=self.log_info)
            section_data = self.llm.run_rl(section_prompt, self.model_options,'roadmap_creation_agent',"roadamp_solution::roadmap", logInDb=self.log_info, socketio=self.socketio, client_id=self.client_id)
            socketSender.sendSteps(f"Extracting sections in Markdown", True)

            # Step 3: Extract labor and non-labor estimates
            socketSender.sendSteps(f"Analyzing labor and non-labor resources", False)
            # roadmap_details = RoadmapDao.fetchRoadmapDetails(roadmap_id=self.roadmap_id)
            estimate_prompt = extract_labor_nonlabor_estimates_prompt(
                template_content=template_content,
                tenant_id=self.tenant_id,
                roadmap_details=roadmap_details
            )
            estimate_data = self.llm.run(estimate_prompt, self.model_options, "extract_labor_nonlabor_estimates_prompt", logInDb=self.log_info)
            estimate_json = extract_json_after_llm(estimate_data,step_sender=socketSender)
            socketSender.sendSteps(f"Analyzing labor and non-labor resources", True)

            # Step 4: Fetch tenant configuration for currency format
            tenant_config = TenantDao.getTenantInfo(tenant_id=self.tenant_id)
            tenant_config_res = tenant_config[0]['configuration']
            tenant_formats = {}
            if tenant_config_res is not None:
                tenant_formats["currency_format"] = tenant_config_res.get("currency", {})
                tenant_formats["date_format"] = tenant_config_res.get("date_time", {})
            appLogger.info({"event": "tenant_config", "data": tenant_formats, "tenant_id": self.tenant_id})

            # Step 5: Process labor roles and calculate budget
            socketSender.sendSteps("Processing roles and budget", False)
            labor_team = estimate_json.get("labor_team", [])
            non_labor_team = estimate_json.get("non_labor_team", [])

            # Transform labor roles for budget calculation
            processed_roles = []
            for role in labor_team:
                processed_roles.extend(OnboardingAgentUtils().transform_role_data(role))

            # Combine labor and non-labor teams
            team = non_labor_team + processed_roles
            appLogger.info({"event": "solution_team_combined", "data": team})

            # Calculate budget
            labour_budget = OnboardingAgentUtils().calculate_labour_budget_from_roles(labor_team)
            non_labour_budget = OnboardingAgentUtils().calculate_non_labour_budget_from_team(non_labor_team)
            total_budget = labour_budget + non_labour_budget
            appLogger.info({"event": "solution_budget_calculated", "data": total_budget})

            # Create tango_analysis dictionary
            tango_analysis = {
                "thought_process_behind_labor_team": estimate_json.get("thought_process_labor", ""),
                "thought_process_behind_non_labor_team": estimate_json.get("thought_process_non_labor", ""),
            }
            appLogger.info({"event": "solution_tango_analysis", "data": tango_analysis})
            socketSender.sendSteps("Processing roles and budget", True)

            # Step 6: Emit results via SocketIO
            output = {
                "solution_markdown": section_data,
                "team": team,
                "budget": total_budget,
                "tango_analysis": tango_analysis
            }
            
            

            if self.socketio:
                self.socketio.emit("roadmap_agent", {
                    "event": "solution_and_estimate_data",
                    "data": output,
                    "session_id": self.session_id
                }, room=self.client_id)
                
            self.roadmapService.updateRoadmapCreationTrackUtility(
                tenantID=self.tenant_id, 
                userID=self.user_id,
                roadmap_id=self.roadmap_id,
                newly_completed_items=["roles_budget"]
            )
            
            with open("solution_output.md", "w") as f:
                f.write(section_data)

            return {
                "status": "success",
                "sections_markdown": section_data,
                "estimates": estimate_json,
                "team": team,
                "budget": total_budget,
                "tango_analysis": tango_analysis,
                "session_id": self.session_id
            }

        except Exception as e:
            sender.sendError(key="Error creating business case",function="create_scope_and_resources_data")
            appLogger.error({"event":"create_scope_and_resources_data","error":str(e),"traceback":traceback.format_exc()})
            return {"status": "error", "error": str(e), "traceback": traceback.format_exc(), "session_id": self.session_id}
        
        
    def fetch_solution_tempaltes(self):
        key = f"SOLUTION_TEMPLATE_{self.tenant_id}_{self.roadmap_id}"
        files = FileDao.FilesUploadedInS3ForKey(key)
        
        # Format template files in the required structure
        busienss_case_template_data = {
            "solution_template": {
                "solution_template": [
                    {
                        "file_id": file["file_id"],
                        "s3_key": file["s3_key"],
                        "filename": file["filename"],
                        "file_type": file["file_type"],
                        "created_on": file["created_on"],
                        "url": S3Service().generate_presigned_url(file["s3_key"])
                    } for file in files
                ]
            }
        }
        return busienss_case_template_data
    
    