import os
import re
import json
import time
import random
import datetime
import traceback
import concurrent.futures
from .base import ChatService
from src.trmeric_utils.json_parser import *
from src.trmeric_services.chat_service.utils import *
from src.trmeric_services.chat_service.Prompts import *
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.journal.Activity import detailed_activity, activity, record
from src.trmeric_services.idea_pad.IdeaPadService import IdeaPadService



class IdeationChat(ChatService):
    def __init__(self, request_info, session_id, chat_type):
        self.idea_service = IdeaPadService()

        
    def sample_beginnings(self,name):
        beginnings = [
            f"Hey {name}, what’s that bold idea you’ve been thinking about? Let’s dive in! 🚀",
            f"Alright {name}, hit me with it—what’s the fresh thinking you’ve got? 🌱",
            f"Hello {name}, I’m ready to brainstorm with you! What’s inspiring you today? 💡",
            f"Alright {name}, what’s the idea that’s been quietly demanding attention? Let’s give it a voice. 💡",
            f"Hello {name}, I can sense a wild concept brewing in the shadows — let’s bring it into the light. 🌟",
            # f"No names, no limits — just ideas. What’s the spark you’ve been holding onto?",
        ]
        return random.choice(beginnings)

    def start_session(self, chat, **kwargs):
        content = getIdeationQnaChat(
            persona = json.dumps(chat.context.get("customer_info", {}) or {}),
            internal_knowledge = chat.context.get("roadmap_project_knowledge","") or None
        )
        return {
            "role": "system",
            "content": content,
            "username": "Tango",
            "time": datetime.datetime.now().isoformat(),
        }

    def generate_next_question(self, chat, **kwargs):
        first_question = self.sample_beginnings(chat.name)
        print("--debug idea first_que: ", first_question,"\n")

        if chat.chat_type == 6 and len(chat.getConvMessagesArr()) == 2:
            return f"""
        ```
        {{
            "question": "{first_question}",
            "options": [],
            "mindmap": "",
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


    def fetchPrefilledRoadmapOrProjectData(self, chat, socketio,client_id,step_sender=None, **kwargs):

        try:
            model_opts = chat.modelOptions
            uploaded_files = chat.getConvUploadedFiles()
            conversation = chat.fetchOnlyQna()
            print("--debug uploaded_files-----", uploaded_files)
            
            detailed_activity( 
                activity_name="idea_context_gathering",
                activity_description=f"Beginning data collection for idea creation, assessing idea relevance based on user requirements. Tenant ID: {chat.tenant_id}",
                user_id=chat.user_id
            )
        
            ideation_canvas = {}
            step_sender.sendSteps("Creating Ideascape", False)
            org_strategy = chat.context.get("org_alignment") or []

            # all_portfolios = RoadmapDao.fetchAllPortfolioOfTenant(tenant_id=chat.tenant_id)
            # all_portfolios = PortfolioDao.fetchApplicablePortfolios(user_id=chat.user_id, tenant_id=chat.tenant_id)
            all_portfolios = chat.context.get("all_portfolios") or []
            # internal_knowledge = BaseAgent(log_info={"tenant_id":chat.tenant_id,"user_id":chat.user_id}).project_and_roadmap_context_string
            internal_knowledge = chat.context.get("roadmap_project_knowledge") or ""
            # print("\n\internal_knowledge----------- knowledge ", internal_knowledge)
            step_sender.sendSteps("Assessing Portfolio Alignment", False)
            portfolio_selection_prompt = roadmapInternalKnowledgePrompt(
                conversation=conversation,
                persona=None,
                org_info=None,
                portfolios=all_portfolios
            )
            selection_response = chat.llm.run(portfolio_selection_prompt,model_opts,'agent::portfolio_selection',logInDb=chat.log_info)
            selection_output = extract_json_after_llm(selection_response,step_sender=step_sender)
            # print("\n\n--debug selection_output---", selection_output)
            
            selected_portfolio_ids = [p['id'] for p in selection_output.get('selected_portfolios', [])]    
            step_sender.sendSteps("Assessing Portfolio Alignment", True)  

            # portfolio_context = get_tenant_portfoliocontext(chat.tenant_id,selected_portfolio_ids)
            portfolio_context = PortfolioDao.fetchPortfolioContext(
                portfolio_ids=selected_portfolio_ids,
                tenant_id=chat.tenant_id,
                projection_attrs=["id", "title", "industry","kpis", "strategic_priorities"],
                take_child= False #no subportfolio info req
            )
            print("\n\n------debug portfolio_context-----", portfolio_context)
            
            files_content = process_uploaded_files(chat.file_analyzer, uploaded_files, step_sender=step_sender, source='creation')
            
            step_sender.sendSteps("Aligning the OKR(s)",False)
            
            #Ideation Canvas
            prompt = ideationCanvasPrompt(
                conversation=conversation,
                org_info=chat.context.get("customer_info", {}) or {},
                portfolio_context = portfolio_context,
                org_strategy=org_strategy,
                # portfolios=json.dumps(all_portfolios[:150]),
                internal_knowledge = internal_knowledge,
                files = json.dumps(files_content,indent=2)
            )
            # print("\n\ndebug ---prompt for ideacanvas- ", prompt.formatAsString())
            # response = chat.llm.run(prompt, model_opts, 'agent::ideation_creation', logInDb = chat.log_info)
            response = chat.llm.run_rl(prompt, model_opts,'ideation_agent','canvas::ideation', logInDb = chat.log_info,socketio=socketio,client_id=client_id)

            output = extract_json_after_llm(response,step_sender=step_sender)
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

            ideation_canvas["details"] = output
            ideation_canvas["tango_analysis"] = thought_process

            step_sender.sendSteps("Aligning the OKR(s)",True)

            start = time.time() 
            step_sender.sendSteps("Capturing key insights", False)

            language = chat.context.get("user_language") or "English"
            solution_insights = self.idea_service.createIdeationInsights(output,chat.tenant_id,chat.user_id,language=language,step_sender=step_sender)
            ideation_canvas["session_id"] = chat.session_id
            ideation_canvas["creation_source"] = "conversation"
            ideation_canvas["insights"] = solution_insights.get("insights",{}) or None
            
            elapsed_time = time.time()-start
            print("--debug time taken for solution_insights--", elapsed_time)
            step_sender.sendSteps("Capturing key isights", True)

            save_as_json(data = ideation_canvas,filename=f"ideacanvas_{chat.user_id}.json")       
            # Track successful completion of idea preparation
            detailed_activity(
                activity_name="idea_preparation_complete",
                activity_description=f"Idea preparation phase completed successfully. All necessary data has been collected, analyzed, and stored for Idea '{output.get('roadmap_name', 'N/A')}'. System is ready to proceed to detailed roadmap creation stages (objectives, scope, timeline, roles, and budget estimation).",
                user_id=chat.user_id
            )
            step_sender.sendSteps("Creating Ideascape", True)  

            appLogger.info({"event": "idea:prefill:prompt:end", "data": len(output),"tenant_id": chat.tenant_id, "user_id": chat.user_id})
            return ideation_canvas
                
        except Exception as e:
            
            detailed_activity(
                activity_name="idea_creation_error",
                activity_description=f"Error occurred during idea preparation phase: {str(e)[:200]}. Process halted and user will need to retry idea creation.",
                status="error",
                user_id=chat.user_id,
            )
            step_sender.sendError(key=str(e),function = "fetchPrefilledideaOrProjectData")
            appLogger.error({"event":"idea:prefill:prompt","error":e,"traceback":traceback.format_exc()})

