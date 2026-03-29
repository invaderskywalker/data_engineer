from src.trmeric_services.agents.core import AgentFunction
from src.trmeric_services.integration.SpecifiedIntegrationRetriever.SpecifiedIntegrationRetreiver import SpecifiedIntegrationRetriever as IntegrationRetriever
from src.trmeric_services.agents.functions.onboarding.prompts.RoadmapPrompt import RoadmapGenerator
from src.trmeric_services.agents.functions.onboarding.utils.sync import integration_sync
import traceback
import json
from src.trmeric_database.dao import TangoDao
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.tango.types.TangoYield import TangoYield
from src.trmeric_services.agents.functions.onboarding.utils.clarifying import clarifying_information_enhancement
from src.trmeric_services.agents.functions.onboarding.utils.roadmap import further_specific_roadmap_creation, process_roadmaps, roadmap_creation_cancel
from src.trmeric_services.journal.Activity import detailed_activity

def specific_roadmap_creation(tenantID: int, userID: int, llm, integrations, sessionID, integration_source_list:list = [], clarifying_information:str= '', **kwargs):
    print(f"source_list: {integration_source_list}")
    last_user_message = kwargs.get('last_user_message', None)
    last_tango_message = kwargs.get('last_tango_message', None)
    
    #############################################################################################    
    # obtain states using Tango States
    
    states = TangoDao.fetchTangoStatesForSessionId(sessionID)
    jira_sync_completed_by_tango_in_chat = False
    integrations_selection_option_shown_to_user = False
    integrations_confirmed = False
    clarifying_count = 0
    integrationInfo = None
    clarifying_questions = []
    for state in states:
        if state['key'] == 'ONBOARDING_ROADMAP_CLARIFYING_QUESTION':
            clarifying_count += 1
            clarifying_questions.append(state['value'])
        if state['key'] == 'ONBOARDING_ROADMAP_SYNC':
            jira_sync_completed_by_tango_in_chat = True
        if state['key'] == 'ONBOARDING_ROADMAP_SHOW_INTEGRATION':
            integrations_selection_option_shown_to_user = True
        if state['key'] == 'ONBOARDING_ROADMAP_FINISHED':
            return "Roadmaps have already been created in this onboarding session"
        if state['key'] == 'ONBOARDING_ROADMAP_INTEGRATIONS_CONFIRMED':
            integrations_confirmed = True
        if state['key'] == 'ONBOARDING_ROADMAP_SOURCE_INFORMATION':
            integrationInfo = json.loads(state['value'])
    
    
    clarifying_information = clarifying_information_enhancement(clarifying_information, clarifying_questions, last_tango_message, last_user_message)

    #############################################################################################    
    # in the case where the user has not yet selected integrations
    try:
        if not integrations_selection_option_shown_to_user:
            detailed_activity("onboarding::roadmaps::show_integrations", "The user has begun the roadmap onboarding process. The user is selecting what integrations to use for roadmap creation", user_id=userID)
            return further_specific_roadmap_creation(tenantID, userID, sessionID)
    except Exception as e:
        print(traceback.format_exc())
        appLogger.error({
            "event": "create_roadmaps_from_integrations_init_ahub",
            "tenant_id": tenantID, 
            "user_id": userID,
            "error":  e, 
            "traceback":traceback.format_exc()
        })
        return "Error in asking for integrations"

    #############################################################################################
    # next, after integrations are selected, their content is synced and shown to user in tiles
    try:
        if not jira_sync_completed_by_tango_in_chat:
            yield "Tango is syncing your integrations. Please wait a moment... \n\n"
            synced = integration_sync(integrations, tenantID, userID, sessionID, 'TANGO_ONBOARDING_ROADMAP')
            if synced: return synced
    except Exception as e: 
        print(traceback.format_exc())
        appLogger.error({
            "event": "create_roadmaps_from_integrations_init_ahub",
            "tenant_id": tenantID, 
            "user_id": userID,
            "error":  e, 
            "traceback":traceback.format_exc()
        })
        return "Error in syncing integrations"

    #############################################################################################
    # after integrations are synced, and the user selects them at that step, we ask the user to confirm the integrations they selected
    
    try:           
        if jira_sync_completed_by_tango_in_chat and not integrations_confirmed:
            source_names = []
            for integration in integrations:
                if integration.name == 'uploaded_files':
                    files = integration.fetchCurrentSessionUploadedFiles('TANGO_ONBOARDING_ROADMAP')
                    for file_id, file_name in files.items():
                        source_names.append(f"Uploaded Document: {file_name}")       
            for source in integration_source_list:
                integration = source.get('integration', None)
                source_name = source.get('source_name', None)
                source_names.append(f"{integration}: {source_name}")
            ret_val = f"""Here are some of the possible sources we recognized from your integrations. We will use your uploaded documents. 
            If you would like to use any of these other sources from integrations, please provide the names in the chat. 
            If you need new integrations, please cancel the project creation and restart. Otherwise, to proceed, click the confirm sources button."""  
            yield_after = f"""
```json
{{
"onboarding_roadmap_source_confirmation": {json.dumps(source_names, indent=4)}"   
}}
```
            """ 
            if len(source_names) == 0:
                return further_specific_roadmap_creation(tenantID, userID, sessionID)
            return TangoYield(return_info=ret_val, yield_info=yield_after)
    except Exception as e:
        print(traceback.format_exc())
        appLogger.error({
            "event": "create_roadmaps_from_integrations_init_ahub",
            "tenant_id": tenantID, 
            "user_id": userID,
            "error":  e, 
            "traceback":traceback.format_exc()
        })
        return "Error in confirming integrations"
    
    #############################################################################################
    # check the edge case where no sources have been specified. return the user to the beginning step.
    try:
        if len(integration_source_list) == 0:
            for integration in integrations:
                if integration.name == "uploaded_files":
                    files = integration.fetchCurrentSessionUploadedFiles("TANGO_ONBOARDING_ROADMAP")
                    if not files:
                        TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_ROADMAP_CANCEL', "", sessionID)
                        return further_specific_roadmap_creation(tenantID=tenantID, userID=userID, sessionID=sessionID)
    
    except Exception as e:
        print(traceback.format_exc())
        appLogger.error({
            "event": "create_roadmaps_from_integrations_init_ahub",
            "tenant_id": tenantID, 
            "user_id": userID,
            "error":  e, 
            "traceback":traceback.format_exc()
        })
        return "Error in checking for uploaded files"
    
    #############################################################################################
    # at this point all sources have been read and confirmed correctly. we can now generate roadmaps
    try:
        if not integrationInfo:
            yield "Tango is looking for the information you provided in the sources you mentioned. Please wait a moment... \n\n"
            detailed_activity("onboarding::roadmaps::confirmed_sources", f"User has confirmed the sources for roadmap creation: {str(integration_source_list)}...", user_id=userID)
            gen = IntegrationRetriever(integration_source_list, integrations, 'roadmap', llm, userID, tenantID, last_user_message).integrationInfo
            try:
                while True:
                    update = next(gen)
                    yield update 
            except StopIteration as e:
                integrationInfo = e.value   
            TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_ROADMAP_SOURCE_INFORMATION', json.dumps(integrationInfo), sessionID)
            detailed_activity("onboarding::roadmaps::integration_info_retrieved", f"Integration information has been retrieved: {str(integrationInfo)[:30000]}...", user_id=userID)

        print('generating roadmaps')
        appLogger.info({"event":"onboarding:roadmap","msg": "Generating roadmaps", "tenant_id": tenantID, "user_id": userID})
        yield "Tango has compiled the information from your provided sources and is now generating roadmaps... \n\n"
        roadmaps = RoadmapGenerator(llm, integrationInfo, clarifying_information, clarifying_count).generateRoadmaps(userID)
        print('generating roadmaps output ')
        if "clarifying_question" in roadmaps:
            clarifying_question = roadmaps["clarifying_question"].get_return_info()
            TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_ROADMAP_CLARIFYING_QUESTION', clarifying_question, sessionID)
            return clarifying_question
        
    except Exception as e: 
        print(f"Error initializing action hub: {e}")
        print(traceback.format_exc())
        appLogger.error({
            "event": "create_roadmaps_from_integrations_init_ahub",
            "tenant_id": tenantID, 
            "user_id": userID,
            "error":  e, 
            "traceback":traceback.format_exc()
        })
        return "Error in generating roadmaps"
    
    #############################################################################################
    # generate roadmaps are sent to the API for creation
    try:
        print('Processing roadmaps')
        roadmap_names = [roadmap['title'] for roadmap in roadmaps]
        detailed_activity("onboarding::roadmaps::roadmaps_generated", f"All Roadmaps have been generated: {str(roadmap_names)[:500]}...", user_id=userID)
        gen = process_roadmaps(roadmaps, userID, tenantID, sessionID, llm)
        appLogger.info({"event":"onboarding:roadmap","msg": "Processing roadmaps", "tenant_id": tenantID, "user_id": userID})
        try:
            while True:
                yield next(gen)
        except StopIteration as e:
            exit_status = e.value
        return exit_status
    except Exception as e:
        print(f"Error creating roadmaps: {e}")
        print(traceback.format_exc())
        appLogger.error({
            "event": "create_roadmaps_from_integrations_process_roadmaps",
            "tenant_id": tenantID, 
            "user_id": userID,
            "error":  e, 
            "traceback":traceback.format_exc()
        })
        return "Error with roadmap creation API"

