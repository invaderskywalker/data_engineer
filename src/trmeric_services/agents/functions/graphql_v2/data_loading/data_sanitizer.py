"""
Data Sanitizer

Utilities for cleaning and validating data before loading into TigerGraph.
"""

from typing import Dict, List, Any
from datetime import datetime, date
import json
from ..infrastructure.trmeric_schema import (
    INT_FIELDS,
    DOUBLE_FIELDS,
    LIST_STRING_FIELDS,
    LIST_DOUBLE_FIELDS,
)


class DataSanitizer:
    """Utilities for sanitizing data before graph loading."""
    
    # Use canonical list-of-string fields defined in the schema module
    LIST_FIELDS = set(LIST_STRING_FIELDS)
    

    EXCLUDED_FIELDS = {
        "CustomerSummaryProfile": {"timestamp"}
    }
    
    @staticmethod
    def sanitize_values(data: Dict[str, Any], vertex_type: str = None, datetime_fields: List[str] = None) -> Dict[str, Any]:
        """
        Sanitize dictionary values for TigerGraph loading.
        
        Args:
            data: Dictionary to sanitize
            vertex_type: Type of vertex for context-specific sanitization
            datetime_fields: List of keys that should be treated as datetime fields
            
        Returns:
            Sanitized dictionary
        """
        if datetime_fields is None:
            datetime_fields = ["start_date", "end_date", "target_date", "actual_date", "created_date", "due_date"]
        
        # Get excluded fields for this vertex type
        excluded = DataSanitizer.EXCLUDED_FIELDS.get(vertex_type, set())
        
        sanitized = {}
        for k, v in data.items():
            # Skip excluded fields
            if k in excluded:
                continue

            # Datetime fields handling
            if k in datetime_fields and v is None:
                sanitized[k] = None
                continue

            # None handling with schema-aware defaults
            if v is None:
                if k in INT_FIELDS:
                    sanitized[k] = 0
                elif k in DOUBLE_FIELDS:
                    sanitized[k] = 0.0
                elif k in LIST_STRING_FIELDS or k in LIST_DOUBLE_FIELDS:
                    sanitized[k] = []
                else:
                    sanitized[k] = ""
                continue

            # Datetime objects
            if isinstance(v, (datetime, date)):
                sanitized[k] = v.isoformat()
                continue

            # Integer fields
            if k in INT_FIELDS:
                try:
                    sanitized[k] = int(v)
                except (ValueError, TypeError):
                    # Fallback to 0
                    sanitized[k] = 0
                continue

            # Double/float fields
            if k in DOUBLE_FIELDS:
                try:
                    sanitized[k] = float(v)
                except (ValueError, TypeError):
                    sanitized[k] = 0.0
                continue

            # List of strings
            if k in LIST_STRING_FIELDS:
                # Accept lists, JSON strings, or comma-separated strings
                if isinstance(v, list):
                    sanitized[k] = [str(item).strip() for item in v if item is not None and str(item).strip()]
                elif isinstance(v, str):
                    try:
                        parsed = json.loads(v)
                        if isinstance(parsed, list):
                            sanitized[k] = [str(item).strip() for item in parsed if item is not None and str(item).strip()]
                        else:
                            # treat as comma-separated
                            sanitized[k] = [s.strip() for s in v.split(",") if s.strip()]
                    except (json.JSONDecodeError, ValueError):
                        sanitized[k] = [s.strip() for s in v.split(",") if s.strip()]
                else:
                    sanitized[k] = [str(v)]
                continue

            # List of doubles
            if k in LIST_DOUBLE_FIELDS:
                if isinstance(v, list):
                    out = []
                    for item in v:
                        try:
                            out.append(float(item))
                        except (ValueError, TypeError):
                            continue
                    sanitized[k] = out
                elif isinstance(v, str):
                    try:
                        parsed = json.loads(v)
                        if isinstance(parsed, list):
                            out = []
                            for item in parsed:
                                try:
                                    out.append(float(item))
                                except (ValueError, TypeError):
                                    continue
                            sanitized[k] = out
                        else:
                            # comma-separated
                            sanitized[k] = [float(s) for s in v.split(",") if s.strip()]
                    except (json.JSONDecodeError, ValueError):
                        try:
                            sanitized[k] = [float(s) for s in v.split(",") if s.strip()]
                        except Exception:
                            sanitized[k] = []
                else:
                    try:
                        sanitized[k] = [float(v)]
                    except Exception:
                        sanitized[k] = []
                continue

            # Strings (fallback)
            if isinstance(v, str):
                sanitized[k] = v.strip()
                continue

            # Lists not in schema list fields -> convert to JSON string
            if isinstance(v, list):
                sanitized[k] = json.dumps(v)
                continue

            # Dicts -> JSON string
            if isinstance(v, dict):
                sanitized[k] = json.dumps(v)
                continue

            # Numbers and other primitives fall through
            sanitized[k] = v

        return sanitized
    
    @staticmethod
    def validate_vertex_data(vertex_id: Any, attributes: Dict[str, Any], vertex_type: str) -> bool:
        """
        Validate vertex data before loading.
        
        Args:
            vertex_id: Vertex identifier
            attributes: Vertex attributes
            vertex_type: Type of vertex
            
        Returns:
            True if valid, False otherwise
        """
        # Ensure vertex_id is not None
        if vertex_id is None or str(vertex_id).strip() == "":
            print(f"Invalid vertex_id for {vertex_type}: {vertex_id}")
            return False
        
        # Ensure required ID field exists in attributes
        if "id" in attributes and (attributes["id"] is None or str(attributes["id"]).strip() == ""):
            print(f"Invalid id attribute for {vertex_type}: {attributes.get('id')}")
            return False
        
        return True
    
    @staticmethod
    def clean_string_field(value: Any, default: str = "Unknown") -> str:
        """
        Clean string field, replacing None or empty strings with default.
        
        Args:
            value: Value to clean
            default: Default value if cleaning needed
            
        Returns:
            Cleaned string
        """
        if value is None:
            return default
        str_value = str(value).strip()
        return str_value if str_value else default
    
    @staticmethod
    def clean_numeric_field(value: Any, default: float = 0.0) -> float:
        """
        Clean numeric field, replacing None with default.
        
        Args:
            value: Value to clean
            default: Default value if cleaning needed
            
        Returns:
            Cleaned numeric value
        """
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def clean_json_comments(comments: Any) -> str:
        """
        Clean comments field that might be JSON encoded.
        
        Args:
            comments: Raw comments value
            
        Returns:
            Cleaned comments string
        """
        if isinstance(comments, str):
            try:
                json_comments = json.loads(comments)
                if isinstance(json_comments, dict):
                    return json_comments.get('comments', 'Unknown')
                return comments
            except json.JSONDecodeError:
                return comments
        elif comments is None:
            return "Unknown"
        else:
            return str(comments)
    
    @staticmethod
    def prepare_vertex_batch(data: List[tuple], vertex_type: str) -> List[tuple]:
        """
        Prepare vertex data for batch loading.
        
        Args:
            data: List of (vertex_id, attributes) tuples
            vertex_type: Type of vertex
            
        Returns:
            List of validated and sanitized (vertex_id, attributes) tuples
        """
        prepared = []
        for vertex_id, attrs in data:
            # Validate
            if not DataSanitizer.validate_vertex_data(vertex_id, attrs, vertex_type):
                continue
            
            # Sanitize (pass vertex_type for context-specific handling)
            sanitized_attrs = DataSanitizer.sanitize_values(attrs, vertex_type=vertex_type)
            prepared.append((vertex_id, sanitized_attrs))
        
        return prepared
    
    @staticmethod
    def prepare_edge_batch(data: List[tuple]) -> List[tuple]:
        """
        Prepare edge data for batch loading.
        
        Args:
            data: List of (source_id, target_id) tuples
            
        Returns:
            List of (source_id, target_id, {}) tuples with validated IDs
        """
        prepared = []
        for row in data:
            source_id, target_id = row[0], row[1]
            # Skip invalid edges
            if source_id is None or target_id is None:
                continue
            if str(source_id).strip() == "" or str(target_id).strip() == "":
                continue
            
            prepared.append((source_id, target_id, {}))
        
        return prepared
