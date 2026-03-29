
from src.trmeric_services.tango.functions.Types import TangoFunction
from src.trmeric_services.tango.functions.integrations.internal.helpers.SQLHandler import (
    SQL_Handler
)
from src.database.Database import db_instance
from src.database.dao import PortfolioDao, ProjectsDao
from src.trmeric_services.tango.functions.integrations.internal.prompts.Roadmaps import view_roadmaps
from src.trmeric_services.tango.functions.integrations.internal.prompts.IdeaPads import view_ideas


def get_or_plan_it_or_tech_strategy(
    eligibleProjects: list[int],
    tenantID: int,
    userID: int,
    **kwargs
):
    project_data = []
    for project_id in eligibleProjects:
        project_data.append(ProjectsDao.fetch_project_details(project_id))
        
    print("project data --- ", project_data)
    
    roadmap_data = view_roadmaps(tenantID, userID)
    print("roadmap data --- ", roadmap_data)
    
    ideas_data = view_ideas(eligibleProjects, tenantID, userID)
    print("ideas data --- ", ideas_data)
    
    response_prompt = f"""
    I have three datasets related to my organization:
    
    1. **Project Data**: 
       {project_data}
       Each project includes fields such as objectives, timelines, stakeholders, progress, and metrics.

    2. **Roadmap Data**: 
       {roadmap_data}
       Roadmaps include strategic goals, phases, and milestones.

    3. **Ideas Data**: 
       {ideas_data}
       

    **Objective**:
    Analyze these datasets across the following strategic dimensions:
    - Business Alignment
    - Digital Transformation
    - IT Governance
    - Infrastructure Strategy
    - Cybersecurity
    - Enterprise Systems
    - Data Strategy
    - Workforce Enablement
    - Sustainability
    - Vendor and Partner Management
    - Financial Management

    For each dataset:
    - Summarize the key insights for each dimension.
    - Identify opportunities, gaps, or risks associated with each dataset.
    - Propose actionable recommendations to improve alignment with these dimensions.

    **Output Format**:
    Provide the analysis in a structured format with clear section headings for **Projects**, **Roadmaps**, and **Ideas**, followed by subsections for each of the 11 dimensions. Use bullet points for clarity.
    """
    
    
    return response_prompt


RETURN_DESCRIPTION = """
    The thought on how to plan on IT ot Tech strategy 
"""

ARGUMENTS = []


GET_OR_PLAN_IT_TECH_STRATEGY = TangoFunction(
    name="get_or_plan_it_or_tech_strategy",
    description="""
    Important for portfolio snapshot: A function that returns a descriptive snapshot of portfolios for this user. 
    When the question asked is related to snapshot of portfolios then this should be triggered.
    """,
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=get_or_plan_it_or_tech_strategy,
    func_type="sql",
    integration="trmeric"
)
