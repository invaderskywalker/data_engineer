import os
import re
import json
import time
import datetime
import traceback
import concurrent.futures
from src.trmeric_services.chat_service.utils import *
from src.trmeric_services.chat_service.Prompts import *
from src.trmeric_api.logging.AppLogger import appLogger
from .base import ChatService
from src.trmeric_services.journal.Activity import detailed_activity, activity, record
from src.trmeric_utils.json_parser import *
from src.trmeric_services.phoenix.queries import KnowledgeQueries
from src.trmeric_services.roadmap.RoadmapService import RoadmapService
# from src.trmeric_utils.helper.file_analyser import FileAnalyzer
import random
from src.trmeric_services.agents.functions.graphql_v2.analysis.roadmap_inference import (
    infer_roadmap, 
    format_guidance_for_canvas_stages,
    format_basic_stage_prompt_section,
    format_okr_stage_prompt_section,
    format_cpc_stage_prompt_section,
    format_pattern_info_markdown
)
from src.trmeric_services.agents.functions.graphql_v2.utils.tenant_helper import is_knowledge_integrated

class RoadmapChat(ChatService):
    def __init__(self, request_info, session_id, chat_type):
        self.roadmap_service = RoadmapService()
        # self.file_analyzer = FileAnalyzer(tenant_id = request_info.get("tenant_id"))

    def start_session(self, chat, **kwargs):
        print(f"Starting session for ChatType {chat.chat_type} with session_id: {chat.session_id}")
        detailed_activity(
            activity_name="roadmap_creation_initiation",
            activity_description="User has started the roadmap creation process. Initializing roadmap creation chat with user.",
            user_id=chat.user_id,
        )
        # content = getRoadmapQnaChat_V2(chat.roadmapContext, user_id=chat.user_id)
        #  - **role**: {role}
        #     - **name**: User's name
        #     - **customer_context**: Company, industry, business details (e.g., FinTech, Healthcare)
        #     - **portfolio**: List of portfolios the user oversees
        #     - **org_strategy**: Strategic goals (e.g., revenue growth, compliance)
        #     - **knowledge**:
        print("--debug in start_session roadmap------- role", chat.context.get("role"))
        content = getRoadmapQnaChat_V2(
            persona = {
                "role": chat.context.get("role"),
                "customer_context": chat.context.get("customer_info",{}),
                "portfolio": chat.context.get("user_portfolios",[]),
                "org_strategy": chat.context.get("org_alignment" ,[]),
                "knowledge": chat.context.get("solutions_knowledge",[])
            },
            language = chat.context.get("user_language","English") or "English"
        )
        # if chat.tenant_id in DEMAND_TENANTS else getRoadmapQnaChat(json.dumps(context.get("persona", {}) or {}))
        return {
            "role": "system",
            "content": content,
            "username": "Tango",
            "time": datetime.datetime.now().isoformat(),
        }

    def fetchPrefilledRoadmapOrProjectData(self, chat, socketio, client_id, step_sender=None, **kwargs):
        step_start_times = {}
        # if (chat.tenant_id in DEMAND_TENANTS) or True:
        try:
            context = chat.context
            conversation  = chat.fetchOnlyQna()
            uploaded_files = chat.getConvUploadedFiles()
            release_quarter = TenantDao.fetchReleaseCycleTag(tenant_id=chat.tenant_id)
            quarter_tags = [q['title'].strip() for q in release_quarter] if len(release_quarter)>0 else ['Q1','Q2','Q3','Q4']

            print("--debug uploaded_files-----", uploaded_files, quarter_tags)
            files_content = process_uploaded_files(chat.file_analyzer, uploaded_files, step_sender=step_sender, source='creation')

            step_sender.sendSteps("Gathering Internal Knowledge", False)

            internal_knowledge = context.get("solutions_knowledge") or []
            org_strategy = context.get("org_alignment") or []
            all_portfolios = context.get("all_portfolios") or []

            appLogger.info({"event":"internal_knowledge_rodmap", "status": "done","tenant_id": chat.tenant_id, "user_id": chat.user_id})
            step_sender.sendSteps("Gathering Internal Knowledge", True)

            step_key = "Creating Demand Canvas"
            step_sender.sendSteps(step_key, False)
            step_start_times[step_key] = time.time()

            # Infer roadmap guidance from graph patterns (if knowledge is integrated)
            stage_guidance = {"basic": {}, "okr": {}, "cpc": {}}
            
            graphname = is_knowledge_integrated(chat.tenant_id)
            pattern_info = None  # Initialize pattern_info
            
            if graphname:
                try:
                    description_text = "\n".join([f"Q: {item.get('question','')}\nA: {item.get('answer','')}" for item in conversation])
                    
                    inference_result = infer_roadmap(
                        roadmap_data={"description": description_text, "tenant_id": chat.tenant_id},
                        graphname=graphname,
                        tenant_id=chat.tenant_id
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
                        
                        # Format pattern information as user-friendly markdown
                        pattern_info = format_pattern_info_markdown(inference_result)
                        print(" DEBUG: pattern_info generated, length:", len(pattern_info) if pattern_info else 0)
                        print(" DEBUG: pattern_info preview:", pattern_info[:200] if pattern_info else "EMPTY")
                        
                        appLogger.info({"event": "roadmap_inference_success", "tenant_id": chat.tenant_id, "pattern_name": pattern_name})
                    else:
                        failure_reason = inference_result.get("inference_status", "unknown") if inference_result else "null_result"
                        failure_msg = inference_result.get("message", "") if inference_result else ""
                        appLogger.warning({"event": "roadmap_inference_incomplete", "status": failure_reason, "message": failure_msg})
                except Exception as e:
                    appLogger.error({"event": "roadmap_inference_failed", "error": str(e), "traceback": traceback.format_exc()})
            else:
                appLogger.info({"event": "roadmap_knowledge_not_integrated", "tenant_id": chat.tenant_id, "using_default_flow": True})

            cpc=None
            okr=None
            basic_info=None
            roadmap_canvas = {}

            stages = ["basic", "okr", "cpc"]
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = [
                    executor.submit(
                        self.roadmap_service.create_roadmap_canvas,
                        tenant_id=chat.tenant_id,
                        user_id=chat.user_id,
                        roadmap_stage=stage,
                        conversation=conversation,
                        persona=chat.context.get("persona", {}) or {},
                        org_info=chat.context.get("tenant_info", {}) or {},
                        org_alignment=org_strategy,
                        portfolios=all_portfolios,
                        internal_knowledge=internal_knowledge,
                        socketio=socketio,
                        client_id=client_id,
                        step_sender=step_sender,
                        guidance=stage_guidance.get(stage, {}),
                        files_content = json.dumps(files_content),
                        quarter_tags = quarter_tags,
                    )
                    for stage in stages
                ]
            results = {stage: future.result() for stage, future in zip(stages, futures)}
            basic_info, okr, cpc = results["basic"], results["okr"], results["cpc"]
            
            #Assign Quarter tag
            quarter = basic_info.get("quarter","") or ""
            basic_info.pop("quarter", None)
            for item in release_quarter:
                tag = item.get("title","") or ""
                if not tag:
                    continue
                if (quarter and quarter.lower()) in tag.lower():
                    quarter = item
                    break                   
            basic_info["quarter"] = quarter if len(release_quarter)>0 else {}
            print("---debug quarter tag------", basic_info["quarter"])
            
            # Add pattern_info to basic_info so it flows into tango_analysis when saved
            print(" DEBUG: Before adding to basic_info, pattern_info exists:", bool(pattern_info))
            if pattern_info:
                basic_info["pattern_info"] = pattern_info
                print(" DEBUG: pattern_info ADDED to basic_info stage")
            
            roadmap_canvas["basic"] = basic_info
            roadmap_canvas["okr"] = okr
            roadmap_canvas["cpc"] = cpc


            step_sender.sendSteps("Matching Existing Solutions", False)
            start = time.time() 
            
            solution_insights = self.roadmap_service.creatDemandInsights(roadmap_canvas,chat.tenant_id,chat.user_id,step_sender=step_sender)
            roadmap_canvas["insights"] = solution_insights
            roadmap_canvas["creation_source"] = "conversation"
            roadmap_canvas["session_id"] = chat.session_id
        
            
            elapsed_time = time.time()-start
            print("--debug time taken for solution_insights--", elapsed_time)
            step_sender.sendSteps("Matching Existing Solutions", True, time=elapsed_time)
            
            
            # with open(f"roadmap_canvas_{chat.user_id}.json", "w") as f:
            #     json.dump(roadmap_canvas, f, indent=4)
            
            
            elapsed_time = time.time() - step_start_times[step_key]  # Calculate time taken
            print("--debug time taken for creating roadmap canvas---", elapsed_time)
            step_sender.sendSteps(step_key, True, time=elapsed_time)  # Pass elapsed time

            # Final verification before returning to backend
            print(" DEBUG FINAL: pattern_info in basic_info?", "pattern_info" in roadmap_canvas.get("basic", {}))
            print(" DEBUG FINAL: pattern_info at top level?", "pattern_info" in roadmap_canvas)
            if "pattern_info" in roadmap_canvas.get("basic", {}):
                print(" DEBUG FINAL: basic['pattern_info'] exists, length:", len(roadmap_canvas["basic"]["pattern_info"]))

            appLogger.info({"event": "roadmap:prefill::canvas::end", "data": len(roadmap_canvas),"tenant_id": chat.tenant_id, "user_id": chat.user_id})
            return roadmap_canvas
        except Exception as e:
            appLogger.error({"event":"roadmap:prefill:prompt","error":e,"traceback":traceback.format_exc()})
            step_sender.sendError(key=str(e),function = "fetchPrefilledRoadmapOrProjectData")

        ###Normal roadmap flow
        # else:
        #     appLogger.info({"event": "roadmap:normal_flow_start","tenant_id": chat.tenant_id, "user_id": chat.user_id})
        #     try:
        #         detailed_activity(
        #             activity_name="roadmap_context_gathering",
        #             activity_description=f"Beginning data collection for roadmap creation. Fetching tenant portfolios, organizational strategy alignments, and assessing portfolio relevance based on user requirements. Tenant ID: {chat.tenant_id}",
        #             user_id=chat.user_id
        #         )
        #         step_key = "Fetching Portfolio"
        #         step_sender.sendSteps(step_key, False)
        #         step_start_times[step_key] = time.time()

        #         all_portfolios = RoadmapDao.fetchAllPortfolioOfTenant(tenant_id=chat.tenant_id)
        #         elapsed_time = time.time() - step_start_times[step_key]
        #         step_sender.sendSteps(step_key, True, time=elapsed_time)

        #         step_key = "Fetching Org Strategy Alignment"
        #         step_sender.sendSteps(step_key, False)
        #         step_start_times[step_key] = time.time()

        #         org_strategy = RoadmapDao.fetchOrgStrategyAlignMentOfTenant(tenant_id=chat.tenant_id)
        #         elapsed_time = time.time() - step_start_times[step_key]
        #         print("--debug time taken for fetching org strategy alignment---", elapsed_time)


        #         step_sender.sendSteps(step_key, True, time=elapsed_time)
        #         TangoDao.insertTangoState(tenant_id=chat.tenant_id, user_id=chat.user_id,
        #             key="create_roadmap_personaPortfolioOrgStrategy",
        #             value=json.dumps({
        #                 "customer_persona": chat.context.get("persona", {}) or {},
        #                 "portfolios": all_portfolios,
        #                 "org_strategy": org_strategy
        #             }),
        #             session_id=chat.session_id
        #         )

        #         step_key = "Assessing Portfolio Alignment"
        #         step_sender.sendSteps(step_key, False)
        #         step_start_times[step_key] = time.time()

        #         portfolio_selection_prompt = roadmapInternalKnowledgePrompt(
        #             conversation=chat.fetchOnlyQna(),
        #             org_info=chat.context.get("tenant_info", {}) or {},
        #             persona=chat.context.get("persona", {}) or {},
        #             portfolios=all_portfolios
        #         )
        #         selection_response = chat.llm.run(portfolio_selection_prompt, chat.modelOptions1,
        #             'agent::portfolio_selection',
        #             logInDb={"tenant_id": chat.tenant_id, "user_id": chat.user_id}
        #         )
        #         selection_output = extract_json_after_llm(selection_response)

        #         elapsed_time = time.time() - step_start_times[step_key]
        #         print("--debug time taken for internal knowledge--", elapsed_time)

        #         step_sender.sendSteps(step_key, True, time=elapsed_time)
        #         selected_portfolio_ids = [p['id'] for p in selection_output.get('selected_portfolios', [])]

        #         detailed_activity(
        #             activity_name="roadmap_portfolio_analysis",
        #             activity_description=f"Completed portfolio relevance analysis using AI. Analyzed {len(all_portfolios)} available portfolios and selected {len(selected_portfolio_ids)} relevant portfolios based on user requirements and organizational context. Selected portfolio IDs: {selected_portfolio_ids}",
        #             user_id=chat.user_id
        #         )

        #         step_key = "Gathering Internal Knowledge"
        #         step_sender.sendSteps(step_key, False)
        #         step_start_times[step_key] = time.time()

        #         internal_knowledge = KnowledgeQueries.fetchPortfolioKnowledge(portfolio_ids=selected_portfolio_ids)
        #         elapsed_time = time.time() - step_start_times[step_key]
        #         detailed_activity(
        #             activity_name="roadmap_knowledge_retrieval",
        #             activity_description=f"Retrieved internal knowledge from selected portfolios. Gathered {len(internal_knowledge) if internal_knowledge else 0} knowledge items from {len(selected_portfolio_ids)} portfolios to inform roadmap creation. Knowledge will be used to enhance roadmap accuracy and alignment with organizational capabilities.",
        #             user_id=chat.user_id
        #         )

        #         appLogger.info({"event":"internal_knowledge_rodamp", "status": "done"})
        #         step_sender.sendSteps(step_key, True, time=elapsed_time)

        #         TangoDao.insertTangoState(tenant_id=chat.tenant_id, user_id=chat.user_id,
        #             key="create_roadmap_sessionID", value=chat.session_id,
        #             session_id='')
                
        #         step_key = "Creating Roadmap"
        #         step_sender.sendSteps(step_key, False)

        #         step_start_times[step_key] = time.time()
        #         prompt = roadmapBasicInfoPrompt(
        #             conversation=chat.fetchOnlyQna(),
        #             org_info=chat.context.get("tenant_info", {}) or {},
        #             persona=chat.context.get("persona", {}) or {},
        #             org_alignment=org_strategy,
        #             portfolios=[p for p in all_portfolios if p['id'] in selected_portfolio_ids],
        #             internal_knowledge=internal_knowledge,
        #         )
        #         response = chat.llm.run(
        #             prompt, chat.modelOptions1,
        #             'agent::roadmap_creation',
        #             logInDb={"tenant_id": chat.tenant_id, "user_id": chat.user_id}
        #         )
        #         output = extract_json_after_llm(response, step_sender=step_sender)
                
        #         detailed_activity(
        #             activity_name="roadmap_basic_info_generation",
        #             activity_description=f"Successfully generated roadmap name and description using AI analysis. Created roadmap titled '{output.get('roadmap_name', 'N/A')}' with detailed description. Utilized user conversation, organizational context, portfolio alignment, and internal knowledge to create comprehensive roadmap foundation ready for detailed planning stages.",
        #             user_id=chat.user_id
        #         )
        #         elapsed_time = time.time() - step_start_times[step_key]
        #         print("--debug time taken for creating roadmap name & desc---", elapsed_time)
        #         step_sender.sendSteps(step_key, True, time=elapsed_time)
                
        #         TangoDao.insertTangoState(tenant_id=chat.tenant_id, user_id=chat.user_id,
        #             key="create_roadmap_basicInfo",
        #             value=json.dumps({
        #                 "basic_info": {"RoadmapName": output.get("roadmap_name"),"Description": output.get("description")},
        #                 "internal_knowledge": internal_knowledge
        #             }),
        #             session_id=chat.session_id
        #         )
        #         detailed_activity(
        #             activity_name="roadmap_preparation_complete",
        #             activity_description=f"Roadmap preparation phase completed successfully. All necessary data has been collected, analyzed, and stored for roadmap '{output.get('roadmap_name', 'N/A')}'. System is ready to proceed to detailed roadmap creation stages (objectives, scope, timeline, roles, and budget estimation).",
        #             user_id=chat.user_id
        #         )
        #         appLogger.info({"event": "roadmap:prefill:prompt:end", "data": len(output),"tenant_id": chat.tenant_id, "user_id": chat.user_id})
        #         return output
        #     except Exception as e:
        #         detailed_activity(
        #             activity_name="roadmap_creation_error",
        #             activity_description=f"Error occurred during roadmap preparation phase: {str(e)[:200]}. Process halted and user will need to retry roadmap creation.",
        #             status="error",
        #             user_id=chat.user_id,
        #         )
        #         appLogger.error({"event":"roadmap:prefill:prompt","error":e,"traceback":traceback.format_exc()})
        #         step_sender.sendError(key=str(e),function = "fetchPrefilledRoadmapOrProjectData")



    ##Not in use
    def post_demand_canvas(self,chat, stage, files, canvas, step_sender):

        start = time.time()
        if stage == "insights": ##Demand insights
            step_sender.sendSteps("Matching Existing Solutions", False)

            solution_insights = self.roadmap_service.createDemandInsights(canvas, chat.tenant_id, chat.user_id, step_sender=step_sender)
            step_sender.sendSteps("Matching Existing Solutions", True)
            return solution_insights
            

        else:
            print("---something wentwrong------", files)
            step_sender.sendError(key="Couldn't fetch uploaded files",function = "post_demand_canvas")
            appLogger.info({"event": "post_demand_canvas","msg": "something went wrong {files}","tenant_id": chat.tenant_id, "user_id": chat.user_id})
            return {}


    def sample_beginnings(self, name, portfolios, limit: int = 9):
        
        portfolio_count = len(portfolios)
        
        if portfolio_count < limit:
            portfolio_str = ", ".join(portfolios)
            beginnings = [
                f"🎯 Hello {name}, I see you currently manage {portfolio_str}. Which of these would you like to create demand in?",
                f"💼 Hi {name}, looks like you’re overseeing {portfolio_str}. Where should we focus demand generation today?",
                f"🎉 Hello, {name} let's begin. I see you have access to {portfolio_str} portfolio(s). Which portfolio would you like to create demand in?",
            ]

        # 🌐 Case 2: Many portfolios — summarize for cleaner UX
        else:
            sample_list = ", ".join(portfolios[:limit])
            remaining = portfolio_count - limit
            beginnings = [
                f"🎉 Hello {name}, let’s get started. You have access to several portfolios — including {sample_list}, and {remaining} more. Which one would you like to create demand in?",
                f"🎉 Hello, {name} let's begin. I see you have access to {sample_list} and {remaining} other portfolio(s). Which portfolio would you like to create demand in?",
                f"📈 Hello {name}, impressive lineup — {sample_list}, and {remaining} additional portfolios. Which one are we driving new demand for?",
            ]


        return random.choice(beginnings)


    def generate_next_question(self, chat, **kwargs):
        # if chat.chat_type == 3 and len(chat.getConvMessagesArr()) == 2:
        # if (chat.tenant_id in DEMAND_TENANTS) or True:
        context = chat.context
        user_portfolios = context.get("user_portfolios")
        # portfolio_str = f"{', '.join(map(str, chat.user_portfolios))}"
        # language = UsersDao.fetchUserLanguage(user_id=chat.user_id)
        portfolio_str = f"{', '.join(map(str, user_portfolios))}"
        first_question = self.sample_beginnings(chat.name,user_portfolios,limit=9)

        language = context.get("user_language") or "English"
        # print("--debug context-----", portfolio_str)
        if language == "Spanish":
            portfolio_str += " portafolio(s)"
            return f"""<|end_header_id|>

Aquí está la primera pregunta::
```
{{
    "question": "🎉 Hola, {chat.name}, comencemos. Veo que tienes acceso a {portfolio_str}. ¿En cuál portafolio te gustaría crear demanda?",
    "options": {json.dumps(user_portfolios)},
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
    "question": "{first_question}",
    "options": {json.dumps(user_portfolios)},
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
# "question": "🎉 Hello, {chat.name} let's begin. I see you have access to {portfolio_str}. Which portfolio would you like to create demand in?",

Please respond with your answer, and I'll proceed with the next question!"""
#         else:
#             return '''<|end_header_id|>

# Here's the first question:
# ```
# {
#     "question": "Tell me about your roadmap or the proposed project! What's the broad scope and objective of this initiative?",
#     "options": [],
#     "hint": ["For example, you can share the high-level goals, key performance indicators (KPIs), or the overall vision behind this project. This will help me understand the context and purpose of your roadmap."],
#     "question_progress": "0%",
#     "counter": 0,
#     "last_question_progress": "0%",
#     "topics_answered_by_user": [],
#     "should_stop": false,
#     "should_stop_reason": "",
#     "are_all_topics_answered_by_user": false
# }
# ```

# Please respond with your answer, and I'll proceed with the next question!'''

    