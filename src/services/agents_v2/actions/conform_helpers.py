"""
Helper functions for conforming mapped data to schema requirements using LLM.
Used by both sheet_mapper_v2.py and text_mapper.py.
"""

import json
from src.trmeric_api.logging.AppLogger import debugLogger
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_utils.helper.common import MyJSON
from ..schema import SCHEMAS

DEFAULT_MODEL = "gpt-4.1"
DEFAULT_TEMPERATURE = 0.1
DEFAULT_OUTPUT_TOKENS = 10000

def _sanitize_for_json(obj):
    """Recursively convert type objects to strings for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    elif isinstance(obj, type):
        return str(obj)
    return obj


def conform_project_update_data_llm(mapped_data: list[dict], user_id: int, tenant_id: int) -> list[dict]:
    """
    Uses LLM to conform mapped_data for project_update jobs to schema requirements.
    Batches large datasets to avoid token limits and improve reliability.
    Handles sanitization automatically.
    Args:
        mapped_data: List of dicts from sheet mapping.
        user_id: User ID for logging.
        tenant_id: Tenant ID for logging.
    Returns:
        List of dicts with conformed values matching the PROJECT_UPDATE_SCHEMA.
    """
    # Sanitize data first to handle any Python type objects
    sanitized_data = _sanitize_for_json(mapped_data)
    
    # Batch size to avoid token limits - adjust as needed
    BATCH_SIZE = 50
    
    # If dataset is small, process all at once
    if len(sanitized_data) <= BATCH_SIZE:
        return _conform_batch(sanitized_data, user_id, tenant_id)
    
    # Process in batches for large datasets
    all_conformed = []
    for i in range(0, len(sanitized_data), BATCH_SIZE):
        batch = sanitized_data[i:i + BATCH_SIZE]
        debugLogger.info(f"Processing batch {i//BATCH_SIZE + 1}/{(len(sanitized_data) + BATCH_SIZE - 1)//BATCH_SIZE} ({len(batch)} items)")
        conformed_batch = _conform_batch(batch, user_id, tenant_id)
        all_conformed.extend(conformed_batch)
    
    return all_conformed


def _conform_batch(batch_data: list[dict], user_id: int, tenant_id: int) -> list[dict]:
    """
    Internal function to conform a single batch of data.
    """
    batch_data = [b["data"] for b in batch_data]
    # Get the actual schema from imports
    # project_update_schema = SCHEMAS.get("project_update", {})
    
    # # Handle schema with array wrapper (like PROJECT_UPDATE_SCHEMA with "data" field)
    # if "data" in project_update_schema and isinstance(project_update_schema["data"], list):
    #     item_schema = project_update_schema["data"][0] if project_update_schema["data"] else {}
    #     schema_description = f"Each object in the array should match: {json.dumps(item_schema, indent=2, ensure_ascii=False)}"
    # else:
    #     item_schema = project_update_schema
    #     schema_description = f"Each object in the array should match: {json.dumps(item_schema, indent=2, ensure_ascii=False)}"

    prompt = f"""
        You are a data validation and transformation expert. 
        Your job is to conform a list of project updates into a strict schema.

        Required Output Format: JSON array of objects  
        Each object must have:
        - project_name (string, required)
        - At least one update type array (status_updates, risk_updates, milestone_updates, etc.)

        For STATUS UPDATES specifically, transform all free-text or raw status fields into this exact structure:

        "status_updates": [
            {{
                "status_type": <int: 1=scope, 2=schedule, 3=spend>,,
                "status_value": <int: 1=on_track, 2=at_risk, 3=compromised>,
                "comment": "<string: good text explaining update>"
            }},...
        ],
            
        Transformation Rules:
        - Map status_update_comments or other free text into "comment"
        - Deduce "status_type" (scope, schedule, spend) if possible from text; otherwise default to "scope"
        - Deduce "status_value" (on_track, at_risk, compromised) if possible; otherwise default to "on_track"
        - Ensure both status_type and status_value integers are correctly aligned with the status_type/status_value
        - If multiple comments exist, create multiple entries in the status_updates array
        - If a field is missing, fill with sensible defaults from the schema

        Input data to transform:
        {MyJSON.dumps(batch_data)}

        Output: JSON array only, no explanations or extra text.
    """
    model_options = ModelOptions(
        model=DEFAULT_MODEL,
        temperature=DEFAULT_TEMPERATURE,
        max_tokens=DEFAULT_OUTPUT_TOKENS
    )
    llm = ChatGPTClient(user_id=user_id, tenant_id=tenant_id)
    chat_completion = ChatCompletion(
        system=prompt,
        prev=[],
        user="Output properly sir"
    )
    # print("debugf -- ", chat_completion.formatAsString())
    response = llm.run(
        chat_completion,
        model_options,
        'project_update_conformance',
        logInDb={"tenant_id": tenant_id, "user_id": user_id}
    )
    conformed = extract_json_after_llm(response)
    print("debugf conform batch-- ", response)
    return conformed
    # Ensure output matches the nested schema: [{project_name, status_updates: [...]}, ...]
    # if isinstance(conformed, dict) and "data" in conformed:
    #     conformed_list = conformed["data"]
    # elif isinstance(conformed, list):
    #     conformed_list = conformed
    # else:
    #     debugLogger.warning("LLM conformance failed for batch, returning original data")
    #     return batch_data

    # Validate each item has project_name and at least one type of update
    # validated = []
    # for item in conformed_list:
    #     pname = item.get("project_name")
    #     if not pname:
    #         continue
            
    #     # Check if at least one update type is present
    #     has_updates = (
    #         (item.get("status_updates") and isinstance(item.get("status_updates"), list)) or
    #         (item.get("risk_updates") and isinstance(item.get("risk_updates"), list)) or
    #         (item.get("milestone_updates") and isinstance(item.get("milestone_updates"), list))
    #     )
        
    #     if has_updates:
    #         validated.append(item)
    # return validated

