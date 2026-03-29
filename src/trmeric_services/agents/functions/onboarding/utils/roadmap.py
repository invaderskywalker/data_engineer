from src.trmeric_services.agents.functions.onboarding.creation_tools.AutonomousCreateRoadmap import RoadmapAgent
from src.trmeric_services.agents.functions.onboarding.transition import transition_text
from src.trmeric_services.tango.types.TangoYield import TangoYield
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_database.dao import TangoDao
import concurrent.futures
import traceback, json
import datetime
import re

def further_specific_roadmap_creation(tenantID, userID, sessionID,**kwargs):
    TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_ROADMAP_SHOW_INTEGRATION', "", sessionID)
    ret_val =  """Please provide sources using which we can create your roadmap: You can add documents or turn on integrations. If you use integrations, please be sure to tell me about the specific source you want to use, such as a channel, document, or project, referenced by name."""
    
    yield_after = """
```json
{
    "onboarding_add_integration": [
        {
            "key": "TANGO_ONBOARDING_ROADMAP"
        }
    ]
}
```
    """
    
    return TangoYield(return_info=ret_val, yield_info=yield_after)
    
def roadmap_creation_cancel(tenantID, userID, sessionID, **kwargs):
    TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_ROADMAP_CANCEL', "", sessionID)
    return transition_text(sessionID)

# Helper function to process one roadmap
def process_single_roadmap(roadmap, user_id, tenant_id, llm):
    # print("process_single_roadmap ------", roadmap)
    # Extract data from the roadmap
    roadmap_title = roadmap.get('title', 'Unnamed roadmap')
    roadmap_description = roadmap.get('description', '')
    roadmap_objectives = roadmap.get('objectives', '')
    roadmap_scope = roadmap.get('scope', [])
    roadmap_priority = roadmap.get('priority', 1)
    roadmaps_keyresults = roadmap.get('key_results', [])
    roadmap_team = roadmap.get('team', [])
    roadmap_category = roadmap.get('category', '')
    roadmap_type = roadmap.get('type', 1)
    roadmap_budget = roadmap.get('budget', 0)
    roadmap_org_strategy_align = roadmap.get('org_strategy_align', '')
    roadmap_constraints = roadmap.get('constraints', [])
    roadmap_start_date = roadmap.get('start_date', None)
    roadmap_end_date = roadmap.get('end_date', None)
    roadmap_portfolio = roadmap.get('roadmap_portfolio', None)
    roadmap_business_sponsor_lead = roadmap.get("business_sponsor_lead", None)

    # Create a single JSON object for the roadmap
    roadmap_json = {
        "title": roadmap_title,
        "description": roadmap_description,
        "objectives": roadmap_objectives,
        "scope": roadmap_scope,
        "priority": roadmap_priority,
        "key_results": roadmaps_keyresults,
        "team": roadmap_team,
        # "category": roadmap_category,
        "type": roadmap_type,
        "budget": 0,
        "org_strategy_align": roadmap_org_strategy_align,
        "constraints": roadmap_constraints,
        "start_date": roadmap_start_date,
        "end_date": roadmap_end_date,
        "roadmap_portfolio": roadmap_portfolio,
        "roadmap_business_sponsor_lead": roadmap_business_sponsor_lead,
    }
    
    for key, value in roadmap.items():
        if key == "source" or key.startswith("source_"):
            roadmap_json[key] = value
    
    print(f"Creating roadmap: {roadmap_title} with description: {roadmap_description}")
    appLogger.info({"event":"onboarding:roadmap","msg": "roadmap_created", "roadmap_title": roadmap_title})
    try:
        request_data, ret_val = RoadmapAgent().create_roadmap(
            tenant_id=tenant_id,
            user_id=user_id,
            input_json=roadmap_json,
            llm=llm,
        )
        print(f"Created roadmap: {roadmap_title}")
        return request_data, ret_val
    except Exception as e:
        print(f"Error creating roadmap {roadmap_title}: {str(e)}")
        traceback.print_exc()
        return None, f"Error creating roadmap {roadmap_title}: {str(e)}\n"


def process_roadmaps(roadmaps, user_id, tenant_id, sessionID, llm):
    progress_json = []
    progress_str = ""
    
    # First yield the initial processing messages for all roadmaps
    for roadmap in roadmaps:
        roadmap_title = roadmap.get('title', 'Unnamed roadmap')
        yield f"Tango is doing final enhancements to the roadmap for {roadmap_title}. Please wait a few moments... \n\n"
    
    # Process roadmaps in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        # Map the processing function to all roadmaps
        futures_to_roadmaps = {executor.submit(process_single_roadmap, roadmap, user_id, tenant_id,llm): roadmap for roadmap in roadmaps}
        
        # Process results as they complete
        for future in concurrent.futures.as_completed(futures_to_roadmaps):
            roadmap = futures_to_roadmaps[future]
            roadmap_title = roadmap.get('title', 'Unnamed roadmap')
            try:
                request_data, ret_val = future.result()
                if request_data:
                    progress_json.append(dict(request_data))
                    progress_str += ret_val + "\n"
                else:
                    progress_str += ret_val
            except Exception as e:
                progress_str += f"Error processing roadmap {roadmap_title}: {str(e)}\n"
                print(f"Error in future for roadmap {roadmap_title}: {str(e)}")
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
        TangoDao.insertTangoState(tenant_id, user_id, 'ONBOARDING_ROADMAP_FINISHED', '', sessionID)
    else:
        return progress_str
    
    return TangoYield(return_info=ret_val, yield_info=yield_after)
