import json
import traceback
from typing import Dict, Any, List
# from .utils import clean_and_merge_fields
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions2
from src.trmeric_utils.enums import AgentFnTypes, AgentReturnTypes
from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_database.dao import TangoDao, AuthDao
from src.trmeric_services.agents.functions.potential_agent.actions import *
from src.trmeric_services.agents.functions.potential_agent.context import *   
from src.trmeric_services.agents.functions.potential_agent.utils import build_context_for_action, get_action_handler
from src.trmeric_services.agents_v2.config.getter import DEFAULT_RESOURCE_DATA_PARAMS

RESTRICTED_ACTIONS = ["assign_to_project", "update_resource_data","assign_to_demand", "add_potential","unassign_demand_or_project"]
ALLOWED_ROLE = "ORG_RESOURCE_MANAGER"



UNASSIGN_PARAMS = [
    {
        "resource_name": None,
        "project_name": None,
        "roadmap_name": None
    }
]


UPDATE_RESOURCE_PARAMS = [
    {
        "name": None,  
        "country": None,
        "role": None,
        "skills": None,
        "experience": None,
        "rate": None,
        "location": None,
        "portfolio": None,
    }
]


ASSIGN_PARAMS = [
    {
        "resource_name": None,
        "project_name": None,
        "roadmap_name": None
    }
]
   
   

