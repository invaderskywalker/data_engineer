import gc
import pandas as pd
import traceback, json
from src.trmeric_s3.s3 import S3Service
from src.trmeric_database.dao import TangoDao
from src.trmeric_utils.enums import AgentFnTypes
from src.trmeric_database.Database import db_instance
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.agents.core import AgentFunction
from src.trmeric_services.agents.core.agent_functions import AgentFunction, AgentReturnTypes
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_services.agents.functions.onboarding.transition import transition_text
from src.trmeric_services.agents.functions.onboarding.utils.clarifying import clarifying_information_enhancement
from src.trmeric_services.agents.functions.onboarding.utils.capacity import further_specific_capacity_creation_internal,further_specific_capacity_creation_provider, process_uploadedFiles, capacity_creation_looks_good_internal,capacity_creation_looks_good_provider,capacity_creation_cancel,save_to_db,capacity_show_table,upload_resource_button,go_to_projects_button
from src.trmeric_services.agents.functions.onboarding.capacity import process_internal_capacity,process_provider_capacity
from src.trmeric_services.agents.functions.onboarding.prompts.CapacityPrompt import capacity_onboarding_flow

def specific_capacity_creation( 
    tenantID: int, 
    userID: int,
    integrations,
    sessionID,
    clarifying_information='',
    llm= None,
    model_opts=None,
    socketio=None,
    client_id=None,
    logInfo=None,
    **kwargs
):
    
    internalFilesInfo = None
    providerFilesInfo = None
    internal_sources_shown = False
    provider_sources_shown = False
    
    internal_uploaded_files = {}
    provider_uploaded_files = {}
    
    all_info_given = False
    clarifying_count = 0
    clarifying_questions = []
    
    last_user_message = kwargs.get('last_user_message', None)
    last_tango_message = kwargs.get('last_tango_message', None)
    states = TangoDao.fetchTangoStatesForSessionId(sessionID)
    
    # capacity_internal_query = f"""SELECT * FROM capacity_resource where tenant_id = {tenantID}"""
    # capacity_provider_query = f"""SELECT * FROM capacity_external_providers where tenant_id = {tenantID}"""
    
    # existing_internal = db_instance.retrieveSQLQueryOld(capacity_internal_query)
    # existing_provider = db_instance.retrieveSQLQueryOld(capacity_provider_query)
    
    # if len(existing_internal)>0 and len(existing_provider)> 0:
    #     TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_CAPACITY_FINISHED', '', sessionID)
    #     return "The capacity planning process has already been completed for this customer."
    
    print("--debug in specific_capacity_creation---", clarifying_information, states)
    
    # Check if the metadata contains the key 'clarifying_information'
            

    for state in states:
        #upload resource button
        if state['key'] == 'ONBOARDING_CAPACITY_SHOW_SOURCE_INTERNAL':
            internal_sources_shown = True
        if state['key'] == 'ONBOARDING_CAPACITY_SHOW_SOURCE_PROVIDER':
            provider_sources_shown = True
            
        #state to store uploaded files   
        if state['key'] == 'ONBOARDING_CAPACITY_SOURCE_INFORMATION_INTERNAL':
            internalFilesInfo = json.loads(state['value'])
        if state['key'] == 'ONBOARDING_CAPACITY_SOURCE_INFORMATION_PROVIDER':
            providerFilesInfo = json.loads(state['value'])
            
        #state to trigger looks good button
        if state['key'] == 'ONBOARDING_CAPACITY_LOOKS_GOOD_INTERNAL':
            internal_show_looksGoodBtn = True
        if state['key'] == 'ONBOARDING_CAPACITY_LOOKS_GOOD_PROVIDER':
            provider_show_looksGoodBtn = True
            
        if state['key'] == 'ONBOARDING_CAPACITY_CLARIFYING_QUESTION':
            clarifying_count += 1
            clarifying_questions.append(state['value'])
        if state['key'] == 'ONBOARDING_CAPACITY_FINISHED':
            return "Capacity Planning has already been completed in this onboarding session"
        
    
    if last_user_message:
        TangoDao.insertTangoState(
            tenant_id=tenantID, 
            user_id=userID,
            key="capcity_onboarding_conv", 
            value=f"User: {last_user_message}", 
            session_id=sessionID
        )
        
    conv = TangoDao.fetchTangoStatesForSessionIdAndUserAndKeyAllValue(session_id=sessionID, user_id=userID, key="capcity_onboarding_conv")[::-1]
    # print("--debug conv", conv)
    prompt = capacity_onboarding_flow(conv)
    # print("--prompt\n", prompt.formatAsString())
    response = llm.run(prompt, model_opts , 'agent::value_realization', logInfo)
    # print("--response\n", response)
    response = extract_json_after_llm(response)
    print("--response json \n", response)
    flow_stage = response.get("flow_stage", "") or ""


    # if not internal_sources_shown:
    #     print("--debug internal_sources_shown", internal_sources_shown)
    #     for chunk in further_specific_capacity_creation_internal(tenantID, userID, sessionID, socketio, client_id):
    #         print("--debug chunk-------", chunk)
    #         yield chunk
    # clarifying_information = clarifying_information_enhancement(clarifying_information, 
    #             clarifying_questions, last_tango_message, last_user_message)
    res = ""
    try:
        saved_data = f"Information about company employees started: {all_info_given}\n\n"
        if flow_stage == "internal_team":
            #Flow1: Internal Employees
            print("--debug starting internal flow----")
            appLogger.info({"event": "internal_flow","data": response})
            
            for chunk in process_internal_capacity(tenantID, userID, sessionID, integrations, clarifying_information, 
                socketio, client_id, internalFilesInfo,saved_data,llm,model_opts,logInfo,uploaded_files = internal_uploaded_files, **kwargs):
                res += chunk
                yield chunk
                
            # print("--debug internal uploaded files: ", internal_uploaded_files)
        elif flow_stage == "provider":
            curr_response = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(sessionID, userID, 'ONBOARDING_CAPACITY_SOURCE_INFORMATION_INTERNAL_TEMP')
            if len(curr_response)>0:
                curr_response = curr_response[0]['value']
                TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_CAPACITY_SOURCE_INFORMATION_INTERNAL', curr_response, sessionID)
                
            print("--debug starting provider flow----")
            appLogger.info({"event": "provider_flow","data": response})
            for chunk in process_provider_capacity(tenantID, userID, sessionID, integrations, clarifying_information, 
                socketio, client_id, providerFilesInfo,saved_data,llm,model_opts,logInfo,uploaded_files = provider_uploaded_files, **kwargs):
                res += chunk
                yield chunk
          
    except Exception as e:
        print("--debug error in processcapacity files", traceback.format_exc())
        appLogger.error({
            "event": "process_capacity",
            "error": e,
            "traceback": traceback.format_exc()
        })
        
    TangoDao.insertTangoState(
        tenant_id=tenantID, 
        user_id=userID,
        key="capcity_onboarding_conv", 
        value=f"Onboarding Capacity Agent: {str(response)} \n\n Next step process: {res}", 
        session_id=sessionID
    )
    

    if flow_stage =="completed":
        
        curr_response = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(sessionID, userID, 'ONBOARDING_CAPACITY_SOURCE_INFORMATION_PROVIDER_TEMP')
        if len(curr_response)>0:
            curr_response = curr_response[0]['value']
            TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_CAPACITY_SOURCE_INFORMATION_PROVIDER', curr_response, sessionID)
        
        yield f"""Alright! That concludes the onboarding process for capacity planner.
                Please review the same, and if you spot minor inaccuracies, inform trmeric customer support.
                If you have any further questions, please feel free to ask!
        """ 
        TangoDao.insertTangoState(tenantID,userID,"ONBOARDING_CAPACITY_FINISHED","capacityPlanner done",sessionID)
        appLogger.info({"event": "flow_completed", "data": response})
        return transition_text(sessionID, **kwargs)
        #show go to projects btn: later!!
        # yield go_to_projects_button(key = '')
        # return

