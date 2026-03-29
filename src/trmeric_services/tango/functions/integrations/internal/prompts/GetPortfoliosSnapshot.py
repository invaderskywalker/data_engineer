
from src.trmeric_services.tango.functions.Types import TangoFunction
from src.trmeric_services.tango.functions.integrations.internal.helpers.SQLHandler import (
    SQL_Handler
)
from src.trmeric_database.Database import db_instance
from src.trmeric_database.dao.portfolios import PortfolioDao


def getPortfolioAndProjectsList(tenantID, eligibleProjects):
    query = f"""
    select pp.id, pp.title as portfolio_title,  wp.id as project_id
    from workflow_project as wp
    left join workflow_projectkpi as wpkpi on wpkpi.project_id = wp.id
    left JOIN projects_portfolio pp ON wp.portfolio_id_id = pp.id
    where {eligibleProjects} AND pp.tenant_id_id = {tenantID};
    """
    return db_instance.retrieveSQLQueryOld(query)


def getKeyResultsOfPortfolios(tenantID, eligibleProjects):
    query = f"""
    select pp.id, pp.title as portfolio_title,  ARRAY_AGG(wpkpi.name) AS key_results from workflow_project as wp
    left join workflow_projectkpi as wpkpi on wpkpi.project_id = wp.id
    left JOIN projects_portfolio pp ON wp.portfolio_id_id = pp.id
    where {eligibleProjects} AND pp.tenant_id_id = {tenantID} 
    GROUP BY pp.id, pp.title;
    """
    return db_instance.retrieveSQLQueryOld(query)


def topProjectsByBudgetAndTheirHealth(tenantID, eligibleProjects, portfolioID):

    query = f"""
    
            select 
                wp.title as "Project Title",  
                TO_CHAR(wp.total_external_spend, '$999,999,999') AS Budget,
                
                CASE 
                    WHEN wp.scope_status = 'at_risk' THEN '<scope_status_HASH_1>'
                    WHEN wp.scope_status = 'compromised' THEN '<scope_status_HASH_2>'
                    WHEN wp.scope_status = 'on_track' THEN '<scope_status_HASH_3>'
                    ELSE '<scope_HASH_4>'
                END AS "Scope Status",
                
                CASE 
                    WHEN wp.delivery_status = 'at_risk' THEN '<delivery_status_HASH_1>'
                    WHEN wp.delivery_status = 'compromised' THEN '<delivery_status_HASH_2>'
                    WHEN wp.delivery_status = 'on_track' THEN '<delivery_status_HASH_3>'
                    ELSE '<delivery_status_HASH_4>'
                END AS "Delivery Status",
                
                CASE 
                    WHEN wp.spend_status = 'at_risk' THEN '<spend_status_HASH_1>'
                    WHEN wp.spend_status = 'compromised' THEN '<spend_status_HASH_2>'
                    WHEN wp.spend_status = 'on_track' THEN '<spend_status_HASH_3>'
                    ELSE '<spend_status_HASH_4>'
                END AS "Spend Status",
    
                
                ARRAY_AGG(distinct wpkpi.name) AS "Key Results"
            from workflow_project as wp 
            join workflow_projectkpi as wpkpi on wpkpi.project_id = wp.id
            JOIN projects_portfolio pp ON wp.portfolio_id_id = pp.id
            where wp.tenant_id_id = {tenantID} and pp.id = {portfolioID} and {eligibleProjects} 
            GROUP BY wp.id, pp.title, wp.title
            order by wp.total_external_spend desc
            limit 5
    """

    query = f"""
    
            select 
                wp.title as "Project Title",  
                TO_CHAR(wp.total_external_spend, '$999,999,999') AS Budget,
                CASE 
                    WHEN wp.scope_status = 'at_risk' THEN 'At Risk'
                    WHEN wp.scope_status = 'compromised' THEN 'Compromised'
                    WHEN wp.scope_status = 'on_track' THEN 'On Track'
                    ELSE wp.scope_status
                END AS "Scope Status",
                
                CASE 
                    WHEN wp.delivery_status = 'at_risk' THEN 'At Risk'
                    WHEN wp.delivery_status = 'compromised' THEN 'Delayed'
                    WHEN wp.delivery_status = 'on_track' THEN 'On Track'
                    ELSE wp.delivery_status
                END AS "Schedule Status",
                
                CASE 
                    WHEN wp.spend_status = 'at_risk' THEN 'At Risk'
                    WHEN wp.spend_status = 'compromised' THEN 'Compromised'
                    WHEN wp.spend_status = 'on_track' THEN 'On Track'
                    ELSE wp.spend_status
                END AS "Spend Status",
                ARRAY_AGG(distinct wpkpi.name) AS "Key Results"
            from workflow_project as wp 
            join workflow_projectkpi as wpkpi on wpkpi.project_id = wp.id
            JOIN projects_portfolio pp ON wp.portfolio_id_id = pp.id
            where wp.tenant_id_id = {tenantID} and pp.id = {portfolioID} and {eligibleProjects} 
            GROUP BY wp.id, pp.title, wp.title
            order by wp.total_external_spend desc
            limit 5
    """
    return db_instance.retrieveSQLQuery(query).formatData()


