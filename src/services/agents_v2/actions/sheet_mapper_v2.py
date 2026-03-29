import pandas as pd
import logging
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
import json
import uuid
from src.trmeric_database.dao import JobDAO
from ..helper.common import MyJSON
from .conform_helpers import conform_project_update_data_llm
from ..schema import SCHEMAS
from src.trmeric_api.logging.ProgramState import ProgramState
import traceback

# Helper: recursively convert type objects to strings for JSON serialization
def _sanitize_for_json(obj):
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    elif isinstance(obj, type):
        return str(obj)
    return obj


# Constants
DEFAULT_MODEL = "gpt-4.1"
DEFAULT_TEMPERATURE = 0.1
DEFAULT_OUTPUT_TOKENS = 1000

from datetime import date, datetime
from uuid import UUID


# class DateEncoder(json.JSONEncoder):
#     def default(self, obj):
#         if isinstance(obj, (date, datetime)):
#             return obj.isoformat()
#         elif isinstance(obj, UUID):
#             return str(obj)  # Convert UUID to string
#         return super().default(obj)


def _make_json_safe(obj):
    if isinstance(obj, set):
        return list(obj)
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_json_safe(v) for v in obj]
    return obj


SYSTEM_PROMPT = """
    You are an expert data mapper tasked with mapping \
    CSV columns to a predefined schema. \
    Your goal is to propose a JSON mapping that \
    specifies how each schema field should be \
    populated from the CSV data. \
    Use the following functions to define mappings: \
    - `use_column(col_name)`: Use a single column's value.
    - `add_columns([col1, col2, ...])`: Concatenate multiple columns with a space separator.
    - `empty()`: Return an empty value (appropriate for the schema type, e.g., [] for lists, "" for strings).
    - `default_value(value)`: Use a user-specified default value for the field. - arg for this default_value in output will be the [value]
    - `split_column(col_name, delimiter, index)`: Split a column by delimiter and select the part at the specified index (0-based) 
        for the schema field. For list-type fields, use `split_column(col_name, delimiter, -1)` to return all parts as a list. Use for fields like first_name, last_name, street, city, year, month, tags_list, etc., when a single column contains multiple parts.

    Input will include:
    - CSV column names
    - First row of data (as a dictionary)
    - The target schema
    - User-specified default values (if provided)
    - Clarifying information (if provided)
    - All planning context (for prior mappings)

    For each schema field, propose the best mapping based on column names and sample data. 
    If unsure, use `empty()`. 
    Output a JSON object where keys are schema fields and values are objects with `function` and `args` keys.
    
    - For 'full_name' -> if we have to split in 'first_name' and 'last_name' we sohlud see how many workds make up the name:- 
        if two word name then use `split_column('full_name', ' ', 0)` and `split_column('full_name', ' ', 1)`
        if n word name then use `split_column('full_name', ' ', 0)` and `split_column('full_name', ' ', n-1)`
    - For 'address' -> 'street', 'city', use `split_column('address', ',', 0)`, `split_column('address', ',', 1)`.
    - For 'tags' -> 'tags_list', use `split_column('tags', ',', -1)` to return a list

    When user make comment you have to update the related fields keep other fields maped with same. See all_planning_context for clarity
    Output Format:
    ```json
    {
        "thought_process": "",
        "clarification_question": "",
        "mapping": {
            "project_title": {"function": "add_columns", "args": [...]},
            "project_description": {"function": "use_column", "args": [...]},
            "project_budget": {"function": "empty", "args": []}
            "..": {"function": "default_value", "args": [..]}
        },
    }
    ```
"""

