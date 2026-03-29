"""
Roadmap analyst configuration using column-based approach.
Extends the BaseAnalystConfig class for common functionality.
"""

import json
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

from src.trmeric_services.agents.functions.analyst.analyst_configs.base_config import BaseAnalystConfig
from src.trmeric_services.agents.functions.analyst.analyst_configs.roadmap.roadmap_row_maps import ROW_MAPPINGS
from src.trmeric_services.agents.functions.analyst.analyst_configs.roadmap.roadmap_pseudocolumns import PSEUDO_COLUMNS
# Security clauses remain the same
SEC_CLAUSES = ["tenant_id = {tenant_id}"]

# Single source of truth for all columns
COLUMNS = [
    # Core fields
    {"name": "id", "type": "int", "description": "Unique roadmap identifier"},
    {"name": "title", "type": "str", "description": "Roadmap name"},
    {"name": "description", "type": "str", "description": "Detailed description of roadmap"},
    {"name": "objectives", "type": "str", "description": "Roadmap objectives"},
    {"name": "type", "type": "int", "description": "Roadmap Type (Program, Project, Enhancement)", 
    "value_mapping": {
        1: "Program",
        2: "Project",
        3: "Enhancement"
    }},
    {"name": "priority", "type": "int", "description": "Priority (1=High, 2=Medium, 3=Low)", 
    "value_mapping": {
        1: "High",
        2: "Medium",
        3: "Low"
    }},
    # Dates and timing
    {"name": "start_date", "type": "date", "description": "Start date"},
    {"name": "end_date", "type": "date", "description": "End date"},
    {"name": "min_time_value", "type": "int", "description": "The numerical value of the minimum time to complete this roadmap"},
    {"name": "min_time_value_type", "type": "int", "description": "Time value type (1=days, 2=weeks, 3=months, 4=years) for the min_time_value. Always use this when you use min_time_value", 
    "value_mapping": {
        1: "days",
        2: "weeks",
        3: "months",
        4: "years"
    }},    
    {"name": "budget", "type": "float", "description": "Budget amount"},   

    {"name": "category", "type": "str", "description": "Roadmap categories - comma separated list"},
    {"name": "org_strategy_align", "type": "str", "description": "Describes how the roadmap aligns with the organization's general strategy"},
    {"name": "business_case", "type": "json", "description": "The justification for this roadmap on the basis of business value"},

    {"name": "total_capital_cost", "type": "float", "description": "Total capital cost"},
    {"name": "tango_analysis", "type": "json", "description": "Reasoning for the scopes, timelines, portfolio, labor_team, objectives, constraints, key results, category, ..."}

]

COLUMNS.extend(PSEUDO_COLUMNS)

class RoadmapConfig(BaseAnalystConfig):
    """Roadmap-specific implementation of the analyst configuration."""
    
    def __init__(self):
        """Initialize the roadmap configuration."""
        super().__init__(
            columns=COLUMNS,
            security_clauses=SEC_CLAUSES,
            table_name="roadmap_roadmap",
            entity_name="roadmap",
            id_field="id",
            table_alias="rr", 
            cluster_column_name="objectives"  
        )
    
    def _build_system_prompt(self, valid_entities, query, subgoal, analysis_reason, 
                           current_date, analysis_plan, available_roles, df_analysis=None):
        """Build system prompt for roadmap evaluation."""
        return f"""
        # Strategic Roadmap Analysis Expert (Markdown Output)

        You are a senior strategy consultant specializing in portfolio and roadmap analysis. Roadmaps are future projects.
        Your job is to analyze the following roadmaps and produce a cohesive, insightful markdown report for a fellow expert.

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

        ## Roadmap Data
        The following is the full data for the current batch of roadmaps to be analyzed (no truncation):
        {json.dumps(valid_entities, indent=2)}

        ## Output Instructions
        - Write a markdown report (no JSON, no code blocks, no raw data dumps)
        - Focus on strategic value, market impact, and portfolio alignment
        - Reference specific roadmap names, objectives, constraints, and key results
        - Analyze resource allocation, timing, and dependencies
        - Highlight portfolio-level patterns and strategic opportunities
        - Consider team composition and capacity planning
        - Reference the quantitative analysis results when relevant to provide context for your insights
        - End with 1-2 actionable recommendations
        - Do not repeat database field names unless needed for clarity
        - Remember: Your insights should leverage both the batch data you can see AND the quantitative analysis of the full dataset
        """
    
    def _build_user_prompt(self, len_entities, analysis_reason):
        """Build user prompt for roadmap evaluation."""
        return f"""
        Please analyze these {len_entities} roadmaps, focusing on:
        1. {analysis_reason}
        2. Resource allocation and timing optimization
        3. Key results and objective alignment
        4. Strategic opportunities and risks
        """

# Create an instance for export
roadmap_config = RoadmapConfig()

# Export the configuration dictionary compatible with GeneralAnalyst
roadmap_config_dict = {
    "columns": COLUMNS,
    "field_mapping": roadmap_config.build_nested_json,
    "get_query": roadmap_config.get_query,
    "eval_prompt_template": roadmap_config.eval_prompt_template,
    "fetch_data": roadmap_config.fetch_data,
    "cluster_func": roadmap_config.cluster_func,
    "id_field": "id",
    "row_mapping": ROW_MAPPINGS,
}