def getProjectsPlannedVsActualSpend(tenantID, eligibleProjects):
    query = f"""

        SELECT 
            wp.title AS "Project Name",
            SUM(wpm.actual_spend) AS "Total Actual Spend",
            SUM(wpm.planned_spend) AS "Total Planned Spend",
            (-SUM(wpm.actual_spend) + SUM(wpm.planned_spend)) AS "Spend Vs Plan"
        FROM 
            workflow_project AS wp
        JOIN 
            workflow_projectmilestone AS wpm ON wp.id = wpm.project_id
        WHERE 
            wp.tenant_id_id = {tenantID}
            and {eligibleProjects}
        GROUP BY 
            wp.id, wp.title
        ORDER BY 
            (-SUM(wpm.actual_spend) + SUM(wpm.planned_spend)) DESC
        LIMIT 5;

    """
    return db_instance.retrieveSQLQuery(query).formatData()


def SummaryOfRemainingProjectSpend(tenantID, eligibleProjects):
    query = f"""
        SELECT 
        COUNT(DISTINCT wp.id) AS "Number of Projects",
        SUM(wpm.actual_spend) AS "Total Actual Spend",
        SUM(wpm.planned_spend) AS "Total Planned Spend",
        (-SUM(wpm.actual_spend) + SUM(wpm.planned_spend)) AS  "Total Spend Vs Plan"
    FROM 
        workflow_project AS wp
    JOIN 
        workflow_projectmilestone AS wpm ON wp.id = wpm.project_id
    WHERE 
        wp.tenant_id_id = {tenantID}
        and {eligibleProjects}
        AND wp.id NOT IN (
            SELECT wp.id
            FROM workflow_project AS wp
            JOIN workflow_projectmilestone AS wpm ON wp.id = wpm.project_id
            WHERE 
                wp.tenant_id_id = {tenantID}
                and {eligibleProjects}
            GROUP BY wp.id
            ORDER BY (SUM(wpm.actual_spend) - SUM(wpm.planned_spend)) DESC
            LIMIT 5
        );
    """
    return db_instance.retrieveSQLQueryOld(query)


def getFutureRoadmaps(tenantID, condition):
    query = f"""
        SELECT 
            rr.title AS "Roadmap Title", 
            TO_CHAR(rr.budget, '$999,999,999') AS Budget,
            
            ARRAY_AGG(DISTINCT pp.title) AS "Roadmap Portfolios",
            ARRAY_AGG(DISTINCT rrkpi.name) AS "Roadmap Key Results"
        FROM 
            roadmap_roadmap AS rr
        LEFT JOIN 
            roadmap_roadmapkpi AS rrkpi ON rrkpi.roadmap_id = rr.id
        LEFT JOIN 
            roadmap_roadmapportfolio AS rrp ON rrp.roadmap_id = rr.id
        LEFT JOIN 
            projects_portfolio AS pp ON pp.id = rrp.portfolio_id
        WHERE 
            rr.tenant_id = {tenantID}
            {condition}
        GROUP BY 
            rr.title, rr.budget;
    """
    return db_instance.retrieveSQLQuery(query).formatData()


