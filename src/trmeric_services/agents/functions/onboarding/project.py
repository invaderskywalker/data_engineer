from src.trmeric_services.agents.core import AgentFunction
from src.trmeric_services.integration.SpecifiedIntegrationRetriever.SpecifiedIntegrationRetreiver import SpecifiedIntegrationRetriever as IntegrationRetriever
from src.trmeric_services.agents.functions.onboarding.prompts.ProjectPrompt import ProjectGenerator
from src.trmeric_services.agents.functions.onboarding.utils.sync import integration_sync
import traceback, json
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.tango.types.TangoYield import TangoYield
from src.trmeric_database.dao import TangoDao
from src.trmeric_services.agents.functions.onboarding.utils.clarifying import clarifying_information_enhancement
from src.trmeric_services.agents.functions.onboarding.utils.project import further_specific_project_creation, process_projects, project_creation_cancel
from src.trmeric_services.journal.Activity import detailed_activity

def specific_project_creation( tenantID: int, userID: int, llm, integrations, sessionID, integration_source_list=[], clarifying_information='', **kwargs):        
    last_user_message = kwargs.get('last_user_message', None)
    last_tango_message = kwargs.get('last_tango_message', None)   
    isolated_rows = kwargs.get('excel_or_csv_has_projects_on_each_row', None)
    print(f"source_list: {integration_source_list}")
    
    ######################################################
    # Retrieve the state of the onboarding session
    
    states = TangoDao.fetchTangoStatesForSessionId(sessionID)
    jira_sync_completed_by_tango_in_chat = False
    integrations_selection_option_shown_to_user = False
    integrations_confirmed = False
    integrationInfo = None
    isolated_rows_checked = False
    clarifying_count = 0
    clarifying_questions = []
    for state in states:
        if state['key'] == 'ONBOARDING_PROJECT_CLARIFYING_QUESTION':
            clarifying_count += 1
            clarifying_questions.append(state['value'])
        if state['key'] == 'ONBOARDING_PROJECT_SYNC':
            jira_sync_completed_by_tango_in_chat = True
        if state['key'] == 'ONBOARDING_PROJECT_SHOW_INTEGRATION':
            integrations_selection_option_shown_to_user = True
        if state['key'] == 'ONBOARDING_PROJECT_FINISHED':
            return "Projects have already been created in this onboarding session"
        if state['key'] == 'ONBOARDING_PROJECT_INTEGRATIONS_CONFIRMED':
            integrations_confirmed = True
        if state['key'] == 'ONBOARDING_PROJECT_SOURCE_INFORMATION':
            integrationInfo = json.loads(state['value'])
        if state['key'] == 'ISOLATED_ROWS_PROJECT':
            isolated_rows_checked = True
            saved_integration_source_list = json.loads(state['value'])
           
    ######################################################
    # Check if clarifying information is provided
    clarifying_information = clarifying_information_enhancement(clarifying_information, clarifying_questions, last_tango_message, last_user_message)
        
        
    ######################################################
    # Show the possible integrations to the user
    try: 
        if not integrations_selection_option_shown_to_user:
            detailed_activity("onboarding::projects::show_integrations", "The user has begun the project onboarding process. The user is selecting what integrations to use for project creation", user_id=userID)
            return further_specific_project_creation(tenantID, userID, sessionID)
    except Exception as e:
        print(traceback.format_exc())
        appLogger.error({
            "event": "create_projects_from_integrations_show_integrations",
            "tenant_id": tenantID, 
            "user_id": userID,
            "error":  e, 
            "traceback":traceback.format_exc()
        })
        return "Error showing integrations during project creation"

    ######################################################
    # After the user selects their integrations, we sync their possible sources to show in tiles.

    try:
        if not jira_sync_completed_by_tango_in_chat and integrations_selection_option_shown_to_user:
            yield "Tango is syncing information from your provided integrations. Please wait a moment... \n\n"
            synced = integration_sync(integrations, tenantID, userID, sessionID, 'TANGO_ONBOARDING_PROJECT')
            if synced: return synced
    except Exception as e:
        print(traceback.format_exc())
        appLogger.error({
            "event": "create_projects_from_integrations_sync_integrations",
            "tenant_id": tenantID, 
            "user_id": userID,
            "error":  e, 
            "traceback":traceback.format_exc()
        })
        return "Error syncing integrations during project creation"

    ######################################################
    # Confirm the sources the user wants to use for the project creation
    try:            
        if jira_sync_completed_by_tango_in_chat and not integrations_confirmed:
            source_names = []
            for integration in integrations:
                if integration.name == 'uploaded_files':
                    files = integration.fetchCurrentSessionUploadedFiles('TANGO_ONBOARDING_PROJECT')
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
"onboarding_project_source_confirmation": {json.dumps(source_names, indent=4)}"
}}
```
            """ 
            if len(source_names) == 0:
                TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_PROJECT_CANCEL', "", sessionID)
                return further_specific_project_creation(tenantID, userID, sessionID)
            return TangoYield(return_info=ret_val, yield_info=yield_after)
    except Exception as e:
        print(traceback.format_exc())
        appLogger.error({
            "event": "create_projects_from_integrations_confirm_sources",
            "tenant_id": tenantID, 
            "user_id": userID,
            "error":  e, 
            "traceback":traceback.format_exc()
        })
        return "Error confirming sources during project creation"

    ######################################################
    # If edge case of no sources provided by user, we cancel them and restart.
    try:    
        # Check if the only source is a single uploaded file that is xlsx or csv
        if (
            len(integration_source_list) == 1 and
            integration_source_list[0].get('integration') == 'uploaded_files' and
            integration_source_list[0].get('source_name', '').lower().endswith(('.xlsx', '.csv')) and
            not isolated_rows_checked
        ):
            isolated_rows_checked = True
            saved_integration_source_list = integration_source_list
            TangoDao.insertTangoState(tenantID, userID, 'ISOLATED_ROWS_PROJECT', json.dumps(integration_source_list), sessionID)  
            return "ASK THE USER: We noticed that you only provided a single excel or csv file as a source. Are your projects isolated by rows in this file?"
        elif len(integration_source_list) == 0:
            for integration in integrations:
                if integration.name == "uploaded_files":
                    files = integration.fetchCurrentSessionUploadedFiles("TANGO_ONBOARDING_PROJECT")
                    if not files:
                        return further_specific_project_creation(tenantID, userID, sessionID)
                    if files and not isolated_rows_checked:
                        isolated_rows_checked = True
                        saved_integration_source_list = integration_source_list
                        TangoDao.insertTangoState(tenantID, userID, 'ISOLATED_ROWS_PROJECT', json.dumps(integration_source_list), sessionID)  
                        return "ASK THE USER: We noticed that you only provided a single excel or csv file as a source. Are your projects isolated by rows in this file?"
    
    except Exception as e:
        print(traceback.format_exc())
        appLogger.error({
            "event": "create_projects_from_integrations_check_sources",
            "tenant_id": tenantID, 
            "user_id": userID,
            "error":  e, 
            "traceback":traceback.format_exc()
        })
        return "Error checking sources during project creation"
    
    if isolated_rows_checked:
        integration_source_list = saved_integration_source_list
    
    ######################################################
    # Generate the projects from the integrations
    try:
        if not integrationInfo:
            detailed_activity("onboarding::projects::confirmed_sources", f"User has confirmed the sources for project creation: {str(integration_source_list)}...", user_id=userID)
            yield "Tango is looking for the information you provided in the sources you mentioned. Please wait a moment... \n\n"
            gen = IntegrationRetriever(integration_source_list, integrations, 'project', llm, userID, tenantID, last_user_message, isolated_rows = isolated_rows).integrationInfo
            try:
                while True:
                    update = next(gen)
                    yield update 
            except StopIteration as e:
                integrationInfo = e.value
            TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_PROJECT_SOURCE_INFORMATION', json.dumps(integrationInfo), sessionID)
            detailed_activity("onboarding::projects::integration_info_retrieved", f"Integration information has been retrieved: {str(integrationInfo)[:30000]}...", user_id=userID)

        yield "Tango has compiled the information from your provided sources and is now generating projects... \n\n"
        projects = ProjectGenerator(llm, integrationInfo, clarifying_information, clarifying_count).generateProjects(userID)
        print(f"Generated projects: {projects}")
        if "clarifying_question" in projects:
            clarifying_question = projects["clarifying_question"].get_return_info()
            TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_PROJECT_CLARIFYING_QUESTION', clarifying_question, sessionID)
            return clarifying_question
        
    except Exception as e: 
        print(traceback.format_exc())
        appLogger.error({
            "event": "create_projects_from_integrations_init_ahub",
            "tenant_id": tenantID, 
            "user_id": userID,
            "error":  e, 
            "traceback":traceback.format_exc()
        })
        return "Error in generating projects"
    
    ######################################################
    # Process the projects and create using API
    try:
        print('Processing projects')
        gen = process_projects(projects, userID, tenantID, sessionID, llm)
        try:
            while True:
                yield next(gen)
        except StopIteration as e:
            exit_status = e.value
        project_names = [project.get('title', 'Unnamed project') for project in projects]
        detailed_activity("onboarding::projects::projects_generated", f"All Projects have been generated: {str(project_names)[:500]}...", user_id=userID)
        return exit_status
    except Exception as e:
        print(traceback.format_exc())
        appLogger.error({
            "event": "create_projects_from_integrations_process_projects",
            "tenant_id": tenantID, 
            "user_id": userID,
            "error":  e, 
            "traceback":traceback.format_exc()
        })
        return "Error with project creation API"


PROJECT_CREATION_FUNC = AgentFunction(
    name="specific_project_creation",
    description="""
    IF THE USER SAYS "I want to integrate information about my projects", CALL THIS FUNCTION.
    
    Anytime the user asks you to create a project or projects, or is in the flow of creating projects, call only this function. This creates projects from specifically mentioned integrations. 
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
                
                IMPORTANT: IF A SOURCE BEGINS WITH "UPLOADED DOCUMENT: ...", THEN IGNORE IT. DO NOT ASSIGN IT TO ANOTHER INTEGRATION LIKE DRIVE/OFFICE.
                DO NOT EVER MAKE ASSUMPTIONS ABOUT THE INTEGRATION SOURCE. IF THE USER SAYS "UPLOADED DOCUMENT: ...", THEN IT IS JUST AN UPLOADED DOCUMENT - IGNORE IT.
                FOR EXAMPLE: if you see "Selected Projects - Uploaded Document: Customer Context - XXXX - TREMERIC Copy 2.xlsx", you should ignore and leave an empty json.
               
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
                            "type": "str"
                        },
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
        {
            "name": "excel_or_csv_has_projects_on_each_row",
            "description": '''
            If Tango assistant has just ask the user whether or not the excel or csv file has projects on each row, and the user has answered, then set this to True or False.
            DO NOT EVER make this assumption yourself. If the user has not answered, then set this to False or don't provide it.
            ''',
            "type": "bool",
            "required": "false"
        }
    ],
    return_description="Confirmation of projects being created",
    function=specific_project_creation,
    return_type = "YIELD"
)


PROJECT_CREATION_CANCEL = AgentFunction(
    name="project_creation_cancel",
    description="""
    In the process of project creation, if the user says they want to cancel the project creation process, call this function.
    """,   
    args = [],
    return_description="Options of what the user can do next",
    function=project_creation_cancel,
)