ROADMAP_CREATION_FUNC = AgentFunction(
    name="specific_roadmap_creation",
    description="""
    IF THE USER SAYS "I want to build roadmaps", CALL THIS FUNCTION.
    
    Anytime the user asks you to create a roadmap, or is in the flow of creating roadmaps, call only this function. This creates roadmaps from specifically mentioned integrations. 
    You don't need to call other functions to read from the integration sources as this one will do it for you. Even if the user has not listed integration sources yet, call this function with no integration arguments and we will prompt for those sources.
    
    Remember that if the user says no more questions or clarifying questions, this does not mean that you provide no arguments, but rather you note this as clarifying information.
    """,
    args = [
        {
            "name": "integration_source_list",
            "description": 
            """
                A list of integration sources to use for creating projects, as clearly specified by the user. Add as many integration sources as the user provides.
                Be careful to distinguish clarifying information from the actual sources the user wants to use. Clarifying Information is further described below.
                
                Remember that these integrations should be things like specific channels, documents, or project from software like Slack, Jira, Google Drive, or Microsoft Office.
                Any other descriptive information not about an integration specifically should be placed in the clarifying_information argument.
                
                IMPORTANT: If a user submits a source called Uploaded Document: xxx, then it will be processed internally and you can ignore it here.
                
                For example, things such as contact information are clarifying information, not integration sources. But, a specific slack channel is an integration source.
                Return the list in the following format:
                    [
                        {
                            "name": "integration_to_use_1",
                            "integration": "Choose the specified integration string from the following: slack, jira, drive, office",
                            "source_name": "Name of the document/channel/project or source that the user asked you to pull information from",
                            "source_id": "ID of the document/channel/project or source that the user asked you to pull information from",
                            "type": "str"
                        },
                        {
                            "name": "integration_to_use_2",
                            "integration": "Choose the specified integration string from the following: slack, jira, drive, office",
                            "source_name": "Name of the document/channel/project or source that the user asked you to pull information from",
                            "source_id": "ID of the document/channel/project or source that the user asked you to pull information from",
                        }
                    ]
            """,
            "type": "list"
        },
        {
            "name": "clarifying_information",
            "description": '''
            If the user has tried to run this process once, and you, Tango, had determined that this process did not contain enough information or had points of confusion, you asked the user follow up questions.
            In this case, if the user has provided the necessary information, and you are running this process again, set this to True. Make sure you compile and keep all the user's clarifying information that they provided in the follow-up questions.
            If there has not been follow up questions asked and no feedback is provided, you can set this to None.
            
            This should be a string of the clarifying information provided. Be sure to look through all of the user's recent messages and feel free to include them completely. You don't need to be concise here and can include all the information the user has provided. 
            
            If a user says to keep some field empty or fill it to Tango's discretion, etc... you should include all of this info it in this string paragraph here.     
                        
            If a user asks you to move on and create projects, or to ask no more clarifying questions, the also note this down here.   
            ''',
            "type": "str",
            "required": "true"
        },
    ],
    return_description="Confirmation of roadmaps being created",
    function=specific_roadmap_creation,
    return_type = "YIELD"
)

ROADMAP_CREATION_CANCEL = AgentFunction(
    name="roadmap_creation_cancel",
    description="""
    In the process of roadmap creation, if the user says they want to cancel the roadmap creation process, call this function.
    """,   
    args = [],
    return_description="Options of what the user can do next",
    function=roadmap_creation_cancel,
)