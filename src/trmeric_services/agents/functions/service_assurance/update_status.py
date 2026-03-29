from src.trmeric_services.tango.functions.integrations.general.ClarifyingQuestionFunction import ask_clarifying_question
from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_utils.enums import AgentFnTypes
from src.trmeric_services.agents.apis.service_assurance import ServiceAssuranceApis
from src.trmeric_utils.constants.project_status import PROJECT_STATUS_TYPE_TO_CODE, PROJECT_STATUS_VALUE_TO_CODE
from src.trmeric_services.agents.prompts.agents import update_status_data_creation_prompt
from src.trmeric_utils.json_parser import extract_json_after_llm

def update_project_status(
    tenantID: int,
    userID: int,
    eligibleProjects: list[int],
    update_data=None,
    # if_user_has_asked_to_update_project_status_and_given_any_comment=False,
    llm= None,
    model_opts=None,
    socketio=None,
    client_id=None,
    **kwargs
):
    
    print("debug -- update_project_status ", tenantID, userID, update_data)
    error_message = ""
    success_messages = ""
    log_info = {"tenant_id": tenantID, "user_id": userID}

    service_assurance_service = ServiceAssuranceApis()
    
    try:
        if not update_data:
            raise Exception("Provide comment for update for respective projects")
        
        prompt = update_status_data_creation_prompt(update_data)
        response = llm.run(prompt, model_opts, "update_project_llm", log_info)  
        print("response update_status_data_creation_prompt ", response)
        res_json = extract_json_after_llm(response)
        print("json update_status_data_creation_prompt", res_json)
        
        
        for item in res_json.get("status_updates"):
            print("updating .. item in ", item)
            project_id = item["project_id"]
            project_name = item["project_title"]
            update_type = item["update_types"]
            update_value = item["update_values"]
            user_given_comments_for_each_type = item["comments"]
            if len(update_type) == len(update_value) and len(update_type) == len(user_given_comments_for_each_type) and len(update_value) > 0:
                checkDone = 0
                for i in range(len(update_type)):
                    _type = PROJECT_STATUS_TYPE_TO_CODE[update_type[i]]
                    _value = PROJECT_STATUS_VALUE_TO_CODE[update_value[i]]
                    _comment = user_given_comments_for_each_type[i]
                    if _comment == "":
                        raise Exception("No comment provided")
                    request_json = {
                        "tenant_id": tenantID,
                        "user_id": userID,
                        "type": _type,
                        "value": _value,
                        "comments": _comment,
                        "actual_percentage": 0
                    }
                    response = service_assurance_service.update_status(project_id, request_json)
                    if (response.status_code == 201):
                        # pass
                        # success_messages += f"""
                        #         Status Updated for Project - {project_name}
                                
                        #     """
                        checkDone += 1
                    else:
                        error_message += f"Failure in updating status: f{_type} for project {project_name} - error: {response}"
                 
                if checkDone > 0 and socketio:
                    success_messages += f"""
                        Status Updated for Project - {project_name}
                    """
                    socketio.emit("tango_agent_response", f"Status Updated for Project - {project_name}", room=client_id)
            else:
                raise(f"{project_name} could not be updated")
            
        
        
        
        return f"{success_messages}"
    except Exception  as e:
        print("error occured in updating project status ", e)
        error_message += str(e)
            
    
    return f"""
        I could not understand what your update is.   {error_message}                        
    """
    

RETURN_DESCRIPTION = """
This function returns a response to clarify user intent when there is insufficient information to update project statuses directly. 
Typically, it will prompt the user to provide more detailed instructions on the desired status updates for the selected projects.
"""

ARGUMENTS = [
    {
        "name": "update_data",
        "type": "json[]",
        "description": """
            Since the user can give multiple projects and they can have multiple project ids
            Add the update type and update value which the user tells in this format
            [{
                "project_id": "", // important: project id for update
                "project_name": "", // important: project name for update
                "user_comment": "", // comment given for each project update
            },...]
        """,
    },
]

UPDATE_PROJECT_STATUS = AgentFunction(
    name="update_project_status",
    description="""
        Very careful with this function:
        Do not pass the arguments in user_comment if the user hasn't mentioned.
        This function as the name suggessts is responsible for updating project status.
    """,
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=update_project_status,
    type_of_func=AgentFnTypes.ACTION_TAKER.name
)
