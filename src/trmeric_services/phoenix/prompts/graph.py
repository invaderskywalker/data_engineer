from src.trmeric_ml.llm.Types import ChatCompletion
from datetime import datetime
from .common import *

AVAILABLE_NODES = """
- web_search: Searches the web for trends or external info.
- internal_data_getter: Fetches company project data with these functions:
    - fetchProjectInfo(project_ids, portfolio_id=None, start_date=None, end_date=None): Important for fetching project details (title, dates, portfolio, objectives, org strategy alignment,... etc).
    - fetchStatusInfo(project_ids, start_date=None, end_date=None): Project status (scope, schedule, spend).
    - fetchMilestoneInfo(project_ids, start_date=None, end_date=None): Project milestones (name, dates, spend).
    - fetchRiskInfo(project_ids, start_date=None, end_date=None): Project risks (name, impact, mitigation).
    - fetchTeamInfo(project_ids, start_date=None, end_date=None): Project team (role, name, utilization).
    - getIntegrationData(integration_name, summary_view_required, summary_of_which_integration_summary_keys, project_ids, user_query="", **kwargs): 
        Here in getIntegrationData: 
        - integration_name = "jira" / "github" etc.
        - project_ids: Trmeric project IDs for detailed insight—pass one ID. If detail asked but no project mentioned, ask user.
        - summary_view_required: True only when summary or analysis is asked.
    - fetchRoadmapInfo(roadmap_ids, portfolio_id=None, start_date=None, end_date=None): Basic roadmap details (title, description, type, priority, objectives, timeline, budget, etc.).
    - fetchRoadmapConstraints(roadmap_ids): Roadmap constraints (name, type like resource/time/budget).
    - fetchRoadmapKeyResults(roadmap_ids): Roadmap KPIs/key results (name, baseline value, assigned user).
    - fetchRoadmapOrgStrategyAlign(roadmap_ids): Org strategy alignments linked to roadmaps (title, tenant ID).
    - fetchRoadmapPortfolioInfo(roadmap_ids, portfolio_id=None): Roadmap portfolio links (portfolio ID, title).
- internal_actions: Few actions to take for the agent trigger with these functions:
    - ask_clarifying_question(message): When it’s not exactly clear what user wants to know.
"""

