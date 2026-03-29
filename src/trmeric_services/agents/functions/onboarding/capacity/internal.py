import re
import gc
import json
import traceback
import pandas as pd
from src.trmeric_s3.s3 import S3Service
from src.trmeric_database.dao import TangoDao
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.agents.functions.onboarding.utils.capacity import (
    process_uploadedFiles, capacity_creation_looks_good_internal, capacity_show_table,further_specific_capacity_creation_internal,
    upload_resource_button,save_to_db,process_uploadedFiles_v2, skip_button
)


def process_internal_capacity(
    tenantID, userID, sessionID, integrations, clarifying_information, 
    socketio, client_id, internalFilesInfo,saved_data,llm,model_opts, logInfo,uploaded_files, **kwargs
):
    print("--debug in process_internal_capacity---")
    try:
        for integration in integrations:
            if integration.name == "uploaded_files":
                api = integration
                break
        internal_files = api.fetchCurrentSessionUploadedFiles('TANGO_ONBOARDING_CAPACITY_INTERNAL')

        if len(internal_files) == 0:
            for chunk in further_specific_capacity_creation_internal(tenantID, userID, sessionID, socketio, client_id):
                # print("--debug chunk-------", chunk)
                yield chunk
            return
            # return further_specific_capacity_creation_internal(tenantID,userID,sessionID,**kwargs)  # No files found, handle this scenario in the main function
    except Exception as e:
        appLogger.error({
            "event": "files capacity",
            "error": e,
            "traceback": traceback.format_exc()
        })
        return None

    try:
        last_uploaded_files_state_internal = internalFilesInfo
        
        # print("--debug calling process_uploadedFiles---",last_uploaded_files_state_internal)
        # print("--debug curr_files---", internal_files)
        # for file_id, file_name in internal_files.items():
        #     print(f"File ID: {file_id}, File Name: {file_name}")
        #     uploaded_files[file_name] = S3Service().generate_presigned_url(file_id)
                        
        internal_response = process_uploadedFiles_v2(
            curr_files=internal_files,
            prev_state=last_uploaded_files_state_internal,
            key="internal",
            user_message=clarifying_information,
            info_given=False,
            user_id=userID,
            tenant_id=tenantID,
            session_id=sessionID,
            saved_data = saved_data,
            llm = llm,model_opts = model_opts, logInfo=logInfo,
            **kwargs
        )
        
        if not internal_response:
            print("--debug error in interanl response---")
            yield f"""I couldn’t find any useful information in the uploaded files. Please check the files and try again."""
            return 
        
        current_files_state = internal_response["structured_data"]
        looks_good = internal_response["looks_good"]
        is_unique_identifer = internal_response["unique_identifier"]
        missing_cols = internal_response["missing_cols"]
        missing_details = internal_response["missing_details"]
        available_details = internal_response["available_details"]


        df = current_files_state["current_state"]
        print("\n\n--debug after proceessing df\n", df)
        appLogger.info({"event": "process_internal_files", "message" : "response_achieved", "data": df})
        # numeric_cols = ["experience", "rate", "allocation"]

        # for col in df.columns:
        #     if col in numeric_cols:
        #         df[col] = df[col].astype(str).replace("[^\d.]", "", regex=True)
        #         df[col] = pd.to_numeric(df[col], errors="coerce")
        
        # Clean and convert 'rate' column
        #Also check here if 'rate' column is present in the df
        if 'rate' in df.columns:
            df['rate'] = df['rate'].astype(str).replace(r'[^\d.]', '', regex=True)
            print("\n\n--debug after rate cleanup\n", df)

        df.fillna(0, inplace=True)
        curr_response = json.dumps(df.to_dict(orient="records"))
        
        if is_unique_identifer:
            yield f"""Thankyou for uploading the data, these are the processed values: {available_details}\n\n"""
            if len(missing_cols)>0:
                yield f"""These are the missing information, {missing_details}. It will be crucial for the resource planning engine to function well. Would you like to add these info?\n\n"""
                
            for chunk in capacity_show_table("internal", tenantID, userID, sessionID,data=curr_response, **kwargs):
                yield chunk
                
            yield upload_resource_button(key="TANGO_ONBOARDING_CAPACITY_INTERNAL")
                # yield skip_button(key = "internal")
                
        else:
            yield f"""No useful info is retrived from the uploaded doc, please review."""
        socketio.sleep(seconds=1)
        
        # socketio.emit("onboarding_resource_table", {"event": "onboarding_resource_table","key": "internal_employees","data": df.to_dict(orient="records")
        # }, room=client_id)

        TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_CAPACITY_SOURCE_INFORMATION_INTERNAL_TEMP', curr_response, sessionID)

        if looks_good:
            yield capacity_creation_looks_good_internal("internal",tenantID, userID, sessionID)
        else:
            yield f"I couldn’t find any details on these fields {missing_cols}"
            
        internal_data_db = save_to_db(
            key = "internal",
            structured_data=curr_response,
            user_id=userID,
            tenant_id=tenantID
        )
        del df
        del curr_response
        gc.collect()
        appLogger.info({"event": "process_internal_db", "message":  internal_data_db})
        # print("\n--debug internal entries saved in db-------", internal_data_db)

    except Exception as e:
        appLogger.error({
            "event": "process_internal_capacity",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