################################################################################################################################


CAPACITY_CREATION_FUNC = AgentFunction(
    name="specific_capacity_creation",
    description="""
    CALL THIS FUNCTION in the following scenarios related to capacity planning or resource allocation for the user's team:

    1. If the user says, "I want to upload team resource data for capacity planning."
    2. Anytime the user requests capacity planning or resource allocation for their team during onboarding, including but not limited to:
       - Internal flow (e.g., "I need to plan capacity for my internal team").
       - Provider flow (e.g., "I want to allocate resources for my provider team").
       - Completing the capacity planning process (e.g., "I’m finishing up the capacity planning for my team").
    3. If the user asks for assistance with capacity planning or resource allocation at any stage, even if they haven’t specified integration sources.

    Do not call other functions to read from integration sources, as this function will handle that automatically. If the user has not yet listed integration sources, invoke this function without integration arguments, and the system will prompt for the necessary sources (internal and provider datasets) as needed.
    """,
    args=[
        {
            "name": "clarifying_information",
            "description": """
            Any additional clarifications provided by the user during the onboarding process.
            
            This field should capture:
            - Whether the user wants to add resources later instead of now.
            - Any instructions related to the document (e.g., "Ignore missing data" or "Only use the first sheet").
            - Notes about preferences for capacity planning.
            
            If a user says to keep some field empty or fill it to the system's discretion, include this information.
            
            If no clarifications were given, set this to `None`.
            """,
            "type": "str",
            "required": "true"
        },
    ],
    return_description="Confirmation that the resource document has been uploaded and processed.",
    function=specific_capacity_creation,
    return_type=AgentReturnTypes.YIELD.name,
    type_of_func=AgentFnTypes.SKIP_FINAL_ANSWER.name
)

