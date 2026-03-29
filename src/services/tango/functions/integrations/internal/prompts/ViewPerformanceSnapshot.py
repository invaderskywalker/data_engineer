from src.trmeric_services.tango.functions.Types import TangoFunction
from src.trmeric_services.tango.functions.integrations.internal.helpers.SQLHandler import (
    SQL_Handler
)
from src.database.Database import db_instance
from src.database.dao.portfolios import PortfolioDao
from datetime import datetime
from typing import List

def getClosedProjectIdsLastQuarter(
    tenantID: int, 
    last_quarter_start: str, 
    last_quarter_end: str, 
    eligible_project_ids: List[int], 
    portfolio_ids: List[int] = None
) -> List[int]:
    try:
        tenantID = int(tenantID)
        datetime.strptime(last_quarter_start, '%Y-%m-%d')
        datetime.strptime(last_quarter_end, '%Y-%m-%d')
        eligible_project_ids = [int(pid) for pid in eligible_project_ids]
        portfolio_ids = [int(pid) for pid in portfolio_ids] if portfolio_ids else []

        eligible_project_ids_str = f"({', '.join(map(str, eligible_project_ids))})" if eligible_project_ids else "(0)"  # Commented out as per request
        portfolio_filter = f"AND po.portfolio_id IN ({', '.join(map(str, portfolio_ids))})" if portfolio_ids else ""

        query = f"""
            WITH PortfolioData AS (
                SELECT 
                    wpport.project_id, 
                    MAX(pp.id) AS portfolio_id
                FROM workflow_projectportfolio AS wpport
                LEFT JOIN projects_portfolio AS pp ON wpport.portfolio_id = pp.id
                GROUP BY wpport.project_id
            )
            SELECT 
                wp.id AS project_id
            FROM 
                workflow_project AS wp
            LEFT JOIN 
                PortfolioData AS po ON wp.id = po.project_id
            WHERE 
                wp.tenant_id_id = {tenantID}
                AND wp.archived_on BETWEEN '{last_quarter_start}' AND '{last_quarter_end}'
                AND wp.parent_id IS NOT NULL;
        """
        result = db_instance.retrieveSQLQueryOld(query)
        return [row["project_id"] for row in result] if result else []
    except Exception as e:
        print(f"Error in getClosedProjectIdsLastQuarter: {str(e)}")
        return []

