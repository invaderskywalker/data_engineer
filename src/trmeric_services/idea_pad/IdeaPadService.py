import json
import time
import traceback
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_services.idea_pad.Prompts import *
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_services.journal.Activity import activity, record
from src.trmeric_services.journal.Activity import detailed_activity, activity_log
from src.trmeric_database.dao import IdeaDao,PortfolioDao,CustomerDao,TenantDao,RoadmapDao,TangoDao
from datetime import datetime, timezone
from src.trmeric_services.agents.core.agent_functions import AgentFunction,AgentFnTypes
from src.controller.qna import QnaController
from src.trmeric_services.roadmap.utils import parse_auditlog_response
from src.trmeric_database.Redis import RedClient

class IdeaPadService:
    def __init__(self):
        self.llm = ChatGPTClient()
        self.qna_controller = QnaController()
        self.modelOptions = ModelOptions(model="gpt-4.1",max_tokens=9000,temperature=0.2)

    @activity("idea_generation_complete")
    def generateIdeas(
        self, tenant_id, idea_theme, user_id=None, socket_id=None, log_input=None
    ):
        # Record input data and description for activity logging
        record("input_data", {
            "user_request": "Generate strategic ideas",
            "idea_theme": idea_theme,
            "tenant_context": "Analyzing organizational portfolios, KPIs, and strategic goals"
        })
        record("description", "Complete idea generation transformation: User requested strategic ideas with specific theme, Tango analyzed organizational context and generated contextual business/IT strategies aligned with company goals and KPIs.")
        
        portfolios = PortfolioDao.fetchPortfoliosOfTenant(
            tenant_id=tenant_id
        )
        prev_ideas = IdeaDao.fetchPreviousIdeasOfTenant(
            tenant_id=tenant_id)
        defaultKPIs = IdeaDao.fetchDefaultIdeasKPIs(
            tenant_id=tenant_id
        )
        defaultStrategy = IdeaDao.fetchDefaultIdeasStrategy(
            tenant_id=tenant_id
        )
        tenantPersona = CustomerDao.FetchCustomerPersona(tenant_id=tenant_id)[
            0]['persona']
        tenantOrgInfo = CustomerDao.FetchCustomerOrgDetailInfo(
            tenant_id=tenant_id)[0]['org_info']

        prompt = generateIdeasPrompt(
            portfolios=portfolios,
            prev_ideas=prev_ideas,
            org_details=tenantOrgInfo,
            org_persona=tenantPersona,
            defaultKPIs=defaultKPIs,
            defaultStrategicGoals=defaultStrategy,
            idea_theme=idea_theme
        )

        response = self.llm.run(
            prompt, 
            self.modelOptions, 
            "generateIdeas",
            logInDb=log_input
        )
        return extract_json_after_llm(response)

    @activity("idea_enhancement_complete")
    def enhanceIdea(
        self, tenant_id, idea, user_id=None, socket_id=None, log_input=None
    ):
        # Record input data and description for activity logging
        record("input_data", {
            "user_request": "Enhance strategic idea",
            "original_idea": idea,
            "organizational_context": "KPIs, strategic goals, org details analyzed"
        })
        record("description", "Complete idea enhancement transformation: User provided basic idea, Tango enhanced it with strategic depth, alignment to organizational goals/KPIs, complexity analysis, and actionable recommendations.")
        
        defaultKPIs = IdeaDao.fetchDefaultIdeasKPIs(
            tenant_id=tenant_id)
        defaultStrategy = IdeaDao.fetchDefaultIdeasStrategy(
            tenant_id=tenant_id)
        tenantPersona = CustomerDao.FetchCustomerPersona(tenant_id=tenant_id)[
            0]['persona']
        tenantOrgInfo = CustomerDao.FetchCustomerOrgDetailInfo(
            tenant_id=tenant_id)[0]['org_info']

        prompt = enhanceIdeaPrompt(
            idea,
            org_details=tenantOrgInfo,
            org_persona=tenantPersona,
            defaultKPIs=defaultKPIs,
            defaultStrategicGoals=defaultStrategy
        )

        response = self.llm.run(
            prompt,
            self.modelOptions,
            "enhanceIdea",
            logInDb=log_input
        )
        return extract_json_after_llm(response)

    @activity("idea_roadmap_creation_complete")
    def createRoadmapFromIdea(
        self, tenant_id, entity_id, user_id=None, socket_id=None, log_input=None
    ):
        idea_details = IdeaDao.fetchIdeaDetails(tenant_id, entity_id)
        reducedIdeaDetails = {
            "idea_title": idea_details[0]['title'],
            "idea_description": idea_details[0]['elaborate_description'],
            "idea_strategies": idea_details[0]['list_of_strategies'],
            "idea_kpis": idea_details[0]['list_of_kpis']
        }
        
        # Record input data and description for activity logging
        record("input_data", {
            "user_request": "Create roadmap from idea",
            "entity_id": entity_id,
            "idea_details": reducedIdeaDetails,
            "organizational_context": "Idea details, org persona, and details analyzed"
        })
        record("description", "Complete roadmap creation transformation: User requested roadmap from strategic idea, Tango analyzed idea details and organizational context to generate comprehensive implementation roadmap with objectives, constraints, capabilities, and resource requirements.")

        tenantPersona = CustomerDao.FetchCustomerPersona(tenant_id=tenant_id)[
            0]['persona']
        tenantOrgInfo = CustomerDao.FetchCustomerOrgDetailInfo(
            tenant_id=tenant_id)[0]['org_info']

        prompt = createRoadmapFromIdeaPrompt(
            reducedIdeaDetails,
            org_details=tenantOrgInfo,
            org_persona=tenantPersona,
        )
        response = self.llm.run(
            prompt, 
            self.modelOptions,
            "createRoadmapFromIdea",
            logInDb=log_input
        )
        return extract_json_after_llm(response)


    def fetch_idea_chat_prefill(self, socketio, client_id, metadata, **kwargs):
        """
        Wrapper method to call QnaController.fetchQnaChatPrefillSocketIO with _type=6.
        """
        return self.qna_controller.fetchQnaChatPrefillSocketIO(
            socketio=socketio,
            client_id=client_id,
            metadata=metadata,
            _type="idea" #_type=6 for "idea"
        )

    def get_ideation_context(self,tenant_id=None,user_id=None,idea_id=None):

        from src.trmeric_services.agents.core.base_agent import BaseAgent
        from src.trmeric_services.chat_service.utils import _process_solutions
        base_agent = BaseAgent(log_info={"tenant_id":tenant_id,"user_id":user_id})

        # language = UsersDao.fetchUserLanguage(user_id = user_id)
        existing_solutions_ = TenantDao.listCustomerSolutions(tenant_id)
        existing_solutions = _process_solutions(solutions=existing_solutions_,limit=4)

        existing_roadmaps_and_projects = base_agent.project_and_roadmap_context_string
        idea_data = IdeaDao.fetchIdeaDetails(tenant_id=tenant_id, idea_id=idea_id)[0] if idea_id else None
        return {
            # "language": language,
            "idea_data": idea_data,
            "existing_solutions": existing_solutions,
            "existing_roadmaps_and_projects": existing_roadmaps_and_projects,
        }


    @activity("ideation_insights_complete")
    def createIdeationInsights(self,canvas,tenant_id,user_id,language='English',step_sender=None):
        
        try:
            context = RedClient.execute(
                query = lambda: self.get_ideation_context(tenant_id=tenant_id,user_id=user_id),
                key_set = f"IdeationContext::tenant_id:{tenant_id}::user_id:{user_id}",
                expire = 86400
            )

            language = language or "English"
            existing_solutions = context.get("existing_solutions","") or None
            existing_roadmaps_and_projects = context.get("existing_roadmaps_and_projects","")or None

            prompt = ideationInsightsPrompt(
                idea_canvas = json.dumps(canvas,indent=2),
                solutions = json.dumps(existing_solutions,indent=2),
                existing_roadmaps_and_projects = existing_roadmaps_and_projects,
                language=language
            )
            # print("\n--debug [IdeaInsights] prompt-----", prompt.formatAsString())

            response = self.llm.run(prompt, self.modelOptions,'agent::create_ideation_insights', logInDb={"tenant_id":tenant_id,"user_id":user_id})
            result = extract_json_after_llm(response,step_sender=step_sender)
            # print("--debug result [sol insights]---", result)        
            appLogger.info({"event": "createIdeationInsights", "msg": "done","tenant_id":tenant_id,"user_id":user_id})
            return result
        
        except Exception as e:
            if step_sender:
                step_sender.sendError(key=f"Error generating idea insights",function="createIdeationInsights")
            appLogger.error({"event": "createIdeationInsights", "error": e, "traceback": traceback.format_exc(),"tenant_id":tenant_id,"user_id":user_id})
            return {}




    ### Create History view or Audit Log for Demand change
    def createIdeationAuditHistory(self,tenantID=None,userID=None,socketio=None,client_id=None,cache_seconds=86400*10,entity='idea',model_name='Concept',**kwargs):
        # return
        data = kwargs.get("data",{})
        entity_id = data.get("idea_id","")
        step_sender = kwargs.get("steps_sender",None)
        if not entity_id:
            step_sender.sendError(key="No idea_id provided",function=f"createAuditHistory")
            return {}
        try:
            insights = TangoDao.fetchTangoStatesTenant(tenant_id=tenantID, key=f"{entity}_auditlog_{entity_id}", _limit=1)
            if len(insights)==0 or (len(insights)>0 and insights[0]["created_date"] is not None and (datetime.now(timezone.utc) - datetime.fromisoformat(insights[0]["created_date"])).seconds > cache_seconds):
            
                audit_logs = TenantDao.fetchAuditLogData(
                    projection_attrs=["model_name","action","changes","timestamp","user_id"],
                    object_id=entity_id,
                    model_name = model_name,
                    tenant_id = tenantID
                )
                print("\n\n--debug audit_logs------", len(audit_logs))

                if not audit_logs:
                    socketio.emit(f"{entity}_creation_agent",{"event":f"{entity}_logs","data":"No data found","entity_id": entity_id},room=client_id)
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
                all_users = TenantDao.FetchUsersOfTenant(tenant_id=tenantID)
                user_mapping = {}
                for user in all_users:
                    user_mapping[user["user_id"]] = user["first_name"]

                # print("\n\n--debug user_mapping-------", user_mapping)

                prompt = changeHistoryPrompt(
                    audit_logs = json.dumps(audit_logs),
                    existing_insights = insights_val,
                    user_mapping = user_mapping,
                    user_id=userID, 
                    entity=entity
                )
                response = self.llm.run(prompt, self.modelOptions,f"agent::{entity}_logs", logInDb={"tenant_id":tenantID,"user_id":userID})

                # print("\n\n--debug response changelog---", response)
                result = extract_json_after_llm(response,step_sender=step_sender)

                data = result.get("change_logs",[]) or []
                data =  data + insights_val
                TangoDao.upsertTangoState(
                    tenant_id=tenantID, user_id=userID, key=f"{entity}_auditlog_{entity_id}",
                    value=json.dumps(data), session_id=None
                )
            else:
                insights_val = insights[0]["value"]
                created_date = insights[0]["created_date"]
                print("--debug insight already there------", len(insights_val))
                
                appLogger.info({"event":"create_auditLog","msg":"Insights present","created_date":created_date,f"{entity}_id":entity_id,"tenant_id":tenantID})
                data = json.loads(insights_val) or []

            logs = parse_auditlog_response(data)
            socketio.emit(f"{entity}_creation_agent",{"event":f"{entity}_logs","data":logs,f"{entity}_id": entity_id},room=client_id)
            return
        except Exception as e:
            step_sender.sendError(key="Error creating changelogs",function=f"createAuditHistory")
            appLogger.error({"event": "createAuditHistory","error": str(e),"traceback":traceback.format_exc()})


    #Idea's scope
    def createIdeationScope(self,tenantID=None, userID=None,data=None,socketio=None,client_id=None,logInfo=None,sessionID=None, **kwargs):
        
        try:
            step_sender = kwargs.get("steps_sender",None)

            idea_id = data.get("idea_id","")
            print("--deubg createIdeationScope--------", idea_id)
            start = time.time()
            steps_sender_class = step_sender
            steps_sender_class.sendSteps("Gathering Ideation Information", False)
            
            context = RedClient.execute(
                query = lambda: self.get_ideation_context(tenant_id=tenantID,user_id=userID,idea_id=idea_id),
                key_set = f"IdeationContext::tenant_id:{tenantID}::user_id:{userID}::idea_id:{idea_id}",
                expire = 86400
            )
            # context = self.get_ideation_context(tenant_id=tenantID,user_id=userID,idea_id=idea_id)
            
            idea_details = context.get("idea_data",{}) or None
            print("\n\n--debug idea_details-------", idea_details)
            solutions = context.get("existing_solutions",[]) or []
            language = context.get("language","English") or "English"
            idea_portfolio = idea_details[0].get("list_of_portfolios",[]) if idea_details and len(idea_details)>0 else []

            print("\n\n--debug createIdeationScope  idea_portoflio----", idea_portfolio, "Solutions: ", len(solutions))
            solution_context = []
            for sol in solutions:
                new_sol = {k: v for k, v in sol.items() if k not in ["additional_details","id","tenant_id","application_type","service_line"]}
                new_sol["type"] = sol["application_type"] if "application_type" in sol else "NA"
                new_sol["portfolio"] = sol["service_line"] if "service_line" in sol else "NA"

                if len(idea_portfolio)>0:
                    for portfolio in idea_portfolio:
                        service_line = sol.get("service_line") or ""
                        if len(service_line)>0 and portfolio.lower() in service_line.lower():
                            solution_context.append(new_sol)
                else:
                    continue

            conv_ = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id=sessionID, user_id=userID, key="create_idea_conv")
            conv = conv_[0].get("value","") if len(conv_)>0 else {}

            # uploaded_files = FileDao.s3ToOriginalFileMapping(sessionID =session_id,userID=userID, file_type='DEMAND_FILE_UPLOAD') 
            # file_content = process_uploaded_files(FileAnalyzer(tenant_id=tenantID),uploaded_files,step_sender=steps_sender_class,source='scope')    

            steps_sender_class.sendSteps("Gathering idea Information", True)
            # print("--debug createidea2_ey_context------ Conv: ", len(conv), uploaded_files)

            steps_sender_class.sendSteps("Analyzing Scope Requirements", False)                
            prompt = ideationScopePrompt(
                language = language,
                conversation = json.dumps(conv,indent=2),
                idea_details = json.dumps(idea_details,indent=2),
                solution_context = json.dumps(solution_context,indent=2)
                # files= json.dumps(file_content,indent=2),
            )
            # print("\n--debug [Scope] prompt-----", prompt.formatAsString())

            response = self.llm.run(prompt, self.modelOptions,'agent::create_ideascope', logInDb = logInfo,socketio=socketio,client_id=client_id)
            result = extract_json_after_llm(response,step_sender=steps_sender_class)
            
           
            steps_sender_class.sendSteps("Analyzing Scope Requirements", True)
            elapsed_time = int(time.time() - start)  # Calculate time taken
            print("--debug time taken createidea2_ey----", elapsed_time)
            
            socketio.emit("ideation_agent",{"event":"idea_scope","data":result,"session_id":sessionID,"idea_id": idea_id},room=client_id)
            appLogger.info({"event": "createIdeaScope","idea_id": idea_id,"log_info":logInfo,"msg": "done", "time": elapsed_time})

        except Exception as e:
            step_sender.sendError(key=f"Error generating scope: {str(e)}",function="createIdeaScope")
            appLogger.error({"event": "createIdeaScope", "error": e,"idea_id": idea_id,"log_info":logInfo,"traceback": traceback.format_exc()})
            
        return
            
    
    def createDemandInsightsFroParentIdea(self, tenantID=None, userID=None, data=None, socketio=None,client_id=None, **kwargs):
        try:
            from src.trmeric_services.roadmap.RoadmapService import RoadmapService
            roadmapService = RoadmapService()
            
            step_sender = kwargs.get("steps_sender",None)
            idea_id = data.get("idea_id") or 0
            
            idea_data = self.get_ideation_context(tenant_id=tenantID, user_id=userID, idea_id=idea_id)
            idea_data = idea_data.get("idea_data") or {}
            data={"ideas": idea_data}
            result = roadmapService.createDemandInsights(data,tenantID,userID,step_sender=step_sender)
            
            socketio.emit("ideation_agent",{"event":"demand_insight","data":result,"idea_id": idea_id},room=client_id)
            appLogger.info({"event": "createDemandInsightsFroParentIdea","idea_id": idea_id,"msg": "done"})

        except Exception as e:
            step_sender.sendError(key=f"Error generating scope: {str(e)}",function="createIdeaScope")
            appLogger.error({"event": "createDemandInsightsFroParentIdea", "error": e,"idea_id": idea_id,"traceback": traceback.format_exc()})
            
        return
        
    
            
    




