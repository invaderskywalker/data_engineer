from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional
from enum import Enum


DEFAULT_WEB_AGENT_PARAMS = {
    "web_queries_string": [""],
    # "website_web_queries_also_add_which_company_in_string": [],
    "website_urls": [""]
}

DEFAULT_COMPANY_PARAMS = {}
DEFAULT_COMPANY_INDUSTRY_PARAMS = {}
DEFAULT_COMPANY_PERFORMANCE_PARAMS = {"period": None}
DEFAULT_COMPETITOR_PARAMS = {"competitor_name": None}
DEFAULT_ENTERPRISE_STRATEGY_PARAMS = {"title": None}
DEFAULT_INDUSTRY_PARAMS = {"industry_ids": [], "name": None}
DEFAULT_SOCIAL_MEDIA_PARAMS = {"platform": None}
DEFAULT_ANALYZE_FILE_PARAMS = {"files_s3_keys_to_read": []}
DEFAULT_FETCH_SCHEMA_PARAMS = {"schema_type": None}
DEFAULT_S3_PARAMS = {"files_s3_keys_to_read": []}
DEFAULT_S3_FILE_PARAMS = {"files_s3_keys_to_read": []}
DEFAULT_INTEGRATION_DATA_PARAMS = {
    "integration_name": None,
    "project_ids": [],
    "user_detailed_query": ""
}
DEFAULT_SNAPSHOTS_PARAMS = {
    "snapshot_type": None,
    "last_quarter_start": None,
    "last_quarter_end": None,
    "user_chosen_portfolio_ids": None,
    "quarter_start": None,
    "quarter_end": None,
    "program_ids": [],
    "kwargs": {}
}

DEFAULT_PROVIDER_STOREFRONT_PARAMS = {
    "provider_ids": [],
    "data_sources_array": [
        "service_catalog", 
        "capabilities", 
        "case_studies", 
        "trmeric_assessment",
        "opportunities", 
        "win_themes",
        "provider_skills"
    ]
}

DEFAULT_PROVIDER_QUANTUM_PARAMS = {
    "provider_id": "",
    "service_provider_id": "",
    "data_sources_array": [
        "service_catalog", 
        "offers", 
        "ways_of_working", 
        "case_studies",
        "partnerships", 
        "certifications_and_audit", 
        "leadership_and_team",
        "voice_of_customer", 
        "information_and_security", 
        "aspiration",
        "core_capabilities",
    ]
}

DEFAULT_SOME_INFO_ABOUT_TRMERIC_PARAMS = {
    "queries_to_ask_for_vector_search": []
}

DEFAULT_CUSTOMER_SOLUTIONS_PARAMS = {}
DEFAULT_SESSION_UPLOADED_FILES_PARAMS = {}

DEFAULT_PARAMS_FOR_PROJECT_AGENT = {
    # "detailed_user_query": ""
    "use": False,
    # 🔑 Single cognitive hook
    "analysis_focus": ""
}

DEFAULT_PARAMS_FOR_ROADMAP_AGENT = {
    # "detailed_user_query": ""
    "use": False,
    # 🔑 Single cognitive hook
    "analysis_focus": ""
}

DEFAULT_PARAMS_FOR_COMBINED_AGENT = {
    "natural_language_text_to_query_roadmap_and_project_data": ""
}

DEFAULT_PARAMS_FOR_PROVIDER_OFFERS = {
    "provider_ids": []
}

class JournalParams(BaseModel):
    back_hours_to_query_from_now: int = 0
    


DEFAULT_PARAMS_FOR_FETCHING_ACTIONS = {
    # "action_ids": [],
    "projection_attrs": ["id", "head_text", "priority", "due_date", "ref_object"],
    "due_date_before": None,
    "due_date_after": None,
    "order_clause": "ORDER BY aa.id DESC",
    "limit": 50
}


DEFAULT_PARAMS_FOR_FETCHING_IDEAS = {
    # --- Which attributes (columns) to fetch by default ---
    # These provide a compact but insightful snapshot of each idea.
    "projection_attrs": [
        "id",
        "title",
        "elaborate_description",
        "rank",
        "current_state",
        # "status",
        "budget",
        "start_date",
        "end_date",
        "owner",
        "org_strategy_align",
        "objectives",
        "category",
        "tango_analysis",
        "kpis",
        "constraints",
        "portfolios",
        "business_members",
        "roadmaps",
        "business_case"
    ],
    "idea_ids": None,
    "portfolio_ids": None,
    "state_filter": None,
    "order_clause": "ORDER BY ic.rank ASC",
    "limit": 50
}