def view_portfolio_snapshot(
    eligibleProjects: list[int],
    tenantID: int,
    userID: int,
    portfolio_id=None,
    **kwargs
):
    print("in view_portfolio_snapshot ", eligibleProjects,
          portfolio_id, tenantID, userID)

    portfolio_ids = []
    if (portfolio_id):
        for val in portfolio_id:
            portfolio_ids.append(int(val))

    print("portfolio ids in query --- ", portfolio_ids)

    if len(eligibleProjects) == 1:
        project_condition = f"wp.id = {eligibleProjects[0]}"
    else:
        project_condition = f"wp.id in {tuple(eligibleProjects)}"

    if (len(portfolio_ids) > 0):
        eligibleProjects = []
        checkPortfoliosId = getPortfolioAndProjectsList(
            tenantID=tenantID, eligibleProjects=project_condition)
        for item in checkPortfoliosId:
            if item["id"] in portfolio_ids:
                eligibleProjects.append(item["project_id"])

    print("updated eligible projects --- ", eligibleProjects)

    if len(eligibleProjects) == 1:
        project_condition = f"wp.id = {eligibleProjects[0]}"
    else:
        project_condition = f"wp.id in {tuple(eligibleProjects)}"

    print("eligible projects condition --- ", project_condition)

    keyResultsByPortfolioCut = getKeyResultsOfPortfolios(
        tenantID=tenantID, eligibleProjects=project_condition)
    response = f"""
    Response Structure format:
    
    *** Header1 - What is the portfolio moving the needle on 
        - Key business results being delivered by the portfolio
            Up-to 5-6 key results per portfolio in bullets

    Data For top Key Results per portfolio: 
    {keyResultsByPortfolioCut}
    
    -------------------
    
    Now, 
    *** Header2 - What are the top projects per portfolio & how are they doing in tabular format?
        Top 3 - 5 projects in each portfolio and their health in tabular form
        Output this in Tabular view
        
        --

    """
    # print("key results by portfolio cut ", keyResultsByPortfolioCut)
    for portfolio in keyResultsByPortfolioCut:
        if ((len(portfolio_ids) > 0)):
            if ((portfolio["id"] in portfolio_ids)):
                projectsInPortfolio = topProjectsByBudgetAndTheirHealth(
                    tenantID=tenantID, eligibleProjects=project_condition, portfolioID=portfolio["id"])
                response += f"""
                    For Portfolio: {portfolio["portfolio_title"]}
                    
                    Top 5 projects by budget:
                    Respond with actual status update with hashed values
                    {projectsInPortfolio}
                    -- 
                """
        elif (len(portfolio_ids) == 0):
            projectsInPortfolio = topProjectsByBudgetAndTheirHealth(
                tenantID=tenantID, eligibleProjects=project_condition, portfolioID=portfolio["id"])
            response += f"""
                For Portfolio: {portfolio["portfolio_title"]}
                
                Top 5 projects by budget:
                Respond with actual status update with hashed values
                {projectsInPortfolio}
                
                --
                
            """

    topProjectsPlannedVsActual = getProjectsPlannedVsActualSpend(
        tenantID=tenantID, eligibleProjects=project_condition)
    restProjectsSpendSummary = SummaryOfRemainingProjectSpend(
        tenantID=tenantID, eligibleProjects=project_condition)

    response += f"""
    ------------------------------
    
    
    *** Header3- How are we doing on spend vs plan?
        Tabular view
        
        Cover the top 5 projects by name
        And the rest - give a number of projects and total spend vs plan
        
        
        <combine_these_two_table> // combine these table into one
        
        Top 5 projects by name with spend vs plan:
        {topProjectsPlannedVsActual}
        
        summary of the remaining projects:
        {restProjectsSpendSummary}
        
        <combine_these_two_table>
        
        
        
        
        
    ---------------------------

    """

    condition = ""
    if (len(portfolio_ids) > 0):
        if len(portfolio_ids) == 1:
            condition = f"and pp.id = {portfolio_ids[0]}"
        else:
            condition = f"and pp.id in {tuple(portfolio_ids)}"
    futureRoadmaps = getFutureRoadmaps(tenantID=tenantID, condition=condition)
    response += f"""
    ***Header4 - What is the plan for the future?
        The grid of top planned initiatives, the key results expected from each and the budgeted spend (this should be tabular)
        
        {futureRoadmaps}
    ------------------------
    """

    # print("final data create for snapshot ", response)

    return response


RETURN_DESCRIPTION = """
    This function returns data to provide a good portfolio snapshot, descriptive answer for these sections:
    *** What is the portfolio moving the needle on?
    *** What are the top projects in each portfolio & how are they doing?
    *** How are we doing on spend vs plan?
    *** What is the plan for the future?
"""

ARGUMENTS = [
    {
        "name": "portfolio_id",
        "type": "int[]",
        "description": "The specific portfolio id(s) that the user is interested in.",
        "conditional": "in",
    },
]


VIEW_PORTFOLIOS_SNAPSHOT = TangoFunction(
    name="view_portfolio_snapshot",
    description="""
    Important for portfolio snapshot: A function that returns a descriptive snapshot of portfolios for this user. 
    When the question asked is related to snapshot of portfolios then this should be triggered.
    """,
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=view_portfolio_snapshot,
    func_type="sql",
    integration="trmeric"
)
