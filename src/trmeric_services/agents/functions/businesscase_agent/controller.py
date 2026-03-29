import uuid
import json
import yaml
import traceback
from datetime import datetime
from src.trmeric_s3.s3 import S3Service
from src.trmeric_utils.fuzzySearch import squeeze_text
from src.trmeric_utils.json_parser import extract_json_after_llm

from src.trmeric_ml.llm.Types import ModelOptions, ChatCompletion
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
from src.trmeric_services.roadmap.RoadmapService import RoadmapService
from src.trmeric_database.dao import FileDao, RoadmapDao,IdeaDao,TenantDao
from .default import default_template_content,default_template_content_idea
from src.trmeric_services.roadmap.utils import calculateTotalLaborCost,calculateTotalNonLaborCost
from .prompts import businessCaseTemplatePrompt, createFinancialPrompt, businessCasePromptForIdea,kpFormatTemplatePrompt,kp_businesscase_prompt

KP_TEMPLATE_TENANTS = [198,"198", 776,"776"]


class BusinessTemplateAgent:
    def __init__(self, tenant_id: int, user_id: int, entity_id: int,entity: str="roadmap", socketio=None, client_id=None, session_id: str = None, log_info=None, llm=None, mode="default",sender=None):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.entity_id = entity_id
        self.socketio = socketio
        self.client_id = client_id
        self.session_id = session_id
        self.log_info = log_info
        self.s3_service = S3Service()
        self.llm = llm
        self.mode = mode
        self.model_options = ModelOptions(model="gpt-4.1", max_tokens=16384, temperature=0.1)
        self.roadmapService = RoadmapService()
        self.socketSender = sender
        self.entity = entity
        debugLogger.info(f"Initialized BusinessTemplateAgent for {entity} with session_id: {self.session_id}")

    def track_uploaded_files(self):
        """Fetch and track files uploaded in the current session."""
        try:
            files = FileDao.FilesUploadedInS3ForSession(sessionID=self.session_id) or []
            debugLogger.info(f"Retrieved {len(files)} files for session {self.session_id}")

            file_data = []
            for file in files:
                if isinstance(file, dict) and "s3_key" in file:
                    file_info = {
                        "file_id": file.get("s3_key"),
                        "file_type": file.get("file_type", ""),
                        "url": self.s3_service.generate_presigned_url(file["s3_key"]),
                        "uploaded_at": file.get("uploaded_at", datetime.now().isoformat()),
                    }
                    file_data.append(file_info)

            return {"status": "success", "data": file_data, "session_id": self.session_id}

        except Exception as e:
            appLogger.error({"event": "error_in_track_uploaded_files", "error": str(e), "traceback": traceback.format_exc(), "session_id": self.session_id})
            raise e

    def format_template_content(self, raw_content: str):
        """Detect pattern or format the template content into a standardized JSON structure."""
        try:

            # Fallback: Use LLM to infer JSON structure

            debugLogger.info("Using LLM to infer JSON structure from raw content")
            if self.tenant_id in KP_TEMPLATE_TENANTS:
                format_prompt = kpFormatTemplatePrompt(file_content = raw_content)

            format_prompt = ChatCompletion(
                system=f"""
                    You are an expert in analyzing structured and semi-structured business case documents. Your task is to convert the provided document content into a clean JSON schema that includes ALL sections and subsections detected in the content, formatted consistently with the style of the provided default template. You must think carefully, step by step, to ensure precision and consistency.


                    Your job is to analyze the full document content provided — whether or not sections are clearly labeled — and generate a JSON structure that captures:
                    - All major sections (e.g., Executive Summary, Objectives, Scope, Planning,( Financials in table format))
                    - Any subsections within them
                    - Even implicit sections (e.g., Stakeholders, Additional Benefits, Cost Summary) that are logically grouped in the text
                    
                    
                    
                    Content of file: 
                    <content_of_file>
                    {raw_content}
                    <content_of_file>

                    For each section or subsection, include:
                    - "description": what this section is about
                    - "format": expected format (paragraph, list, table, date, number, etc.)
                    - If it's a table, include "columns": [ ... ]
                    - If it contains dates, specify expected date format (e.g., DD/MM/YYYY)
                    - If it is list of json objects then make it a table
                    DO NOT include any actual data from the document. Only describe the structure.
                    DO NOT guess based on generic business case templates. Use only what's inferred from the actual document content.
                    Include sections- executive summary, project background, risks - if not found in template document.
                    
                    
                    For each section/subsection, include:
                        "description": purpose of the section
                        "format": paragraph, list, table, date, number
                        "columns": if it's a table
                        "date_format": if date is involved
                        "subsections": if nested structure is detected
            

                    Now, improtant-- 
                    financial section and risk section should be exactly added like this-- 
                    ```json
                    "financial_analysis_and_ROI": {{
                        "description": ",
                        "format": "table",
                        "subsections": {{
                            "revenue_uplift_cashflow": {{
                                "description": "",
                                "format": "table",
                                "columns": []
                            }},
                            "operational_efficiency_gains": {{
                                "description": "",
                                "format": "table",
                                "columns": []
                            }},
                            "cash_flow_analysis": {{
                                "description": "",
                                "format": "table",
                                "columns": []
                            }}
                        }},
                        {{
                            "calculation": {{
                                "description": "",
                                "format": "table",
                                "columns": [
                                    "formula",
                                    "calculation",
                                    "result",
                                    "justification"
                                ],
                                "section<name>": [{{
                                    "data": {{}}
                                }}],
                            }}
                        }}
                    }}
                    ```
              
                    ```json
                    {{
                        "risk_analysis": {{
                            "description": "",
                            "format": "table",
                            "subsections": {{
                                "risks": {{
                                    "description": "",
                                    "format": "table"
                                }}
                            }}
                        }},
                    }}
                    ```
                     
                        
                        
                    The output should be clean JSON and follow this shape:
                    ```json
                    {{
                        "output_structure": {{
                            "<section_name_1>":{{
                                "description": "<what is this section>",
                                "format": "<expected format: paragraph / table / list / date / etc.>",
                                "subsections": {{
                                    "<optional subsection 1>": {{
                                        "description": "<what is expected>",
                                        "format": "<format>"
                                    }},...
                                }},
                            }},
                            .....,
                        }}
                    }}
                    ```
                    
                """,
                prev=[],
                user="""
                    Analyze the content carefully and return only the correct JSON structure containing:
                    all explicitly or implicitly present sections/subsections
                    the mandatory sections defined above
                    Do not add anything beyond that.
                """,
            )

            # print("doc format -- prompt ", format_prompt.formatAsString())

            response = self.llm.run(format_prompt, self.model_options, "format_template_content", logInDb=self.log_info,socketio=self.socketio,client_id=self.client_id)
            # print("doc format -- template ", response)
            formatted_json = extract_json_after_llm(response,step_sender=self.socketSender)
            return formatted_json

        except Exception as e:
            print("error here ", e, traceback.format_exc())
            self.socketSender.sendError(key="Error in formatting template content",function="format_template_content")
            appLogger.error({"event": "error_in_format_template_content", "error": str(e), "traceback": traceback.format_exc()})
            raise e

    def read_template_file(self, file_id: str):
        """Read the content of a template file by its file_id (s3_key) and format it."""
        try:
            # Download file content from S3
            file_content_ = self.s3_service.download_file_as_text(file_id)
            file_content = squeeze_text(content = file_content_) or ""

            debugLogger.info(f"Successfully read template file for file_id {file_id}")

            # Format the content into a standardized JSON structure
            template_content = self.format_template_content(file_content)
            # print("\n\n----debug read_template_file-----", template_content)
            
            return {"status": "success", "file_id": file_id, "content": template_content, "file_content": file_content}

        except Exception as e:
            appLogger.error({"event": "read_template_file", "error": str(e), "traceback": traceback.format_exc()})
            return {"status": "error", "file_id": file_id, "error": str(e), "traceback": traceback.format_exc()}

    def create_business_case(self, file_id):
        """Generate a business case using the template file."""
        try:
            socketSender = self.socketSender
            # socketSender = SocketStepsSender("business_template_agent", self.socketio, self.client_id)
            # Read and format the template file
            template_file_id = None
            file_content = None
            if self.mode == "template":
                socketSender.sendSteps("Checking uploaded Template", False)
                key = f"BUSINESS_CASE_TEMPLATE_{self.tenant_id}"
                files = FileDao.FilesUploadedInS3ForKey(key=key)
                print("file uploaded .. ", files)
                socketSender.sendSteps("Checking uploaded Template", True)
                socketSender.sendSteps(f"Detected template", False)
                socketSender.sendSteps(f"Detected template", True, 0, 0.1)

                if len(files) <= 0:
                    socketSender.sendSteps(f"Selecting default template", False)
                    socketSender.sendSteps(f"Selecting default template", True, 0, 0.1)
                    template_content = default_template_content if self.entity=="roadmap" else default_template_content_idea
                else:
                    detected_template = None
                    for f in files:
                        if f.get("file_id") == file_id:
                            template_file_id = f.get("s3_key")
                    
                    if template_file_id:
                        socketSender.sendSteps(f"Detecting pattern from template", False)
                        # template_file_id = files[0].get("s3_key")
                        print("file template_file_id .. ", template_file_id)

                        template_result = self.read_template_file(template_file_id)
                        # return
                        if template_result["status"] != "success":
                            raise Exception(f"Failed to read template file: {template_result['error']}")
                        template_content = template_result["content"]
                        file_content = template_result["file_content"]
                        print("\n---debug file_content---------", file_content[:1000])

                        socketSender.sendSteps(f"Detecting pattern from template", True)
                        # socketSender.sendSteps(f"Found {len(template_content)} sections in template", False)
                        # socketSender.sendSteps(f"Found {len(template_content)} sections in template", True)
                    else:
                        socketSender.sendSteps(f"Failed to find this template", False)
                        socketSender.sendSteps(f"Failed to find this template", True, 0, 0.1)
                        
                        socketSender.sendSteps(f"Selecting default template", False)
                        socketSender.sendSteps(f"Selecting default template", True, 0, 0.1)
                        template_content = default_template_content if self.entity=="roadmap" else default_template_content_idea
            else:
                template_content = default_template_content if self.entity=="roadmap" else default_template_content_idea

            # print("file template_content .. ", json.dumps(template_content), indent=2)

            # return

            socketSender.sendSteps(f"Fetching Data", False)
            # Fetch roadmap data
            prompt = self.get_businesscase_context(template_content,file_content=file_content)
            # print("debug prompt .. ", prompt.formatAsString())

            response = self.llm.run(prompt, self.model_options, "businessCaseTemplateCreate", logInDb=self.log_info,socketio=self.socketio,client_id=self.client_id)
            # print("response -- ", response)
            format = 'json'
            if self.tenant_id in KP_TEMPLATE_TENANTS:
                format = 'markdown'
                business_case = extract_json_after_llm(response)
            else:
                business_case = extract_json_after_llm(response,step_sender=socketSender)
            socketSender.sendSteps(f"Analysing", True)

            print("\n\nresponse\n", response)
            # print("business_case", business_case)

            if self.socketio:
                self.socketio.emit("business_template_agent", {"event": "business_case_complete_created", "data": business_case, "session_id": self.session_id,'entity':self.entity, "format": format}, room=self.client_id)

            return {"status": "success", "data": business_case, "session_id": self.session_id}

        except Exception as e:
            debugLogger.error(f"Error creating business case: {str(e)}", exc_info=True)
            self.socketSender.sendError(key="Error creating business case",function="create_business_case")
            return {"status": "error", "error": str(e), "traceback": traceback.format_exc(), "session_id": self.session_id}

    def retriggerFinancialCalculations(self) -> dict:

        try:
            socketSender = self.socketSender
            if self.tenant_id in KP_TEMPLATE_TENANTS:
                socketSender.sendSteps(f"Fetching Data", False)
                # Fetch roadmap data
                prompt = self.get_businesscase_context({},file_content="")
                # print("debug prompt .. ", prompt.formatAsString())

                response = self.llm.run(prompt, self.model_options, "businessCaseTemplateCreate", logInDb=self.log_info,socketio=self.socketio,client_id=self.client_id)
                format = 'markdown'
                # business_case = response
                business_case = extract_json_after_llm(response)
                socketSender.sendSteps(f"Analysing", True)
                print("\n\nresponse\n", response)
                if self.socketio:
                    self.socketio.emit("business_template_agent", {"event": "business_case_complete_created", "data": business_case, "session_id": self.session_id,'entity':self.entity, "format": format}, room=self.client_id)
                return

            # socketSender = SocketStepsSender("business_template_agent", self.socketio, self.client_id)
            socketSender.sendSteps("Retriggering Financial Calculations", False)
            socketSender.sendSteps("Retriggering Financial Calculations", True, 0, 1)

            socketSender.sendSteps("Preparing Financial Recalculation", False)
            roadmap_data = RoadmapDao.fetchRoadmapDataForBusinessPlan(roadmap_id= self.entity_id)
            team_data = RoadmapDao.fetchTeamDataRoadmap(roadmap_id=self.entity_id)
            if not roadmap_data:
                raise Exception(f"No roadmap data found for roadmap_id {self.entity_id}")

            # Calculate costs
            labor_cost_analysis = calculateTotalLaborCost(team_data)
            non_labor_cost_analysis = calculateTotalNonLaborCost(team_data)

            socketSender.sendSteps("Preparing Financial Recalculation", False)
            socketSender.sendSteps("Preparing Financial Recalculation", True)

            socketSender.sendSteps("Recalculating Financial Metrics", False)
            financial_template = {"financial_analysis_and_ROI": (default_template_content.get("output_structure") or {}).get("financial_analysis_and_ROI")}
            # Create a focused financial prompt
            financial_prompt = createFinancialPrompt(roadmap_data[0], labor_cost_analysis, non_labor_cost_analysis, json.dumps(financial_template), tenant_id=self.tenant_id)
            # print("financial_prompt ", financial_prompt.formatAsString())
            # Run LLM for financial calculations
            response = self.llm.run(financial_prompt, self.model_options, "retriggerFinancialCalculations", logInDb=self.log_info,socketio=self.socketio,client_id=self.client_id)
            financial_data = extract_json_after_llm(response,step_sender=socketSender)
            socketSender.sendSteps("Recalculating Financial Metrics", True)

            # Emit WebSocket event with only financial data
            if self.socketio:
                self.socketio.emit("business_template_agent", {"event": "financial_calculations_updated", "data": financial_data, "session_id": self.session_id}, room=self.client_id)

            return {"status": "success", "data": financial_data, "session_id": self.session_id}

        except Exception as e:
            appLogger.error({"event": "error_in_retrigger_financial_calculations", "error": str(e), "traceback": traceback.format_exc(), "session_id": self.session_id})
            if self.socketio:
                self.socketio.emit("business_template_agent", {"event": "financial_calculations_error", "error": str(e), "session_id": self.session_id}, room=self.client_id)
            return {"status": "error", "error": str(e), "traceback": traceback.format_exc(), "session_id": self.session_id}

    def fetch_business_case_template_files(self):
        key = f"BUSINESS_CASE_TEMPLATE_{self.tenant_id}"
        files = FileDao.FilesUploadedInS3ForKey(key)
        
        # Format template files in the required structure
        busienss_case_template_data = {
            "business_case_template": {
                "business_case_template": [
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


    def get_businesscase_context(self,template_content,file_content=None):
        print("---debug get_businesscase_context for ",self.entity, "id: ", self.entity_id, "\n\nTemplateContent: ", template_content)
        prompt = None
        socketSender = self.socketSender
        config = TenantDao.checkTenantConfig(self.tenant_id)
        
        if self.entity == "roadmap":
            roadmap_data = RoadmapDao.fetchRoadmapDataForBusinessPlan(roadmap_id = self.entity_id)
            socketSender.sendSteps(f"Fetching Data", True)
            socketSender.sendSteps(f"Analysing", False)
            team_data = RoadmapDao.fetchTeamDataRoadmap(roadmap_id=self.entity_id)
            if not roadmap_data:
                socketSender.sendError(key="No roadmap data found!",function="get_businesscase_context")
                raise Exception(f"No roadmap data found for roadmap_id {self.entity_id}")

            # Calculate costs
            labor_cost_analysis = calculateTotalLaborCost(team_data)
            non_labor_cost_analysis = calculateTotalNonLaborCost(team_data)

            # print("--debug labor-non-laosdf data -------", labor_cost_analysis, " sfsf\n", non_labor_cost_analysis)

            if self.tenant_id in KP_TEMPLATE_TENANTS and self.entity == "roadmap":
                print("--debug check tenant-----", KP_TEMPLATE_TENANTS, self.tenant_id)
                prompt = kp_businesscase_prompt(
                    roadmap_details = json.dumps(roadmap_data[0],indent=2),
                    file_content = file_content,
                    template_content = json.dumps(template_content),
                    labor_cost=labor_cost_analysis,
                    non_labor_cost=non_labor_cost_analysis, 
                    config = config
                )
                # print("--debug prompt-----", prompt.formatAsString())
                return prompt
            # Generate business case using the template
            prompt = businessCaseTemplatePrompt(
                roadmap_data=roadmap_data[0], 
                labor_cost_analysis=labor_cost_analysis,
                non_labor_cost_analysis=non_labor_cost_analysis, 
                template_content=json.dumps(template_content),
                tenant_id=self.tenant_id
            )
        elif self.entity == "idea":
            #fetch idea data
            idea_data = IdeaDao.fetchIdeaDetails(tenant_id=self.tenant_id, idea_id=self.entity_id)
            print("\n--debug idea_data ", idea_data)
            if not idea_data:
                socketSender.sendError(key="No idea data found!",function="get_businesscase_context")
                raise Exception(f"No idea data found for idea_id {self.entity_id}")
            # Generate business case using the template

            socketSender.sendSteps(f"Fetching Data", True)
            socketSender.sendSteps(f"Analysing", False)
            prompt = businessCasePromptForIdea(
                idea_data = idea_data[0],
                template_content=json.dumps(template_content),
                config = config,
                labor_cost_analysis=None,
                non_labor_cost_analysis=None
            )
        else:
            raise ValueError(f"Invalid entity type: {self.entity}")
            
        return prompt



    def tenant_config_details(self):
        #later add this in commondao with redis
        config = TenantDao.checkTenantConfig(tenant_id = self.tenant_id)
        return config

    