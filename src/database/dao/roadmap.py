from src.database.Database import db_instance
from src.api.logging.AppLogger import appLogger
from src.utils.enums import AuthRoles
from .auth import AuthDao
from .portfolios import PortfolioDao
from src.utils.constants.base import roadmap_type_mapping,roadmap_state_mapping


class RoadmapDao:

    @staticmethod
    def getRoadmapIdToAttachedProject(project_id):
        query = f"""
            select wp.roadmap_id from  workflow_project as wp where wp.id = {project_id}
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def getRoadmapInfo(project_id):

        query = f"""
            select rr.*
            from roadmap_roadmap as rr
            where rr.id = (select wp.roadmap_id from  workflow_project as wp where wp.id = {project_id} )

        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def getKpiOfRoadmapInfo(project_id):
        query = f"""
            select rrkpi.name 
            from roadmap_roadmap as rr
            join roadmap_roadmapkpi as rrkpi
            on rr.id = rrkpi.roadmap_id
            where rr.id = (select wp.roadmap_id from  workflow_project as wp where wp.id = {project_id} )

        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def FetchRoadmapNames(tenant_id):
        query = f"""
        select 
            rr.title from roadmap_roadmap as rr where rr.tenant_id = {tenant_id}
        """
        return db_instance.retrieveSQLQueryOld(query)

    def FetchRoadmapNamesWithIDS(tenant_id, roadmap_ids):
        query = f"""
        select 
            rr.id, rr.title from roadmap_roadmap as rr where rr.tenant_id = {tenant_id}
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchRoadmapsForTenantCreatedAfterYesterday(tenant_id):
        query = f"""
            SELECT id as roadmap_id, 
                title as roadmap_title
            FROM roadmap_roadmap
            WHERE created_on >= DATE_TRUNC('day', CURRENT_DATE - INTERVAL '1 day')
            AND created_on < DATE_TRUNC('day', CURRENT_DATE)
            AND tenant_id={tenant_id};
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchOrgStrategyAlignMentOfTenant(tenant_id):
        query = f"""
            SELECT * FROM roadmap_roadmaporgstratergyalign
            where tenant_id = {tenant_id}
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def fetchRoadmapForTenant(tenant_id, portfolio_ids):
        portfolio_ids_str = f"({', '.join(map(str, portfolio_ids))})"
        query = f"""
            SELECT 
                rr.id AS id, 
                rr.title AS title, 
                rr.org_strategy_align,
                COALESCE(ARRAY_AGG(rmk.name) FILTER (WHERE rmk.name IS NOT NULL), '{{}}') AS kpi_names
            FROM roadmap_roadmap AS rr
            LEFT JOIN roadmap_roadmapkpi AS rmk 
                ON rr.id = rmk.roadmap_id
            left join roadmap_roadmapportfolio rrp on rrp.roadmap_id = rr.id
             join projects_portfolio pp ON rrp.portfolio_id = pp.id
            WHERE rr.tenant_id = {tenant_id} and pp.id IN {portfolio_ids_str}
            GROUP BY rr.id, pp.id, rr.title, rr.org_strategy_align;
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    # portfolio_ids_str = f"({', '.join(map(str, portfolio_ids))})"
    #     # project_ids_str = f"({', '.join(map(str, applicable_projects))})" 
    #     query = f"""
    #         select  
    #             COALESCE(pp.id, 0) AS portfolio_id,
    #             COALESCE(pp.title, 'No Portfolio') AS portfolio_title,
    #             rr.id as roadmap_id,
    #             rr.title as roadmap_title,
    #             rr.start_date,
    #             rr.end_date,
    #             rr.budget as planned_spend,
    #             rr.budget,
    #             ARRAY_AGG(rrkpi.name) AS kpi_names,
    #             rr.priority,
    #             rr.current_state
    #         from roadmap_roadmap rr
    #         left join roadmap_roadmapportfolio rrp on rrp.roadmap_id = rr.id
    #         left join roadmap_roadmapkpi as rrkpi on rrkpi.roadmap_id = rr.id
    #         left join projects_portfolio pp ON rrp.portfolio_id = pp.id
    #         where rr.tenant_id = {tenant_id} and pp.id IN {portfolio_ids_str}

    @staticmethod
    def fetchAllOrgstategyAlignmentTitles(tenant_id):
        try:
            data = RoadmapDao.fetchOrgStrategyAlignMentOfTenant(tenant_id)
            titles = []
            for d in data:
                titles.append(d["title"])
            return titles
        except Exception as e:
            appLogger.error({
                "event": "db_op",
                "function": "fetchAllOrgstategyAlignmentTitles",
                "error": e,
            })
            return []

    @staticmethod
    def fetchTeamDataRoadmap(roadmap_id):
        query = f"""
            select * from roadmap_roadmapestimate
            where roadmap_id = {roadmap_id}
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            return []


    @staticmethod
    def fetchRoadmapDataForBusinessPlan(roadmap_id):
        query = f"""
            select 
                rr.title as roadmap_title,
                rr.description as roadmap_description,
                rr.objectives as roadmap_objectives,
                rr.budget as roadmap_budget,
                rr.category as roadmap_category,
                rr.org_strategy_align as roadmap_org_strategy_alignment,
                rr.total_capital_cost as roadmap_total_capital_cost,
                json_agg(
                    distinct json_build_object(
                        'constraint_title', rrc.name,
                        'constraint_type', 
                        case
                            when rrc.type = 1 then 'Cost'
                            when rrc.type = 2 then 'Resource'
                            when rrc.type = 3 then 'Risk'
                            when rrc.type = 4 then 'Scope'
                            when rrc.type = 5 then 'Quality'
                            when rrc.type = 6 then 'Time'
                            else 'Unknown'
                        end
                    )::text
                ) as roadmap_constraints,
                json_agg(
                    distinct pp.title
                ) as roadmap_portfolios,
                json_agg(
                    distinct json_build_object(
                        'key_result_title', rrkpi.name,
                        'baseline_value', rrkpi.baseline_value
                    )::text
                ) as roadmap_key_results,
                json_agg(
                    distinct rrs.name
                ) as roadmap_scope,
				json_agg(
					distinct json_build_object(
                        'team_name', rrt.name,
						'team_unit_size', rrt.unit,
                        'labour_type', 
                        case
                            when rrt.labour_type = 1 then 'labour'
                            when rrt.labour_type = 2 then 'non labour'
                            else 'Unknown'
                        end,
                        'labour_estimate_value', rrt.estimate_value,
                        'team_efforts', 
                        case
                            when rrt.type = 1 then 'person days'
                            when rrt.type = 2 then 'person months'
                            else 'Unknown'
                        end
                    )::text
                ) AS team_data,
                -- Separate JSON for cash inflow of type 'savings'
                json_agg(
                    DISTINCT json_build_object(
                        'cash_inflow', rrac.cash_inflow,
                        'time_period', rrac.time_period,
                        'category', rrac.category,
                        'justification_text', rrac.justification_text
                    )::text
                ) FILTER (WHERE rrac.type = 'savings') AS operational_efficiency_gains_savings_cash_inflow,
                
                -- Separate JSON for cash inflow of type 'revenue'
                json_agg(
                    DISTINCT json_build_object(
                        'cash_inflow', rrac.cash_inflow,
                        'time_period', rrac.time_period,
                        'category', rrac.category,
                        'justification_text', rrac.justification_text
                    )::text
                ) FILTER (WHERE rrac.type = 'revenue') AS revenue_uplift_cash_inflow_data
                
            from roadmap_roadmap as rr 
            left join roadmap_roadmapconstraints as rrc on rr.id = rrc.roadmap_id
            left join roadmap_roadmapportfolio as rp on rr.id = rp.roadmap_id
            left join projects_portfolio as pp on rp.portfolio_id = pp.id
            left join roadmap_roadmapkpi as rrkpi on rr.id = rrkpi.roadmap_id
            left join roadmap_roadmapscope as rrs on rr.id = rrs.roadmap_id
			left join roadmap_roadmapestimate as rrt on rrt.roadmap_id = rr.id
            left join roadmap_roadmapannualcashinflow as rrac on rr.id = rrac.roadmap_id
            where rr.id = {roadmap_id}
            group by rr.id;
        """

        # appLogger.info({
        #     "event": "businessCaseTemplateCreate_query",
        #     "query":  query
        # })
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchRoadmapScoreFields(roadmap_id):
        """Fetch supplemental fields not included in fetchRoadmapDataForBusinessPlan.

        Returns a single-row dict with keys:
            solution, current_state, priority, type, start_date, end_date
        """
        query = f"""
            SELECT
                rr.solution,
                rr.current_state,
                rr.priority,
                rr.type,
                rr.start_date,
                rr.end_date
            FROM roadmap_roadmap AS rr
            WHERE rr.id = {roadmap_id}
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def getRoadmapItems(tenant_id):
        query = f"""
            select 
                wp.id, 
                wp.title, 
                wp.roadmap_id, 
                rr.title as roadmap_title
            from workflow_project as wp
            left join roadmap_roadmap as rr on rr.id = wp.roadmap_id
            where 
                wp.tenant_id_id = {tenant_id} 
                and wp.roadmap_id is not null
                and wp.end_date > NOW()::date 
                and wp.start_date < NOW()::date 
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    
    
    @staticmethod
    def fetchRoadmapList( tenant_id,  portfolio_id=None, **kwargs):
        """
        Fetches a list of roadmap IDs, titles, and their associated portfolio details.
        Optional filter by portfolio_id.
        """
        date_filter = ""
        portfolio_filter = ""
        if portfolio_id:
            portfolio_filter = f"WHERE rrp.portfolio_id = {portfolio_id}"
        
        query = f"""
            SELECT 
                rr.id AS roadmap_id,
                rr.title AS roadmap_title,
                COALESCE(pp.id, 0) AS portfolio_id,
                COALESCE(pp.title, 'No Portfolio') AS portfolio_title
            FROM 
                roadmap_roadmap rr
            LEFT JOIN 
                roadmap_roadmapportfolio rrp ON rr.id = rrp.roadmap_id
            LEFT JOIN 
                projects_portfolio pp ON rrp.portfolio_id = pp.id
            where rr.tenant_id = {tenant_id}
            {portfolio_filter}
            ORDER BY 
                rr.id ASC;
        """
        return db_instance.retrieveSQLQueryOld(query)


    @staticmethod
    def fetchAllPortfolioOfTenant(tenant_id):
        try:
            query = f"""
                select id, title from projects_portfolio where tenant_id_id = {tenant_id}
            """
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            return []
        
        
    @staticmethod
    def fetchRoadmapDetails(roadmap_id):
        
        query = f"""
            SELECT 
                rr.title AS roadmap_title,
                rr.description AS roadmap_description,
                rr.objectives AS roadmap_objectives,
                rr.category AS roadmap_category,
                rr.org_strategy_align AS roadmap_org_strategy_alignment,
                rr.start_date AS roadmap_start_date,
		        rr.end_date AS roadmap_end_date,
                rr.min_time_value AS roadmap_min_time_value,
                rr.type AS roadmap_type,
                rr.solution AS roadmap_solution,
                rr.current_state AS roadmap_state,
                JSON_AGG(
                    DISTINCT JSON_BUILD_OBJECT(
                        'constraint_title', rrc.name,
                        'constraint_type', 
                        CASE
                            WHEN rrc.type = 1 THEN 'Cost'
                            WHEN rrc.type = 2 THEN 'Resource'
                            WHEN rrc.type = 3 THEN 'Risk'
                            WHEN rrc.type = 4 THEN 'Scope'
                            WHEN rrc.type = 5 THEN 'Quality'
                            WHEN rrc.type = 6 THEN 'Time'
                            ELSE 'Unknown'
                        END
                    )::TEXT
                ) AS roadmap_constraints,

                JSON_AGG(
                    DISTINCT pp.title
                ) AS roadmap_portfolios,

                JSON_AGG(
                    DISTINCT JSON_BUILD_OBJECT(
                        'key_result_title', rrkpi.name,
                        'baseline_value', rrkpi.baseline_value
                    )::TEXT
                ) AS roadmap_key_results,

                JSON_AGG(
                    DISTINCT rrs.name
                ) AS roadmap_scope

            FROM roadmap_roadmap AS rr
            LEFT JOIN roadmap_roadmapconstraints AS rrc ON rr.id = rrc.roadmap_id
            LEFT JOIN roadmap_roadmapportfolio AS rp ON rr.id = rp.roadmap_id
            LEFT JOIN projects_portfolio AS pp ON rp.portfolio_id = pp.id
            LEFT JOIN roadmap_roadmapkpi AS rrkpi ON rr.id = rrkpi.roadmap_id
            LEFT JOIN roadmap_roadmapscope AS rrs ON rr.id = rrs.roadmap_id
            LEFT JOIN roadmap_roadmapannualcashinflow AS rrac ON rr.id = rrac.roadmap_id

            WHERE rr.id = {roadmap_id}
            GROUP BY rr.id;
        """
        try:
            # print("debug . bs ", roadmap_id, query)
            result = db_instance.retrieveSQLQueryOld(query)
            # print("debug . bs ", roadmap_id, result)
            
            for item in result:
                if item["roadmap_type"]:
                    item["roadmap_type"] = roadmap_type_mapping(item["roadmap_type"])
                if item.get('roadmap_state'):
                    item["roadmap_state"] = roadmap_state_mapping(item['roadmap_state'])
                print("--debug roadmap type->", item["roadmap_type"], " current_state-->", item["roadmap_state"])
            return result
        except Exception as e:
            print("error in fetchRoadmapDetails ", e)
            return None
    


    @staticmethod
    def fetchRoadmapDetailsV2FOrPortfolioReview(tenant_id, should_portfolio_exist=False):
        portfolio_condition = "AND rp.portfolio_id IS NOT NULL" if should_portfolio_exist else ""

        query = f"""
            SELECT 
                rr.id,
                rr.title AS roadmap_title,
                rr.description AS roadmap_description,
                rr.objectives AS roadmap_objectives,
                rr.category AS roadmap_category,
                rr.org_strategy_align AS roadmap_org_strategy_alignment,
                rr.start_date AS roadmap_start_date,
		        rr.end_date AS roadmap_end_date,
                

                JSON_AGG(
                    DISTINCT pp.title
                ) AS roadmap_portfolios,

                JSON_AGG(
                    DISTINCT JSON_BUILD_OBJECT(
                        'key_result_title', rrkpi.name,
                        'baseline_value', rrkpi.baseline_value
                    )::TEXT
                ) AS roadmap_key_results,

                JSON_AGG(
                    DISTINCT rrs.name
                ) AS roadmap_scope

            FROM roadmap_roadmap AS rr
            LEFT JOIN roadmap_roadmapconstraints AS rrc ON rr.id = rrc.roadmap_id
            LEFT JOIN roadmap_roadmapportfolio AS rp ON rr.id = rp.roadmap_id
            LEFT JOIN projects_portfolio AS pp ON rp.portfolio_id = pp.id
            LEFT JOIN roadmap_roadmapkpi AS rrkpi ON rr.id = rrkpi.roadmap_id
            LEFT JOIN roadmap_roadmapscope AS rrs ON rr.id = rrs.roadmap_id
            LEFT JOIN roadmap_roadmapannualcashinflow AS rrac ON rr.id = rrac.roadmap_id
            WHERE rr.tenant_id = {tenant_id} 
            -- and rr.current_state in (0,1)
            {portfolio_condition}
            GROUP BY rr.id;
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception:
            return None
    

    @staticmethod
    def get_data_for_insight_gen(tenant_id, filter_string: str = "") -> str:
        base_query = f"""
            SELECT 
                rr.id as roadmap_id, 
                rr.title as roadmap_title, 
                rr.category as roadmap_category,
                CASE 
                    WHEN rr.type = 1 THEN 'Program'
                    WHEN rr.type = 2 THEN 'Project'
                    WHEN rr.type = 3 THEN 'Enhancement'
                    WHEN rr.type = 4 THEN 'New Development'
                    WHEN rr.type = 5 THEN 'Enhancements or Upgrade'
                    WHEN rr.type = 6 THEN 'Consume a Service'
                    WHEN rr.type = 7 THEN 'Support a Pursuit'
                    WHEN rr.type = 8 THEN 'Acquisition'
                    WHEN rr.type = 9 THEN 'Global Product Adoption'
                    WHEN rr.type = 10 THEN 'Innovation Request for NITRO'
                    WHEN rr.type = 11 THEN 'Regional Product Adoption'
                    WHEN rr.type = 12 THEN 'Client Deployment'
                    ELSE 'Unknown'
                END AS roadmap_type,
                CASE 
                    WHEN rr.current_state = 0 THEN 'Intake'
                    WHEN rr.current_state = 1 THEN 'Approved'
                    WHEN rr.current_state = 2 THEN 'Execution'
                    WHEN rr.current_state = 3 THEN 'Archived'
                    WHEN rr.current_state = 4 THEN 'Elaboration'
                    WHEN rr.current_state = 5 THEN 'Solutioning'
                    WHEN rr.current_state = 6 THEN 'Prioritize'
                    WHEN rr.current_state = 99 THEN 'Hold'
                    WHEN rr.current_state = 100 THEN 'Rejected'
                    WHEN rr.current_state = 999 THEN 'Cancelled'
                    WHEN rr.current_state = 200 THEN 'Draft'
                    ELSE 'Unknown'
                END AS current_state,
                rr.start_date as roadmap_start_date,
                rr.end_date as roadmap_end_date,
                CASE 
                    WHEN rr.priority = 1 THEN 'High'
                    WHEN rr.priority = 2 THEN 'Medium'
                    WHEN rr.priority = 3 THEN 'Low'
                    ELSE 'Unknown'
                END AS roadmap_priority,
                json_agg(
                    DISTINCT json_build_object(
                        'portfolio_id', pp.id,
                        'portfolio_title', pp.title
                    )::text
                ) FILTER (WHERE pp.id IS NOT NULL) as roadmap_portfolios,
                json_agg(
                    DISTINCT json_build_object(
                        'constraint_title', rrc.name,
                        'constraint_type', 
                        CASE
                            WHEN rrc.type = 1 THEN 'Cost'
                            WHEN rrc.type = 2 THEN 'Risk'
                            WHEN rrc.type = 3 THEN 'Resource'
                            ELSE 'Other'
                        END
                    )::text
                ) FILTER (WHERE rrc.name IS NOT NULL) as roadmap_constraints
            FROM roadmap_roadmap AS rr 
            LEFT JOIN roadmap_roadmapconstraints AS rrc ON rr.id = rrc.roadmap_id
            LEFT JOIN roadmap_roadmapportfolio AS rp ON rr.id = rp.roadmap_id
            LEFT JOIN projects_portfolio AS pp ON rp.portfolio_id = pp.id
            WHERE rr.tenant_id = {tenant_id}
        """
        if filter_string:
            base_query += f" {filter_string}"
        base_query += " GROUP BY rr.id, rr.priority, rr.type;"
        try:
            return db_instance.retrieveSQLQueryOld(base_query)
        except Exception:
            return []
        
        
    @staticmethod
    def fetchEligibleRoadmapList(tenant_id,  user_id, **kwargs):
        ## user role
        ## if requestor
        ## only show roadmaps he created
        role = AuthDao.fetchRoleOfUserInTenant(user_id)
        print("role of this user is ", role)
        _filter = "" 
        if role == AuthRoles.ORG_DEMAND_REQUESTOR.name:
            _filter = f"and rr.created_by_id = {user_id}"
        
        ## if demand manager
        ## only show roadmaps in his portfolio
        if role == AuthRoles.ORG_DEMAND_MANAGER.name:
            portfolios_eligible = PortfolioDao.fetchApplicablePortfolios(user_id, tenant_id)
            portfolio_ids = []
            for p in portfolios_eligible:
                portfolio_ids.append(p["id"])
            portfolio_ids_str = f"({', '.join(map(str, portfolio_ids))})"
            _filter = f"and pp.id in {portfolio_ids_str}"
            
            
        query = f"""
            SELECT 
                rr.id AS roadmap_id,
                rr.title AS roadmap_title,
                COALESCE(pp.id, 0) AS portfolio_id,
                COALESCE(pp.title, 'No Portfolio') AS portfolio_title
            FROM 
                roadmap_roadmap rr
            LEFT JOIN 
                roadmap_roadmapportfolio rrp ON rr.id = rrp.roadmap_id
            LEFT JOIN 
                projects_portfolio pp ON rrp.portfolio_id = pp.id
            where rr.tenant_id = {tenant_id}
             {_filter}
            ORDER BY 
                rr.id ASC;
        """
        result = db_instance.retrieveSQLQueryOld(query)
        
        if kwargs.get("fetch_only_ids") or False:
            arr = []
            for r in result:
                arr.append(r.get("roadmap_id"))
            return arr
        
        # print("fetchEligibleRoadmapList", result)
        return result
    
        
    
    
    @staticmethod
    def fetchRoadmapKpis(roadmap_id):
        query = f"""
            SELECT name,baseline_value FROM roadmap_roadmapkpi
            WHERE roadmap_id = {roadmap_id}
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def fetchRoadmapScope(rodmap_id):
        query = f"""
            select name from roadmap_roadmapscope where roadmap_id = {rodmap_id}
        """
        result = db_instance.retrieveSQLQueryOld(query)
        if len(result) > 0:
            return result[0]["name"]
        else:
            return None
        
    @staticmethod
    def fetchRoadmapCashInflow(roadmap_id):
        query = f"""
            SELECT 
                rci.cash_inflow,rci.time_period,rci.category,rci.justification_text
            FROM 
                public.roadmap_roadmapannualcashinflow rci
            WHERE 
                rci.roadmap_id = {roadmap_id}
            ORDER BY 
                rci.time_period ASC
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            print(f"Error executing query: {e}")
            return []
        
    @staticmethod
    def fetchRoadmapConstraints(roadmap_id):
        query = f"""
            SELECT name,type FROM public.roadmap_roadmapconstraints
            where roadmap_id = {roadmap_id}
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    
    @staticmethod
    def fetchRoadmapCategory(tenant_id):
        query = f"""
            SELECT title FROM public.roadmap_roadmapcategory
            where tenant_id = {tenant_id}
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchEligibleRoadmapIdAndTitle(tenant_id,  user_id):
        role = AuthDao.fetchRoleOfUserInTenant(user_id)
        print("fetchEligibleRoadmapIdAndTitle----", role)
        _filter = "" 
        if role == AuthRoles.ORG_DEMAND_REQUESTOR.name:
            _filter = f"and rr.created_by_id = {user_id}"
            
        if role == AuthRoles.ORG_DEMAND_MANAGER.name:
            portfolios_eligible = PortfolioDao.fetchApplicablePortfolios(user_id, tenant_id)
            portfolio_ids = []
            for p in portfolios_eligible:
                portfolio_ids.append(p["id"])
            portfolio_ids_str = f"({', '.join(map(str, portfolio_ids))})"
            _filter = f"and pp.id in {portfolio_ids_str}"
            
        query = f"""
            SELECT 
                rr.id AS roadmap_id,
                rr.title AS roadmap_title
            FROM 
                roadmap_roadmap rr
            LEFT JOIN 
                roadmap_roadmapportfolio rrp ON rr.id = rrp.roadmap_id
            LEFT JOIN 
                projects_portfolio pp ON rrp.portfolio_id = pp.id
            where rr.tenant_id = {tenant_id}
             {_filter}
            ORDER BY 
                rr.id ASC;
        """
        result = db_instance.retrieveSQLQueryOld(query)
        return result

    @staticmethod
    def fetchBusinessSponsorsOfRoadmaps(tenant_id: int, state: int, demand_queue: str):
        query = """
            SELECT DISTINCT ON (rr.id)
                rr.id AS roadmap_id,
                rr.title AS roadmap_title,
                rr.current_state,
                trc.title AS release_cycle_title,
                trc.start_date AS release_cycle_start_date,
                trc.end_date AS release_cycle_end_date,
                pb.sponsor_first_name AS first_name,
                pb.sponsor_last_name AS last_name,
                pb.sponsor_email AS email,
                pb.sponsor_role,
                pb.bu_name AS business_unit
            FROM roadmap_roadmap rr

            LEFT JOIN roadmap_roadmapreleasecycle rrcycle
                ON rr.id = rrcycle.roadmap_id
                AND rrcycle.tenant_id = rr.tenant_id

            LEFT JOIN tenant_release_cycles trc
                ON rrcycle.release_cycle_id = trc.id
                AND trc.tenant_id = rr.tenant_id

            LEFT JOIN roadmap_roadmapbusinessmember rrbm
                ON rrbm.roadmap_id = rr.id

            LEFT JOIN projects_portfoliobusiness pb
                ON pb.id = rrbm.portfolio_business_id
                AND pb.sponsor_role = 'Business Requester'

            WHERE rr.tenant_id = %s
            AND rr.current_state = %s
            AND trc.title ILIKE %s
            ORDER BY rr.id DESC
        """
        params = (
            tenant_id,
            state,
            f"%{demand_queue}%"
        )
        return db_instance.execute_query_safe(query, params)


    # @staticmethod
    # def fetchAllBusinessRequestorsWithZeroRoadmaps(tenant_id: int):
    #     query = """
    #         SELECT
    #             pb.id AS business_member_id,
    #             pb.sponsor_first_name AS first_name,
    #             pb.sponsor_last_name AS last_name,
    #             pb.sponsor_email AS email,
    #             pb.sponsor_role,
    #             pb.bu_name AS business_unit,
    #             COUNT(rr.id) AS roadmap_count
    #         FROM projects_portfoliobusiness pb
    #         LEFT JOIN roadmap_roadmapbusinessmember rrbm
    #             ON pb.id = rrbm.portfolio_business_id
    #         LEFT JOIN roadmap_roadmap rr
    #             ON rr.id = rrbm.roadmap_id
    #             AND rr.tenant_id = pb.tenant_id
    #         WHERE pb.tenant_id = %s
    #         AND pb.sponsor_role = 'Business Requester'
    #         GROUP BY
    #             pb.id,
    #             pb.sponsor_first_name,
    #             pb.sponsor_last_name,
    #             pb.sponsor_email,
    #             pb.sponsor_role,
    #             pb.bu_name
    #         HAVING COUNT(rr.id) = 0
    #         ORDER BY roadmap_count DESC
    #     """
    #     params = (tenant_id,)
    #     return db_instance.execute_query_safe(query, params)

    
    @staticmethod
    def fetchAllBusinessRequestorsWithZeroRoadmaps(tenant_id: int):

        query = """
            SELECT 
                uu.id,
                uu.email,
                uu.first_name,
                uu.last_name
            FROM authorization_userorgrolemap auom

            JOIN users_user uu 
                ON uu.id = auom.user_id

            LEFT JOIN roadmap_roadmap rr 
                ON rr.created_by_id = auom.user_id
                AND rr.tenant_id = auom.tenant_id

            WHERE auom.org_role_id IN (
                SELECT id 
                FROM authorization_orgroles 
                WHERE identifier = %s
                AND tenant_id = %s
            )

            AND rr.id IS NULL
            AND auom.deleted_on IS NULL
            AND uu.is_active = TRUE
            AND auom.tenant_id = %s
        """

        params = (
            'organization_demand_business_requester',
            tenant_id,
            tenant_id
        )

        return db_instance.execute_query_safe(query, params)