def getCompletedProjectsLastQuarter(
    tenantID: int, 
    closed_project_ids: List[int], 
    last_quarter_start: str, 
    last_quarter_end: str, 
    eligible_project_ids: List[int], 
    portfolio_ids: List[int] = None
):
    try:
        tenantID = int(tenantID)
        closed_project_ids = [int(pid) for pid in closed_project_ids]
        datetime.strptime(last_quarter_start, '%Y-%m-%d')
        datetime.strptime(last_quarter_end, '%Y-%m-%d')
        eligible_project_ids = [int(pid) for pid in eligible_project_ids]
        portfolio_ids = [int(pid) for pid in portfolio_ids] if portfolio_ids else []

        # Remove intersection with eligible_project_ids
        filtered_project_ids = closed_project_ids  # Changed from list(set(closed_project_ids) & set(eligible_project_ids))
        project_ids_str = f"({', '.join(map(str, filtered_project_ids))})" if filtered_project_ids else "(0)"
        portfolio_filter = f"AND po.portfolio_id IN ({', '.join(map(str, portfolio_ids))})" if portfolio_ids else ""

        query = f"""
            WITH PortfolioData AS (
                SELECT 
                    wpport.project_id, 
                    MAX(pp.id) AS portfolio_id
                FROM workflow_projectportfolio AS wpport
                LEFT JOIN projects_portfolio AS pp ON wpport.portfolio_id = pp.id
                GROUP BY wpport.project_id
            )
            SELECT 
                wp.id AS "Project ID",
                wp.title AS "Project Title",
                TO_CHAR(wp.start_date, 'YYYY-MM-DD') AS "Original Start Date",
                TO_CHAR(wp.end_date, 'YYYY-MM-DD') AS "Original End Date",
                TO_CHAR(wp.archived_on, 'YYYY-MM-DD') AS "Actual Closure Date",
                COALESCE(wp.total_external_spend, 0) AS "Original Budget",
                COALESCE(SUM(wpm.actual_spend), 0) AS "Actual Budget",
                CASE 
                    WHEN MAX(CASE WHEN wps.type = 1 THEN wps.value END) = 1 THEN 'Green'
                    WHEN MAX(CASE WHEN wps.type = 1 THEN wps.value END) = 2 THEN 'Amber'
                    WHEN MAX(CASE WHEN wps.type = 1 THEN wps.value END) = 3 THEN 'Red'
                    ELSE 'Unknown'
                END AS "Final Scope Status",
                CASE 
                    WHEN MAX(CASE WHEN wps.type = 2 THEN wps.value END) = 1 THEN 'Green'
                    WHEN MAX(CASE WHEN wps.type = 2 THEN wps.value END) = 2 THEN 'Amber'
                    WHEN MAX(CASE WHEN wps.type = 2 THEN wps.value END) = 3 THEN 'Red'
                    ELSE 'Unknown'
                END AS "Final Schedule Status",
                CASE 
                    WHEN MAX(CASE WHEN wps.type = 3 THEN wps.value END) = 1 THEN 'Green'
                    WHEN MAX(CASE WHEN wps.type = 3 THEN wps.value END) = 2 THEN 'Amber'
                    WHEN MAX(CASE WHEN wps.type = 3 THEN wps.value END) = 3 THEN 'Red'
                    ELSE 'Unknown'
                END AS "Final Spend Status",
                ARRAY_AGG(DISTINCT jsonb_build_object(
                    'name', wpm.name,
                    'target_date', wpm.target_date,
                    'actual_spend', wpm.actual_spend,
                    'planned_spend', wpm.planned_spend,
                    'status_value', CASE 
                        WHEN wpm.status_value = 1 THEN 'Not Started'
                        WHEN wpm.status_value = 2 THEN 'In Progress'
                        WHEN wpm.status_value = 3 THEN 'Completed'
                        ELSE 'Unknown'
                    END
                )) FILTER (WHERE wpm.id IS NOT NULL) AS "Milestones"
            FROM 
                workflow_project AS wp
            LEFT JOIN 
                workflow_projectmilestone AS wpm ON wp.id = wpm.project_id
            LEFT JOIN 
                workflow_projectstatus AS wps ON wp.id = wps.project_id
            LEFT JOIN 
                PortfolioData AS po ON wp.id = po.project_id
            WHERE 
                wp.tenant_id_id = {tenantID}
                AND wp.id IN {project_ids_str}
                {portfolio_filter}
            GROUP BY 
                wp.id, wp.title, wp.start_date, wp.end_date, wp.archived_on, wp.total_external_spend
            ORDER BY 
                wp.archived_on DESC;
        """
        return db_instance.retrieveSQLQueryOld(query)
    except Exception as e:
        print(f"Error in getCompletedProjectsLastQuarter: {str(e)}")
        return []

def getBusinessValueFromProjects(
    tenantID: int, 
    closed_project_ids: List[int], 
    eligible_project_ids: List[int], 
    portfolio_ids: List[int] = None
):
    try:
        tenantID = int(tenantID)
        closed_project_ids = [int(pid) for pid in closed_project_ids]
        eligible_project_ids = [int(pid) for pid in eligible_project_ids]
        portfolio_ids = [int(pid) for pid in portfolio_ids] if portfolio_ids else []

        # Remove intersection with eligible_project_ids
        filtered_project_ids = closed_project_ids  # Changed from list(set(closed_project_ids) & set(eligible_project_ids))
        project_ids_str = f"({', '.join(map(str, filtered_project_ids))})" if filtered_project_ids else "(0)"
        portfolio_filter = f"AND po.portfolio_id IN ({', '.join(map(str, portfolio_ids))})" if portfolio_ids else ""

        query = f"""
            WITH PortfolioData AS (
                SELECT 
                    wpport.project_id, 
                    MAX(pp.id) AS portfolio_id
                FROM workflow_projectportfolio AS wpport
                LEFT JOIN projects_portfolio AS pp ON wpport.portfolio_id = pp.id
                GROUP BY wpport.project_id
            )
            SELECT 
                wp.id AS "Project ID",
                wp.title AS "Project Title",
                wp.objectives AS "Objectives",
                ARRAY_AGG(DISTINCT jsonb_build_object(
                    'name', wpkpi.name
                )) AS "Key Results"
            FROM 
                workflow_project AS wp
            LEFT JOIN 
                workflow_projectkpi AS wpkpi ON wpkpi.project_id = wp.id
            LEFT JOIN 
                PortfolioData AS po ON wp.id = po.project_id
            WHERE 
                wp.tenant_id_id = {tenantID}
                AND wp.id IN {project_ids_str}
                {portfolio_filter}
            GROUP BY 
                wp.id, wp.title, wp.objectives;
        """
        return db_instance.retrieveSQLQueryOld(query)
    except Exception as e:
        print(f"Error in getBusinessValueFromProjects: {str(e)}")
        return []

