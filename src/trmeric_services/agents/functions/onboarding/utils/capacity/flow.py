import pandas as pd
import traceback, json
from src.trmeric_s3.s3 import S3Service
from src.trmeric_database.dao import TangoDao
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_database.models.project import CapacityResource
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_services.agents.functions.onboarding.transition import transition_text
from src.trmeric_services.agents.functions.utility import emit_event
from src.trmeric_services.agents.functions.onboarding.prompts.CapacityPrompt import columnsPrompt,categorizeFilesPrompt,create_categorization_prompt,create_categorization_prompt_v2
from src.trmeric_services.agents.functions.onboarding.utils.capacity import clean_dataframe


def upload_resource_button(key: str):
    upload_dict = {
        "onboarding_add_capacity": [
            {
                "label": "Upload Resources",
                "key": key
            },
            {
                "label": "Skip",
                "key": key
            }
        ]
    }
    upload_json = f"""\n```json\n{json.dumps(upload_dict, indent=4)}\n```"""
    return upload_json


def skip_button(key: str):
    skip_dict = {
        "onboarding_add_capacity": [
            {
                "label": "Skip",
                "key": key
            }
        ]
    }
    skip_json = f"""```json\n{json.dumps(skip_dict, indent=4)}\n```"""
    return skip_json

def go_to_projects_button(key: str):
    upload_dict = {
        "onboarding_add_capacity": [
            {
                "label": "Go to Projects",
                "key": "onboarding_capacity_finished"
            }
        ]
    }
    upload_json = f"```json\n{json.dumps(upload_dict, indent=4)}\n```"
    return upload_json

    


def further_specific_capacity_creation_internal(tenantID, userID, sessionID, socketio=None,client_id=None, **kwargs):
    print("--debug in further_specific_capacity_creation_internal")
    TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_CAPACITY_SHOW_SOURCE_INTERNAL', "", sessionID)
    ret_val =  f"""Let's get started with the Capacity planning process.
            Would you like to add team resources? Click upload resources and you can get synthesized capacity planner 
            during the project creation or You can add them while creating the project.
    """    
    # yield_after = upload_resource_button(key = "TANGO_ONBOARDING_CAPACITY_INTERNAL")
    yield_after = """
```json
{
    "onboarding_add_capacity": [
        {
            "label": "Upload Resources",
            "key": "TANGO_ONBOARDING_CAPACITY_INTERNAL"
        }
    ]
}
```
    """ 
    yield ret_val
    yield yield_after
   
    # socketio.emit("tango_chat_onboarding", yile) 
    # return f"{ret_val}\n\n{yield_after}" 
    # return TangoYield(return_info=ret_val, yield_info=yield_after,yield_now = '') 

def further_specific_capacity_creation_provider(tenantID, userID, sessionID, **kwargs):
    
    TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_CAPACITY_SHOW_SOURCE_PROVIDER', "", sessionID)
    ret_val =  f"""Are there any external providers? Click upload resources and you can get synthesized capacity planner during the 
                project creation or You can add them while creating the project
    """  
    # yield_after = upload_resource_button(key = "TANGO_ONBOARDING_CAPACITY_PROVIDER")  
    yield_after = """
```json
{
    "onboarding_add_capacity": [
        {
            "label": "Upload Resources",
            "key": "TANGO_ONBOARDING_CAPACITY_PROVIDER"
        }
    ]
}
```
    """
    yield ret_val
    yield yield_after
    # return f"{ret_val}\n\n{yield_after}" 
    # return TangoYield(return_info=ret_val, yield_info=yield_after,yield_now = '') 



def capacity_show_table(key, tenantID, userID, sessionID, data, **kwargs):
    
    ret_val =  f"""Here are the data I found in the file that you had uploaded."""   
    if key == "internal" :
        # yield_after = view_resource_button(key = "show_internal_employees",data=data)
        yield_after = f"""
```json
{{
    "onboarding_show_table": [
        {{
            "label": "View Resources",
            "key": "show_internal_employees",
            "data": {data}
        }}
    ]
}}
```
    """    
    elif key == "provider": 
        # yield_after = view_resource_button(key = "show_provider_employees",data=data)
        yield_after = f"""
```json
{{
    "onboarding_show_table": [
        {{
            "label": "View Resources",
            "key": "show_provider_employees",
            "data": {data}
        }}
    ]
}}
```
    """   
    yield ret_val
    yield yield_after
    # return TangoYield(return_info=ret_val, yield_info=yield_after,yield_now = '')     
    # return f"{ret_val}\n\n{yield_after}"