CREATE_IDEA_INSIGHTS = AgentFunction(
    name="createIdeationInsights",
    description="""This function is used to generate the ideation insights for newly generated idea canvas.""",
    args=[],
    return_description="",
    function=IdeaPadService.createIdeationInsights,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)

CREATE_IDEA_LOGS = AgentFunction(
    name="createIdeationAuditHistory",
    description="""This function is used to track the changelog made to an idea.""",
    args=[],
    return_description="",
    function=IdeaPadService.createIdeationAuditHistory,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)

CREATE_IDEA_SCOPE = AgentFunction(
    name="createIdeationScope",
    description="""This function is used to generate scope for idea.""",
    args=[],
    return_description="",
    function=IdeaPadService.createIdeationScope,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)


QNA_CHAT_PREFILL_IDEA= AgentFunction(
    name="fetch_idea_chat_prefill",
    description="""This function is used to generate the canvas for different workflows(chat_types)""",
    args=[],
    return_description="",
    function=IdeaPadService.fetch_idea_chat_prefill,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)

CREATE_DEMAND_INSIGHTS_FROM_IDEA = AgentFunction(
    name="create_demand_insights_from_parent_idea",
    description="""This function is used to generate..""",
    args=[],
    return_description="",
    function=IdeaPadService.createDemandInsightsFroParentIdea,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)