def getLearningsFromRetrospectives(
    tenantID: int, 
    closed_project_ids: List[int], 
    eligible_project_ids: List[int], 
    portfolio_ids: List[int] = None
):
    try:
        tenantID = int(tenantID)
        closed_project_ids = [int(pid) for pid in closed_project_ids]
        eligible_project_ids = [int(pid) for pid in eligible_project_ids]
        portfolio_ids = [int(pid) for pid in portfolio_ids] if portfolio_ids else []

        # Remove intersection with eligible_project_ids
        filtered_project_ids = closed_project_ids  # Changed from list(set(closed_project_ids) & set(eligible_project_ids))
        project_ids_str = f"({', '.join(map(str, filtered_project_ids))})" if filtered_project_ids else "(0)"
        portfolio_filter = f"AND po.portfolio_id IN ({', '.join(map(str, portfolio_ids))})" if portfolio_ids else ""

        query = f"""
            WITH PortfolioData AS (
                SELECT 
                    wpport.project_id, 
                    MAX(pp.id) AS portfolio_id
                FROM workflow_projectportfolio AS wpport
                LEFT JOIN projects_portfolio AS pp ON wpport.portfolio_id = pp.id
                GROUP BY wpport.project_id
            )
            SELECT 
                wp.id AS "Project ID",
                wp.title AS "Project Title",
                ARRAY_AGG(DISTINCT wpr.things_to_keep_doing) AS "Things to Keep Doing",
                ARRAY_AGG(DISTINCT wpr.areas_for_improvement) AS "Areas for Improvement",
                ARRAY_AGG(DISTINCT wpr.detailed_analysis) AS "Detailed Analysis"
            FROM 
                workflow_project AS wp
            LEFT JOIN 
                workflow_projectretro AS wpr ON wpr.project_id = wp.id
            LEFT JOIN 
                PortfolioData AS po ON wp.id = po.project_id
            WHERE 
                wp.tenant_id_id = {tenantID}
                AND wp.id IN {project_ids_str}
                {portfolio_filter}
            GROUP BY 
                wp.id, wp.title;
        """
        return db_instance.retrieveSQLQueryOld(query)
    except Exception as e:
        print(f"Error in getLearningsFromRetrospectives: {str(e)}")
        return []

def getNewRoadmapsLastQuarter(
    tenantID: int, 
    condition: str, 
    last_quarter_start: str, 
    last_quarter_end: str, 
    eligible_project_ids: List[int], 
    portfolio_ids: List[int] = None
):
    try:
        tenantID = int(tenantID)
        datetime.strptime(last_quarter_start, '%Y-%m-%d')
        datetime.strptime(last_quarter_end, '%Y-%m-%d')
        eligible_project_ids = [int(pid) for pid in eligible_project_ids]
        portfolio_ids = [int(pid) for pid in portfolio_ids] if portfolio_ids else []

        eligible_project_ids_str = f"({', '.join(map(str, eligible_project_ids))})" if eligible_project_ids else "(0)"  # Commented out as per request
        portfolio_filter = f"AND rp.portfolio_id IN ({', '.join(map(str, portfolio_ids))})" if portfolio_ids else ""
        filter_string = f"AND rr.created_on BETWEEN '{last_quarter_start}' AND '{last_quarter_end}' {condition}"

        query = f"""
            SELECT 
                rr.title AS "Roadmap Title",
                TO_CHAR(rr.created_on, 'YYYY-MM-DD') AS "Created Date",
                TO_CHAR(rr.budget, '$999,999,999') AS "Budget",
                json_agg(DISTINCT pp.title) FILTER (WHERE pp.title IS NOT NULL) AS "Associated Portfolios",
                json_agg(DISTINCT rrkpi.name) FILTER (WHERE rrkpi.name IS NOT NULL) AS "Key Results"
            FROM 
                roadmap_roadmap AS rr
            LEFT JOIN 
                roadmap_roadmapportfolio AS rp ON rr.id = rp.roadmap_id
            LEFT JOIN 
                projects_portfolio AS pp ON rp.portfolio_id = pp.id
            LEFT JOIN 
                roadmap_roadmapkpi AS rrkpi ON rr.id = rrkpi.roadmap_id
            LEFT JOIN 
                workflow_project AS wp ON wp.portfolio_id_id = pp.id
            WHERE 
                rr.tenant_id = {tenantID}
                {filter_string}
                {portfolio_filter}
                -- AND (wp.id IS NULL OR wp.id IN {eligible_project_ids_str})  -- Commented out eligible projects condition
            GROUP BY 
                rr.title, rr.created_on, rr.budget
            ORDER BY 
                rr.created_on DESC;
        """
        return db_instance.retrieveSQLQueryOld(query)
    except Exception as e:
        print(f"Error in getNewRoadmapsLastQuarter: {str(e)}")
        return []

