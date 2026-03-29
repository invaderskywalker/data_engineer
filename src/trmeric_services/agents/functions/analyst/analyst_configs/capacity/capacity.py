"""
Project analyst configuration using column-based approach.
Extends the BaseAnalystConfig class for common functionality.
"""

import json
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

from src.trmeric_services.agents.functions.analyst.analyst_configs.base_config import BaseAnalystConfig
from src.trmeric_services.agents.functions.analyst.analyst_configs.capacity.capacity_row_maps import ROW_MAPPINGS
from src.trmeric_services.agents.functions.analyst.analyst_configs.capacity.capacity_pseudocolumns import PSEUDO_COLUMNS

# Security clauses remain the same
SEC_CLAUSES = ["tenant_id = {tenant_id}"]

# Single source of truth for all columns
COLUMNS = [
    # Core fields
    {"name": "id", "type": "int", "description": "Unique Person identifier"},
    {"name": "first_name", "type": "str", "description": "First name"},
    {"name": "last_name", "type": "str", "description": "Last name"},
    {"name": "country", "type": "str", "description": "Country"},
    {"name": "email", "type": "str", "description": "Email address"},
    {"name": "role", "type": "str", "description": "Role in the organization"},
    {"name": "skills", "type": "str", "description": "Skills - comma separated list"},
    {"name": "allocation", "type": "int", "description": "Allocation percentage"},
    {"name": "experience_years", "type": "int", "description": "Years of experience"},
    {"name": "experience", "type": "str", "description": "Experience description of previous work"},
    {"name": "projects", "type": "str", "description": "Projects working on - comma separated list"},
    {"name": "is_active", "type": "bool", "description": "Active status"},
    {"name": "is_external", "type": "bool", "description": "External resource flag"},
]

COLUMNS.extend(PSEUDO_COLUMNS)

class CapacityConfig(BaseAnalystConfig):
    """Project-specific implementation of the analyst configuration."""
    
    def __init__(self):
        """Initialize the project configuration."""
        super().__init__(
            columns=COLUMNS,
            security_clauses=SEC_CLAUSES,
            table_name="capacity_resource",
            entity_name="capacity",
            id_field="id",
            table_alias="cr", 
            cluster_column_name="projects" 
        )
    
    # get_query method is now inherited from BaseAnalystConfig
    
    def _build_system_prompt(self, valid_entities, query, subgoal, analysis_reason, 
                             current_date, analysis_plan, available_roles, df_analysis=None):
        """Build system prompt for project evaluation."""
        return f"""
        # Strategic Resource Analysis Expert (Markdown Output)

        You are a senior strategy consultant specializing in workforce and capacity analysis.
        Your job is to analyze the following employee data and produce a cohesive, insightful markdown report for a fellow expert.

        ## Context
        - General Goal: {query}
        - Subgoal: {subgoal or query}
        - Analysis Purpose: {analysis_reason}
        - Current Date: {current_date}
        - Analysis Plan: {json.dumps(analysis_plan, indent=2)}
        - Available Roles: {json.dumps(available_roles, indent=2)}

        ## Important Note About Batched Processing
        You are currently analyzing only a subset (batch) of the complete dataset. The numerical/statistical calculations below were performed on the ENTIRE dataset, not just the batch you can see. Use these calculations to inform your analysis of the batch you have, but understand they reflect the full dataset.

        ## Data Analysis Results - These are IMPORTANT CALCULATIONS. If anything here is pertinent to your subgoal, emphasize it. This is general for the entire dataset. 
        If the subgoal is asking for a calculation like a mean or standard deviation, and it is provided here, emphasize this as your answer in this response. You should bold this answer or create a section for it.
        {df_analysis if df_analysis else "No quantitative analysis was performed on this data."}

        ## Employee Data
        The following is the employee data for the current batch to be analyzed (no truncation):
        {json.dumps(valid_entities, indent=2)}

        ## Output Instructions
        - Write a markdown report (no JSON, no code blocks, no raw data dumps)
        - Reference specific employee names, roles, skills, allocation, experience, and any other relevant fields from the Employee Data section.
        - Synthesize actionable, non-obvious insights about skill gaps, resource allocation, experience levels, potential risks, and opportunities for development or reassignment.
        - Highlight workforce-level patterns and cross-functional relationships.
        - Reference the quantitative analysis results when relevant to provide context for your insights (e.g., average allocation, distribution of experience years).
        - End with 1-2 actionable recommendations for the user related to capacity planning, talent development, or resource optimization.
        - Do not repeat database field names unless needed for clarity.
        - Do not truncate or summarize the input data; use all details as needed.
        - Remember: Your insights should leverage both the batch data you can see AND the quantitative analysis of the full dataset.
        """
    
    def _build_user_prompt(self, len_entities, analysis_reason):
        """Build user prompt for project evaluation."""
        return f"""
        Please analyze these {len_entities} employees, focusing on:
        1. {analysis_reason}
        """
    
    # cluster_func method is now inherited from BaseAnalystConfig

# Create an instance for export
capacity_config = CapacityConfig()

# Export the configuration dictionary compatible with GeneralAnalyst
capacity_config_dict = {
    "columns": COLUMNS,
    "field_mapping": capacity_config.build_nested_json,
    "get_query": capacity_config.get_query,
    "eval_prompt_template": capacity_config.eval_prompt_template,
    "fetch_data": capacity_config.fetch_data,
    "cluster_func": capacity_config.cluster_func,
    "id_field": "id",
    "row_mapping": ROW_MAPPINGS,
}