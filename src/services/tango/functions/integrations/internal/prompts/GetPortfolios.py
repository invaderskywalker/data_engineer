
from src.trmeric_services.tango.functions.integrations.internal.helpers.SQLHandler import (
    SQL_Handler
)
from src.trmeric_database.Database import db_instance
from src.trmeric_database.dao import PortfolioDao



def getRoadmapVsPortfolioQuery(tenant_id):
    query = f"""
        SELECT 
            COALESCE(pp.id, 0) AS portfolio_id, 
            COALESCE(pp.title, 'No Portfolio') AS portfolio_title,
            rr.id AS roadmap_id,
            rr.title AS roadmap_title,
            rr.start_date,
            rr.end_date
        FROM 
            roadmap_roadmap rr
        LEFT JOIN 
            roadmap_roadmapportfolio rrp ON rr.id = rrp.roadmap_id
        JOIN 
            projects_portfolio pp ON pp.id = rrp.portfolio_id
        WHERE 
            (pp.tenant_id_id = {tenant_id} OR pp.id IS NULL);
        """
    return query
  
def getProjectsVsPortfolioQuery(tenantID):
    query = f"""
        SELECT 
        COALESCE(pp.id, 0) AS portfolio_id,
        COALESCE(pp.title, 'No Portfolio') AS portfolio_title,
        wp.id AS project_id,
        wp.title AS project_name,
        wp.start_date,
        wp.end_date
    FROM 
        workflow_project wp
    JOIN 
        projects_portfolio pp ON wp.portfolio_id_id = pp.id
    WHERE 
        (pp.tenant_id_id = {tenantID} OR pp.id IS NULL)
        AND wp.archived_on IS NULL
        AND wp.parent_id is not NULL;
    """
    return query


def getCombinedPortfoliosQuery(tenant_id):
    query = f"""
        SELECT 
            COALESCE(pp.id, 0) AS portfolio_id, 
            COALESCE(pp.title, 'No Portfolio') AS portfolio_title
        FROM 
            roadmap_roadmap rr
        LEFT JOIN 
            roadmap_roadmapportfolio rrp ON rr.id = rrp.roadmap_id
        JOIN 
            projects_portfolio pp ON pp.id = rrp.portfolio_id
        WHERE 
            (pp.tenant_id_id = {tenant_id} OR pp.id IS NULL)

        UNION

        SELECT 
            COALESCE(pp.id, 0) AS portfolio_id,
            COALESCE(pp.title, 'No Portfolio') AS portfolio_title
        FROM 
            workflow_project wp
        JOIN 
            projects_portfolio pp ON wp.portfolio_id_id = pp.id
        WHERE 
            (pp.tenant_id_id = {tenant_id} OR pp.id IS NULL)
            AND wp.archived_on IS NULL
            AND wp.parent_id is not NULL;
    """
    return query


def view_portfolios(tenantID: int, userID: int,  **kwargs):
    return PortfolioDao.fetchApplicablePortfolios(user_id=userID, tenant_id=tenantID)
    # roadmap_portfolios_query = getRoadmapVsPortfolioQuery(tenantID)
    # projects_portfolio_query = getProjectsVsPortfolioQuery(tenantID)
    # response1 = db_instance.retrieveSQLQuery(roadmap_portfolios_query).formatData()
    # response2 = db_instance.retrieveSQLQuery(projects_portfolio_query).formatData()
    # response3 = db_instance.retrieveSQLQuery(getCombinedPortfoliosQuery(tenantID)).formatData()
    # return "Roadmap vs portfolio: "+ response1 + "\n\n" + "Projects vs Portfolios: "+ response2 + "\n\n" + "All unique portfolios: " + response3


RETURN_DESCRIPTION = """
    Returns two tables:
    1. with roadmap and corresponding portfolio
    2. with project and corresponding portfolio
"""

ARGUMENTS = []