def getExecutiveSummary(
    tenantID: int, 
    last_quarter_start: str, 
    last_quarter_end: str, 
    eligible_project_ids: List[int], 
    portfolio_ids: List[int] = None
):
    try:
        tenantID = int(tenantID)
        datetime.strptime(last_quarter_start, '%Y-%m-%d')
        datetime.strptime(last_quarter_end, '%Y-%m-%d')
        eligible_project_ids = [int(pid) for pid in eligible_project_ids]
        portfolio_ids = [int(pid) for pid in portfolio_ids] if portfolio_ids else []

        eligible_project_ids_str = f"({', '.join(map(str, eligible_project_ids))})" if eligible_project_ids else "(0)"  # Commented out as per request
        portfolio_filter = f"AND po.portfolio_id IN ({', '.join(map(str, portfolio_ids))})" if portfolio_ids else ""

        query = f"""
            WITH PortfolioData AS (
                SELECT 
                    wpport.project_id, 
                    MAX(pp.id) AS portfolio_id
                FROM workflow_projectportfolio AS wpport
                LEFT JOIN projects_portfolio AS pp ON wpport.portfolio_id = pp.id
                GROUP BY wpport.project_id
            )
            SELECT 
                COUNT(DISTINCT CASE WHEN wp.archived_on IS NULL THEN wp.id END) AS ongoing_count,
                COUNT(DISTINCT CASE WHEN wp.archived_on BETWEEN '{last_quarter_start}' AND '{last_quarter_end}' THEN wp.id END) AS closed_count,
                COALESCE(AVG(CASE WHEN wp.archived_on IS NULL THEN wpm.actual_spend / NULLIF(wpm.planned_spend, 0) END), 0) AS avg_cpi,
                COALESCE(SUM(CASE WHEN wp.archived_on IS NULL THEN wpm.actual_spend END), 0) AS total_spend_ongoing,
                COALESCE(SUM(CASE WHEN wp.archived_on BETWEEN '{last_quarter_start}' AND '{last_quarter_end}' THEN wpm.actual_spend END), 0) AS total_spend_closed
            FROM workflow_project AS wp
            LEFT JOIN workflow_projectmilestone AS wpm ON wp.id = wpm.project_id
            LEFT JOIN PortfolioData AS po ON wp.id = po.project_id
            WHERE wp.tenant_id_id = {tenantID}
                -- AND wp.id IN {eligible_project_ids_str}  -- Commented out eligible projects condition
                AND wp.parent_id IS NOT NULL
                {portfolio_filter};
        """
        return db_instance.retrieveSQLQueryOld(query)
    except Exception as e:
        print(f"Error in getExecutiveSummary: {str(e)}")
        return "## Executive Summary\nError retrieving data."

