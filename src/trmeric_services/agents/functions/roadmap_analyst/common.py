

import tiktoken
from typing import Any, List, Optional, Dict
import json
from datetime import date
import pandas as pd
import numpy as np
import re


class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.isoformat()  # Convert date to string (e.g., '2025-06-07')
        return super().default(obj)

def clean_raw_data(raw_data: list[dict]) -> list[dict]:
    try:
        cleaned_data = []
        for record in raw_data:
            cleaned_record = {
                k: v
                for k, v in record.items()
                if v not in (None, "", " ", "null", "None")
                and not (isinstance(v, (list, dict)) and len(v) == 0)
            }

            if cleaned_record:
                cleaned_data.append(cleaned_record)
        return cleaned_data
    except Exception as e:
        print(f"Error in clean_raw_data: {e}")
        return raw_data

# Updated sanitize_html function to remove ALL HTML tags
def sanitize_html(text):
    if not isinstance(text, str):
        return text
    # Remove all HTML tags
    clean_text = re.sub(r'<[^>]+>', '', text, flags=re.IGNORECASE)
    # Remove dangerous attributes (in case they appear outside tags)
    dangerous_attributes = r'\s*(on\w+|style|class|id|data-[^=]+)\s*=\s*["\'][^"\']*["\']'
    clean_text = re.sub(dangerous_attributes, '', clean_text, flags=re.IGNORECASE)
    # Remove inline JavaScript
    clean_text = re.sub(r'javascript:[^"\']*["\']', '', clean_text, flags=re.IGNORECASE)
    # Remove HTML comments
    clean_text = re.sub(r'<!--[\s\S]*?-->', '', clean_text)
    # Normalize whitespace
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    return clean_text

# Helper function to clean strings of control characters
def clean_string(text):
    if not isinstance(text, str):
        return text
    # Remove control characters (ASCII 0-31, except 9, 10, 13 for tab, newline, carriage return)
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)


# Clean text function (unchanged)
def clean_text(text):
    if isinstance(text, str):
        text = re.sub(r'[^\x00-\x7F]+', ' ', text)  # Replace non-ASCII characters
        text = text.replace('¬†', ' ').replace('‚Äã', '')  # Replace specific artifacts
        text = re.sub(r'/', ' ', text)  # Replace forward slashes with a space
        text = clean_string(text)  # Remove control characters
        return text.strip()
    return text

# --- Utility Functions ---
def sanitize_data(data):
    """Sanitize data for JSON serialization."""
    for item in data:
        for key, value in item.items():
            if isinstance(value, (list, tuple)):
                item[key] = [sanitize_item(v) if isinstance(v, dict) else sanitize_scalar(v) for v in value]
            elif isinstance(value, dict):
                item[key] = sanitize_item(value)
            else:
                item[key] = sanitize_scalar(value)
    return data


def sanitize_item(item):
    """Sanitize a single dictionary."""
    if isinstance(item, dict):
        for k, v in item.items():
            item[k] = sanitize_scalar(v)
    return item


def sanitize_scalar(value):
    """Handle NaN, NaT, and arrays."""
    if isinstance(value, (pd.Series, np.ndarray)):
        return [sanitize_scalar(v) for v in value]
    elif isinstance(value, (list, tuple)):
        return [sanitize_scalar(v) for v in value]
    elif pd.isna(value):
        return None
    elif isinstance(value, (pd.Timestamp, pd.Timedelta)):
        return str(value)
    return value


def calculate_available_roles(all_roles_count_master_data, all_roles_consumed_for_tenant):
    """Computes available roles by subtracting consumed roles from master count."""
    master_data_dict = {role["role"]: role["total_count"] for role in all_roles_count_master_data}
    allocated_roles_dict = {role["role"]: role["allocated_count"] for role in all_roles_consumed_for_tenant}
    all_roles = set(master_data_dict.keys()).union(set(allocated_roles_dict.keys()))
    available_roles = {}
    for role in all_roles:
        total_count = master_data_dict.get(role, 0)
        allocated_count = allocated_roles_dict.get(role, 0)
        available_roles[role] = max(total_count - allocated_count, 0)
    return available_roles

def estimate_tokens(text, model="gpt-4o") -> int:
    """Estimate token count using OpenAI's tokenizer."""
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))



