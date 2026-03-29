"""
Response Cleaner - Processes Raw Graph Query Results

Cleans and groups raw GSQL results into structured dictionaries.
"""

from typing import Dict, List, Any


def clean_entity_response(
    raw_results: List[Dict], 
    entity_prefix: str = "proj"
) -> Dict[str, Dict[str, Any]]:
    """
    Clean and group entity-related data from raw GSQL results.
    
    Handles two formats:
    1. Simple vertex format: [{'entities': [{'v_id': '123', 'v_type': 'Project', 'attributes': {...}}]}]
    2. Complex format: [{"proj_2473": [...], "technology_2473": [...]}, ...]
    
    Args:
        raw_results: List of dictionaries from GSQL query
        entity_prefix: Prefix used for entity variables (e.g., "proj", "road")
        
    Returns:
        Dictionary where keys are entity IDs and values are entity data
        
    Example:
        Input: [{"proj_2473": [...], "technology_2473": [...]}, ...]
        Output: {"2473": {"id": "2473", "technology": [...]}, ...}
    """
    entities = {}
    
    # Check if we have the simple TigerGraph vertex format
    if raw_results and isinstance(raw_results[0], dict) and 'entities' in raw_results[0]:
        # Handle simple vertex format: [{'entities': [{...}]}]
        for block in raw_results:
            if 'entities' not in block:
                continue
            for vertex in block.get('entities', []):
                v_id = vertex.get('v_id')
                if not v_id:
                    continue
                
                # Extract attributes
                attrs = vertex.get('attributes', {})
                if not attrs:
                    continue
                
                # Create entity entry with all attributes
                entities[v_id] = {
                    'id': v_id,
                    'v_type': vertex.get('v_type', 'Unknown')
                }
                entities[v_id].update(attrs)
        
        return entities
    
    # Handle complex format with entity prefixes
    for block in raw_results:
        for key, entries in block.items():
            if not entries:
                continue
            
            # Extract entity ID from key like 'proj_2473', 'portfolio_2473'
            parts = key.split('_')
            if len(parts) < 2:
                continue
            
            entity_type = parts[0]  # e.g., 'proj', 'portfolio', 'technology'
            entity_id = parts[-1]
            
            # Initialize the entity entry if not already
            if entity_id not in entities:
                entities[entity_id] = {"id": entity_id}
            
            if entity_type == entity_prefix:
                # Top-level entity attributes
                for attr_key, attr_val in entries[0].get("attributes", {}).items():
                    # attr_key is like "proj_2473.title"
                    clean_key = attr_key.split(".")[-1]
                    entities[entity_id][clean_key] = attr_val
            
            else:
                # For related entities (portfolio, technology, etc.)
                entity_list = []
                for entry in entries:
                    clean_entity = {}
                    for attr_key, attr_val in entry.get("attributes", {}).items():
                        # attr_key is like "technology_2473.name"
                        clean_key = attr_key.split(".")[-1]
                        clean_entity[clean_key] = attr_val
                    entity_list.append(clean_entity)
                
                # Append to proper key (e.g., "portfolio", "technology")
                existing = entities[entity_id].get(entity_type, [])
                existing.extend(entity_list)
                entities[entity_id][entity_type] = existing
    
    return entities


def clean_project_response(raw_results: List[Dict]) -> Dict[str, Dict[str, Any]]:
    """
    Clean project query results.
    
    Args:
        raw_results: Raw GSQL results
        
    Returns:
        Cleaned project data dictionary
    """
    return clean_entity_response(raw_results, entity_prefix="proj")


def clean_roadmap_response(raw_results: List[Dict]) -> Dict[str, Dict[str, Any]]:
    """
    Clean roadmap query results.
    
    Args:
        raw_results: Raw GSQL results
        
    Returns:
        Cleaned roadmap data dictionary
    """
    return clean_entity_response(raw_results, entity_prefix="road")
