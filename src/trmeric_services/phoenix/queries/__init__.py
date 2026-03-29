
from src.trmeric_database.Database import db_instance
from src.trmeric_services.tango.functions.integrations.internal.GetIntegrationData import get_jira_data, get_github_data


def fetchProjectInfo(project_ids, portfolio_id=None, start_date=None, end_date=None, **kwargs):
    if not project_ids:
        return []
    
    project_ids_str = f"({', '.join(map(str, project_ids))})"
    date_filter = ""
    if start_date:
        date_filter += f"AND wp.created_on >= '{start_date}' "
    if end_date:
        date_filter += f"AND wp.created_on <= '{end_date}' "
    
    portfolio_filter = ""
    if portfolio_id:
        portfolio_filter = f"AND wpp.portfolio_id = {portfolio_id}"
    
    query = f"""
        SELECT 
            wp.id AS project_id,
            wp.title AS project_title,
            wp.start_date,
            wp.end_date,
            wp.project_type,
            wp.spend_status,
            wp.scope_status,
            wp.delivery_status,
            wp.project_category,
            wp.project_location,
            wp.sdlc_method,
            wp.state AS project_state,
            wp.objectives,
            wp.org_strategy_align,
            wp.created_on,
            wp.updated_on,
            COALESCE(
                STRING_AGG(DISTINCT pp.id::TEXT, ', '), '0'
            ) AS portfolio_ids,
            COALESCE(
                STRING_AGG(DISTINCT pp.title, ', '), 'No Portfolio'
            ) AS portfolio_titles
        FROM 
            workflow_project wp
        LEFT JOIN 
            workflow_projectportfolio wpp ON wp.id = wpp.project_id
        LEFT JOIN 
            projects_portfolio pp ON wpp.portfolio_id = pp.id
        WHERE 
            wp.id IN {project_ids_str}
            {date_filter}
            {portfolio_filter}
        GROUP BY 
            wp.id, wp.title, wp.start_date, wp.end_date, wp.project_type, 
            wp.spend_status, wp.scope_status, wp.delivery_status, wp.project_category, 
            wp.project_location, wp.sdlc_method, wp.state, wp.objectives, 
            wp.org_strategy_align, wp.created_on, wp.updated_on
        ORDER BY 
            wp.created_on DESC;
    """
    return db_instance.retrieveSQLQueryOld(query)


def fetchStatusInfo(project_ids, start_date=None, end_date=None, **kwargs):
    if not project_ids:
        return []
    
    project_ids_str = f"({', '.join(map(str, project_ids))})"
    date_filter = ""
    if start_date and end_date:
        if start_date == end_date:
            date_filter = f"AND wps.created_date >= '{start_date}'"
        else:
            date_filter = f"AND wps.created_date BETWEEN '{start_date}' AND '{end_date}'"

    query = f"""
        SELECT 
            wps.project_id,
            wp.title as project_title,
            CASE 
                WHEN wps.type = 1 THEN 'Scope'
                WHEN wps.type = 2 THEN 'Schedule'
                WHEN wps.type = 3 THEN 'Spend'
                ELSE 'Unknown Type'
            END AS status_type,
            CASE 
                WHEN wps.value = 1 THEN 'On Track'
                WHEN wps.value = 2 THEN 'At Risk'
                WHEN wps.value = 3 THEN 'Compromised'
                ELSE 'Unknown Value'
            END AS status_value,
            wps.comments AS status_comments,
            wps.actual_percentage,
            wps.created_date
        FROM 
            workflow_projectstatus wps
        LEFT JOIN workflow_project as wp on wps.project_id = wp.id
        WHERE 
            wps.project_id IN {project_ids_str}
            {date_filter}
        ORDER BY 
            wps.created_date DESC;
    """
    try:
        return db_instance.retrieveSQLQueryOld(query)
    except Exception as e:
        return []
        


