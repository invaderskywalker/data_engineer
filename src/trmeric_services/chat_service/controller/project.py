import json
import random
import datetime
from .base import ChatService
from src.trmeric_utils.json_parser import *
from src.trmeric_services.chat_service.utils import *
from src.trmeric_services.chat_service.Prompts import *
from src.trmeric_services.journal.Activity import detailed_activity, activity, record




class ProjectChat(ChatService):
    def __init__(self, request_info, session_id, chat_type):
        pass


    def sample_beginnings(self, name, portfolios, limit: int = 9):
        
        portfolio_count = len(portfolios)
        
        if portfolio_count < limit:
            portfolio_str = ", ".join(portfolios)
            beginnings = [
                f"🎯 Hello {name}, I see you currently manage {portfolio_str}. Which of these would you like to create project in?",
                f"💼 Hi {name}, looks like you’re overseeing {portfolio_str}. Where should we focus project generation today?",
                f"🎉 Hello, {name} let's begin. I see you have access to {portfolio_str} portfolio(s). Which portfolio would you like to create project in?",
            ]
        else:
            sample_list = ", ".join(portfolios[:limit])
            remaining = portfolio_count - limit
            beginnings = [
                f"🎉 Hello {name}, let’s get started. You have access to several portfolios — including {sample_list}, and {remaining} more. Which one would you like to create project in?",
                f"🎉 Hello, {name} let's begin. I see you have access to {sample_list} and {remaining} other portfolio(s). Which portfolio would you like to create project in?",
                f"📈 Hello {name}, impressive lineup — {sample_list}, and {remaining} additional portfolios. Which one are we driving new project for?",
            ]


        return random.choice(beginnings)


    def start_session(self, chat, **kwargs):
        # content = getProjectQnaChat(json.dumps(chat.context.get("persona", {}) or {}))
        print(f"Starting session for ChatType {chat.chat_type} with session_id: {chat.session_id}")
        detailed_activity(
            activity_name="project_creation_initiation",
            activity_description="User has started the project creation process. Initializing project creation chat with user.",
            user_id=chat.user_id,
        )        
        content = getProjectQnaChatV2(
            persona = {
                # "role": chat.context.get("role"),
                "customer_context": chat.context.get("customer_info",{}),
                "portfolio": chat.context.get("user_portfolios",[]),
                "org_strategy": chat.context.get("org_alignment" ,[]),
                # "knowledge": chat.context.get("solutions_knowledge",[])
            },
            # language = chat.context.get("user_language","English") or "English"
        )
        return {
            "role": "system",
            "content": content,
            "username": "Tango",
            "time": datetime.datetime.now().isoformat(),
        }

    def generate_next_question(self, chat, **kwargs):

        context = chat.context
        user_portfolios = context.get("user_portfolios")
        first_question = self.sample_beginnings(chat.name,user_portfolios,limit=9)
        print("--debug proj first_que: ", first_question,"\n")
        if chat.chat_type == 2 and len(chat.getConvMessagesArr()) == 2:
            return f"""
        ```
        {{
            "question": "{first_question}",
            "options": {json.dumps(user_portfolios)},
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
        # return
        try:
            context = chat.context
            model_opts = chat.modelOptions2
            uploaded_files = chat.getConvUploadedFiles()
            print("--debug uploaded_files-----", uploaded_files)

            conversation=chat.fetchOnlyQna(),
            org_info=context.get("customer_info", {}) or {},
            persona=context.get("persona", {}) or {},
            org_alignment = context.get("org_alignment",[]) or []

            print("--debug [Context: ]-----", conversation, "orginfo : ", org_info, "persona: ", persona)
            
            detailed_activity( 
                activity_name="project_context_gathering",
                activity_description=f"Beginning data collection for project creation, assessing project relevance based on user requirements. Tenant ID: {chat.tenant_id}",
                user_id=chat.user_id
            )
        
            step_sender.sendSteps("Creating project Canvas", False)
            # all_portfolios = RoadmapDao.fetchAllPortfolioOfTenant(tenant_id=chat.tenant_id)
            all_portfolios = context.get("all_portfolios",[]) or []
            technologies_ = context.get("technologies",[]) or []

            # technologies = [tech['title'] for tech in technologies_ if tech['title'] is not None]

            
            files_content = process_uploaded_files(chat.file_analyzer, uploaded_files, step_sender=step_sender, source='creation')
            step_sender.sendSteps("Aligning the OKR(s)",False)

            # step_sender.sendSteps("Assessing Portfolio Alignment", False)
            # portfolio_selection_prompt = roadmapInternalKnowledgePrompt(
            #     conversation=conversation,
            #     persona=persona,
            #     org_info=org_info,
            #     portfolios=all_portfolios
            # )
            # selection_response = chat.llm.run(portfolio_selection_prompt,model_opts,'agent::portfolio_selection',logInDb=chat.log_info)
            # selection_output = extract_json_after_llm(selection_response,step_sender=step_sender)
            # # print("--debug selection_output---", selection_output)
            # selected_portfolio_ids = [p['id'] for p in selection_output.get('selected_portfolios', [])]    
            # step_sender.sendSteps("Assessing Portfolio Alignment", True)  
            # step_sender.sendSteps("Gathering Internal Knowledge", False)
            # internal_knowledge = KnowledgeQueries.fetchPortfolioKnowledge(portfolio_ids=selected_portfolio_ids)
            # # print("portfolio knowledge ", internal_knowledge)
            # appLogger.info({"event":"internal_knowledge_portfolio", "status": "done","tenant_id": chat.tenant_id, "user_id": chat.user_id})
            # TangoDao.insertTangoState(tenant_id=chat.tenant_id, user_id=chat.user_id,key="create_portfolio_sessionID", value= chat.session_id,session_id='')
            
            # Portfolio canvas details
            prompt = projectCanvasPrompt(
               conversation = conversation,
               org_info=chat.context.get("customer_info", {}) or {},
               portfolios = all_portfolios,
               org_strategy = org_alignment,
               files = json.dumps(files_content,indent=2)
            )
            print("\n\ndebug ---prompt for project creation ", prompt.formatAsString())
            # return
            # response = chat.llm.run(prompt, model_opts, 'agent::portfolio_creation', logInDb = chat.log_info)
            step_sender.sendSteps("Aligning the OKR(s)",True)

            response = chat.llm.run_rl(prompt, model_opts,'project_creation_agent','canvas::project', logInDb = chat.log_info,socketio=socketio,client_id=client_id)
            output = extract_json_after_llm(response,step_sender=step_sender)
            print("\n\n--debug response------ ", output)

           
            detailed_activity(
                activity_name="project_preparation_complete",
                activity_description=f"project preparation phase completed successfully. All necessary data has been collected, analyzed, and stored for project '{output.get('roadmap_name', 'N/A')}'. System is ready to proceed to detailed roadmap creation stages (objectives, scope, timeline, roles, and budget estimation).",
                user_id=chat.user_id
            )
            step_sender.sendSteps("Creating project Canvas", True)  
            appLogger.info({"event": "project:prefill:prompt:end", "data": len(output),"tenant_id": chat.tenant_id, "user_id": chat.user_id})
            return output
                
        except Exception as e:
            
            detailed_activity(
                activity_name="project_creation_error",
                activity_description=f"Error occurred during project preparation phase: {str(e)[:200]}. Process halted and user will need to retry project creation.",
                status="error",
                user_id=chat.user_id,
            )
            step_sender.sendError(key=str(e),function = "fetchPrefilledprojectOrProjectData")
            appLogger.error({"event":"project:prefill:prompt","error":e,"traceback":traceback.format_exc()})









#             return '''<|end_header_id|>

# Here's the first question:

# ```
# {
#     "question": "Tell me about your project! What's the broad scope and objective of this project? I'm excited to learn more about it!",
#     "options": [],
#     "hint": ["For example, you can share the problem you're trying to solve, the goals you want to achieve, or the key stakeholders involved. This will help me understand your project better."],
#     "question_progress": "0%",
#     "counter": 0,
#     "last_question_progress": "0%",
#     "topics_answered_by_user": [],
#     "should_stop": false,
#     "should_stop_reason": "",
#     "are_all_topics_answered_by_user": false
# }
# ```

# Please respond with your project's broad scope and objective. I'll use this information to guide our conversation and ask the next question!'''

    # def fetchPrefilledRoadmapOrProjectData(self, chat, socketio, client_id, step_sender):
        # messages = [
        #     {
        #         "role": "user",
        #         "content": createProjectDataFromQNA(
        #             chat.fetchOnlyQna(), "Trmeric", chat.context.get("persona", {}) or {}
        #         ),
        #     }
        # ]
        # return messages

    
        