def potential_analyst(
    tenantID: int,
    userID: int,
    last_user_message: str = None,
    socketio: Any = None,
    client_id: str = None,
    llm: Any = None,
    sessionID: str = None,
    base_agent=None,
    **kwargs
):
    """Entry point for Potential Analyst to classify and process user actions."""
    sender = kwargs.get("step_sender") or None
    # model_opts = kwargs.get("model_opts2") #gpt-4.1
    model_opts = ModelOptions2(model="gpt-5.1",max_output_tokens=3000,temperature=0.1)
    try:
        eligible_projects = base_agent.eligible_projects or []

        # Store user message
        if last_user_message:
            TangoDao.insertTangoState(
                tenant_id=tenantID,
                user_id=userID,
                key="potential_agent_conv",
                value=f"User Message: {last_user_message}",
                session_id=sessionID
            )

        # sender.sendSteps(key="Analyzing Intent", val=False)
        # Fetch conversation history
        conv_ = TangoDao.fetchTangoStatesForSessionIdAndUserAndKeyAll(session_id=sessionID, user_id=userID, key="potential_agent_conv")
        conversation_ = []
        for c in conv_:
            value = c.get("value", "")
            if value.startswith("User Message:"):
                message = value.replace("User Message: ", "").strip()
                conversation_.append(f"User: {message}")
            elif value.startswith("Agent Message:") or value.startswith("Agent Response:"):
                message = value.replace("Agent Message: ", "").replace("Agent Response: ", "").strip()
                conversation_.append(f"Agent: {message}")
                
        conversation = conversation_[::-1]  # Most recent first
        conversation = "\n".join(conversation)
        # print("\n\n---debug All conv--------", conversation)


        prompt = ChatCompletion(
            system=f"""
                You are an assistant tasked with analyzing a conversation and user context to determine the user's intended action, resource names, and relevant details for resource management.

                **Input Details**:
                - **Conversation**: A list of strings, with the most recent message first.
                - **Valid Actions**:
                    - `assign_to_project`: Assign a resource to a project or change his/her allocation .
                    - `assign_to_demand`: Assign a resource to a demand/roadmap or change his/her allocation in it. (Note Demand = Roadmap!)
                    - `update_resource_data`: Update resource attributes (e.g., role, skills, location).
                    - `analyze_potential`: Analyze resources or projects based on a query or generic questionnare on resources data.
                    - `add_potential`: Add a new resource or add an new org team or add resource to an org team in the system.
                    - `unassign_demand_or_project`: Remove or deallocate resource(s) to project or demand/roadmap.

                - **Clarification Context**:
                    - If multiple resources match a query (e.g., same name), the conversation may include a clarification request (e.g., "Multiple resources matched").
                    - The latest query may specify a resource (e.g., "continue with Emily Gomez") to resolve ambiguity.
                - **Context Management**:
                    - The user context contains all applicable data about resources, projects and demands(roadmaps)
                    - The user query is based solely on this data.

                **Task**:
                **Determine the User’s Intended Action intelligently**:
                    - `update_resource_data`: Triggered when the user mentions updating resource attributes specifies fields like role, skills, location etc., even if details are incomplete.
                    - `assign_to_project`: Triggered when the user wants to assign a resource to a project or change the allocation of a resource.
                    - `assign_to_demand`: Triggered when the user wants to assign a resource to a demand/roadmap or change the allocation of a resource.
                    - `analyze_potential`: Triggered when the user queries resource or project details without indicating an update or assignment (e.g., "list resources", "show skill gaps").
                    - `add_potential`: Triggered when the user queries to add new resource/ org team or add resource to an org team in the system.
                    - `unassign_demand_or_project`: Triggered when the user wants to unassign or remove resource(s) from their allocated project or roadmap.

                    - If the intent is ambiguous but includes update-related keywords, prefer `update_resource_data` and request clarification in `thought_process`.
                    - Similarly if there are add/upload related keywords, prefer `add_potential` and request in `clarifying_info`.

                IMPORTANT: If clarification is needed on what action to take `assign_to_demand or project` from user_query put in `clarifying_info` else leave empty.
                (e.g. user has mentioned assign resource X to Y whether it's project/roadmap?)


                1. **For `update_resource_data`**:
                    - Extract the resources & fields to update (e.g., skills, role, experience) and their values from the query, if provided.
                    - You've to put all the data to be updated for resource(s) in array `update_resource_params` in this format only {UPDATE_RESOURCE_PARAMS}
                    - Valid roles include 'Frontend Engineer', 'Backend Engineer', etc.
                    - If no resource name or fields are specified, set `action` to `update_resource_data` and request clarification in `thought_process`.
                    - Use the clarification context to resolve ambiguous resource references.

                2. **For `assign_to_project`**:
                    - Extract project details (e.g., project_name, resource_name) in the format {ASSIGN_PARAMS}.
                    - If user asks to update allocation, extract all project details to assign the updated project's allocation.

                3. **For `assign_to_demand`**:
                    - Extract demand/roadmap details (e.g., roadmap_name, resource_name ) in the format {ASSIGN_PARAMS}.
                    - If user asks to update allocation, extract all roadmap's details to assign the updated roadmap's allocation.

                4. **For `add_potential`**:
                    - When user wants to add a resource/ add an org team then use this.
                    - Extract the resource and org team details from the user_query (name,email,portfolio,org team name etc.)

                5. **For `analyze_potential`**:
                    - Analyzing the query provide rich querying and flexible projections for capacity planning,skill-based search, provider dependency analysis, and team utilization insights.
                    - You have to give the output for the json key `selected_analyze_potential_attributes` in this format only {DEFAULT_RESOURCE_DATA_PARAMS}
                    - Choose which attributes to include for lighter or heavier payloads for DEFAULT_RESOURCE_DATA_PARAMS.selected_projection_attrs
                    - Use country for location if user queries.
                        ```python
                        ["id","first_name","last_name","role","experience_years","primary_skill","skills","current_allocation","past_projects","country",
                         "current_projects","future_projects","org_team","is_external","provider_company_name","provider_company_website","provider_company_address"
                        ]
                        ```
                6. **For `unassign_demand_or_project`**:
                    - When user wants to remove or unassign resource(s) from their allocated project/ demand(roadmap).
                    - Intelligently assess whether the request query is about removing demand/project, ask in `clarifying_info` if not clear.
                    - You've to extract the details (resource_name, project_name, roadmap_name) as [] in format {UNASSIGN_PARAMS} only.


                Use `thought_process` to explain the analysis or query interpretation.

                
                **Output**:
                - Return a JSON object with the following structure:
                    ```json
                    {{
                        "action": "", // One of: 'assign_to_project', 'update_resource_data', 'analyze_potential', 'assign_to_demand', 'add_potential', 'unassign_demand_or_project'
                        "selected_analyze_potential_attributes": {DEFAULT_RESOURCE_DATA_PARAMS}, // Only if action is 'analyze_potential', else empty json
                        "unassign_params": {UNASSIGN_PARAMS}, // Only if action is 'unassign_demand_or_project' , else empty []
                        "update_resource_params" : {UPDATE_RESOURCE_PARAMS}, //fill the array only if action = 'update_resource_data' else empty []
                        "assign_params": {ASSIGN_PARAMS}, // only if action is 'assign_to_project' or 'assign_to_demand'.
                        "clarifying_info": "", // Clearly ask when unclear about the action to take for assignment of resource.
                        "thought_process": "", // Brief Explanation of how the action and details were determined in 10-30 words.
                    }}
                    ```
                -If the query is incomplete or ambiguous, use thought_process to explain and set action to analyze_potential.
                -Only if the query intent is about `analyze_potential` fill the `selected_analyze_potential_attributes` based on the query requirements else keep it empty always.
                -Only if query is about unassigning or removing resource(s) from project/roadmap for action `unassign_demand_or_project` based on query requirements else keep it empty always.
                -Only if the query's intent is `update_resource_data` extract all the data in above format & fill `update_resource_params` else keep it empty always.
                -Only if the query is about assigning resource to project/demand extract respective details & fill `assign_params` else keep empty always.
                
                **Edge Cases**:
                - Clearly demarcate `assign_to_project` and `assign_to_demand` from user query, if not then you must ask in `clarifying_info` as is this a project/demand?
                - When mentioned allocation/assign in demand/roadmap then only trigger `assign_to_demand` similarly when mentioned assign/allocate to project trigger `assign_to_project`.
                - If the user query is vague (e.g., "update resource data") but includes update-related keywords, select `update_resource_data` and request clarification in `thought_process`.
                - If the query references a non-existent resource or project, note this in `thought_process` and set `action` to `analyze_potential`.
            """,
            prev=[],
            user=f"""
                Properly think and decide, output in proper JSON.
                User Query: {last_user_message}
                Conversation: {conversation}
            """
        )
        # print("--debug prompt1--------", prompt.formatAsString())
        response = llm.exec(prompt,model_opts,"agent::potential::decision",{"tenant_id": tenantID, "user_id": userID})        
        output = extract_json_after_llm(response,step_sender=sender)
        print("--debug outptu----", output)

        action = output.get("action", "analyze_potential")
        thought_process = output.get("thought_process", "")
        clarifying_info = output.get("clarifying_info","")
        unassign_params = output.get("unassign_params",[]) or []
        update_params = output.get("update_resource_params",[]) or []
        assign_params = output.get("assign_params",{}) or {}

        # print("\n--debug update params------", update_params)
        print("\n--debug assign_params------", assign_params)
        if clarifying_info:
            print("--debug clarification req------", clarifying_info)
            yield clarifying_info
            socketio.emit("agent_chat_user", clarifying_info, room=client_id)
            socketio.emit("agent_chat_user", "<end>", room=client_id)
            socketio.emit("agent_chat_user", "<<end>>", room=client_id)
            return

        print("\n---debug output---------", output)
        # print(f"\n\n--debug analysis---- Action: {action}\n\n Thought Process: {thought_process}")   
        # print("-------unassign------\n", unassign_params) 
      
        #####Restriction to take action in the potential agent : only for "org_resource_manager"
        # - If the user's role isn't resource manager deny straightforward here
        user_role = AuthDao.fetchAllRolesOfUserInTenant(user_id = userID)
        print("--debug user_role--------", user_role)
        # user_role = "ORG_RESOURCE_MANAGER"
        if action in RESTRICTED_ACTIONS and ALLOWED_ROLE not in user_role:
            print("--debug [RESTRICTED] !!!!!!!!! FOR THE ROLE:------------- ", user_role)
            response = (
                f"🔒 Access denied: As {user_role[0].replace('_', ' ').title()}, you’re not authorized to perform this action. "
                f"Only {ALLOWED_ROLE.replace('_', ' ').title()}s have permission."
            )

            yield response
            
            socketio.emit("agent_chat_user", response, room=client_id)
            socketio.emit("agent_chat_user", "<end>", room=client_id)
            socketio.emit("agent_chat_user", "<<end>>", room=client_id)
            return
        
        initial_context = build_context_for_action(action=action,tenant_id = tenantID,user_id = userID, eligible_projects=eligible_projects)
        # print("\n\n--debug initial_context-------", initial_context[:100])
        context_string = initial_context.get("context_string","No context available") or "No context"

        orgteam_info = initial_context.get("team_info")
        roadmap_info = initial_context.get("roadmap_info",[]) or []
        projects_info = initial_context.get("projects_info",[]) or []
        portfolio_info = initial_context.get("portfolio_info",[]) or []
        resources_info = initial_context.get("resources_info",[]) or []
        def safe_len(x):
            return len(x) if isinstance(x, (list, dict, tuple, set, str)) else 0

        print(f"""
        --- DEBUG CONTEXT LOADED ---
            Resources   : {safe_len(resources_info):>4} entries
            Projects    : {safe_len(projects_info):>4} entries
            Roadmaps    : {safe_len(roadmap_info):>4} entries
            Org Teams   : {safe_len(orgteam_info):>4} entries
            Portfolios  : {safe_len(portfolio_info):>4} entries
            Context Str : {len(context_string) if context_string else 0:>4} chars
            Total items : {safe_len(resources_info) + safe_len(projects_info) + safe_len(roadmap_info) + safe_len(orgteam_info) + safe_len(portfolio_info):>4}
        """
        )
        
        answer = ''
        for response in take_action(
            tenantID=tenantID,
            userID=userID,
            llm =llm,
            last_user_message=last_user_message,
            plan = output,
            socketio=socketio,
            client_id=client_id,
            sessionID=sessionID,
            context_string=context_string,
            conversation = conversation,
            portfolio_info = portfolio_info,
            team_info = orgteam_info,
            resources_info = resources_info,
            projects_info = projects_info,
            roadmap_info = roadmap_info,
            **kwargs
        ):
            yield response
            answer += response
            
            socketio.emit("agent_chat_user", response, room=client_id)
        socketio.emit("agent_chat_user", "<end>", room=client_id)
        socketio.emit("agent_chat_user", "<<end>>", room=client_id)
        
        # Store agent response
        TangoDao.insertTangoState(
            tenant_id=tenantID,
            user_id=userID,
            key="potential_agent_conv",
            value=f"Agent Message: {answer}",
            session_id=sessionID
        )

    except Exception as e:
        appLogger.error({"event": "Potential analyst failed","error": str(e),"traceback": traceback.format_exc()})
        sender.sendError(key=f"potential_analyst_error: {str(e)}", function="potential_analyst")
        
        

