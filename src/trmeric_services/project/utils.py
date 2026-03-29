import time
import json
import traceback
from src.trmeric_services.roadmap.Prompts import *
from datetime import datetime


def format_project_json(canvas_data, roles_data):
    """Format the combined results into the required JSON structure."""
    # print("\n\n [Roles data]----", roles_data)
    # Canvas data
    title = canvas_data.get("title", "")    
    description = canvas_data.get("description", "")
    objectives = canvas_data.get("objectives", "")
    scope = canvas_data.get("scope", []) 
    start_date = canvas_data.get("start_date", "")
    end_date = canvas_data.get("end_date", "")
    key_results = canvas_data.get("key_results", [])
    project_category = canvas_data.get("project_category", "")
    portfolio_list = canvas_data.get("portfolio_list", [])
    state = canvas_data.get("state", "Discovery")
    technology_stack = canvas_data.get("technology_stack", "")
    sdlc_method = canvas_data.get("sdlc_method", "")
    project_type = canvas_data.get("project_type", "")
    org_strategy_align = canvas_data.get("org_strategy_align", "")
    service_category = canvas_data.get("service_category", "")
    internal_project = canvas_data.get("internal_project", False)
    project_location = canvas_data.get("project_location", [])
    last_updated = canvas_data.get("last_updated", datetime.now().date().isoformat())
    # team = canvas_data.get("team", [])



    # Thought processes from canvas
    thought_process_description = canvas_data.get("thought_process_behind_description", "")
    thought_process_objectives = canvas_data.get("thought_process_behind_objectives", "")
    thought_process_scope = canvas_data.get("thought_process_behind_scope", "")
    thought_process_key_results = canvas_data.get("thought_process_behind_key_results", "")
    thought_process_timeline = canvas_data.get("thought_process_behind_timeline", "")
    thought_process_team = canvas_data.get("thought_process_behind_team", "")
    thought_process_category = canvas_data.get("thought_process_behind_project_category", "")
    thought_process_portfolio = canvas_data.get("thought_process_behind_portfolio_list", "")
    thought_process_technology_stack = canvas_data.get("thought_process_behind_technology_stack", "")
    thought_process_sdlc_method = canvas_data.get("thought_process_behind_sdlc_method", "")
    thought_process_project_type = canvas_data.get("thought_process_behind_project_type", "")
    thought_process_org_strategy = canvas_data.get("thought_process_behind_org_strategy_align", "")
    thought_process_service_category = canvas_data.get("thought_process_behind_service_category", "")
    thought_process_internal_project = canvas_data.get("thought_process_behind_internal_project", "")
    thought_process_location = canvas_data.get("thought_process_behind_project_location", "")
    thought_process_state = canvas_data.get("thought_process_behind_state", "")

    # Roles data
    recommended_roles = roles_data.get("recommended_project_roles", [])
    thought_process_roles = roles_data.get("thought_process_behind_the_above_list", "")


    # Calculate budget
    # Labor budget: Sum (rate * hours) for each role, assuming hours based on timeline
    # labour_budget = 0
    # for role in recommended_roles:
    #     rate = role.get("approximate_rate", 0)
    #     for timeline in role.get("timeline", []):
    #         start = datetime.strptime(timeline.get("start_date", start_date), "%Y-%m-%d")
    #         end = datetime.strptime(timeline.get("end_date", end_date), "%Y-%m-%d")
    #         hours = (end - start).days * 8  # Assume 8 hours/day
    #         labour_budget += rate * hours

    # budget = labour_budget

    # Tango analysis
    tango_analysis = {
        "thought_process_behind_description": thought_process_description,
        "thought_process_behind_objectives": thought_process_objectives,
        "thought_process_behind_scope": thought_process_scope,
        "thought_process_behind_key_results": thought_process_key_results,
        "thought_process_behind_timeline": thought_process_timeline,
        "thought_process_behind_team": thought_process_team,  # Non-labor team thought process
        "thought_process_behind_labor_team": thought_process_roles,  # Labor team thought process
        "thought_process_behind_project_category": thought_process_category,
        "thought_process_behind_portfolio_list": thought_process_portfolio,
        "thought_process_behind_technology_stack": thought_process_technology_stack,
        "thought_process_behind_sdlc_method": thought_process_sdlc_method,
        "thought_process_behind_project_type": thought_process_project_type,
        "thought_process_behind_org_strategy_align": thought_process_org_strategy,
        "thought_process_behind_service_category": thought_process_service_category,
        "thought_process_behind_internal_project": thought_process_internal_project,
        "thought_process_behind_project_location": thought_process_location,
        "thought_process_behind_state": thought_process_state
    }

    # Final JSON structure
    return {
        "title": title,
        "description": description,
        "objectives": objectives,
        "scope": scope,
        "start_date": start_date,
        "end_date": end_date,
        # "budget": budget,
        "key_results": key_results,
        # "team": team,
        "recommended_roles": recommended_roles,
        "portfolio_list": portfolio_list,
        "project_category": project_category,
        "technology_stack": technology_stack,
        "sdlc_method": sdlc_method,
        "project_type": project_type,
        "org_strategy_align": org_strategy_align,
        "service_category": service_category,
        "internal_project": internal_project,
        "project_location": project_location,
        "state": state,
        "tango_analysis": tango_analysis,
        "last_updated": last_updated
    }