def fetchMilestoneInfo(project_ids, start_date=None, end_date=None, **kwargs):
    if not project_ids:
        return []
    
    project_ids_str = f"({', '.join(map(str, project_ids))})"
    date_filter = ""
    if start_date and end_date:
        date_filter = f"AND wpm.target_date BETWEEN '{start_date}' AND '{end_date}'"
    
    query = f"""
        SELECT 
            wpm.project_id,
            wp.title as project_title,
            wpm.name AS milestone_name,
            wpm.target_date,
            wpm.planned_spend,
            wpm.actual_spend,
            wpm.actual_date,
            wpm.status_value,
            wpm.comments
        FROM 
            workflow_projectmilestone wpm
        LEFT JOIN workflow_project as wp on wpm.project_id = wp.id
        WHERE 
            wpm.project_id IN {project_ids_str}
            {date_filter}
        ORDER BY 
            wpm.target_date ASC;
    """
    return db_instance.retrieveSQLQueryOld(query)


def fetchRiskInfo(project_ids, start_date=None, end_date=None, **kwargs):
    if not project_ids:
        return []
    
    project_ids_str = f"({', '.join(map(str, project_ids))})"
    date_filter = ""
    
    if start_date:
        date_filter += f"AND wpr.due_date >= '{start_date}' "
    
    if end_date:
        date_filter += f"AND wpr.due_date <= '{end_date}' "
    
    query = f"""
        SELECT 
            wpr.project_id,
            wp.title AS project_title,
            ARRAY_AGG(wpr.description) AS risk_descriptions,
            ARRAY_AGG(wpr.impact) AS impacts,
            ARRAY_AGG(wpr.mitigation) AS mitigations,
            ARRAY_AGG(wpr.priority) AS priorities,
            ARRAY_AGG(
                CASE 
                    WHEN wpr.priority = 1 THEN 'High'
                    WHEN wpr.priority = 2 THEN 'Medium'
                    WHEN wpr.priority = 3 THEN 'Low'
                    ELSE ''
                END
            ) AS priority_meanings,
            ARRAY_AGG(wpr.due_date) AS due_dates
        FROM 
            workflow_projectrisk wpr
        LEFT JOIN workflow_project wp ON wp.id = wpr.project_id
        WHERE 
            wpr.project_id IN {project_ids_str}
        GROUP BY 
            wpr.project_id, wp.title
        ORDER BY 
            wpr.project_id, MAX(wpr.priority) DESC, MIN(wpr.due_date) ASC;
    """
    return db_instance.retrieveSQLQueryOld(query)

def fetchTeamInfo(project_ids, start_date=None, end_date=None, **kwargs):
    if not project_ids:
        return []
    
    project_ids_str = f"({', '.join(map(str, project_ids))})"
    date_filter = ""
    query = f"""
        SELECT 
            wpts.project_id,
            wp.title AS project_title,
            wpts.member_role,
            wpts.member_name,
            wpts.location,
            wpts.member_utilization,
            CASE 
                WHEN wpts.is_external = false THEN 'Internal Team' 
                ELSE 'External Team' 
            END AS team_type,
            wpts.average_spend AS average_rate_per_hour
        FROM 
            workflow_projectteamsplit wpts
        LEFT JOIN workflow_project wp ON wp.id = wpts.project_id
        WHERE 
            wpts.project_id IN {project_ids_str}
            {date_filter}
        ORDER BY 
            wpts.member_name ASC;
    """
    return db_instance.retrieveSQLQueryOld(query)


def getIntegrationData(integration_name, summary_view_required, summary_of_which_integration_summary_keys, project_ids, user_query= "", **kwargs ):
    tenantID = kwargs.get("tenantID")
    userID = kwargs.get("userID")
    if integration_name == "jira":
        return get_jira_data(tenantID, userID, summary_analysis_of_which_jira_projects=summary_of_which_integration_summary_keys, project_id=project_ids, user_query=user_query)
    if integration_name == "github":
        return get_github_data(tenantID, userID, project_id=project_ids, user_query=user_query)
    
    







