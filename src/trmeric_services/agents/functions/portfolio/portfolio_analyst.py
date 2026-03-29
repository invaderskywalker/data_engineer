from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_services.agents.apis.portfolio_api.PortfolioApiService import PortfolioApiService
from src.trmeric_database.dao import PortfolioDao, ProjectsDao

def portfolio_analyst(
    tenantID: int,
    userID: int,
    eligibleProjects: list[int],
    dimension='',
    portfolio_ids=[],
    **kwargs
):
    """
    This function performs detailed analysis on a specific project or group of projects. 
    It takes the project data and looks into metrics such as budget, timeline, resource allocation, etc.
    """
    _portfolio_ids = portfolio_ids
    if _portfolio_ids is None or (isinstance(_portfolio_ids, list) and len(_portfolio_ids) == 0):
        _data = PortfolioDao.fetchPortfolioDetailsForApplicableProjectsForUser(tenant_id=tenantID, projects_list=eligibleProjects)
        _portfolio_ids = []
        for _d in _data:
            if _d["id"] not in _portfolio_ids:
                _portfolio_ids.append(_d["id"])
                
    print("--portfolio_analyst --",_portfolio_ids )
                
    data_obtained = ''
    portfolio_api_service = PortfolioApiService()
    applicable_projects = ProjectsDao.FetchAvailableProject(tenant_id=tenantID, user_id=userID)
    
    if dimension == "spend_analysis_by_category_of_projects":
        result = portfolio_api_service.fetchSpendBycategory(tenant_id=tenantID, applicable_projects=applicable_projects, portfolio_ids=_portfolio_ids, ongoing=True)
        data_obtained = f"""
        Spend Analysis By Category Of Projects:
            {str(result["graph_data"])}
        """
    elif dimension == "spend_analysis_vs_actual_of_projects":
        result = portfolio_api_service.fetchSpendVsActual(tenant_id=tenantID, applicable_projects=applicable_projects, portfolio_ids=_portfolio_ids, ongoing=True)
        data_obtained = f"""
            Actual Spend Vs Planned Spend Data for Ongonig Projects:
            Data:{str(result["graph_data"])}
        """
    elif dimension == "spend_analysis_by_portfolio":
        result = portfolio_api_service.fetch_actual_planned_spend_by_portfolio(tenant_id=tenantID, applicable_projects=applicable_projects, portfolio_ids=_portfolio_ids)
        data_obtained = f"""
        Spend Analysis by portfolio for ongonig projects:
        {str(result["graph_data"])}
        """
    elif dimension == "health_analysis":
        result = portfolio_api_service.fetchOngoingProjectDetails(tenant_id=tenantID, applicable_projects=applicable_projects, portfolio_ids=_portfolio_ids)
        data_obtained += f"""
        Ongoing Projects Data:
            {str(result["ongoing_projects_table_data"])}
        """
        
    elif dimension == "health_analysis_of_projects_by_portfolio":
        result = portfolio_api_service.get_health_of_projects_status_by_portfolio(tenant_id=tenantID, applicable_projects=applicable_projects, portfolio_ids=_portfolio_ids)
        data_obtained += f"""
        Health analysis of projects grouped portfolio :
        Data:{result}
        """
    elif dimension == "health_analysis_change_of_projects":
        result = portfolio_api_service.fetch_health_of_projects_last_week_and_current(tenant_id=tenantID, applicable_projects=applicable_projects, portfolio_ids=_portfolio_ids)
        data_obtained += f"""
        Health analysis of projects changed from last week grouped by metric:
        Data:{result}
        """    
    
    return data_obtained


RETURN_DESCRIPTION = """
    A detailed analysis of the project data, identifying performance issues and suggesting improvements.
"""

ARGUMENTS = [
    {
        "name": "portfolio_ids",
        "type": "int[]",
        "description": "The portfolio_id(s) that the user wants to get analysis on.",
        "required": "false"
    },
    {
        "name": "dimension",
        "type": "str",
        "options": ["spend_analysis_by_category_of_projects", "spend_analysis_vs_actual_of_projects", "spend_analysis_by_portfolio", "health_analysis"],
        "description": """
            The dimension to get analysis of portfolios
        """,
        "required": "true"
    },
]

PORTFOLIO_ANALYST = AgentFunction(
    name="portfolio_analyst",
    description="""
        This function analyzes the performance of individual projects within the portfolio, 
        providing detailed insights into budget overruns, timeline issues, resource allocation, and other performance metrics.
    """,
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=portfolio_analyst,
)
