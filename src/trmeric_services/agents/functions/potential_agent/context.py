import json
from .utils import register_context_builder,clean_and_merge_fields
from src.trmeric_database.dao import ProjectsDao,TenantDao,RoadmapDao, PortfolioDao



@register_context_builder("assign_to_demand")
def context_assign_to_demand(tenant_id: int, user_id: int, **kwargs):
    roadmap_arr_ = RoadmapDao.fetchEligibleRoadmapList(tenant_id=tenant_id, user_id=user_id)
    roadmap_info = [{"roadmap_id": r["roadmap_id"], "roadmap_title": r["roadmap_title"]} for r in roadmap_arr_ if r]

    return {
        "roadmap_info": roadmap_info,
        "context_string": f"""
            These are the roadmaps that the user has access to:
            ------------------
            All available roadmaps of this tenant: {json.dumps(roadmap_info, indent=2, default=str)}
        """
    }

@register_context_builder("update_resource_data")
def context_update_resource_data(tenant_id: int, user_id: int, **kwargs):
    user_portfolios = PortfolioDao.fetchApplicablePortfolios(user_id=user_id, tenant_id=tenant_id)
    portfolio_info = [{'id': p['id'], 'title': p['title']} for p in user_portfolios]

    return {
        "portfolio_info": portfolio_info,
        "context_string": f"""
            ---------------------------------------------
            Accessible Portfolios:
            {json.dumps(portfolio_info, indent=2)}
        """
    }

@register_context_builder("assign_to_project")
def context_assign_to_project(tenant_id: int, user_id: int, eligible_projects: list, **kwargs):
    project_arr = ProjectsDao.fetchProjectIdTitleAndPortfolio(tenant_id=tenant_id, project_ids=eligible_projects)
    return {
        "projects_info": project_arr,
        "context_string": f"""
            These are the projects that the user has access to:
            ------------------
            All the projects which are currently active: {json.dumps(project_arr, indent=2)}
        """
    }

@register_context_builder("add_potential")
def context_add_potential(tenant_id:int,user_id:int,**kwargs):
    org_teams = TenantDao.fetchOrgTeamGroupsForTenant(tenant_id=tenant_id)
    potential_data = TenantDao.getResourceCapacityBasicInfo(tenant_id=tenant_id)
    user_portfolios = PortfolioDao.fetchApplicablePortfolios(user_id=user_id, tenant_id=tenant_id)

    print("---debug potential data----- 1",potential_data[:2])
    clean_potential_data = clean_and_merge_fields(potential_data)
    print("---debug potential data----- 1",clean_potential_data[:2],"\nTotal: ",len(potential_data))

    portfolio_info = [{'id': p.get('id'), 'title': p.get('title')} for p in user_portfolios]
    team_info = [{"orgteam_id": t.get('id'), "orgteam_name": t.get("name") or ""} for t in org_teams]
    resources_info = [{"resource_id": r.get('id'), "resource_name": r.get('name')} for r in clean_potential_data]

    return {
        'portfolio_info': portfolio_info,
        'team_info': team_info,
        'resources_info': resources_info,
        'context_string':  f"""
            Active Resources:
            {json.dumps(resources_info, indent=2)}
            ---------------------------------------------
            Accessible Portfolios:
            {json.dumps(portfolio_info, indent=2)}
            ---------------------------------------------
            Existing Org Teams:
            {json.dumps(team_info, indent=2)}
        """
    }


@register_context_builder('unassign_demand_or_project')
def context_unassign_resource(tenant_id:int, user_id:int, eligible_projects:list, **kwargs):
    roadmap_arr_ = RoadmapDao.fetchEligibleRoadmapList(tenant_id=tenant_id, user_id=user_id)
    roadmap_info = [{"roadmap_id": r.get("roadmap_id"), "roadmap_title": r.get("roadmap_title")} for r in roadmap_arr_ if r]
    # resources_info = [{"resource_id": r.get('id'), "resource_name": r.get('name')} for r in clean_potential_data]
    # print("\n--debug roadmap_arr--------", roadmap_info[:5]) 

    project_info = ProjectsDao.fetchProjectIdTitleAndPortfolio(tenant_id=tenant_id,project_ids = eligible_projects)
    return {
        'projects_info': project_info,
        'roadmap_info': roadmap_info,
        "context_string": f"""
            The user has access to:
            ------------------
            All the projects which are currently active : {json.dumps(project_info, indent=2)}
            ----------------------
            All available roadmaps of this tenant: {json.dumps(roadmap_info, indent=2, default=str)}
        """
    }