def format_project_data_all_components(
    data: Any,
    verbose: bool = False,
    indent_level: int = 0,
    schema: Optional[Dict] = None,
    max_text_length: int = 400,
    separator: str = "------------project separator -----------",
    internal_separator: str = "----"
) -> str:
    """
    Process an input array or data structure into a single markdown-formatted string.
    All attributes are listed as indented key-value pairs, with project items separated by a divider
    and nested array sub-items separated by an internal divider. Top-level items are labeled
    'Project Item X', while nested array items are labeled 'Item X'.

    Args:
        data (Any): Input data (list, dict, str, etc.).
        verbose (bool): If True, include full details for nested structures; otherwise, summarize.
        indent_level (int): Current indentation level (used for recursion).
        schema (Optional[Dict]): Optional schema to guide dictionary field processing (e.g., PROJECT_SCHEMA).
        max_text_length (int): Maximum length for text fields before truncation.
        separator (str): Separator between top-level project items in the output string.
        internal_separator (str): Separator between sub-items within nested arrays (e.g., status_comments, risks).

    Returns:
        str: A single markdown-formatted string with project items separated by the specified separator
             and nested array sub-items separated by the internal separator.
    """
    formatted_lines = []
    indent = "  " * indent_level

    # Handle non-list inputs by wrapping in a list
    if not isinstance(data, list):
        data = [data]

    # Process each item in the list
    for index, item in enumerate(data, 1):
        # Use 'Project Item' for top-level, 'Item' for nested
        item_label = "Project Item" if indent_level == 0 else "Item"
        item_lines = [f"{indent}**{item_label} {index}**:"]
        indent_inner = indent + "  "

        if isinstance(item, dict):
            # Use schema fields if provided, else all keys
            fields = schema["fields"].keys() if schema else item.keys()

            # Process scalar fields (non-list/dict)
            scalar_fields = [f for f in fields if not isinstance(item.get(f), (list, dict))]
            for field in scalar_fields:
                value = item.get(field, "N/A")
                if isinstance(value, (int, float)):
                    if field in ["planned_spend", "actual_spend", "project_budget"]:
                        value = f"${value:,.2f}"
                    elif field == "percent_complete":
                        value = f"{value:.0f}%"
                elif isinstance(value, str) and len(value) > max_text_length and not verbose:
                    value = value[:max_text_length] + "..."
                field_name = field.replace('_', ' ').title()
                # Handle multi-line values (e.g., project_objectives)
                value_lines = str(value).split('\n')
                if len(value_lines) > 1:
                    item_lines.append(f"{indent_inner}**{field_name}**: {value_lines[0]}")
                    for line in value_lines[1:]:
                        item_lines.append(f"{indent_inner}{line}")
                else:
                    item_lines.append(f"{indent_inner}**{field_name}**: {value}")

            # Process nested fields (lists or dicts)
            nested_fields = [f for f in fields if isinstance(item.get(f), (list, dict))]
            for field in nested_fields:
                value = item.get(field, [])
                field_name = field.replace('_', ' ').title()
                item_lines.append(f"{indent_inner}**{field_name}**:")

                if isinstance(value, list):
                    if not value:
                        item_lines.append(f"{indent_inner}  *None*")
                    elif verbose:
                        # Recursively format nested list as indented key-value pairs
                        nested_lines = format_project_data_all_components(
                            value, verbose=verbose, indent_level=indent_level + 2, schema=None,
                            max_text_length=max_text_length, separator=separator,
                            internal_separator=internal_separator
                        )
                        # Split nested lines into sub-items and add internal separator
                        sub_items = nested_lines.split(f"\n{separator}\n")
                        item_lines.append(f"{indent_inner}  {sub_items[0]}")
                        for sub_item in sub_items[1:]:
                            item_lines.append(f"{indent_inner}  {internal_separator}")
                            item_lines.append(f"{indent_inner}  {sub_item}")
                    else:
                        # Summarize nested list
                        if field == "status_comments" and value:
                            latest_comment = max(value, key=lambda c: c.get('timestamp', ''), default=None)
                            if latest_comment and isinstance(latest_comment, dict):
                                comment = latest_comment.get('comment', 'N/A')
                                if len(comment) > max_text_length:
                                    comment = comment[:max_text_length] + "..."
                                timestamp = latest_comment.get('timestamp', 'N/A')
                                item_lines.append(f"{indent_inner}  *Latest Comment*: {comment} ({timestamp})")
                            item_lines.append(f"{indent_inner}  *Total Comments*: {len(value)}")
                        elif field == "risks" and value:
                            active_risks = [r for r in value if isinstance(r, dict) and r.get('status_value') != 'completed']
                            high_priority = sum(1 for r in active_risks if isinstance(r, dict) and r.get('priority') == '1')
                            item_lines.append(f"{indent_inner}  *Active Risks*: {len(active_risks)} (*High Priority*: {high_priority})")
                        else:
                            item_lines.append(f"{indent_inner}  *Count*: {len(value)}")
                elif isinstance(value, dict):
                    # Recursively format nested dict as indented key-value pairs
                    nested_lines = format_project_data_all_components(
                        [value], verbose=verbose, indent_level=indent_level + 2, schema=None,
                        max_text_length=max_text_length, separator=separator,
                        internal_separator=internal_separator
                    )
                    item_lines.append(f"{indent_inner}  {nested_lines}")
                else:
                    item_lines.append(f"{indent_inner}  *Value*: {value}")

        elif isinstance(item, list):
            item_lines.append(f"{indent_inner}**List**:")
            if verbose and item:
                nested_lines = format_project_data_all_components(
                    item, verbose=verbose, indent_level=indent_level + 2, schema=None,
                    max_text_length=max_text_length, separator=separator,
                    internal_separator=internal_separator
                )
                # Split nested lines into sub-items and add internal separator
                sub_items = nested_lines.split(f"\n{separator}\n")
                item_lines.append(f"{indent_inner}  {sub_items[0]}")
                for sub_item in sub_items[1:]:
                    item_lines.append(f"{indent_inner}  {internal_separator}")
                    item_lines.append(f"{indent_inner}  {sub_item}")
            else:
                item_lines.append(f"{indent_inner}  *Count*: {len(item)}")

        elif isinstance(item, (str, int, float, bool)) or item is None:
            value = item if item is not None else "N/A"
            if isinstance(value, float):
                value = f"{value:.2f}"
            elif isinstance(value, str) and len(value) > max_text_length and not verbose:
                value = value[:max_text_length] + "..."
            item_lines.append(f"{indent_inner}**Value**: {value}")

        else:
            item_lines.append(f"{indent_inner}**Value**: {str(item)}")

        formatted_lines.append("\n".join(item_lines))

    # Join all project items with the separator
    return f"\n{separator}\n".join(formatted_lines) if formatted_lines else f"{indent}*No valid data found.*"




