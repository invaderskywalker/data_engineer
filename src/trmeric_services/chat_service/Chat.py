import os
import re
import json
import time
import datetime
import traceback
from openai import OpenAI
from src.trmeric_utils.json_parser import *
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_services.chat_service.Prompts import *
from src.trmeric_ml.llm.models.BedrockClient import Bedrock
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_database.dao import TangoDao,TenantDao,CustomerDao,RoadmapDao
from src.trmeric_services.agents.functions.onboarding.utils.core import OnboardingAgentUtils
from src.trmeric_services.phoenix.queries import KnowledgeQueries
from src.trmeric_ws import SocketStepsSender
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_api.logging.TimingLogger import start_timer, stop_timer, log_event_start
from src.trmeric_services.journal.Activity import detailed_activity, activity, record
import concurrent.futures
from src.trmeric_database.dao import UsersDao


from src.trmeric_services.roadmap.RoadmapService import RoadmapService
from src.trmeric_services.agents.functions.graphql_v2.analysis.roadmap_inference import (
    infer_roadmap, 
    format_guidance_for_canvas_stages,
    format_basic_stage_prompt_section,
    format_okr_stage_prompt_section,
    format_cpc_stage_prompt_section,
)
from src.trmeric_services.agents.functions.graphql_v2.utils.tenant_helper import (is_knowledge_integrated)

from src.trmeric_services.chat_service.utils import *

