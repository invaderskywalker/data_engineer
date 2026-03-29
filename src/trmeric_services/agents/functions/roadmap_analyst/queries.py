
from src.trmeric_services.tango.functions.integrations.internal.GetIntegrationData import get_jira_data, get_github_data, get_ado_data, get_smartsheet_data
from typing import List, Dict
from src.trmeric_services.integration.IntegrationService import IntegrationService
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
from src.trmeric_database.dao import TangoDao
import json


def getIntegrationData(
    integration_name: str,
    project_ids: List[str],
    # user_query: str = "",
    **kwargs
) -> Dict:
    tenantID = kwargs.get("tenantID")
    userID = kwargs.get("userID")
    debugLogger.info(f"here now getIntegrationData {integration_name}, {project_ids}")
    # print(integration_name == "jira"  \
    #     or integration_name == "github" \
    #     or integration_name == "ado" \
    #     or integration_name == "smartsheet")
    # if (
    #     integration_name == "jira"  \
    #     or integration_name == "github" \
    #     or integration_name == "ado" \
    #     or integration_name == "smartsheet"
    # ):
    return IntegrationService().fetchProjectDataforAllIntegration(
        tenant_id=tenantID, 
        user_id=userID, 
        integration_type=integration_name,
        project_ids=project_ids
    )
    # else:
    #     return ""
        
    # elif integration_name == "jira":
    #     return get_jira_data(
    #         tenantID=tenantID, 
    #         userID=userID, 
    #         summary_analysis_of_which_jira_projects=summary_of_which_integration_summary_keys, 
    #         project_id=project_ids, 
    #         user_query=user_query
    #     )
    # elif integration_name == "github":
    #     return get_github_data(
    #         tenantID=tenantID, 
    #         userID=userID, 
    #         project_id=project_ids, 
    #         user_query=user_query
    #     )
    # elif integration_name == "ado":
    #     return get_ado_data(
    #         tenantID=tenantID, 
    #         userID=userID, 
    #         project_id=project_ids, 
    #     )
    # elif integration_name == "smartsheet":
    #     return get_smartsheet_data(
    #         tenantID=tenantID, 
    #         userID=userID, 
    #         project_id=project_ids, 
    #     )
    # else:
    #     raise ValueError(f"Unsupported integration: {integration_name}")
    
    


