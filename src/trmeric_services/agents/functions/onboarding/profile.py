from src.trmeric_services.agents.core import AgentFunction
from src.trmeric_services.integration.SpecifiedIntegrationRetriever.SpecifiedIntegrationRetreiver import SpecifiedIntegrationRetriever as IntegrationRetriever
from src.trmeric_services.agents.functions.onboarding.prompts.ProfilePrompt import ProfileGenerator
import traceback, json
from src.trmeric_database.Database import db_instance
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_database.dao import TangoDao
from src.trmeric_services.agents.functions.onboarding.utils.clarifying import clarifying_information_enhancement
from src.trmeric_services.agents.functions.onboarding.utils.profile import process_profiles, further_specific_profile_creation, profile_creation_cancel
from src.trmeric_services.journal.Activity import detailed_activity


def specific_profile_creation(tenantID: int, userID: int, llm, integrations, sessionID, user_write_company_info_in_chat = '', clarifying_information = '',  **kwargs):
    last_user_message = kwargs.get('last_user_message', None)
    last_tango_message = kwargs.get('last_tango_message', None)
    
    states = TangoDao.fetchTangoStatesForSessionId(sessionID)
    clarifying_count = 0
    clarifying_questions = []
    
    customer_profile_query =f"""
    SELECT * FROM customer_profile where tenant_id = {tenantID}
    """
    existing_profile = db_instance.retrieveSQLQueryOld(customer_profile_query)
    
    if len(existing_profile) > 0:
        print("--debug existing_profile", len(existing_profile))
        TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_PROFILE_FINISHED', '', sessionID)
        return "Profile has already been created for this customer. You can not create another profile."
    
    integrationInfo = None
    onboarding_sources_shown = False
    
    print("--debug in specific_profile_creation", last_user_message, clarifying_count, onboarding_sources_shown)
    for state in states:
        if state['key'] == 'ONBOARDING_PROFILE_SHOW_SOURCE':
            onboarding_sources_shown = True
        if state['key'] == 'ONBOARDING_PROFILE_CLARIFYING_QUESTION':
            clarifying_count += 1
            clarifying_questions.append(state['value'])
        if state['key'] == 'ONBOARDING_PROFILE_FINISHED':
            return "Profile has already been created in this onboarding session"
        if state['key'] == 'ONBOARDING_PROFILE_SOURCE_INFORMATION':
            integrationInfo = json.loads(state['value'])
        
    if not onboarding_sources_shown:
        print("--debug onboarding_sources_shown", onboarding_sources_shown)
        detailed_activity("onboarding::profile::show_sources", "The user has begun the profile onboarding process.", user_id=userID)
        return further_specific_profile_creation(tenantID, userID, sessionID)
    
    clarifying_information = clarifying_information_enhancement(clarifying_information, clarifying_questions, last_tango_message, last_user_message)
        
    integration_source_list = []
    info_given = False
    
    query = f"""
    select 
        org_info as org_info
    from 
        tenant_customer
    where 
        tenant_id = {tenantID}
    """
    org_info = db_instance.retrieveSQLQueryOld(query)[0].get("org_info")
    links = []
    if org_info:
        company_site = org_info.get("company_website")
        if company_site:
            links.append(company_site)
            detailed_activity("onboarding::profile::company_website", f"Company website provided: {company_site}", user_id=userID)
        other_sites = org_info.get("other_sites_to_refer")
        if other_sites:
            for site in other_sites:
                links.append(site)
    
    try:
        if not user_write_company_info_in_chat:
            for integration in integrations:
                if integration.name == "uploaded_files":
                    files = integration.fetchCurrentSessionUploadedFiles("TANGO_ONBOARDING_PROFILE")
                    if files:
                        info_given = True
                    if len(links) > 0:
                        info_given = True
                    if not info_given: 
                        return further_specific_profile_creation(tenantID, userID, sessionID)
        else:
            clarifying_information = user_write_company_info_in_chat + "\n" + str(clarifying_information)
    
    except Exception as e:
        print(traceback.format_exc())
        appLogger.error({
            "event": "create_profiles_from_integrations_fetch_files",
            "tenant_id": tenantID, 
            "user_id": userID,
            "error":  e, 
            "traceback":traceback.format_exc()
        })
        return "Error fetching uploaded files"
                                

    try:
        if not integrationInfo:
            detailed_activity("onboarding::profile::sources_confirmed", "User has confirmed sources for profile creation. Gathering company information from provided sources", user_id=userID)
            yield "Tango is looking for the information you provided in the sources you mentioned. Please wait a moment... \n\n"
            gen = IntegrationRetriever(integration_source_list, integrations, 'profile', llm, userID, tenantID, last_user_message).integrationInfo
            try:
                while True:
                    update = next(gen)
                    yield update 
            except StopIteration as e:
                integrationInfo = e.value
            TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_PROFILE_SOURCE_INFORMATION', json.dumps(integrationInfo), sessionID)
            detailed_activity("onboarding::profile::sources_processed", f"Profile sources processed: {list(integrationInfo.keys())[:5]}...", user_id=userID)

            yield "Tango has compiled the information from your provided sources and is now generating your profile... \n\n"
        profiles = ProfileGenerator(llm, integrationInfo, clarifying_information, clarifying_count).generateprofiles(userID)
        if "clarifying_question" in profiles:
            clarifying_question = profiles["clarifying_question"].get_return_info()
            TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_PROFILE_CLARIFYING_QUESTION', clarifying_question, sessionID)            
            return clarifying_question
        
    except Exception as e: 
        print(f"Error initializing action hub: {e}")
        print(traceback.format_exc())
        appLogger.error({
            "event": "create_profiles_from_integrations_init_ahub",
            "tenant_id": tenantID, 
            "user_id": userID,
            "error":  e, 
            "traceback":traceback.format_exc()
        })
        return "Error initializing action hub"
    
    try:
        gen = process_profiles(profiles, userID, tenantID, sessionID, llm)
        try:
            while True:
                yield next(gen)
        except StopIteration as e:
            exit_status = e.value
        
        # Extract organization name for activity logging
        profile_org_name = "Unknown"
        if profiles and len(profiles) > 0:
            org_details = profiles[0].get('organization_details', {})
            if isinstance(org_details, dict):
                profile_org_name = org_details.get('name', 'Unknown')
        
        detailed_activity("onboarding::profile::profile_generated", f"Customer profile generated successfully for organization: {profile_org_name}", user_id=userID)
        return exit_status
    except Exception as e:
        print(f"Error creating profiles: {e}")
        print(traceback.format_exc())
        appLogger.error({
            "event": "create_profiles_from_integrations_process_profiles",
            "tenant_id": tenantID, 
            "user_id": userID,
            "error":  e, 
            "traceback":traceback.format_exc()
        })
        return "Error creating profiles"
        

