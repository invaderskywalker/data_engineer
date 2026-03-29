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
from src.trmeric_services.project.projectService import ProjectService
from src.trmeric_services.roadmap.RoadmapService import RoadmapService
from src.trmeric_services.journal.Activity import detailed_activity, activity, record


class MissionChat(ChatService):
    def __init__(self, request_info, session_id, chat_type):
        self.roadmap_service = RoadmapService()
        self.project_service = ProjectService()
        # self.file_analyzer = FileAnalyzer(tenant_id = request_info.get("tenant_id"))

    def start_session(self, chat, **kwargs):
        entity = kwargs.get('entity',None) or None
        print(f"Starting session for ChatType {chat.chat_type} for Mission-> {entity} with session_id: {chat.session_id}")
        detailed_activity(
            activity_name="mission_ignition",
            activity_description="User has initiated a new mission. Tango is powering up the agentic convo to co-create an epic workflow.",
            user_id=chat.user_id,
        )
        print(f"--debug in start_session mission-------for entity {entity} &  role", chat.context.get("role"))
        
        # Generate the system prompt content with mission-themed persona
        content = getMissionChat(
            persona={
                "role": chat.context.get("role"),
                "customer_context": chat.context.get("customer_info", {}),
                "portfolio": chat.context.get("user_portfolios", []),
                "org_strategy": chat.context.get("org_alignment", []),
                "knowledge": chat.context.get("solutions_knowledge", [])  # Past mission learnings for dynamic refs
            },
            entity = entity,
            language=chat.context.get("user_language", "English") or "English"
        )
        
        return {
            "role": "system",
            "content": content,
            "username": "Tango",
            "time": datetime.datetime.now().isoformat(),
        }

    def fetchPrefilledRoadmapOrProjectData(self, chat, socketio, client_id, step_sender=None, **kwargs):
        print("--debug in fetchPrefilledRoadmapOrProjectData ------- mission44", kwargs)
        entity = kwargs.get("entity",None) or None
        print("--debug in mission fetchPrefilledRoadmapOrProjectData---------", entity)
        try:
            if not entity:
                print("--debug no entity-------", entity)
                return {}
            
            print(f"--debug [INITIATING] {entity} creation for Mission")
            mission_canvas = self.create_canvas_lifecycle(
                chat = chat,
                entity = entity,
                socketio = socketio,
                client_id = client_id,
                sender = step_sender
            )
            print(f"--debug [FINISHED] {entity} creation for Mission")

            with open(f"mission_{entity}_canvas_{chat.user_id}.json", "w") as f:
                json.dump(mission_canvas, f, indent=4)
            if not mission_canvas:
                return {}
            return mission_canvas

        except Exception as e:
            appLogger.error({"event":"mission:fetchPrefilledRoadmapOrProjectData","error":str(e),"traceback":traceback.format_exc()})
            step_sender.sendError(key=str(e),function = "fetchPrefilledRoadmapOrProjectData")
            return {}

    def create_canvas_lifecycle(self,chat,entity,socketio,client_id,sender,**kwargs):
            
        step_start_times = {}
        try:
            step_sender = sender
            context = chat.context
            model_opts = chat.modelOptions2
            conversation  = chat.fetchOnlyQna()
            uploaded_files = chat.getConvUploadedFiles()
            release_quarter = TenantDao.fetchReleaseCycleTag(tenant_id=chat.tenant_id)
            quarter_tags = [q['title'].strip() for q in release_quarter] if len(release_quarter)>0 else ['Q1','Q2','Q3','Q4']
            files_content = process_uploaded_files(chat.file_analyzer, uploaded_files, step_sender=step_sender, source='creation')

            step_sender.sendSteps("Gathering Internal Knowledge", False)

            internal_knowledge = context.get("solutions_knowledge") or []
            org_strategy = context.get("org_alignment") or []
            all_portfolios = context.get("all_portfolios") or []
            appLogger.info({"event":"internal_knowledge_rodmap", "status": "done","tenant_id": chat.tenant_id, "user_id": chat.user_id})
            step_sender.sendSteps("Gathering Internal Knowledge", True)

            mission_canvas = {}
            if entity == 'roadmap':

                step_key = "Creating Demand Canvas"
                step_sender.sendSteps(step_key, False)
                step_start_times[step_key] = time.time()

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
                
                roadmap_canvas["basic"] = basic_info
                roadmap_canvas["okr"] = okr
                roadmap_canvas["cpc"] = cpc


                step_sender.sendSteps("Matching Existing Solutions", False)
                start = time.time() 
                
                solution_insights = self.roadmap_service.createDemandInsights(roadmap_canvas,chat.tenant_id,chat.user_id,step_sender=step_sender)
                roadmap_canvas["insights"] = solution_insights
                roadmap_canvas["creation_source"] = "conversation"
                roadmap_canvas["session_id"] = chat.session_id
                
                elapsed_time = time.time()-start
                print("--debug time taken for solution_insights--", elapsed_time)
                step_sender.sendSteps("Matching Existing Solutions", True, time=elapsed_time)            
                elapsed_time = time.time() - step_start_times[step_key]  # Calculate time taken
                print(f"--debug time taken for creating {entity}_canvas---", elapsed_time)
                step_sender.sendSteps(step_key, True, time=elapsed_time)  # Pass elapsed time

                mission_canvas = roadmap_canvas

            else: # project
                detailed_activity( 
                    activity_name="project_context_gathering",
                    activity_description=f"Beginning data collection for project creation, assessing project relevance based on user requirements. Tenant ID: {chat.tenant_id}",
                    user_id=chat.user_id
                )
            
                step_sender.sendSteps("Creating project Canvas", False)
                all_portfolios = context.get("all_portfolios",[]) or []
                technologies_ = context.get("technologies",[]) or []
                # technologies = [tech['title'] for tech in technologies_ if tech['title'] is not None]

                step_sender.sendSteps("Aligning the OKR(s)",False)
                prompt = projectCanvasPrompt(
                    conversation = conversation,
                    org_info=chat.context.get("customer_info", {}) or {},
                    portfolios = all_portfolios,
                    org_strategy = org_strategy,
                    files = json.dumps(files_content,indent=2)
                )
                print("\n\ndebug ---prompt for project creation ", prompt.formatAsString())
                # return
                # response = chat.llm.run(prompt, model_opts, 'agent::portfolio_creation', logInDb = chat.log_info)
                step_sender.sendSteps("Aligning the OKR(s)",True)

                response = chat.llm.run_rl(prompt, model_opts,'project_creation_agent','canvas::project', logInDb = chat.log_info,socketio=socketio,client_id=client_id)
                output = extract_json_after_llm(response,step_sender=step_sender)
                print(f"\n\n--debug {entity} response------ ", output)

                insights = self.project_service.createProjectInsights(output,chat.tenant_id,chat.user_id,step_sender=step_sender)
                output["insights"] = insights
                output["creation_source"] = "conversation"
                output["session_id"] = chat.session_id
                
                detailed_activity(
                    activity_name="project_preparation_complete",
                    activity_description=f"project preparation phase completed successfully. All necessary data has been collected, analyzed, and stored for project '{output.get('roadmap_name', 'N/A')}'. System is ready to proceed to detailed roadmap creation stages (objectives, scope, timeline, roles, and budget estimation).",
                    user_id=chat.user_id
                )
                step_sender.sendSteps("Creating project Canvas", True)  
                appLogger.info({"event": "project:prefill:prompt:end", "data": len(output),"tenant_id": chat.tenant_id, "user_id": chat.user_id})
                mission_canvas = output
                

            appLogger.info({"event": "mission:prefill::canvas::end", "data": len(mission_canvas),"tenant_id": chat.tenant_id, "user_id": chat.user_id})
            return mission_canvas
        except Exception as e:
            appLogger.error({"event":"create_canvas_lifecycle","error":str(e),"traceback":traceback.format_exc()})
            step_sender.sendError(key=str(e),function = "fetchPrefilledRoadmapOrProjectData")




    def mission_openings(self, name: str, portfolios: list[str], recent_missions: list[str] = None,entity:str='project', limit:int = 7) -> str:
        """
        Craft dynamic, mission-themed opening salvos.
        These set the tone: excitement, urgency, accomplishment.
        """
        # print("--debug calling mission_openings for: ", entity)
        recent_missions = recent_missions or []
        portfolio_count = len(portfolios)

        # Personal touch: reference recent wins or ongoing ops if available
        recent_hint = ""
        if recent_missions:
            examples = ", ".join(recent_missions[:3])
            if len(recent_missions) > 3:
                examples += f", and {len(recent_missions) - 3} others"
            recent_hint = f" (coming off strong from {examples})"

        # Helper to pick the right framing
        if entity.lower() == 'project':
            action_phrase = "launch and execute"
            focus_phrase = "delivery"
            emoji = "⚡"  # energy, speed
        else:  # roadmap
            action_phrase = "plan and shape"
            focus_phrase = "strategic direction"
            emoji = "📐"  # structure, planning

        # Case 1: Few portfolios — name them for intimacy
        if portfolio_count <= limit:
            portfolio_str = ", ".join(portfolios) if portfolios else "new territory"
            openings = [                
                f"🎯 Welcome back, {name}. We've got active sectors: {portfolio_str}. "
                f"Which one demands our focus — or are we charting a new frontier?",
                
                f"🔥 {name}, the deck is yours. Current theaters of operation: {portfolio_str}. "
                f"Where are we striking next?",
            ]

        # Case 2: Many portfolios — tease scale, build awe
        else:
            sample_list = ", ".join(portfolios[:limit])
            remaining = portfolio_count - limit
            openings = [
                # f"Hello {name}. Let's build a structured plan for your next strategic priority. 📐 What outcome are you aiming for?",
                f"Hello {name}. Your portfolio spans {portfolio_count} domains including {sample_list} and {remaining} others. "
                f"Let's {action_phrase} a new {entity} — where should we start?",
                
                f"Hey, {name}. Welcome. Let's {action_phrase} your first {entity} from the ground up. What outcome are you aiming for today?",
                
                f"Hello {name}. Perfect timing — a clean slate. Ready to define and {action_phrase} a new {entity}? Where should we begin?",
                f"Welcome, {name}. Today is the ideal moment to {action_phrase} a focused {entity}. Tell me: what are we setting in motion?",

                f"Hello {name}. We're starting fresh — an excellent opportunity to shape a high-impact {entity} initiative. 🌱 What's our next big push?",                
                f"Welcome, {name}. Today is the perfect moment to outline a new {entity} initiative. ⏳ Where would you like to begin?",
            ]

        # Fallback for zero portfolios (new user or clean slate)
        if not portfolios:
            openings = [
                f"Hello {name}. Perfect timing — a clean slate. "
                f"Ready to define and {action_phrase} a new {entity}? Where should we begin?",
            
                f"Welcome, {name}. Today is the ideal moment to {action_phrase} a focused {entity}. "
                f"Tell me: what are we setting in motion?",
            ]

        return random.choice(openings)

    def generate_next_question(self, chat, **kwargs) -> str:
        """
        Kick off the agentic mission flow with full context and mission-ready metadata.
        This is where ideation mode begins — Tango is now co-pilot.
        """
        context = chat.context
        entity = kwargs.get("entity",None) or None
        user_name = chat.name or "Commander"
        user_portfolios = context.get("user_portfolios", [])
        recent_missions = context.get("recent_mission_names", [])  or [] # e.g., ["AI Workflow Merge", "Demand 2.0"]

        opening_question = self.mission_openings(
            name=user_name,
            portfolios=user_portfolios,
            recent_missions=recent_missions,
            entity = entity,
            limit=7
        )

        language = context.get("user_language", "English")

        return f"""
        ```
        {{
            "question": "{opening_question}",
            "agent_tip": [],
            "question_progress": "",
            "counter": 0,
            "last_question_progress": "0%",
            "workflow_stage": "",
            "mode": "mission_briefing",
            "topics_answered_by_user": [],
            "should_stop": false,
            "should_stop_reason": "",
            "are_all_topics_answered_by_user": false,
            "suggested_next_actions": ["describe_scope", "select_portfolio", "upload_context", "start_fresh"]
        }}
        ```
        """


    # def create_project_canvas():

    #     context = chat.context
    #     model_opts = chat.modelOptions2
    #     uploaded_files = chat.getConvUploadedFiles()
    #     print("--debug uploaded_files-----", uploaded_files)

    #     conversation=chat.fetchOnlyQna(),
    #     org_info=context.get("customer_info", {}) or {},
    #     persona=context.get("persona", {}) or {},
    #     org_alignment = context.get("org_alignment",[]) or []

    #     print("--debug [Context: ]-----", conversation, "orginfo : ", org_info, "persona: ", persona)
        
        

    