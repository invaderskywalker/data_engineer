
from src.trmeric_ml.llm.Types import ChatCompletion
from datetime import datetime




# AVAILABLE_NODES = """
# - web_search: Searches the web for trends or external info.

# - internal_data_getter: Fetches company project data with these functions:
#     - fetchProjectInfo(project_ids, portfolio_id=None, start_date=None, end_date=None): Important for fetching project details (title, dates, portfolio, objectives, org sterategy alignment,... etc).
#     - fetchStatusInfo(project_ids, start_date=None, end_date=None): Project status (scope, schedule, spend).
#     - fetchMilestoneInfo(project_ids, start_date=None, end_date=None): Project milestones (name, dates, spend).
#     - fetchRiskInfo(project_ids, start_date=None, end_date=None): Project risks (name, impact, mitigation).
#     - fetchTeamInfo(project_ids, start_date=None, end_date=None): Project team (role, name, utilization).
#     - getIntegrationData(integration_name, summary_view_required, summary_of_which_integration_summary_keys, project_ids, user_query= "", **kwargs ). 
#         Here in getIntegrationData. 
#         for exam-ple integration_name = "jira" / "github" etc
#         project_ids: is trmeric project ids. this is used for fetching detailed insight of the integration. pass only one project id to it. If detail is asked by user but no project is mentioned ask him.
#         summary_view_required: make this true only when summary or analysis is asked
#     - fetchRoadmapInfo(roadmap_ids, portfolio_id=None, start_date=None, end_date=None): Basic roadmap details (title, description, type, priority, objectives, timeline, budget, etc.).
#     - fetchRoadmapConstraints(roadmap_ids): Roadmap constraints (name, type like resource/time/budget).
#     - fetchRoadmapKeyResults(roadmap_ids): Roadmap KPIs/key results (name, baseline value, assigned user).
#     - fetchRoadmapOrgStrategyAlign(roadmap_ids): Org strategy alignments linked to roadmaps (title, tenant ID).
#     - fetchRoadmapPortfolioInfo(roadmap_ids, portfolio_id=None): Roadmap portfolio links (portfolio ID, title).
        
# - internal_actions: Few actions to take for the agent trigger with these functions
#     - ask_clarifying_question(message) - When it is not exactly clear as to what user wants to know
#     - general_reply(message) - when user is just asking normal things
    
# - activate_other_agent: Only to be triggered when the user wants you to trigger other agent. Only one agent can be triggered at one time. The other agents are listed:
#     - orion_planning - when user is interested inititating the roadmap creation flow
# """

# - knowledge: Fetches insights from Trmeric knowledge Base
#     - Params: 
#         - project_ids (list): e.g., [2417, 2419]
#         - outcome (list, optional): e.g., ['failure', 'bad', 'good', 'success']

# - suggested_agentic_actions: Proactive IT triggers to level up—queue ‘em, then fire on ‘Yes’:
#     - initiate_roadmap_agent(params): Kick off a roadmap planning agent—map the future, fam.
#     - create_jira_issue(params): Drop a Jira ticket—title, desc, project ID, let’s track it.
#     - add_team_member(params): Toss a new player into a project—role, name, get ‘em in.
#     - source_provider(params): Start discovery sourcing—hunt a provider to crush it.
 
def getBlueprintStructureV2():
    return f"""
    {{
        "thought_process": "",
        "nodes": {{
            "web_search": {{
                "web_queries": []
            }},
            "internal_data_getter": [
                {{
                    "function": specific internal_data function (e.g., "fetchStatusInfo") if applicable, otherwise empty string bro.
                    "params": dict of parameters for the function (e.g., {{"project_ids": [], "start_date": "2025-01-01"}})
                }},...
            ],
            "internal_actions": [
                {{
                    "function": specific internal_actions functions
                    "params": dict of parameters for the function
                }},...
            ],
            "activate_other_agent": [
                {{
                    "agent_name": "<specific agent name from available activate_other_agent node which requested by user>"
                }}
            ]
           
        }}
    }}
    """
    
#  "knowledge": [
#                 {{
#                     "params": dict of parameters (e.g., {{"project_ids": [], "outcome": []}})
#                 }},...
#             ]



# def output_prompt_mini(query, analysis, response):
#     currentDate = datetime.now().date().isoformat()
#     systemPrompt = f"""
#         You’re Orion, Trmeric’s AI sidekick—sharp, snappy, and all about that autonomous IT hustle.
#         You’re running the right-side chat in a dual-panel UI—left canvas drops the main juice, 
#         and you’re here to sum it up tight and push *smart* moves based on the data.

#         Data:
#         <user_query>
#         {query}
#         <user_query>
        
#         <analysis_steps>
#         {analysis}
#         <analysis_steps>
        
#         <canvas_response>
#         {response}
#         <canvas_response>

#         Job:
#         1. Sum up the vibe or analysis in *one punchy line*—zero in on the biggest risks or wins.
#         2. Nudge ‘em forward in *one slick line*—push a fix tied to the data.
#         3. Suggest 1-3 CTA buttons in JSON—*reason from the analysis/response* to pick high-impact fixes.

#         Available Triggers:
#         - initiate_roadmap_agent: Spin up a roadmap agent.
#         - create_jira_issue: Drop a Jira ticket (title, desc, project).
#         - add_team_member: Add a player (role, project)—use if risks suggest team overload.
#         - initiate_troubleshoot_agent: Kick off a troubleshooting agent (project, issue)—use for tech-heavy fixes.
#         - source_provider: Hunt a provider.

#         Rules:
#         - **Output Structure**: *Exactly* 2 lines (summary + nudge) + JSON buttons below. No drift.
#         - **Vibe Check**: Short query (under 5 words) or casual (e.g., ‘Hello’) with no analysis/response depth? One-line sum, one-line nudge, ```json{{'cta_buttons': []}}```.
#         - **Deep Query**: Solid analysis or detailed response? Pinpoint top risks (e.g., ‘API failures’), nudge a fix, 2-3 buttons max.
#         - **Risk Reasoning**: Think through the data:
#           - High-priority risks (e.g., ‘API failures’)? Suggest `create_jira_issue` or `initiate_troubleshoot_agent`.
#           - Team strain implied (e.g., tight deadlines, big risks)? Suggest `add_team_member`.
#           - Delays/bottlenecks (e.g., ‘sprint spillover’)? Tie to team or roadmap fixes.
#           - No flags? ```json{{'cta_buttons': []}}```.
#         - **Tone Lock**: Swagger only—‘Yo, fam, let’s roll.’ No soft vibes.
#         - Buttons in JSON: 
#           ```json
#           {{
#               "cta_buttons": [
#                   {{"label": "DO X", "action": "trigger_name", "params": {{"key": "value"}}}}, ...
#               ]
#           }}
#           ```

        

#         CurrentDate: {currentDate}
#     """
#     userPrompt = f"""
#         Think sharp—2 lines (summary, nudge) + JSON buttons *only if data demands it*.
#     """
#     return ChatCompletion(system=systemPrompt, prev=[], user=userPrompt)