PROFILE_CREATION_FUNC = AgentFunction(
    name="specific_profile_creation",
    description="""
    IF THE USER SAYS "I want to create my company profile", CALL THIS FUNCTION.
    
    Anytime the user asks you to create a profile, or is in the flow of creating a profile, call only this function. This creates profiles from specifically mentioned integrations. 
    You don't need to call other functions to read from the integration sources as this one will do it for you. Even if the user has not listed integration sources yet, call this function with no integration arguments and we will prompt for those sources.
    
    Remember that if the user says no more questions or clarifying questions, this does not mean that you provide no arguments, but rather you note this as clarifying information.
    """,
    args=[
        {
            "name": "user_write_company_info_in_chat",
            "description": "If the user adds the company information in the chat, add that info into this string. Otherwise, set this to None.",
            "type": "str",
        },
        {
            "name": "clarifying_information",
            "description": '''
            In this case, if the user has provided necessary information, and you are running this process again, set this to True. Make sure you compile and keep all the user's clarifying information that they provided in the follow-up questions.
            
            This should be a string of the clarifying information provided. Be sure to look through all of the user's recent messages and feel free to include them completely. You don't need to be concise here and can include all the information the user has provided. 
            
            If a user says to keep some field empty or fill it to Tango's discretion, etc... you should include all of this info it in this string paragraph here.
                        
            If a user asks you to move on and create projects, or to ask no more clarifying questions, the also note this down here.   
            ''',
            "type": "str",
            "required": "true"
        },
    ],
    return_description="Confirmation of profiles being created",
    function=specific_profile_creation,
    return_type = "YIELD"
)

PROFILE_CREATION_CANCEL = AgentFunction(
    name="profile_creation_cancel",
    description="""
    In the process of profile creation, if the user says they want to cancel the profile creation process, call this function.
    """,   
    args = [],
    return_description="Options of what the user can do next",
    function=profile_creation_cancel,
)