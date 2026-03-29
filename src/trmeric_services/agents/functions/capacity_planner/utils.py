import os
import re
import json
import datetime
import traceback
from src.trmeric_utils.json_parser import save_as_json
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_database.dao import RoadmapDao,ProjectsDao,TenantDao,TangoDao
from src.trmeric_services.agents.functions.utility.socketio import emit_event,timeline_event,start_show_timeline,stop_show_timeline,end_event



# def send_timeline_updates(socketio, client_id, project_id, team_id, stop_event, interval=8, **kwargs):
#     """
#     Sends periodic timeline updates until stop_event is set. Safe for background execution with Flask-SocketIO.
#     """
#     step_counter = 0
#     stages = kwargs.get("stages",[]) or []

#     try:
#         while not stop_event.is_set() and step_counter < len(stages):
#             stage = stages[step_counter % len(stages)]

#             emit_event("capacity_planner", timeline_event(stage, "timeline", False, "project_id", project_id, "team_id", team_id),socketio,client_id)
#             # Sleep safely (SocketIO-safe sleep)
#             socketio.sleep(seconds = interval)

#             emit_event("capacity_planner",timeline_event(stage, "timeline", True, "project_id", project_id, "team_id", team_id),socketio,client_id)
#             step_counter += 1

#     except Exception as e:
#         appLogger.error({"event": "timeline_thread_error","error": str(e),"traceback": traceback.format_exc()})



def capacity_planner_context(tenant_id,project_id):
    try:
        ##Tenant Config
        tenant_config = TenantDao.getTenantInfo(tenant_id)
        tenant_config_res = tenant_config[0].get('configuration',{}) or None

        #Project context 
        project_details = ProjectsDao.fetchProjectDetailsForIssueCreation(project_id)

        ## If proj is inherited from roadmap
        attached_roadmap = RoadmapDao.getRoadmapIdToAttachedProject(project_id)
        roadmap_id = attached_roadmap[0].get("roadmap_id",None) if attached_roadmap else None
        print("--debug capacity_planner_context roadmap id--------", roadmap_id)
        roadmap = {}
        if roadmap_id:
            roadmap_details = RoadmapDao.fetchRoadmapDetails(roadmap_id=roadmap_id)
            roadmap_estimation  = get_roadmap_estimation_data(roadmap_id)

            roadmap_inputs = {
                "id": roadmap_id,
                "title": roadmap_details[0].get("roadmap_title",""),
                "type": roadmap_details[0].get("roadmap_type",""),
                "description": roadmap_details[0].get("roadmap_description",""),
                "scope": roadmap_details[0].get("roadmap_scope",""),
                # "roadmap_objectives": roadmap_details[0].get("roadmap_objectives")
            } if len(roadmap_details) > 0 else {}

            roadmap["info"] = roadmap_inputs
            roadmap["estimation"] = roadmap_estimation.get("labor",[]) or []

        result = {
            "tenant_config": tenant_config_res,
            "project_context": project_details[0] or [],
            "roadmap_context": roadmap if roadmap_id else {}
        }
        # save_as_json(data = result,filename=f"capacity_planner_context_{project_id}.json")
        return result
    
    except Exception as e:
        appLogger.error({"event": "capacity_planner_context", "error": str(e), "traceback": traceback.format_exc()})
        return {}





def get_roadmap_estimation_data(roadmap_id):

    estimation_data = RoadmapDao.fetchTeamDataRoadmap(roadmap_id)
    estimation_json = {"labor":[],"non_labor":[]}

    for item in estimation_data:
        name = item.get("name",None) or None
        if name is None:
            continue

        resource_entry = {
            "role": name,
            "rate": item.get("estimate_value", "") or "",
            "allocation": item.get("allocation", 0) or 0,
            "desc": item.get("description", "") or "",
            "location": item.get("location", ""),
            "timeline": f"Start date: {item.get('start_date','')} End date: {item.get('end_date','')}"
        }

        if item.get("labour_type",0) == 1:
            estimation_json["labor"].append(resource_entry)
        else:
            estimation_json["non_labor"].append(resource_entry)
            
    return estimation_json



def roadmap_instructions_prompt(inherited_roadmap):
    
    parsed = json.loads(inherited_roadmap)
    if not parsed: 
        return None

    # print("\n222--debug roadmap_instructions_prompt: ", type(inherited_roadmap),"\nroadmap",inherited_roadmap)
    return f"""
        This project has been inherited from a roadmap i.e. now it's in a execution stage, whose details are provided here.
        Follow the instructions below for recommendation.
        <inherited_roadmap>
            {inherited_roadmap}
        </inherited_roadmap>

        It consists of:
            1.Basic roadmap info: <inherited_roadmap>.info (Title,**Type,Scope**,desc etc.)
            2.Estimation details: <inherited_roadmap>.estimation 
                -The roles which were finalized for this roadmap, it includes (role,allocation,desc,rate,location etc.)
        You've to take this context into consideration when suggesting the roles for the current project and mention it's relevance in the thought process below
    """
    


