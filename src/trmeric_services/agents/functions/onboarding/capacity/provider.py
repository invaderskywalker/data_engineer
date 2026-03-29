import gc
import json
import json
import traceback
import pandas as pd
from src.trmeric_s3.s3 import S3Service
from src.trmeric_services.agents.functions.onboarding.utils.capacity import (
    process_uploadedFiles, capacity_creation_looks_good_provider, capacity_show_table,save_to_db,
    further_specific_capacity_creation_provider,upload_resource_button,process_uploadedFiles_v2,skip_button
)
from src.trmeric_database.dao import TangoDao
from src.trmeric_api.logging.AppLogger import appLogger


def process_provider_capacity(
    tenantID, userID, sessionID, integrations, clarifying_information, 
    socketio, client_id, providerFilesInfo,saved_data,llm,model_opts,logInfo, **kwargs
):
    try:
        for integration in integrations:
            if integration.name == "uploaded_files":
                api = integration
                break
        provider_files = api.fetchCurrentSessionUploadedFiles('TANGO_ONBOARDING_CAPACITY_PROVIDER')

        if len(provider_files) == 0:
            for chunk in further_specific_capacity_creation_provider(tenantID,userID,sessionID,**kwargs): # No files found, handle this scenario in the main function
                yield chunk
            return
        
    except Exception as e:
        appLogger.error({
            "event": "files provider capacity",
            "error": e,
            "traceback": traceback.format_exc()
        })
        return None

    try:
        saved_data = f"Information about external providers started\n\n"
        last_uploaded_files_state_provider = providerFilesInfo
        print("--debug curr_files---", provider_files)
        
        
        provider_response = process_uploadedFiles_v2(
            curr_files=provider_files,
            prev_state=last_uploaded_files_state_provider,
            key="provider",
            user_message=clarifying_information,
            saved_data=saved_data,
            info_given=False,
            user_id=userID,
            tenant_id=tenantID,
            session_id=sessionID,
            llm = llm,model_opts = model_opts, logInfo=logInfo,
            **kwargs
        )
        print("\n\n--debug provider response----------------------", provider_response)
        
        if not provider_response:
            print("--debug error in provider response---")
            yield f"""I couldn’t find any useful information in the uploaded files. Please check the files and try again."""
            return 
        
        current_files_state = provider_response["structured_data"]
        looks_good = provider_response["looks_good"]
        is_unique_identifer = provider_response["unique_identifier"]
        missing_cols = provider_response["missing_cols"]
        missing_details = provider_response["missing_details"]
        available_details = provider_response["available_details"]


        df = current_files_state["current_state"]
        print("--debug after proceessing df", df)
        # numeric_cols = ["experience", "rate", "allocation"]
        appLogger.info({"event": "process_provider_files", "message" : "response_achieved", "data": df})

        
        if 'rate' in df.columns:
            df['rate'] = df['rate'].astype(str).replace(r'[^\d.]', '', regex=True)
            print("\n\n--debug after rate cleanup\n", df)

        df.fillna(0, inplace=True)
        curr_response = json.dumps(df.to_dict(orient="records"))
        
        if is_unique_identifer:
            yield f"""Thankyou for uploading the data, these are the processed values: {available_details}\n\n"""
            if len(missing_cols)>0:
                yield f"""These are the missing information, {missing_details}. It will be crucial for the resource planning engine to function well.\nWould you like to add these info?"""
                
            for chunk in capacity_show_table("provider", tenantID, userID, sessionID,data=curr_response, **kwargs):
                yield chunk
                
            yield upload_resource_button(key="TANGO_ONBOARDING_CAPACITY_PROVIDER")
                # yield skip_button(key = "provider")
        else:
            yield f"""No useful info is retrived from the uploaded doc, please review."""
        
        # socketio.emit("onboarding_resource_table", {"event": "onboarding_resource_table","key": "internal_employees","data": df.to_dict(orient="records")
        # }, room=client_id)

        TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_CAPACITY_SOURCE_INFORMATION_PROVIDER_TEMP', curr_response, sessionID)

        if looks_good:
            yield capacity_creation_looks_good_provider("provider",tenantID, userID, sessionID)
        else:
            yield f"I couldn’t find any details on these fields {missing_cols}"
            
        provider_data_db = save_to_db(
            key = "provider",
            structured_data=curr_response,
            user_id=userID,
            tenant_id=tenantID
        )
        del df
        del curr_response
        gc.collect()
        # print("\n--debug provider entries saved in db-------", provider_data_db)
        appLogger.info({"event": "process_internal_db", "message":  internal_data_db})

    except Exception as e:
        appLogger.error({
            "event": "process_provider_capacity",
            "error": str(e),
            "traceback": traceback.format_exc()
        })


    #     current_files_state1 = response1["structured_data"]
    #     looks_good1 = response1["looks_good"]
    #     missing_cols1 = response1["missing_cols"]

    #     df1 = current_files_state1["current_state"]
    #     numeric_cols1 = ["experience", "rate", "allocation"]

    #     for col in df1.columns:
    #         if col in numeric_cols1:
    #             df1[col] = df1[col].astype(str).replace("[^\d.]", "", regex=True)
    #             df1[col] = pd.to_numeric(df1[col], errors="coerce")

    #     df1.fillna(0, inplace=True)
    #     curr_response1 = json.dumps(df1.to_dict(orient="records"))

    #     yield capacity_show_table("provider", tenantID, userID, sessionID, **kwargs)
    #     socketio.sleep(seconds=2)
    #     socketio.emit("onboarding_resource_table", {
    #         "event": "onboarding_resource_table",
    #         "key": "provider_employees",
    #         "data": df1.to_dict(orient="records")
    #     }, room=client_id)

    #     TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_CAPACITY_SOURCE_INFORMATION_PROVIDER', curr_response1, sessionID)

    #     if looks_good1:
    #         yield capacity_creation_looks_good_provider(tenantID, userID, sessionID)
    #     else:
    #         yield f"I couldn’t find any details on these fields {missing_cols1}"

    # except Exception as e:
    #     appLogger.error({
    #         "event": "capacity_provider",
    #         "error": e,
    #         "traceback": traceback.format_exc()
    #     })
