from src.trmeric_services.agents.core.agent_functions import AgentFunction
from .portfolio_analyst import portfolio_analyst
from src.trmeric_database.dao import PortfolioDao



def portfolio_insights(
    tenantID: int,
    userID: int,
    eligibleProjects: list[int],
    portfolio_ids=[],
    budget=False,
    detailed_or_summary_analysis="",
    **kwargs
):
    """
    This function generates high-level insights for the portfolio. 
    It checks for issues like underperforming projects, risks, and overall health.
    """
    
    data = ''
    
    ## also need the portfolio id. vs portfolio name which is currently in discussion
    ## also fetch important key results of portfolios
    ##
    data += f"""
        List the portfolios name first:
        {str(PortfolioDao.fetchPortfolioIdAndTitle(tenantID=tenantID, eligibleProjects=eligibleProjects))}
    """
    if not budget:
        data += f"""
            List important key results by portfolio:
            {str(PortfolioDao.getKeyResultsOfPortfolios(tenantID=tenantID, eligibleProjects=eligibleProjects))}
        """
    data += "Data for spend_analysis_by_portfolio "+ str(portfolio_analyst(tenantID=tenantID, userID=userID, dimension="spend_analysis_by_portfolio", eligibleProjects=eligibleProjects, portfolio_ids=portfolio_ids))
    # data += "Data for spend_analysis_by_category_of_projects---" + str(portfolio_analyst(tenantID=tenantID, userID=userID, dimension="spend_analysis_by_category_of_projects", eligibleProjects=eligibleProjects, portfolio_ids=portfolio_ids))
    data += "Data for spend_analysis_vs_actual_of_projects ---"+str(portfolio_analyst(tenantID=tenantID, userID=userID, dimension="spend_analysis_vs_actual_of_projects", eligibleProjects=eligibleProjects, portfolio_ids=portfolio_ids))
    
    if detailed_or_summary_analysis == "detailed":
        data += """
            Look at all the data and create response in the best possible way as per the user request.
        """
    else:
        data += """
            Important ---- 
            Look at all of the question 
            and look into these portfolio related data 
            and create a perfect response  
            List: Top 2 most important key result by portfiolio.
            If budget is needed in answer use table  to represent
            If key results is needed in answer then use bullets and list major key results driving.
            
            And also expand a lot on recomendations from knowledge layer and create more recomendation as per your understanding of data
        """
    
    
    # data += str(portfolio_analyst(tenantID=tenantID, userID=userID, dimension="health_analysis", eligibleProjects=eligibleProjects, portfolio_ids=portfolio_ids))
    
    return data
    

RETURN_DESCRIPTION = """
    High-level insights about the portfolio's  on
    - spend_analysis_by_category_of_projects
    - spend_analysis_vs_actual_of_projects
    - spend_analysis_by_portfolio
"""

ARGUMENTS = [
    {
        "name": "portfolio_ids",
        "type": "int[]",
        "description": "The portfolio_id(s) that the user wants to get insight on."
    },
    {
        "name": "budget",
        "type": "boolean",
        "description": "If question is targeted on portfolio budget."
    },
    {
        "name": "detailed_or_summary_analysis",
        "type": "str",
        "options": ["detailed", "summary"],
        "description": ""
    },
]

PORTFOLIO_INSIGHTS = AgentFunction(
    name="portfolio_insights",
    description="""
    This function extracts, high-level insights about the portfolio, 
    focusing on identifying key areas requiring attention such as underperforming projects, 
    risks, and overall portfolio health.
    """,
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=portfolio_insights,
)
