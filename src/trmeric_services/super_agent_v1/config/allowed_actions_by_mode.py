


# ============================================================
# ACTION SETS — mode-gated permissions
# ============================================================

ANALYSIS_ALLOWED_ACTIONS = {
    "web_search",
    "fetch_projects_data_using_project_agent",
    "fetch_roadmaps_data_using_roadmap_agent",
    "fetch_ideas_data_using_idea_agent",
    "fetch_tango_usage_qna_data",
    "fetch_users_data",
    "fetch_agent_activity_data",
    "fetch_accessible_portfolio_data_using_portfolio_agent",
    "get_tenant_knowledge_and_entity_relation_and_volume_stats",
    "total_time_spent_by_customer_on_trmeric",
    
    "fetch_additional_project_execution_intelligence",
    "get_available_execution_integrations",
    
    "generate_report_doc_after_analysis",

    "generate_llm_chart",
    
    "fetch_files_uploaded_in_session",
    "read_file_details_with_s3_key",
    "read_image_details_with_s3_key",
    # "think_aloud_reasoning",
    "ask_clarification",
    "read_files",
    
    
    "generate_report_doc_after_analysis",
    "generate_html_after_analysis",
    "generate_ppt_after_analysis",


    "accessible_roadmaps_of_user",
    "accessible_projects_of_user"
}

DEEP_RESEARCH_ALLOWED_ACTIONS =  {
    
    "web_search",
    "fetch_projects_data_using_project_agent",
    "fetch_roadmaps_data_using_roadmap_agent",
    "fetch_ideas_data_using_idea_agent",
    "fetch_tango_usage_qna_data",
    "fetch_users_data",
    "fetch_agent_activity_data",
    "fetch_accessible_portfolio_data_using_portfolio_agent",
    "get_tenant_knowledge_and_entity_relation_and_volume_stats",
    "total_time_spent_by_customer_on_trmeric",
    
    "fetch_additional_project_execution_intelligence",
    "get_available_execution_integrations",
    
    "fetch_files_uploaded_in_session",
    "read_file_details_with_s3_key",
    "read_image_details_with_s3_key",
    "ask_clarification",
    
    
    # Document lifecycle — ONLY deep research
    "identify_required_sections",
    "write_markdown_file",
    "read_files",
    "update_section_in_markdown_file",
    "append_section_in_markdown_file",
    "validate_section",
    "freeze_section",
}


CUSTOMER_SUCCESS_ALLOWED_ACTIONS = {
    "read_file_details_with_s3_key",
    "fetch_trmeric_info_from_vectorstore",
    # "think_aloud_reasoning",
    "log_bug_or_enhancement",
    "list_issues_aka_bug_enhancement",
    "ask_clarification",
}


CONTEXT_BUILDING_ALLOWED_ACTIONS = {
    # Gather
    "web_search",
    "read_file_details_with_s3_key",
    "analyze_file_structure",
    "fetch_company",
    "fetch_company_industry",
    "fetch_company_performance",
    "fetch_competitor",
    "fetch_enterprise_strategy",
    "fetch_social_media",
    "fetch_industry",
    # Classify
    "map_text",                  # uploaded PDF / DOCX / TXT / PPT file
    "map_excel_columns",         # uploaded CSV / Excel file
    "map_from_conversation",     # typed input, no file needed
    # Store
    "store_company_context",
    "store_enterprise_strategy",
    "store_performance_context",
    "store_competitor_context",
    "store_company_industry_mapping",
    "store_social_media_context",
    "store_portfolio_context",
    "store_company_orgstrategy",
    "set_user_designation",
}
