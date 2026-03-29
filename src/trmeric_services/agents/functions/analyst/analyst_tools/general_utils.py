"""Utility functions for analyst operations."""

import pandas as pd
import numpy as np
import tiktoken, json
import traceback
from typing import List, Dict, Any
from src.trmeric_api.logging.AppLogger import appLogger


def build_user_context(base_agent) -> str:
    """Build user context string from base agent if available."""
    if not base_agent:
        return ""
    
    context_parts = []
    
    # Add context string if available
    if hasattr(base_agent, 'context_string'):
        context_parts.append(base_agent.context_string)
        
    # Add organization info if available
    if hasattr(base_agent, 'org_info_string'):
        context_parts.append(base_agent.org_info_string)
        
    # Add user info if available
    if hasattr(base_agent, 'user_info_string'):
        context_parts.append(base_agent.user_info_string)
        
    return "\n".join(filter(None, context_parts))

def build_row_mapping_args(arguments: List[str], tenant_id: str, user_id: str) -> Dict[str, str]:
    """Build arguments for row mapping based on provided parameters."""
    args = {}
    for argument in arguments:
        if argument == "tenant_id":
            args[argument] = tenant_id
        elif argument == "user_id":
            args[argument] = user_id
    return args

def build_row_mapping(row_mapping: List[Dict], tenant_id: str, user_id: str, mapping_cache: Dict = None) -> List[Dict]:
    """Builds and returns structured row mapping info for the query optimizer."""
    mappings = []
    if not row_mapping:
        return mappings
        
    # Cache key based on tenant and user
    cache_key = f"row_mapping_{tenant_id}_{user_id}"
    
    # Try to get from cache if provided
    if mapping_cache is not None and cache_key in mapping_cache:
        print("[GeneralAnalyst] Using cached row mappings")
        return mapping_cache[cache_key]

    try:
        for mapping in row_mapping:
            # Skip invalid mappings
            if not all(k in mapping for k in ["name", "columns", "data", "args", "type", "description"]):
                print(f"[GeneralAnalyst] Warning: Skipping invalid mapping: {mapping}")
                continue
                
            # Build args and get values
            try:
                args = build_row_mapping_args(mapping.get("args", []), tenant_id, user_id)
                func = mapping.get("data")
                values = func(**args) if func and callable(func) else []
                print(values)
                
                # Skip if no values returned
                if not values:
                    print(f"[GeneralAnalyst] Warning: No values returned for mapping: {mapping['name']}")
                    continue
                
                columns = mapping.get("columns", [])
                columns_with_id = []
                for i in range(len(columns)):
                    columns_with_id.append({"id": i, "column": columns[i]})
                                        
                mapping_info = {
                    "name": mapping.get("name"),
                    "columns": columns_with_id,
                    "type": mapping.get("type", "exact"),
                    "description": mapping.get("description", ""),
                    "values": values,
                }
                
                mappings.append({"mapping_id": len(mappings), "mapping_info": mapping_info})
            except Exception as e:
                print(f"[GeneralAnalyst] Error building mapping {mapping.get('name')}: {str(e)}")
                continue
                
        # Store in cache if provided
        if mapping_cache is not None:
            mapping_cache[cache_key] = mappings
        print(mappings)
        return mappings
        
    except Exception as e:
        print(f"[GeneralAnalyst] Error building row mappings: {str(e)}")
        return []

def calculate_available_roles(all_roles_count_master_data: List[Dict], all_roles_consumed_for_tenant: List[Dict]) -> Dict:
    """Calculate available roles based on total and allocated counts."""
    # Create dictionaries of role counts
    master_dict = {role["role"]: role["total_count"] for role in all_roles_count_master_data}
    allocated_dict = {role["role"]: role["allocated_count"] for role in all_roles_consumed_for_tenant}
    all_roles = set(master_dict.keys()) | set(allocated_dict.keys())
    
    # Calculate available roles (never negative)
    return {
        role: max(master_dict.get(role, 0) - allocated_dict.get(role, 0), 0)
        for role in all_roles
    }

def sanitize_data(data: List[Dict]) -> List[Dict]:
    """Sanitize a list of dictionaries for JSON serialization."""
    return [sanitize_item(item) for item in data]

def sanitize_item(item: Dict) -> Dict:
    """Sanitize a dictionary for JSON serialization."""
    if not isinstance(item, dict):
        return item
        
    result = {}
    for key, value in item.items():
        if isinstance(value, (list, tuple)):
            result[key] = [sanitize_item(v) if isinstance(v, dict) else sanitize_scalar(v) for v in value]
        elif isinstance(value, dict):
            result[key] = sanitize_item(value)
        else:
            result[key] = sanitize_scalar(value)
    return result

def sanitize_scalar(value: Any) -> Any:
    """Convert non-serializable scalar values to serializable ones."""
    try:
        if isinstance(value, (pd.Series, np.ndarray)):
            return [sanitize_scalar(v) for v in value]
        elif pd.isna(value):  # Handles NaN and NaT
            return None
        elif isinstance(value, (pd.Timestamp, pd.Timedelta)):
            return str(value)
        return value
    except Exception as e:
        appLogger.error(f"Error sanitizing scalar: {str(e)}")
        return None

def estimate_tokens(text: str, model: str = "gpt-4o") -> int:
    """Estimate token count using tiktoken."""
    try:
        enc = tiktoken.encoding_for_model(model)
        return len(enc.encode(text))
    except (KeyError, ValueError) as e:
        appLogger.error(f"Error estimating tokens: {str(e)}")
        # Fallback encoding
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception as e2:
            appLogger.error(f"Fallback encoding error: {str(e2)}")
            return 0

def emit_table_to_ui(data: List[Dict], socketio=None, client_id=None, analyst_key=None, id_field=None):
    """Emit table data to UI after query optimization."""
    try:
        if not data or not isinstance(data, list):
            print("[GeneralAnalyst] No valid data to emit")
            return

        # Remove id field from each row
        processed_data = []
        for item in data:
            if id_field and id_field in item:
                item = dict(item)
                item.pop(id_field, None)
            processed_data.append(item)

        if socketio and client_id:
            # Get the base entity type from analyst key (e.g., 'roadmap' from 'roadmap_analyst')
            entity_type = analyst_key.replace('_analyst', '')
            socketio.emit("tango_ui", 
                {
                    "event": f"roadmap_analysis",
                    "component": "table",
                    "data": processed_data,
                    "response_instruction": "Filtered data",
                    "partial": False
                },
                room=client_id
            )
    except Exception as e:
        appLogger.error(f"Error emitting table: {str(e)}\n{traceback.format_exc()}")

def generator_cleaner(analysis_result):
    if isinstance(analysis_result, str):
        return [analysis_result]
    elif isinstance(analysis_result, list) and all(isinstance(item, str) for item in analysis_result):
        return analysis_result
    elif isinstance(analysis_result, list): # Handle list of dicts or other structures if eval returns that
            # Attempt to convert to string representation, might need refinement based on actual eval output
        return [json.dumps(analysis_result, indent=2)]
    else:
        # Fallback for unexpected types
        return [str(analysis_result)]

