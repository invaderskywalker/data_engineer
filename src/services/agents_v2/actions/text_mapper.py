from src.services.agents_v2.schema import SCHEMAS
from .conform_helpers import conform_project_update_data_llm
import pandas as pd
from src.ml.llm.models.OpenAIClient import ChatGPTClient
from src.ml.llm.Types import ChatCompletion, ModelOptions
from src.utils.json_parser import extract_json_after_llm
from src.api.logging.AppLogger import appLogger, debugLogger
import uuid
from src.database.dao import JobDAO
from ..helper.common import MyJSON
from src.api.logging.ProgramState import ProgramState
import traceback
from typing import List, Dict
from datetime import datetime

# Constants
DEFAULT_MODEL = "gpt-4.1"
DEFAULT_TEMPERATURE = 0.1
DEFAULT_OUTPUT_TOKENS = 1000

# Helper: recursively convert type objects to strings for JSON serialization
def _sanitize_for_json(obj):
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    elif isinstance(obj, type):
        return str(obj)
    return obj

def create_text_mapping(
    FIELDS: List[str],
    text_contents: List[Dict],
    num_items: int = 1,
    clarifying_information: str = '',
    user_id: int = 1,
    tenant_id: int = 1,
    file_type_lower: str = '',
    mode: str = 'preview',
    context: str = ''
) -> Dict:
    """
    Creates a direct key-value mapping from text-based file content to schema fields using an LLM.

    Args:
        FIELDS (list[str]): List of target schema field names.
        text_contents (List[Dict]): List of dictionaries containing filename, s3_key, content, and analysis.
        num_items (int): Number of items to extract (projects, roadmaps, potentials, or status updates).
        clarifying_information (str): User-provided feedback to refine mappings.
        user_id (int): User ID for logging.
        tenant_id (int): Tenant ID for logging.
        file_type_lower (str): File type ('project', 'roadmap', 'potential', 'project_update').
        mode (str): Processing mode ('all' or 'preview').
        context (str): Additional context for mapping.

    Returns:
        Dict: JSON mapping of items to schema fields and scheduling status.
    """
    debugLogger.info("Starting text project mapping process")

    # Use SCHEMAS to select fields if FIELDS is empty or None
    # Always use SCHEMAS for fields and type hints
    schema_dict = SCHEMAS.get(file_type_lower, {})
    schema_fields = list(schema_dict.keys())
    schema_types = {k: v for k, v in schema_dict.items()}
    user_prompt_data = {
        "files": [
            {
                "filename": item['filename'],
                "content": str(item.get("content", "")),
                "analysis": item['analysis']
            } for item in text_contents
        ],
        "schema": schema_fields,
        "schema_types": schema_types,
        "num_items": num_items,
        "file_type": file_type_lower,
        "clarifying_information": clarifying_information,
        "all_planning_context": context
    }
    user_prompt = MyJSON.dumps(user_prompt_data)

    SYSTEM_PROMPT = """
    You are an expert data extractor tasked with identifying and mapping structured data from unstructured text (DOC, DOCX, PDF, TXT, PPT, PPTX) to a predefined schema. Your goal is to:
    - Identify up to N distinct items (as specified by num_items) within the provided text files based on the file_type.
    - For each item, map its details directly to the schema fields as key-value pairs.
    - Items may be separated by headers, sections, bullet points, or slide breaks (e.g., 'Slide:' for PPT/PPTX files).
    - Use the 'analysis' field to identify item boundaries (e.g., headers or slide markers).
    - If a field cannot be mapped, set its value to an empty string ("") or an empty list ([]) based on the expected type.
    - If unsure, provide a `clarification_question` to request more details from the user.

    **File Types and What to Extract:**
    - **project**: Extract project information (names, objectives, timelines, stakeholders, budgets, etc.)
    - **roadmap**: Extract roadmap information (initiatives, timelines, goals, milestones, etc.)
    - **potential**: Extract resource/potential information (skills, availability, rates, etc.)
    - **project_update**: Extract project updates (project names, status, risks, milestones, etc.)

    Input includes:
    - List of files with filename, content (first 5000 characters), and analysis.
    - Target schema fields.
    - Number of items to extract (num_items).
    - File type indicating what kind of data to extract.
    - User-provided clarifying information.
    - Prior planning context.

    Output a JSON object with:
    - `thought_process`: Explanation of how items were identified and mapped.
    - `clarification_question`: If clarification is needed.
    - `item_mappings`: List of dictionaries, each containing direct key-value mappings for schema fields.

    Output Format:
    ```json
    {
        "thought_process": "",
        "clarification_question": "",
        "item_mappings": [
            {
                "field1": "value1",
                "field2": "value2",
                "...": ""
            },
            ...
        ]
    }
    ```
    """

    model_options = ModelOptions(
        model=DEFAULT_MODEL,
        temperature=DEFAULT_TEMPERATURE,
        max_tokens=25000
    )
    llm = ChatGPTClient(user_id=user_id, tenant_id=tenant_id)
    chat_completion = ChatCompletion(
        system=SYSTEM_PROMPT,
        prev=[],
        user=user_prompt
    )

    response = llm.run(
        chat_completion,
        model_options,
        'text_project_mapping',
        logInDb={"tenant_id": tenant_id, "user_id": user_id}
    )
    print("response --- ", response)
    mappings = extract_json_after_llm(response)

    if not mappings.get("item_mappings") or len(mappings["item_mappings"]) == 0:
        debugLogger.error("No item mappings generated by LLM")
        return {
            'error': 'No item mappings generated',
            'needs_clarification': True,
            'clarification_question': f'The system could not identify distinct {file_type_lower}s in the files. Please provide more specific instructions or clarify item boundaries.'
        }
    
    formatted_results = {}
    if file_type_lower == "project_update":
        formatted_results = mappings.get("item_mappings", [])
    else:
        formatted_results = execute_text_mapping(
            mappings=mappings.get("item_mappings"),
            mode=mode,
            text_contents=text_contents,
            schema_fields=schema_fields,
            schema_types=schema_types
        )
        
    
    
    print("debug -- formatted results ",  mode, formatted_results)

    scheduling_messages = ''
    if mode == 'all':
        run_id = f"{file_type_lower}-creation-{tenant_id}-{user_id}-{uuid.uuid4()}"
        job_dao = JobDAO
        filename = text_contents[0]["filename"] if text_contents and "filename" in text_contents[0] else None
        # Special handling for project_update - use update job type instead of create
        if file_type_lower == "project_update":
            job_type = "update-project"
            mapped_data = mappings.get("item_mappings", [])
            conformed_data = conform_project_update_data_llm(mapped_data, user_id, tenant_id)
            payload = {
                "job_type": job_type,
                "run_id": run_id,
                "total_count": len(conformed_data),
                "mapped_data": conformed_data,
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
            print("in else ")
            job_type = f"create-{file_type_lower}"
            print("in else ", job_type)
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

        try:
            socket_id = ProgramState.get_instance(user_id).get("socket_id")
            if socket_id:
                run_id_summary = f"text-mapping-{tenant_id}-{user_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
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
                appLogger.info(f"Created session-summary job {session_job_id} for User ID: {user_id}")
        except Exception as e:
            appLogger.error({
                "event": "Text_mapping_summary_job_creation_failed",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "user_id": user_id,
                "socket_id": socket_id if 'socket_id' in locals() else None
            })

        # scheduling_messages = f"All {len(formatted_results)} {file_type_lower}s have been scheduled for {file_type_lower} creation"

    res = {
        "item_mappings": mappings,
        "metadata": {
            "file_count": len(text_contents),
            "num_items_extracted": len(mappings.get("item_mappings", [])),
            "source_files": [item['filename'] for item in text_contents]
        },
        "formatted_results_according_to_mapping": formatted_results[:2] if mode == "preview" else formatted_results,
        "mode": mode,
        "scheduling_messages": scheduling_messages
    }
    print("res -- ", res)
    return res
    
def execute_text_mapping(
    mappings: List[Dict],
    mode: str = "all",
    text_contents: List[Dict] = [],
    schema_fields: List[str] = [],
    schema_types: dict = None
) -> List[Dict]:
    """
    Executes text mappings to produce structured project data from direct key-value mappings.

    Args:
        mappings (List[Dict]): List of project mappings from LLM (direct key-value pairs).
        mode (str): Processing mode ('all' or 'preview').
        text_contents (List[Dict]): List of text file contents for reference.
        schema_fields (List[str]): List of schema fields for validation.

    Returns:
        List[Dict]: List of structured project records.
    """
    debugLogger.info("Starting text mapping execution process")
    results = []

    for idx, project_mapping in enumerate(mappings):
        if idx >= 3 and mode == "preview":
            break

        debugLogger.debug(f"Processing project {idx + 1}")
        record = {}
        actual_data = {}

        for schema_key in schema_fields:
            try:
                value = project_mapping.get(schema_key, "")
                # Use schema_types for type hints if available
                schema_type = "string"
                if schema_types and schema_key in schema_types:
                    schema_type = schema_types[schema_key]
                actual_data[schema_key] = value
                converted_value = _convert_value(value, str(schema_type), schema_key)
                record[schema_key] = converted_value
            except Exception as e:
                debugLogger.error(f"Error processing {schema_key} for project {idx + 1}: {str(e)}")
                raise ValueError(f"Error processing {schema_key} for project {idx + 1}: {str(e)}")

        results.append({
            "data": record,
            "extra_data": {"source_files": [item['filename'] for item in text_contents]},
            "original_used_data": actual_data
        })

    debugLogger.info(f"Text mapping executed successfully for {len(results)} items")
    return results


def _convert_value(value: any, schema_type: str, schema_key: str) -> any:
    """
    Converts a value to the expected schema type.

    Args:
        value: The input value.
        schema_type: The schema type (e.g., "float", "date", "list").
        schema_key: The schema field name for logging.

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
    

    