def capacity_creation_looks_good_internal(key,tenantID, userID, sessionID, **kwargs):
    TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_CAPACITY_LOOKS_GOOD_INTERNAL', True, sessionID)
    
    # ret_val = f"Looks Good!"
    yield_after = f"""
```json
{{
    "capacity_looks_good": [
        {{
            "label": "Looks Good {key}!",
            "key": "ONBOARDING_CAPACITY_LOOKS_GOOD_INTERNAL"
        }}
    ]
}}
```
    """
   
    yield yield_after
    
    
def capacity_creation_looks_good_provider(key,tenantID, userID, sessionID, **kwargs):
    TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_CAPACITY_LOOKS_GOOD_PROVIDER', True, sessionID)
    
    # ret_val = f"Looks Good!"
    yield_after = f"""
```json
{{
    "capacity_looks_good": [
        {{
            "label": "Looks Good {key}!",
            "key": "ONBOARDING_CAPACITY_LOOKS_GOOD_PROVIDER"
        }}
    ]
}}
```
    """
   
    yield yield_after

def capacity_creation_cancel(tenantID, userID, sessionID, **kwargs):
    TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_CAPACITY_CANCEL', "", sessionID)
    return transition_text(sessionID)
     
   

def categorize_columns(df, llm, user_message, required_columns, model_opts, logInfo):
    """
    Uses LLM to understand column meanings and map them to required fields.
    """
    try:
        print("--debug user msg", user_message)
        
        instruction = f"Here is a sample of the uploaded dataframe:\n{df.head(3).to_markdown(index=False)}\n"
        if user_message:
            instruction += f"\nUser Message: {user_message}\n"
        
        prompt = columnsPrompt(instruction, required_columns, df)
        response = llm.run(prompt, model_opts, 'agent::onboarding_capacity::categorize_columns', logInfo)
        print("--debug response", response)

        mapped_columns = extract_json_after_llm(response)
        print("--debug mapped_columns", mapped_columns)
        # required_mapped = all(col in mapped_columns["mapped_columns"].values() for col in required_columns)
        # if not required_mapped:
        #     print("LLM failed to map all required columns.")
        # df.rename(columns=mapped_columns["mapped_columns"], inplace=True)
        
        # Check if the required columns are present in the mapped output
        mapped_cols_set = set(mapped_columns.get("mapped_columns", {}).values())
        required_cols_set = set(required_columns)

        if not required_cols_set.issubset(mapped_cols_set):
            missing_mapped_cols = required_cols_set - mapped_cols_set
            print(f"LLM failed to map all required columns. Missing mappings: {', '.join(missing_mapped_cols)}")

        return df.rename(columns=mapped_columns["mapped_columns"])
    
    except Exception as e:
        error_msg = traceback.format_exc()
        print(f"Error in categorize_columns: {e}\n{error_msg}")
        appLogger.error({
            "event": "categorize_columns_error",
            "error": str(e),
            "traceback": error_msg
        })
        return df  # Return original DataFrame if an error occurs

def check_missing_fields(df, required_columns):
    """
    Identify missing required fields in the DataFrame.
    Returns a tuple (trigger_looks_good, missing_fields_message)
    """
    if df is not None:
        missing_fields = [col for col in required_columns if col not in df.columns]

        if missing_fields:
            print("--debug missing_fields", missing_fields, '\n')
            return False, f"Missing data: {', '.join(missing_fields)}. Please provide the required fields."
    
    return True, None  
    #  if missing_fields:
    #         print("--debug missing_fields", missing_fields, '\n')
    #         trigger_looks_good = True
    #         ret_val = f"Missing data : {', '.join(missing_fields)}. Please provide the required fields."
    #         return TangoYield(return_info=ret_val, yield_info=f"missing data: {missing_fields}")


def extract_all_df(files, all_sheets, saved_data):
    """
    Extract data from all given files and update all_sheets.
    """
    try:
        for file_id, file_name in files.items():
            saved_data += f"Processing file: {file_name}:\n"
            print("--debug file_id , name", file_id , ' ', file_name,)

            df_dict = S3Service().download_file_as_pd(file_id)
            # df_dict = S3Service().download(key=file_id)
            print("--debug file as pd: ",df_dict)
            if not df_dict:
                saved_data += f"Failed to download file: {file_name}\n"
                continue 

            for sheet_name, sheet_df in df_dict.items():
                if sheet_df is None or sheet_df.empty:
                    saved_data += f"Skipping empty sheet: {sheet_name} in {file_name}\n"
                    continue  # Skip empty sheets
                
                if sheet_name not in all_sheets:
                    all_sheets[sheet_name] = []  # Initialize list if not present
                all_sheets[sheet_name].append(sheet_df)

            saved_data += f"File {file_name} processed successfully.\n"
            print("--debug saved df", saved_data)
        return saved_data
    except Exception as e:
        appLogger.error({"event":"extract_df","error": str(e),"traceback": traceback.format_exc()})
        return saved_data  