###Allocator
def resource_allocator_context(tenant_id,session_id,user_id,project_id,team_id):
    
    try:
        selected_roles_ = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(
            session_id=session_id,user_id=user_id,
            key=f"resource_allocator_{project_id}_{team_id}"
        )
        selected_roles = json.loads(selected_roles_[0]['value']) if len(selected_roles_)>0 else None
        
        resources = ProjectsDao.getCapacityPlannerResources(tenant_id=tenant_id)
        project_details = ProjectsDao.fetchProjectDetailsForIssueCreation(project_id=project_id)
        # project_providers = TenantDao.FetchAllProvidersForProject(project_id=project_id_in_conv)
        
        print("--debug project portfolio------", project_details[0]['portfolio'])
        portfolio_orgteams = TenantDao.fetchOrgTeamsAndPortfolioMappingForTenant(tenant_id=tenant_id)
        portfolio_orgteam_mapping = {}
        for item in portfolio_orgteams:
            portfolio_orgteam_mapping[item.get("portfolio_name","")] = item.get("org_team","") or "No Team"

        result = {
            "selected_roles": selected_roles,
            "resources": resources,
            "project_details": project_details,
            "portfolio_orgteam_mapping": portfolio_orgteam_mapping,
            # "project_providers": project_providers
        }
        # save_as_json(result,f"allocator_context_{project_id}.json")
        return result
    except Exception as e:
        appLogger.error({"event": "resource_allocator_context", "error": str(e), "traceback": traceback.format_exc()})
        return {}
        




def parse_resource_recommendataion(data):
    """
    Deduplicate resources by ID within internal_employees and provider_employees, merging group_list for duplicates.
    Adds trending, spendType, external, and cleans role field.
    """
    finalized_resources = data.copy()  
    before_ids = set()
    for item in finalized_resources.get("internal_employees", []):
        before_ids.add(item["id"])
    for item in finalized_resources.get("provider_employees", []):
        before_ids.add(item["id"])
    print(f"---debug deduplicated: before={before_ids}")
    
    # Deduplicate internal_employees
    internal_ids = {}
    deduped_internal = []
    for item in finalized_resources.get("internal_employees", []):
        resource_id = item["id"]
        name = item.get("name",None) or None
        if resource_id not in internal_ids:
            # First occurrence: add fields and store
            parts = name.strip().split()
            item["first_name"] = parts[0] if parts else ""
            item["last_name"] = " ".join(parts[1:]) if len(parts) > 1 else ""
            item["trending"] = "true"
            item["spendType"] = "Capex"
            item["external"] = "false"
            item["role"] = item["role"].strip()
            internal_ids[resource_id] = {"resource": item["name"]}
            deduped_internal.append(item)
    
    # Deduplicate provider_employees
    provider_ids = {}
    deduped_provider = []
    for item in finalized_resources.get("provider_employees", []):
        resource_id = item["id"]
        name = item.get("name",None) or None
        if resource_id not in provider_ids:
            # First occurrence: add fields and store
            parts = name.strip().split()
            item["first_name"] = parts[0] if parts else ""
            item["last_name"] = " ".join(parts[1:]) if len(parts) > 1 else ""
            item["trending"] = "true"
            item["spendType"] = "Capex"
            item["external"] = "true"
            item["role"] = item["role"].strip()
            provider_ids[resource_id] = {"resource": item["name"]}
            deduped_provider.append(item)
      
    # Update finalized_resources
    finalized_resources["internal_employees"] = deduped_internal
    finalized_resources["provider_employees"] = deduped_provider
    
    print(f"---debug deduplicated: internal={len(deduped_internal)}, provider={len(deduped_provider)}")
    after_ids = set()
    for item in finalized_resources.get("internal_employees", []):
        after_ids.add(item["id"])
    for item in finalized_resources.get("provider_employees", []):
        after_ids.add(item["id"])
    # print(f"\n---debug deduplicated: after={after_ids}")

    return finalized_resources




