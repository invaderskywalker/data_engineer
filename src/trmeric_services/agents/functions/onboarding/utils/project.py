from src.trmeric_services.agents.functions.onboarding.transition import transition_text
from src.trmeric_database.dao import TangoDao
from src.trmeric_services.tango.types.TangoYield import TangoYield
import traceback
from src.trmeric_services.agents.functions.onboarding.creation_tools.AutonomousCreateProject import AutomousProjectAgent
import json
import concurrent.futures

def further_specific_project_creation(tenantID, userID, sessionID, **kwargs):
    TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_PROJECT_SHOW_INTEGRATION', "", sessionID)
    ret_val =  """Please provide sources using which we can create your project: You can add documents or turn on integrations. If you use integrations, please be sure to tell me about the specific source you want to use, such as a channel, document, or project, referenced by name."""
    
    yield_after = """
```json
{
    "onboarding_add_integration": [
        {
            "key": "TANGO_ONBOARDING_PROJECT"
        }
    ]
}
```
    """
    
    return TangoYield(return_info=ret_val, yield_info=yield_after)
    
def project_creation_cancel(tenantID, userID, sessionID, **kwargs):
    TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_PROJECT_CANCEL', "", sessionID)
    return transition_text(sessionID)

# Helper function to process one project
def process_single_project(project, user_id, tenant_id, llm):
    project_name = project.get('title', 'Unnamed project')
    input_json = {
        "state": project.get('state', 'Build'),
        "title": project.get('title', 'Unnamed project'),
        "description": project.get('description', ''),
        "objectives": project.get('objectives', ''),
        "total_external_spend": project.get('total_external_spend', None),
        "technology_stack": project.get('technology_stack', ""),
        "project_location": project.get('project_location', ''),
        "project_type": project.get('project_type', ''),
        "project_category": project.get('project_category', ''),
        "internal_project": project.get('internal_project', False),
        "start_date": project.get('start_date', None),
        "end_date": project.get('end_date', None),
        "sdlc_method": project.get('sdlc_method', ''),
        "kpi": project.get('kpi', []),
        "team": project.get('team', [])
    }
    
    for key, value in project.items():
        if key == "source" or key.startswith("source_"):
            input_json[key] = value
        
    print(f"Creating project: {project_name}")
    try:
        project_agent = AutomousProjectAgent()
        request_data, ret_val = project_agent.create_project(
            tenant_id=tenant_id,
            user_id=user_id,
            input_json=input_json,
            llm=llm
        )
        print(f"Created project: {project_name}")
        return request_data, ret_val
    except Exception as e:
        print(f"Error creating project {project_name}: {str(e)}")
        traceback.print_exc()
        return None, f"Error creating project {project_name}: {str(e)}\n"

def process_projects(projects, user_id, tenant_id, sessionID, llm):
    progress_json = []
    progress_str = ""
    
    # First yield the initial processing messages for all projects
    for project in projects:
        project_name = project.get('title', 'Unnamed project')
        yield f"Tango is doing final enhancements to the project for {project_name}. Please wait a few moments... \n\n"
    
    # Process projects in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        # Map the processing function to all projects
        futures_to_projects = {executor.submit(process_single_project, project, user_id, tenant_id, llm): project for project in projects}
        
        # Process results as they complete
        for future in concurrent.futures.as_completed(futures_to_projects):
            project = futures_to_projects[future]
            project_name = project.get('title', 'Unnamed project')
            try:
                request_data, ret_val = future.result()
                if request_data:
                    progress_json.append(dict(request_data))
                    progress_str += ret_val + "\n"
                else:
                    progress_str += ret_val
            except Exception as e:
                progress_str += f"Error processing project {project_name}: {str(e)}\n"
                print(f"Error in future for project {project_name}: {str(e)}")
                traceback.print_exc()
    
    if progress_json:
        yield_after = f"""
```json
{{
    "review_progress": {json.dumps(progress_json, indent=4)}
}}
```
        """
        ret_val = progress_str
        TangoDao.insertTangoState(tenant_id, user_id, 'ONBOARDING_PROJECT_FINISHED', '', sessionID)
    else:
        return progress_str
    
    return TangoYield(return_info=ret_val, yield_info=yield_after)