"""
Project analyst configuration using column-based approach.
Extends the BaseAnalystConfig class for common functionality.
"""

import json
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

from src.trmeric_services.agents.functions.analyst.analyst_configs.base_config import BaseAnalystConfig
from src.trmeric_services.agents.functions.analyst.analyst_configs.project.project_row_maps import ROW_MAPPINGS
from src.trmeric_services.agents.functions.analyst.analyst_configs.project.project_pseudocolumns import PSEUDO_COLUMNS

# Security clauses remain the same
SEC_CLAUSES = ["tenant_id_id = {tenant_id}"]

# Single source of truth for all columns
COLUMNS = [
    # Core fields
    {"name": "id", "type": "int", "description": "Unique project identifier"},
    {"name": "title", "type": "str", "description": "Project name"},
    {"name": "description", "type": "str", "description": "Detailed description"},
    {"name": "state", "type": "str", "description": "Project state as either: Discovery, Planning, Execution"},
    {"name": "internal_project", "type": "bool", "description": "Internal project flag"},
    {"name": "project_category", "type": "str", "description": "Project category"},
    {"name": "project_location", "type": "str", "description": "Project location"},
    {"name": "project_type", "type": "str", "description": "Project type: (Innovate, Transform, Run)"},
    
    {"name": "scope_status", "type": "str", "description": "Scope status: (on_track, at_risk)"},
    {"name": "spend_status", "type": "str", "description": "Scope status: (on_track, compromised)"},
    {"name": "technology_stack", "type": "str", "description": "Technology stack - comma separated string"},
    {"name": "total_external_spend", "type": "float", "description": "Total external spend"},
    {"name": "objectives", "type": "str", "description": "Project objectives in a list"},
    {"name": "sdlc_method", "type": "str", "description": "SDLC method categorization: (Hybrid, Waterfall, Agile)"},
    {"name": "member_roles", "type": "str", "description": "Member roles - comma separated string of members needed for this project and their roles"},
    {"name": "org_strategy_align", "type": "str", "description": "Strategy alignment"},
    # Portfolio fields
    {"name": "portfolio_id_id", "type": "int", "description": "Portfolio identifier"},
    {"name": "is_program", "type": "bool", "description": "flag if project is a program"},
]

COLUMNS.extend(PSEUDO_COLUMNS)

class ProjectConfig(BaseAnalystConfig):
    """Project-specific implementation of the analyst configuration."""
    
    def __init__(self):
        """Initialize the project configuration."""
        super().__init__(
            columns=COLUMNS,
            security_clauses=SEC_CLAUSES,
            table_name="workflow_project",
            entity_name="project",
            id_field="id",
            table_alias="wp", 
            cluster_column_name="objectives"  
        )
    
    def _build_system_prompt(self, valid_entities, query, subgoal, analysis_reason, 
                             current_date, analysis_plan, available_roles, df_analysis=None):
        """Build system prompt for project evaluation."""
        return f"""
        # Strategic Project Analysis Expert (Markdown Output)

        You are a senior strategy consultant specializing in portfolio and project analysis.
        Your job is to analyze the following projects and produce a cohesive, insightful markdown report for a fellow expert.

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

        ## Project Data
        The following is the project data for the current batch to be analyzed (no truncation):
        {json.dumps(valid_entities, indent=2)}

        ## Output Instructions
        - Write a markdown report (no JSON, no code blocks, no raw data dumps)
        - Reference specific project names, priorities, timelines, budgets, constraints, and any other relevant fields
        - Synthesize actionable, non-obvious insights about timing, strategic value, resource allocation, risks, and opportunities
        - Highlight portfolio-level patterns and cross-project relationships
        - Reference the quantitative analysis results when relevant to provide context for your insights
        - End with 1-2 actionable recommendations for the user
        - Do not repeat database field names unless needed for clarity
        - Do not truncate or summarize the input data; use all details as needed
        - Remember: Your insights should leverage both the batch data you can see AND the quantitative analysis of the full dataset
        """
    
    def _build_user_prompt(self, len_entities, analysis_reason):
        """Build user prompt for project evaluation."""
        return f"""
        Please analyze these {len_entities} projects, focusing on:
        1. {analysis_reason}
        2. Portfolio-level patterns and opportunities
        3. Resource optimization and risk mitigation
        4. Any other non-obvious insights
        """

# Create an instance for export
project_config = ProjectConfig()

# Export the configuration dictionary compatible with GeneralAnalyst
project_config_dict = {
    "columns": COLUMNS,
    "field_mapping": project_config.build_nested_json,
    "get_query": project_config.get_query,
    "eval_prompt_template": project_config.eval_prompt_template,
    "fetch_data": project_config.fetch_data,
    "cluster_func": project_config.cluster_func,
    "id_field": "id",
    "row_mapping": ROW_MAPPINGS,
}