def create_mapping(
    FIELDS: list[str], # target fields
    data: pd.DataFrame, # sheet data
    clarifying_information: str, ## user comment
    user_id: int,
    tenant_id: int,
    file_type_lower='',
    mode='all',
    context='',
    filename=''
):
    """
    Creates a mapping from CSV columns to schema fields using an LLM.

    Args:
        FIELDS (list[str]): List of target schema field names.
        data (pd.DataFrame): Input DataFrame from CSV.
        clarifying_information (str): User-provided feedback to refine mappings.
        user_id (int): User ID for logging.
        tenant_id (int): Tenant ID for logging.
        file_type_lower (str): File type for job creation.
        mode (str): Processing mode ('all' or 'preview').
        context (str): Additional context for mapping.
        filename (str): Original filename for job payloads.

    Returns:
        dict: JSON mapping of schema fields to CSV column functions.
    """
    debugLogger.info("Starting column mapping process")
    
    # Check if DataFrame is empty
    if data.empty:
        debugLogger.error("Input DataFrame is empty")
        raise ValueError("Input DataFrame is empty")
    
     # Identify and filter out null columns
    null_columns = [col for col in data.columns if data[col].isna().all()]
    non_null_columns = [col for col in data.columns if col not in null_columns]
    
    # Store null columns for reference (e.g., for logging or user feedback)
    # mapping_metadata = {
    #     "ignored_null_columns": null_columns, 
    #     "non_null_columns": non_null_columns
    # }
    
    # Prepare user prompt
    # Get the first row of data for non-null columns
    first_row = data[non_null_columns].iloc[0].to_dict()
    print("debug ")
    user_prompt_data = {
        "columns": non_null_columns,
        "first_row": first_row,
        "schema": FIELDS,
        "clarifying_information": clarifying_information if clarifying_information else "",
        "all_planning_context": context
    }
    # print("debig user ", user_prompt_data)
    # user_prompt_data = _make_json_safe(user_prompt_data)
    user_prompt = MyJSON.dumps(user_prompt_data)
    model_options = ModelOptions(
        model=DEFAULT_MODEL,
        temperature=DEFAULT_TEMPERATURE,
        max_tokens=DEFAULT_OUTPUT_TOKENS
    )
    llm = ChatGPTClient(user_id=user_id, tenant_id=tenant_id)
    chat_completion = ChatCompletion(
        system=SYSTEM_PROMPT,
        prev=[],  # Add previous messages if needed for context
        user=user_prompt
    )
    response = llm.run(
        chat_completion,
        model_options, 
        'sheet::mapping', 
        logInDb={
            "tenant_id": tenant_id,
            "user_id": user_id
        }
    )
    print("response ----", response)
    mappings = extract_json_after_llm(response)
    
    ##### create unused cols list
    ## used cols list
    used_cols_list = set()
    for schema_key, mapping in mappings.get("mapping").items():
        func = mapping["function"]
        args = mapping["args"]
        
        try:
            if func in ["use_column", "split_column"]:
                used_cols_list.add(args[0])

            elif func == "add_columns":
                [used_cols_list.add(a) for a in args]

        except Exception as e:
            print("error ", e)
            
    unused_cols_list = [col for col in non_null_columns if col not in used_cols_list]
    formatted_results = execute_mapping(
        mappings=mappings.get("mapping"),
        data=data,
        mode=mode,
        unused_cols_list=unused_cols_list
    )
    with open("temp.json", 'w') as f:
        MyJSON.dump(formatted_results, f, indent =2)
    
    scheduling_messages = ''
    if mode == 'all':
        run_id = f"{file_type_lower}-creation-{tenant_id}-{user_id}-{uuid.uuid4()}"
        job_dao = JobDAO
        
        # Special handling for project_update - use update job type instead of create
        if file_type_lower == "project_update":
            job_type = "update-project"
            # conformed_results = conform_project_update_data_llm(formatted_results, user_id, tenant_id)
            payload = {
                "job_type": job_type,
                "run_id": run_id,
                "total_count": len(formatted_results),
                "mapped_data": formatted_results,
                "socket_id": ProgramState.get_instance(user_id).get("socket_id"),
                "filename": filename,
                "creator_source": "trucible"
            }
            job_dao.create(
                tenant_id=tenant_id,
                user_id=user_id,
                schedule_id=None,
                job_type=job_type,
                payload=payload
            )
        else:
            job_type = f"create-{file_type_lower}"
            if file_type_lower == "potential":
                payload = {
                    "job_type": job_type,
                    "run_id": run_id,
                    "total_count": len(formatted_results),
                    "data": formatted_results,
                    "extra_data": None,
                    "socket_id": ProgramState.get_instance(user_id).get("socket_id"),
                    "filename": filename,
                    "creator_source": "trucible"
                }
                job_dao.create(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    schedule_id=None,
                    job_type=job_type,
                    payload=payload
                )
            else:
                for fr in formatted_results:
                    payload = {
                        "job_type": job_type,
                        "run_id": run_id,
                        "total_count": len(formatted_results),
                        "data": fr["data"],
                        "extra_data": fr.get("extra_data") or {},
                        "original_used_data": fr.get("original_used_data") or {},
                        "socket_id": ProgramState.get_instance(user_id).get("socket_id"),
                        "filename": filename,
                        "creator_source": "trucible"
                    }
                    job_dao.create(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        schedule_id=None,
                        job_type=job_type,
                        payload=payload
                    )
                    
        # Create session summary job
        try:

            # Get current socket_id from ProgramState
            ps = ProgramState.get_instance(user_id)
            socket_id = ps.get("socket_id")
            
            if socket_id:
                # Generate run_id for this sheet mapping session
                run_id_summary = f"sheet-mapping-{tenant_id}-{user_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                
                # Create job for session summary (no session_ids needed)
                session_summary_payload = {
                    "job_type": "session-summary",
                    "run_id": run_id_summary,
                    "user_id": user_id,
                    "socket_id": socket_id
                }
                
                session_job_id = job_dao.create(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    schedule_id=None,
                    job_type="session-summary",
                    payload=session_summary_payload
                )
                
                appLogger.info(f"Created session-summary job {session_job_id} for User ID: {user_id}, Socket ID: {socket_id}")
                
        except Exception as e:
            appLogger.error({
                "event": "Sheet_mapping_summary_job_creation_failed",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "user_id": user_id,
                "socket_id": socket_id if 'socket_id' in locals() else None
            })
        
        scheduling_messages = f"All items have been scheduled for {file_type_lower} creation"
            
        # if file_type_lower == "roadmap":
        #     run_id = f"roadmap-creation-{tenant_id}-{user_id}-{uuid.uuid4()}"
        #     job_dao = JobDAO
        #     job_type = "create-roadmap"
        #     for fr in formatted_results:
        #         payload = {
        #             "job_type": job_type,
        #             "run_id": run_id,
        #             "total_count": len(formatted_results),
        #             "data": fr["data"],
        #             "extra_data": fr["extra_data"]
        #         }
        #         job_dao.create(
        #             tenant_id=tenant_id,
        #             user_id=user_id,
        #             schedule_id=None,
        #             job_type=job_type,
        #             payload=payload
        #         )
                
        #     scheduling_messages = "All items have been scheduled for roadmap creation"
        
    return {
        # "metadata": mapping_metadata,
        "sheet_columns_to_fields_mapping": mappings,
        "metadata": {
            "used_cols_list": list(used_cols_list),
            "unused_cols_list": unused_cols_list,
            "null_col_list": null_columns
        },
        # "formatted_results_according_to_mapping": formatted_results,
        "formatted_results_according_to_mapping": [fr["data"] for fr in formatted_results[:2]],
        "mode": mode,
        "scheduling_message": scheduling_messages
    }