class Chat:
    """
    Handles the discovery chat and the messages within it.
    """

    def __init__(
        self,
        requestInfo,
        chatType,
        sessionId="",
        temperature=0,
    ):
        # print("\n\n\n\n--------debug [Request Info]-----------", requestInfo)
        self.temperature = temperature
        self.sessionId = sessionId
        self.messages = []
        self.dbMessages = []
        self.userName = requestInfo.get("username")
        self.tenant_id = requestInfo.get("tenant_id")
        self.user_id = requestInfo.get("user_id")
        self.chatType = chatType
        self.openai = OpenAI(api_key=os.getenv("OPENAI_KEY"))
        self.llm = ChatGPTClient(self.user_id, self.tenant_id)
        self.onboarding_agent_utils = OnboardingAgentUtils()
        
        self.name = requestInfo.get("first_name","") or "Welcome"
        self.log_info = {"tenant_id": self.tenant_id, "user_id": self.user_id}
        

        self.updatePersonaDate()
        
        ##Demand flow for EY tenants: Dev: 776, QA: 232 , Prod: 183
        if (self.tenant_id in DEMAND_TENANTS) or True:
            self.roadmapContext = roadmapPersona(tenant_id = self.tenant_id, user_id = self.user_id)
            self.role  = USER_ROLES[self.roadmapContext.get("role", "")].get("role","Organization Demand Requestor") or "Organization Demand Requestor"
            self.user_portfolios = self.roadmapContext.get("user_portfolios", []) or []
            self.all_portfolios = self.roadmapContext.get("all_portfolios_of_customer", []) or []
            
            if len(self.user_portfolios)==0:
                self.user_portfolios = [portfolio["title"] for portfolio in self.all_portfolios if len(self.all_portfolios)>0]
            # print("--debug user_portfolios---", '\n', self.user_portfolios)
    
        self.roadmapInfo = None
        self.modelOptions = ModelOptions(model="gpt-4.1",max_tokens=10000,temperature=0)
        self.roadmapService = RoadmapService()

        if chatType == 1:
            self._fetchRoadmapDataIfRoadmapAttached()

    def updatePersonaDate(self):
        try:
            personaData = {
                "core_business": "",
                "industry_domain_specialization": ""
            }
            
            personaData = CustomerDao.FetchCustomerPersona(self.tenant_id)[0]["persona"]
                        
            self.tenantOrgInfo = CustomerDao.FetchCustomerOrgDetailInfo(self.tenant_id)[0]['org_info']
            print("here persona data", personaData)
            self.org_strategy_alignment = RoadmapDao.fetchAllOrgstategyAlignmentTitles(self.tenant_id)
            self.customerPersona = {
                "core_business": personaData.get("core_business","") if personaData else  "",
                "industry_domain_specialization": personaData.get("industry_domain_specialization","") if personaData else  ""
            }
            
        except Exception as e:
            print("error in update persona", e, traceback.format_exc())
            self.tenantOrgInfo = ""
            self.customerPersona= ""
            self.org_strategy_alignment = ""

    def _fetchRoadmapDataIfRoadmapAttached(self):
        """
        Generates the roadmap data for the chat by doing the following:
        - fetching teh roadmap for a given project
        - if a roadmap exists, then getting information about that roadmap and its KPIs
        - then with that data generating the roadmap data
        """
        info = RoadmapDao.getRoadmapIdToAttachedProject(self.sessionId)
        roadmap_id = info[0]["roadmap_id"]

        print(
            "--------------------_fetchRoadmapDataIfRoadmapAttached-----------------------",
            roadmap_id, info
        )
        if roadmap_id is None:
            pass
        else:
            roadmapInfo = RoadmapDao.getRoadmapInfo(self.sessionId)[0]
            KPIsOfRoadmap = RoadmapDao.getKpiOfRoadmapInfo(self.sessionId)
            data = {
                "description": roadmapInfo["description"],
                "objectives": roadmapInfo["objectives"],
                "kpis": KPIsOfRoadmap,
                "start_date": roadmapInfo["start_date"],
                "end_date": roadmapInfo["end_date"],
                "budget": str(roadmapInfo["budget"]) + " USD",
            }
            self.roadmapInfo = data

    def generateNextQuestion(self):
        try:
            print("debug---generateNextQuestion--", self.chatType, self.roadmapInfo is None,
                  len(self.getConvMessagesArr()))  
            
            messages = self.getConvMessagesArr()  
            last_message = ""
            if len(messages) > 0:
                last_message = messages[len(messages) - 1]
                    
            if (self.chatType == 1 and len(self.getConvMessagesArr()) == 2 and self.roadmapInfo is None):
                return '''<|end_header_id|>

Here's the first question:

```json
{
    "question": "Excellent choice! Collaborating with the right tech provider can be transformative. Let's narrow things down. Does the nature of work or project be broadly fit into any of the below listed classification?",
    "options": [
        "Data & analytics",
        "Product engineering",
        "Cloud Transformation",
        "IT Infra & Operations",
        "Application maintenance & support",
        "Business applications (ERP, HR etc.)",
        "CX - (Saleforce, Web transfromation etc.)",
        "Cannot be classified into above buckets"
    ],
    "hint": [],
    "question_progress": "0%",
    "counter": 0,
    "last_question_progress": "0%",
    "topics_answered_by_user": {
        "nature of the project": "false",
        "the project's broad objective for the customer": "false",
        "the technology, tools, frameworks, and solutions to be used in the project by the provider": "false",
        "specific business domain or business process knowledge or capabilities required by the provider": "false",
        "preferred location for the provider": "false",
        "new project or an ongoing project": "false",
        "timeline of the project": "false",
        "budget/funding of the project": "false",
        "definition of 'success' for this project": "false",
        "what evaluation criteria will be used to evaluate the provider": "false",
        "if the user wants to share more about the project": "false"
    },
    "should_stop": "false",
    "should_stop_reason": "",
    "are_all_topics_answered_by_user": "false"
}
```

Please respond with one of the options, and I'll proceed with the next question!
'''

            elif (self.chatType == 2 and len(self.getConvMessagesArr()) == 2):
                return '''<|end_header_id|>

Here's the first question:

```
{
    "question": "Tell me about your project! What's the broad scope and objective of this project? I'm excited to learn more about it!",
    "options": [],
    "hint": ["For example, you can share the problem you're trying to solve, the goals you want to achieve, or the key stakeholders involved. This will help me understand your project better."],
    "question_progress": "0%",
    "counter": 0,
    "last_question_progress": "0%",
    "topics_answered_by_user": [],
    "should_stop": false,
    "should_stop_reason": "",
    "are_all_topics_answered_by_user": false
}
```

Please respond with your project's broad scope and objective. I'll use this information to guide our conversation and ask the next question!'''
                
            elif (self.chatType == 3 and len(self.getConvMessagesArr()) == 2):
                if (self.tenant_id in DEMAND_TENANTS) or True:
                    print("debug---generateNextQuestion-- 1",self.tenant_id)
                    
                    portfolio_str = f"{', '.join(map(str, self.user_portfolios))}"
                    language = UsersDao.fetchUserLanguage(user_id = self.user_id)
                    print("language ---", language)
                    if language == "Spanish":
                        # if (len(self.user_portfolios) > 1):
                        portfolio_str += " portafolio(s)"
                        return f"""<|end_header_id|>

    Aquí está la primera pregunta::
    ```
    {{
        "question": "🎉 Hola, {self.name}, comencemos. Veo que tienes acceso a {portfolio_str}. ¿En cuál portafolio te gustaría crear demanda?",
        "options": {json.dumps(self.user_portfolios)},
        "auto_select_best_options": [],
        "hint": [],
        "agent_tip": [],
        "question_progress": "0%",
        "counter": 0,
        "last_question_progress": "0%",
        "draft_title": "",
        "draft_title_generated": false,
        "topics_answered_by_user": [],
        "should_stop": false,
        "should_stop_reason": "",
        "are_all_topics_answered_by_user": false
    }}
    ```

    Please respond with your answer, and I'll proceed with the next question!"""
                    else:
                        portfolio_str += " portfolio(s)"
                        return f"""<|end_header_id|>

    Here's the first question:
    ```
    {{
        "question": "🎉 Hello, {self.name} let's begin. I see you have access to {portfolio_str}. Which portfolio would you like to create demand in?",
        "options": {json.dumps(self.user_portfolios)},
        "auto_select_best_options": [],
        "hint": [],
        "agent_tip": [],
        "question_progress": "0%",
        "counter": 0,
        "last_question_progress": "0%",
        "draft_title": "",
        "draft_title_generated": false,
        "topics_answered_by_user": [],
        "should_stop": false,
        "should_stop_reason": "",
        "are_all_topics_answered_by_user": false
    }}
    ```

    Please respond with your answer, and I'll proceed with the next question!"""
                            
                  
                else:
                    print("debug---generateNextQuestion-- 1",
                        self.chatType, len(self.getConvMessagesArr()))
                    return '''<|end_header_id|>

Here's the first question:
```
{
    "question": "Tell me about your roadmap or the proposed project! What's the broad scope and objective of this initiative?",
    "options": [],
    "hint": ["For example, you can share the high-level goals, key performance indicators (KPIs), or the overall vision behind this project. This will help me understand the context and purpose of your roadmap."],
    "question_progress": "0%",
    "counter": 0,
    "last_question_progress": "0%",
    "topics_answered_by_user": [],
    "should_stop": false,
    "should_stop_reason": "",
    "are_all_topics_answered_by_user": false
}
```

Please respond with your answer, and I'll proceed with the next question!'''


            elif (self.chatType == 4 and len(self.getConvMessagesArr()) == 2):
                return '''

Here's the first question:
```
{
    "question": "To get started, could you please share the top pain points you are looking to solve by using Trmeric?", 
    "options": [], 
    "hint": ["For example, if you're in the healthcare domain, you might mention challenges like reducing operational inefficiencies or improving patient care delivery."],
    "question_progress": "0%", 
    "counter": 0,
    "last_question_progress": "0%",
    "topics_answered_by_user": [],
    "should_stop": false,
    "should_stop_reason": "",
    "are_all_topics_answered_by_user": false
}
```

Please respond with your answer, and I'll proceed with the next question!'''


            elif (self.chatType == 5 and len(self.getConvMessagesArr()) == 2): #for Portfolio
                return f"""<|end_header_id|>
    
    Here's the first question:
    ```
    {{
        "question": "🎉 Hello, {self.name} let's begin. What's the broad overview of your portfolio including the name and key functions it covers?",
        "options": [],
        "hint": [],
        "agent_tip": [],
        "question_progress": "0%",
        "counter": 0,
        "last_question_progress": "0%",
        "topics_answered_by_user": [],
        "should_stop": false,
        "should_stop_reason": "",
        "are_all_topics_answered_by_user": false
    }}
    ```
    
    Please respond with your answer, and I'll proceed with the next question!"""




            print("debug---generateNextQuestion-- 2",
                  self.chatType, len(self.getConvMessagesArr()))
            response = self.openai.chat.completions.create(
                model=self.modelOptions.model,
                messages=self.getConvMessagesArr(),
                max_tokens=self.modelOptions.max_tokens,
                temperature=self.modelOptions.temperature,
                stream=False,
            )
            

            try:
                TangoDao.createEntryInStats(
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    function_name="generateNextQuestion_"+str(self.chatType),
                    model_name=response.model,
                    total_tokens=response.usage.total_tokens,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens
                )
            except Exception as e:
                appLogger.error({
                    "event": "error_in_storing_stats",
                    "error": e,
                    "traceback": traceback.format_exc()
                })

            output = response.choices[0].message.content
            output_json = extract_json_after_llm(output)
            
            if ("agent_tip" in output_json):
                output_json["hint"] = output_json["agent_tip"]
            return json.dumps(output_json)
        
            # return extract_json_after_llm(response)
            # return Bedrock().run_bedrock(self.getConvMessagesArr())
        except Exception as e:
            print(f"error occured in get next generateNextQuestion: {e}", traceback.format_exc())
            raise e

    def startSession(self):
        """
        This is called when user is starting the chat session for the 
        first time and the system message (instruction) is loaded into context
        """
        if self.chatType == 1:
            if self.roadmapInfo is not None:
                systemMessage = {
                    "role": "system",
                    "content": getPromptIfStarterRoadmap(self.roadmapInfo),
                    "username": "Tango",
                    "time": datetime.datetime.now().isoformat(),
                }
            else:
                systemMessage = {
                    "role": "system",
                    "content": getPromptIfNoRoadmap(),
                    "username": "Tango",
                    "time": datetime.datetime.now().isoformat(),
                }
        elif self.chatType == 2:
            systemMessage = {
                "role": "system",
                "content": getProjectQnaChat(json.dumps(self.customerPersona)),
                "username": "Tango",
                "time": datetime.datetime.now().isoformat(),
            }
        elif self.chatType == 3:
            detailed_activity(
                activity_name="roadmap_creation_initiation",
                activity_description="User has started the roadmap creation process. Initializing roadmap creation chat with user.",
                user_id=self.user_id,
            )
            content = getRoadmapQnaChat_V2(self.roadmapContext, user_id=self.user_id)
            # if self.tenant_id in DEMAND_TENANTS else getRoadmapQnaChat(json.dumps(self.customerPersona))
            systemMessage = {
                "role": "system",
                # "content": getRoadmapQnaChat(self.customerPersona),
                "content": content,
                "username": "Tango",
                "time": datetime.datetime.now().isoformat(),
            }
        elif self.chatType == 4:
            systemMessage = {
                "role": "system",
                "content": onboardProcessPrompt(json.dumps(self.customerPersona)),
                "username": "Tango",
                "time": datetime.datetime.now().isoformat(),
            }
        elif self.chatType == 5:
            systemMessage = {
                "role": "system",
                "content": getPortfolioQnaChat(json.dumps(self.customerPersona)),
                "username": "Tango",
                "time": datetime.datetime.now().isoformat(),
            }
            
        userMessage = {
            "role": "user",
            "content": "Please start asking from the first question.",
            "username": self.userName,
            "time": datetime.datetime.now().isoformat(),
        }

        self.dbMessages.append(systemMessage)
        self.dbMessages.append(userMessage)

    def addUserMessage(self, content):
        userMessage = {
            "role": "user",
            "content": content,
            "username": self.userName,
            "time": datetime.datetime.now().isoformat(),
        }
        self.dbMessages.append(userMessage)

    def addAssistantMessage(self, content):
        systemMessage = {
            "role": "assistant",
            "content": content,
            "username": "Tango",
            "time": datetime.datetime.now().isoformat(),
        }
        self.dbMessages.append(systemMessage)

    @activity("discovery_session_create_brief")
    def createProjectBrief(self, companyName):
        """
        This is used when user has completed the 
        discovery chat and wants to see the project brief
        """
        record("description", "Generating project brief for a provider based on user's answers during the chat session.")
        record("user_id", self.user_id)

        company_name_hash = "COMPANY_NAME_HASH"
        qna = self.fetchOnlyQna()
        
        record("input_data", qna)
        if self.roadmapInfo is not None:
            messages = [
                {
                    "role": "user",
                    "content": createProjectBriefCreationPromptV4(
                        self.roadmapInfo, qna, company_name_hash
                    ),
                }
            ]
        else:
            messages = [
                {
                    "role": "user",
                    "content": createProjectBriefCreationPromptV3(qna, company_name_hash),
                }
            ]
        # print("before llm -- ", companyName, messages)
        response = self.openai.chat.completions.create(
            model=self.modelOptions.model,
            messages=messages,
            max_tokens=self.modelOptions.max_tokens,
            temperature=self.modelOptions.temperature,
            stream=False,
        )

        try:
            TangoDao.createEntryInStats(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                function_name="createProjectBrief",
                model_name=response.model,
                total_tokens=response.usage.total_tokens,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens
            )
        except Exception as e:
            appLogger.error({
                "event": "error_in_storing_stats",
                "error": e,
                "traceback": traceback.format_exc()
            })

        output_ = response.choices[0].message.content

        # output_ = Bedrock().run_bedrock(messages)
        # unhash from string
        output_ = output_.replace(company_name_hash, companyName)
        ##
        output = extract_json_after_llm(output_)

        # print('--createProjectBrief--', output)

        response = {}
        parsedResult = []
        for key, value in output.items():
            temp = {}
            temp["title"] = key
            temp["value"] = value

            parsedResult.append(temp)

        response["project_brief"] = parsedResult
        return response

    def fetchPrefilledRoadmapOrProjectData(self,socketio,client_id):
        """
        This is used when user has completed the qna chat and wants to move to complete the entity workflow
        Chattype: 2-Project, 3-Roadmap/Demand , 4-Onboarding, 5-Portfolio
        """
        qna = self.fetchOnlyQna()
        agent = agentNameMapping(self.chatType)
        entity = agent.split('_')[0]
        step_sender = SocketStepsSender(agent_name=agent, socketio=socketio, client_id=client_id)
        print("--debug qna fetched--- for ",entity,"\nAgent: ", agent, "\n QNA: ", qna)
        
        #store the conv
        TangoDao.insertTangoState(tenant_id=self.tenant_id, user_id=self.user_id,
            key=f"create_{entity}_conv", 
            value= f""""{entity} Creation Conv:\n {json.dumps(qna)}""",
            session_id=self.sessionId
        )
        appLogger.info({"event":"fetchPrefilledRoadmapOrProjectData","status": "qna_fetched","tenant_id":self.tenant_id,"user_id":self.user_id,"chatType":entity})
        
        company_name = "Trmeric"
        if self.chatType == 2:
            messages = [
                {
                    "role": "user",
                    "content": createProjectDataFromQNA(
                        qna, company_name, self.customerPersona
                    ),
                }
            ]
        
        elif self.chatType == 4: #for onboarding
            messages = [
                {
                    "role": "user",
                    "content": createOnboardBriefFromQNA(
                        qna, company_name,self.customerPersona
                    ),
                }
            ]
        
        elif self.chatType == 3: #roadmap flow
            
            messages = [{"role": "user","content": "roadmap"}]
            print("--debug in fetchPrefilledRoadmapOrProjectData---- ")
            appLogger.info({"event": "roadmap:prefill:prompt:start","tenant_id": self.tenant_id, "user_id": self.user_id})
            
            socketio.emit("roadmap_creation_agent",{"event": "show_timeline"},room=client_id)
            step_start_times = {}
            
            if (self.tenant_id in DEMAND_TENANTS) or True: #for EY
                try:
                    # print("\n\n\n\n\n\n\n\n\n---deubg roadmap_context new-------",self.roadmapContext)
                    context = self.roadmapContext
                    step_key = "Gathering Internal Knowledge"
                    step_sender.sendSteps(step_key, False)
                    step_start_times[step_key] = time.time()  # Record start time
                    
                    internal_knowledge = context.get("knowledge") or []
                    org_strategy = context.get("org_strategy") or []
                    all_portfolios = context.get("all_portfolios_of_customer") or []
                    
                    
                    elapsed_time = time.time() - step_start_times[step_key]  # Calculate time taken
                    # print("--debug time taken for fetching internal knowledge---", elapsed_time)
                    appLogger.info({"event":"internal_knowledge_rodmap", "status": "done","tenant_id": self.tenant_id, "user_id": self.user_id})
                    step_sender.sendSteps(step_key, True, time=elapsed_time)  # Pass elapsed time
                    
                    
                    TangoDao.insertTangoState(tenant_id=self.tenant_id, user_id=self.user_id,
                        key="create_roadmap_sessionID", value= self.sessionId,
                        session_id=''
                    )
                    
                    #5 :Create roadmap canvas
                    step_key = "Creating Demand Canvas"
                    step_sender.sendSteps(step_key, False)
                    step_start_times[step_key] = time.time()  # Record start time
                    
                    # Infer roadmap guidance from graph patterns (if knowledge is integrated)
                    stage_guidance = {"basic": {}, "okr": {}, "cpc": {}}
                    
                    graphname = is_knowledge_integrated(self.tenant_id)
                    if graphname:
                        try:
                            description_text = "\n".join([f"Q: {item.get('question','')}\nA: {item.get('answer','')}" for item in qna])
                            
                            inference_result = infer_roadmap(
                                roadmap_data={"description": description_text, "tenant_id": self.tenant_id},
                                graphname=graphname,
                                tenant_id=self.tenant_id
                            )
                            
                            if inference_result and inference_result.get("inference_status") == "success":
                                # Use the new formatting functions to get stage-specific guidance
                                stage_guidance = format_guidance_for_canvas_stages(inference_result)
                                
                                # Add formatted prompt sections for each stage
                                stage_guidance["basic"]["prompt_section"] = format_basic_stage_prompt_section(stage_guidance["basic"])
                                stage_guidance["okr"]["prompt_section"] = format_okr_stage_prompt_section(stage_guidance["okr"])
                                stage_guidance["cpc"]["prompt_section"] = format_cpc_stage_prompt_section(stage_guidance["cpc"])
                                
                                pattern_name = inference_result.get("pattern_reference", {}).get("pattern_name", "")
                                confidence = inference_result.get("pattern_match", {}).get("confidence", 0.0)
                                
                                appLogger.info({"event": "roadmap_inference_success", "tenant_id": self.tenant_id, "pattern_name": pattern_name})
                            else:
                                failure_reason = inference_result.get("inference_status", "unknown") if inference_result else "null_result"
                                failure_msg = inference_result.get("message", "") if inference_result else ""
                                appLogger.warning({"event": "roadmap_inference_incomplete", "status": failure_reason, "message": failure_msg})
                        except Exception as e:
                            appLogger.error({"event": "roadmap_inference_failed", "error": str(e), "traceback": traceback.format_exc()})
                    else:
                        appLogger.info({"event": "roadmap_knowledge_not_integrated", "tenant_id": self.tenant_id, "using_default_flow": True})

                    cpc=None
                    okr=None
                    basic_info=None
                    roadmap_canvas = {}
                    
                    stages = ["basic", "okr", "cpc"]
                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                        futures = [
                            executor.submit(
                                self.roadmapService.create_roadmap_canvas,
                                tenant_id=self.tenant_id,
                                user_id=self.user_id,
                                roadmap_stage=stage,
                                conversation=qna,
                                persona=self.customerPersona,
                                org_info=self.tenantOrgInfo,
                                org_alignment=org_strategy,
                                portfolios=all_portfolios,
                                internal_knowledge=internal_knowledge,
                                socketio=socketio,
                                client_id=client_id,
                                step_sender=step_sender,
                                guidance=stage_guidance.get(stage, {})
                            )
                            for stage in stages
                        ]
                    
                    results = {stage: future.result() for stage, future in zip(stages, futures)}
                    basic_info, okr, cpc = results["basic"], results["okr"], results["cpc"]
                    
                    roadmap_canvas["basic"] = basic_info
                    roadmap_canvas["okr"] = okr
                    roadmap_canvas["cpc"] = cpc

                    step_key1 = "Matching Existing Solutions"
                    step_sender.sendSteps(step_key1, False)
                    step_start_times[step_key1] = time.time() 
                    
                    solution_insights = self.roadmapService.createDemandInsights(roadmap_canvas,self.tenant_id,self.user_id,step_sender=step_sender)
                    roadmap_canvas["insights"] = solution_insights
                    roadmap_canvas["creation_source"] = "conversation"
                    roadmap_canvas["session_id"] = self.sessionId
                    
                    elapsed_time = time.time() - step_start_times[step_key1]  
                    print("--debug time taken for solution_insights--", elapsed_time)
                    step_sender.sendSteps(step_key1, True, time=elapsed_time)
                    
                    
                    with open(f"roadmap_canvas_{self.user_id}.json", "w") as f:
                        json.dump(roadmap_canvas, f, indent=4)
                    
                    
                    elapsed_time = time.time() - step_start_times[step_key]  # Calculate time taken
                    print("--debug time taken for creating roadmap canvas---", elapsed_time)
                    step_sender.sendSteps(step_key, True, time=elapsed_time)  # Pass elapsed time
                    
                    appLogger.info({"event": "roadmap:prefill::canvas::end", "data": len(roadmap_canvas),"tenant_id": self.tenant_id, "user_id": self.user_id})               
                    return roadmap_canvas
                        
                except Exception as e:
                    appLogger.error({"event":"roadmap:prefill:prompt","error":e,"traceback":traceback.format_exc()})
                    # socketio.emit("roadmap_creation_agent",{"event": "stop_show_timeline","error":str(e)},room=client_id)
                    step_sender.sendError(key=str(e),function = "fetchPrefilledRoadmapOrProjectData")
                
            
            else: # Normal roadmap flow
                #Tenant level data for Portfolio and Org strategy Alignment
                appLogger.info({"event": "roadmap:normal_flow_start","tenant_id": self.tenant_id, "user_id": self.user_id})
                try:
                    # Track data gathering phase
                    detailed_activity(
                        activity_name="roadmap_context_gathering",
                        activity_description=f"Beginning data collection for roadmap creation. Fetching tenant portfolios, organizational strategy alignments, and assessing portfolio relevance based on user requirements. Tenant ID: {self.tenant_id}",
                        user_id=self.user_id
                    )
                
                    #1
                    step_key = "Fetching Portfolio"
                    step_sender.sendSteps(step_key, False)
                    
                    step_start_times[step_key] = time.time()  # Record start time
                    all_portfolios = RoadmapDao.fetchAllPortfolioOfTenant(tenant_id=self.tenant_id)
                    elapsed_time = time.time() - step_start_times[step_key]  # Calculate time taken
                    
                    # print("--debug time taken for fetching portfolio---", elapsed_time)
                    step_sender.sendSteps(step_key, True, time=elapsed_time)  # Pass elapsed time
                    
                    #2
                    step_key = "Fetching Org Strategy Alignment"
                    step_sender.sendSteps(step_key, False)
                    
                    step_start_times[step_key] = time.time()  # Record start time
                    org_strategy = RoadmapDao.fetchOrgStrategyAlignMentOfTenant(tenant_id=self.tenant_id)
                    elapsed_time = time.time() - step_start_times[step_key]  # Calculate time taken
                    
                    print("--debug time taken for fetching org strategy alignment---", elapsed_time)
                    step_sender.sendSteps(step_key, True, time=elapsed_time)  # Pass elapsed time
                    
                    #store the portfolio and org strategy alignment
                    TangoDao.insertTangoState(tenant_id=self.tenant_id, user_id=self.user_id,
                        key="create_roadmap_personaPortfolioOrgStrategy", 
                        value=json.dumps({
                            "customer_persona": self.customerPersona,
                            "portfolios": all_portfolios,
                            "org_strategy": org_strategy
                        }),
                        session_id=self.sessionId
                    )
                    
                    
                    #3: Assessing Portfolio Alignment
                    step_key = "Assessing Portfolio Alignment"
                    step_sender.sendSteps(step_key, False)
                    step_start_times[step_key] = time.time()  # Record start time
                    
                    portfolio_selection_prompt = roadmapInternalKnowledgePrompt(
                        conversation=qna,
                        org_info=self.tenantOrgInfo,
                        persona=self.customerPersona,
                        portfolios=all_portfolios
                    )
                    selection_response = self.llm.run(
                        portfolio_selection_prompt,
                        ModelOptions(model="gpt-4o", max_tokens=4096, temperature=0.2),
                        'agent::portfolio_selection',
                        logInDb={"tenant_id": self.tenant_id, "user_id": self.user_id}
                    )
                    selection_output = extract_json_after_llm(selection_response)
                    # print("--debug selection_output---", selection_output)
                    
                    elapsed_time = time.time() - step_start_times[step_key]  # Calculate time taken
                    print("--debug time taken for internal knowledge--", elapsed_time)
                    step_sender.sendSteps(step_key, True, time=elapsed_time)  # Pass elapsed time
                    
                    
                    selected_portfolio_ids = [p['id'] for p in selection_output.get('selected_portfolios', [])]
                    # print("debug ---selected_portfolio_ids- ", selected_portfolio_ids)    
                
                    # Track portfolio analysis completion
                    detailed_activity(
                        activity_name="roadmap_portfolio_analysis",
                        activity_description=f"Completed portfolio relevance analysis using AI. Analyzed {len(all_portfolios)} available portfolios and selected {len(selected_portfolio_ids)} relevant portfolios based on user requirements and organizational context. Selected portfolio IDs: {selected_portfolio_ids}",
                        user_id=self.user_id
                    )
                    
                    #4
                    step_key = "Gathering Internal Knowledge"
                    step_sender.sendSteps(step_key, False)
                    step_start_times[step_key] = time.time()  # Record start time
                    
                    internal_knowledge = KnowledgeQueries.fetchPortfolioKnowledge(portfolio_ids=selected_portfolio_ids)
                    # print("portfolio knowledge ", internal_knowledge)
                    
                    elapsed_time = time.time() - step_start_times[step_key]  # Calculate time taken
                    # print("--debug time taken for fetching internal knowledge---", elapsed_time)
                
                    # Track internal knowledge gathering
                    detailed_activity(
                        activity_name="roadmap_knowledge_retrieval",
                        activity_description=f"Retrieved internal knowledge from selected portfolios. Gathered {len(internal_knowledge) if internal_knowledge else 0} knowledge items from {len(selected_portfolio_ids)} portfolios to inform roadmap creation. Knowledge will be used to enhance roadmap accuracy and alignment with organizational capabilities.",
                        user_id=self.user_id
                    )
                    
                    appLogger.info({"event":"internal_knowledge_rodamp", "status": "done"})
                    step_sender.sendSteps(step_key, True, time=elapsed_time)  # Pass elapsed time
                    
                    
                    TangoDao.insertTangoState(tenant_id=self.tenant_id, user_id=self.user_id,
                        key="create_roadmap_sessionID", value= self.sessionId,
                        session_id=''
                    )
                    
                    
                    #5 :get roadmap name & desc
                    step_key = "Creating Roadmap"
                    step_sender.sendSteps(step_key, False)
                    step_start_times[step_key] = time.time()  # Record start time
                    
                    prompt = roadmapBasicInfoPrompt(
                        conversation = qna,
                        persona = self.customerPersona,
                        org_info = self.tenantOrgInfo,
                        org_alignment = org_strategy,
                        portfolios=[p for p in all_portfolios if p['id'] in selected_portfolio_ids],  # Filter portfolios
                        internal_knowledge=internal_knowledge,
                    )
                    # print("\n\ndebug ---prompt for roadmap name & desc- ", prompt.formatAsString())
                    
                    response = self.llm.run(
                        prompt, 
                        ModelOptions(model="gpt-4o", max_tokens=4096, temperature=0.1), 
                        'agent::roadmap_creation', 
                        logInDb = {"tenant_id": self.tenant_id, "user_id": self.user_id} 
                    )
                    output = extract_json_after_llm(response,step_sender=step_sender)
                    # print("\n\n--debug response------ ", output)
                    
                    # Track roadmap name and description generation
                    detailed_activity(
                        activity_name="roadmap_basic_info_generation",
                        activity_description=f"Successfully generated roadmap name and description using AI analysis. Created roadmap titled '{output.get('roadmap_name', 'N/A')}' with detailed description. Utilized user conversation, organizational context, portfolio alignment, and internal knowledge to create comprehensive roadmap foundation ready for detailed planning stages.",
                        user_id=self.user_id
                    )
                    
                    elapsed_time = time.time() - step_start_times[step_key]  # Calculate time taken
                    print("--debug time taken for creating roadmap name & desc---", elapsed_time)
                    step_sender.sendSteps(step_key, True, time=elapsed_time)  # Pass elapsed time
                    
                    TangoDao.insertTangoState(tenant_id=self.tenant_id, user_id=self.user_id,
                        key="create_roadmap_basicInfo", 
                        value= json.dumps({
                            "basic_info": {"RoadmapName": output.get("roadmap_name"),"Description": output.get("description")},
                            "internal_knowledge": internal_knowledge
                        }),
                        session_id=self.sessionId
                    )
                    
                    # Track successful completion of roadmap preparation
                    detailed_activity(
                        activity_name="roadmap_preparation_complete",
                        activity_description=f"Roadmap preparation phase completed successfully. All necessary data has been collected, analyzed, and stored for roadmap '{output.get('roadmap_name', 'N/A')}'. System is ready to proceed to detailed roadmap creation stages (objectives, scope, timeline, roles, and budget estimation).",
                        user_id=self.user_id
                    )
                    
                    appLogger.info({"event": "roadmap:prefill:prompt:end", "data": len(output)})
                    return output
                     
                except Exception as e:
                    # Track any errors in the roadmap creation process
                    detailed_activity(
                        activity_name="roadmap_creation_error",
                        activity_description=f"Error occurred during roadmap preparation phase: {str(e)[:200]}. Process halted and user will need to retry roadmap creation.",
                        status="error",
                        user_id=self.user_id,
                    )
                    appLogger.error({"event":"roadmap:prefill:prompt","error":e,"traceback":traceback.format_exc()})
                    # socketio.emit("roadmap_creation_agent",{"event": "stop_show_timeline"},room=client_id)
                    step_sender.sendError(key=str(e),function = "fetchPrefilledRoadmapOrProjectData")
                
        
        else: #Portfolio flow
            try:
                model_opts = ModelOptions(model="gpt-4.1", max_tokens=4096, temperature=0.1)
                # Track data gathering phase
                detailed_activity( 
                    activity_name="portfolio_context_gathering",
                    activity_description=f"Beginning data collection for portfolio creation, assessing portfolio relevance based on user requirements. Tenant ID: {self.tenant_id}",
                    user_id=self.user_id
                )
            
                step_sender.sendSteps("Creating Portfolio Canvas", False)
                all_portfolios = RoadmapDao.fetchAllPortfolioOfTenant(tenant_id=self.tenant_id)
                
                step_sender.sendSteps("Assessing Portfolio Alignment", False)
                portfolio_selection_prompt = roadmapInternalKnowledgePrompt(
                    conversation=qna,
                    org_info=self.tenantOrgInfo,
                    persona=self.customerPersona,
                    portfolios=all_portfolios
                )
                selection_response = self.llm.run(portfolio_selection_prompt,model_opts,'agent::portfolio_selection',logInDb=self.log_info)
                selection_output = extract_json_after_llm(selection_response,step_sender=step_sender)
                # print("--debug selection_output---", selection_output)
                
                selected_portfolio_ids = [p['id'] for p in selection_output.get('selected_portfolios', [])]    
                step_sender.sendSteps("Assessing Portfolio Alignment", True)  
            
               
                step_sender.sendSteps("Gathering Internal Knowledge", False)
                internal_knowledge = KnowledgeQueries.fetchPortfolioKnowledge(portfolio_ids=selected_portfolio_ids)
                # print("portfolio knowledge ", internal_knowledge)
                
                appLogger.info({"event":"internal_knowledge_portfolio", "status": "done","tenant_id": self.tenant_id, "user_id": self.user_id})
                TangoDao.insertTangoState(tenant_id=self.tenant_id, user_id=self.user_id,key="create_portfolio_sessionID", value= self.sessionId,session_id='')
                
                # Portfolio canvas details
                prompt = portfolioCanvasPrompt(
                    conversation = json.dumps(qna),
                    persona = json.dumps(self.customerPersona),
                    org_info = json.dumps(self.tenantOrgInfo),
                    portfolios=[p for p in all_portfolios if p['id'] in selected_portfolio_ids],  # Filter portfolios
                    internal_knowledge=internal_knowledge,
                )
                # print("\n\ndebug ---prompt for portfolio name & desc- ", prompt.formatAsString())
                response = self.llm.run(prompt, model_opts, 'agent::portfolio_creation', logInDb = self.log_info)
                output = extract_json_after_llm(response,step_sender=step_sender)
                # print("\n\n--debug response------ ", output)
                
                it_leader = output.get("it_leader",{})
                name = it_leader.get("name", "")
                output.pop("it_leader",None)
                output["it_leader"] = {
                    "first_name": name.split(' ')[0],
                    "last_name": " ".join(name.split(" ")[1:]) or "Kumar",
                    "role": it_leader.get("role", ""),
                    "email": it_leader.get("email", "")
                }
                
                step_sender.sendSteps("Gathering Internal Knowledge", True)  # Pass elapsed time
                # Track portfolio name and description generation
                detailed_activity(
                    activity_name="portfolio_basic_info_generation",
                    activity_description=f"Successfully generated portfolio name and description using AI analysis. Created portfolio titled '{output.get('portfolio_name', 'N/A')}' with detailed description. Utilized user conversation, organizational context, portfolio alignment, and internal knowledge to create comprehensive portfolio foundation ready for detailed planning stages.",
                    user_id=self.user_id
                )
                
                
                TangoDao.insertTangoState(tenant_id=self.tenant_id, user_id=self.user_id,
                    key="create_portfolio_basicInfo", 
                    value= json.dumps({
                        "basic_info": {"portfolioName": output.get("portfolio_name"),"Description": output.get("description")},
                        "internal_knowledge": internal_knowledge
                    }),
                    session_id=self.sessionId
                )
            
                # Track successful completion of portfolio preparation
                detailed_activity(
                    activity_name="portfolio_preparation_complete",
                    activity_description=f"portfolio preparation phase completed successfully. All necessary data has been collected, analyzed, and stored for portfolio '{output.get('roadmap_name', 'N/A')}'. System is ready to proceed to detailed roadmap creation stages (objectives, scope, timeline, roles, and budget estimation).",
                    user_id=self.user_id
                )
                step_sender.sendSteps("Creating Portfolio Canvas", True)  
                appLogger.info({"event": "portfolio:prefill:prompt:end", "data": len(output),"tenant_id": self.tenant_id, "user_id": self.user_id})
                return output
                    
            except Exception as e:
                # Track any errors in the portfolio creation process
                detailed_activity(
                    activity_name="portfolio_creation_error",
                    activity_description=f"Error occurred during portfolio preparation phase: {str(e)[:200]}. Process halted and user will need to retry portfolio creation.",
                    status="error",
                    user_id=self.user_id,
                )
                step_sender.sendError(key=str(e),function = "fetchPrefilledportfolioOrProjectData")
                appLogger.error({"event":"portfolio:prefill:prompt","error":e,"traceback":traceback.format_exc()})
        
        response = self.openai.chat.completions.create(
            model=self.modelOptions.model,
            messages=messages,
            max_tokens=self.modelOptions.max_tokens,
            temperature=self.modelOptions.temperature,
            stream=False,
        )
        try:
            TangoDao.createEntryInStats(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                function_name="fetchPrefilledRoadmapOrProjectData",
                model_name=response.model,
                total_tokens=response.usage.total_tokens,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens
            )
        except Exception as e:
            appLogger.error({"event": "error_in_storing_stats","error": str(e),"traceback": traceback.format_exc()})

        output = response.choices[0].message.content
        return extract_json_after_llm(output,step_sender=step_sender)

    def fetchOnlyQna(self):
        try:
            result = []
            for i, msg in enumerate(self.getConvMessagesArr(True)):

                if i == 0 or i == 1:
                    continue
                temp = {}
                if msg["role"] == "assistant":
                    try:
                        response_json = json.loads(msg["content"])
                    except Exception as e:
                        try:
                            response_json = json.loads(
                                extract_json_data(msg["content"])
                            )
                            # print("--debug response_json", response_json)
                        except Exception as e1:
                            extract_json = extract_json_v2(msg["content"])
                            # print("--debug extract_json", extract_json)
                            response_json = json.loads(extract_json)

                    temp["question"] = response_json["question"]
                    result.append(temp)

                else:
                    temp["answer"] = msg["content"]
                    result.append(temp)

            return result

        except Exception as e:
            raise e

    def parseMessagesAndReturn(self, only_question=False):
        try:
            answer_pattern = re.compile(
                r"Important: Remeber to read through all the info.*",
                re.DOTALL | re.IGNORECASE,
            )
            result = []
            for i, msg in enumerate(self.getConvMessagesArr(True)):
                if i == 0 or i == 1:
                    continue

                # print("--debug parseMessagesAndReturn msg: ", i, msg)
                if i % 2 == 0:
                    temp = {}
                    try:
                        response_json = json.loads(msg["content"])
                    except Exception as e:
                        # print("parseMessagesAndReturn error 1", e)
                        try:
                            # response_json = json.loads(
                            #     extract_json_after_llm(msg["content"])
                            # )
                            response_json = extract_json_after_llm(msg["content"])
                            
                            # print("--debug parseMessagesAndReturn response json ",
                            #       response_json)
                        except Exception as e1:
                            try:
                                print("parseMessagesAndReturn error 2", e1, i, msg)
                                extract_json = extract_json_v2(msg["content"])
                                response_json = json.loads(extract_json)
                            except Exception as e2:
                                print("parseMessagesAndReturn error 2", e1,)
                                try:
                                    extracted_json = extract_json_data_v2(
                                        msg["content"])
                                    response_json = json.loads(extracted_json)
                                except Exception as e3:
                                    print("parse error 3", e3)
                                # response_json = {}

                    if only_question:
                        temp["question"] = response_json["question"]
                    else:
                        temp["question"] = response_json
                        temp["question"]["id"] = i // 2 + 1
                        temp["answer"] = ""
                    result.append(temp)
                if i % 2 == 1:
                    temp = result[-1]
                    temp2 = re.sub(answer_pattern, "", msg["content"])
                    temp["answer"] = temp2

            return result

        except Exception as e:
            raise e

    def getConvMessagesArr(self, ignore_any_model_type=False):
        msgs = []
        for msg in self.dbMessages:
            msgs.append({"role": msg["role"], "content": msg["content"]})
        return msgs

    def getMessages(self):
        return json.dumps(self.dbMessages)

    def setMessagesFromDB(self, messages):
        self.dbMessages = messages