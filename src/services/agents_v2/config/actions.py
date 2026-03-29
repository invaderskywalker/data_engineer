from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional
from enum import Enum

DEFAULT_CITATIONS_INTERFACE = {
    "source": "",
    "url": ""
}

DEFAULT_ENTRPRISE_SECTIONS = {
    "section_name": "",
    "content": ""
}

# Default parameters for DataActions methods
DEFAULT_COMPANY_CONTEXT_PARAMS = {
    "name": "",
    "description": "",
    "business_units": [],
    "culture_values": "",
    "management_team": [],
    "doc_s3_keys": [],
    "company_url": "",
    "citations": [DEFAULT_CITATIONS_INTERFACE]
}

DEFAULT_ENTERPRISE_STRATEGY_PARAMS = {
    "title": "",
    "doc_s3_keys": [],
    "detailed_strategies_sections": [DEFAULT_ENTRPRISE_SECTIONS],
    "citations": [DEFAULT_CITATIONS_INTERFACE]
}

DEFAULT_INDUSTRY_CONTEXT_PARAMS = {
    "name": "",
    "trends": [],
    "value_chain": [],
    "function_kpis": {},
    # "citations": [DEFAULT_CITATIONS_INTERFACE],
    "doc_s3_keys": []
}

# DEFAULT_COMPANY_INDUSTRY_MAPPING_PARAMS = {
#     "industry_id": None,
#     "citations": [DEFAULT_CITATIONS_INTERFACE]
# }

DEFAULT_COMPANY_INDUSTRY_MAPPING_PARAMS = {
    "industry_info": DEFAULT_INDUSTRY_CONTEXT_PARAMS,
    "citations": [DEFAULT_CITATIONS_INTERFACE],
}

DEFAULT_SOCIAL_MEDIA_CONTEXT_PARAMS = {
    "platform": "",
    "handle": "",
    "latest_posts": [],
    "doc_s3_keys": []
}

DEFAULT_COMPETITOR_CONTEXT_PARAMS = {
    "name": "",
    "summary": "",
    "recent_news": [],
    "financials": {},
    "citations": [],
    "doc_s3_keys": [],
    "company_url": ""
}

DEFAULT_PERFORMANCE_CONTEXT_PARAMS = {
    "period": "",
    "revenue": None,
    "profit": None,
    "funding_raised": None,
    "investor_info": [],
    "citations": [],
    "doc_s3_keys": []
}

# New trucible-specific default parameters
DEFAULT_CLASSIFY_FILE_PARAMS = {
    "s3_key": "",
    "user_message": ""
}

DEFAULT_SUMMARIZE_CONTENT_PARAMS = {
    "file_data": {},
    "target_classification": ""
}

DEFAULT_MAP_EXCEL_PARAMS = {
    "type": "",
    "s3_key": "",
    "user_input": "",
    "user_wants_more_modifications": True,
    "user_satisfied_with_your_provided_mapping": False,
    "name_of_sheet_to_process": ""
}

DEFAULT_MAP_DOCS_PARAMS = {
    "type": "",
    "s3_keys": [""],
    "user_input": "",
    "user_wants_more_modifications": True,
    "user_satisfied_with_your_provided_mapping": False,
    "num_projects": ""
}

DEFAULT_CREATE_DEMAND_PARAMS = {
    "s3_key": "",
    "user_input": ""
}

DEFAULT_HANDOFF_PARAMS = {
    "classification": "",
    "processed_data": {},
    "file_summary": ""
}

DEFAULT_PROCESSING_SUMMARY_PARAMS = {
    "processing_results": {},
    "error_summary": {}
}


DEFAULT_SET_USER_DESIGNATION = {
    "designation": ""
}

DEFAULT_FIND_SUITABLE_PROVIDER_PARAMS = {
    "roadmap_id": "",
    "project_id": "",
    "idea_description": "",
    "tag": ""
}


DEFAULT_PARAMS_FOR_ROADMAPS_CREATION = {
    "description_of_roadmaps_for_creation": []
}


DEFAULT_PARAMS_FOR_IDEATION_PPT_CREATION = {
    "content_type": "single_idea",
    "ideas": [
        {
            "title": "",
            "description": "",
            "impact": ""
        }
    ],
    "include_2x2_matrix": True,
    "include_value_chain": True,
    "axis_x_label": "",
    "axis_y_label": "",
    "quadrant_labels": [
        "Quick Wins", "Big Bets", "Long Term", "Low Priority"
    ],
}


DEFAULT_CONNECT_WITH_PROVIDER_DEFAULTS = {
    "email_details": [
        {
            "provider_id": "",
            "provider_name": "",
            "roadmap_id": "",
            "project_id": "",
            "idea_description": "",
            "tag": "",
            "markdown_mail": ""
        }
    ],
    "user_satisfied_with_email_contents": False
}



DEFAULT_PARAMS_FOR_TEMPLATE_GENERATION = {
    # "mode": "<save_template|generate_with_changes>",
    "template_name": "",
    "category": "BRD",
    "changes": "",
    "s3_keys": [],                              # Auto-filled from upload
    "user_satisfied_with_template": False,
    "user_wants_modifications": False
}


DEFAULT_ORGSTRATEGY_PARAMS = {
    "org_strategies_to_create": ["<array of strings>"]
}









class TagOptions(str, Enum):
    IDEA = "idea"
    PROJECT = "project"
    ROADMAP = "roadmap"

class EmailDetail(BaseModel):
    provider_id: str = ""
    provider_name: str = ""
    roadmap_id: str = ""
    project_id: str = ""
    idea_description: str = ""
    tag: TagOptions = Field(default=TagOptions.IDEA, description="Tag type; options: idea, project, roadmap")
    markdown_mail_body: str = ""
    closing_salutation: str = ''
    name_and_designation_string: str = ""
    email_subject: str = ""
    
    @field_validator("provider_id", mode="before")
    def convert_to_str(cls, v):
        return str(v)

class ContactProviderParams(BaseModel):
    email_details: List[EmailDetail] = [EmailDetail()]
    user_satisfied_with_email_contents_and_markdown_mail: bool = False


class Citation(BaseModel):
    source: str = ""
    url: str = ""

class IndustryContext(BaseModel):
    name: str = ""
    trends: Optional[List[str]] = []
    value_chain: Optional[List[str]] = []
    function_kpis: Optional[Dict] = {}
    doc_s3_keys: Optional[List[str]] = []

class CompanyIndustryMappingParams(BaseModel):
    industry_info: IndustryContext = IndustryContext()
    citations: List[Citation] = Field(default_factory=lambda: [Citation()])
    
    
# CONTENT_TYPE_CHOICES = [
#     ('strategy', 'Strategy'),
#     ('kpi', 'KPI'),
#     ('risk', 'Risk'),
#     ('priority', 'Priority'),
#     ('investment_theme', 'Investment Theme'),
#     ('operating_model', 'Operating Model'),
#     ('narrative', 'Narrative'),
# ]

# SOURCE_TYPE_CHOICES = [
#     ('doc_upload', 'Document Upload'),
#     ('sheet_upload', 'Sheet Upload'),
#     ('manual', 'Manual'),
#     ('web', 'Web'),
# ]

DEFAULT_PORTFOLIO_CONTEXT_PARAMS = [
    {
        "portfolio_id": 0,
        "content_type": "",
        "title": "",
        "summary": "",
        "content": {},
        "source_type": "doc_upload",
        "doc_s3_keys": [],
        "citations": [],
        "user_confirmed": ""
    }
]