def execute_mapping(
    mappings: dict,
    data: pd.DataFrame,
    mode="all",
    unused_cols_list= []
) -> list[dict]:
    debugLogger.info("Starting mapping execution process")
    metadata = mappings.pop("metadata", {})
    non_null_columns = [col for col in data.columns if col not in metadata.get("ignored_null_columns", [])]
    
    # Filter out rows that are completely empty in the columns we're mapping from
    # Get all columns that are actually used in mappings
    used_columns = set()
    for schema_key, mapping in mappings.items():
        func = mapping["function"]
        args = mapping["args"]
        if func in ["use_column", "split_column"]:
            used_columns.add(args[0])
        elif func == "add_columns":
            used_columns.update(args)
    
    # Convert to list and filter to only columns that exist in the DataFrame
    used_columns = [col for col in used_columns if col in data.columns]
    
    if used_columns:
        # A row is considered empty if ALL used columns are NaN or empty/whitespace
        def is_row_empty_for_mapping(row):
            for col in used_columns:
                value = row[col]
                if pd.notna(value) and str(value).strip():
                    return False  # Found non-empty value in a used column
            return True  # All used columns are empty
        
        original_row_count = len(data)
        data = data[~data.apply(is_row_empty_for_mapping, axis=1)]
        filtered_row_count = len(data)
        
        if original_row_count != filtered_row_count:
            debugLogger.info(f"Filtered out {original_row_count - filtered_row_count} rows with empty values in mapped columns, processing {filtered_row_count} rows")
    
    # Initialize result list
    results = []
    # Process each row
    for idx, row in data[non_null_columns].iterrows():
        if idx >= 3 and mode == "preview":
            break
            
        debugLogger.debug(f"Processing row {idx}")
        record = {}
        actual_record = {}
        for schema_key, mapping in mappings.items():
            func = mapping["function"]
            args = mapping["args"]
            schema_type = "string"
            actual_col = []

            try:
                if func == "use_column":
                    value = row.get(args[0], None) or None
                    actual_col.append(args[0])
                    if value is None or pd.isna(value):
                        value = "" if "string" in schema_type else [] if "list" in schema_type else 0.0 if "float" in schema_type else None
                    else:
                        value = _convert_value(value, schema_type, schema_key)
                elif func == "add_columns":
                    values = [str(row.get(arg, "")) for arg in args]
                    [actual_col.append(arg) for arg in args]
                    value = "- ".join(v for v in values if v)
                    
                    parts = []
                    for col in args:
                        val = row.get(col, "")
                        if pd.notna(val) and str(val).strip():
                            parts.append(f"{col}: {val}")

                    value = "\n".join(parts)
                    value = _convert_value(value, schema_type, schema_key)

                    # value = _convert_value(value, schema_type, schema_key)

                elif func == "default_value":
                    if len(args) > 0:
                        value = str(args[0])
                    else:
                        value = ""

                elif func == "empty":
                    value = [] if "list" in schema_type else "" if "string" in schema_type else 0.0 if "float" in schema_type else None
                    
                elif func == "split_column":
                    col_name = args[0]
                    actual_col.append(args[0])
                    delimiter = args[1] if len(args) > 1 else " "
                    index = int(args[2]) if len(args) > 2 else 0
                    value_str = row.get(col_name, "") or ""
                    if value_str and isinstance(value_str, str):
                        parts = value_str.rsplit(delimiter, abs(index)) if index < 0 else value_str.split(delimiter)
                        parts = [p.strip() for p in parts]
                        if index == -1 and "list" in schema_type:
                            value = parts
                        elif index < 0:
                            value = parts[index] if abs(index) <= len(parts) else ""
                        else:
                            value = parts[index] if index < len(parts) else ""
                    else:
                        value = [] if "list" in schema_type else ""
                    value = _convert_value(value, schema_type, schema_key)

                record[schema_key] = value
                for col_name in actual_col:
                    actual_record[col_name] = row.get(col_name, "") or ""
                

            except Exception as e:
                debugLogger.error(f"Error processing {schema_key} in row {idx}: {str(e)}")
                raise ValueError(f"Error processing {schema_key} in row {idx}: {str(e)}")

        # results.append(record)
        # Collect unused columns for this row
        # extra_data = {col: row.get(col, None) for col in unused_cols_list}
        extra_data = {
            col: row[col] if pd.notna(row[col]) else ""
            for col in unused_cols_list
        }
        results.append({
            "data": record,
            "extra_data": extra_data,
            "original_used_data": actual_record
        })

    debugLogger.info(f"Mapping executed successfully for {len(results)} rows")

    return results

def _convert_value(value: any, schema_type: str, schema_key: str) -> any:
    """
    Converts a value to the expected schema type.

    Args:
        value: The input value.
        schema_type: The schema type (e.g., "float", "date", "list").
        schema_key: The schema field name for logging.
        logger: Logger instance.

    Returns:
        The converted value.
    """
    try:
        if "float" in schema_type and value is not None:
            return float(value)
        elif "date" in schema_type and value is not None:
            return pd.to_datetime(value).isoformat()
        elif "list" in schema_type and value is not None:
            if isinstance(value, str):
                return [v.strip() for v in value.split(",") if v.strip()]
            return [value]
        return str(value) if value is not None else ""
    except Exception as e:
        debugLogger.warning(f"Failed to convert {schema_key} to {schema_type}: {str(e)}")
        return "" if "string" in schema_type else [] if "list" in schema_type else 0.0 if "float" in schema_type else None
    
