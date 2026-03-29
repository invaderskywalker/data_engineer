from src.trmeric_services.tango.functions.integrations.general.ClarifyingQuestionFunction import ask_clarifying_question
from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_utils.enums import AgentFnTypes
from src.trmeric_services.agents.apis.service_assurance import ServiceAssuranceApis
from src.trmeric_utils.constants.project_status import PROJECT_STATUS_TYPE_TO_CODE, PROJECT_STATUS_VALUE_TO_CODE
from src.trmeric_services.agents.prompts.agents import create_risk_prompt
from src.trmeric_utils.json_parser import extract_json_after_llm

def update_or_create_risk(
    tenantID: int,
    userID: int,
    eligibleProjects: list[int],
    # project_id = None,
    risk_data=None,
    llm= None,
    model_opts=None,
    **kwargs
):
    print("debug -- update_or_create_risk ", tenantID, userID, risk_data)
    error_message = ""
    success_message = ""
    
    if not risk_data or risk_data == []:
        return "If the user has not mentioned project for the risk update. Ask"
    
    ## existing risks for these projects
    
    
    service_assurance_service = ServiceAssuranceApis()
        
    prompt = create_risk_prompt(risk_data)
    log_info = {"tenant_id": tenantID, "user_id": userID}
    response = llm.run(prompt, model_opts, "update_or_create_risk", log_info)  
    # print("response update_or_create_risk ", response)
    res_json = extract_json_after_llm(response)
    # print("json update_or_create_risk", res_json)
    
    if res_json:
        print(f"res_json type: {type(res_json)}, value: {res_json}")
        for item in res_json:
            print(f"item type: {type(item)}, value: {item}")
            if item["valid_risk_data"] == 'true':
                project_id = item["project_id"]
                priority = value = 1 if item['priority'] == "" or item["priority"] is None or item["priority"] == 0 else item['priority']
                request_json = {
                    "user_id": userID,
                    "tenant_id": tenantID,
                    "risk_list":[{
                        "id": 0,
                        "description": item["description"],
                        "impact": item["impact"],
                        "mitigation": item["mitigation"],
                        "priority": priority,
                        "due_date": item["due_date"]
                    }]
                }
                response = service_assurance_service.create_risk(project_id, request_json)
                success_message += f"--updated project risk - {item['project_name']}"
            else:
                error_message += f"Pass proper risk description for {item['project_name']}"
      
    print("error message ", error_message)
    print("success message ", success_message)          
    if success_message != "":
        return success_message      
    return f"""
        I'm not clear on what you want to do?  {error_message}                        
    """
        
    

RETURN_DESCRIPTION = """
This function will be used for the creating/updating risks in user's project(s)
"""

ARGUMENTS = [
    {
        "name": "risk_data",
        "type": "json[]",
        "description": """
            Since the user can give multiple projects and they can have multiple project ids
            [{
                "project_id": "", // important: project id for risk add/update
                "project_name": "", // important: project name for risk add/update
                "detailed_risk_comment": "", // don't pass placeholders. important: comment given for each project risk add/update. if commernt is not given . dont pass placeholder
            },...]
        """,
        "required": 'true'
    },
]

UPDATE_OR_CREATE_RISK = AgentFunction(
    name="update_or_create_risk",
    description="""
        This function is repsosible for creating/updating risks of a project.
        Do not pass placeholders to this fn.
    """,
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=update_or_create_risk,
    type_of_func=AgentFnTypes.ACTION_TAKER.name
)