def getPortfolioOverview(
    tenantID: int, 
    last_quarter_start: str, 
    last_quarter_end: str, 
    eligible_project_ids: List[int], 
    portfolio_ids: List[int] = None
):
    try:
        tenantID = int(tenantID)
        datetime.strptime(last_quarter_start, '%Y-%m-%d')
        datetime.strptime(last_quarter_end, '%Y-%m-%d')
        eligible_project_ids = [int(pid) for pid in eligible_project_ids]
        portfolio_ids = [int(pid) for pid in portfolio_ids] if portfolio_ids else []

        eligible_project_ids_str = f"({', '.join(map(str, eligible_project_ids))})" if eligible_project_ids else "(0)"  # Commented out as per request
        portfolio_filter = f"AND po.portfolio_id IN ({', '.join(map(str, portfolio_ids))})" if portfolio_ids else ""

        query = f"""
            WITH PortfolioData AS (
                SELECT 
                    wpport.project_id, 
                    MAX(pp.id) AS portfolio_id,
                    MAX(pp.title) AS title
                FROM workflow_projectportfolio AS wpport
                LEFT JOIN projects_portfolio AS pp ON wpport.portfolio_id = pp.id
                GROUP BY wpport.project_id
            ),
            ProjectTotals AS (
                SELECT 
                    COUNT(DISTINCT CASE WHEN wp.archived_on IS NULL THEN wp.id END) AS ongoing_count,
                    COUNT(DISTINCT CASE WHEN wp.archived_on BETWEEN '{last_quarter_start}' AND '{last_quarter_end}' THEN wp.id END) AS closed_count,
                    COALESCE(SUM(CASE WHEN wp.archived_on IS NULL THEN wp.total_external_spend END), 0) AS ongoing_budget,
                    COALESCE(SUM(CASE WHEN wp.archived_on BETWEEN '{last_quarter_start}' AND '{last_quarter_end}' THEN wp.total_external_spend END), 0) AS closed_budget,
                    COALESCE(AVG(wpts.member_utilization), 0) AS avg_resource_utilization
                FROM workflow_project AS wp
                LEFT JOIN workflow_projectteamsplit AS wpts ON wp.id = wpts.project_id
                LEFT JOIN PortfolioData AS po ON wp.id = po.project_id
                WHERE wp.tenant_id_id = {tenantID}
                    -- AND wp.id IN {eligible_project_ids_str}  -- Commented out eligible projects condition
                    AND wp.parent_id IS NOT NULL
                    {portfolio_filter}
            ),
            PortfolioCounts AS (
                SELECT 
                    COALESCE(po.title, 'Uncategorized') AS pillar,
                    COUNT(DISTINCT wp.id) AS project_count,
                    COALESCE(SUM(wp.total_external_spend), 0) AS total_budget,
                    COUNT(DISTINCT wp.id)::FLOAT / SUM(COUNT(DISTINCT wp.id)) OVER () * 100 AS percent_portfolio
                FROM workflow_project AS wp
                LEFT JOIN PortfolioData AS po ON wp.id = po.project_id
                WHERE wp.tenant_id_id = {tenantID}
                    -- AND wp.id IN {eligible_project_ids_str}  -- Commented out eligible projects condition
                    AND wp.parent_id IS NOT NULL
                    {portfolio_filter}
                GROUP BY COALESCE(po.title, 'Uncategorized')
            )
            SELECT 
                pt.ongoing_count AS "Ongoing Projects",
                pt.closed_count AS "Closed Projects",
                pt.ongoing_budget AS "Ongoing Budget",
                pt.closed_budget AS "Closed Budget",
                pt.avg_resource_utilization AS "Average Resource Utilization",
                ARRAY_AGG(DISTINCT jsonb_build_object(
                    'pillar', pc.pillar,
                    'project_count', pc.project_count,
                    'total_budget', pc.total_budget,
                    'percent_portfolio', COALESCE(pc.percent_portfolio, 0)
                )) AS "Strategic Pillars"
            FROM ProjectTotals AS pt
            CROSS JOIN PortfolioCounts AS pc
            GROUP BY pt.ongoing_count, pt.closed_count, pt.ongoing_budget, pt.closed_budget, pt.avg_resource_utilization;
        """
        return db_instance.retrieveSQLQueryOld(query)
    except Exception as e:
        print(f"Error in getPortfolioOverview: {str(e)}")
        return "Error retrieving portfolio overview."