def get_roadmap_query(tenant_id,  filter_string: str = "") -> str:
    base_query = f"""
        SELECT 
            rr.id as roadmap_id, 
            rr.title as roadmap_title, 
            rr.description as roadmap_description,
            rr.objectives as roadmap_objectives, 
            rr.start_date as roadmap_start_date,
            rr.end_date as roadmap_end_date,
            rr.budget as roadmap_budget,
            rr.category as roadmap_category,
            CASE 
                WHEN rr.type = 1 THEN 'Program'
                WHEN rr.type = 2 THEN 'Project'
                WHEN rr.type = 3 THEN 'Enhancement'
                WHEN rr.type = 4 THEN 'New Development'
                WHEN rr.type = 5 THEN 'Enhancements or Upgrade'
                WHEN rr.type = 6 THEN 'Consume a Service'
                WHEN rr.type = 7 THEN 'Support a Pursuit'
                WHEN rr.type = 8 THEN 'Acquisition'
                WHEN rr.type = 9 THEN 'Global Product Adoption'
                WHEN rr.type = 10 THEN 'Innovation Request for NITRO'
                WHEN rr.type = 11 THEN 'Regional Product Adoption'
                WHEN rr.type = 12 THEN 'Client Deployment'
                ELSE 'Unknown'
            END AS roadmap_type,
            rr.org_strategy_align as roadmap_org_strategy_alignment,
            rr.approved_state,
            rr.rank as roadmap_priority,
            CASE 
                WHEN rr.current_state = 0 THEN 'Intake'
                WHEN rr.current_state = 1 THEN 'Approved'
                WHEN rr.current_state = 2 THEN 'Execution'
                WHEN rr.current_state = 3 THEN 'Archived'
                WHEN rr.current_state = 4 THEN 'Elaboration'
                WHEN rr.current_state = 5 THEN 'Solutioning'
                WHEN rr.current_state = 6 THEN 'Prioritize'
                WHEN rr.current_state = 99 THEN 'Hold'
                WHEN rr.current_state = 100 THEN 'Rejected'
                WHEN rr.current_state = 999 THEN 'Cancelled'
                WHEN rr.current_state = 200 THEN 'Draft'
                ELSE 'Unknown'
            END AS current_state,
            CASE 
                WHEN COUNT(atd.id) > 0 THEN true
                ELSE false
            END AS is_test_data,
            uu.first_name as owner_first_name,
            uu.last_name as owner_last_name,
            rr.assigned_to_id as assigned_to_id,
            au_assignee.first_name as assignee_first_name,
            rr.tango_analysis as roadmap_additional_info,
            json_agg(
                DISTINCT json_build_object(
                    'constraint_title', rrc.name,
                    'constraint_type', 
                    CASE
                        WHEN rrc.type = 1 THEN 'Cost'
                        WHEN rrc.type = 2 THEN 'Risk'
                        WHEN rrc.type = 3 THEN 'Resource'
                        ELSE 'Other'
                    END
                )::text
            ) FILTER (WHERE rrc.name IS NOT NULL) as roadmap_constraints,
            json_agg(
                DISTINCT json_build_object(
                    'portfolio_id', pp.id,
                    'portfolio_title', pp.title,
                    'portfolio_rank', rp.rank
                )::text
            ) FILTER (WHERE pp.id IS NOT NULL) as roadmap_portfolios,
            json_agg(
                DISTINCT json_build_object(
                    'key_result_title', rrkpi.name,
                    'baseline_value', rrkpi.baseline_value
                )::text
            ) FILTER (WHERE rrkpi.name IS NOT NULL) as roadmap_key_results,
            json_agg(
                DISTINCT json_build_object(
                    'team_name', rrt.name,
                    'team_unit_size', rrt.unit,
                    'unit_type', 
                    CASE
                        WHEN rrt.type = 1 THEN 'days'
                        WHEN rrt.type = 2 THEN 'months'
                        WHEN rrt.type = 3 THEN 'weeks'
                        WHEN rrt.type = 4 THEN 'hours'
                        ELSE 'Unknown'
                    END,
                    'labour_type', 
                    CASE
                        WHEN rrt.labour_type = 1 THEN 'labour'
                        WHEN rrt.labour_type = 2 THEN 'non labour'
                        ELSE 'Unknown'
                    END,
                    'description', rrt.description,
                    'start_date', rrt.start_date,
                    'end_date', rrt.end_date,
                    'location', rrt.location,
                    'allocation', rrt.allocation,
                    'total_estimated_hours',
                    CASE
                        WHEN rrt.type = 1 THEN rrt.unit * 8
                        WHEN rrt.type = 2 THEN rrt.unit * 160
                        WHEN rrt.type = 3 THEN rrt.unit * 40
                        WHEN rrt.type = 4 THEN rrt.unit
                        ELSE 0
                    END,
                    'total_estimated_cost',
                    CASE
                        WHEN rrt.labour_type = 1 THEN 
                            COALESCE(NULLIF(rrt.estimate_value, '')::NUMERIC, 0) * 
                            CASE
                                WHEN rrt.type = 1 THEN rrt.unit * 8
                                WHEN rrt.type = 2 THEN rrt.unit * 160
                                WHEN rrt.type = 3 THEN rrt.unit * 40
                                WHEN rrt.type = 4 THEN rrt.unit
                                ELSE 0
                            END
                        WHEN rrt.labour_type = 2 THEN COALESCE(NULLIF(rrt.estimate_value, '')::NUMERIC, 0)
                        ELSE 0
                    END
                )::text
            ) FILTER (WHERE rrt.name IS NOT NULL) AS team_data,
            json_agg(
                DISTINCT rrs.name
            ) FILTER (WHERE rrs.name IS NOT NULL) as roadmap_scopes,
            COALESCE(
                json_agg(
                    DISTINCT json_build_object(
                        'request_type', CASE
                            WHEN aar.request_type = 1 THEN 'Roadmap'
                            WHEN aar.request_type = 2 THEN 'Project'
                            ELSE 'Unknown'
                        END,
                        'request_id', aar.request_id,
                        'request_date', aar.request_date,
                        'from_state', CASE
                            WHEN aar.from_state = 0 THEN 'Intake'
                            WHEN aar.from_state = 1 THEN 'Approved'
                            WHEN aar.from_state = 2 THEN 'Execution'
                            WHEN aar.from_state = 3 THEN 'Archived'
                            WHEN aar.from_state = 4 THEN 'Elaboration'
                            WHEN aar.from_state = 5 THEN 'Solutioning'
                            WHEN aar.from_state = 6 THEN 'Prioritize'
                            WHEN aar.from_state = 99 THEN 'Hold'
                            WHEN aar.from_state = 100 THEN 'Rejected'
                            WHEN aar.from_state = 999 THEN 'Cancelled'
                            WHEN aar.from_state = 200 THEN 'Draft'
                            ELSE 'Unknown'
                        END,
                        'to_state', CASE
                            WHEN aar.to_state = 0 THEN 'Intake'
                            WHEN aar.to_state = 1 THEN 'Approved'
                            WHEN aar.to_state = 2 THEN 'Execution'
                            WHEN aar.to_state = 3 THEN 'Archived'
                            WHEN aar.to_state = 4 THEN 'Elaboration'
                            WHEN aar.to_state = 5 THEN 'Solutioning'
                            WHEN aar.to_state = 6 THEN 'Prioritize'
                            WHEN aar.to_state = 99 THEN 'Hold'
                            WHEN aar.to_state = 100 THEN 'Rejected'
                            WHEN aar.to_state = 999 THEN 'Cancelled'
                            WHEN aar.to_state = 200 THEN 'Draft'
                            ELSE 'Unknown'
                        END,
                        'approver_id', aar.approver_id,
                        'requestor_id', aar.requestor_id,
                        'approver_first_name', au.first_name,
                        'approver_last_name', au.last_name,
                        'requestor_first_name', ru.first_name,
                        'requestor_last_name', ru.last_name,
                        'approval_status', CASE
                            WHEN aar.approval_status = 1 THEN 'Pending'
                            WHEN aar.approval_status = 2 THEN 'Approved'
                            WHEN aar.approval_status = 3 THEN 'Rejected'
                            ELSE 'Unknown'
                        END,
                        'request_comments', aar.request_comments,
                        'approval_reject_comments', aar.approval_reject_comments,
                        'approval_reject_date', aar.approval_reject_date
                    )::text
                ) FILTER (WHERE aar.id IS NOT NULL),
                '[]'
            ) as approval_history
        FROM roadmap_roadmap AS rr 
        LEFT JOIN roadmap_roadmapconstraints AS rrc ON rr.id = rrc.roadmap_id
        LEFT JOIN roadmap_roadmapportfolio AS rp ON rr.id = rp.roadmap_id
        LEFT JOIN projects_portfolio AS pp ON rp.portfolio_id = pp.id
        LEFT JOIN roadmap_roadmapkpi AS rrkpi ON rr.id = rrkpi.roadmap_id
        LEFT JOIN roadmap_roadmapestimate AS rrt ON rrt.roadmap_id = rr.id
        LEFT JOIN roadmap_roadmapscope AS rrs ON rr.id = rrs.roadmap_id
        LEFT JOIN users_user AS uu ON rr.created_by_id = uu.id
        LEFT JOIN authorization_approval_request AS aar ON rr.id = aar.request_id AND aar.request_type = 1
        LEFT JOIN users_user AS au ON aar.approver_id = au.id
        LEFT JOIN users_user AS ru ON aar.requestor_id = ru.id
        LEFT JOIN users_user AS au_assignee ON rr.assigned_to_id = au_assignee.id
        LEFT JOIN adminapis_test_data AS atd
            ON atd.table_pk = rr.id
            AND atd.table_name = 'roadmap'
            AND atd.tenant_id = rr.tenant_id

        WHERE rr.tenant_id = {tenant_id}
    """
    if filter_string:
        base_query += f" {filter_string}"
    base_query += " GROUP BY rr.id, uu.first_name, uu.last_name, rr.assigned_to_id, au_assignee.first_name, au_assignee.last_name, rr.tango_analysis;"
    return base_query