def group_resources_hierarchically(resources, tenant_id, filter_inactive=True, is_external=False):
    """
    Group resources by org_team's primary_skill > org_team_name > list of resources.
    Deduplicates by resource ID within each team.
    """
    from src.trmeric_services.agents.functions.potential_agent.utils import PRIMARY_SKILLS
    _org_teams = TenantDao.fetchOrgTeamGroupsForTenant(tenant_id)
    org_teams = [team.get("name", "No Team") or 'No Team' for team in _org_teams if _org_teams] + ['No Team'] or ["No Team"]
    print("\n\n---debug org_teams -----------", org_teams)
    
    grouped = {}
    skipped_resources = []
    
    for resource in resources:
        if filter_inactive and not resource.get('is_active', True):
            print(f"Skipping inactive resource: {resource['id']}")
            skipped_resources.append({"id": resource['id'],"name":resource["name"]})
            continue
        
        # Get resource's primary skill
        resource_primary_skill = resource.get('primary_skill', 'Other')
        if resource_primary_skill not in PRIMARY_SKILLS:
            resource_primary_skill = 'Other'
        
        # Get organization_team list
        org_teams_list = resource.get('organization_team', [])
        if not org_teams_list:
            org_teams_list = [{
                'leader_name': None,
                'org_team': 'No Team',
                'primary_skill': resource_primary_skill
            }]
        
        for team in org_teams_list:
            org_team_name = team.get('org_team', 'No Team') or 'No Team'
            team_primary_skill = team.get('primary_skill', resource_primary_skill) or resource_primary_skill
            
            # Validate team_primary_skill
            if not team_primary_skill or team_primary_skill not in PRIMARY_SKILLS:
                team_primary_skill = resource_primary_skill if org_team_name == 'No Team' else 'Other'
            
            # Validate org_team_name against portfolio_orgteams
            if org_team_name not in org_teams and org_team_name != 'No Team':
                print(f"Skipping invalid org_team: {org_team_name} for resource {resource['id']}")
                skipped_resources.append({"id": resource['id'],"name":resource["name"]})
                continue
            
            # Initialize nested dicts
            if team_primary_skill not in grouped:
                grouped[team_primary_skill] = {}
            if org_team_name not in grouped[team_primary_skill]:
                grouped[team_primary_skill][org_team_name] = {}
            
            resource_id = resource['id']
            
            # Add resource to group, deduplicating by resource_id
            if resource_id not in grouped[team_primary_skill][org_team_name]:
                grouped[team_primary_skill][org_team_name][resource_id] = {
                    'id': resource_id,
                    'name': resource.get('name',''),
                    # 'role': resource.get('role',''),
                    'description': resource.get('description',''),
                    'availability': resource.get('availability',''),
                    'allocation': resource.get('allocation',''),
                    'skills': resource.get('skills', '') or "",
                    'external': resource.get('external',''),
                    'project_timeline': resource.get('project_timeline',[]) or [],
                    'org_team_leader': f"{team.get('leader_first_name', '')} {team.get('leader_last_name', '')}" or "Unknown"
                }
                if is_external:
                    # print("--debug grouping provider-------", resource['id'], "name", resource["name"])
                    resource_data = grouped[team_primary_skill][org_team_name][resource_id]
                    grouped[team_primary_skill][org_team_name][resource_id] = {
                        **resource_data,
                        "external_provider_name": resource["external_provider_name"],
                        "tenant_provider_name": resource["tenant_provider_name"],
                        # "external_provider_website": resource["external_provider_website"],
                        # "tenant_provider_website": resource["tenant_provider_website"],
                    }
    
    # Convert to final nested structure
    result = {
        skill: {
            team: list(resources.values())
            for team, resources in teams.items()
        }
        for skill, teams in grouped.items()
    }

    ##Verify the count 
    total_resources = 0
    duplicate_ids = []
    for skill, teams in result.items():
        # print("--debug skill-----", skill)
        for team, resources in teams.items():
            # print("\n--debug teams----", team)
            total_resources += len(resources)
            for resource in resources:
                if resource['id'] in duplicate_ids:
                    print(f"Duplicate ID found: {resource['id']}")
                    duplicate_ids.append(resource['id'])


    print("--debug total_resources-----", total_resources)
    print("--debug duplicate_ids-----", duplicate_ids)
    # Write to JSON for debugging
    # with open(f"resource_grp1_{tenant_id}_{datetime.datetime.now()}.json", "w") as f:
    #     json.dump(result, f, indent=4)
    
    print(f"---debug grouped resources: {len(result)} primary skills")
    print(f"\n\n---debug skipped resources: {skipped_resources}")
    appLogger.info({"event":"grouping_resources","skipped": skipped_resources,"duplicates": duplicate_ids,"tenant_id":tenant_id})
    return result



