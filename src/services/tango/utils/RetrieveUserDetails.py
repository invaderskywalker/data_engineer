from src.trmeric_database.Database import TrmericDatabase
# from src.trmeric_services.tango.utils.FormatJsonifiedData import formatSQLData
from src.trmeric_utils.FormatJsonifiedData import formatSQLData


def retrieveUserInformation(
    db: TrmericDatabase,
    userID: str,
    tenantID: str,
):

    returnDescription = ""
    query = retrieveAvailablePortfolios(db, tenantID)
    portfolios = db.retrieveSQLQueryOld(query)
    returnDescription += (
        "These are the portfolios that you have access to:\n"
        + formatSQLData(portfolios)
    )

    portfolioTables = []
    portfolioTables.append(portfolios)

    eligibleProjectsQuery = getEligibleProjectsForUser(
        user_id=userID, tenant_id=tenantID
    )
    eligibleProjects = db.retrieveSQLQueryOld(eligibleProjectsQuery)
    eligibleProjectIds = [item["id"] for item in eligibleProjects]

    for portfolio in portfolios:
        portfolioID = portfolio["portfolio_id"]
        query = retrieveAvailableProjects(portfolioID)
        projects = db.retrieveSQLQueryOld(query)
        filtered_projects = [
            item for item in projects if item["project_id"] in eligibleProjectIds
        ]
        returnDescription += (
            f"\n\nThese are the projects in the portfolio {portfolio['portfolio_title']} that you have access to. These will be used for the database related functions, not outside integrations like Jira, Github, etc.\n"
            + formatSQLData(filtered_projects)
        )

    # jiraData = getJiraProjects()
    # returnDescription += (
    #     f"\n\nThese are the projects that you have access to in Jira. These will be used for the Jira related functions, not the database related functions.\n"
    #     + formatSQLData(jiraData)
    # )
    
    # slackInfo = getSlackInfo()
    # slackChannels = slackInfo[0]
    # slackDMs = slackInfo[1]
    # slackUsers = slackInfo[2]
    
    # returnDescription += (
    #     f"\n\nThese are the Slack Channels that you have access to. These will be used for the Slack related functions, not the database related functions.\n"
    #     + (str(slackChannels))
    # )
    # returnDescription += (
    #     f"\n\nThese are the Slack DMs that you have access to. These will be used for the Slack related functions, not the database related functions.\n"
    #     + (str(slackDMs))
    # )
    # returnDescription += (
    #     f"\n\nThis is information on slack users. These will be used for the Slack related functions, not the database related functions.\n"
    #     + (str(slackUsers))
    # )
    return returnDescription


def retrieveEligibleProjects(db: TrmericDatabase, userID: str, tenantID: str):
    eligibleProjectsQuery = getEligibleProjectsForUser(
        user_id=userID, tenant_id=tenantID
    )
    eligibleProjects = db.retrieveSQLQueryOld(eligibleProjectsQuery)
    eligibleProjectIds = [item["id"] for item in eligibleProjects]
    return eligibleProjectIds


# def getJiraProjects():
#     jira = Jira()
#     return jira.getAllAvailabeProjects()

# def getSlackInfo():
#     data = []
#     slack = Slack()
#     data.append(slack.list_channels())
#     data.append(slack.list_direct_messages())
#     data.append(slack.list_all_users())
#     return data

def retrieveAvailablePortfolios(db: TrmericDatabase, tenantID: str):
    # return f"""
    # select 
    #     id as portfolio_id,
    #     title as portfolio_title,
    #     description as portfolio_description,
    #     (first_name || ' ' || last_name) as portfolio_leader
    # from projects_portfolio 
    # where tenant_id_id = {tenantID}
    # """
    return f"""
    select 
        id as portfolio_id,
        title as portfolio_title,
        description as portfolio_description
    from projects_portfolio 
    where tenant_id_id = {tenantID}
    """


def retrieveAvailableProjects(portfolioID: str):
#     return f"""
#     select 
# 	wp.id as project_id,
# 	title as title,
# 	description as description,
# 	project_category as category,
# 	(first_name || ' ' || last_name) as project_manager,
# 	project_manager_id_id as project_manager_id
# From
# 	workflow_project as wp
# Join 
# 	users_user as uu on uu.id = wp.project_manager_id_id
# Where
# 	wp.portfolio_id_id = {portfolioID}
#     """
    return f"""
    select 
	wp.id as project_id,
	title as title,
	description as description,
	project_category as category,
	project_manager_id_id as project_manager_id
From
	workflow_project as wp
Join 
	users_user as uu on uu.id = wp.project_manager_id_id
Where
	wp.portfolio_id_id = {portfolioID}
    """


def getEligibleProjectsForUser(user_id, tenant_id):
    query = f"""
        -- org admin
        select wp.id from workflow_project as wp 
        where (wp.current_stage = 'actionhub_project' OR wp.current_stage = 'trmeric_project_build')
        and wp.parent_id IS NOT NULL
        and wp.tenant_id_id = {tenant_id}
        and exists (
        select * from authorization_userorgrolemap as aurm
        join authorization_orgroles as aor on aor.id = aurm.org_role_id
        where aurm.user_id = {user_id} and (aor.identifier = 'org_admin' or aor.identifier = 'org_leader')) 

        union

        -- porfolio lead
        select wp.id from workflow_project as wp 
        where (wp.current_stage = 'actionhub_project' OR wp.current_stage = 'trmeric_project_build')
        and wp.parent_id IS NOT NULL
        and wp.tenant_id_id = {tenant_id}
        and exists (select * from authorization_portfolioleadermap where user_id = {user_id})

        union 

        -- created by or pm 

        SELECT DISTINCT wp.id
        FROM workflow_project wp 
        join authorization_userprojectrolemap as uprm on uprm.project_id = wp.id or uprm.project_id = wp.parent_id
        WHERE uprm.user_id = {user_id}
        and (wp.current_stage = 'actionhub_project' OR wp.current_stage = 'trmeric_project_build')
        and wp.parent_id IS NOT NULL
        and wp.tenant_id_id = {tenant_id}
    """

    return query
