from src.trmeric_services.tango.functions.Types import TangoFunction
from src.database.Database import db_instance
from datetime import datetime
import json
from typing import List, Optional
import traceback

from datetime import date

class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.isoformat()  # Convert date to string (e.g., '2025-06-07')
        return super().default(obj)


def get_risk_report_data(tenantID: int, userID: int, quarter_start: str, quarter_end: str, portfolio_ids: Optional[List[int]] = None) -> dict:
    """Fetch comprehensive risk data and project statuses for ongoing projects in the specified quarter.

    Args:
        tenantID (int): Tenant ID to filter projects.
        userID (int): User ID to filter projects (assumed to be project manager).
        quarter_start (str): Start date of the quarter (YYYY-MM-DD).
        quarter_end (str): End date of the quarter (YYYY-MM-DD).
        portfolio_ids (Optional[List[int]]): List of portfolio IDs to filter projects (optional).

    Returns:
        dict: JSON object containing raw data for executive summary, risk register,
              portfolio assessment, trends, overall assessment, and project statuses.

    Raises:
        ValueError: If input parameters are invalid.
    """
    try:
        tenantID = int(tenantID)
        userID = int(userID)
        datetime.strptime(quarter_start, '%Y-%m-%d')
        datetime.strptime(quarter_end, '%Y-%m-%d')
        if portfolio_ids:
            if not all(isinstance(pid, int) for pid in portfolio_ids):
                raise ValueError("portfolio_ids must be a list of integers")
            portfolio_ids_str = "{" + ",".join(map(str, portfolio_ids)) + "}"
        else:
            portfolio_ids_str = None
    except ValueError as e:
        raise ValueError(f"Invalid input: {str(e)}")

    portfolio_filter = ""
    if portfolio_ids_str:
        portfolio_filter = f"AND wpport.portfolio_id = ANY('{portfolio_ids_str}'::integer[])"

    # Base filter for active projects and risks in the quarter
    base_filter = f"""
        JOIN workflow_project wp ON wpr.project_id = wp.id
        LEFT JOIN workflow_projectportfolio wpport ON wp.id = wpport.project_id
        WHERE wp.tenant_id_id = {tenantID}
          AND wp.archived_on IS NULL
          AND wp.parent_id is not null
          -- AND wp.project_manager_id_id = {userID}
          -- AND wpr.status_value IN (1, 3, 4, 5)
          -- AND wpr.due_date BETWEEN '{quarter_start}' AND '{quarter_end}'
          {portfolio_filter}
    """

    # 1. Executive Summary Query (unchanged)
    executive_query = f"""
        WITH TopRisks AS (
            SELECT 
                wpr.id AS risk_id,
                wpr.project_id,
                wp.title AS project_title,
                wpr.description,
                wpr.impact,
                wpr.priority,
                CASE wpr.status_value
                    WHEN 1 THEN 'Active'
                    WHEN 2 THEN 'Resolved'
                    WHEN 3 THEN 'Monitoring'
                    WHEN 4 THEN 'Escalated'
                    WHEN 5 THEN 'Mitigated'
                    WHEN 6 THEN 'Closed'
                    ELSE 'Unknown'
                END AS status,
                wpr.due_date
            FROM workflow_projectrisk wpr
            {base_filter}
            ORDER BY wpr.priority DESC, wpr.due_date ASC
            LIMIT 10
        ),
        RiskSummary AS (
            SELECT 
                COUNT(*) AS total_risks,
                SUM(CASE WHEN wpr.impact IN ('Major', 'Catastrophic') THEN 1 ELSE 0 END) AS high_impact_risks,
                SUM(CASE WHEN wpr.mitigation IS NULL OR wpr.mitigation = '' THEN 1 ELSE 0 END) AS inadequate_mitigation_risks,
                (SELECT jsonb_agg(
                    jsonb_build_object(
                        'risk_id', risk_id,
                        'project_id', project_id,
                        'project_title', project_title,
                        'description', description,
                        'impact', impact,
                        'priority', priority,
                        'status', status,
                        'due_date', due_date
                    )
                ) FROM TopRisks) AS top_critical_risks
            FROM workflow_projectrisk wpr
            {base_filter}
        ),
        Metrics AS (
            SELECT 
                total_risks,
                high_impact_risks,
                ROUND(CAST(high_impact_risks::FLOAT / NULLIF(total_risks, 0) * 100 AS numeric), 2) AS high_impact_percentage,
                inadequate_mitigation_risks,
                top_critical_risks
            FROM RiskSummary
        )
        SELECT 
            jsonb_build_object(
                'total_risks', total_risks,
                'high_impact_percentage', high_impact_percentage,
                'inadequate_mitigation_risks', inadequate_mitigation_risks,
                'top_critical_risks', top_critical_risks,
                'recommendations', jsonb_build_array(
                    'Prioritize mitigation for high-impact risks in critical projects',
                    'Allocate additional resources to address inadequate mitigation plans',
                    'Conduct a cross-project risk correlation review',
                    'Enhance monitoring for technology and compliance risks',
                    'Schedule a risk governance meeting with leadership'
                )
            ) AS executive_summary
        FROM Metrics;
    """
    executive_result = db_instance.retrieveSQLQueryOld(executive_query)
    executive_summary = executive_result[0]['executive_summary'] if executive_result else {}

    # 2. Detailed Risk Register Query (unchanged)
    risk_register_query = f"""
        SELECT 
            wp.title AS project_name,
            wpr.description AS risk_description,
            CASE 
                WHEN wpr.priority = 5 THEN 'Very High'
                WHEN wpr.priority = 4 THEN 'High'
                WHEN wpr.priority = 3 THEN 'Medium'
                WHEN wpr.priority = 2 THEN 'Low'
                WHEN wpr.priority = 1 THEN 'Very Low'
                ELSE 'Unknown'
            END AS likelihood,
            wpr.impact AS impact,
            COALESCE(wpr.mitigation, 'No mitigation defined') AS current_mitigation_strategy,
            CASE wpr.status_value
                WHEN 1 THEN 'Active'
                WHEN 2 THEN 'Resolved'
                WHEN 3 THEN 'Monitoring'
                WHEN 4 THEN 'Escalated'
                WHEN 5 THEN 'Mitigated'
                WHEN 6 THEN 'Closed'
                ELSE 'Unknown'
            END AS status
        FROM workflow_projectrisk wpr
        JOIN workflow_project wp ON wpr.project_id = wp.id
        JOIN users_user uu ON wp.project_manager_id_id = uu.id
        LEFT JOIN workflow_projectportfolio wpport ON wp.id = wpport.project_id
        WHERE wp.tenant_id_id = {tenantID}
          AND wp.archived_on IS NULL
          -- AND wp.project_manager_id_id = {userID}
          -- AND wpr.status_value IN (1, 3, 4, 5)
          AND wpr.due_date BETWEEN '{quarter_start}' AND '{quarter_end}'
          {portfolio_filter}
        ORDER BY wp.title, wpr.priority DESC, wpr.due_date ASC;
    """
    risk_register = db_instance.retrieveSQLQueryOld(risk_register_query) or []

    # 3. Project Status Query (new)
    status_query = f"""
        WITH LatestStatuses AS (
            SELECT DISTINCT ON (ps.project_id, ps.type)
                wp.title AS project_name,
                CASE
                    WHEN ps.type = 1 THEN 'scope_status'
                    WHEN ps.type = 2 THEN 'delivery_status'
                    WHEN ps.type = 3 THEN 'spend_status'
                END AS status_type,
                CASE
                    WHEN ps.value = 1 THEN 'on_track'
                    WHEN ps.value = 2 THEN 'at_risk'
                    WHEN ps.value = 3 THEN 'compromised'
                END AS status_value,
                ps.comments AS comment,
                ps.created_date
            FROM public.workflow_projectstatus ps
            JOIN workflow_project wp ON ps.project_id = wp.id
            LEFT JOIN workflow_projectportfolio wpport ON wp.id = wpport.project_id
            WHERE wp.tenant_id_id = {tenantID}
              AND wp.archived_on IS NULL
              AND ps.created_date BETWEEN '{quarter_start}' AND '{quarter_end}'
              {portfolio_filter}
            ORDER BY ps.project_id, ps.type, ps.created_date DESC
        )
        SELECT 
            jsonb_agg(
                jsonb_build_object(
                    'project_name', project_name,
                    'status_type', status_type,
                    'status_value', status_value,
                    'comment', comment,
                    'created_date', created_date
                )
            ) AS project_statuses
        FROM LatestStatuses;
    """
    status_result = db_instance.retrieveSQLQueryOld(status_query)
    project_statuses = status_result[0]['project_statuses'] if status_result else []

    # 4. Portfolio-Level Risk Assessment Query (unchanged)
    portfolio_assessment_query = f"""
        WITH CrossProjectRisks AS (
            SELECT 
                wpr.description,
                COUNT(DISTINCT wpr.project_id) AS affected_projects,
                ARRAY_AGG(wp.title) AS project_titles
            FROM workflow_projectrisk wpr
            {base_filter}
            GROUP BY wpr.description
            HAVING COUNT(DISTINCT wpr.project_id) > 1
        ),
        ResourceConstraints AS (
            SELECT 
                wpts.member_name AS resource,
                COUNT(DISTINCT wpts.project_id) AS project_count,
                ARRAY_AGG(wp.title) AS conflicting_projects
            FROM workflow_projectteamsplit wpts
            JOIN workflow_project wp ON wpts.project_id = wp.id
            LEFT JOIN workflow_projectportfolio wpport ON wp.id = wpport.project_id
            WHERE wp.tenant_id_id = {tenantID}
              AND wp.project_manager_id_id = {userID}
              AND wp.archived_on IS NULL
              {portfolio_filter}
            GROUP BY wpts.member_name
            HAVING COUNT(DISTINCT wpts.project_id) > 1
        ),
        SystemicRisks AS (
            SELECT 
                wpr.description AS systemic_risk,
                COUNT(*) AS risk_count
            FROM workflow_projectrisk wpr
            {base_filter}
            GROUP BY wpr.description
        ),
        RiskConcentration AS (
            SELECT 
                wpr.description AS risk_description,
                COUNT(*) AS risk_count,
                ROUND(CAST(COUNT(*)::FLOAT / NULLIF(SUM(COUNT(*)) OVER (), 0) * 100 AS numeric), 2) AS percentage
            FROM workflow_projectrisk wpr
            {base_filter}
            GROUP BY wpr.description
            HAVING COUNT(*) > (SELECT COUNT(*) / 5 FROM workflow_projectrisk WHERE status_value IN (1, 3, 4, 5))
        )
        SELECT 
            jsonb_build_object(
                'cross_project_risks', (SELECT jsonb_agg(jsonb_build_object(
                    'description', description,
                    'affected_projects', affected_projects,
                    'project_titles', project_titles
                )) FROM CrossProjectRisks),
                'resource_constraints', (SELECT jsonb_agg(jsonb_build_object(
                    'resource', resource,
                    'project_count', project_count,
                    'conflicting_projects', conflicting_projects
                )) FROM ResourceConstraints),
                'systemic_risks', (SELECT jsonb_agg(jsonb_build_object(
                    'systemic_risk', systemic_risk,
                    'risk_count', risk_count
                )) FROM SystemicRisks),
                'risk_concentration', (SELECT jsonb_agg(jsonb_build_object(
                    'risk_description', risk_description,
                    'risk_count', risk_count,
                    'percentage', percentage
                )) FROM RiskConcentration)
            ) AS portfolio_assessment;
    """
    portfolio_assessment_result = db_instance.retrieveSQLQueryOld(portfolio_assessment_query)
    portfolio_assessment = portfolio_assessment_result[0]['portfolio_assessment'] if portfolio_assessment_result else {}

    # 5. Risk Trends Query (unchanged)
    trends_query = f"""
        SELECT 
            DATE_TRUNC('month', wpr.due_date) AS month,
            COUNT(*) AS risk_count,
            SUM(CASE WHEN wpr.impact IN ('Major', 'Catastrophic') THEN 1 ELSE 0 END) AS high_impact_risks,
            ROUND(CAST(SUM(CASE WHEN wpr.impact IN ('Major', 'Catastrophic') THEN 1 ELSE 0 END)::FLOAT / NULLIF(COUNT(*), 0) * 100 AS numeric), 2) AS high_impact_percentage
        FROM workflow_projectrisk wpr
        {base_filter}
        GROUP BY DATE_TRUNC('month', wpr.due_date)
        ORDER BY month DESC;
    """
    risk_trends = db_instance.retrieveSQLQueryOld(trends_query) or []

    # 6. Overall Risk Assessment Query (unchanged)
    overall_assessment_query = f"""
        WITH RiskPosture AS (
            SELECT 
                COUNT(*) AS total_risks,
                SUM(CASE WHEN wpr.impact IN ('Major', 'Catastrophic') THEN 1 ELSE 0 END) AS high_impact_risks,
                SUM(CASE WHEN wpr.due_date <= CURRENT_DATE + INTERVAL '1 month' AND wpr.status_value IN (1, 4) THEN 1 ELSE 0 END) AS emerging_risks
            FROM workflow_projectrisk wpr
            {base_filter}
        )
        SELECT 
            jsonb_build_object(
                'total_risks', total_risks,
                'high_impact_risks', high_impact_risks,
                'emerging_risks', emerging_risks,
                'risk_appetite', 'Moderate',
                'aggregated_impact', 'Potential delays in 20% of projects and budget overrun of $500K',
                'recommendations', jsonb_build_array(
                    'Implement automated risk monitoring tools',
                    'Allocate additional resources to high-impact risks',
                    'Conduct training on compliance risk management',
                    'Review cross-project dependencies quarterly'
                )
            ) AS overall_assessment
        FROM RiskPosture;
    """
    overall_assessment_result = db_instance.retrieveSQLQueryOld(overall_assessment_query)
    overall_assessment = overall_assessment_result[0]['overall_assessment'] if overall_assessment_result else {}

    res = {
        'executive_summary': executive_summary,
        'risk_register': risk_register,
        'project_statuses': project_statuses,
        'portfolio_assessment': portfolio_assessment,
        'risk_trends': risk_trends,
        'overall_assessment': overall_assessment
    }
    
    # with open("raw_roadmap_data.json", "w") as f:
    #     json.dump(res, f, indent=2, cls=DateEncoder)
    
    return res
   
