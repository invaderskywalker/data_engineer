from typing import List
from src.api.logging.AppLogger import appLogger
from src.utils.constants.base import AUDIT_LOG_MAP
from src.database.Database import db_instance,TrmericDatabase

class TenantDao:
    @staticmethod
    def FetchAllTenants():
        query = """SELECT * FROM public.tenant_tenant ORDER BY id ASC"""
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def FetchAllTenantIDs():
        query = """SELECT id FROM public.tenant_tenant ORDER BY id ASC"""
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def FetchUsersOfTenant(tenant_id):
        try:
            query = f"""
            SELECT uu.id as user_id, uu.username, uu.first_name FROM users_user as uu where uu.tenant_id = {tenant_id}
            """
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            return []
    
    @staticmethod
    def getTenantID(provider_name):
        providerDecrypted = TrmericDatabase().deanonymize_text_from_base64(provider_name)
        query = f"""
                select tenant_id from tenant_provider where company_name = '{providerDecrypted}'
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def FetchAllProvidersForProject(project_id):
        
        query = f"""
            select id,company_name from tenant_provider where id in 
                (select provider_id FROM public.workflow_projectprovider where project_id = {project_id})
        """
        try:
            result = db_instance.retrieveSQLQueryOld(query)
            _providers = []
            providers = [item['company_name'] for item in result]
            for i in range(len(providers)):
                providers[i] = TrmericDatabase().deanonymize_text_from_base64(providers[i])
                _providers.append({
                    "id": result[i]['id'],
                    "provider_name": providers[i]
                })
            
            # print("--debug in FetchAllProvidersForProject", _providers)
            return _providers
        except Exception:
            return None
        
    @staticmethod
    def getCapacityResource(first_name, last_name,tenant_id):
        query = f"""
            select * from capacity_resource where first_name like '%{first_name}%' 
            and last_name like '%{last_name}%' 
            and tenant_id = {tenant_id}
            select * from capacity_resource where first_name like '%{first_name}%' 
            and last_name like '%{last_name}%' 
            and tenant_id = {tenant_id}
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception:
            return None
        
    @staticmethod
    def getDistinctAvailableRoles(tenant_id):
        query = f"""
            SELECT distinct(role), country FROM public.capacity_resource
            where tenant_id = {tenant_id}   
            and role is not null
        """
        return db_instance.retrieveSQLQueryOld(query)
        
    @staticmethod
    def getRoleCountForTenant(tenant_id):
        query = f"""
            SELECT role, COUNT(*) AS total_count
            FROM public.capacity_resource
            WHERE tenant_id = {tenant_id}
            AND role IS NOT NULL
            GROUP BY role;
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def getAllRoadmapsRoleCountForTenant(tenant_id):
        query = f"""
            SELECT re.name AS role, COUNT(*) AS allocated_count
            FROM public.roadmap_roadmapestimate re
            JOIN public.roadmap_roadmap rr ON re.roadmap_id = rr.id
            WHERE rr.tenant_id = {tenant_id} AND re.labour_type = 1
            GROUP BY re.name;
        """
        return db_instance.retrieveSQLQueryOld(query)
        
    @staticmethod
    def getCapacityProviderID(provider_name,tenant_id):
        # provider = f"({', '.join(map(str, provider_name))})" 
        query = f"""
            select id from capacity_external_providers where company_name = '{provider_name}' and tenant_id = {tenant_id}
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception:
            return None
        
    @staticmethod
    def getCapacityResourceTimeline(resource_id,project_name,tenant_id):
        query = f"""
            select id from capacity_resource_timeline 
            where resource_id = {resource_id} and project_name = '{project_name}'
            and tenant_id = {tenant_id}
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception:
            return None
        
    @staticmethod
    def getOnboardingV2Steps(self, tenant_id):
        query = f"""
            SELECT s.*
            FROM onboarding_v2_step s
            JOIN onboarding_v2_info o ON s.onboarding_id = o.id
            WHERE o.tenant_id = {tenant_id};
        """
        return db_instance.retrieveSQLQueryOld(query)
          
    @staticmethod
    def fetchTenantType(tenant_id):
        try:
            query = f"""
                SELECT types FROM tenant_tenant
                WHERE id = {tenant_id}
            """
            tenant_type_obj = db_instance.retrieveSQLQueryOld(query)
            if tenant_type_obj and len(tenant_type_obj) > 0:
                return "provider" if tenant_type_obj[0]["types"] != "customer" else "customer"
            return "customer"  # Default to customer if no data found
        except Exception as e:
            appLogger.error({
                "function": "fetchTenantType",
                "event": "DB_CALL_FAILURE",
                "error": str(e)
            })
            return "customer"  # Default to customer on error
    
        
    @staticmethod
    def getResourceCapacityBasicInfo(tenant_id):
        query = f"""
            SELECT
                cr.id,
                cr.first_name,
                cr.last_name,
                cr.role,
                cr.skills,
                cr.allocation,
                cr.experience_years,
                cr.experience,
                cr.projects,
                cr.is_active,
                cr.is_external,
                cr.availability_time,
                cr.primary_skill
            FROM capacity_resource AS cr
            WHERE cr.tenant_id = {tenant_id} AND cr.is_active = true
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            print(f"Error in getResourceCapacityBasicInfo: {e}")
            return []
        
        
    @staticmethod
    def getTenantInfo(tenant_id):
        query = f"""
            SELECT id, title, description, types, created_on, configuration, year_cycle
            FROM tenant_tenant WHERE id = {tenant_id}
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({"function": "getTenantInfo","event": "DB_CALL_FAILURE","error": str(e)})
            return []
        
    @staticmethod
    def checkCustomerType(tenant_id):
        query = f"select types from tenant_tenant where id = {tenant_id}"
        tenant_type = "customer"
        try:
            tenant_type_obj = db_instance.retrieveSQLQueryOld(query)
            print("tenant_type_obj ", tenant_type_obj)
            if tenant_type_obj:
                if tenant_type_obj[0]["types"] != "customer":
                    tenant_type = "provider"
        except Exception as e:
            appLogger.error(
                {"event": "error in FetchAvailableProject", "error": e})
        return tenant_type   
    
    @staticmethod
    def checkTenantConfig(tenant_id):
        try:
            tenant_config = TenantDao.getTenantInfo(tenant_id=tenant_id)
            tenant_formats = {"currency_format": "USD"}
            if not tenant_config or len(tenant_config) == 0:
                return tenant_formats
            
            tenant_config_res = tenant_config[0].get("configuration", {})
            tenant_year_cycle_res = tenant_config[0].get("year_cycle") or "Jan-Dec"
            # print("debug checkTenantConfig ", tenant_config_res)
            if tenant_config_res is not None:
                tenant_formats["currency_format"] = tenant_config_res.get("currency","USD") or "USD"
                tenant_formats["year_cycle"] = tenant_year_cycle_res
                tenant_formats["financial_cycle"] = tenant_year_cycle_res
                # tenant_formats["date_format"] = tenant_config_res.get("date_time",{}) 
            return tenant_formats
        except Exception as e:
            return None
        
        
    @staticmethod
    def listCustomerSolutions(tenant_id):
        query = f"""
            SELECT * FROM tenant_customer_solution WHERE tenant_id = {tenant_id}
            order by id desc  
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({"function": "listCustomerSolutions","event": "DB_CALL_FAILURE","error": str(e)})
            return []
        
        
    @staticmethod
    def listCustomerSolutionsDelivered(tenant_id):
        query = f"""
            SELECT * FROM tenant_customer_solution_delivered 
            WHERE tenant_id = {tenant_id}
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({"function": "listCustomerSolutionsDelivered","event": "DB_CALL_FAILURE","error": str(e)})
            return []

    @staticmethod
    def listCustomerSolutionsDeliveredForFiles(tenant_id):
        query = f"""
            SELECT * FROM tenant_customer_solution_delivered 
            WHERE tenant_id = {tenant_id}
            AND file_id is not null
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({"function": "listCustomerSolutionsDeliveredForFiles","event": "DB_CALL_FAILURE","error": str(e)})
            return []
        
        
    @staticmethod
    def fetchResourceDetailsForTenant(tenant_id, resource_ids= []):
        """
        Fetch resource details with associated projects from capacity_resource_timeline for a given tenant using a subquery.
        """
        # Build condition statement for resource IDs
        condition_statement = ""
        if resource_ids:
            resource_ids_str = ", ".join(map(str, resource_ids))
            condition_statement = f"cr.id IN ({resource_ids_str}) AND "

        query = f"""
            SELECT
                cr.id,
                cr.first_name AS first_name,
                cr.last_name AS last_name,
                cr.role,
                CONCAT(
                    cr.experience_years, ' years of experience as a ',
                    cr.role, '. ',
                    cr.experience
                ) AS description,
                cr.primary_skill,
                cr.skills,
                (
                    SELECT COALESCE(
                        json_agg(
                            json_build_object(
                                'project_id', crt.trmeric_project_id,
                                'project_name', crt.project_name,
                                'project_allocation', crt.allocation,
                                'start_date', crt.start_date,
                                'end_date', crt.end_date
                            )
                        ) FILTER (WHERE crt.trmeric_project_id IS NOT NULL),
                        '[]'
                    )
                    FROM public.capacity_resource_timeline AS crt
                    WHERE crt.resource_id = cr.id
                    AND crt.tenant_id = {tenant_id}
                ) AS projects,
                (
                    SELECT COALESCE(
                        json_agg(
                            json_build_object(
								'team_id', crg.id,
                                'leader_first_name', cr.first_name,
                                'leader_last_name' , cr.last_name,
                                'org_team', crg.name
                            )
                        ) FILTER (WHERE crg.leader_id IS NOT NULL),
                        '[]'
                    )
                    FROM public.capacity_resource_group AS crg
                    LEFT JOIN capacity_resource ON cr.id = crg.leader_id
					LEFT JOIN capacity_resource_group_mapping crgm ON crg.id = crgm.group_id
                    AND cr.tenant_id = {tenant_id}
                    WHERE  crgm.resource_id = cr.id
                    AND crg.tenant_id = {tenant_id}
                ) AS org_team,
                cr.is_external,
                cr.availability_time
            FROM public.capacity_resource AS cr
            WHERE {condition_statement}cr.tenant_id = {tenant_id} AND cr.is_active = true
        """

        try:
            result = db_instance.retrieveSQLQueryOld(query)  
            # print("--debug fetchResourceDetailsForTenant query2----", result[:2])       
            return result
            
        except Exception as e:
            appLogger.error({"function": "listCustomerSolutionsDelivered","event": "DB_CALL_FAILURE","error": str(e)})
            return []
        
    
    @staticmethod
    def fetchOrgTeamGroupsForTenant(tenant_id):
        query = f"""
            select * from capacity_resource_group where tenant_id = {tenant_id}
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({"function": "fetchOrgTeamGroupsForTenant","event": "DB_CALL_FAILURE","error": str(e)})
            return []

    @staticmethod
    def fetchOrgTeamsAndPortfolioMappingForTenant(tenant_id):
        query = f"""
            SELECT DISTINCT 
                crgpm.portfolio_id,
                pp.title AS portfolio_name,
                crgpm.resource_group_id,
                crg.name AS org_team
            FROM 
                capacity_resource_group_portfolio_mapping crgpm
                INNER JOIN projects_portfolio pp ON crgpm.portfolio_id = pp.id
                INNER JOIN capacity_resource_group crg ON crgpm.resource_group_id = crg.id
            WHERE 
                crgpm.tenant_id = {tenant_id};
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({"function": "fetchOrgTeamGroupsForTenant","event": "DB_CALL_FAILURE","error": str(e)})
            return []



    @staticmethod
    def fetchAuditLogData(
        log_ids: List[int] = None,
        projection_attrs: List[str] = ["id", "timestamp", "model_name", "changes"],
        object_id: int = None,
        model_name: str = None,
        tenant_id: int = None,
        action: str = None,
        user_id: int = None,
        limit: int = 30
    ):
        """
            Fetch audit log data with specified projection attributes, optionally filtering by 
            log_ids, object_id, model_name, tenant_id, action, or user_id.
        """
        try:
    
            select_clauses = []
            joins = set()  
            group_by_clauses = set()
            where_conditions = []

            # No aggregation required based on current map
            requires_aggregation = False

            # Build SELECT clauses based on projection attributes
            for attr in projection_attrs:
                mapping = AUDIT_LOG_MAP.get(attr)
                if not mapping:
                    continue
                # Use table alias explicitly in SELECT clause
                column = mapping["column"]
                if "AS" not in column and mapping["table"]:
                    column = f"{mapping['table']}.{column}"
                select_clauses.append(column)
                if "join" in mapping:
                    joins.add(mapping["join"])
                if mapping.get("group_by", True) and requires_aggregation:
                    # Use table alias in GROUP BY clause
                    group_by_column = mapping["column"].split(" AS ")[0]
                    if "AS" not in mapping["column"] and mapping["table"]:
                        group_by_column = f"{mapping['table']}.{group_by_column}"
                    group_by_clauses.add(group_by_column)

            # Construct WHERE clause
            if log_ids:
                log_ids_str = f"({', '.join(map(str, log_ids))})"
                where_conditions.append(f"al.id IN {log_ids_str}")
            if object_id is not None:
                where_conditions.append(f"al.object_id = {object_id}")
            if model_name:
                where_conditions.append(f"al.model_name ILIKE '{model_name}%'")
            if tenant_id is not None:
                where_conditions.append(f"al.tenant_id = {tenant_id}")
            if action:
                where_conditions.append(f"al.action = '{action}'")
            if user_id is not None:
                where_conditions.append(f"al.user_id = {user_id}")

            select_clause_str = ",\n                ".join(select_clauses) if select_clauses else "al.id"
            join_clause_str = "\n            ".join(joins)
            where_clause_str = " AND ".join(where_conditions) if where_conditions else "1=1"
            group_by_clause = f"\n            GROUP BY {', '.join(group_by_clauses)}" if group_by_clauses and requires_aggregation else ""

            query = f"""
                SELECT 
                    {select_clause_str}
                FROM admin_trmeric_auditlog AS al
                {join_clause_str}
                WHERE {where_clause_str}
                {group_by_clause}
                ORDER BY al.timestamp DESC
                LIMIT {limit};
            """
            
            # print("query in fetchAuditLogDataWithProjectionAttrs:\n", query)
            return db_instance.retrieveSQLQueryOld(query)

        except Exception as e:
            appLogger.error({"function": "fetchAuditLogDataWithProjectionAttrs","event": "DB_CALL_FAILURE","error": str(e)})
            return []


    @staticmethod
    def fetchReleaseCycleTag(tenant_id, year = '2025'):
        query = f"""
            SELECT id,title FROM tenant_release_cycles 
            WHERE tenant_id = {tenant_id}
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({"function": "fetchReleaseCycleTag","event": "DB_CALL_FAILURE","error": str(e)})
            return []

    @staticmethod
    def getOrgTeamsAndPortfolioDetailsForResources(resource_ids: list[int], tenant_id: int):
        if not resource_ids:
            return []
        
        resource_ids_str = ", ".join(map(str, resource_ids))
        query = f"""
            SELECT 
                rgm.resource_id,
                ARRAY_AGG(DISTINCT rgm.group_id) AS resource_group_ids,
                ARRAY_AGG(DISTINCT rgpm.portfolio_id) AS portfolio_ids
            FROM capacity_resource_group_mapping rgm
            LEFT JOIN capacity_resource_group_portfolio_mapping rgpm
                ON rgm.group_id = rgpm.resource_group_id
                AND rgm.tenant_id = rgpm.tenant_id
            WHERE rgm.resource_id IN ({resource_ids_str})
            AND rgm.tenant_id = {tenant_id}
            GROUP BY rgm.resource_id
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({"function": "getOrgTeamsAndPortfolioDetailsForResources","event": "DB_CALL_FAILURE","error": str(e)})
            return []



    @staticmethod
    def getTotalRoleCountByPortfolio(tenant_id: int):
        query = f"""
            SELECT 
                cr.role,
                cr.country,
                pp.title AS portfolio,
                COUNT(DISTINCT cr.id) AS headcount
            FROM public.capacity_resource cr
            LEFT JOIN capacity_resource_portfolio crp ON cr.id = crp.resource_id
            LEFT JOIN projects_portfolio pp ON pp.id = crp.portfolio_id
            WHERE cr.tenant_id = {tenant_id}
            AND NULLIF(TRIM(cr.role), '') IS NOT NULL
            GROUP BY cr.role, pp.title, cr.country
            ORDER BY cr.role, portfolio;
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({"function": "getTotalRoleCountByPortfolio","event": "DB_CALL_FAILURE","error": str(e)})
            return []


    @staticmethod
    def getAllRoadmapsEstimationDetailsForTenant(tenant_id: int,exclude_roadmap_id: int = None):
        query = f"""
            SELECT re.name AS role, re.start_date, re.end_date, COUNT(*) AS allocated_count
            FROM public.roadmap_roadmapestimate re
            JOIN public.roadmap_roadmap rr ON re.roadmap_id = rr.id
            WHERE rr.tenant_id = {tenant_id}
            AND re.labour_type = 1
            AND re.start_date IS NOT NULL 
            AND re.end_date IS NOT NULL
        """

        ## Exclude current roadmap estimates for retrigger estimation
        if exclude_roadmap_id:
            query += f" AND rr.id != {exclude_roadmap_id}"        
        query += " GROUP BY re.name, re.start_date, re.end_date"

        # print("--debug getAllRoadmapsEstimationDetailsForTenant query--", query)
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({"function": "getAllRoleAllocationsWithTimeline","event": "DB_CALL_FAILURE","error": str(e)})
            return []



    @staticmethod
    def fetch_total_time_spent_in_trmeric(tenant_id):
        query = f"""
            SELECT * FROM tenant_tenant_stats 
            WHERE stat_key = 'ALL_TOTAL_HOURS'
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({"function": "fetch_total_time_spent_in_trmeric","event": "DB_CALL_FAILURE","error": str(e)})
            return []