def getOngoingProjects(
    tenantID: int, 
    last_quarter_start: str, 
    last_quarter_end: str, 
    eligible_project_ids: List[int], 
    portfolio_ids: List[int] = None
):
    try:
        tenantID = int(tenantID)
        datetime.strptime(last_quarter_start, '%Y-%m-%d')
        datetime.strptime(last_quarter_end, '%Y-%m-%d')
        eligible_project_ids = [int(pid) for pid in eligible_project_ids]
        portfolio_ids = [int(pid) for pid in portfolio_ids] if portfolio_ids else []

        eligible_project_ids_str = f"({', '.join(map(str, eligible_project_ids))})" if eligible_project_ids else "(0)"  # Commented out as per request
        portfolio_filter = f"AND po.portfolio_id IN ({', '.join(map(str, portfolio_ids))})" if portfolio_ids else ""

        query = f"""
            WITH PortfolioData AS (
                SELECT 
                    wpport.project_id, 
                    MAX(pp.id) AS portfolio_id
                FROM workflow_projectportfolio AS wpport
                LEFT JOIN projects_portfolio AS pp ON wpport.portfolio_id = pp.id
                GROUP BY wpport.project_id
            )
            SELECT 
                wp.id AS "Project ID",
                wp.title AS "Project Title",
                wp.objectives AS "Objectives",
                COALESCE(SUM(wpm.actual_spend), 0) AS "Actual Budget",
                COALESCE(wp.total_external_spend, 0) AS "Planned Budget",
                COALESCE(AVG(wps.actual_percentage), 0) AS "Percent Complete",
                CASE 
                    WHEN MAX(CASE WHEN wps.type = 1 THEN wps.value END) = 1 THEN 'Green'
                    WHEN MAX(CASE WHEN wps.type = 1 THEN wps.value END) = 2 THEN 'Amber'
                    WHEN MAX(CASE WHEN wps.type = 1 THEN wps.value END) = 3 THEN 'Red'
                    ELSE 'Unknown'
                END AS "Scope Status",
                CASE 
                    WHEN MAX(CASE WHEN wps.type = 2 THEN wps.value END) = 1 THEN 'Green'
                    WHEN MAX(CASE WHEN wps.type = 2 THEN wps.value END) = 2 THEN 'Amber'
                    WHEN MAX(CASE WHEN wps.type = 2 THEN wps.value END) = 3 THEN 'Red'
                    ELSE 'Unknown'
                END AS "Schedule Status",
                CASE 
                    WHEN MAX(CASE WHEN wps.type = 3 THEN wps.value END) = 1 THEN 'Green'
                    WHEN MAX(CASE WHEN wps.type = 3 THEN wps.value END) = 2 THEN 'Amber'
                    WHEN MAX(CASE WHEN wps.type = 3 THEN wps.value END) = 3 THEN 'Red'
                    ELSE 'Unknown'
                END AS "Spend Status",
                ARRAY_AGG(DISTINCT jsonb_build_object(
                    'name', wpm.name,
                    'target_date', wpm.target_date,
                    'status_value', CASE 
                        WHEN wpm.status_value = 1 THEN 'Not Started'
                        WHEN wpm.status_value = 2 THEN 'In Progress'
                        WHEN wpm.status_value = 3 THEN 'Completed'
                        ELSE 'Unknown'
                    END
                )) FILTER (WHERE wpm.id IS NOT NULL) AS "Milestones",
                ARRAY_AGG(DISTINCT jsonb_build_object(
                    'risk_id', pr.id,
                    'description', pr.description,
                    'impact', pr.impact,
                    'status_value', pr.status_value
                )) FILTER (WHERE pr.id IS NOT NULL) AS "Risks",
                COALESCE(AVG(wpts.member_utilization), 0) AS "Resource utilization"
            FROM workflow_project AS wp
            LEFT JOIN workflow_projectmilestone AS wpm ON wp.id = wpm.project_id
            LEFT JOIN workflow_projectstatus AS wps ON wp.id = wps.project_id
            LEFT JOIN workflow_projectteamsplit AS wpts ON wp.id = wpts.project_id
            LEFT JOIN workflow_projectrisk AS pr ON wp.id = pr.project_id
            LEFT JOIN PortfolioData AS po ON wp.id = po.project_id
            WHERE wp.tenant_id_id = {tenantID}
                AND wp.archived_on IS NULL
                AND wp.parent_id IS NOT NULL
                -- AND wp.id IN {eligible_project_ids_str}  -- Commented out eligible projects condition
                AND wp.created_on BETWEEN '{last_quarter_start}' AND '{last_quarter_end}'
                {portfolio_filter}
            GROUP BY wp.id, wp.title, wp.objectives, wp.total_external_spend
            ORDER BY wp.total_external_spend DESC
        """
        return db_instance.retrieveSQLQueryOld(query)
    except Exception as e:
        print(f"Error in getOngoingProjects: {str(e)}")
        return "Error retrieving ongoing projects."