class PlanningKnowledgeQueries:
    @staticmethod
    def fetchOngoingProjectKeyResults(tenantID=None):
        query= f"""
            SELECT 
                wp.id AS project_id,
                wp.title AS project_title,
                wp.start_date,
                wp.end_date,
                wp.project_type,
                wp.project_category,
                wp.project_location,
                wp.sdlc_method,
                wp.objectives,
                wp.org_strategy_align,
                wp.created_on,
                COALESCE(pp.id, 0) AS portfolio_id,
                COALESCE(pp.title, 'No Portfolio') AS portfolio_title
            FROM 
                workflow_project wp
            LEFT JOIN 
                workflow_projectportfolio wpp ON wp.id = wpp.project_id
            LEFT JOIN 
                projects_portfolio pp ON wpp.portfolio_id = pp.id
            WHERE 
                wp.tenant_id_id = {tenantID}
            ORDER BY 
                wp.created_on DESC;
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def fetchFutureRoadmapsKeyResults(tenantID=None):
        query= f"""
        
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    
    @staticmethod
    def fetchAllOrgStrategiesForThisOrganization(tenantID=None):
        query= f"""
        
        """
        return db_instance.retrieveSQLQueryOld(query)





class RoadmapQueries:
    # Fetch basic roadmap details
    @staticmethod
    def fetchRoadmapInfo(roadmap_ids, portfolio_id=None, start_date=None, end_date=None, tenantID=None, **kwargs):
        # if not roadmap_ids:
        #     return []
        
        roadmap_ids_str = f"({', '.join(map(str, roadmap_ids))})"
        date_filter = ""
        if start_date:
            date_filter += f"AND rr.start_date >= '{start_date}' "
        if end_date:
            date_filter += f"AND rr.end_date <= '{end_date}' "
        
        portfolio_filter = ""
        if portfolio_id:
            portfolio_filter = f"AND rrp.portfolio_id = {portfolio_id}"
        
        query = f"""
            SELECT 
                rr.id AS roadmap_id,
                rr.title AS roadmap_title,
                rr.description,
                rr.objectives,
                CASE 
                    WHEN rr.type = 1 THEN 'Program'
                    WHEN rr.type = 2 THEN 'Project'
                    WHEN rr.type = 3 THEN 'Enhancement'
                    ELSE 'Unknown'
                END AS roadmap_type,
                CASE 
                    WHEN rr.priority = 1 THEN 'High'
                    WHEN rr.priority = 2 THEN 'Medium'
                    WHEN rr.priority = 3 THEN 'Low'
                    ELSE 'Unspecified'
                END AS priority,
                rr.start_date,
                rr.end_date,
                rr.budget,
                rr.min_time_value,
                CASE 
                    WHEN rr.min_time_value_type = 1 THEN 'Days'
                    WHEN rr.min_time_value_type = 2 THEN 'Weeks'
                    WHEN rr.min_time_value_type = 3 THEN 'Months'
                    ELSE 'Unspecified'
                END AS min_time_value_type,
                rr.created_on,
                -- rr.updated_on,
                -- rr.approved_state,
                rr.category,
                rr.org_strategy_align,
                rr.duration,
                COALESCE(pp.id, 0) AS portfolio_id,
                COALESCE(pp.title, 'No Portfolio') AS portfolio_title
            FROM 
                roadmap_roadmap rr
            LEFT JOIN 
                roadmap_roadmapportfolio rrp ON rr.id = rrp.roadmap_id
            LEFT JOIN 
                projects_portfolio pp ON rrp.portfolio_id = pp.id
            WHERE 
                rr.tenant_id = {tenantID}
                -- rr.id IN {roadmap_ids_str}
                -- {date_filter}
                {portfolio_filter}
            ORDER BY 
                rr.created_on DESC;
        """
        return db_instance.retrieveSQLQueryOld(query)

    # Fetch roadmap constraints
    @staticmethod
    def fetchRoadmapConstraints(roadmap_ids, tenantID=None, **kwargs):
        if not roadmap_ids:
            return []
        
        roadmap_ids_str = f"({', '.join(map(str, roadmap_ids))})"
        date_filter = ""

        query = f"""
            SELECT 
                rrc.id AS constraint_id,
                rrc.roadmap_id,
                rr.title AS roadmap_title,
                rrc.name AS constraint_name,
                CASE 
                    WHEN rrc.type = 1 THEN 'Resource'
                    WHEN rrc.type = 2 THEN 'Time'
                    WHEN rrc.type = 3 THEN 'Budget'
                    ELSE 'Other'
                END AS constraint_type
            FROM 
                roadmap_roadmapconstraints rrc
            LEFT JOIN 
                roadmap_roadmap rr ON rrc.roadmap_id = rr.id
            WHERE 
                rrc.roadmap_id IN {roadmap_ids_str}
            ORDER BY 
                rrc.id ASC;
        """
        return db_instance.retrieveSQLQueryOld(query)

    # Fetch roadmap KPIs (Key Results)
    @staticmethod
    def fetchRoadmapKeyResults(roadmap_ids, tenantID=None, userID=None, **kwargs):
        if not roadmap_ids:
            return []
        
        roadmap_ids_str = f"({', '.join(map(str, roadmap_ids))})"
        date_filter = ""
        # if start_date or end_date:
        #     date_filter = "AND rr.start_date " + (f">= '{start_date}' " if start_date else "") + (f"<= '{end_date}' " if end_date else "")
        
        query = f"""
            SELECT 
                -- rrk.id AS kpi_id,
                -- rrk.roadmap_id,
                rr.title AS roadmap_title,
                rrk.name AS kpi_name,
                rrk.baseline_value
                -- rrk.user_id AS assigned_user_id
            FROM 
                roadmap_roadmapkpi rrk
            LEFT JOIN 
                roadmap_roadmap rr ON rrk.roadmap_id = rr.id
            WHERE 
                rrk.roadmap_id IN {roadmap_ids_str}
            ORDER BY 
                rrk.id ASC;
        """
        return db_instance.retrieveSQLQueryOld(query)

    # Fetch roadmap org strategy alignments
    @staticmethod
    def fetchRoadmapOrgStrategyAlign(roadmap_ids, tenantID=None, **kwargs):
        # if not roadmap_ids:
        #     return []
        
        roadmap_ids_str = f"({', '.join(map(str, roadmap_ids))})"
        tenant_filter = ""
        if tenantID:
            tenant_filter = f" rosa.tenant_id = {tenantID}"
        
        query = f"""
            SELECT 
                rr.title AS roadmap_title,
                rosa.title AS strategy_title
            FROM 
                roadmap_roadmap rr
            LEFT JOIN 
                roadmap_roadmaporgstratergyalign rosa ON rr.tenant_id = rosa.tenant_id
            WHERE 
                {tenant_filter}
            ORDER BY 
                rosa.id ASC;
        """
        return db_instance.retrieveSQLQueryOld(query)

    # Fetch roadmap portfolio links
    @staticmethod
    def fetchRoadmapPortfolioInfo(roadmap_ids, portfolio_id=None, tenantID=None, **kwargs):
        if not roadmap_ids:
            return []
        
        roadmap_ids_str = f"({', '.join(map(str, roadmap_ids))})"
        portfolio_filter = ""
        if portfolio_id:
            portfolio_filter = f"AND rrp.portfolio_id = {portfolio_id}"
        
        query = f"""
            SELECT 
                -- rrp.id AS link_id,
                rrp.roadmap_id,
                rr.title AS roadmap_title,
                -- rrp.portfolio_id,
                pp.title AS portfolio_title
            FROM 
                roadmap_roadmapportfolio rrp
            LEFT JOIN 
                roadmap_roadmap rr ON rrp.roadmap_id = rr.id
            LEFT JOIN 
                projects_portfolio pp ON rrp.portfolio_id = pp.id
            WHERE 
                rrp.roadmap_id IN {roadmap_ids_str}
                {portfolio_filter}
            ORDER BY 
                rrp.id ASC;
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    
   
   
class KnowledgeQueries:
    @staticmethod
    def fetchPortfolioKnowledge(portfolio_ids=[], **kwargs):
        print("fetchPortfolioKnowledge -- debug --- ", portfolio_ids)
        if (portfolio_ids == None or len(portfolio_ids) == 0):
            return []
        portfolio_ids_str = f"({', '.join(map(str, portfolio_ids))})"
        query = f"""
            SELECT portfolio_id, knowledge
                FROM tango_portfolioknowledge
                where portfolio_id in {portfolio_ids_str};
        """
        return db_instance.retrieveSQLQueryOld(query)
