
ONBOARDING_STEPS = [
    ## Customer Context
    {"step": "customer_context", "sub_step": "strategic_goals", "expectation": "Your company’s long-term objectives", "file_types": "PDF, Excel, PPT", "external_platforms": []},
    {"step": "customer_context", "sub_step": "location_and_currency", "expectation": "Office locations and currency preferences", "file_types": "PDF, Excel", "external_platforms": []},
    {"step": "customer_context", "sub_step": "technology_landscape", "expectation": "Overview of current tech stack", "file_types": "PDF, PPT, Doc", "external_platforms": []},
    {"step": "customer_context", "sub_step": "it_organization", "expectation": "IT team structure and roles", "file_types": "PDF, Excel, Org Chart", "external_platforms": []},
    {"step": "customer_context", "sub_step": "business_units", "expectation": "List of business units and their functions", "file_types": "PDF, Excel", "external_platforms": []},
    
    ## Project Planning
    {"step": "project_planning", "sub_step": "current_initiatives", "expectation": "Details of ongoing projects", "file_types": "PDF, Excel, PPT", "external_platforms": ["Jira", "ADO"]},
    
    ## Resource Management
    {"step": "resource_management", "sub_step": "team_members", "expectation": "Team roster with roles", "file_types": "PDF, Excel, CSV", "external_platforms": []},
    {"step": "resource_management", "sub_step": "resource_allocation", "expectation": "How resources are assigned to projects", "file_types": "PDF, Excel, CSV", "external_platforms": ["Jira", "ADO"]},
    {"step": "resource_management", "sub_step": "service_providers", "expectation": "List of external vendors", "file_types": "PDF, Excel", "external_platforms": []},
    
    ## Project Assurance
    {"step": "project_assurance", "sub_step": "project_health", "expectation": "Status of project KPIs", "file_types": "PDF, Excel, PPT", "external_platforms": ["Jira", "ADO"]},
    {"step": "project_assurance", "sub_step": "project_details", "expectation": "Detailed project descriptions", "file_types": "PDF, Excel", "external_platforms": ["Jira", "ADO"]},
    {"step": "project_assurance", "sub_step": "schedules", "expectation": "Project timelines", "file_types": "PDF, Excel, PPT", "external_platforms": ["Jira", "ADO"]},
    {"step": "project_assurance", "sub_step": "team_assignments", "expectation": "Who’s working on what", "file_types": "PDF, Excel", "external_platforms": ["Jira", "ADO"]},
    {"step": "project_assurance", "sub_step": "financial_data", "expectation": "Project budgets and costs", "file_types": "PDF, Excel", "external_platforms": []},
    {"step": "project_assurance", "sub_step": "risks_and_achievements", "expectation": "Risks and milestones", "file_types": "PDF, Excel, PPT", "external_platforms": ["Jira", "ADO"]},
    
    ## Value Realization
    {"step": "value_realization", "sub_step": "completed_projects", "expectation": "List of finished projects", "file_types": "PDF, Excel, PPT", "external_platforms": ["Jira", "ADO"]},
    {"step": "value_realization", "sub_step": "baseline_kpis", "expectation": "Initial performance metrics", "file_types": "PDF, Excel", "external_platforms": []},
    {"step": "value_realization", "sub_step": "current_values", "expectation": "Current KPI results", "file_types": "PDF, Excel", "external_platforms": []},
    
    ## Reporting and Measurement
    {"step": "reporting_and_measurement", "sub_step": "reporting_tools", "expectation": "Tools used for reporting", "file_types": "PDF, Doc", "external_platforms": ["Power BI", "Tableau"]},
    {"step": "reporting_and_measurement", "sub_step": "key_performance_metrics", "expectation": "Key metrics tracked", "file_types": "PDF, Excel", "external_platforms": []},
    {"step": "reporting_and_measurement", "sub_step": "audience", "expectation": "Who receives reports", "file_types": "PDF, Excel", "external_platforms": []},
    {"step": "reporting_and_measurement", "sub_step": "data_collection_process", "expectation": "How data is gathered", "file_types": "PDF, Doc", "external_platforms": []},
    
    ## Governance
    {"step": "governance", "sub_step": "documentation_locations", "expectation": "Where docs are stored", "file_types": "PDF, Link", "external_platforms": ["SharePoint", "Google Drive"]},
    {"step": "governance", "sub_step": "core_governance_process", "expectation": "Governance workflows", "file_types": "PDF, Doc", "external_platforms": []},
    {"step": "governance", "sub_step": "practical_implementation", "expectation": "How governance is applied", "file_types": "PDF, Doc", "external_platforms": []},
]


NEW_ONBOARDING_STEP = [
    {"step": "general_section", "sub_step": "general_section", "expectation": "", "file_types": "", "external_platforms": []},
]