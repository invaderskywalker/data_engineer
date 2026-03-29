from src.trmeric_database.Database import db_instance
from src.trmeric_api.logging.AppLogger import appLogger


class ProjectsDao:

    @staticmethod
    def FetchLatestProjectStatusUpdate(project_id):
        query = f"""
            SELECT 
                wps.type AS status_type,
                wps.value AS status_value,
                wps.comments AS status_comments,
				wp.portfolio_id_id AS portfolio_id
            FROM 
                workflow_project wp
            JOIN 
                workflow_projectstatus wps ON wp.id = wps.project_id
            WHERE 
                wp.id = {project_id} 
            ORDER BY 
                wps.created_date DESC
            LIMIT 1;
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def FetchAllProjectStatusUpdates(project_id):
        query = f"""
            SELECT 
                wps.type AS status_type,
                wps.value AS status_value,
                wps.comments AS status_comments,
				wp.portfolio_id_id AS portfolio_id
            FROM 
                workflow_project wp
            JOIN 
                workflow_projectstatus wps ON wp.id = wps.project_id
            WHERE 
                wp.id = {project_id} 
            ORDER BY 
                wps.created_date DESC
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def FetchProjectDetails(project_id):
        query = f"""
            select * from workflow_project where id={project_id}
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def FetchProviderIdsForProjects(project_id):
        query = f"""
            SELECT 
                tp.id AS provider_id
            FROM 
                workflow_projectprovider wpp
            JOIN 
                tenant_provider tp ON wpp.provider_id = tp.id
            WHERE 
                wpp.project_id = {project_id};
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def FetchProjectIdsIdsForProvider(provider_id):
        query = f"""
            SELECT 
                wp.id AS project_id,
                wp.title AS project_title,
                wp.state,
                wp.current_stage,
                wp.start_date,
                wp.end_date
            FROM 
                workflow_project wp
            JOIN 
                workflow_projectprovider wpp ON wp.id = wpp.project_id
            WHERE 
                wpp.provider_id = {provider_id};
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def FetchProjectManagerInfoForProjects(_project_ids):
        project_ids_str = f"({', '.join(map(str, _project_ids))})"
        query = f"""
        select 
        wp.id as project_id , 
        wp.title as project_name,
        wp.project_manager_id_id as project_manager_id,
        uu.first_name, uu.last_name
        from workflow_project as wp
        join users_user as uu on uu.id = project_manager_id_id
        where wp.id in 
        {project_ids_str}
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def FetchProjectNamesForIds(_project_ids):
        project_ids_str = f"({', '.join(map(str, _project_ids))})"
        query = f"""
        select 
            wp.id as project_id , 
            wp.title as project_title
            
        from workflow_project as wp
        where wp.id in 
        {project_ids_str}
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def FetchTeamMemberNames(_project_ids):
        project_ids_str = f"({', '.join(map(str, _project_ids))})"
        query = f"""
        select wpts.member_name
            from workflow_project as wp
            join workflow_projectteamsplit as wpts 
            on wp.id = wpts.project_id
        where wp.id in 
        {project_ids_str}
        """
        return db_instance.retrieveSQLQueryOld(query)

    def FetchEligibleProjectsForVRAgent(tenant_id: int, user_id: int):
        # added to fetch all archived projects only
        query = f"""
               -- org admin
                select wp.id from workflow_project as wp 
                where (wp.current_stage = 'actionhub_project' OR wp.current_stage = 'trmeric_project_build' OR wp.current_stage = 'trmeric_project_build_archive' OR wp.current_stage = 'actionhub_project_archive' )
                and wp.form_status = 2
            	and wp.archived_on IS NOT NULL
                and wp.tenant_id_id = {tenant_id}
                and exists (
                select * from authorization_userorgrolemap as aurm
                join authorization_orgroles as aor on aor.id = aurm.org_role_id
                where aurm.user_id = {user_id} and (aor.identifier = 'org_admin' or aor.identifier = 'org_leader')) 

                union

                -- porfolio lead
                select wp.id from workflow_project as wp 
                where (wp.current_stage = 'actionhub_project' OR wp.current_stage = 'trmeric_project_build_archive' OR wp.current_stage = 'actionhub_project_archive' )
                and wp.form_status = 2
           		and wp.archived_on IS NOT NULL
                and wp.tenant_id_id = {tenant_id}
                and exists (select * from authorization_portfolioleadermap where user_id = {user_id})

                union 

                -- created by or pm 

                SELECT DISTINCT wp.id
                FROM workflow_project wp 
                WHERE (wp.project_manager_id_id = {user_id} or wp.created_by_id = {user_id})
                and (wp.current_stage = 'actionhub_project' OR wp.current_stage = 'trmeric_project_build' OR wp.current_stage = 'trmeric_project_build_archive' OR wp.current_stage = 'actionhub_project_archive' )
                and wp.form_status = 2
            	and wp.archived_on IS NOT NULL
                and wp.tenant_id_id = {tenant_id}
        """
        eligibleProjects = db_instance.retrieveSQLQueryOld(query)
        eligibleProjectIds = [item["id"] for item in eligibleProjects]
        return eligibleProjectIds

    @staticmethod
    def FetchAvailableProject(tenant_id, user_id):
        query = f"select types from tenant_tenant where id = {tenant_id}"
        tenant_type = "customer"
        try:
            tenant_type_obj = db_instance.retrieveSQLQueryOld(query)
            # print("tenant_type_obj ", tenant_type_obj)
            if tenant_type_obj:
                if tenant_type_obj[0]["types"] != "customer":
                    tenant_type = "provider"
        except Exception as e:
            appLogger.error(
                {"event": "error in FetchAvailableProject", "error": e})

        if tenant_type == "customer":
            query = f"""
                    select wp.id from workflow_project as wp
					join workflow_projectportfolio as wpp on wpp.project_id=wp.id
					join authorization_portfolioleadermap as aplm on aplm.portfolio_id=wpp.portfolio_id and aplm.user_id = {user_id}
                    where wp.parent_id IS NOT NULL
                    and wp.archived_on IS NULL
                    and wp.tenant_id_id = {tenant_id}
                    and exists (
						select * from authorization_userorgrolemap as aurm
						join authorization_orgroles as aor on aor.id = aurm.org_role_id
						where aurm.user_id = {user_id}
                    )
					union

					select wp.id from workflow_project as wp 
                    where wp.parent_id IS NOT NULL
                    and wp.archived_on IS NULL
                    and wp.tenant_id_id = {tenant_id}
					and not exists (
						select * from authorization_portfolioleadermap as aplm where aplm.user_id= {user_id}
					)
                    and exists (
                    select * from authorization_userorgrolemap as aurm
                    join authorization_orgroles as aor on aor.id = aurm.org_role_id
                    where aurm.user_id = {user_id})

					

					

					union 


                    -- created by or pm 


                    SELECT DISTINCT wp.id
                    FROM workflow_project wp 
                    WHERE (wp.project_manager_id_id = {user_id} or wp.created_by_id = {user_id})
                    and wp.parent_id IS NOT NULL
                    and wp.archived_on IS NULL
                    and wp.tenant_id_id = {tenant_id}
                    
                    
                    order by id asc
            """
        elif tenant_type == "provider":
            query = f"""
                SELECT wp.id
                FROM workflow_project wp 
                where wp.parent_id IS NOT NULL
                and wp.archived_on IS NULL
                and wp.tenant_id_id = {tenant_id}
            """
        eligibleProjects = db_instance.retrieveSQLQueryOld(query)
        eligibleProjectIds = [item["id"] for item in eligibleProjects]
        return eligibleProjectIds

    @staticmethod
    def FetchAccesibleArchivedProjects(tenant_id, user_id):
        query = f"select types from tenant_tenant where id = {tenant_id}"
        tenant_type = "customer"
        try:
            tenant_type_obj = db_instance.retrieveSQLQueryOld(query)
            # print("tenant_type_obj ", tenant_type_obj)
            if tenant_type_obj:
                if tenant_type_obj[0]["types"] != "customer":
                    tenant_type = "provider"
        except Exception as e:
            appLogger.error(
                {"event": "error in FetchAvailableProject", "error": e})

        if tenant_type == "customer":
            query = f"""
                    select wp.id from workflow_project as wp
					join workflow_projectportfolio as wpp on wpp.project_id=wp.id
					join authorization_portfolioleadermap as aplm on aplm.portfolio_id=wpp.portfolio_id and aplm.user_id = {user_id}
                    where wp.parent_id IS NOT NULL
                    and wp.archived_on IS NOT NULL
                    and wp.tenant_id_id = {tenant_id}
                    and exists (
						select * from authorization_userorgrolemap as aurm
						join authorization_orgroles as aor on aor.id = aurm.org_role_id
						where aurm.user_id = {user_id}
                    )
					union

					select wp.id from workflow_project as wp 
                    where wp.parent_id IS NOT NULL
                    and wp.archived_on IS NOT NULL
                    and wp.tenant_id_id = {tenant_id}
					and not exists (
						select * from authorization_portfolioleadermap as aplm where aplm.user_id= {user_id}
					)
                    and exists (
                    select * from authorization_userorgrolemap as aurm
                    join authorization_orgroles as aor on aor.id = aurm.org_role_id
                    where aurm.user_id = {user_id})

					

					

					union 


                    -- created by or pm 


                    SELECT DISTINCT wp.id
                    FROM workflow_project wp 
                    WHERE (wp.project_manager_id_id = {user_id} or wp.created_by_id = {user_id})
                    and wp.parent_id IS NOT NULL
                    and wp.archived_on IS NOT NULL
                    and wp.tenant_id_id = {tenant_id}
                    
                    
                    order by id asc
            """
        elif tenant_type == "provider":
            query = f"""
                SELECT wp.id
                FROM workflow_project wp 
                where wp.parent_id IS NOT NULL
                and wp.archived_on IS NOT NULL
                and wp.tenant_id_id = {tenant_id}
            """
        eligibleProjects = db_instance.retrieveSQLQueryOld(query)
        eligibleProjectIds = [item["id"] for item in eligibleProjects]
        return eligibleProjectIds


    @staticmethod
    def fetchProjectsForTenantCreatedAfterYesterday(tenant_id):
        # query = f"""
        #     SELECT
        #         id as project_id,
        #         title as project_title,CASE
        #             WHEN current_stage = 'trmeric_project_discover' THEN 'Discover Project'
        #             WHEN current_stage = 'actionhub_project' THEN 'Actionhub Project'
        #             WHEN current_stage = 'trmeric_project_engage' THEN 'Engage Project'
        #             WHEN current_stage = 'trmeric_project_build' THEN 'Actionhub Project'
        #             ELSE 'Unknown Stage'
        #     END AS project_stage
        #     FROM public.workflow_project
        #     WHERE created_on >= DATE_TRUNC('day', CURRENT_DATE - INTERVAL '1 day')
        #     AND created_on < DATE_TRUNC('day', CURRENT_DATE)
        #     AND tenant_id_id={tenant_id};
        # """
        query = f"""
            SELECT 
                wp.id as project_id, 
                wp.title as project_title,
                uu.username as created_by,
                CASE 
                    WHEN wp.current_stage = 'trmeric_project_discover' THEN 'Discover Project'
                    WHEN wp.current_stage = 'actionhub_project' THEN 'Actionhub Project'
                    WHEN wp.current_stage = 'trmeric_project_engage' THEN 'Engage Project'
                    WHEN wp.current_stage = 'trmeric_project_build' THEN 'Actionhub Project'
                    ELSE 'Unknown Stage'
            END AS project_stage
            FROM workflow_project as wp
            join users_user as uu on uu.id = wp.created_by_id
            WHERE wp.created_on >= DATE_TRUNC('day', CURRENT_DATE - INTERVAL '1 day')
            AND wp.created_on < DATE_TRUNC('day', CURRENT_DATE)
            AND wp.tenant_id_id={tenant_id}
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def projectStatusUpdatesMadeYesterday(tenant_id):
        query = f"""
            SELECT 
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
                wp.title AS project_title,
                uu.username AS updated_by
            FROM 
                workflow_project wp
            JOIN 
                workflow_projectstatus wps ON wp.id = wps.project_id
            JOIN 
                users_user uu ON uu.id = wp.created_by_id
            WHERE 
                wps.created_date >= DATE_TRUNC('day', CURRENT_DATE - INTERVAL '1 day')
                AND wps.created_date < DATE_TRUNC('day', CURRENT_DATE)
                AND wp.tenant_id_id = {tenant_id}
            ORDER BY 
                wps.created_date DESC;

        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchProjectDetailsForIssueCreation(project_id):
        """Update this query as required"""
        query = f"""
            SELECT  
                wp.title,  
                wp.description,  
                wp.objectives,  
                wp.technology_stack,  
                wp.project_category,  
                wp.start_date,  
                wp.end_date,  
                ARRAY_AGG(wpkpi.name) AS key_results,  
                wps.scope AS project_scope,
                pp.title AS portfolio
            FROM workflow_project AS wp  
            LEFT JOIN workflow_projectkpi AS wpkpi ON wpkpi.project_id = wp.id  
            LEFT JOIN workflow_projectscope AS wps ON wps.project_id = wp.id  
            LEFT JOIN projects_portfolio AS pp ON pp.id = wp.portfolio_id_id
            WHERE wp.id = {project_id}  
            GROUP BY  
                wp.title, wp.description, wp.objectives, wp.technology_stack,
                wp.project_category, wp.start_date,wp.end_date, wps.scope, pp.title;
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchMilestoneForProject(project_id):
        query = f"""
            select id,name as milestone_name, target_date, planned_spend, actual_spend
            from workflow_projectmilestone where project_id = {project_id}
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchProjectMilestones(project_id):
        query = f"""
            SELECT
                wm.id AS id, 
                wm.name AS milestone_name, 
                wm.target_date, 
                wm.planned_spend, 
                wm.actual_spend,
                wm.comments,
                wm.type,
                CASE
                    WHEN type = 1 THEN 'scope_milestone'
                    WHEN type = 2 THEN 'schedule_milestone'
                    WHEN type = 3 THEN 'spend_milestone'
                END AS type_name
            FROM workflow_projectmilestone as wm
            WHERE project_id = {project_id}
        """
        milestones = db_instance.retrieveSQLQueryOld(query)

        if not milestones:
            return {
                "scope_milestones": [],
                "schedule_milestones": [],
                "spend_milestones": []
            }

        # Separate milestones by type
        scope_milestones = []
        schedule_milestones = []
        spend_milestones = []

        for milestone in milestones:
            if milestone['type_name'] == 'scope_milestone':
                scope_milestones.append(milestone)
            elif milestone['type_name'] == 'schedule_milestone':
                schedule_milestones.append(milestone)
            elif milestone['type_name'] == 'spend_milestone':
                spend_milestones.append(milestone)

        return {
            "scope_milestones": scope_milestones,
            "schedule_milestones": schedule_milestones,
            "spend_milestones": spend_milestones
        }
   
    @staticmethod
    def fetchProjectTeamDetails(project_id):

        fetch_pm_query = f"""
            SELECT 
                pt.project_id,
                pt.name AS project_name,
                pt.pm_first_name,
                pt.pm_last_name,
                pt.pm_email,
                pt.updated_date,
                pt.start_date,
                pt.end_date
            FROM 
                public.workflow_projectteam pt
            WHERE 
                pt.project_id = {project_id};
        """
        pm_details = db_instance.retrieveSQLQueryOld(fetch_pm_query)

        # Query to fetch team details
        fetch_team_query = f"""
            SELECT 
                pts.project_id,
                pts.is_external,
                pts.location,
                pts.team_members,
                CASE 
                    WHEN pts.spend_type = 1 THEN 'Internal'
                    WHEN pts.spend_type = 2 THEN 'External'
                    ELSE 'Unknown'
                END AS spend_type,
                pts.average_spend,
                pts.member_email,
                pts.member_name,
                pts.member_role,
                pts.member_utilization
            FROM 
                public.workflow_projectteamsplit pts
            WHERE 
                pts.project_id = {project_id};
        """
        team_details = db_instance.retrieveSQLQueryOld(fetch_team_query)

        # Structure the data
        team_data = {}

        if pm_details:
            pm_detail = pm_details[0]  # Assuming one PM per project
            team_data = {
                'project_id': pm_detail['project_id'],
                'project_title': pm_detail['project_name'],
                'pm': {
                    'first_name': db_instance.deanonymize_text_from_base64(pm_detail['pm_first_name']),
                    'last_name': db_instance.deanonymize_text_from_base64(pm_detail['pm_last_name']),
                    'email': pm_detail['pm_email'],
                    'start_date': pm_detail['start_date'],
                    'end_date': pm_detail['end_date'],
                    'updated_date': pm_detail['updated_date']
                },
                'team_members': []
            }
        else:
            team_data = {
                'project_id': project_id,
                'project_title': None,
                'pm': None,
                'team_members': []
            }

        if team_details:
            for member in team_details:
                team_data['team_members'].append({
                    'is_external': member['is_external'],
                    'location': member['location'],
                    'team_members': member['team_members'],
                    'spend_type': member['spend_type'],
                    'average_spend': member['average_spend'],
                    'email': db_instance.deanonymize_text_from_base64(member['member_email']),
                    'name': db_instance.deanonymize_text_from_base64(member['member_name']),
                    'role': member['member_role'],
                    'utilization': member['member_utilization']
                })

        return team_data

    @staticmethod
    def fetchProjectsInfoForPortfolio(portfolio_id, tenant_id, archived=False):
        condition_statement = ''
        if archived:
            condition_statement = "AND wp.archived_on IS not NULL"

        query = f"""
            SELECT 
                COALESCE(pp.id, 0) AS portfolio_id,
                COALESCE(pp.title, 'No Portfolio') AS portfolio_title,
                wp.id AS project_id,
                wp.title AS project_name,
                wp.start_date,
                wp.end_date,
                wp.project_type,
                wp.spend_status,
                wp.scope_status,
                wp.delivery_status,
                uu.first_name as project_manager_name,
                
                ARRAY_AGG(wpkpi.name) AS kpi_names,
                ARRAY_AGG(wps.comments) AS insights,
                -- Milestone data
                JSON_AGG(
                    JSON_BUILD_OBJECT(
                        'milestone_name', wpm.name,
                        'target_date', wpm.target_date,
                        'planned_spend', wpm.planned_spend,
                        'actual_spend', wpm.actual_spend
                    )
                ) FILTER (WHERE wpm.id IS NOT NULL) AS milestones
                
            FROM 
                workflow_project wp
            join workflow_projectportfolio wpp on wp.id = wpp.project_id
            join projects_portfolio pp ON wpp.portfolio_id = pp.id
            left join workflow_projectkpi  wpkpi on wp.id = wpkpi.project_id
            LEFT JOIN users_user as uu on wp.project_manager_id_id = uu.id
            left join workflow_projectstatus as wps on wp.id = wps.project_id
            LEFT JOIN workflow_projectmilestone wpm ON wp.id = wpm.project_id AND wpm.type = 3  -- Only type 3 milestones
        
            WHERE 
                pp.id = {portfolio_id}
                and wp.tenant_id_id = {tenant_id}
                {condition_statement}
                AND wp.parent_id is not NULL
            GROUP BY 
            pp.id, pp.title, wp.id, uu.first_name, wp.title, wp.start_date, wp.end_date, 
            wp.project_type, wp.spend_status, wp.scope_status, wp.delivery_status;
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchfutureProjectsInfoForPortfolio(portfolio_id, tenant_id):

        query = f"""
            select  
                COALESCE(pp.id, 0) AS portfolio_id,
                COALESCE(pp.title, 'No Portfolio') AS portfolio_title,
                rr.id as project_id,
                rr.title as project_name,
                rr.start_date,
                rr.end_date,
                rr.budget as planned_spend,
                ARRAY_AGG(rrkpi.name) AS kpi_names
            from roadmap_roadmap rr
            left join roadmap_roadmapportfolio rrp on rrp.roadmap_id = rr.id
            left join roadmap_roadmapkpi as rrkpi on rrkpi.roadmap_id = rr.id
            left join projects_portfolio pp ON rrp.portfolio_id = pp.id
            where rr.tenant_id = {tenant_id} and pp.id = {portfolio_id}
            GROUP BY pp.id, pp.title, rr.id, rr.title, rr.start_date, rr.end_date;
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def getTeamInfoProject(project_id):

        query = f"""
            SELECT * FROM public.workflow_projectteam
                where project_id= {project_id};
        """

        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def getProviderIdInfoProject(project_id):
        query = f"""
            SELECT provider_id_id FROM public.workflow_project
            where id={project_id};
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchInfoForListOfProjects(project_ids):
        if not project_ids:
            return []

        project_ids_str = f"({', '.join(map(str, project_ids))})"
        query = f"""
            select 
                COALESCE(wp.id,0) as project_id, 
                COALESCE(wp.title,'No Project') as project_title,
                wp.start_date,
                wp.end_date,
                wp.project_type,
                wp.spend_status,
                wp.scope_status,
                wp.delivery_status,
                COALESCE(uu.first_name,'Unknown') as project_manager_name,
                ARRAY_AGG(wpkpi.name) AS kpi_names,
                ARRAY_AGG(wps.comments) AS insights,
                JSON_AGG(
                    JSON_BUILD_OBJECT(
                        'milestone_name', wpm.name,
                        'target_date', wpm.target_date,
                        'planned_spend', wpm.planned_spend,
                        'actual_spend', wpm.actual_spend
                    )
                ) FILTER (WHERE wpm.id IS NOT NULL) AS milestones
            from workflow_project as wp
            left join workflow_projectkpi as wpkpi on wp.id = wpkpi.project_id
            LEFT JOIN users_user as uu on wp.project_manager_id_id = uu.id
            left join workflow_projectstatus as wps on wp.id = wps.project_id
            LEFT JOIN workflow_projectmilestone wpm ON wp.id = wpm.project_id AND wpm.type = 3
            where wp.id in ({project_ids_str})
            GROUP BY 
            wp.id, uu.first_name, wp.title, wp.start_date, wp.end_date, wp.project_type, 
            wp.spend_status, wp.scope_status, wp.delivery_status;
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchProjectsInfoForPortfolioV2Old(portfolio_ids, tenant_id, applicable_projects, archived=False):
        if len(applicable_projects) == 0:
            return []

        portfolio_ids_str = f"({', '.join(map(str, portfolio_ids))})"
        project_ids_str = f"({', '.join(map(str, applicable_projects))})"

        condition_statement = f'AND wp.archived_on IS NULL and wp.id in {project_ids_str}'
        if archived:
            condition_statement = "AND wp.archived_on IS not NULL"

        query = f"""
            SELECT 
                COALESCE(pp.id, 0) AS portfolio_id,
                COALESCE(pp.title, 'No Portfolio') AS portfolio_title,
                wp.id AS project_id,
                wp.title AS project_name,
                wp.description AS project_description,
                wp.objectives,
                wp.start_date,
                wp.end_date,
                wp.project_type,
                wp.spend_status,
                wp.scope_status,
                wp.delivery_status,
                uu.first_name as project_manager_name,
                
                ARRAY_AGG(distinct wpkpi.name) AS kpi_names,
                ARRAY_AGG(distinct wps.comments) AS insights,
              
				JSON_AGG(
					JSON_BUILD_OBJECT(
						'milestone_name', wpm.name,
						'target_date', wpm.target_date,
						'planned_spend', wpm.planned_spend,
						'actual_spend', wpm.actual_spend
					)::TEXT -- Convert JSON object to text
				) FILTER (WHERE wpm.id IS NOT NULL) AS unique_milestones_text,

				JSON_AGG(
					DISTINCT JSON_BUILD_OBJECT(
						'milestone_name', wpm.name,
						'target_date', wpm.target_date,
						'planned_spend', wpm.planned_spend,
						'actual_spend', wpm.actual_spend
					)::TEXT
				)::JSON AS milestones,
    
                
            FROM 
                workflow_project wp
            join workflow_projectportfolio wpp on wp.id = wpp.project_id
            join projects_portfolio pp ON wpp.portfolio_id = pp.id
            left join workflow_projectkpi  wpkpi on wp.id = wpkpi.project_id
            LEFT JOIN users_user as uu on wp.project_manager_id_id = uu.id
            left join workflow_projectstatus as wps on wp.id = wps.project_id
            LEFT JOIN workflow_projectmilestone wpm ON wp.id = wpm.project_id AND wpm.type = 3  -- Only type 3 milestones
        
            WHERE 
                pp.id IN {portfolio_ids_str}
                and wp.tenant_id_id = {tenant_id}
                AND wp.parent_id is not NULL
                -- and is_program is false
                {condition_statement}
                
            GROUP BY 
            pp.id, pp.title, wp.id, uu.first_name, wp.title, wp.start_date, wp.end_date, 
            wp.project_type, wp.spend_status, wp.scope_status, wp.delivery_status;
        """
        # print("debug pppppp ", query)
        return db_instance.retrieveSQLQueryOld(query)


    @staticmethod
    def fetchProjectsInfoForPortfolioV2(portfolio_ids, tenant_id, applicable_projects, archived=False, start_date=None, end_date=None):
        if len(applicable_projects) == 0:
            return []

        portfolio_ids_str = f"({', '.join(map(str, portfolio_ids))})"
        project_ids_str = f"({', '.join(map(str, applicable_projects))})"

        condition_statement = f'AND wp.archived_on IS NULL and wp.id in {project_ids_str}'
        if archived:
            condition_statement = "AND wp.archived_on IS NOT NULL"
            
        if start_date and end_date:
            condition_statement = f"AND wp.start_date >= '{start_date}' and end_date <= '{end_date}'"

        query = f"""
            SELECT 
                COALESCE(pp.id, 0) AS portfolio_id,
                COALESCE(pp.title, 'No Portfolio') AS portfolio_title,
                wp.id AS project_id,
                wp.title AS project_name,
                wp.description AS project_description,
                wp.objectives,
                wp.start_date,
                wp.end_date,
                wp.project_type,
                wp.spend_status,
                wp.scope_status,
                wp.delivery_status,
                wp.org_strategy_align,
                wp.total_external_spend as project_budget,
                wp.capex_budget as capex_budget,
                wp.opex_budget as opex_budget,
                wp.capex_pr_planned AS capex_pr_planned,
                wp.opex_pr_planned AS opex_pr_planned,
                wp.capex_actuals AS capex_actuals,
                wp.opex_actuals AS opex_actuals,
                uu.first_name AS project_manager_name,
                MAX(CASE WHEN atd.id IS NOT NULL THEN 'true' ELSE 'false' END) AS is_test_data,
                ARRAY_AGG(DISTINCT wpkpi.name) AS kpi_names,
                ARRAY_AGG(DISTINCT wps.comments) AS insights,
                JSON_AGG(
                    JSON_BUILD_OBJECT(
                        'milestone_name', wpm.name,
                        'target_date', wpm.target_date,
                        'planned_spend', wpm.planned_spend,
                        'actual_spend', wpm.actual_spend
                    )::TEXT
                ) FILTER (WHERE wpm.id IS NOT NULL) AS unique_milestones_text,
                JSON_AGG(
                    DISTINCT JSON_BUILD_OBJECT(
                        'milestone_name', wpm.name,
                        'target_date', wpm.target_date,
                        'planned_spend', wpm.planned_spend,
                        'actual_spend', wpm.actual_spend
                    )::TEXT
                )::JSON AS milestones,
                JSONB_AGG(
                    JSONB_BUILD_OBJECT(
                        'value', CASE
                            WHEN wps.value = 1 THEN 'on_track'
                            WHEN wps.value = 2 THEN 'at_risk'
                            WHEN wps.value = 3 THEN 'compromised'
                        END,
                        'created_date', wps.created_date,
                        'comments', wps.comments
                    )
                ) FILTER (WHERE wps.type = 1) AS scope_status_comments,
                JSONB_AGG(
                    JSONB_BUILD_OBJECT(
                        'value', CASE
                            WHEN wps.value = 1 THEN 'on_track'
                            WHEN wps.value = 2 THEN 'at_risk'
                            WHEN wps.value = 3 THEN 'compromised'
                        END,
                        'created_date', wps.created_date,
                        'comments', wps.comments
                    )
                ) FILTER (WHERE wps.type = 2) AS delivery_status_comments,
                JSONB_AGG(
                    JSONB_BUILD_OBJECT(
                        'value', CASE
                            WHEN wps.value = 1 THEN 'on_track'
                            WHEN wps.value = 2 THEN 'at_risk'
                            WHEN wps.value = 3 THEN 'compromised'
                        END,
                        'created_date', wps.created_date,
                        'comments', wps.comments
                    )
                ) FILTER (WHERE wps.type = 3) AS spend_status_comments
            FROM 
                workflow_project wp
            JOIN workflow_projectportfolio wpp ON wp.id = wpp.project_id
            JOIN projects_portfolio pp ON wpp.portfolio_id = pp.id
            LEFT JOIN workflow_projectkpi wpkpi ON wp.id = wpkpi.project_id
            LEFT JOIN users_user AS uu ON wp.project_manager_id_id = uu.id
            LEFT JOIN workflow_projectstatus AS wps ON wp.id = wps.project_id
            LEFT JOIN adminapis_test_data atd 
                ON atd.table_pk = wp.id 
                AND atd.table_name = 'project' 
                AND atd.tenant_id = wp.tenant_id_id
            LEFT JOIN workflow_projectmilestone wpm ON wp.id = wpm.project_id AND wpm.type = 3  -- Only type 3 milestones
            WHERE 
                pp.id IN {portfolio_ids_str}
                AND wp.tenant_id_id = {tenant_id}
                AND wp.parent_id IS NOT NULL
                {condition_statement}
            GROUP BY 
                pp.id, pp.title, wp.id, uu.first_name, wp.title, wp.start_date, wp.end_date, 
                wp.project_type, wp.spend_status, wp.scope_status, wp.delivery_status;
        """
        # print("debug pppppp ", query)
        return db_instance.retrieveSQLQueryOld(query)


    @staticmethod
    def fetchProjectsInfoForPortfolioV3(portfolio_ids, tenant_id, applicable_projects, archived=False):
        if len(applicable_projects) == 0 or len(portfolio_ids) == 0:
            return []

        portfolio_ids_str = f"({', '.join(map(str, portfolio_ids))})"
        project_ids_str = f"({', '.join(map(str, applicable_projects))})"

        condition_statement = f'AND wp.archived_on IS NULL AND wp.id IN {project_ids_str}'
        if archived:
            condition_statement = f'AND wp.archived_on IS NOT NULL'

        query = f"""
            WITH ProjectData AS (
                SELECT 
                    wp.id AS project_id,
                    wp.title AS project_name,
                    wp.description AS project_description,
                    wp.objectives,
                    wp.start_date,
                    wp.end_date,
                    wp.project_type,
                    wp.spend_status,
                    wp.scope_status,
                    wp.delivery_status,
                    wp.project_manager_id_id AS project_manager_id
                FROM workflow_project wp
                WHERE wp.tenant_id_id = {tenant_id}
                    AND wp.parent_id IS NOT NULL
                    {condition_statement}
            ),
            PortfolioData AS (
                SELECT 
                    wpp.project_id,
                    pp.id AS portfolio_id,
                    pp.title AS portfolio_title
                FROM workflow_projectportfolio wpp
                JOIN projects_portfolio pp ON wpp.portfolio_id = pp.id
                WHERE pp.id IN {portfolio_ids_str}
            ),
            ProjectManagerData AS (
                SELECT 
                    uu.id AS project_manager_id,
                    uu.first_name AS project_manager_name
                FROM users_user uu
            ),
            KPIData AS (
                SELECT 
                    wpkpi.project_id,
                    ARRAY_AGG(DISTINCT wpkpi.name) AS kpi_names
                FROM workflow_projectkpi wpkpi
                GROUP BY wpkpi.project_id
            ),
            StatusData AS (
                SELECT 
                    wps.project_id,
                    ARRAY_AGG(DISTINCT wps.comments) AS insights,
                    jsonb_agg(
                        jsonb_build_object(
                            'value', CASE
                                WHEN wps.value = 1 THEN 'on_track'
                                WHEN wps.value = 2 THEN 'at_risk'
                                WHEN wps.value = 3 THEN 'compromised'
                            END,
                            'created_date', wps.created_date,
                            'comments', wps.comments
                        )
                    ) FILTER (WHERE wps.type = 1) AS scope_status_comments,
                    jsonb_agg(
                        jsonb_build_object(
                            'value', CASE
                                WHEN wps.value = 1 THEN 'on_track'
                                WHEN wps.value = 2 THEN 'at_risk'
                                WHEN wps.value = 3 THEN 'compromised'
                            END,
                            'created_date', wps.created_date,
                            'comments', wps.comments
                        )
                    ) FILTER (WHERE wps.type = 2) AS delivery_status_comments,
                    jsonb_agg(
                        jsonb_build_object(
                            'value', CASE
                                WHEN wps.value = 1 THEN 'on_track'
                                WHEN wps.value = 2 THEN 'at_risk'
                                WHEN wps.value = 3 THEN 'compromised'
                            END,
                            'created_date', wps.created_date,
                            'comments', wps.comments
                        )
                    ) FILTER (WHERE wps.type = 3) AS spend_status_comments
                FROM workflow_projectstatus wps
                GROUP BY wps.project_id
            ),
            MilestoneData AS (
                SELECT 
                    wpm.project_id,
                    ARRAY_AGG(
                        jsonb_build_object(
                            'milestone_name', wpm.name,
                            'target_date', wpm.target_date,
                            'planned_spend', wpm.planned_spend,
                            'actual_spend', wpm.actual_spend
                        )::text
                    ) FILTER (WHERE wpm.id IS NOT NULL) AS unique_milestones_text,
                    jsonb_agg(
                        jsonb_build_object(
                            'milestone_name', wpm.name,
                            'target_date', wpm.target_date,
                            'planned_spend', wpm.planned_spend,
                            'actual_spend', wpm.actual_spend
                        )
                    ) FILTER (WHERE wpm.id IS NOT NULL) AS milestones
                FROM workflow_projectmilestone wpm
                WHERE wpm.type = 3
                GROUP BY wpm.project_id
            )
            SELECT 
                COALESCE(po.portfolio_id, 0) AS portfolio_id,
                COALESCE(po.portfolio_title, 'No Portfolio') AS portfolio_title,
                p.project_id,
                p.project_name,
                p.project_description,
                p.objectives,
                p.start_date,
                p.end_date,
                p.project_type,
                p.spend_status,
                p.scope_status,
                p.delivery_status,
                pm.project_manager_name,
                k.kpi_names,
                s.insights,
                s.scope_status_comments,
                s.delivery_status_comments,
                s.spend_status_comments,
                m.unique_milestones_text,
                m.milestones
            FROM ProjectData p
            LEFT JOIN PortfolioData po ON p.project_id = po.project_id
            LEFT JOIN ProjectManagerData pm ON p.project_manager_id = pm.project_manager_id
            LEFT JOIN KPIData k ON p.project_id = k.project_id
            LEFT JOIN StatusData s ON p.project_id = s.project_id
            LEFT JOIN MilestoneData m ON p.project_id = m.project_id
        """
        return db_instance.retrieveSQLQueryOld(query)



    @staticmethod
    def fetchfutureProjectsInfoForPortfolioV2(portfolio_ids, applicable_projects, tenant_id, start_date=None, end_date=None):
        portfolio_ids_str = f"({', '.join(map(str, portfolio_ids))})"
        # project_ids_str = f"({', '.join(map(str, applicable_projects))})"
        condition_statement = ''
        if start_date and end_date:
            condition_statement = f"AND wp.start_date >= '{start_date}' and end_date <= '{end_date}'"
        query = f"""
            select  
                COALESCE(pp.id, 0) AS portfolio_id,
                COALESCE(pp.title, 'No Portfolio') AS portfolio_title,
                rr.id as roadmap_id,
                rr.title as roadmap_title,
                rr.description,
                rr.objectives,
                rr.start_date,
                rr.end_date,
                rr.budget as planned_spend,
                rr.budget,
                ARRAY_AGG(rrkpi.name) AS kpi_names,
                rr.priority,
                rr.current_state,
                rr.org_strategy_align,
                rr.capex_budget,
                rr.opex_budget,
                rr.capex_pr_planned,
                rr.opex_pr_planned,
                rr.capex_actuals,
                rr.opex_actuals,
                MAX(CASE WHEN atd.id IS NOT NULL THEN 'true' ELSE 'false' END) AS is_test_data
            from roadmap_roadmap rr
            left join roadmap_roadmapportfolio rrp on rrp.roadmap_id = rr.id
            left join roadmap_roadmapkpi as rrkpi on rrkpi.roadmap_id = rr.id
            left join projects_portfolio pp ON rrp.portfolio_id = pp.id
            left join adminapis_test_data atd 
                on atd.table_pk = rr.id 
                and atd.table_name = 'roadmap' 
                and atd.tenant_id = rr.tenant_id
            where rr.tenant_id = {tenant_id} and pp.id IN {portfolio_ids_str}
            and rr.current_state in (0,1)
            {condition_statement}
            GROUP BY pp.id, pp.title, rr.id, rr.title, rr.start_date, rr.end_date;
        """
        return db_instance.retrieveSQLQueryOld(query)

    
    @staticmethod
    def fetchAllProjectsForTenant(tenant_id):
        query = f"""
            select id from workflow_project where tenant_id_id = {tenant_id}
        """
        data = db_instance.retrieveSQLQueryOld(query)
        arr = []
        for _d in data:
            arr.append(_d["id"])
        return arr

    @staticmethod
    def fetchStatusOfProjectsLastWeek(project_ids, tenant_id):
        if len(project_ids) == 0:
            return []

        project_ids_str = f"({', '.join(map(str, project_ids))})"
        query = f"""
            WITH ranked_status AS (
                SELECT
                    ps.project_id,
                    CASE
                        WHEN ps.type = 1 THEN 'scope_status'
                        WHEN ps.type = 2 THEN 'delivery_status'
                        WHEN ps.type = 3 THEN 'spend_status'
                    END AS type,
                    CASE
                        WHEN ps.value = 1 THEN 'on_track'
                        WHEN ps.value = 2 THEN 'at_risk'
                        WHEN ps.value = 3 THEN 'compromised'
                    END AS value,
                    ps.created_date,
                    ps.comments,
                    ps.actual_percentage,
                    ps.created_by_id,
                    ROW_NUMBER() OVER (PARTITION BY ps.project_id, ps.type ORDER BY ps.created_date DESC) AS rn
                FROM
                    public.workflow_projectstatus ps
                WHERE
                ps.created_date <= NOW() - INTERVAL '7 days'
            )
            SELECT
                wp.id as project_id,
                rs.type,
                rs.value,
                rs.created_date
            FROM
                ranked_status rs
            LEFT JOIN
                public.workflow_project wp
                ON rs.project_id = wp.id
            WHERE
                rs.rn = 1
                AND wp.tenant_id_id = {tenant_id}
                and wp.id in {project_ids_str}
            ORDER BY
                wp.id, rs.type;

        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchProjectOrgAnignment(project_ids, portfolio_ids):
        if (len(project_ids) == 0):
            return []
        project_ids_str = f"({', '.join(map(str, project_ids))})"
        portfolio_ids_str = f"({', '.join(map(str, portfolio_ids))})"
        query = f"""
        select wp.id, wp.title, wp.org_strategy_align , ARRAY_AGG(wpkpi.name) AS kpi_names
            from workflow_project wp
            join workflow_projectportfolio wpp on wp.id = wpp.project_id
            join projects_portfolio pp ON wpp.portfolio_id = pp.id
            left join workflow_projectkpi  wpkpi on wp.id = wpkpi.project_id
            
        where wp.id in {project_ids_str} and 
        pp.id IN {portfolio_ids_str} and 
        wp.archived_on IS NULL
        AND wp.parent_id is not NULL
        GROUP BY wp.id, wp.title, wp.org_strategy_align
        """
        return db_instance.retrieveSQLQueryOld(query)
    

    @staticmethod
    def fetchProjectsIdAndTItle(project_ids):
        # removed archived_on is null to access all project names
        if not project_ids:
            return
        project_ids_str = f"({', '.join(map(str, project_ids))})"
        query = f"""
            select wp.id, wp.title from workflow_project wp
        --  where wp.archived_on IS NULL
            where wp.parent_id is not NULL
            and wp.id in {project_ids_str}
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            return None

    @staticmethod
    def fetchProjectForCapacity(project_name):
        if project_name is not None:
            query = f"""select id,start_date,end_date from workflow_project where title = '{project_name}'"""
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            return None

    @staticmethod
    def fetchProjectsWithLastUpdates(project_ids, tenant_id):
        if len(project_ids) == 0:
            return []
        project_ids_str = f"({', '.join(map(str, project_ids))})"
        fetch_projects_query = f"""
            SELECT 
                wp.id, 
                wp.title,
                JSON_AGG(
                    JSON_BUILD_OBJECT(
                        'milestone_name', wpm.name,
                        'target_date', wpm.target_date,
                        'planned_spend', wpm.planned_spend,
                        'actual_spend', wpm.actual_spend,
                        'type', 
                        CASE
                            WHEN wpm.type = 1 THEN 'scope_milestone'
                            WHEN wpm.type = 2 THEN 'schedule_milestone'
                            WHEN wpm.type = 3 THEN 'spend_milestone'
                        END
                    )
                ) FILTER (
                    WHERE wpm.id IS NOT NULL 
                    AND (
                        wpm.target_date BETWEEN CURRENT_DATE - INTERVAL '7 days' AND CURRENT_DATE
                        OR wpm.target_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'
                    )
                ) AS milestones,
                JSON_AGG(
                    JSON_BUILD_OBJECT(
                        'risk_description', wpr.description,
                        'risk_impact', wpr.impact,
                        'risk_mitigation_strategy', wpr.mitigation,
                        'due_date', wpr.due_date
                    )
                ) FILTER (WHERE wpr.id IS NOT NULL) AS risk_and_mitigation
            FROM workflow_project wp
            LEFT JOIN workflow_projectmilestone wpm ON wp.id = wpm.project_id
            LEFT join workflow_projectrisk wpr on wp.id = wpr.project_id
            WHERE wp.archived_on IS NULL
            AND wp.parent_id IS NOT NULL
            AND wp.id IN {project_ids_str}
            GROUP BY wp.id;
        """
        projects = db_instance.retrieveSQLQueryOld(fetch_projects_query)

        fetch_updates_query = f"""
            WITH ranked_updates AS (
                SELECT
                    ps.project_id,
                    CASE
                        WHEN ps.type = 1 THEN 'scope_status'
                        WHEN ps.type = 2 THEN 'delivery_status'
                        WHEN ps.type = 3 THEN 'spend_status'
                    END AS type,
                    CASE
                        WHEN ps.value = 1 THEN 'on_track'
                        WHEN ps.value = 2 THEN 'at_risk'
                        WHEN ps.value = 3 THEN 'compromised'
                    END AS value,
                    ps.comments as comment,
                    ps.created_date,
                    ROW_NUMBER() OVER (PARTITION BY ps.project_id, ps.type ORDER BY ps.created_date DESC) AS rn
                FROM
                    public.workflow_projectstatus ps
                WHERE
                    ps.project_id IN {project_ids_str}
            )
            SELECT
                project_id,
                type,
                value,
                comment,
                created_date
            FROM
                ranked_updates
            WHERE
                rn = 1;
        """
        updates = db_instance.retrieveSQLQueryOld(fetch_updates_query)

        project_data = {}

        # Process project details
        for project in projects:
            # print("debug -----------", project)
            project_id = project['id']
            # Separate milestones by type
            milestones = project.get('milestones', [])
            if milestones is None:
                milestones = []

            risk_and_mitigation = project.get('risk_and_mitigation', [])
            if risk_and_mitigation is None:
                risk_and_mitigation = []

            scope_milestones = []
            schedule_milestones = []
            spend_milestones = []

            for milestone in milestones:
                if milestone['type'] == 'scope_milestone':
                    scope_milestones.append(milestone)
                elif milestone['type'] == 'schedule_milestone':
                    schedule_milestones.append(milestone)
                elif milestone['type'] == 'spend_milestone':
                    spend_milestones.append(milestone)

            project_data[project_id] = {
                'project_id': project_id,
                'project_title': project['title'],
                'last_updates': {
                    'scope_status': None,
                    'delivery_status': None,
                    'spend_status': None
                },
                'latest_update_time': None,
                'milestones': {
                    'scope_milestones': scope_milestones,
                    'schedule_milestones': schedule_milestones,
                    'spend_milestones': spend_milestones
                },
                'risk_and_mitigation': risk_and_mitigation
            }

        for update in updates:
            project_id = update['project_id']
            update_type = update['type']
            update_comment = update['comment']
            if project_id in project_data:
                project_data[project_id]['last_updates'][update_type] = {
                    'value': update['value'],
                    'update_comment': update_comment,
                    'updated_time': update['created_date']
                }

                # Update the latest update time
                latest_time = project_data[project_id]['latest_update_time']
                update_time = update['created_date']
                if not latest_time or update_time > latest_time:
                    project_data[project_id]['latest_update_time'] = update_time

        # Convert the final dictionary to JSON
        return list(project_data.values())

    @staticmethod
    def fetchAllProjectsForProgram(program_id, tenant_id):
        query = f"""
            select 
                wp.id, wp.title,
                pp.id as program_id,
                pp.name
                from workflow_project as wp 
                left join program_program pp on pp.id = wp.program_id
                where 
                wp.program_id is not null and
                wp.tenant_id_id = {tenant_id} and 
                pp.id = {program_id}
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchProjectsRisks(project_ids):
        result = []
        for proj in project_ids:
            query = f"""
                SELECT 
                    wp.id as project_id,
                    wp.title as project_title,
                    wpr.id as risk_id,
                    wpr.description as risk_description,
                    wpr.impact as risk_impact,
                    wpr.mitigation as risk_mitigation,
                    wpr.due_date as risk_due_date
                    FROM public.workflow_projectrisk as wpr
                    left join workflow_project as wp on wpr.project_id = wp.id
                    where wp.id = {proj}
            """
            res = db_instance.retrieveSQLQueryOld(query)
            result.append(res)

        return result
    
    
    @staticmethod
    def fetchProjectsRisksV2(project_ids):
        project_ids_str = f"({', '.join(map(str, project_ids))})"
        riskStatusMapping = {
            'Active': 1,
            'Resolved': 2,
            'Monitoring': 3,
            'Escalated': 4,
            'Mitigated': 5,
            'Closed': 6,
        }

        query = f"""
            SELECT 
                wpr.id,
                wpr.description,
                wpr.impact,
                wpr.mitigation,
                wpr.due_date,
                CASE wpr.status_value
                        WHEN {riskStatusMapping['Active']} THEN 'Active'
                        WHEN {riskStatusMapping['Resolved']} THEN 'Resolved'
                        WHEN {riskStatusMapping['Monitoring']} THEN 'Monitoring'
                        WHEN {riskStatusMapping['Escalated']} THEN 'Escalated'
                        WHEN {riskStatusMapping['Mitigated']} THEN 'Mitigated'
                        WHEN {riskStatusMapping['Closed']} THEN 'Closed'
                        ELSE 'Unknown'
                END AS status  
            from workflow_projectrisk as wpr
            where wpr.project_id in {project_ids_str} 
        """
        return db_instance.retrieveSQLQueryOld(query)
   

    @staticmethod
    def fetch_project_details(project_id):
        """_summary_

        Args:
            tenant_id (_type_): _description_
            project_id (_type_): _description_
        """
        query = f"""
            SELECT
                MAX(wp.title) as TITLE,
                MAX(wp.description) as project_description,
                MAX(wp.start_date) as PROJECT_START_DATE,
                MAX(wp.end_date) as PROJECT_END_DATE,
                MAX(wp.project_location) as PROJECT_LOCATION,
                MAX(wp.project_type) as PROJECT_TYPE,
                MAX(wp.sdlc_method) as SDLC_METHOD,
                MAX(wpm.planned_spend) as PROJECT_BUDGET,
                MAX(tp.company_name) as PROVIDER_NAME,
                MAX(wp.technology_stack) as TECH_STACK,
                ARRAY_AGG(DISTINCT wpkpi.name) as KEY_RESULTS,
                ARRAY_AGG(DISTINCT jsonb_build_object(
                        'team_id', wpm.team_id,
                        'actual_spend', wpm.actual_spend ,
                        'planned_spend', wpm.planned_spend,
                        'name', wpm.name,
                        'target_date', wpm.target_date
                )) as MILESTONES,
                ARRAY_AGG(DISTINCT jsonb_build_object(
                    'role', wpts.member_role,
                    'member_name', wpts.member_name,
                    'average_rate_per_hour', wpts.average_spend,
                    'contribution_percentage', wpts.member_utilization,
                    'member_location', wpts.location,
                    'team_type', CASE WHEN wpts.is_external = false then 'Internal Team' else 'External Team' end
                )) as TEAMSDATA
            FROM
                    workflow_project as wp
            LEFT JOIN
                    workflow_projectkpi as wpkpi on wp.id=wpkpi.project_id
            LEFT JOIN
                    workflow_projectmilestone as wpm on wp.id=wpm.project_id
            LEFT JOIN
                    workflow_projectprovider as wpprov on wp.id=wpprov.project_id
            LEFT JOIN
                    tenant_provider as tp on tp.id = wpprov.provider_id
            LEFT JOIN
                    workflow_projectportfolio as wpport on wp.id=wpport.project_id
            LEFT JOIN
                    workflow_projectstatus as wps on wp.id=wps.project_id
            LEFT JOIN
                    projects_portfolio as pp on wpport.portfolio_id = pp.id
            LEFT JOIN
                    users_user as uu on wp.project_manager_id_id = uu.id
            LEFT JOIN
                    users_user as uuu on uuu.id = wps.created_by_id
            LEFT JOIN
                    roadmap_roadmap as rr on rr.id = wp.roadmap_id
            LEFT JOIN
                    workflow_projectteam as wpt on wp.id=wpt.project_id
            LEFT JOIN
                    workflow_projectteamsplit as wpts on wp.id=wpts.project_id
            WHERE

                    wp.id = {project_id}
                    AND wp.archived_on IS NULL
                    AND wp.parent_id is not NULL
            GROUP BY
                    wp.id
        """
        # wp.tenant_id_id = {tenant_id}
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetch_project_details_for_service_assurance_old(project_id):
        """_summary_

        Args:
            tenant_id (_type_): _description_
            project_id (_type_): _description_
        """
        query = f"""
            SELECT
                MAX(wp.title) as TITLE,
                MAX(wp.description) as project_description,
                MAX(wp.objectives) as project_objectives,
                MAX(wp.start_date) as PROJECT_START_DATE,
                MAX(wp.end_date) as PROJECT_END_DATE,
                MAX(wpm.planned_spend) as PROJECT_BUDGET,
                MAX(wp.technology_stack) as TECH_STACK,
                ARRAY_AGG(DISTINCT wpkpi.name) as KEY_RESULTS,
                MAX(pp.title) AS portfolio_title,
                ARRAY_AGG(DISTINCT jsonb_build_object(
                        'milestone_id', wpm.id,
                        'name', wpm.name,
                        'target_date', wpm.target_date,
                        'team_id', wpm.team_id,
                        'actual_spend', wpm.actual_spend ,
                        'planned_spend', wpm.planned_spend
                )) as MILESTONES
            FROM
                    workflow_project as wp
            LEFT JOIN
                    workflow_projectkpi as wpkpi on wp.id=wpkpi.project_id
            LEFT JOIN
                    workflow_projectmilestone as wpm on wp.id=wpm.project_id
            LEFT JOIN
                    workflow_projectprovider as wpprov on wp.id=wpprov.project_id
            LEFT JOIN
                    tenant_provider as tp on tp.id = wpprov.provider_id
            LEFT JOIN
                    workflow_projectportfolio as wpport on wp.id=wpport.project_id
            LEFT JOIN
                    workflow_projectstatus as wps on wp.id=wps.project_id
            LEFT JOIN
                    projects_portfolio as pp on wpport.portfolio_id = pp.id
            WHERE
                    wp.id = {project_id}
            GROUP BY
                    wp.id
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetch_project_details_for_service_assurance(project_id):
        query = f"""
            SELECT
                wp.title AS TITLE,
                wp.description AS project_description,
                wp.objectives,
                wp.start_date AS PROJECT_START_DATE,
                wp.end_date AS PROJECT_END_DATE,
                -- wp.state AS CURRENT_PROJECT_STATE,
                wp.key_accomplishments AS KEY_ACCOMPLISHMENTS,
                MAX(wpm.planned_spend) AS PROJECT_BUDGET,
                wp.technology_stack AS TECH_STACK,
                ARRAY_AGG(DISTINCT wpkpi.name) AS KEY_RESULTS,
                pp.title AS portfolio_title,
                (
                    SELECT JSON_AGG(
                                CAST(JSON_BUILD_OBJECT(
                                    'risk_description', wpr_sub.description,
                                    'risk_impact', wpr_sub.impact,
                                    'risk_mitigation_strategy', wpr_sub.mitigation,
                                    'due_date', wpr_sub.due_date
                                ) AS TEXT)
                        )
                    FROM workflow_projectrisk wpr_sub
                    WHERE wpr_sub.project_id = wp.id
                ) AS risk_and_mitigation,
                ARRAY_AGG(DISTINCT jsonb_build_object(
                        'milestone_id', wpm.id,
                        'name', wpm.name,
                        'target_date', wpm.target_date,
                        'team_id', wpm.team_id,
                        'actual_spend', wpm.actual_spend,
                        'planned_spend', wpm.planned_spend
                )) AS MILESTONES
            FROM
                workflow_project AS wp
            LEFT JOIN
                workflow_projectkpi AS wpkpi ON wp.id = wpkpi.project_id
            LEFT JOIN
                workflow_projectmilestone AS wpm ON wp.id = wpm.project_id
            LEFT JOIN
                workflow_projectportfolio AS wpport ON wp.id = wpport.project_id
            LEFT JOIN
                projects_portfolio AS pp ON wpport.portfolio_id = pp.id
            WHERE
                wp.id = {project_id}
                AND wp.archived_on IS NULL
            --  AND wp.parent_id IS NOT NULL
            GROUP BY
                wp.id, pp.title;
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetch_project_details_for_knowledge_layer(project_id):
        query = f"""
            SELECT
                wp.start_date AS PROJECT_START_DATE,
                wp.end_date AS PROJECT_END_DATE,
                MAX(wpm.planned_spend) AS PROJECT_BUDGET,
                wp.technology_stack AS TECH_STACK,
                ARRAY_AGG(DISTINCT wpkpi.name) AS KEY_RESULTS,
                pp.title AS portfolio_title,
                (
                    SELECT JSON_AGG(
                                CAST(JSON_BUILD_OBJECT(
                                    'risk_description', wpr_sub.description,
                                    'risk_impact', wpr_sub.impact,
                                    'risk_mitigation_strategy', wpr_sub.mitigation,
                                    'due_date', wpr_sub.due_date
                                ) AS TEXT)
                        )
                    FROM workflow_projectrisk wpr_sub
                    WHERE wpr_sub.project_id = wp.id
                ) AS risk_and_mitigation,
                ARRAY_AGG(DISTINCT jsonb_build_object(
                        'milestone_id', wpm.id,
                        'name', wpm.name,
                        'target_date', wpm.target_date,
                        'team_id', wpm.team_id,
                        'actual_spend', wpm.actual_spend,
                        'planned_spend', wpm.planned_spend
                )) AS MILESTONES
            FROM
                workflow_project AS wp
            LEFT JOIN
                workflow_projectkpi AS wpkpi ON wp.id = wpkpi.project_id
            LEFT JOIN
                workflow_projectmilestone AS wpm ON wp.id = wpm.project_id
            LEFT JOIN
                workflow_projectportfolio AS wpport ON wp.id = wpport.project_id
            LEFT JOIN
                projects_portfolio AS pp ON wpport.portfolio_id = pp.id
            WHERE
                wp.id = {project_id}
                AND wp.archived_on IS NULL
                AND wp.parent_id IS NOT NULL
            GROUP BY
                wp.id, pp.title;
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchProjectStatuses(project_id):
        query = f"""
            SELECT
                ps.id,
                ps.project_id,
                CASE
                    WHEN ps.type = 1 THEN 'scope_status'
                    WHEN ps.type = 2 THEN 'delivery_status'
                    WHEN ps.type = 3 THEN 'spend_status'
                END AS type,
                CASE
                    WHEN ps.value = 1 THEN 'on_track'
                    WHEN ps.value = 2 THEN 'at_risk'
                    WHEN ps.value = 3 THEN 'compromised'
                END AS value,
                ps.comments as comment,
                ps.created_date
            FROM
                public.workflow_projectstatus ps
            WHERE
                ps.project_id = {project_id}
            order by created_date desc
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchProjectStatusSummary(project_id):
        query = f"""
            SELECT
                CASE
                    WHEN ps.type = 1 THEN 'scope_status'
                    WHEN ps.type = 2 THEN 'delivery_status'
                    WHEN ps.type = 3 THEN 'spend_status'
                END AS type,
                CASE
                    WHEN ps.value = 1 THEN 'on_track'
                    WHEN ps.value = 2 THEN 'at_risk'
                    WHEN ps.value = 3 THEN 'compromised'
                END AS value,
                COUNT(*) AS count
            FROM
                public.workflow_projectstatus ps
            WHERE
                ps.project_id = {project_id}
            GROUP BY type, value
            ORDER BY type, value;
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchProjectLatestStatusUpdate(project_id):
        query = f"""
        WITH ranked_statuses AS (
            SELECT
                ps.project_id,
                CASE
                    WHEN ps.type = 1 THEN 'scope'
                    WHEN ps.type = 2 THEN 'delivery'
                    WHEN ps.type = 3 THEN 'spend'
                END AS type,
                CASE
                    WHEN ps.value = 1 THEN 'green'
                    WHEN ps.value = 2 THEN 'amber'
                    WHEN ps.value = 3 THEN 'red'
                END AS value,
                ps.comments AS comment,
                ps.created_date,
                ROW_NUMBER() OVER (
                    PARTITION BY ps.project_id, ps.type
                    ORDER BY ps.created_date DESC
                ) AS rn
            FROM
                public.workflow_projectstatus ps
            where ps.project_id = {project_id} 
        )
        SELECT
            project_id,
            type,
            value,
            comment,
            created_date
        FROM
            ranked_statuses
        WHERE
            rn = 1;
        """
        data = db_instance.retrieveSQLQueryOld(query)
        project_status = {
            "scope": "unknown",
            "delivery": "unknown",
            "spend": "unknown"
        }

        for record in data:
            status_type = record["type"]
            status_value = record["value"]
            project_status[status_type] = status_value

        return project_status

    @staticmethod
    def fetchProjectLatestStatusUpdateV2(project_id):
        query = f"""
        WITH ranked_statuses AS (
            SELECT
                ps.project_id,
                CASE
                    WHEN ps.type = 1 THEN 'scope'
                    WHEN ps.type = 2 THEN 'delivery'
                    WHEN ps.type = 3 THEN 'spend'
                END AS type,
                CASE
                    WHEN ps.value = 1 THEN 'green'
                    WHEN ps.value = 2 THEN 'amber'
                    WHEN ps.value = 3 THEN 'red'
                END AS value,
                ps.comments AS comment,
                ps.created_date,
                ROW_NUMBER() OVER (
                    PARTITION BY ps.project_id, ps.type
                    ORDER BY ps.created_date DESC
                ) AS rn
            FROM
                public.workflow_projectstatus ps
            where ps.project_id = {project_id} 
        )
        SELECT
            project_id,
            type,
            value,
            comment,
            created_date
        FROM
            ranked_statuses
        WHERE
            rn = 1;
        """
        data = db_instance.retrieveSQLQueryOld(query)
        project_status = {
            "scope": "unknown",
            "delivery": "unknown",
            "spend": "unknown",
            "scope_comment": "",
            "spend_comment": "",
            "delivery_comment": "",
            "project_id": project_id,
            "latest_update_date": None
        }
        latest_update_date = None

        for record in data:
            status_type = record["type"]
            status_value = record["value"]
            comment = record["comment"]
            project_status[status_type] = status_value
            project_status[f"{status_type}_comment"] = comment
            if latest_update_date is None or record["created_date"] > latest_update_date:
                latest_update_date = record["created_date"]

        project_status["latest_update_date"] = latest_update_date

        return project_status


    @staticmethod
    def fetchProjectLatestStatusUpdateV3(project_id):
        query = f"""
        WITH ranked_statuses AS (
            SELECT
                ps.project_id,
                CASE
                    WHEN ps.type = 1 THEN 'scope'
                    WHEN ps.type = 2 THEN 'schedule'
                    WHEN ps.type = 3 THEN 'spend'
                END AS type,
                CASE
                    WHEN ps.value = 1 THEN 'green'
                    WHEN ps.value = 2 THEN 'amber'
                    WHEN ps.value = 3 THEN 'red'
                END AS value,
                ps.comments AS comment,
                ps.created_date,
                ROW_NUMBER() OVER (
                    PARTITION BY ps.project_id, ps.type
                    ORDER BY ps.created_date DESC
                ) AS rn
            FROM
                public.workflow_projectstatus ps
            where ps.project_id = {project_id} 
        )
        SELECT
            project_id,
            type,
            value,
            comment,
            created_date
        FROM
            ranked_statuses
        WHERE
            rn = 1;
        """
        data = db_instance.retrieveSQLQueryOld(query)
        project_status = {
            "scope": "unknown",
            "delivery": "unknown",
            "spend": "unknown",
            "scope_comment": "",
            "spend_comment": "",
            "delivery_comment": "",
            "project_id": project_id,
            "latest_update_date": None
        }
        latest_update_date = None

        for record in data:
            status_type = record["type"]
            status_value = record["value"]
            comment = record["comment"]
            project_status[status_type] = status_value
            project_status[f"{status_type}_comment"] = comment
            if latest_update_date is None or record["created_date"] > latest_update_date:
                latest_update_date = record["created_date"]

        project_status["latest_update_date"] = latest_update_date

        return project_status


    @staticmethod
    def fetchProjectKeyResultInfo(project_id, key_result_id):
        query = f"""
            select id as key_result_id, name as key_result, baseline_value from workflow_projectkpi
            where project_id = {project_id} and id = {key_result_id}
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchAllRetroProjects(tenant_id):
        query = f"""
            select project_id from workflow_projectretro
            where tenant_id = {tenant_id}
        """
        result = db_instance.retrieveSQLQueryOld(query)
        project_ids = [row["project_id"] for row in result] if result else []
        return project_ids

    @staticmethod
    def fetchValueRealizationProjects(tenant_id):
        query = f"""
            select project_id from workflow_projectvaluerealization
            where tenant_id = {tenant_id}
        """
        result = db_instance.retrieveSQLQueryOld(query)
        project_ids = [row["project_id"] for row in result] if result else []
        return project_ids

    @staticmethod
    def getProjectRetroInsightsV2(project_ids: list[int], tenant_id: int):
        # project_ids_str = ", ".join(map(str, project_ids))  # Format project IDs for SQL query

        query = f"""
            SELECT 
                MAX(wp.title) AS project_title,
                MAX(wp.objectives) AS project_objectives,
                CONCAT(
                    'Insights: ', 
                   COALESCE(
                        STRING_AGG(insight_obj->>'data', ' || '), 'N/A'
                    ),'.',
                    'Scope: ', COALESCE(wpr.detailed_analysis->>'project_scope_summary', 'N/A'), '. ',
                    'Spend: ', COALESCE(wpr.detailed_analysis->>'project_spend_summary', 'N/A'), '. ',
                    'Schedule: ', COALESCE(wpr.detailed_analysis->>'project_schedule_summary', 'N/A'), '.'
                ) AS retrospective_summary,

                MAX(wp.provider_id_id) AS provider_id,
                MAX(pp.title) AS portfolio_title,
                MAX(pp.description) AS portfolio_description,

                wpr.things_to_keep_doing,
                wpr.areas_for_improvement

            FROM 
                workflow_projectretro AS wpr
            LEFT JOIN workflow_project AS wp 
                ON wpr.project_id = wp.id
            LEFT JOIN workflow_projectportfolio AS wpport 
                ON wp.id = wpport.project_id
            LEFT JOIN projects_portfolio AS pp 
                ON wpport.portfolio_id = pp.id
            LEFT JOIN LATERAL jsonb_array_elements(wpr.story->'insights') AS insight_obj ON TRUE  

            WHERE 
                wpr.tenant_id = {tenant_id}
            AND 
                wpr.project_id IN {tuple(project_ids)}
            GROUP BY 
                wpr.id, 
                wpr.things_to_keep_doing, 
                wpr.areas_for_improvement;
        """

        try:
            return query
        except Exception as e:
            return None

    @staticmethod
    def getProjectValueRealizations(project_ids: list[int], tenant_id: int):
        query2 = f"""
            WITH parsed_json AS (
            SELECT 
                wpr.id AS value_realization_id,
                wpr.project_id,
                (elem ->> 'id')::bigint AS kpi_id,
                elem ->> 'title' AS key_result,
                elem ->> 'baseline_value' AS baseline_value,
                elem ->> 'target_value' AS planned_value,
                elem ->> 'actual_value' AS achieved_value,
                elem -> 'key_learnings' AS key_learnings
            FROM 
                workflow_projectvaluerealization wpr,
                jsonb_array_elements(wpr.key_result_analysis::jsonb) elem
            WHERE 
                wpr.tenant_id = {tenant_id}
                AND wpr.project_id IN {tuple(project_ids)}
                AND elem ->> 'id' IS NOT NULL
            )

            SELECT 
                p.title AS project_title,
                p.objectives AS project_objectives,
                kpi.name AS kpi_name,
                pj.key_result,
                pj.baseline_value::numeric AS baseline_value,
                pj.planned_value::numeric AS planned_value,
                pj.achieved_value::numeric AS achieved_value,
                pj.key_learnings::jsonb AS key_learnings,
                port.title AS portfolio_title

            FROM  parsed_json pj

            LEFT JOIN 
                workflow_projectkpi kpi ON kpi.id = pj.kpi_id
            LEFT JOIN 
                workflow_project p ON pj.project_id = p.id
            LEFT JOIN 
                workflow_projectportfolio pport ON p.id = pport.project_id
            LEFT JOIN 
                projects_portfolio port ON pport.portfolio_id = port.id
          """

        # query3 = f"""

        #     WITH parsed_json AS (
        #     SELECT
        #         wpr.id AS value_realization_id,
        #         wpr.project_id,
        #         (elem ->> 'id')::bigint AS kpi_id,
        #         elem ->> 'title' AS key_result,
        #         elem ->> 'baseline_value' AS baseline_value,
        #         elem ->> 'target_value' AS planned_value,
        #         elem ->> 'actual_value' AS achieved_value,
        #         elem -> 'key_learnings' AS key_learnings
        #     FROM
        #         workflow_projectvaluerealization wpr,
        #         jsonb_array_elements(wpr.key_result_analysis::jsonb) elem
        #     WHERE
        #         wpr.tenant_id = {tenant_id}
        #         AND wpr.project_id IN {tuple(project_ids)}
        #         AND elem ->> 'id' IS NOT NULL
        #     )
        #     SELECT
        #         p.title AS project_title,
        #         port.title AS portfolio_title,
        #         STRING_AGG(pj.key_result, ' | ') AS key_results,
        #         STRING_AGG(pj.baseline_value, ' | ') AS baseline_values,
        #         STRING_AGG(COALESCE(pj.planned_value, 'None'), ' | ') AS planned_values,
        #         STRING_AGG(COALESCE(pj.achieved_value, 'None'), ' | ') AS achieved_values,
        #         STRING_AGG(pj.key_learnings::TEXT, ' | ') AS key_learnings
        #     FROM
        #         parsed_json pj
        #     LEFT JOIN
        #         workflow_projectkpi kpi ON kpi.id = pj.kpi_id
        #     LEFT JOIN
        #         workflow_project p ON pj.project_id = p.id
        #     LEFT JOIN
        #         workflow_projectportfolio pport ON p.id = pport.project_id
        #     LEFT JOIN
        #         projects_portfolio port ON pport.portfolio_id = port.id
        #     GROUP BY
        #         p.title,port.title;

        # """
        try:
            return query2
        except Exception as e:
            return None

    @staticmethod
    def fetchBasicInfoForServiceAssuranceNotifyAgent(project_id):
        query = f"""
        select 
            wp.id as project_id, 
            wp.title as project_title,
            wp.description as project_description,
            pp.title as portfolio_title,
            wp.objectives as project_objectives,
            wp.technology_stack
            from workflow_project as wp
            join projects_portfolio pp ON wp.portfolio_id_id = pp.id
            where wp.id = {project_id}
        """

        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchBasicInfoForKnwoeldgeLayer(project_id):
        query = f"""
        select 
            wp.id as project_id, 
            wp.description as project_description,
            pp.title as portfolio_title,
            wp.objectives as project_objectives,
            wp.technology_stack
            from workflow_project as wp
            join projects_portfolio pp ON wp.portfolio_id_id = pp.id
            where wp.id = {project_id}
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def findProjectByPmForTenant(tenant_id):
        query = f"""
            WITH project_cte AS (
                SELECT 
                    wp.id AS project_id, 
                    wp.project_manager_id_id AS project_manager_id
                FROM workflow_project AS wp
                LEFT JOIN users_user AS uu 
                    ON wp.project_manager_id_id = uu.id
                WHERE wp.tenant_id_id = {tenant_id}
                AND wp.archived_on IS NULL
                AND wp.parent_id IS NOT NULL
            )
            SELECT 
                project_manager_id, 
                COUNT(project_id) AS total_projects,
                ARRAY_AGG(project_id) AS project_ids
            FROM project_cte
            GROUP BY project_manager_id;
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def findProjectMilestonesAndRisk(project_ids):
        project_ids_str = f"({', '.join(map(str, project_ids))})"
        query = f"""
        
        WITH project_cte AS (
            SELECT 
                wp.id AS project_id,
                wp.title as project_title,
                (
                    SELECT JSON_AGG(
                                CAST(JSON_BUILD_OBJECT(
                                    'risk_description', wpr_sub.description,
                                    -- 'risk_impact', wpr_sub.impact,
                                    'due_date', wpr_sub.due_date
                                ) AS TEXT)
                        )
                    FROM workflow_projectrisk wpr_sub
                    WHERE wpr_sub.project_id = wp.id
                ) AS risk_and_mitigation,
                (
                    SELECT JSON_AGG(
                                CAST(JSON_BUILD_OBJECT(
                                    'milestone_name', wpm_sub.name,
                                    'target_date', wpm_sub.target_date,
                                    'actual_spend', wpm_sub.actual_spend,
                                    'planned_spend', wpm_sub.planned_spend
                                ) AS TEXT)
                        )
                    FROM workflow_projectmilestone wpm_sub
                    WHERE wpm_sub.project_id = wp.id
                ) AS milestones
            FROM workflow_project AS wp
            where wp.id in {project_ids_str}
        )
        SELECT * FROM project_cte;
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def getCapacityPlannerResources(tenant_id: int):
        """
        Combined the logic for fetching both internal and provider resources
        """
        query = f"""
            SELECT 
                cr.id,
                cr.first_name as first_name,
				cr.last_name as last_name,
                cr.role,
                CONCAT(
                    cr.experience_years, ' years of experience as a ', 
                    cr.role, '. ', 
                    cr.experience
                ) AS description,
                CASE 
                    WHEN EXISTS (
                        SELECT 1 
                        FROM capacity_resource_timeline crt2 
                        WHERE crt2.resource_id = cr.id 
                        AND CURRENT_DATE BETWEEN crt2.start_date AND crt2.end_date
                    ) THEN 'Busy' 
                    ELSE 'Available' 
                END AS availability,
                cr.is_active AS active,  
                cr.allocation || '%' AS allocation,
                cr.skills AS skills,
                cr.primary_skill,
                (
                    SELECT COALESCE(
                        json_agg(
                            json_build_object(
                                'leader_first_name', leader_cr.first_name,
                                'leader_last_name', leader_cr.last_name,
                                'org_team', crg.name,
                                'primary_skill', crg.primary_skill
                            )
                        )
                    )
                    FROM public.capacity_resource_group crg
                    INNER JOIN capacity_resource_group_mapping crgm 
                        ON crg.id = crgm.group_id
                        AND crgm.resource_id = cr.id
                    LEFT JOIN capacity_resource leader_cr 
                        ON crg.leader_id = leader_cr.id
                        AND crg.tenant_id = {tenant_id}
                    WHERE crg.tenant_id = {tenant_id}
                ) AS org_team,
                CASE 
                    WHEN cr.is_external THEN 'true' 
                    ELSE 'false' 
                END AS external,
                (
                    SELECT COALESCE(
                        json_agg(
                            json_build_object(
                                'name', crt.project_name,
                                'project_allocation', crt.allocation,
                                'is_current_project', 
                                CASE 
                                    WHEN CURRENT_DATE BETWEEN crt.start_date AND crt.end_date 
                                    THEN 'true' 
                                    ELSE 'false' 
                                END,
                                'start_date', crt.start_date,
                                'end_date', crt.end_date
                            )
                        ) FILTER (WHERE crt.trmeric_project_id IS NOT NULL),
                        '[]'
                    )
                    FROM capacity_resource_timeline crt
                    WHERE crt.resource_id = cr.id
                ) AS project_timeline,
                cep.id AS external_provider_id,
                cep.company_name AS external_provider_name,
                cep.company_website AS external_provider_website,
                tp.id AS tenant_provider_id,
                tp.company_name AS tenant_provider_name,
                tp.company_website AS tenant_provider_website
            FROM capacity_resource cr
            LEFT JOIN capacity_external_providers cep ON cr.external_provider_id = cep.id
            LEFT JOIN tenant_provider tp ON cr.trmeric_provider_tenant_id = tp.id
            WHERE cr.tenant_id = {tenant_id}
            ORDER BY cr.id;
        """
        
        all_resources = db_instance.retrieveSQLQueryOld(query)
        print("--debug getCapacityPlannerResources queryall resoureces----", all_resources[:2])
        
        internal_resources = []
        provider_resources = []

        for resource in all_resources:
            resource_data = {
                "id": resource["id"],
                "name": resource["first_name"] + " " + resource["last_name"],
                "role": resource["role"],
                "description": resource["description"],
                "availability": resource["availability"],
                "is_active": resource["active"],
                "allocation": resource["allocation"],
                "primary_skill": resource["primary_skill"],
                "skills": resource['skills'],
                "external": resource["external"],
                "project_timeline": resource["project_timeline"],
                "organization_team": resource["org_team"]
            }

            if resource["tenant_provider_id"] is not None or resource["external_provider_id"] is not None:
                # print("--debug provider ids: ", resource["external_provider_id"], " ", resource["tenant_provider_id"])
                provider_resource_data = {
                    **resource_data,
                    "external_provider_name": resource["external_provider_name"],
                    "external_provider_website": resource["external_provider_website"],
                    "tenant_provider_name": resource["tenant_provider_name"],
                    "tenant_provider_website": resource["tenant_provider_website"],
                }
                provider_resources.append(provider_resource_data)
            else:
                internal_resources.append(resource_data)

        # print("--debug resources------", internal_resources[:4],"\n", provider_resources[:4])

        result = {
            "internal_resources": internal_resources,
            "provider_resources": provider_resources,
        }
        return result

    @staticmethod
    def getRetroAnalysisForProject(project_id):
        query = f"""
            select * from workflow_projectretro where project_id = {project_id}
        """
        result = db_instance.retrieveSQLQueryOld(query)
        if len(result) > 0:
            return result[0]["story"]
        else:
            return None

    @staticmethod
    def fetchProjectTeamDetailsV2(project_id):

        fetch_team_query = f"""
            SELECT 
                pts.project_id,
                pts.is_external,
                pts.location,
                pts.team_members,
                CASE 
                    WHEN pts.spend_type = 1 THEN 'Internal'
                    WHEN pts.spend_type = 2 THEN 'External'
                    ELSE 'Unknown'
                END AS spend_type,
                pts.average_spend,
                pts.member_role,
                pts.member_utilization
            FROM 
                public.workflow_projectteamsplit pts
            WHERE 
                pts.project_id = {project_id};
        """
        return db_instance.retrieveSQLQueryOld(fetch_team_query)

    @staticmethod
    def fetchProjectsDetailsForTenantGroupedByPortfolio(tenant_id):
        query = f"""
            WITH risk_data AS (
                SELECT 
                    wpr.project_id,
                    JSONB_AGG(JSONB_BUILD_OBJECT(
                        'risk_description', wpr.description,
                        'due_date', wpr.due_date
                    )) AS risks
                FROM workflow_projectrisk wpr
                GROUP BY wpr.project_id
            ),
            team_data AS (
                SELECT 
                    wpt.project_id,
                    COUNT(DISTINCT wpt.member_email) AS total_members,
                    AVG(wpt.member_utilization) AS avg_utilization
                FROM workflow_projectteamsplit wpt
                GROUP BY wpt.project_id
            ),
            milestone_data AS (
                SELECT 
                    wpm.project_id,
                    SUM(wpm.planned_spend) AS project_budget,
                    SUM(wpm.actual_spend) AS actual_spend
                FROM workflow_projectmilestone wpm
                GROUP BY wpm.project_id
            ),
            kpi_data AS (
                SELECT 
                    wpkpi.project_id,
                    ARRAY_AGG(DISTINCT wpkpi.name) AS key_results
                FROM workflow_projectkpi wpkpi
                GROUP BY wpkpi.project_id
            )
            SELECT 
                pp.id AS portfolio_id,
                pp.title AS portfolio_title,
                JSONB_AGG(JSONB_BUILD_OBJECT(
                    'type', 'project',
                    'title', wp.title,
                    'start_date', wp.start_date,
                    'end_date', wp.end_date,
                    'org_alignment', wp.org_strategy_align,
                    'budget', COALESCE(milestone_data.project_budget, 0),
                    'actual_spend', COALESCE(milestone_data.actual_spend, 0),
                    'tech_stack', wp.technology_stack,
                    'key_results', COALESCE(kpi_data.key_results, ARRAY[]::TEXT[]),
                    'risks', COALESCE(risk_data.risks, '[]'::JSONB),
                    'team_size', COALESCE(team_data.total_members, 0),
                    'team_utilization', COALESCE(team_data.avg_utilization, 0)
                )) AS items
            FROM workflow_project wp
            LEFT JOIN workflow_projectportfolio wpport ON wp.id = wpport.project_id
            LEFT JOIN projects_portfolio pp ON wpport.portfolio_id = pp.id
            LEFT JOIN risk_data ON wp.id = risk_data.project_id
            LEFT JOIN team_data ON wp.id = team_data.project_id
            LEFT JOIN milestone_data ON wp.id = milestone_data.project_id
            LEFT JOIN kpi_data ON wp.id = kpi_data.project_id
            WHERE wp.tenant_id_id = {tenant_id}
            AND wp.archived_on IS NULL
            GROUP BY pp.id, pp.title
            HAVING pp.title IS NOT NULL;
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchStatusUpdatesBetweenTimes(project_id, start_date, end_date=None):
        condition = ""
        if end_date:
            condition = f"AND wps.created_date <= '{end_date}'"
        query = f"""
            select 
                CASE 
                    WHEN wps.type = 1 THEN 'Scope'
                    WHEN wps.type = 2 THEN 'Schedule'
                    WHEN wps.type = 3 THEN 'Spend'
                    ELSE 'Unknown Type'
                END AS status_type,
                -- wp.detailed_status A PROJECT_EXECUTION_COMMENT,
                CASE 
                    WHEN wps.value = 1 THEN 'On Track'
                    WHEN wps.value = 2 THEN 'At Risk'
                    WHEN wps.value = 3 THEN 'Compromised'
                    ELSE 'Unknown Value'
                END AS status_value,
                wps.comments AS status_comments
            FROM workflow_projectstatus as wps
            where wps.project_id = {project_id}
            AND wps.created_date >= '{start_date}'
            {condition}
            order by wps.created_date asc
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchProjectDetailsForServiceAssuranceReview(project_id):
        query = f"""
            SELECT 
                wp.title, 
                wp.description, 
                wp.objectives, 
                wp.technology_stack,
                wp.project_category,
                wp.start_date,
                wp.end_date,
                ARRAY_AGG(wpkpi.name) AS key_results,
                wp.key_accomplishments,
                wp.total_external_spend as project_budget
            FROM workflow_project AS wp
            LEFT JOIN workflow_projectkpi AS wpkpi ON wpkpi.project_id = wp.id
            WHERE wp.id = {project_id}
            GROUP BY 
                wp.title, 
                wp.description, 
                wp.objectives, 
                wp.technology_stack, 
                wp.project_category,
                wp.start_date,
                wp.key_accomplishments,
                total_external_spend,
                wp.end_date;

        """
        res = db_instance.retrieveSQLQueryOld(query)
        if len(res)>0:
            return res[0]
        else:
            return None

    @staticmethod
    def fetch_project_details_for_service_assurance_v2(project_id):
        query = f"""
            SELECT
                wp.title AS TITLE,
                wp.description AS project_description,
                wp.objectives,
                wp.start_date AS PROJECT_START_DATE,
                wp.end_date AS PROJECT_END_DATE,
                MAX(wpm.planned_spend) AS PROJECT_BUDGET,
                wp.technology_stack AS TECH_STACK,
                ARRAY_AGG(DISTINCT wpkpi.name) AS KEY_RESULTS,
                pp.title AS portfolio_title,
                (
                    SELECT JSON_AGG(
                                CAST(JSON_BUILD_OBJECT(
                                    'risk_id', wpr_sub.id,
                                    'risk_description', wpr_sub.description,
                                    'risk_impact', wpr_sub.impact,
                                    'risk_mitigation_strategy', wpr_sub.mitigation,
                                    'due_date', wpr_sub.due_date,
                                    'status_value', wpr_sub.status_value
                                ) AS TEXT)
                            )
                    FROM workflow_projectrisk wpr_sub
                    WHERE wpr_sub.project_id = wp.id
                ) AS risk_and_mitigation,
                ARRAY_AGG(DISTINCT 
                    CASE 
                        WHEN wpm.type = 2 THEN jsonb_build_object(
                            'milestone_id', wpm.id,
                            'name', wpm.name,
                            'target_date', wpm.target_date,
                            'actual_date', wpm.actual_date,
                            'status_value', CASE wpm.status_value
                                            WHEN 1 THEN 'not started'
                                            WHEN 2 THEN 'in progress'
                                            WHEN 3 THEN 'completed'
                                            ELSE 'unknown'
                                        END,
                            'comments', wpm.comments
                        )
                        ELSE NULL
                    END
                ) FILTER (WHERE wpm.type = 2) AS SCHEDULE_SCOPE_MILESTONES
            FROM
                workflow_project AS wp
            LEFT JOIN
                workflow_projectkpi AS wpkpi ON wp.id = wpkpi.project_id
            LEFT JOIN
                workflow_projectmilestone AS wpm ON wp.id = wpm.project_id
            LEFT JOIN
                workflow_projectportfolio AS wpport ON wp.id = wpport.project_id
            LEFT JOIN
                projects_portfolio AS pp ON wpport.portfolio_id = pp.id
            WHERE
                wp.id = {project_id}
                AND wp.archived_on IS NULL
                AND wp.parent_id IS NOT NULL
            GROUP BY
                wp.id, pp.title;
        """
        return db_instance.retrieveSQLQueryOld(query)

    # # ARRAY_AGG(DISTINCT jsonb_build_object(
    #                     'milestone_id', wpm.id,
    #                     'name', wpm.name,
    #                     'target_date', wpm.target_date,
    #                     'actual_spend', wpm.actual_spend,
    #                     'planned_spend', wpm.planned_spend
    #             ) FILTER (WHERE wpm.type = 3)) AS SPEND_MILESTONES

    @staticmethod
    def fetchProjectMilestonesV2(project_id):
        query = f"""
            SELECT 
                name AS milestone_name, 
                wm.target_date, 
                wm.actual_date as actual_completion_date,
                wm.planned_spend, 
                wm.actual_spend,
                wm.comments,
                CASE 
					WHEN status_value = 1 THEN 'not_started'
					WHEN status_value = 2 THEN 'in_progress'
					WHEN status_value = 3 THEN 'completed'
				END AS status,
                CASE
                    WHEN type = 1 THEN 'scope_milestone'
                    WHEN type = 2 THEN 'schedule_milestone'
                    WHEN type = 3 THEN 'spend_milestone'
                END AS type_name
            FROM workflow_projectmilestone as wm
            WHERE project_id = {project_id}
            and wm.type in (1,2,3)
        """
        milestones = db_instance.retrieveSQLQueryOld(query)

        if not milestones:
            return {
                "scope_milestones": [],
                "schedule_milestones": [],
                "spend_milestones": []
            }

        # Separate milestones by type
        scope_milestones = []
        schedule_milestones = []
        spend_milestones = []

        for milestone in milestones:
            if milestone['type_name'] == 'scope_milestone':
                scope_milestones.append(milestone)
            elif milestone['type_name'] == 'schedule_milestone':
                schedule_milestones.append(milestone)
            elif milestone['type_name'] == 'spend_milestone':
                spend_milestones.append(milestone)

        return {
            "scope_milestones": scope_milestones,
            "schedule_milestones": schedule_milestones,
            "spend_milestones": spend_milestones
        }
        

    
    def fetchAllProjectMembers(project_id):
        members = []
        query = f"""
            SELECT 
                    pts.id,
                    pts.member_name,
                    pts.member_role,
                    pts.is_external,
                    pts.location,
                    CASE 
                        WHEN pts.spend_type = 1 THEN 'Internal'
                        WHEN pts.spend_type = 2 THEN 'External'
                        ELSE 'Unknown'
                    END AS spend_type,
                    pts.average_spend,
                    pts.member_utilization
                FROM 
                    public.workflow_projectteamsplit pts
                WHERE 
                    pts.project_id = {project_id};
        """
        result = db_instance.retrieveSQLQueryOld(query)
        if result:
            for row in result:
                members.append({
                    "id": row["id"],
                    "member_name": db_instance.deanonymize_text_from_base64(row["member_name"]),
                    "member_role": row["member_role"],
                    "is_external": row["is_external"],
                    "location": row["location"],
                    "spend_type": row["spend_type"],
                    "average_spend": row["average_spend"],
                    "member_utilization": row["member_utilization"]
                })
        return members
    
    
    def fetchAllProjectSponsors(project_id):
        sponsors = []
        query = f"""
            SELECT 
                wpm.id as id,
                ppb.id AS portfolio_business_id,
                ppb.sponsor_first_name,
                ppb.sponsor_last_name,
                ppb.sponsor_email,
                ppb.sponsor_role,
                ppb.bu_name,
                ppb.customer_id,
                ppb.portfolio_id,
                ppb.tenant_id,
                wpm.project_id
            FROM public.workflow_projectbusinessmember wpm
            JOIN public.projects_portfoliobusiness ppb 
                ON wpm.portfolio_business_id = ppb.id
            WHERE wpm.project_id = {project_id};
        """
        result = db_instance.retrieveSQLQueryOld(query)
        if result:
            for row in result:
                sponsors.append({
                    "id": row["id"],
                    "portfolio_business_id": row["portfolio_business_id"],
                    "sponsor_first_name": db_instance.deanonymize_text_from_base64(row["sponsor_first_name"]),
                    "sponsor_last_name": db_instance.deanonymize_text_from_base64(row["sponsor_last_name"]),
                    "sponsor_email": db_instance.deanonymize_text_from_base64(row["sponsor_email"]),
                    "sponsor_role": row["sponsor_role"],
                    "bu_name": row["bu_name"],
                    "customer_id": row["customer_id"],
                    "portfolio_id": row["portfolio_id"],
                    "tenant_id": row["tenant_id"],
                    "project_id": row["project_id"]
                })
        return sponsors

        

    def deleteProjectMilestones(project_id, milestone_ids):
        
        # Create placeholders for the IN clause (e.g., %s, %s, %s)
        placeholders = ', '.join(['%s'] * len(milestone_ids))
        query = f"""
            DELETE FROM workflow_projectmilestone
            WHERE project_id = %s
            AND id IN ({placeholders})
        """
        # Combine project_id with milestone_ids for the parameter tuple
        params = (project_id,) + tuple(milestone_ids)
        return db_instance.executeSQLQuery(query, params)
    

    def deleteProjectRisks(project_id, risk_ids):
        
        placeholders = ', '.join(['%s'] * len(risk_ids))
        query = f"""
            DELETE FROM workflow_projectrisk
            WHERE project_id = %s
            AND id IN ({placeholders})
        """
        params = (project_id,) + tuple(risk_ids)
        return db_instance.executeSQLQuery(query, params)
    
    
    def deleteProjectTeamMembers(project_id, member_ids):
        
        placeholders = ', '.join(['%s'] * len(member_ids))
        query = f"""
            DELETE FROM workflow_projectteamsplit
            WHERE project_id = %s
            AND id IN ({placeholders})
        """
        params = (project_id,) + tuple(member_ids)
        return db_instance.executeSQLQuery(query, params)
    
    
    # def deleteProjectStatus(project_id, status_ids):
        
    #     placeholders = ', '.join(['%s'] * len(status_ids))
    #     query = f"""
    #         DELETE FROM workflow_projectstatus
    #         WHERE project_id = %s
    #         AND id IN ({placeholders})
    #     """
    #     params = (project_id,) + tuple(status_ids)
    #     return db_instance.executeSQLQuery(query, params)
    
    
    def deleteProjectSponsors(project_id, sponsor_ids):
        
        placeholders = ', '.join(['%s'] * len(sponsor_ids))
        query = f"""
            DELETE FROM public.workflow_projectbusinessmember
            WHERE project_id = %s
            AND id IN ({placeholders})
        """
        
        params = (project_id,) + tuple(sponsor_ids)
        return db_instance.executeSQLQuery(query, params)
    
    
    


    @staticmethod
    def getDataForPortfolioReview(eligibleProjects, additional_condition=None):
        project_ids_str = f"({', '.join(map(str, eligibleProjects))})"
        condition = additional_condition or ""
        query = f"""
            WITH ProjectData AS (
                SELECT 
                    wp.id AS project_id,
                    wp.org_strategy_align AS org_strategy,
                    wp.tenant_id_id AS tenant_id
                FROM workflow_project AS wp
                WHERE  wp.id IN {project_ids_str}
            ),
            PortfolioData AS (
                SELECT 
                    wpport.project_id,
                    ARRAY_AGG(DISTINCT pp.title) AS portfolios
                FROM workflow_projectportfolio AS wpport  
                LEFT JOIN projects_portfolio AS pp ON wpport.portfolio_id = pp.id
                GROUP BY wpport.project_id
            ),
            MilestoneData AS (
                SELECT 
                    wpm.project_id, 
                    MAX(wpm.planned_spend) AS planned_spend,
                    MAX(wpm.actual_spend) AS actual_spend,
                    MAX(CASE WHEN wpm.actual_spend > wpm.planned_spend THEN wpm.actual_spend - wpm.planned_spend ELSE 0 END) AS overrun
                FROM workflow_projectmilestone AS wpm
                GROUP BY wpm.project_id
            )
            SELECT 
                p.project_id,
                p.org_strategy,
                po.portfolios,
                m.planned_spend,
                m.actual_spend,
                m.overrun
            FROM ProjectData p
            LEFT JOIN PortfolioData po ON p.project_id = po.project_id
            LEFT JOIN MilestoneData m ON p.project_id = m.project_id
            {condition}
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    
    @staticmethod
    def FetchArchivedProjects(tenant_id):
        query = f"""
            SELECT 
                wp.id
            FROM workflow_project AS wp
            WHERE wp.tenant_id_id = {tenant_id}
            AND wp.archived_on IS NOT NULL
        """
        res = db_instance.retrieveSQLQueryOld(query)
        return [r["id"] for r in res]
    
    @staticmethod
    def getDataForPortfolioReviewArchived(eligibleProjects, additional_condition=None):
        project_ids_str = f"({', '.join(map(str, eligibleProjects))})" if eligibleProjects else "()"
        condition = additional_condition or ""
        query = f"""
            WITH ProjectData AS (
                SELECT 
                    wp.id AS project_id,
                    wp.org_strategy_align AS org_strategy,
                    wp.tenant_id_id AS tenant_id,
                    wp.title AS project_title,
                    wp.archived_on
                FROM workflow_project AS wp
                WHERE wp.id IN {project_ids_str}
            ),
            PortfolioData AS (
                SELECT 
                    wpport.project_id,
                    ARRAY_AGG(DISTINCT pp.title) AS portfolios
                FROM workflow_projectportfolio AS wpport  
                LEFT JOIN projects_portfolio AS pp ON wpport.portfolio_id = pp.id
                GROUP BY wpport.project_id
            ),
            ValueRealizationData AS (
                SELECT 
                    wpr.project_id,
                    COUNT(wpr.id) AS value_realization_count
                FROM workflow_projectvaluerealization AS wpr
                GROUP BY wpr.project_id
            )
            SELECT 
                p.project_id,
                p.project_title,
                p.org_strategy,
                p.archived_on,
                po.portfolios,
                COALESCE(vr.value_realization_count, 0) AS value_realization_count
            FROM ProjectData p
            LEFT JOIN PortfolioData po ON p.project_id = po.project_id
            LEFT JOIN ValueRealizationData vr ON p.project_id = vr.project_id
            {condition}
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    
    @staticmethod
    def fetchAllStatusUpdates(project_id):
        query = f"""
            SELECT 
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
                wps.created_date
            FROM workflow_projectstatus AS wps
            WHERE wps.project_id = {project_id}
            ORDER BY wps.created_date ASC
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def getProjectScope(project_id):
        query = f"""
            SELECT scope from workflow_projectscope 
            where project_id = {project_id}
        """
        return db_instance.retrieveSQLQueryOld(query)
    

    @staticmethod
    def get_all_child_projects(tenant_id):
        query = f"""
            select id from workflow_project
            where parent_id is not null
            and tenant_id_id = {tenant_id}
        """
        data = db_instance.retrieveSQLQueryOld(query)
        return [p["id"] for p in data]

    @staticmethod
    def fetchProjectAttrForId(id, attr):
        query = f"""
            select 
                *
            from workflow_project as wp
            where wp.id = {id}
        """
        data = db_instance.retrieveSQLQueryOld(query)
        required_data = None
        for d in data:
            if attr in d:
                return d.get(attr)
        return required_data
    
    
    @staticmethod
    def fetchProjectTeamAttr(project_id, attr):
        query = f"""
            select * from workflow_projectteam
            where project_id = {project_id}
        """
        data = db_instance.retrieveSQLQueryOld(query)
        required_data = None
        for d in data:
            if attr in d:
                return d.get(attr)
        return required_data
    
    
    @staticmethod
    def fetchKeyResultsOfProject(project_id):
        query = f"""
            select * from workflow_projectkpi
            where project_id = {project_id}
        """
        data = db_instance.retrieveSQLQueryOld(query)
        return data
    
    
    @staticmethod
    def fetchProjectBasicInfoForAutoStatusUpdate(project_id):
        query = f"""
            SELECT 
            wp.title AS TITLE,
                wp.description AS project_description,
                wp.objectives,
                wp.start_date AS PROJECT_START_DATE,
                wp.end_date AS PROJECT_END_DATE
            FROM
                workflow_project AS wp
            WHERE
                wp.id = {project_id}
        """
        return  db_instance.retrieveSQLQueryOld(query)
        
            
    @staticmethod
    def fetchProjectIdTitleAndPortfolio(tenant_id, project_ids):
        project_ids_str = f"({', '.join(map(str, project_ids))})"
        query = f"""
            SELECT 
                wp.id AS project_id,
                wp.title AS project_title,
                ARRAY_AGG(pp.title) AS portfolio_titles
            FROM workflow_project AS wp
            LEFT JOIN workflow_projectportfolio AS wpp ON wp.id = wpp.project_id
            LEFT JOIN projects_portfolio AS pp ON wpp.portfolio_id = pp.id
            WHERE wp.tenant_id_id = {tenant_id}
                AND wp.archived_on IS NULL
                AND wp.parent_id is not null
                and wp.id in {project_ids_str}
            GROUP BY wp.id, wp.title;
        """
        # print("fetchProjectIdTitleAndPortfolio ", query)
        try:
            return  db_instance.retrieveSQLQueryOld(query)
        except:
            return []
        
        
    @staticmethod
    def fetchAllChildProjectsForTenantForPacketFabric(tenant_id):
        query = f"""
            select wp.id, wp.title, wp.program_id, pp.id as portfolio_id, wp.is_program
                from workflow_project AS wp
                left join workflow_projectportfolio AS wpport on wpport.project_id = wp.id
                LEFT JOIN projects_portfolio AS pp ON wpport.portfolio_id = pp.id
            where wp.parent_id is not null
            AND wp.archived_on is null
            and wp.tenant_id_id = 174
                and wp.is_program = false
                and pp.id = 165
            order by wp.id asc
        """
        data = db_instance.retrieveSQLQueryOld(query)
        return data
            
    @staticmethod
    def fetchAllProgramFortenant(tenant_id):
        # print("fetchAllProgramFortenant", tenant_id)
        query = f"""
            select * FROM program_program
                where tenant_id = {tenant_id} 
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            print("error fetching program", e)
            return []
        

    @staticmethod
    def fetchAllProjectTechnologies(limit:int=300):
        query = f"""
            SELECT id,title FROM projects_technology
            ORDER BY id desc
            limit {limit}
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            return []
        
    @staticmethod
    def fetchProjectIdTitle(tenant_id, project_ids):
        project_ids_str = f"({', '.join(map(str, project_ids))})"
        query = f"""
            SELECT 
                wp.id AS project_id,
                wp.title AS project_title
            FROM workflow_project AS wp
            LEFT JOIN workflow_projectportfolio AS wpp ON wp.id = wpp.project_id
            LEFT JOIN projects_portfolio AS pp ON wpp.portfolio_id = pp.id
            WHERE wp.tenant_id_id = {tenant_id}
                AND wp.archived_on IS NULL
                AND wp.parent_id is not null
                and wp.id in {project_ids_str}
            GROUP BY wp.id, wp.title;
        """
        try:
            return  db_instance.retrieveSQLQueryOld(query)
        except:
            return []