def take_action(
    tenantID: int,
    userID: int,
    llm=None,
    last_user_message=None,
    plan=None,
    socketio=None,
    client_id=None,
    sessionID=None,
    context_string=None,
    **kwargs
):
    print("--debug take_action-----", tenantID, userID, last_user_message, "\nPlan:", plan)
    
    action = plan.get("action", "analyze_potential")
    handler = get_action_handler(action)

    if handler is None:
        error_msg = f"Unknown action: {action}"
        print(f"[ERROR] {error_msg}")
        yield error_msg
        return

    print(f"[Executing action] {action}")

    answer = ""
    try:
        for response in handler(
            tenantID=tenantID,
            userID=userID,
            llm=llm,
            last_user_message=last_user_message,
            plan=plan,
            socketio=socketio,
            client_id=client_id,
            sessionID=sessionID,
            context_string=context_string,
            **kwargs
        ):
            yield response
            answer += response

        # Optional: Save final answer
        TangoDao.insertTangoState(
            tenant_id=tenantID,
            user_id=userID,
            key="potential_agent_conv",
            value=f"Agent Response: {answer}",
            session_id=sessionID
        )

    except Exception as e:
        error_msg = f"Error during action '{action}': {str(e)}"
        print(error_msg)
        yield error_msg







# def take_action(
#     tenantID:int,
#     userID: int,
#     llm =None,
#     last_user_message=None,
#     plan =None,
#     socketio=None,
#     client_id=None,
#     sessionID=None,
#     context_string=None,
#     **kwargs
# ):
#     """
#     Takes action based on the user's plan decided by the llm above.
#     Let us revamp this using the Registry pattern for better maintainabliity and use decorators for actions.
#     This will help in adding new actions without modifying the core function.