def extract_all_df_v2(files, all_sheets, saved_data):
    try:
        if isinstance(files, dict):
            file_items = files.items()
        else:
            file_items = [(f.file_id, f.file_name) for f in files]  # Adjust if structure differs

        for file_id, file_name in file_items:
            saved_data += f"Processing file: {file_name}:\n"
            print(f"--debug processing file: {file_name}, file_id: {file_id}")

            df_dict = S3Service().download_file_as_pd_v2(file_id)
            if not df_dict:
                saved_data += f"Failed to download or process file: {file_name}\n"
                print(f"--debug failed to process file: {file_name}")
                continue

            for sheet_name, sheet_df in df_dict.items():
                if sheet_df is None or sheet_df.empty:
                    saved_data += f"Skipping empty sheet: {sheet_name} in {file_name}\n"
                    print(f"--debug empty sheet: {sheet_name} in {file_name}")
                    continue
                
                if sheet_name not in all_sheets:
                    all_sheets[sheet_name] = []
                all_sheets[sheet_name].append(sheet_df)
                saved_data += f"Processed sheet: {sheet_name} in {file_name}\n"
                print(f"--debug added sheet: {sheet_name}, rows: {len(sheet_df)}")

        print(f"--debug all_sheets after processing: {list(all_sheets.keys())}")
        return saved_data
    except Exception as e:
        appLogger.error({"event": "extract_df", "error": str(e), "traceback": traceback.format_exc()})
        saved_data += f"Error extracting data: {str(e)}\n"
        return saved_data
    
    