PROVIDER_CAPACITY_CREATION_FUNC = AgentFunction(
    name="provider_specific_capacity_creation",
    description="""
        IF THE USER SAYS "I want to upload team resource data for capacity planning" OR SIMILAR REQUESTS LIKE "Help me with capacity planning" OR "Allocate resources for my team," CALL THIS FUNCTION.

        This function is designed to assist users during the onboarding process for capacity planning and resource allocation by guiding them through two key workflows: the Internal Flow and the Provider Flow.

        ---

        ### **Internal Flow: Uploading and Processing Team Resource Data**
        1. **When to Trigger**:
        - If the user expresses a need for capacity planning or resource allocation for their team (e.g., "I want to plan my team's capacity" or "Upload data for resource allocation").
        
        2. **What Happens**:
        - **Prompt for Upload**: The user will be asked to upload an **Internal Team File** containing details about their team’s resources

        ---

        ### **Provider Flow: Adding External Resource Data**
        1. **When to Trigger**:
        - After the Internal Team File is processed and the user chooses to proceed (e.g., "Looks good, let’s add provider data" or "Continue with capacity planning").

        2. **What Happens**:
        - **Prompt for Provider File**: The user is asked to upload a **Provider Team File** with details about external resources (e.g., contractors, vendors).
        - **File Requirements**: In addition to the Internal Flow columns, this file must include:
            - `Provider Name`: Name of the external provider or company (e.g., "TechCorp").
        - **Purpose**: Combines internal and provider data for a comprehensive capacity plan.
        
        Call this function whenever the user initiates capacity planning or resource allocation during onboarding to ensure a smooth and structured experience.
        """,
    args=[
        {
            "name": "clarifying_information",
            "description": """
            Any additional clarifications provided by the user during the onboarding process.
            
            This field should capture:
            - Whether the user wants to add resources later instead of now.
            - Any instructions related to the document (e.g., "Ignore missing data" or "Only use the first sheet").
            - Notes about preferences for capacity planning.
            
            If a user says to keep some field empty or fill it to the system's discretion, include this information.
            
            If no clarifications were given, set this to `None`.
            """,
            "type": "str",
            "required": "true"
        },
    ],
    return_description="Confirmation that the resource document has been uploaded and processed.",
    function=specific_capacity_creation,
    return_type=AgentReturnTypes.YIELD.name,
    type_of_func=AgentFnTypes.SKIP_FINAL_ANSWER.name
)


FINISH_CAPACITY_CREATION_FUNC = AgentFunction(
    name="finish_specific_capacity_creation",
    description="""
        IF THE USER SAYS that I’m completing the capacity planning process (e.g., "I’m finishing up the capacity planning for my team").
        Call this function whenever the user finishes capacity planning or resource allocation during onboarding to ensure a smooth and structured experience.
        """,
    args=[
        {
            "name": "clarifying_information",
            "description": """
            Any additional clarifications provided by the user during the onboarding process.
            
            This field should capture:
            - Notes about preferences for capacity planning.
            If a user says to keep some field empty or fill it to the system's discretion, include this information.
            If no clarifications were given, set this to `None`.
            """,
            "type": "str",
            "required": "true"
        },
    ],
    return_description="Confirmation that the resource document has been uploaded and processed.",
    function=specific_capacity_creation,
    return_type=AgentReturnTypes.YIELD.name,
    type_of_func=AgentFnTypes.SKIP_FINAL_ANSWER.name
)




