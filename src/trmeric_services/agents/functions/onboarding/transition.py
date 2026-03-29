from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_services.tango.types.TangoYield import TangoYield
from src.trmeric_database.dao import TangoDao
from src.trmeric_database.Database import db_instance
import json

def generate_onboarding_options_json(
    customer_profile_created_and_finished,
    projects_created_and_finished,
    roadmaps_created_and_finished,
    capacity_planner_created_and_finished
):
    options = []

    if not customer_profile_created_and_finished:
        options.append({"label": "I want to create my company profile"})

    if not projects_created_and_finished:
        options.append({"label": "I want to create a project(s)"})

    if not roadmaps_created_and_finished:
        options.append({"label": "I want to create a roadmap(s)"})

    if not capacity_planner_created_and_finished:
        options.append({"label": "I want to create my capacity planning"})

    payload = {
        "onboarding_options": options
    }

    # Properly formatted JSON inside markdown
    yield_after = f"""\n```json\n{json.dumps(payload, indent=4)}\n```"""
    return yield_after

def transition_text(sessionID, **kwargs):
    tenantID = kwargs.get('tenantID', None)
    userID = kwargs.get('userID', None)
    
    states = TangoDao.fetchTangoStatesForSessionId(sessionID)
    customer_profile_created_and_finished = False
    projects_created_and_finished = False
    roadmaps_created_and_finished = False
    capacity_planner_created_and_finished = False
    
    for state in states:
        if state['key'] == 'ONBOARDING_PROFILE_FINISHED':
            customer_profile_created_and_finished = True
        if state['key'] == 'ONBOARDING_PROJECT_FINISHED':
            projects_created_and_finished = True
        if state['key'] == 'ONBOARDING_ROADMAP_FINISHED':
            roadmaps_created_and_finished = True
        if state['key'] == 'ONBOARDING_CAPACITY_FINISHED':
            capacity_planner_created_and_finished = True
            
    if not customer_profile_created_and_finished: 
        customer_profile_query =f"""
        SELECT * FROM customer_profile where tenant_id = {tenantID}
        """
        existing_profile = db_instance.retrieveSQLQueryOld(customer_profile_query)
        
        if len(existing_profile) > 0:
            print("--debug existing_profile", len(existing_profile))
            TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_PROFILE_FINISHED', '', sessionID)
            return "Profile has already been created for this customer. You can not create another profile."

    yield_after = generate_onboarding_options_json(
            customer_profile_created_and_finished,
            projects_created_and_finished,
            roadmaps_created_and_finished,
            capacity_planner_created_and_finished
        )

#     yield_after = """
# ```json
# {
#     "onboarding_options": [
#     """
    
#     if not customer_profile_created_and_finished:
#         yield_after += """
#         {
#             "label": "I want to create my company profile"
#         },
#         """
#     if not projects_created_and_finished:
#         yield_after += """
#         {
#             "label": "I want to create a project(s)"
#         },
#         """
#     if not roadmaps_created_and_finished:
#         yield_after += """
#         {
#             "label": "I want to create a roadmap(s)"
#         },
#         """
#     if not capacity_planner_created_and_finished:
#         yield_after += """
#         {
#             "label": "I want to create my capacity planning"
#         }
#         """

#     yield_after += """
#     ]
# }
# ```
#     """
    
    ret_val = """
    If the user has created a company profile, roadmap, capacity planner or project, you can call this function to create the next step in the onboarding process.
    Remember that once they have already created a company profile, roadmap, capacity planner or project, you can only create other steps in the onboarding process that have not yet been done.
    
    For example, if the user has created a company profile, you can create a roadmap or project or capacity planner. If the user has created a roadmap, you can create a company profile or project or capacity planner.
    If the user has created a roadmap, you can create a company profile or project or capacity planner.
    If the user has created a project, you can create a company profile or roadmap or capacity planner, etc...
    If the user has created a capacity planner for internal resources , then proceed with provider capacity planner function and complete the capacity planning process.
    
    Now, provide the user with a response as so:
    
    What is the next step you would like to take in the onboarding process. 
    """
    
    yield_info = TangoYield(return_info=ret_val, yield_info=yield_after)
    return yield_info