def process_uploadedFiles_v2(
    curr_files, prev_state, key, user_message, info_given, user_id, tenant_id, session_id, 
    saved_data, llm, model_opts, logInfo, **kwargs
):
    # Define required columns and unique identifiers
    if key == "internal":
        required_columns = ["employee_id", "name", "role", "skill", "allocation", "rate", "experience", "projects"]
        unique_identifiers = ["employee_id", "name"]
        target_mapping = {
            "employeeid": "employee_id",
            "employeename": "name",
            "role": "role",
            "skills": "skill",
            "allocation": "allocation",
            "rate": "rate",
            "experience": "experience",
            "projects": "projects"
        }
    elif key == "provider":  # provider
        required_columns = ["provider_name", "employee_id", "name", "role", "skill", "allocation", "rate", "experience", "projects"]
        unique_identifiers = ["provider_name", "employee_id", "name"]
        target_mapping = {
            "providername": "provider_name",
            "employeeid": "employee_id",
            "employeename": "name",
            "role": "role",
            "skills": "skill",
            "allocation": "allocation",
            "rate": "rate",
            "experience": "experience",
            "projects": "projects"
        }

    try:
        all_sheets = {}
        saved_data = extract_all_df(curr_files, all_sheets, saved_data)
        
        if not all_sheets:
            return {
                "structured_data": {"current_state": pd.DataFrame()},
                "looks_good": False,
                "unique_identifier": False,
                "missing_cols": required_columns,
                "missing_details": "No data extracted from files.",
                "available_details": "No columns available."
            }

        # Normalize and rename columns
        def normalize_column_name(col):
            return col.strip().lower().replace(" ", "").replace("%", "")

        categorizations = []
        for sheet_name, dfs in all_sheets.items():
            for df in dfs:
                # Rename columns
                rename_dict = {}
                for col in df.columns:
                    print("--debug col before", col)
                    norm_col = normalize_column_name(col)
                    print("--debug col after", norm_col)
                    for src, tgt in target_mapping.items():
                        if src == norm_col:
                            rename_dict[col] = tgt
                            break
                df_renamed = df.rename(columns=rename_dict)
                print(f"--debug renamed columns: {df_renamed.columns.tolist()}")

                # Categorize with LLM
                dataframe_str = f"Sheet name: {sheet_name}\n{df_renamed.head().to_markdown(index=False)}"
                prompt = create_categorization_prompt_v2(dataframe_str, key)
                response = llm.runV2(prompt, model_opts, 'agent::onboarding_capacity::categorize_sheet', logInfo)
                categorization = extract_json_after_llm(response)
                categorizations.append((sheet_name, df_renamed, categorization))

        # Filter and merge employee-related dataframes
        employee_dfs = [
            df for sheet_name, df, cat in categorizations 
            if cat["type"] in ["employee_info"] or (key == "provider" and cat["type"] == "provider_info")
        ]
        merged_df = pd.concat(employee_dfs, ignore_index=True) if employee_dfs else pd.DataFrame()
        print(f"--debug merged_df: {merged_df.shape}, columns: {merged_df.columns.tolist()}")

        # Analyze columns
        present_columns = merged_df.columns.tolist()
        has_unique_identifier = any(col in present_columns for col in unique_identifiers)
        print(f"--debug present unique identifiers: {[col for col in unique_identifiers if col in present_columns]}")

        # Determine missing columns based on unique identifier presence
        if has_unique_identifier:
            # Only check non-unique-identifier columns
            non_unique_required = [col for col in required_columns if col not in unique_identifiers]
            missing_cols = [col for col in non_unique_required if col not in present_columns]
        else:
            # If no unique identifiers, all required columns are missing
            missing_cols = [col for col in required_columns if col not in present_columns]

        # looks_good is True if at least one unique identifier is present and no non-unique required columns are missing
        trigger_looks_good = has_unique_identifier and len(missing_cols) == 0

        # Prepare response
        available_details = f"Available columns: {', '.join(present_columns)}" if present_columns else "No relevant columns found."
        missing_details = f"Missing required columns: {', '.join(missing_cols)}" if missing_cols else "All required columns present."
        
        print("-----------------------------------------------------------------------------------------------------\n")
        print("--debug UNIQUE Identifier present: ", has_unique_identifier)
        
        structured_data = {"current_state": merged_df}
        response = {
            "structured_data": structured_data,
            "looks_good": trigger_looks_good,
            "unique_identifier": has_unique_identifier,
            "missing_cols": missing_cols,
            "missing_details": missing_details,
            "available_details": available_details
        }
        print("--debug process_uploadedFiles response: ", response)
        return response

    except Exception as e:
        print("--debug error in process_uploaded_files", traceback.format_exc())
        appLogger.error({
            "event": "capacityPlanner_processFiles",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return None



def process_uploadedFiles(
    curr_files,
    prev_state,
    key,
    saved_data,
    llm,
    model_opts, 
    logInfo,
    **kwargs
):
    """
    Process uploaded files, categorize each dataframe, merge relevant data, and inform the user.
    """
    all_sheets = {}
    structured_data = {}

    # Define required columns and unique identifiers based on key
    if key == "internal":
        required_columns = ["Employee ID", "Employee Name", "Role", "Skills", "Allocation%", "Rate", "Experience", "Projects"]
        unique_identifiers = ["Employee ID", "Employee Name"]
    else:  # For "provider", adjust as needed
        required_columns = ["Provider Name", "Employee ID", "Employee Name", "Role", "Skills", "Allocation%", "Rate", "Experience", "Projects"]
        unique_identifiers = ["Provider Name", "Employee ID", "Employee Name"]

    try:
        # Extract data from all files into all_sheets
        saved_data += extract_all_df(curr_files, all_sheets, saved_data)
        print("--debug saved data", saved_data)
        # List to store categorizations for each dataframe
        categorizations = []

        # Process each dataframe individually
        for sheet_name, dfs in all_sheets.items():
            for df in dfs:
                # Create prompt for this dataframe
                dataframe_str = f"Sheet name: {sheet_name}\n{df.head().to_markdown(index=False)}"
                prompt = create_categorization_prompt(dataframe_str, key)
                
                # Run LLM to categorize this dataframe
                response = llm.runV2(prompt, model_opts, 'agent::onboarding_capacity::categorize_sheet', logInfo)
                categorization = extract_json_after_llm(response)
                
                # Store the dataframe and its categorization
                categorizations.append((sheet_name, df, categorization))

        # Filter dataframes containing employee information
        # For "internal", focus on employee_info; for "provider", include provider-related employee data
        employee_dfs = [
            df for sheet_name, df, cat in categorizations 
            if cat["type"] in ["employee_info"] or (key == "provider" and cat["type"] == "provider_info")
        ]

        # Merge employee-related dataframes
        if employee_dfs:
            merged_df = pd.concat(employee_dfs, ignore_index=True)
        else:
            merged_df = pd.DataFrame()
            print("--debug: No dataframes with employee information found.",merged_df)

        present_columns = merged_df.columns.tolist()
        missing_cols = [col for col in required_columns if col not in present_columns]
        has_unique_identifier = any(col in present_columns for col in unique_identifiers)
        
        # Determine if the data is complete
        trigger_looks_good = len(missing_cols) == 0 and has_unique_identifier
        
        # Prepare user feedback
        available_details = f"Available columns: {', '.join(present_columns)}" if present_columns else "No relevant columns found."
        missing_details = f"Missing required columns: {', '.join(missing_cols)}" if missing_cols else "All required columns present."

        structured_data["current_state"] = merged_df
        response =  {
            "structured_data": structured_data,
            "looks_good": trigger_looks_good,
            "unique_identifier": has_unique_identifier,
            "missing_cols": missing_cols,
            "missing_details": missing_details,
            "available_details": available_details
        }
        print("--debug process_uploadedFiles reposne: ",response)
        return response

    except Exception as e:
        print("--debug error in process_uploaded_files", traceback.format_exc())
        appLogger.error({
            "event": "capacityPlanner_processFiles",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return None


# def merge_sheets(all_sheets, llm, user_message, required_columns, model_opts, logInfo):
#     """
#     Merges all DataFrames in `all_sheets` by identifying common columns dynamically.
#     """
#     try:
#         categorized_dfs = {}

#         for sheet_name, df_list in all_sheets.items():
#             if not df_list:
#                 continue 
            
#             df = df_list[0]  # Extract DataFrame from list
#             # print("--debug before clean_dataframe", df)
#             # df = clean_dataframe(df,required_columns,llm,model_opts,logInfo)
#             # print("--debug after :", df)
        
#             categorized_dfs[sheet_name] = categorize_columns(df, llm, user_message, required_columns, model_opts, logInfo)

#         if not categorized_dfs:
#             print("--debug No valid sheets to merge.")
#             return None

#         # Step 2: Identify Common Columns Across All Sheets
#         all_columns = [set(df.columns) for df in categorized_dfs.values()]
#         common_cols = set.intersection(*all_columns) if all_columns else set()

#         if not common_cols:
#             print("--debug No common columns found. Using concatenation.")
#             merged_df = pd.concat(categorized_dfs.values(), ignore_index=True)
#         else:
#             print(f"--debug Merging on columns: {common_cols}")

#             # Step 3: Iteratively Merge DataFrames on Common Columns
#             merged_df = None
#             for df in categorized_dfs.values():
#                 if merged_df is None:
#                     merged_df = df
#                 else:
#                     merged_df = pd.merge(merged_df, df, on=list(common_cols), how="outer")

#         # Step 4: Ensure All Required Columns Exist
#         for col in required_columns:
#             if col not in merged_df.columns:
#                 continue
#                 # merged_df[col] = "MISSING"

#         merged_df = merged_df.drop_duplicates().reset_index(drop=True)
#         return merged_df

#     except Exception as e:
#         appLogger.error({
#             "event": "capacity_mergeSheets",
#             "error": str(e),
#             "traceback": traceback.format_exc()
#         })

# def process_uploadedFiles(
#         curr_files,
#         prev_state,
#         key,
#         user_message,
#         info_given,
#         user_id, 
#         tenant_id, 
#         session_id,
#         saved_data,
#         llm,
#         model_opts, 
#         logInfo,
#         **kwargs
#     ):
#     """
#     Process uploaded files, categorize data, and merge with previous state.
#     """
#     all_sheets = {}
#     structured_data = {}
#     required_columns = []
#         # required_columns = ["Employee Name", "Experience", "Skills", "Role", "Rate", "Allocation %"] if key == "internal" else ["Company Name", "Website", "Address","Employee Name", "Experience", "Skills", "Role", "Rate", "Allocation %"]
    
#     try:
#         saved_data += extract_all_df(curr_files,all_sheets,saved_data)
        

#         prompt = categorizeFilesPrompt(key,user_message,all_sheets,llm,model_opts,logInfo)
#         print("--debug fileprompts", prompt.formatAsString())
#         response = llm.runV2(prompt, model_opts, 'agent::onboarding_capacity::categorize_files', logInfo)
#         print("--debug response", response)

#         fileresponse = extract_json_after_llm(response)
#         print("--debug fileresponse", fileresponse)
        
#         unique_identifier = fileresponse["is_unique_identifier_available"]
#         relevant_cols = fileresponse["relevant_columns_names_for_categorization_available"]
#         missing_details = fileresponse["missing_details"]
#         available_details = fileresponse["available_details"]
        
#     except Exception as e:
#         appLogger.error({"event": "processFiles", "error": str(e),"traceback": traceback.format_exc()})
        
        
#     try:
        
#         merged_df = merge_sheets(all_sheets, llm, user_message, relevant_cols, model_opts, logInfo)
#         print("--merged df", merged_df)
        
#         trigger_looks_good , missing_cols = check_missing_fields(merged_df, relevant_cols)
        
#         structured_data["current_state"] = merged_df
#         return {
#             "structured_data" : structured_data,
#             "looks_good": trigger_looks_good,
#             "unique_identifier" : unique_identifier,
#             "missing_cols": missing_cols,
#             "missing_details": missing_details,
#             "available_details": available_details
#         }
        
#     except Exception as e:
#         print("--debug error in process_uploaded_files", traceback.format_exc())
#         appLogger.error({
#             "event": "capacityPlanner_processFiles",
#             "error": str(e),
#             "traceback": traceback.format_exc()
#         })

    
    
#     # match key:
#     #     case "internal":
#     #         if fileresponse["is_unique_identifier_available"]:
#     #             yield f"""Thankyou for uploading the data, these are the processed values: {fileresponse["available_details"]}"""
#     #             yield f"""These are the missing information, {fileresponse["missing_details"]}. It will be crucial for the resource planning engine to function well.
#     #                     Would you like to add these info?
#     #             """
#     #         else:
#     #             yield f"""No useful info is retrived from the uploaded doc, please review."""
#     #     case "provider":
#     #         if fileresponse["is_unique_identifier_available"]:
#     #             yield f"""Thankyou for uploading the data, these are the processed values: {fileresponse["available_details"]}"""
#     #             yield f"""These are the missing information, {fileresponse["missing_details"]}. It will be crucial for the resource planning engine to function well.
#     #                     Would you like to add these info?
#     #             """
#     #         else:
#     #             yield f"""No useful info is retrived from the uploaded doc, please review."""
                
#     # if key == "internal":
#     #     required_columns = ["name", "experience", "skills", "role", "rate", "allocation"] 
#     # elif key == "provider": 
#     #     required_columns =["provider_name", "name","email", "experience", "allocation","skills"]

#     # if prev_state:
#     #     saved_data += extract_all_df(prev_state,all_sheets,saved_data)
        
        
#     # print("--debug all_sheets and saved data: ", all_sheets,'\n',saved_data)       
#     # try:
        
#     #     merged_df = merge_sheets(all_sheets, llm, user_message, required_columns, model_opts, logInfo)
#     #     print("--merged df", merged_df)
        
#     #     trigger_looks_good , missing_cols = check_missing_fields(merged_df, required_columns)
        
#     #     structured_data["current_state"] = merged_df
#     #     return {
#     #         "structured_data" : structured_data,
#     #         "looks_good": trigger_looks_good,
#     #         "missing_cols": missing_cols
#     #     }
        
#     # except Exception as e:
#     #     print("--debug error in process_uploaded_files", traceback.format_exc())
#     #     appLogger.error({
#     #         "event": "capacityPlanner_processFiles",
#     #         "error": str(e),
#     #         "traceback": traceback.format_exc()
#     #     })


# def merge_dataframes(prev_df, curr_df):
#     """
#     Merge previous and current DataFrames based on common columns.
#     """
#     try:
#         if isinstance(prev_df, dict):
#             prev_df = pd.DataFrame(prev_df)
#         if isinstance(curr_df, dict):
#             curr_df = pd.DataFrame(curr_df)
        
#         common_cols = list(set(prev_df.columns) & set(curr_df.columns))
#         print(f"--debug Merging on columns: {common_cols}")

#         if common_cols:
#             merged_df = pd.merge(prev_df, curr_df, on=common_cols, how="outer").drop_duplicates()
#         else:
#             merged_df = pd.concat([prev_df, curr_df], ignore_index=True)  # Append if no common columns

#         merged_df.fillna("MISSING", inplace=True)
#         return merged_df

#     except Exception as e:
#         error_msg = traceback.format_exc()
#         print("--debug error in merge_dataframes:", error_msg)
#         return None

# def categorize_and_store_sheets(all_sheets, llm, user_message, required_columns, model_opts, logInfo):
#     """
#     Categorize columns for all sheets using LLM and store them in a structured format.
#     """
#     categorized_sheets = {}

#     try:
#         for sheet_name, sheet_dfs in all_sheets.items():
#             categorized_dict = {}

#             for i, df in enumerate(sheet_dfs):
#                 try:
#                     categorized_df = categorize_columns(df, llm, user_message, required_columns, model_opts, logInfo)
#                     categorized_dict[f"{sheet_name}_{i}"] = categorized_df
#                 except Exception as e:
#                     error_msg = traceback.format_exc()
#                     print(f"--debug error processing sheet {sheet_name}_{i}: {error_msg}")
#                     continue  # Skip to next DataFrame if error occurs
            
#             categorized_sheets[sheet_name] = categorized_dict

#         return categorized_sheets

#     except Exception as e:
#         error_msg = traceback.format_exc()
#         print("--debug error in categorize_and_store_sheets:", error_msg)
#         return {}


# def merge_dataframes(prev_df, curr_df):
#     """
#     Merge previous and current DataFrames based on common columns, handling missing values and duplicates.
#     """
#     try:
#         print("--debug df types:", type(prev_df), type(curr_df))
        
#         # Convert dictionary to DataFrame if needed
#         if isinstance(prev_df, dict):
#             prev_df = pd.concat([pd.DataFrame(v) for v in prev_df.values()], ignore_index=True) if prev_df else pd.DataFrame()
#         if isinstance(curr_df, dict):
#             curr_df = pd.concat([pd.DataFrame(v) for v in curr_df.values()], ignore_index=True) if curr_df else pd.DataFrame()

#         # Handle empty cases
#         if prev_df.empty and curr_df.empty:
#             return pd.DataFrame()

#         if prev_df.empty:
#             return curr_df.fillna("MISSING")
#         if curr_df.empty:
#             return prev_df.fillna("MISSING")

#         # Find common columns
#         common_cols = list(set(prev_df.columns) & set(curr_df.columns))

#         if common_cols:
#             merged_df = pd.merge(prev_df, curr_df, on=common_cols, how="outer")
#         else:
#             merged_df = pd.concat([prev_df, curr_df], ignore_index=True)

#         # Fill missing values
#         merged_df.fillna("MISSING", inplace=True)

#         # Remove exact duplicate rows
#         merged_df = merged_df.drop_duplicates().reset_index(drop=True)

#         return merged_df

#     except Exception as e:
#         error_msg = traceback.format_exc()
#         print("--debug error in merge_dataframes:", error_msg)
#         return None


# def merge_excel_sheets(prev_sheets, curr_sheets):
#     """
#     Merge all categorized sheets from previous and current sessions.
#     """
#     try:
#         merged_sheets = {}
#         all_sheet_names = set(prev_sheets.keys()) | set(curr_sheets.keys())

#         for sheet_name in all_sheet_names:
#             prev_df = prev_sheets.get(sheet_name, pd.DataFrame())
#             curr_df = curr_sheets.get(sheet_name, pd.DataFrame())

#             merged_sheets[sheet_name] = merge_dataframes(prev_df, curr_df)

#         return merged_sheets

#     except Exception as e:
#         error_msg = traceback.format_exc()
#         print("--debug error in merge_excel_sheets:", error_msg)
#         return {}





# temp:


    # def download_and_parse_file(file_id, s3_service: S3Service):
    # """
    # Download file as text and pandas DataFrame from S3.
    # """
    # try:
    #     data = s3_service.download_file_as_text(file_id)
    #     df_dict = s3_service.download_file_as_pd(file_id)  # Supports multiple sheets
        
    #     return data, df_dict
    # except Exception as e:
    #     print("--debug error in process_uploadedFiles", e)
    #     appLogger.error({
    #         "event": f"process_uploadedFiles_{file_id}",
    #         "error": e,
    #         "traceback": traceback.format_exc()
    #     })  
    
        #  try:
        # for sheet_name, sheet_dfs in all_sheets.items():
        #     categorized_dict = {}

        #     for i, df in enumerate(sheet_dfs):
        #         try:
        #             categorized_sheet = categorize_columns(df, llm, user_message, required_columns, model_opts, logInfo)
        #             categorized_dict[f"{sheet_name}_{i}"] = categorized_sheet
        #         except Exception as e:
        #             error_msg = traceback.format_exc()
        #             print(f"--debug error processing sheet {sheet_name}_{i}: {error_msg}")
        #             appLogger.error({
        #                 "event": "capacityPlanner_docUpload",
        #                 "error": str(e),
        #                 "traceback": error_msg
        #             })
        #             continue  # Skip to next DataFrame if error occurs
            
        #     curr_uploaded_files_state[sheet_name] = categorized_dict
            
        # Step 2: Categorize columns using LLM
        # categorized_curr_sheets = categorize_and_store_sheets(all_sheets, llm, user_message, required_columns, model_opts, logInfo)

        # # Step 3: Merge categorized sheets with previous state
        # merged_sheets = merge_excel_sheets(last_uploaded_files_state, categorized_curr_sheets)

        # # Step 4: Check for missing fields
        # for sheet_name, sheet_df in merged_sheets.items():
        #     missing_fields = check_missing_fields(sheet_df, required_columns)
        #     if missing_fields:
        #         print("--debug missing_fields", missing_fields, '\n')
        #         ret_val = f"Missing data in {sheet_name}: {', '.join(missing_fields)}. Please provide the required fields."
        #         return TangoYield(return_info=ret_val, yield_info=f"missing data: {missing_fields}")

        # structured_data = merged_sheets
        # print("--debug structured_data: ", structured_data)
        
       

            
    # temp        
        #     merged_sheets = merge_excel_sheets(last_uploaded_files_state,curr_uploaded_files_state)
        #     for sheet_name, sheet_df in merged_sheets.items():
        #         missing_fields = check_missing_fields(sheet_df, required_columns)
        #         if missing_fields:
        #             print("--debug missing_fields", missing_fields, '\n')
        #             ret_val =  f"Missing data in {sheet_name}: {', '.join(missing_fields)}. Please provide the required fields."
        #             return TangoYield(return_info=ret_val, yield_info=f"{further_specific_capacity_creation}") 
    
        #     structured_data[sheet_name] = merged_sheets
        #     print("--debug structred data ", structured_data)
                
        #     # for sheet_name, sheet_df in all_sheets.items():
                
        #     #     # saved_data += f"Processing file: {sheet_name}:\n"
        #     #     # print("--debug file_name", sheet_name)
                
        #     #     # data = S3Service().download_file_as_text(file_id)
        #     #     # print("--debug data", data)
                
        #     #     try:
        #     #         # df = S3Service().download_file_as_pd(file_id)
        #     #         # print("--debug df: ", df)
        #     #         categorized_dict = {}
        #     #         for name, df in sheet_df.items():
        #     #             categorized_sheet = categorize_columns(df,llm,user_message,required_columns,model_opts,logInfo)
        #     #             categorized_dict[name] = categorized_sheet
        #     #             curr_uploaded_files_state[name] = categorized_dict  
        #     #         print("--debug curr_uploaded_files_state: ", curr_uploaded_files_state)
        #     #     except Exception as e:
        #     #         print(f"--debug error processing file {name}: {e}")
        #     #         appLogger.error({
        #     #             "event": "capacityPlanner_docUpload",
        #     #             "error": e,
        #     #             "traceback": traceback.format_exc()
        #     #         })
        #     #         continue
                
        #         # if data is not None:
        #         #     saved_data += data

        
            
        #     # for file_name, curr_df in curr_uploaded_files_state.items():
        #     #     prev_df = last_uploaded_files_state.get(file_name)

        #     #     if prev_df is not None:
        #     #         merged_df = merge_dataframes(prev_df, curr_df)
        #     #     else:
        #     #         merged_df = curr_df

        #     #     structured_data[file_name] = merged_df
        #     #     print("--debug structred data ", structured_data)

        #     #     # Check for missing fields
        #     #     missing_fields = check_missing_fields(merged_df, required_columns)
        #     #     if missing_fields:
        #     #         print("--debug missing_fields", missing_fields, '\n')
        #     #         # return {
        #     #         #     "structured_data": structured_data,
        #     #         #     "missing_fields": f"Missing data in {file_name}: {', '.join(missing_fields)}. Please provide the required fields.",
        #     #         # }
        #     #         ret_val =  f"Missing data in {file_name}: {', '.join(missing_fields)}. Please provide the required fields."
        #     #         return TangoYield(return_info=ret_val, yield_info=f"{further_specific_capacity_creation}") 
    
            # def merge_dataframes(prev_df, curr_df):
#     """
#     Merge previous and current DataFrames based on common columns.
#     """
#     try:
#         print("--df types: ", type(prev_df), type(curr_df))
#         print("--debug merge_dataframes: ", prev_df, curr_df)

#         # Convert prev_df if it's a dictionary
#         if isinstance(prev_df, dict):
#             if all(isinstance(v, (int, float, str, bool, type(None))) for v in prev_df.values()):
#                 prev_df = pd.DataFrame([prev_df])  # Convert scalar dict to a single-row DataFrame
#             else:
#                 prev_df = pd.concat([pd.DataFrame(v) for v in prev_df.values()], ignore_index=True)  # Handle nested dicts

#         # Convert curr_df if it's a dictionary
#         if isinstance(curr_df, dict):
#             if all(isinstance(v, (int, float, str, bool, type(None))) for v in curr_df.values()):
#                 curr_df = pd.DataFrame([curr_df])  # Convert scalar dict to a single-row DataFrame
#             else:
#                 curr_df = pd.concat([pd.DataFrame(v) for v in curr_df.values()], ignore_index=True)  # Handle nested dicts

#         # Ensure both are valid DataFrames
#         if prev_df.empty and curr_df.empty:
#             print("--debug Both DataFrames are empty")
#             return pd.DataFrame()

#         common_cols = list(set(prev_df.columns) & set(curr_df.columns))
#         print(f"--debug Merging on columns: {common_cols}")

#         if common_cols:
#             merged_df = pd.merge(prev_df, curr_df, on=common_cols, how="outer").drop_duplicates()
#         else:
#             merged_df = pd.concat([prev_df, curr_df], ignore_index=True)  # Append if no common columns

#         merged_df.fillna("MISSING", inplace=True)
#         return merged_df

#     except Exception as e:
#         error_msg = traceback.format_exc()
#         print("--debug error in merge_dataframes:", error_msg)
#         return None
    
    
# def merge_excel_sheets(prev_sheets, curr_sheets):
#     """
#     Merge all sheets from the previous and current Excel files.
#     """
#     try:
#         merged_sheets = {}
#         all_sheet_names = set(prev_sheets.keys()) | set(curr_sheets.keys())
        
#         for sheet_name in all_sheet_names:
#             prev_df = prev_sheets.get(sheet_name, pd.DataFrame())
#             curr_df = curr_sheets.get(sheet_name, pd.DataFrame())
#             print("--debug dfs: ", prev_df, curr_df)
            
#             merged_sheets[sheet_name] = merge_dataframes(prev_df, curr_df)
        
#         return merged_sheets
#     except Exception as e:
#         error_msg = traceback.format_exc()
#         print("--debug error in merge_excel_sheets:", error_msg)
#         return None