#     """

#     print("--debug take_action-----", tenantID, userID, last_user_message, "\nPlan:", plan)
#     action = plan.get("action","analyze_potential")

    
#     answer = ''
#     sender = kwargs.get("step_sender")
#     if action == "update_resource_data":
        
#         resource_data,clarification_msg = update_details(
#             tenant_id=tenantID,
#             user_id=userID,
#             # updates=updates,
#             session_id=sessionID,
#             llm=llm,
#             user_query=last_user_message,
#             socketio=socketio,
#             client_id=client_id,
#             context_string=context_string,
#             plan = plan,
#             **kwargs
#         )

#         if clarification_msg is not None:
#             yield clarification_msg
#             return


#         if not resource_data:
#             error_msg = "Couldn't update details"
#             # socketio.emit("agent_chat_user", json.dumps({"error": error_msg}), room=client_id)
#             yield error_msg
#             return

#         # sender.sendSteps(key="Updating Resource Details", val=False)
        
#         # Call update function
#         for response in update_resource_details_fn(
#             tenant_id=tenantID,
#             user_id=userID,
#             resource_data=resource_data,
#             socketio=socketio,
#             client_id=client_id,
#             session_id=sessionID,
#             llm=llm,
#             **kwargs
#         ):
#             yield response
#             answer += response