CAPACITY_CREATION_CANCEL = AgentFunction(
    name="cancel_capacity_creation",
    description="""
    IF THE USER SAYS "I want to cancel capacity planning" OR "Stop the resource upload process", CALL THIS FUNCTION.
    
    This function allows the user to exit the capacity planning process before completion if he has skipped the process of internal or provider resource data upload.
    It will also cancel the process if the user has already uploaded the files and wants to stop the process.
    """,
    args=[],
    return_description="Confirmation that the capacity planning process has been canceled.",
    function=capacity_creation_cancel,
    return_type=AgentReturnTypes.YIELD.name,
    type_of_func=AgentFnTypes.SKIP_FINAL_ANSWER.name
)



def capacity_uploaded_files_url(integrations=None,metadata=None,socketio=None,client_id=None,**kwargs):
    
    internal_uploaded_files = {}
    provider_uploaded_files = {}
    
    # metadata = metadata or {}
    print("--debug metadata", metadata)
    
    try:
        for integration in integrations:
                if integration.name == "uploaded_files":
                    api = integration
                    break
                
        internal_files = api.fetchCurrentSessionUploadedFiles('TANGO_ONBOARDING_CAPACITY_INTERNAL')
        provider_files = api.fetchCurrentSessionUploadedFiles('TANGO_ONBOARDING_CAPACITY_PROVIDER')
        print("--debug uploaded files ",internal_files, '\n',provider_files )
        
        if internal_files:
            for file_id, file_name in internal_files.items():
                    print(f"File ID: {file_id}, File Name: {file_name}")
                    internal_uploaded_files[file_name] = S3Service().generate_presigned_url(file_id)
        
        print("--debug internal uploaded files: ", internal_uploaded_files)
        
        if provider_files:
            for file_id, file_name in provider_files.items():
                    print(f"File ID: {file_id}, File Name: {file_name}")
                    provider_uploaded_files[file_name] = S3Service().generate_presigned_url(file_id)
                    
        print("--debug provider uploaded files: ", provider_uploaded_files)
        if metadata:
            key = metadata.get('key','')
            if key == "show_internal_employees":
                socketio.emit("tango_onboarding_view", {"key": "internal_employees","data": internal_uploaded_files}, room=client_id)
            elif key == "show_provider_employees":
                socketio.emit("tango_onboarding_view", {"key": "provider_employees","data": provider_uploaded_files}, room=client_id)
                
        appLogger.info({"event": "view_resource_file", "metadata": metadata,"internal": internal_uploaded_files,"provider": provider_uploaded_files})
        return

    except Exception as e:
        print("--debug error in fetching files", e)
        appLogger.error({"event": "files capacity","error": e,"traceback": traceback.format_exc()})


CAPACITY_FILE_UPLOAD = AgentFunction(
    name="capacity_uploaded_files_url",
    description="""This function retrieves the URLs of uploaded files related to onboarding.""",
    args=[],
    return_description="",
    function=capacity_uploaded_files_url,
    type_of_func=AgentFnTypes.ACTION_TAKER.name
)