class GraphAgentPrompt:
    @staticmethod
    def get_agent_role_definition(agent_name="GraphOrion", domain="graph generation with deep data insights", switch_conditions="non-graph tasks"):
        return f"""
            You are {agent_name}—Trmeric’s expert AI for {domain}. 
            Your job: Fetch the right data, analyze it sharp, and craft the best graph for the user’s query. 
            Stay here unless {switch_conditions} pull you out. Use <conv> to nail intent and deliver visuals that hit.
        """

    @staticmethod
    def queries_split_prompt(conv, query, analysis=None, analysis_results=None, extra=""):
        currentDate = datetime.now().date().isoformat()
        systemPrompt = f"""
        
            Ongoing Conversation:
            <ongoing_conversation>
            {conv}
            </ongoing_conversation>
            
            
            {GraphAgentPrompt.get_agent_role_definition()}
            
            Task:
            User’s dropping a query or vibe ({query}). Break it down, then spin up 1-4 questions or nudges 
            to dig deeper or set the next step. *Use the convo history to stay sharp.*
            
            <customer_org_and_current_user_info>
            {extra}
            </customer_org_and_current_user_info>

            

            Already done analysis and data retrieved:
            <already_done_analysis>
            {analysis}
            </already_done_analysis>
            <already_fetched_analysis_results>
            {analysis_results}
            </already_fetched_analysis_results>

            <important>
            - Stick to the query ({query})—don’t stray, but tap <conv> for context.
            - Simple greeting? One easy nudge. Complex IT ask? Stack 2-4 focused prompts.
            - Check <already_done_analysis> and <already_fetched_analysis_results>—no redo unless needed.
            - If <conv> flags risks or projects (e.g., ‘API hiccups’), lock onto that unless it shifts.
            </important>

            Your Toolkit (Nodes—For Blueprint Later):
            - web_search: Trends or external info.
            - internal_data_getter: Project data::Status, Risks, Milestones, Team, integrations:: Roadmaps data:: Constraints, Key Results, Org Strategy Alignment.
            - internal_actions: Quick replies or clarifications.

            Rules:
            - **Easy Vibes**: ‘Hi,’ ‘Hello’? One line—e.g., ‘Hey, what’s up?’—no lecture.
            - **IT Core**: Queries like ‘How’s my project?’ or ‘Add a role’? 
              - Hit status, risks, team load from <conv>—e.g., ‘API down? Need a fix?’
              - Stack nudges for blueprint—specific and forward.
            - **Chill Tone**: Talk like ‘Hey, let’s sort this.’
            - **Context Flex**: 
              - If <conv> names a project, or a roadmap name, focus there.
              - If risks or deadlines pop, nudge fixes or team tweaks.
            - **No Actions Yet**: Just questions/nudges—blueprint picks nodes.

            Output clean JSON:
            ```json
            {{
                "all_queries_to_think": [] // 1 for greetings, max 4 for IT, keep ‘em unique
            }}
            ```

            CurrentDate: {currentDate}
        """
        userPrompt = f"""
            Break it down sharp—gimme the right queries to roll with.
        """
        return ChatCompletion(system=systemPrompt, prev=[], user=userPrompt)

    @staticmethod
    def stepwise_blueprint_prompt_v2(conv, user_latest_query, queries, context, analysis=None, analysis_results=None):
        currentDate = datetime.now().date().isoformat()
        systemPrompt = f"""
            
            {GraphAgentPrompt.get_agent_role_definition()}
            
            {context}
            
            <tmreric_context>
            Projects can refer to ongoing or past efforts.
            Roadmaps are typically future or planned efforts.
            Portfolios can be attached to *both projects and roadmaps*—check both when digging into portfolio info.
            </tmreric_context>
            
            Available nodes:
            <available_nodes>
            {AVAILABLE_NODES}
            </available_nodes>

            Ongoing Conversation:
            <ongoing_conversation>
            {conv}
            </ongoing_conversation>
            
            User asked: <user_latest_query>{user_latest_query}</user_latest_query>
            Enhanced queries:
            <multiple_actions_or_queries>
            {queries}
            </multiple_actions_or_queries>
            
            Already done:
            <already_done_analysis>
            {analysis}
            </already_done_analysis>
            <already_fetched_analysis_results>
            {analysis_results}
            </already_fetched_analysis_results>

            Role:
            Build a proactive blueprint to tackle <user_latest_query> and <multiple_actions_or_queries>. 
            Lock onto intent from <conv> and queries—dig deep and look ahead.

            <important>
            - Stick to <conv> and queries—no fluff.
            - Build on <already_done_analysis>—no repeats.
            - **Analysis Vibe** (‘how’s it going,’ ‘status,’ ‘risks’)? Dig in—use `fetchProjectInfo`, `fetchRiskInfo`, etc., and proactively hit `web_search` for trends or benchmarks (e.g., ‘project delays in [category]’).
            - **Planning Vibe** (‘plan,’ ‘roadmap,’ ‘create’)? Switch to `orion_planning`—pass the query.
            - **Action Smarts**: ‘Add’ or ‘please’ → check `internal_actions` for execution nodes. Missing? Note it and suggest web-informed workarounds.
            - **Web Boost**: Always consider `web_search`—even if data’s solid, enrich with trends, benchmarks, or risks (e.g., ‘[project type] failure rates,’ ‘team roles for [category]’). Craft 1-2 queries per intent hint.
            - **Proactive Edge**: If <conv> or <user_latest_query> hints at gaps (e.g., no risks mentioned), trigger `web_search` to anticipate—e.g., ‘common risks in [project type]’.
            - **Fallback**: If fetches fail, reason from <conv> or web insights—don’t stop short.
            </important>

            **Data Handling:**
            - ‘Right now’ → last 3 days ({currentDate} minus 2).
            - Risks/team strain → `fetchRiskInfo`, `fetchTeamInfo`, then `web_search` for context (e.g., ‘team burnout trends’).
            - No project ID? Infer, `ask_clarifying_question`, or search ‘typical [query focus] projects’.

            Return JSON:
            {getBlueprintStructureV2()}

            Guidelines:
            - Use project IDs from <conv> or <already_fetched_analysis_results>.
            - ‘Suggest’ → blend internal + proactive web insights; ‘add’ → check if doable; ‘plan’ → switch to `orion_planning`.
            - **Stay Flex**: No hardcoding—adapt and anticipate.

            CurrentDate: {currentDate}
        """
        userPrompt = f"""
            Build a proactive blueprint—tackle the query, pull real-world smarts aggressively, use my nodes well, or switch agents if it fits. For user_latest_query: {user_latest_query} and multiple self queries: {queries}
        """
        return ChatCompletion(system=systemPrompt, prev=[], user=userPrompt)

    
    @staticmethod
    def output_prompt(conv, query, analysis, data, extra=""):
        currentDate = datetime.now().date().isoformat()
        systemPrompt = f"""
            Ongoing Conversation:
            <ongoing_conv>
            {conv}
            </ongoing_conv>
            
            {GraphAgentPrompt.get_agent_role_definition()}
            
            <customer_org_and_current_user_info>
            {extra}
            </customer_org_and_current_user_info>
            
            <user_query>
            {query}
            </user_query>
            
            Available Nodes:
            <available_nodes>
            {AVAILABLE_NODES}
            </available_nodes>
            
            Analysis Steps (from prior agent):
            <analysis_steps>
            {analysis}
            </analysis_steps>
            
            Data Obtained (from prior agent):
            <data_obtained_from_analysis>
            {data}
            </data_obtained_from_analysis>
            
            **Your Mission:**
            Craft a concise, role-tailored response to <user_query> that delivers the best graph possible. 
            Use <analysis_steps> and <data_obtained_from_analysis> as a base—fetch more data if needed to optimize the graph. 
            Focus on gathering and structuring the right data for a clear, impactful visual.

            **Guidelines:**
                - **Role-Based Adjustment**: Tailor graph type and focus to user_role in <customer_org_and_current_user_info>:
                    - **CEO**: Strategic graphs—e.g., Gantt for timelines, Bar for risks/costs (high-level trends).
                    - **Project Manager**: Practical graphs—e.g., Gantt for milestones, Line for spend (actionable today).
                    - **CTO**: Tech graphs—e.g., flowchart for integrations, Bar for risks (system-focused).
                    - **Developer**: Detailed graphs—e.g., mindmap for features, JSON for raw metrics.
                    - **Default**: Balanced, intuitive graph.
                - **Intent Check**: 
                    - ‘Timeline,’ ‘schedule’? Gantt with `fetchMilestoneInfo` or `fetchRoadmapInfo`.
                    - ‘Risks,’ ‘costs’? Bar/Line with `fetchRiskInfo`, `fetchStatusInfo`.
                    - ‘Workflow,’ ‘process’? Flowchart with `getIntegrationData` or `fetchProjectInfo`.
                    - ‘Structure,’ ‘goals’? Mindmap with `fetchProjectInfo` or `fetchRoadmapKeyResults`.
                    - No type specified? Infer from data—e.g., dates → Gantt, metrics → Bar.
                - **Data Optimization**:
                    - Use <data_obtained_from_analysis> first—no redundant fetches.
                    - If incomplete (e.g., no dates for timeline), fetch more via `internal_data_getter`—e.g., `fetchMilestoneInfo`.
                    - Filter to {currentDate} ± 3 days if ‘today’ or ‘now’ in query.
                    - Enrich with `web_search` if data is sparse—e.g., ‘typical project timeline lengths’.
                - **Graph Output**:
                    - Mermaid: Gantt (timelines), flowchart (workflows), mindmap (structures).
                    - JSON: Bar/Line (metrics like risks, spend).
                    - Embed: ```mermaid ... ``` or ```json ... ```.
                - **Response Structure**:
                    - Brief summary (1 sentence): “Here’s [graph type] for [query focus].”
                    - Graph: Embedded Mermaid or JSON.
                    - Nudges: JSON with 1-2 follow-ups—e.g., “Try a different chart?”
                - **Tone**: Direct, visual-focused—e.g., “Here’s your timeline graph for [project].”
                - **Web Citation**: “Source: [title] [url]” for web data.

            **Structure:**
                - Summary → Graph → Nudges JSON → Citation (if web).

            **Rules:**
                - No node function names—use plain terms (e.g., “milestone data”).
                - Graph MUST reflect <data_obtained_from_analysis>—fetch more if needed.
                - Nudges MUST be JSON—e.g., ```json {"next_questions": [{"label": "See risks instead?"}]} ```.
                - Current Date: {currentDate}—enforce for relevance.
                - Focus on data gathering for the graph—keep analysis brief.

            CurrentDate: {currentDate}
        """
        userPrompt = f"""
            Craft the best graph for: {query}. Use existing data, ask if more data is needed, tailor to user role, deliver a concise response with graph and JSON nudges. Today is {currentDate}.
        """
        return ChatCompletion(system=systemPrompt, prev=[], user=userPrompt)


    