#         # sender.sendSteps(key="Updating Resource Details", val=True)

#     elif action == "analyze_potential":
#         for response in potential_review(
#             tenantID=tenantID,
#             userID=userID,
#             llm = llm,
#             plan = plan,
#             user_query=last_user_message,
#             socketio=socketio,
#             client_id=client_id,
#             **kwargs
#         ):
#             yield response
#             answer += response

#     elif action == "assign_to_project":
        
#         for response in allocate_resources(
#             tenant_id=tenantID,
#             user_id=userID,
#             llm = llm,
#             plan = plan,
#             user_query=last_user_message,
#             session_id=sessionID,
#             socketio=socketio,
#             client_id=client_id,
#             context_string=context_string,
#             **kwargs
#         ):
#             yield response
#             answer += response

#     elif action == "assign_to_demand":
        
#         for response in allocate_demands(
#             tenant_id=tenantID,
#             user_id=userID,
#             llm = llm,
#             plan = plan,
#             user_query=last_user_message,
#             session_id=sessionID,
#             socketio=socketio,
#             client_id=client_id,
#             context_string=context_string,
#             **kwargs
#         ):
#             yield response
#             answer += response

#     elif action == "unassign_demand_or_project":
#         for response in unassign_resources(
#             tenant_id=tenantID,
#             user_id=userID,
#             llm = llm,
#             plan = plan,
#             user_query=last_user_message,
#             session_id=sessionID,
#             socketio=socketio,
#             client_id=client_id,
#             context_string=context_string,
#             **kwargs
#         ):
#             yield response
#             answer += response

    
#     elif action == "add_potential":
#         for response in add_details(
#             tenant_id=tenantID,
#             user_id=userID,
#             llm = llm,
#             plan = plan,
#             user_query=last_user_message,
#             session_id=sessionID,
#             socketio=socketio,
#             client_id=client_id,
#             context_string=context_string,
#             **kwargs
#         ):
#             yield response
#             answer += response
    
#     TangoDao.insertTangoState(
#         tenant_id=tenantID,
#         user_id=userID,
#         key="potential_agent_conv",
#         value=f"Agent Response: {answer}",
#         session_id=sessionID
#     )
        
#     return


# def build_context_for_action(action:str,tenant_id:int,user_id:int,eligible_projects:list) -> str:

#     context_string = ''
#     portfolio_info = team_info = resources_info = roadmap_info =  projects_info = None
#     if action == "assign_to_demand":
#         roadmap_arr_ = RoadmapDao.fetchEligibleRoadmapList(tenant_id=tenant_id, user_id=user_id)
#         roadmap_info = [{"roadmap_id": r.get("roadmap_id"), "roadmap_title": r.get("roadmap_title")} for r in roadmap_arr_ if r]
#         print("\n--debug roadmap_arr--------", roadmap_info[:2])
#         context_string = f"""
#             These are the roadmaps that the user has access to:
#             ------------------
#             All available roadmaps of this tenant: {json.dumps(roadmap_info, indent=2, default=str)}
#         """

#     elif action == "add_potential":
        
#         org_teams = TenantDao.fetchOrgTeamGroupsForTenant(tenant_id=tenant_id)
#         potential_data = TenantDao.getResourceCapacityBasicInfo(tenant_id=tenant_id)
#         user_portfolios = PortfolioDao.fetchApplicablePortfolios(user_id=user_id, tenant_id=tenant_id)

#         print("---debug potential data----- 1",potential_data[:2])
#         clean_potential_data = clean_and_merge_fields(potential_data)
#         print("---debug potential data----- 1",clean_potential_data[:2],"\nTotal: ",len(potential_data))