TRANSITION_CREATION_FUNC = AgentFunction(
    name="transition_creation_func",
    description="""
    This function is used to create the next step in the onboarding process. This can be called after the user has created a company profile, roadmap,capacity planner or project.
    Whenever the previous step of creating a company profile, roadmap,capacity planner or project is completed, this function is called to create the next step in the onboarding process.
    
    When the user is doing capacity planning process, the steps are as follows: The internal resources data will be asked first, then provider resources data will be asked and user will provide.
    If the user wants to skip the internal resources data, then the provider resources data will be asked. Then if user asks to skip or proceed ahead then capacity planning process is finished
    and transition to the next unfinished step(s) in the onboarding process.
    
    If a user finishes creating a company profile, roadmap, capacity planner or project, and says "I have reviewed the progress", call this function.
    """,
    return_description='It returns a string that prompts the user to select the next step in the onboarding process.',
    args = [],
    function=transition_text,
)

def general_reply(**kwargs):
    return """
    Based off user input, provide a general reply to the user. 
    """
    
GENERAL_CREATION_FUNC = AgentFunction(
    name="general_creation_func",
    description="""
    This function is used to provide a general reply to the user.
    """,
    return_description='It returns an empty string. Answer the general reply based off chat context.',
    args = None,
    function=general_reply
)

def retrieveLatestStates(sessionID, tenantID, **kwargs):
    states = TangoDao.fetchTangoStatesForSessionId(sessionID)
    
    customer_profile_query =f"""
    SELECT * FROM customer_profile where tenant_id = {tenantID}
    """
    existing_profile = db_instance.retrieveSQLQueryOld(customer_profile_query)
    
    profile_finished = False
    if len(existing_profile) > 0:
        profile_finished = True
        
    ONBOARDING_PROFILE_STATES = ["ONBOARDING_PROFILE_SHOW_SOURCE","ONBOARDING_PROFILE_SOURCE_INFORMATION", "ONBOARDING_PROFILE_FINISHED"]
    latest_profile = []
    for state in ONBOARDING_PROFILE_STATES:
        for s in states:
            if s['key'] == state:
                latest_profile.append(state)
                
    if profile_finished:
        latest_profile = ONBOARDING_PROFILE_STATES
                
    latest_project = []
    ONBOARDING_PROJECT_STATES = ["ONBOARDING_PROJECT_SHOW_INTEGRATION", "ONBOARDING_PROJECT_SYNC", "ONBOARDING_PROJECT_INTEGRATIONS_CONFIRMED", "ONBOARDING_PROJECT_SOURCE_INFORMATION","ONBOARDING_PROJECT_FINISHED"]
    for state in ONBOARDING_PROJECT_STATES:
        for s in states:
            if s['key'] == state:
                latest_project.append(state)
    
    latest_roadmap = []    
    ONBOARDING_ROADMAP_STATES = ["ONBOARDING_ROADMAP_SHOW_INTEGRATION", "ONBOARDING_ROADMAP_SYNC", "ONBOARDING_ROADMAP_INTEGRATIONS_CONFIRMED", "ONBOARDING_ROADMAP_SOURCE_INFORMATION", "ONBOARDING_ROADMAP_FINISHED"]
    for state in ONBOARDING_ROADMAP_STATES:
        for s in states:
            if s['key'] == state:
                latest_roadmap.append(state)

    latest_capacityPlanner = []    
    ONBOARDING_CAPACITY_STATES = ['ONBOARDING_CAPACITY_SHOW_SOURCE_INTERNAL','ONBOARDING_CAPACITY_SHOW_SOURCE_PROVIDER','ONBOARDING_CAPACITY_LOOKS_GOOD_INTERNAL','ONBOARDING_CAPACITY_LOOKS_GOOD_PROVIDER',
                                    'ONBOARDING_CAPACITY_SOURCE_INFORMATION_PROVIDER','ONBOARDING_CAPACITY_SOURCE_INFORMATION_INTERNAL','ONBOARDING_CAPACITY_CLARIFYING_QUESTION','ONBOARDING_CAPACITY_FINISHED']
    for state in ONBOARDING_CAPACITY_STATES:
        for s in states:
            if s['key'] == state:
                latest_capacityPlanner.append(state)

                
    return f"""
```json
{{
    "latest_states": [
        {{
            "latest_profile": "{latest_profile}",
            "latest_project": "{latest_project}",
            "latest_roadmap": "{latest_roadmap}",
            "latest_capacityPlanner": "{latest_capacityPlanner}"
        }}
    ]
}}
```
    """