# class IdeaFilter(BaseModel):
#     idea_ids: Optional[List[int]] = []
#     portfolio_ids: Optional[List[int]] = []
#     state_filter: Optional[str] = ''

# class IdeaProjection(BaseModel):
#     projection_attrs: List[str] = []
#     order_clause: Optional[str] = ""

# class IdeaFetchParams(BaseModel):
#     filters: IdeaFilter = IdeaFilter()
#     projection: IdeaProjection = []
    
# Default parameters for resource data fetching
# ===========================
# Default Parameters for Resource Data Fetch
# ===========================
DEFAULT_RESOURCE_DATA_PARAMS = {
    "resource_ids": None,             # Optional list of specific resource IDs
    "name": None,                     # Filter by partial/full name (first, last, or full)
    "primary_skill": None,            # Filter by primary skill keyword
    "skill_keyword": None,            # Filter by secondary skills (broader text match)
    "role": None,                     # Filter by role name
    "is_external": None,              # True = external only, False = internal only, None = all
    "external_company_name": None,    # Filter by provider company name (for externals)
    "org_team_name": None,            # Filter by organization/team name (partial match)
    "min_allocation": None,           # Minimum current allocation % (0–100)
    "max_allocation": None,           # Maximum current allocation % (0–100)
    # "available_only": False,          # If True, includes only resources available (not fully allocated)
    "selected_projection_attrs": [],  # Attributes to include in the query projection
    "portfolio_ids": [],
    "portfolio_name": None, 
    "country": None,                  #Filter by portfolio name
}



DEFAULT_PARAMS_FOR_FETCHING_TEMPLATES = {
    "projection_attrs": [
        "id",
        "category",
        "markdown",
        "version",
        "is_active",
        "created_on",
        "file_id",
        "template_name"
    ],
    "category": None,                    # exact match or partial (ILIKE)
    "only_active": True,                 # only return is_active = true
    "limit": 20,
    "order_clause": "ORDER BY created_on DESC"
}



DEFAULT_PARAMS_FOR_THINKING = {
    "uncertainty_context": "",
    "uncertainty_to_resolve": ""
}


DEFAULT_S3_IMAGE_READ_PARAMS = {
    # List of S3 keys pointing to image files
    "s3_image_keys_to_read": [],

    # Execution mode:
    # - "read"              → OCR only (cheap, deterministic)
    # - "describe"          → GPT-Vision only (interpretive)
    # - "read_and_describe" → OCR + GPT-Vision
    #
    # Default is "read" to stay safe and cost-efficient.
    "mode": "read",

    # Optional: Why the image is being analyzed.
    # Used only when mode includes vision.
    "vision_purpose": "Describe the image clearly for downstream reasoning",

    # Controls verbosity of vision output.
    # One of: "low", "medium", "high"
    "detail_level": "high",
}


DEFAULT_PARAMS_FOR_BUG_ENHANCEMENT = {
    "use": False,
    "type": "bug",                # bug | enhancement
    "title": "",
    "description": "",
    "priority": "medium",         # low | medium | high | critical
}

DEFAULT_PARAMS_FOR_BUG_UPDATE = {
    "use": False,
    "custom_id": "",
    "updates": {},                # { status, priority, resolution_description, ... }
}

DEFAULT_PARAMS_FOR_BUG_LIST_AGENT = {
    "use": False,
    # 🔑 cognitive hook, NOT filters
    "analysis_focus": "",
}


DEFAULT_ANALYTICAL_AGENT_PARAMS_REPORT = {
    "use": False,
    "requirement_focus": "",
    "execution_context": "",
}


DEFAULT_ANALYTICAL_AGENT_PARAMS_NORMAL = {
    "use": False,
    "requirement_focus": "",
    "execution_context": "",
    
    # # Projection requests (OPTIONAL)
    "export_presentation": {
        "export_table_or_sheet": False,
        # "export_charts": False,
        # "chart_intent": "",
        # "export": None,  
        # None | "excel" | "csv"
    },
}

# # Aliases (semantic clarity, zero duplication)
# DEFAULT_PARAMS_FOR_PROJECT_AGENT = DEFAULT_ANALYTICAL_AGENT_PARAMS
# DEFAULT_PARAMS_FOR_ROADMAP_AGENT = DEFAULT_ANALYTICAL_AGENT_PARAMS
# DEFAULT_PARAMS_FOR_BUG_LIST_AGENT = DEFAULT_ANALYTICAL_AGENT_PARAMS

DEFAULT_PARAMS_FOR_SEQUENTIAL_RESEARCH_UPDATE = {
    "topic": ""
}