def getPortfolioPerformance(
    tenantID: int, 
    last_quarter_start: str, 
    last_quarter_end: str, 
    eligible_project_ids: List[int], 
    portfolio_ids: List[int] = None
):
    try:
        tenantID = int(tenantID)
        datetime.strptime(last_quarter_start, '%Y-%m-%d')
        datetime.strptime(last_quarter_end, '%Y-%m-%d')
        eligible_project_ids = [int(pid) for pid in eligible_project_ids]
        portfolio_ids = [int(pid) for pid in portfolio_ids] if portfolio_ids else []

        eligible_project_ids_str = f"({', '.join(map(str, eligible_project_ids))})" if eligible_project_ids else "(0)"  # Commented out as per request
        portfolio_filter = f"AND po.portfolio_id IN ({', '.join(map(str, portfolio_ids))})" if portfolio_ids else ""

        query = f"""
            WITH PortfolioData AS (
                SELECT 
                    wpport.project_id, 
                    MAX(pp.id) AS portfolio_id
                FROM workflow_projectportfolio AS wpport
                LEFT JOIN projects_portfolio AS pp ON wpport.portfolio_id = pp.id
                GROUP BY wpport.project_id
            )
            SELECT 
                COALESCE(AVG(wpm.actual_spend / NULLIF(wpm.planned_spend, 0)), 0) AS "Average CPI",
                COALESCE(AVG(wps.actual_percentage), 0) AS "Average Percent Complete",
                COALESCE(SUM(wpm.actual_spend) / NULLIF(SUM(wp.total_external_spend), 0) * 100, 0) AS "Percent Budget Spent"
            FROM workflow_project AS wp
            LEFT JOIN workflow_projectmilestone AS wpm ON wp.id = wpm.project_id
            LEFT JOIN workflow_projectstatus AS wps ON wp.id = wps.project_id
            LEFT JOIN PortfolioData AS po ON wp.id = po.project_id
            WHERE wp.tenant_id_id = {tenantID}
                AND (wp.archived_on IS NULL OR wp.archived_on BETWEEN '{last_quarter_start}' AND '{last_quarter_end}')
                AND wp.parent_id IS NOT NULL
                -- AND wp.id IN {eligible_project_ids_str}  -- Commented out eligible projects condition
                {portfolio_filter};
        """
        return db_instance.retrieveSQLQueryOld(query)
    except Exception as e:
        print(f"Error in getPortfolioPerformance: {str(e)}")
        return "## Overall Portfolio Performance Analysis\nError retrieving data."

