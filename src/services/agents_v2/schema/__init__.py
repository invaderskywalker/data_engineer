


PROJECT_SCHEMA = {
    "ref_project_id": "",
    "project_title": "string (project name)",
    "project_description": "string (detailed description)",
    "project_objectives": "string (detailed objectives)",
    "project_budget": "float (project budget )",
    "start_date": "date (project start date)",
    "end_date": "date (project end date)",
    "capex_budget": "",
    "opex_budget": "",
    "project_category": "string (project category)",
    "org_strategy": "string (alignment with org strategy)",
    "milestones": "list of dicts (milestone details: name, target_date, actual_spend, planned_spend)",
    "key_results": "list of strings (names of key performance indicators)",
    "portfolio": "string (associated portfolio name)",
    "risks": "list",
    "program_name": "string (associated program name)",
    "technology_stack": "list",
    "risks": "list",
    "key_accomplishments": "",
    "sdlc_method": "",
    "project_stage": "options: dicovery or Mobilisation, Design, Build, Test, Deploy & Hypercare, Complete"
}


ROADMAP_SCHEMA = {
    "ref_id": "string",
    "roadmap_title": "string (roadmap name)",
    "roadmap_description": "string (detailed description of the roadmap)",
    "priority": "string (High, Medium, Low, or Unknown)",
    "budget": "float (budget in dollars)",
    "capex_budget": "",
    "opex_budget": "",
    "fiscal_year": "",
    "rank": "numerical",
    "start_date": "date (start date of roadmap)",
    "end_date": "date (end date of roadmap)",
    "category": "string (roadmap category)",
    "roadmap_type": """string (roadmap/demand type)
        one of - 
            'Program'
            'Project'
            'Enhancement'
            'New Development'
            'Enhancements or Upgrade'
            'Consume a Service'
            'Support a Pursuit'
            'Acquisition'
            'Global Product Adoption'
            'Innovation Request for NITRO'
            'Regional Product Adoption'
            'Client Deployment'
    """,
    "org_strategy_alignment": "string (description of alignment with org strategy)",
    "constraints": "",
    "roadmap_portfolios": "",
    "key_results": "",
    "roadmap_scopes": "list of strings (names of roadmap scopes)",
    "business_unit": "",
    "portfolio": "",
    "business_sponsors": "list of sponsor_name, sponsor_role -extract as much as present in data",
    "business_case_details": "",
    "current_state": """
        one of 
            'Intake'
            'Approved'
            'Execution'
            'Archived'
            'Elaboration'
            'Solutioning'
            'Prioritize'
            'Hold'
            'Rejected'
            'Cancelled'
            'Draft'
    """
}


POTENTIAL_RESURCE = {
    "first_name": "", 
    "last_name": "", 
    "country": "", 
    "email": "", 
    "role": "",
    "skills": "",
    "allocation": "", 
    "experience_years": "", 
    "experience": "", 
    "projects": "",
    "is_active": "", 
    "is_external": "",
    "availability_time": ""
}

PROJECT_UPDATE_SCHEMA = {
    "project_name": "string",

    # Schedule update
    "schedule_value": "on_track | at_risk | compromised | no_info",
    "schedule_comment": "string",

    # Scope update
    "scope_value": "on_track | at_risk | compromised | no_info",
    "scope_comment": "string",
    "scope_percent": "string",

    # Spend (budget) update
    "spend_value": "on_track | at_risk | compromised | no_info",
    "spend_comment": "string",

    # Overall project update
    "overall_value": "on_track | at_risk | compromised | no_info",
    "overall_comment": "string",

    # If none of the above were strongly detectable: fallback
    "general_comment": "string",
}


IDEA_SCHEMA = {
    "idea_name": "string",
    "description": "string",
    "objectives": "string",
    "idea_category": "technical | business | functional categories",
    
    "org_strategy": "string (alignment with org strategy)",
    
    "key_results": "list of strings (names of key performance indicators)",
    "portfolio": "string (associated portfolio name)",
    
    "priority": "string (High, Medium, Low, or Unknown)",
    "budget": "float (budget in dollars)",
    
    "general_comments": "",
}



SCHEMAS = {
    "project": PROJECT_SCHEMA,
    "roadmap": ROADMAP_SCHEMA,
    'potential': POTENTIAL_RESURCE,
    "project_update": PROJECT_UPDATE_SCHEMA,
    "idea_creation_schema": IDEA_SCHEMA
}