#         portfolio_info = [{'id': p.get('id'), 'title': p.get('title')} for p in user_portfolios]
#         team_info = [{"orgteam_id": t.get('id'), "orgteam_name": t.get("name") or ""} for t in org_teams]
#         resources_info = [{"resource_id": r.get('id'), "resource_name": r.get('name')} for r in clean_potential_data]

#         context_string = f"""
#             Active Resources:
#             {json.dumps(resources_info, indent=2)}
#             ---------------------------------------------
#             Accessible Portfolios:
#             {json.dumps(portfolio_info, indent=2)}
#             ---------------------------------------------
#             Existing Org Teams:
#             {json.dumps(team_info, indent=2)}
#         """

#     elif action == "unassign_demand_or_project":

#         roadmap_arr_ = RoadmapDao.fetchEligibleRoadmapList(tenant_id=tenant_id, user_id=user_id)
#         roadmap_info = [{"roadmap_id": r.get("roadmap_id"), "roadmap_title": r.get("roadmap_title")} for r in roadmap_arr_ if r]
#         # resources_info = [{"resource_id": r.get('id'), "resource_name": r.get('name')} for r in clean_potential_data]
#         # print("\n--debug roadmap_arr--------", roadmap_info[:5]) 

#         project_arr = ProjectsDao.fetchProjectIdTitleAndPortfolio(tenant_id=tenant_id,project_ids = eligible_projects)
#         context_string = f"""
#             The user has access to:
#             ------------------
#             All the projects which are currently active : {json.dumps(project_arr, indent=2)}
#             ----------------------
#             All available roadmaps of this tenant: {json.dumps(roadmap_info, indent=2, default=str)}
#         """
#         projects_info = project_arr

#     elif action == "update_resource_data":
#         user_portfolios = PortfolioDao.fetchApplicablePortfolios(user_id=user_id, tenant_id=tenant_id)
#         portfolio_info = [{'id': p.get('id'), 'title': p.get('title')} for p in user_portfolios]

#         context_string = f"""
#             ---------------------------------------------
#             Accessible Portfolios:
#             {json.dumps(portfolio_info, indent=2)}
#         """


#     elif action == "assign_to_project":
#         project_arr = ProjectsDao.fetchProjectIdTitleAndPortfolio(tenant_id=tenant_id,project_ids = eligible_projects)
#         # project_arr_ = [{'project_id': p.get('project_id'), 'project_title': p.get('project_title')} for p in project_arr]
#         context_string = f"""
#             These are the projects that the user has access to:
#             ------------------
#             All the projects which are currently active : {json.dumps(project_arr, indent=2)}
#         """
#         projects_info = project_arr


#     initial_context = {
#         "portfolio_info": portfolio_info,
#         "team_info": team_info,
#         "resources_info": resources_info,
#         "projects_info": projects_info,
#         "roadmap_info": roadmap_info,
#         "context_string": context_string
#     }
#     return initial_context






















POTENTIAL_ANALYST = AgentFunction(
    name="potential_analyst",
    description="Analyzes potential opportunities by evaluating user queries and ongoing conversations.",
    args=[],
    return_description="Yields JSON-formatted prompts for action/resource selection or potential resource data with assigning to project, updating resource details, general query, including reasoning.",
    function=potential_analyst,
    type_of_func=AgentFnTypes.SKIP_FINAL_ANSWER.name,
    return_type=AgentReturnTypes.YIELD.name
)









# Handle clarification response
        # if resource_target and clarifying_info:
        #     # Find the matching resource ID from clarification options
        #     matched_option = next((opt for opt in clarifying_info
        #         if (opt["name"].replace("\n", " ").strip() == resource_target )),None
        #     )
        #     if not matched_option:
        #         error_msg = f"No matching resource found for clarification: {resource_target}"
        #         socketio.emit("agent_chat_user", json.dumps({"error": error_msg}), room=client_id)
        #         yield json.dumps({"error": error_msg})
        #         return

        #     resource_data = [{"id": matched_option["id"], **updates}]
        #     # Clear clarification context
        #     TangoDao.deleteTangoStatesForSessionIdAndUserAndKey(session_id=sessionID, user_id=userID, key=f"clarification_{sessionID}")

        # else:
        # Normal update flow