# try:
        # process_provider_capacity(
        #     tenantID, userID, sessionID, integrations, clarifying_information, 
        #     socketio, client_id, team_resource_document_uploaded, providerFilesInfo, **kwargs
        
        # )
                # except Exception as e:
                #     print("--debug error in process_provider_capacity",traceback.format_exc())
                #     appLogger.error({
                #         "event": "process_provider_capacity",
                #         "error": e,
                #         "traceback": traceback.format_exc()
                #     })
                
                # # # trigger_provider_flow = False
                # # if not internal_show_looksGoodBtn:
                # #     try:        
                # #         for integration in integrations:
                # #             print (integration.name)
                # #             if integration.name == "uploaded_files":
                # #                 api = integration
                # #                 break
                            
                # #         internal_files = api.fetchCurrentSessionUploadedFiles('TANGO_ONBOARDING_CAPACITY_INTERNAL')
                # #         # print("--debug fetched internalfiles: ",internal_files)
                        
                # #         if len(internal_files) == 0:
                # #             return further_specific_capacity_creation_internal(tenantID, userID, sessionID)
                # #     except Exception as e:
                # #         print("--debug error in fetching files", e)
                # #         appLogger.error({
                # #             "event": "files capacity",
                # #             "error": e,
                # #             "traceback": traceback.format_exc()
                # #         })
                        

                # #     try:
                # #         saved_data = f"Information about company employees started: {all_info_given}\n\n"
                            
                # #         #this state will store the last state of uploaded files (data fetched)
                # #         last_uploaded_files_state_internal = internalFilesInfo        
                # #         # print("--debug last_uploaded_files_state: ",last_uploaded_files_state_internal)
                        
                # #         internal_response = process_uploadedFiles(
                # #             curr_files=internal_files,
                # #             prev_state=last_uploaded_files_state_internal,
                # #             key = "internal",
                # #             user_message=clarifying_information,
                # #             saved_data=saved_data,
                # #             info_given=all_info_given,
                # #             user_id=userID,
                # #             tenant_id=tenantID,
                # #             session_id=sessionID,
                # #             llm=llm,
                # #             model_opts=model_opts,
                # #             logInfo=logInfo
                # #         )

                # #         print("--debug response internal", internal_response)
                # #         current_files_state = internal_response["structured_data"]
                # #         looks_good = internal_response["looks_good"]
                # #         missing_cols = internal_response["missing_cols"]
                        
                        
                # #         df = current_files_state["current_state"]  # Extract DataFrame
                # #         numeric_cols = ["experience", "rate", "allocation"]  

                # #         if df is None:
                # #             appLogger.info({"event": "curr_df","info":{df}, "traceback": traceback.format_exc()})
                # #             yield f"No information present in the uploaded file!"
                # #             return
                        
                # #         for col in df.columns:
                # #             if col in numeric_cols:
                                
                # #                 df[col] = df[col].astype(str).replace("[^\d.]", "", regex=True)  
                # #                 df[col] = pd.to_numeric(df[col], errors="coerce")  

                # #         df.fillna(0, inplace=True)
                # #         curr_response = json.dumps(df.to_dict(orient="records"))
                # #         # print("--debug curr_response", curr_response)

                # #         for chunk in capacity_show_table("internal",tenantID,userID,sessionID, data=curr_response,**kwargs):
                # #             yield chunk
                            
                # #         # socketio.sleep(seconds = 1)       
                # #         print("--debug looks good internal", looks_good)
                # #         #store curr_internal files in db
                # #         TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_CAPACITY_SOURCE_INFORMATION_INTERNAL',curr_response,sessionID)
                    
                        
                        
                # #         if looks_good:
                # #             print("--debug shi chlrha??????????????????????????????????")
                # #             for chunk in capacity_creation_looks_good_internal("internal", tenantID, userID, sessionID):
                # #                 yield chunk
                                
                # #             print("--debug chlgya looks good--------", looks_good)
                # #             internal_data_db = save_to_db(
                # #                 key = "internal",
                # #                 structured_data=curr_response,
                # #                 user_id=userID,
                # #                 tenant_id=tenantID
                # #             )
                # #             del df
                # #             del curr_response
                # #             gc.collect()
                # #             print("--debug internal_db", internal_data_db)
                # #         else:
                # #             yield f"I couldn’t find any details on these fields {missing_cols}"
                # #             #show button again
                # #             yield upload_resource_button(key="TANGO_ONBOARDING_CAPACITY_INTERNAL")
                        

                #     except Exception as e:
                #         print("--debug error in onboarding capacity planner--")
                #         appLogger.error({
                #             "event": "process_uploaded_cp_files",
                #             "error": e,
                #             "traceback": traceback.format_exc()
                #         })


                #Flow2: Providers
                # print("--debug starting provider flow----",' ', internal_show_looksGoodBtn,internal_sources_shown)
                
                # #if internal has uploaded files and it looks good, proceed for provider!
                # if internal_show_looksGoodBtn and internal_sources_shown:
                    
                #     if not provider_sources_shown:
                #         print("--debug provider_sources_shown", provider_sources_shown)
                #         for chunk in further_specific_capacity_creation_provider(tenantID, userID, sessionID):
                #             yield chunk
                #         return
                    
                #     clarifying_information = clarifying_information_enhancement(clarifying_information, 
                #                 clarifying_questions, last_tango_message, last_user_message)
                
                    
                #     if not provider_show_looksGoodBtn:
                #         try:        
                #             for integration in integrations:
                #                 print (integration.name)
                #                 if integration.name == "uploaded_files":
                #                     api = integration
                #                     break
                                
                #             provider_files = api.fetchCurrentSessionUploadedFiles('TANGO_ONBOARDING_CAPACITY_PROVIDER')
                #             # print("--debug fetched providerfiles: ",provider_files)
                            
                #             if len(provider_files) == 0:
                #                 return further_specific_capacity_creation_provider(tenantID, userID, sessionID)
                #         except Exception as e:
                #             print("--debug error in fetching provider files", e)
                #             appLogger.error({
                #                 "event": "files provider capacity",
                #                 "error": e,
                #                 "traceback": traceback.format_exc()
                #             })
                            
                            
                #         try:
                #             saved_data = f"Information about company employees started: {all_info_given}\n\n"
                #             last_uploaded_files_state_provider = providerFilesInfo
                #             # print("--debug last_uploaded_files_state provider: ",last_uploaded_files_state_provider)
                            
                #             response1 = process_uploadedFiles(
                #                 curr_files=provider_files,
                #                 prev_state=last_uploaded_files_state_provider,
                #                 key = "provider",
                #                 user_message=clarifying_information,
                #                 saved_data=saved_data,
                #                 info_given=all_info_given,
                #                 user_id=userID,
                #                 tenant_id=tenantID,
                #                 session_id=sessionID,
                #                 llm=llm,
                #                 model_opts=model_opts,
                #                 logInfo=logInfo
                #             )

                #             print("--debug provider response", response1)
                #             current_files_state1 = response1["structured_data"]
                #             looks_good1 = response1["looks_good"]
                #             missing_cols1 = response1["missing_cols"]
                            
                #             df1 = current_files_state1["current_state"]  
                #             numeric_cols1 = ["experience", "rate", "allocation"]  

                #             for col in df1.columns:
                #                 if col in numeric_cols1:
                                    
                #                     df1[col] = df1[col].astype(str).replace("[^\d.]", "", regex=True)  
                #                     df1[col] = pd.to_numeric(df1[col], errors="coerce")  

                #             df1.fillna(0, inplace=True)
                #             curr_response1 = json.dumps(df1.to_dict(orient="records"))

                #             for chunk in  capacity_show_table("provider",tenantID,userID,sessionID, data=curr_response1,**kwargs):
                #                 yield chunk
                #             # yield "provider data"
                            

                #             # Store provider files in db
                #             TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_CAPACITY_SOURCE_INFORMATION_PROVIDER',curr_response1,sessionID)
                
                #             if looks_good1:
                #                 for chunk in capacity_creation_looks_good_provider("provider",tenantID, userID, sessionID):
                #                     yield chunk
                                    
                #                 provider_data_db = save_to_db(
                #                     key = "provider",
                #                     structured_data=curr_response1,
                #                     user_id=userID,
                #                     tenant_id=tenantID
                #                 )
                #                 print("--debug provider_db", provider_data_db)
                #                 del df1
                #                 del curr_response1
                #                 gc.collect()
                                
                #             else:
                #                 yield f"I couldn’t find any details on these fields {missing_cols1}"
                #                 #show button again
                #                 yield upload_resource_button(key="TANGO_ONBOARDING_CAPACITY_PROVIDER")
                    
                #         except Exception as e:
                #             print("--debug error in providerflow", traceback.format_exc())
                #             appLogger.error({"event": "capacity_provider", "error":e, "traceback": traceback.format_exc()})


                # if internal_show_looksGoodBtn and provider_show_looksGoodBtn:
                #     all_info_given = True
                #     TangoDao.insertTangoState(tenantID,userID,"ONBOARDING_CAPACITY_FINISHED","capacityPlanner done",sessionID)
                #     yield f""""Alright! That concludes the onboarding process for capacity planner. 
                #         Please review the same, and if you spot minor inaccuaries, inform trmeric customer support"""

                #     #show go to projects btn: later!!
                #     # yield go_to_projects_button(key = '')
                #     return

