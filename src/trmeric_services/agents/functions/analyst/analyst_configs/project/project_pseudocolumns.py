from src.trmeric_database.Database import db_instance
from src.trmeric_database.dao import ProjectsDao,PortfolioDao


# Parent Table: workflow_project
# linked tables: workflow_project
    # - kpi
    # - milestone:  list of scope,spend & schedule milestones
    # - retro: proj retro story
    # - risk: risk & mitigations
    # - status: added in update status with category, % and comments
    # - team: team and PM info
    # - teamsplit: team members info (team_id)
    # - valuerealization: the value realized from proj once closed
    # - portfolio: linked with projects_portfolio

    # - businessmember : list of business sponsor leads for the proj
    # - scope: LATER

    # - integrations: BIG MODULE : integration_projectmapping and integration_projectdata
        #for different proj integrations: jira, ado, smartsheet, slack,  github etc.



def get_project_kpis(project_id):
    query = f"""SELECT name,baseline_value FROM workflow_projectkpi
WHERE project_id = {project_id}
"""
    result = db_instance.retrieveSQLQueryOld(query)
    result_str = ""
    for i in range(len(result)):
        kpi = result[i]["name"]
        baseline_value = result[i]["baseline_value"]
        result_str += f"{i + 1}. {kpi} - Baseline Value: {baseline_value}\n"
    return result_str




def get_project_milestones(project_id):
    
    project_milestones = ProjectsDao.fetchProjectMilestones(project_id)
    result_str = ""
    counter = 1
    
    for milestone in project_milestones["scope_milestones"]:
        result_str += f"{counter}. {milestone['milestone_name']} - Type: Scope, Target Date: {milestone['target_date']}, Comments: {milestone['comments'] or 'None'}\n"
        counter += 1
        
    for milestone in project_milestones["schedule_milestones"]:
        result_str += f"{counter}. {milestone['milestone_name']} - Type: Schedule, Target Date: {milestone['target_date']}, Comments: {milestone['comments'] or 'None'}\n"
        counter += 1
    
    for milestone in project_milestones["spend_milestones"]:
        result_str += f"{counter}. {milestone['milestone_name']} - Type: Spend, Planned Spend: {milestone['planned_spend']}, Actual Spend: {milestone['actual_spend']}, Comments: {milestone['comments'] or 'None'}\n"
        counter += 1
    
    return result_str


def get_project_teams(project_id):
    
    counter = 1
    result_str = ""
    project_teams = ProjectsDao.fetchProjectTeamDetails(project_id)
    
    if project_teams["pm"]:
        pm = project_teams["pm"]
        result_str += f"{counter}. Project Manager: {pm['first_name']} {pm['last_name']} - Email: {pm['email']}, Start Date: {pm['start_date']}, End Date: {pm['end_date'] or 'N/A'}\n"
        counter += 1
    
    for member in project_teams["team_members"]:
        result_str += f"""{counter}. Team Member: {member['name']} - Role: {member['role']}, 
                    Email: {member['email']}, 
                    Spend Type: {member['spend_type']}, 
                    Utilization: {member['utilization']}%, 
                    Location: {member['location'] or 'N/A'}\n
        """
        counter += 1
    
    return result_str



def get_project_risks(project_id):
    
    counter = 1
    result_str = ""
    risks = ProjectsDao.fetchProjectsRisks(project_ids=[project_id])
    
    project_risks = risks[0] if risks else []
    for risk in project_risks:
        result_str += f"""{counter}. Risk: {risk['risk_description']} - Impact: {risk['risk_impact']},
                Mitigation: {risk['risk_mitigation'] or 'None'},
                Due Date: {risk['risk_due_date'] or 'N/A'}\n
            """
        counter += 1
    
    return result_str



def get_project_status(project_id):
    
    counter = 1
    result_str = ""
    project_status = ProjectsDao.fetchProjectStatusSummary(project_id)
    
    for status in project_status:
        result_str += f"""{counter}. {status['type'].replace('_status', '').title()} Status: {status['value'].replace('_', ' ').title()} (Count: {status['count']})\n"""
        counter += 1
        
    return result_str



def get_project_retro(project_id):
    
    counter = 1
    result_str = ""
    retro_insights = ProjectsDao.getRetroAnalysisForProject(project_id)
    # print("--debug retro insights---", retro_insights)
    if not retro_insights or "insights" not in retro_insights or not retro_insights["insights"]:
        return result_str
    
    for insight in retro_insights["insights"]:
        title = insight.get("title", "Untitled").replace("_", " ").title()
        data = insight.get("data", "N/A")
        result_str += f"{counter}. {title}: {data}\n"
        counter += 1
    
    return result_str


def get_project_valuerz(project_id, tenant_id):
    
    result_str = ""
    counter = 1
    value_realizations = ProjectsDao.getProjectValueRealizations([project_id], tenant_id)
    
    for vr in value_realizations:
        title = vr.get("title", "N/A")
        actual_value = vr.get("actual_value", "N/A")
        target_value = vr.get("target_value", "N/A")
        baseline_value = vr.get("baseline_value", "N/A")
        actions = vr.get("actions", "")
        key_learnings = vr.get("key_learnings", "")
        
        result_str += f"""{counter}. Value Realization: {title} - Actual: {actual_value}, Target: {target_value}, Baseline: {baseline_value}"""
        
        if actions:
            result_str += f", Actions: {actions}"
        if key_learnings:
            result_str += f", Key Learnings: {key_learnings}"
        
        result_str += "\n"
        counter += 1
    
    return result_str


def get_project_portfolio(project_id, tenant_id):
    
    counter = 1
    result_str = ""
    portfolios = PortfolioDao.fetchPortfolioIdAndTitle(tenantID=tenant_id, eligibleProjects=[project_id])

    for portfolio in portfolios:
        portfolio_id = portfolio.get("id", "N/A")
        portfolio_title = portfolio.get("portfolio_title", "N/A")
        result_str += f"{counter}. Portfolio: {portfolio_title} (ID: {portfolio_id})\n"
        counter += 1

    return result_str    
    
        
PSEUDO_COLUMNS = [
    {"name": "key performance indicators", "type": "list", "description": "list of strings of the KPIs for a project with their baseline values. KPIs are also called key results", "pseudocolumn": True, "params": [("project_id", "id")], "function": get_project_kpis},
    {"name": "milestones", "type": "list","description": "list of strings of the Milestones of a project. Milestones are of 3 types: Scope,Schedule and Spend milestones","pseudocolumn": True, "params": [("project_id", "id")], "function": get_project_milestones},
    {"name": "team details", "type": "list", "description": "list of strings representing the teams and its member details of project","pseudocolumn": True, "params": [("project_id", "id")], "function": get_project_teams},
    {"name": "risk indicators", "type": "list", "description": "list of crucial risk indicators of project","pseudocolumn": True, "params": [("project_id", "id")], "function": get_project_risks},
    {"name": "status indicators", "type": "list", "description": "list of status indicators of project","pseudocolumn": True, "params": [("project_id", "id")], "function": get_project_status},
    {"name": "retrospective insights", "type": "list", "description": "detailed retrospective insights of project","pseudocolumn": True, "params": [("project_id", "id")], "function": get_project_retro},
    {"name": "value realizations", "type": "list", "description": "detailed value realizations of project","pseudocolumn": True, "params": [("project_id", "id"), ("tenant_id", "tenant_id")], "function": get_project_valuerz},
    {"name": "portfolio","type": "list", "description": "portfolio infor for a project","pseudocolumn": True, "params": [("project_id", "id"), ("tenant_id", "tenant_id")], "function": get_project_portfolio}
]