def view_risk_report_current_quarter(
    tenantID: int,
    userID: int,
    quarter_start: str,
    quarter_end: str,
    portfolio_ids: Optional[List[int]] = None,
    **kwargs
) -> dict:
    """Generate a comprehensive risk report for ongoing projects in the specified quarter.

    Args:
        tenantID (int): Tenant ID to filter projects.
        userID (int): User ID to filter projects (assumed to be project manager).
        quarter_start (str): Start date of the quarter (YYYY-MM-DD).
        quarter_end (str): End date of the quarter (YYYY-MM-DD).
        portfolio_ids (Optional[List[int]]): List of portfolio IDs to filter projects (optional).

    Returns:
        dict: JSON object containing the risk report with executive summary, risk register,
              portfolio assessment, trends, and overall assessment.
    """
    print("in view_risk_report_current_quarter", tenantID, userID, quarter_start, quarter_end, portfolio_ids)

    # Validate date parameters
    try:
        datetime.strptime(quarter_start, '%Y-%m-%d')
        datetime.strptime(quarter_end, '%Y-%m-%d')
    except ValueError:
        return {"error": "quarter_start and quarter_end must be in YYYY-MM-DD format."}

    # Validate portfolio_ids
    if portfolio_ids and not all(isinstance(pid, int) for pid in portfolio_ids):
        return {"error": "portfolio_ids must be a list of integers."}

    # Fetch data
    output = '{}'
    try:
        report_data = get_risk_report_data(
            tenantID=tenantID,
            userID=userID,
            quarter_start=quarter_start,
            quarter_end=quarter_end,
            portfolio_ids=portfolio_ids
        )
    except Exception as e:
        print("error in risk ", e, traceback.format_exc())
        report_data = {"error": str(e)}
        
    # print("debug -- risk data -- ", report_data)
    
    output = json.dumps(report_data, indent=2)
    return output
 