def get_roadmap_actions_query(tenant_id: int, action: str, portfolio_ids: list = None, filter_string: str = "") -> str:
    # Define column sets for each action
    prioritize_columns = """
        rr.id as roadmap_id,
        rr.title as roadmap_title,
        rr.description as roadmap_description,
        rr.org_strategy_align as roadmap_org_strategy_alignment,
        rr.rank as roadmap_priority,
        CASE 
            WHEN rr.current_state = 0 THEN 'Intake'
            WHEN rr.current_state = 1 THEN 'Approved'
            WHEN rr.current_state = 2 THEN 'Execution'
            WHEN rr.current_state = 3 THEN 'Archived'
            WHEN rr.current_state = 4 THEN 'Elaboration'
            WHEN rr.current_state = 5 THEN 'Solutioning'
            WHEN rr.current_state = 6 THEN 'Prioritize'
            WHEN rr.current_state = 99 THEN 'Hold'
            WHEN rr.current_state = 100 THEN 'Rejected'
            WHEN rr.current_state = 999 THEN 'Cancelled'
            WHEN rr.current_state = 200 THEN 'Draft'
            ELSE 'Unknown'
        END AS current_state,
        json_agg(
            DISTINCT json_build_object(
                'constraint_title', rrc.name,
                'constraint_type', 
                CASE
                    WHEN rrc.type = 1 THEN 'Cost'
                    WHEN rrc.type = 2 THEN 'Risk'
                    WHEN rrc.type = 3 THEN 'Resource'
                    ELSE 'Other'
                END
            )::text
        ) FILTER (WHERE rrc.name IS NOT NULL) as roadmap_constraints,
        json_agg(
            DISTINCT json_build_object(
                'portfolio_id', pp.id,
                'portfolio_title', pp.title,
                'portfolio_rank', rp.rank
            )::text
        ) FILTER (WHERE pp.id IS NOT NULL) as roadmap_portfolios,
        json_agg(
            DISTINCT json_build_object(
                'key_result_title', rrkpi.name,
                'baseline_value', rrkpi.baseline_value
            )::text
        ) FILTER (WHERE rrkpi.name IS NOT NULL) as roadmap_key_results,
        json_agg(
            DISTINCT rrs.name
        ) FILTER (WHERE rrs.name IS NOT NULL) as roadmap_scopes
    """

    schedule_columns = """
        rr.id as roadmap_id,
        rr.title as roadmap_title,
        rr.rank as roadmap_priority,
        CASE 
            WHEN rr.current_state = 0 THEN 'Intake'
            WHEN rr.current_state = 1 THEN 'Approved'
            WHEN rr.current_state = 2 THEN 'Execution'
            WHEN rr.current_state = 3 THEN 'Archived'
            WHEN rr.current_state = 4 THEN 'Elaboration'
            WHEN rr.current_state = 5 THEN 'Solutioning'
            WHEN rr.current_state = 6 THEN 'Prioritize'
            WHEN rr.current_state = 99 THEN 'Hold'
            WHEN rr.current_state = 100 THEN 'Rejected'
            WHEN rr.current_state = 999 THEN 'Cancelled'
            WHEN rr.current_state = 200 THEN 'Draft'
            ELSE 'Unknown'
        END AS current_state,
        json_agg(
            DISTINCT json_build_object(
                'portfolio_id', pp.id,
                'portfolio_title', pp.title,
                'portfolio_rank', rp.rank
            )::text
        ) FILTER (WHERE pp.id IS NOT NULL) as roadmap_portfolios,
        json_agg(
            DISTINCT json_build_object(
                'team_name', rrt.name,
                'team_unit_size', rrt.unit,
                'unit_type', 
                CASE
                    WHEN rrt.type = 1 THEN 'days'
                    WHEN rrt.type = 2 THEN 'months'
                    WHEN rrt.type = 3 THEN 'weeks'
                    WHEN rrt.type = 4 THEN 'hours'
                    ELSE 'Unknown'
                END,
                'labour_type', 
                CASE
                    WHEN rrt.labour_type = 1 THEN 'labour'
                    WHEN rrt.labour_type = 2 THEN 'non labour'
                    ELSE 'Unknown'
                END,
                'description', rrt.description,
                'start_date', rrt.start_date,
                'end_date', rrt.end_date,
                'location', rrt.location,
                'allocation', rrt.allocation,
                'total_estimated_hours',
                CASE
                    WHEN rrt.type = 1 THEN rrt.unit * 8
                    WHEN rrt.type = 2 THEN rrt.unit * 160
                    WHEN rrt.type = 3 THEN rrt.unit * 40
                    WHEN rrt.type = 4 THEN rrt.unit
                    ELSE 0
                END,
                'total_estimated_cost',
                CASE
                    WHEN rrt.labour_type = 1 THEN 
                        COALESCE(NULLIF(rrt.estimate_value, '')::NUMERIC, 0) * 
                        CASE
                            WHEN rrt.type = 1 THEN rrt.unit * 8
                            WHEN rrt.type = 2 THEN rrt.unit * 160
                            WHEN rrt.type = 3 THEN rrt.unit * 40
                            WHEN rrt.type = 4 THEN rrt.unit
                            ELSE 0
                        END
                    WHEN rrt.labour_type = 2 THEN COALESCE(NULLIF(rrt.estimate_value, '')::NUMERIC, 0)
                    ELSE 0
                END
            )::text
        ) FILTER (WHERE rrt.name IS NOT NULL) AS team_data
    """

    # Select columns based on action
    if action == "prioritize":
        select_clause = prioritize_columns
        state_filter = "AND rr.current_state IN (0, 4, 5, 6)"
    elif action == "schedule":
        select_clause = schedule_columns
        state_filter = "AND rr.current_state = 1"
    else:
        raise ValueError(f"Invalid action: {action}")

    # Build the base query
    base_query = f"""
        SELECT 
            {select_clause}
        FROM roadmap_roadmap AS rr 
        LEFT JOIN roadmap_roadmapconstraints AS rrc ON rr.id = rrc.roadmap_id
        LEFT JOIN roadmap_roadmapportfolio AS rp ON rr.id = rp.roadmap_id
        LEFT JOIN projects_portfolio AS pp ON rp.portfolio_id = pp.id
        LEFT JOIN roadmap_roadmapkpi AS rrkpi ON rr.id = rrkpi.roadmap_id
        LEFT JOIN roadmap_roadmapestimate AS rrt ON rrt.roadmap_id = rr.id
        LEFT JOIN roadmap_roadmapscope AS rrs ON rr.id = rrs.roadmap_id
        WHERE rr.tenant_id = {tenant_id}
    """

    # Add state filter
    base_query += f" {state_filter}"

    # Add portfolio filter if provided
    if portfolio_ids:
        portfolio_ids_str = ",".join(map(str, portfolio_ids))
        base_query += f" AND pp.id IN ({portfolio_ids_str})"

    # Add additional filter_string if provided
    if filter_string:
        base_query += f" {filter_string}"

    # Add GROUP BY clause
    base_query += " GROUP BY rr.id;"

    return base_query


def get_recent_queries(user_id, limit=10):
    recent_queries = TangoDao.fetchTangoStatesForUserIdbyKey(user_id=user_id, key="query_history")
    recent_queries_arr = [q.get("value") for q in recent_queries[:limit] if q.get("value")]
    recent_queries_str = json.dumps(recent_queries_arr, indent=2)
    return recent_queries_str
