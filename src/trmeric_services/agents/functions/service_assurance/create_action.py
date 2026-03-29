from src.trmeric_services.tango.functions.integrations.general.ClarifyingQuestionFunction import ask_clarifying_question
from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_utils.enums import AgentFnTypes
from src.trmeric_services.agents.apis.service_assurance import ServiceAssuranceApis
from src.trmeric_utils.constants.project_status import PROJECT_STATUS_TYPE_TO_CODE, PROJECT_STATUS_VALUE_TO_CODE
from src.trmeric_services.agents.prompts.agents import create_action_prompt
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_database.dao import TenantDao

def update_or_create_action(
    tenantID: int,
    userID: int,
    eligibleProjects: list[int],
    action_data=None,
    llm= None,
    model_opts=None,
    **kwargs
):
    
    print("debug -- update_or_create_action ", tenantID, userID, action_data)
    
    error_message = ""
    success_message = ""
    
    if not action_data or action_data == []:
        return ask_clarifying_question("Provide Action Info and if you want collaboration") 
    
    user_list = TenantDao.FetchUsersOfTenant(tenant_id=tenantID)
    # print(user_list)
    for action in action_data:
        if action.get("collaboration_feedback_provided_by_user") == "true":
            pass
        else:
            return f"""
                Do you want to add collaborators for this action. Whom you want top choose: {user_list}
            """
            
        
    service_assurance_service = ServiceAssuranceApis()
        
    prompt = create_action_prompt(action_data, user_list)
    log_info = {"tenant_id": tenantID, "user_id": userID}
    response = llm.run(prompt, model_opts, "update_or_create_risk", log_info)  
    res_json = extract_json_after_llm(response)
    print("json update_or_create_action", res_json)
    
    if res_json:
        for item in res_json:
            if item.get("valid_action_data") == 'true':
                priority = value = 1 if item['priority'] == "" or item["priority"] is None or item["priority"] == 0 else item['priority']
                request_json = {
                    "user_id": userID,
                    "tenant_id": tenantID,
                    "creation_list":[{
                        "head_text": item["head_text"],
                        "details_text": item["details_text"],
                        "due_date": item["due_date"],
                        "priority": priority,
                        "tag": item["tag"]
                    }]
                }
                res = service_assurance_service.add_action(request_json)
                
                try:
                    response_json = res.json()
                    print("Response JSON:", response_json)
                    action_id = response_json["data"][0]["id"]
                    if len(item["colaborators_info"]) > 0:
                        ## add these collaborators
                        request_json = {
                            "user_id": userID,
                            "tenant_id": tenantID,
                            "user_list":item["colaborators_info"],
                            "type": 1, 
                            "ref_id": action_id, 
                            "details": item["details_text"],
                        }
                        res = service_assurance_service.add_collaboration(request_json)
                        print("Response collaborate:", res)
                        success_message += f"---Collaborators added---"

                    # return response_json
                except ValueError:
                    print("Response is not in JSON format.")
                    error_message += f"Error in adding collaborators"
                    # return res.text
                
                success_message += f"--action created - {str(res)}"
            else:
                error_message += f"Pass proper data for {item['project_name']} - all data info - {response}"
      
    print("error message ", error_message)
    print("success message ", success_message)          
    if success_message != "":
        return success_message      
    return ask_clarifying_question(f"""
        I'm not clear on what you want to do?  {error_message}                        
    """)
        
    

RETURN_DESCRIPTION = """
This function will be used for the creating/updating action and action collaboration
"""

ARGUMENTS = [
    {
        "name": "action_data",
        "type": "json[]",
        "description": """
            Since the user can give multiple actions so a json is required
            [{
                "detailed_action_comment": "", // don't pass placeholders. important: comment given for each project action add/update. if commernt is not given . dont pass placeholder
                "collaboration_feedback": "", // if the user has mentioned he wants collaboartion and with whom
                "collaboration_feedback_provided_by_user": "true" or "false"
            },...]
        """,
        "required": 'true'
    },
]

UPDATE_OR_CREATE_ACTION = AgentFunction(
    name="update_or_create_action",
    description="""
        Very careful with this function:
        Do not pass the arguments in action_data if the user hasn't mentioned.
    """,
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=update_or_create_action,
    type_of_func=AgentFnTypes.ACTION_TAKER.name
)
