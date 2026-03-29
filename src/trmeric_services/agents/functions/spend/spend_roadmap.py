from src.trmeric_services.agents.core import AgentFunction
from src.trmeric_database.dao import TangoDao
import json
from src.trmeric_services.agents.functions.spend.utils.roadmap_prompt import RoadmapGenerator
from src.trmeric_services.agents.functions.spend.utils.spend import emit_progress
from src.trmeric_services.agents.functions.onboarding.creation_tools.AutonomousCreateRoadmap import RoadmapAgent
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_services.journal.Activity import detailed_activity

def spend_roadmap(tenantID, userID, llm, sessionID, **kwargs):
    states = TangoDao.fetchTangoStatesForSessionId(sessionID)
    uijson = None
    for state in states:
        if state['key'] == 'SPEND_EVALUATION_FINISHED':
            uijson = json.loads(state['value'])
 
    if uijson:
        roadmap = RoadmapGenerator(llm, roadmap_info= uijson).generateRoadmaps()
        result = RoadmapAgent().create_roadmap(tenant_id = tenantID, user_id = userID, input_json = roadmap, llm = llm, source = False)
        
        # Log activity: Generated roadmap based on spend analysis
        detailed_activity(
            activity_name="spend_roadmap_generation",
            activity_description="User requested roadmap creation based on spend analysis. Tango generated comprehensive implementation roadmap with prioritized initiatives, timelines, and resource requirements for IT cost optimization strategies.",
            user_id=userID
        )
        
        return result
    
def spend_roadmap_action(tenantID, userID, llm, sessionID, category, subcategory, **kwargs):
    states = TangoDao.fetchTangoStatesForSessionId(sessionID)
    uijson = None
    for state in states:
        if state['key'] == 'SPEND_EVALUATION_FINISHED':
            uijson = json.loads(state['value'])
            
    uijson = uijson['data']
    subsection = uijson['categories_breakdown']
    subsection = next((sub for sub in subsection if sub['category'] == category), None)
    if subsection is None:
        return "Category not found"
    subsection = subsection['sub_category_breakdown']
    subsection = next((sub for sub in subsection if sub['sub_category'] == subcategory), None)
    if subsection is None:
        return "Subcategory not found"
 
    if uijson:
        Generator = RoadmapGenerator(llm, roadmap_info= uijson)
        roadmap = Generator.generateRoadmaps(level = 'sub_category', subsection = subsection)
        result = RoadmapAgent().create_roadmap(tenant_id = tenantID, user_id = userID, input_json = roadmap, llm = llm, source = False)
        
        # Log activity: Generated subcategory-specific roadmap
        detailed_activity(
            activity_name="spend_subcategory_roadmap_generation",
            activity_description=f"User requested focused roadmap for {category} - {subcategory} subcategory. Tango generated targeted implementation roadmap with specific initiatives, vendor recommendations, and cost optimization strategies for this spend area.",
            user_id=userID
        )
        
        return result


def roadmap_spend_controller(**kwargs):
    tenantID = kwargs.get('tenantID', None)
    userID = kwargs.get('userID', None)
    sessionID = kwargs.get('sessionID', None)
    
    llm = ChatGPTClient(userID, tenantID)
        
    level = kwargs.get('level', None)
    if level is None:
        return "Please provide a level for the roadmap"
    if level == "full":
        return spend_roadmap(tenantID, userID, llm, sessionID,)
    if level == "category":
        category = kwargs.get('category', None)
        if category is None:
            return "Please provide a category for the roadmap"
        pass # add next level
    if level == "sub_category":
        category = kwargs.get('category', None)
        if category is None:
            return "Please provide a category for the roadmap"
        sub_category = kwargs.get('sub_category', None)
        if sub_category is None:
            return "Please provide a sub category for the roadmap"
        return spend_roadmap_action(tenantID, userID, llm, sessionID, category, sub_category)
        
# SPEND_ROADMAP = AgentFunction(
#     name="spend_roadmap",
#     description="""
#     Call this function when the user has finished running their spend evaluation and would like to create a roadmap based off of this.
#     IMPORTANT: Only call this function if the user explecity asks for a roadmap creation. 
#     """,
#     args=[
#     ],
#     return_description="confirmation of the created roadmap",
#     function=spend_roadmap,
# )