def view_performance_snapshot_last_quarter(
    eligibleProjects: List[int],
    tenantID: int,
    userID: int,
    last_quarter_start: str,
    last_quarter_end: str,
    **kwargs
):
    try:
        # Validate inputs
        tenantID = int(tenantID)
        userID = int(userID)
        eligibleProjects = [int(pid) for pid in eligibleProjects] if eligibleProjects else []
        portfolio_ids = [int(pid) for pid in kwargs.get("portfolio_ids", [])] if kwargs.get("portfolio_ids") else []
        datetime.strptime(last_quarter_start, '%Y-%m-%d')
        datetime.strptime(last_quarter_end, '%Y-%m-%d')

        # Removed check for empty eligibleProjects since eligible project conditions are commented out
        print("in view_performance_snapshot_last_quarter ", eligibleProjects, tenantID, userID, last_quarter_start, last_quarter_end, portfolio_ids)

        closed_project_ids = getClosedProjectIdsLastQuarter(
            tenantID=tenantID,
            last_quarter_start=last_quarter_start,
            last_quarter_end=last_quarter_end,
            eligible_project_ids=eligibleProjects,
            portfolio_ids=portfolio_ids
        )
        print("closed project IDs --- ", closed_project_ids)

        completed_projects = getCompletedProjectsLastQuarter(
            tenantID=tenantID,
            closed_project_ids=closed_project_ids,
            last_quarter_start=last_quarter_start,
            last_quarter_end=last_quarter_end,
            eligible_project_ids=eligibleProjects,
            portfolio_ids=portfolio_ids
        )

        business_value = getBusinessValueFromProjects(
            tenantID=tenantID,
            closed_project_ids=closed_project_ids,
            eligible_project_ids=eligibleProjects,
            portfolio_ids=portfolio_ids
        )

        learnings = getLearningsFromRetrospectives(
            tenantID=tenantID,
            closed_project_ids=closed_project_ids,
            eligible_project_ids=eligibleProjects,
            portfolio_ids=portfolio_ids
        )

        condition = ""
        new_roadmaps = getNewRoadmapsLastQuarter(
            tenantID=tenantID,
            condition=condition,
            last_quarter_start=last_quarter_start,
            last_quarter_end=last_quarter_end,
            eligible_project_ids=eligibleProjects,
            portfolio_ids=portfolio_ids
        )
        executive_summary = getExecutiveSummary(
            tenantID=tenantID,
            last_quarter_start=last_quarter_start,
            last_quarter_end=last_quarter_end,
            eligible_project_ids=eligibleProjects,
            portfolio_ids=portfolio_ids
        )
        ongoing_projects_performance = getOngoingProjects(
            tenantID=tenantID,
            last_quarter_start=last_quarter_start,
            last_quarter_end=last_quarter_end,
            eligible_project_ids=eligibleProjects,
            portfolio_ids=portfolio_ids
        )
        portfolio_overview = getPortfolioOverview(
            tenantID=tenantID,
            last_quarter_start=last_quarter_start,
            last_quarter_end=last_quarter_end,
            eligible_project_ids=eligibleProjects,
            portfolio_ids=portfolio_ids
        )
        portfolio_performance = getPortfolioPerformance(
            tenantID=tenantID,
            last_quarter_start=last_quarter_start,
            last_quarter_end=last_quarter_end,
            eligible_project_ids=eligibleProjects,
            portfolio_ids=portfolio_ids
        )
        
        response = {
            "executive_summary": executive_summary,
            "performance_of_ongoing_projects": ongoing_projects_performance,
            "portfolio_overview": portfolio_overview,
            "learnings_from_closed_projects": learnings,
            "new_roadmaps": new_roadmaps,
            "completed_projects": completed_projects,
            "business_value": business_value,
            "portfolio_performance": portfolio_performance
        }

        return response
    except Exception as e:
        print(f"Error generating performance snapshot: {str(e)}")
        return f"Error: Failed to generate performance snapshot due to {str(e)}"

RETURN_DESCRIPTION = """
    This function returns a comprehensive Project Performance Report for Q2 2025, covering:
    *** Executive Summary: Key highlights, strategic impact, and recommendations
    *** Project Portfolio Overview: Snapshot of ongoing/closed projects, budgets, and strategic pillars
    *** Performance of Ongoing Projects: Health dashboard, KPIs, expected business value, achievements, challenges
    *** Analysis of Closed Projects: Summary, actual business value, lessons learned
    *** Overall Portfolio Performance: Aggregated CPI/SPI trends, comparison to targets
    Data is provided in a JSON format for executive analysis, filtered by portfolio IDs.
"""

ARGUMENTS = [
    {
        "name": "last_quarter_start",
        "type": "str",
        "description": "Start date of the quarter in YYYY-MM-DD format.",
        "conditional": "required",
    },
    {
        "name": "last_quarter_end",
        "type": "str",
        "description": "End date of the quarter in YYYY-MM-DD format.",
        "conditional": "required",
    },
]

VIEW_PERFORMANCE_SNAPSHOT_LAST_QUARTER = TangoFunction(
    name="view_performance_snapshot_last_quarter",
    description="""
    A function that returns a comprehensive performance snapshot for Q2 2025.
    Triggered for performance reviews or retrospectives, using archived_on to identify closed projects.
    Provides data for LLM analysis in a JSON format for executive leadership.
    Filters results by optional portfolio IDs.
    """,
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=view_performance_snapshot_last_quarter,
    func_type="sql",
    integration="trmeric"
)