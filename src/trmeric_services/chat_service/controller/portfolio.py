import os
import re
import json
import time
import datetime
import traceback
import concurrent.futures
from .base import ChatService
from src.trmeric_utils.json_parser import *
from src.trmeric_services.chat_service.utils import *
from src.trmeric_services.chat_service.Prompts import *
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.journal.Activity import detailed_activity, activity, record
from src.trmeric_database.dao import db_instance
# from src.trmeric_utils.helper.file_analyser import FileAnalyzer
import random


class PortfolioChat(ChatService):
    def __init__(self, request_info, session_id, chat_type):
        pass

    def sample_beginnings(self, name, portfolios, sub_portfolios:dict={}, limit:int=9):
        """
        Generates a dynamic and professional opening prompt for portfolio creation.
        - If portfolio_count < 10: conversational, includes actual portfolio names.
        - If portfolio_count >= 10: summarized, concise, and executive tone.
        """
        if sub_portfolios:
            print("--debug subportfolios conv-----", sub_portfolios)
            parent = sub_portfolios.get("parent", None) or None
            children = sub_portfolios.get("children", []) or []

            if not parent:
                return f"Hello {name}, I wasn’t able to retrieve your parent portfolio details. Could you confirm which main portfolio this sub-portfolio will belong to?"

            child_count = len(children)

            if child_count == 0:
                beginnings = [
                    f"Hello {name}, we’re about to establish a new sub-portfolio under **{parent}**. Let’s define its purpose and the strategic objectives it will advance.",
                    f"Hi {name}, looks like **{parent}** is ready for its first extension. What will be the core focus and business outcome of this new sub-portfolio?",
                    f"Hello {name}, a fresh opportunity under **{parent}**—great timing. Let’s clarify what this sub-portfolio is meant to achieve.",
                    f"Hey {name}, exciting times ahead—**{parent}** is expanding. What strategic theme or capability will this sub-portfolio bring into focus?",
                ]

            else:
                sample_list = ", ".join(children)
                # remaining = child_count - 4

                beginnings = [
                    f"Hello {name}, the **{parent}** portfolio already spans several areas—like {sample_list}, "
                    f"Let’s define how this new sub-portfolio will strengthen that framework and what strategic outcomes it should deliver.",

                    f"Hi {name}, under **{parent}**, you’re already managing {sample_list}. What distinctive focus or capability will this new sub-portfolio add?",

                    f"Hello {name}, **{parent}** has evolved into a robust ecosystem with initiatives such as {sample_list}. "
                    f"Let’s outline where this new sub-portfolio fits and what goals it should advance.",

                    f"Hey {name}, **{parent}** continues to grow with sub-portfolios like {sample_list}. What strategic intent do you envision for the next addition?",

                    f"Hi {name}, looks like **{parent}** already covers {sample_list}, among others. "
                    f"How should this new sub-portfolio differentiate itself and drive additional value?",
                ]
            return random.choice(beginnings)

        portfolio_count = len(portfolios)
        if portfolio_count < limit:
            portfolio_str = ", ".join(portfolios)
            beginnings = [
                f"Hey {name}, ready to shape your next big portfolio move? I see you’re currently driving {portfolio_str}. 🎯 Which new one are you thinking about?",
                f"Alright {name}, you’ve already got quite a few great initiatives like {portfolio_str}. What fresh idea do you want to bring to life next?",
                f"Hello {name}, looks like your portfolios — {portfolio_str} — are thriving. Which new one should we add to your strategic mix?",
                f"Great to see you, {name}! You’ve built an impressive lineup with {portfolio_str}. What’s the next big play you’re envisioning?",
            ]
        

        else:
            sample_list = ", ".join(portfolios[:limit])
            remaining = portfolio_count - limit
            beginnings = [
                f"Hi {name}, I can see several portfolios making an impact — {sample_list} and {remaining} others. Which fresh one are you planning to create next?",
                # f"Alright {name}, you’ve already got quite a few great initiatives like {sample_list}, and {remaining} more. What fresh idea do you want to bring to life next?",
                # f"Hello {name}, you’re leading a diverse portfolio landscape — including {sample_list}, and {remaining} more. 🌐\n\nWhich new portfolio are you planning to shape next?",
            ]

        return random.choice(beginnings)
        

    def portfolio_context_for_subportfolio_creation(self, id:int, tenant_id:int):
        print("--debug portfolio_context_for_subportfolio_creation Portfolio: ", id)
        portfolio_context = portfolio_context_for_subportfolio_creationconv(portfolio_id=id, tenant_id=tenant_id)
        parent_portfolio = portfolio_context.get("parent_portfolio","")
        sub_portfolios = portfolio_context.get("sub_portfolios",[]) or []

        # print("--debug parent_portfolio---", parent_portfolio.get('title',None),"id: ", parent_portfolio.get("id",None), "\nSub portfolios---", len(sub_portfolios))
        return {
            "parent": parent_portfolio.get("title") or None,
            "children": [c.get('title') for c in sub_portfolios if c.get('title') is not None]
        }



    def start_session(self, chat, **kwargs):
        id = kwargs.get("parent_id",None) or None
        print("--debug start_session  portfolio parent_id---------", id)
        
        subportfolio_context = None
        if id is not None:
            subportfolio_context = self.portfolio_context_for_subportfolio_creation(id = id, tenant_id=chat.tenant_id)
        # content = getPortfolioQnaChat(json.dumps(context.get("persona", {}) or {}))
        content = getPortfolioQnaChat(
            persona = {
                "customer_context": chat.context.get("customer_info",{}),
                "portfolio": chat.context.get("user_portfolios",[]),
                "org_strategy": chat.context.get("org_alignment" ,[]),
                # "knowledge": chat.context.get("solutions_knowledge",[])
            },
            subportfolio_context = subportfolio_context
        )
        return {
            "role": "system",
            "content": content,
            "username": "Tango",
            "time": datetime.datetime.now().isoformat(),
        }

    def generate_next_question(self, chat, **kwargs):
        
        id = kwargs.get("parent_id",None) or None
        print("--debug generate_next_question  portfolio parent_id---------", id)
        
        subportfolio_context = {}
        if id is not None:
            subportfolio_context = self.portfolio_context_for_subportfolio_creation(id = id, tenant_id=chat.tenant_id)
            
        user_portfolios = chat.context.get("user_portfolios")
        first_question = self.sample_beginnings(chat.name,user_portfolios,sub_portfolios=subportfolio_context,limit=7)
        if chat.chat_type == 5 and len(chat.getConvMessagesArr()) == 2:
            return f"""<|end_header_id|>

        Here's the first question:
        ```
        {{
            "question": "{first_question}",
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


    def fetchPrefilledRoadmapOrProjectData(self, chat, socketio,client_id,step_sender=None,**kwargs):
        # return
        try:
            context = chat.context
            model_opts = chat.modelOptions2
            uploaded_files = chat.getConvUploadedFiles()
            print("--debug uploaded_files-----", uploaded_files)

            conversation=chat.fetchOnlyQna(),
            org_info=context.get("customer_info", {}) or {},
            persona=context.get("persona", {}) or {},

            print("--debug [Context: ]-----", conversation, "orginfo : ", org_info, "persona: ", persona)
            
            detailed_activity( 
                activity_name="portfolio_context_gathering",
                activity_description=f"Beginning data collection for portfolio creation, assessing portfolio relevance based on user requirements. Tenant ID: {chat.tenant_id}",
                user_id=chat.user_id
            )
        
            step_sender.sendSteps("Creating Portfolio Canvas", False)
            # all_portfolios = RoadmapDao.fetchAllPortfolioOfTenant(tenant_id=chat.tenant_id)
            all_portfolios = context.get("all_portfolios",[]) or []
            # technologies_ = ProjectsDao.fetchAllProjectTechnologies()
            technologies = context.get("technologies",[]) or []
            # technologies = [tech['title'] for tech in technologies_ if tech['title'] is not None]

            
            files_content = process_uploaded_files(chat.file_analyzer, uploaded_files, step_sender=step_sender, source='creation')


            step_sender.sendSteps("Assessing Portfolio Alignment", False)
            portfolio_selection_prompt = roadmapInternalKnowledgePrompt(
                conversation=conversation,
                persona=persona,
                org_info=org_info,
                portfolios=all_portfolios
            )
            selection_response = chat.llm.run(portfolio_selection_prompt,model_opts,'agent::portfolio_selection',logInDb=chat.log_info)
            selection_output = extract_json_after_llm(selection_response,step_sender=step_sender)
            # print("--debug selection_output---", selection_output)
            
            selected_portfolio_ids = [p['id'] for p in selection_output.get('selected_portfolios', [])]    
            step_sender.sendSteps("Assessing Portfolio Alignment", True)  
        
            
            step_sender.sendSteps("Gathering Internal Knowledge", False)
            portfolio_context = get_tenant_portfoliocontext(chat.tenant_id,selected_portfolio_ids)

            # internal_knowledge = KnowledgeQueries.fetchPortfolioKnowledge(portfolio_ids=selected_portfolio_ids)
            # print("portfolio knowledge ", internal_knowledge)
            
            appLogger.info({"event":"internal_knowledge_portfolio", "status": "done","tenant_id": chat.tenant_id, "user_id": chat.user_id})
            # TangoDao.insertTangoState(tenant_id=chat.tenant_id, user_id=chat.user_id,key="create_portfolio_sessionID", value= chat.session_id,session_id='')
            
            # Portfolio canvas details
            prompt = portfolioCanvasPrompt(
                conversation=conversation,
                org_info= org_info,
                persona= persona,
                portfolio_context=portfolio_context,
                portfolios = None,
                # portfolios=[p for p in all_portfolios if p['id'] in selected_portfolio_ids],
                technologies = json.dumps(technologies),
                files = json.dumps(files_content,indent=2)
            )
            # print("\n\ndebug ---prompt for portfolio name & desc- ", prompt.formatAsString())
            # response = chat.llm.run(prompt, model_opts, 'agent::portfolio_creation', logInDb = chat.log_info)
            response = chat.llm.run_rl(prompt, model_opts,'portfolio_agent','canvas::portfolio', logInDb = chat.log_info,socketio=socketio,client_id=client_id)

            output = extract_json_after_llm(response,step_sender=step_sender)
            # print("\n\n--debug response------ ", output)
            
            it_leader = output.get("it_leader",{}) or {}
            tech_budget = output.get("tech_budget",{}) or {}
            business_leaders = output.get("business_leaders",[]) or []
            output.pop("it_leader",None)
            output.pop("tech_budget",None)
            output.pop("business_leaders",None)

            if tech_budget.get("value")==0 or len(tech_budget.get("start_date",""))<2 or len(tech_budget.get("end_date",""))<2:
                output["tech_budget"] = {"value": 0,"start_date": None,"end_date": None}
            else:    
                output["tech_budget"] = tech_budget


            name = it_leader.get("name", "") or None
            output["it_leader"] = {
                "first_name": name.split(' ')[0] if name else "",
                "last_name": " ".join(name.split(" ")[1:]) if name else "",
                "role": it_leader.get("role", "") or "",
                "email": it_leader.get("email", "") or ""
            }

            business_leaders_ = []
            if business_leaders:
                for leader in business_leaders:
                    name = leader.get("name", "") or None
                    if name:
                        business_leaders_.append({
                        "sponsor_first_name": name.split(' ')[0],
                        "sponsor_last_name": " ".join(name.split(" ")[1:]) or "",
                        "sponsor_role": leader.get("role", "") or None,
                        })
            output["business_leaders"] = business_leaders_
            output["creation_source"] = "conversation"
            output["session_id"] = chat.session_id
            step_sender.sendSteps("Gathering Internal Knowledge", True)  # Pass elapsed time
            # Track portfolio name and description generation
            detailed_activity(
                activity_name="portfolio_basic_info_generation",
                activity_description=f"Successfully generated portfolio name and description using AI analysis. Created portfolio titled '{output.get('portfolio_name', 'N/A')}' with detailed description. Utilized user conversation, organizational context, portfolio alignment, and internal knowledge to create comprehensive portfolio foundation ready for detailed planning stages.",
                user_id=chat.user_id
            )
        
            # Track successful completion of portfolio preparation
            detailed_activity(
                activity_name="portfolio_preparation_complete",
                activity_description=f"portfolio preparation phase completed successfully. All necessary data has been collected, analyzed, and stored for portfolio '{output.get('roadmap_name', 'N/A')}'. System is ready to proceed to detailed roadmap creation stages (objectives, scope, timeline, roles, and budget estimation).",
                user_id=chat.user_id
            )
            step_sender.sendSteps("Creating Portfolio Canvas", True)  
            appLogger.info({"event": "portfolio:prefill:prompt:end", "data": len(output),"tenant_id": chat.tenant_id, "user_id": chat.user_id})
            return output
                
        except Exception as e:
            
            detailed_activity(
                activity_name="portfolio_creation_error",
                activity_description=f"Error occurred during portfolio preparation phase: {str(e)[:200]}. Process halted and user will need to retry portfolio creation.",
                status="error",
                user_id=chat.user_id,
            )
            step_sender.sendError(key=str(e),function = "fetchPrefilledportfolioOrProjectData")
            appLogger.error({"event":"portfolio:prefill:prompt","error":e,"traceback":traceback.format_exc()})



## Trucible helper methods to load Strategy and kpi in portfolio canvas directly
def _add_portfolio_info(content_type, portfolio_id, content, llm, log_info, model_opts):

    if not portfolio_id or not content_type:
        return {'error': 'no portfolio id or content type', 'success': False}
    print("--debug _add_portfolio_info------", content_type, portfolio_id)
    if "strateg" in content_type.lower() or "priorit" in content_type.lower():
        res = _add_portfolio_strategy_info(content_type,portfolio_id,content,llm, log_info, model_opts)
        return res

    try:
        prompt = ChatCompletion(
            system=f"""
            You are extracting PORTFOLIO KPIs.
            From the content below, extract measurable portfolio KPIs.

            Rules:
            - KPIs must be measurable
            - Baseline value must be a realistic numeric or clearly measurable starting point
            - Be concise and concrete
            - Do NOT invent KPIs not implied by the content

            Return STRICT JSON only in this format:

            ```json
            {{
                "key_results": [
                    {{
                        "name": "KPI name",
                        "baseline_value": "baseline value in 50-60 words"
                    }}
                ]
            }}
            ```
            """,
            prev = [],
            user = f"This is the content: {json.dumps(content)}"
        )
        llm_response = llm.run(prompt, model_opts,f"_add_portfolio_info_{content_type}" ,log_info)
        result = extract_json_after_llm(llm_response)
        print("--debug result----------", result)

        if not result or "key_results" not in result:
            return {'success': False, 'error': 'failed to extract KPIs'}
        sql = create_sql_query_projects_portfoliokpi(result["key_results"],portfolio_id)
        res = db_instance.executeSQLQuery2(sql)
        # print("--debug added in portfolio tables-------------------", res)

        return {'success': True,'key_results': result["key_results"]}
    except Exception as e:
        appLogger.error({'event': '_add_portfolio_info','error': str(e), 'tenant_id': log_info,'content_type': content_type})
        return {'success': False,'key_results': []}
    
    
def _add_portfolio_strategy_info(content_type,portfolio_id,content,llm, log_info, model_opts):

    tenant_id = log_info.get('tenant_id',None) or None
    if not portfolio_id or not content_type:
        return {'error': 'no portfolio id or content type', 'success': False}
    print("--debug _add_portfolio_strategy_info---------- ", content_type, portfolio_id)
    try:
        prompt = ChatCompletion(
            system=f"""
            You are extracting PORTFOLIO strategic priorities (organizational alignment).
            Rules:
            - Treat the content as an authoritative strategy title
            - Extract strategy titles from them exactly as provided
            - Do NOT invent or enrich

            Return STRICT JSON only in this format:

            ```json
            {{
                "strategic_priorities": [{{"title": "<strategy name in 3-4 words>"}}]
            }}
            ```
            """,
            prev = [],
            user = f"This is the content: {json.dumps(content)}"
        )
        llm_response = llm.run(prompt, model_opts,f"_add_portfolio_info_{content_type}" ,log_info)
        result = extract_json_after_llm(llm_response)
        print("--debug result----------", result)

        print(f"Interpreting portfolio_strategy as title-only org alignment")
        if not result or "strategic_priorities" not in result:
            return {'success': False, 'error': 'failed to extract priorities'}
        
        sql = create_sql_query_projects_portfolioorgstrategyalign(result["strategic_priorities"],portfolio_id, tenant_id)
        res = db_instance.executeSQLQuery2(sql)
        # print("--debug added in portfolio tables-------------------", res)

        return {'success': True,'strategic_priorities': result["strategic_priorities"]}

    except Exception as e:
        appLogger.error({'event': '_add_portfolio_strategy_info','error': str(e), 'tenant_id': log_info,'content_type': content_type})
        return {'success': False,'strategic_priorities': []}



def sql_quote(value):
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def create_sql_query_projects_portfoliokpi(key_results, portfolio_id):

    if not key_results:
        return "-- No portfolio KPIs to insert"

    query = """
    INSERT INTO public.projects_portfoliokpi (name,baseline_value,portfolio_id)
    VALUES
    """

    values = []
    for kr in key_results:
        name = kr.get("name")
        baseline_value = kr.get("baseline_value")

        if not name or not baseline_value:
            continue  # skip invalid rows safely

        values.append(
            f"""(
                {sql_quote(name)},
                {sql_quote(baseline_value)},
                {portfolio_id}
            )"""
        )

    if not values:
        return "-- No valid portfolio KPIs after validation"

    return query + ",\n".join(values) + ";"


def create_sql_query_projects_portfolioorgstrategyalign(priorities:list, portfolio_id:int,tenant_id:int):

    if not priorities:
        return "-- No portfolio strategies to insert"

    query = """
    INSERT INTO public.projects_portfolioorgstrategyalign (title, portfolio_id,tenant_id)
    VALUES
    """

    values = []
    for p in priorities:
        title = p.get("title")
        if not title:
            continue 

        values.append(
            f"""(
                {sql_quote(title)},
                {portfolio_id},
                {tenant_id}
            )"""
        )

    if not values:
        return "-- No valid portfolio strategies after validation"

    return query + ",\n".join(values) + ";"
