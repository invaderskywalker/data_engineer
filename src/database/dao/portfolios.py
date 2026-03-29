from src.database.Database import db_instance
from src.utils.enums import ALL_ROLES
from .auth import AuthDao
from src.utils.constants.base import PORTFOLIO_ATTRIBUTE_MAP


class PortfolioDao:
    @staticmethod
    def fetchPortfoliosOfTenant(tenant_id):
        query = f"""
        select id, title from projects_portfolio where tenant_id_id = {tenant_id}
        """
        return db_instance.retrieveSQLQueryOld(query)


    @staticmethod
    def fetchChildPortfoliosRecursive(tenant_id, parent_portfolio_ids):
        # Convert parent portfolio IDs to a comma-separated string for the IN clause
        parent_ids_str = ','.join(map(str, parent_portfolio_ids))
        
        query = f"""
            WITH RECURSIVE portfolio_hierarchy AS (
                -- Base case: Start with the parent portfolios
                SELECT 
                    pp.id,
                    pp.title,
                    pp.parent_id,
                    pp.first_name AS portfolio_leader_first_name,
                    pp.last_name AS portfolio_leader_last_name,
                    pp.tenant_id_id,
                    1 AS level
                FROM 
                    projects_portfolio pp
                WHERE 
                    pp.id IN ({parent_ids_str})
                    AND pp.tenant_id_id = {tenant_id}

                UNION ALL

                -- Recursive case: Find child portfolios up to 4 levels deep
                SELECT 
                    pp.id,
                    pp.title,
                    pp.parent_id,
                    pp.first_name AS portfolio_leader_first_name,
                    pp.last_name AS portfolio_leader_last_name,
                    pp.tenant_id_id,
                    ph.level + 1 AS level
                FROM 
                    projects_portfolio pp
                INNER JOIN 
                    portfolio_hierarchy ph ON pp.parent_id = ph.id
                WHERE 
                    pp.tenant_id_id = {tenant_id}
            ),
            portfolio_details AS (
                -- Aggregate project and roadmap counts, and test data flag
                SELECT 
                    ph.id,
                    ph.title,
                    ph.parent_id,
                    ph.portfolio_leader_first_name,
                    ph.portfolio_leader_last_name,
                    COUNT(DISTINCT wp.id) AS project_count,
                    COUNT(DISTINCT rrp.roadmap_id) AS roadmap_count,
                    MAX(CASE WHEN atd.id IS NOT NULL THEN 'true' ELSE 'false' END) AS is_test_data
                FROM 
                    portfolio_hierarchy ph
                LEFT JOIN workflow_projectportfolio wpp 
                    ON wpp.portfolio_id = ph.id
                LEFT JOIN workflow_project wp 
                    ON wp.id = wpp.project_id
                    AND wp.parent_id IS not NULL
                    AND wp.tenant_id_id = {tenant_id}
                LEFT JOIN 
                    roadmap_roadmapportfolio rrp ON rrp.portfolio_id = ph.id
                LEFT JOIN 
                    adminapis_test_data atd 
                    ON atd.table_pk = ph.id 
                    AND atd.table_name = 'portfolio'
                    AND atd.tenant_id = ph.tenant_id_id
                GROUP BY 
                    ph.id, 
                    ph.title, 
                    ph.parent_id, 
                    ph.portfolio_leader_first_name, 
                    ph.portfolio_leader_last_name
            )
            SELECT 
                id,
                title,
                parent_id,
                portfolio_leader_first_name,
                portfolio_leader_last_name,
                project_count,
                roadmap_count,
                is_test_data
            FROM 
                portfolio_details
            ORDER BY 
                id;
        """
        return db_instance.retrieveSQLQueryOld(query)


    @staticmethod
    def fetchPortfolioLeaders(user_id, tenant_id):
        query = f"""
            SELECT 
                p.id, 
                p.title,
                p.parent_id, 
                uu.avatar, 
                p.first_name AS portfolio_leader_first_name, 
                p.last_name AS portfolio_leader_last_name,
                COUNT(DISTINCT wp.id) AS project_count,
                COUNT(DISTINCT rrp.roadmap_id) AS roadmap_count
            FROM 
                projects_portfolio p
            LEFT JOIN 
                public.authorization_portfolioleadermap apl ON p.id = apl.portfolio_id
            LEFT JOIN 
                users_user uu ON uu.id = {user_id}
      
            LEFT JOIN workflow_projectportfolio wpp 
                ON wpp.portfolio_id = p.id
            LEFT JOIN workflow_project wp 
                ON wp.id = wpp.project_id
                AND wp.parent_id IS not NULL
                AND wp.tenant_id_id = {tenant_id}
                
            LEFT JOIN 
                roadmap_roadmapportfolio rrp ON rrp.portfolio_id = p.id
            WHERE 
                p.tenant_id_id = {tenant_id} 
                AND apl.user_id = {user_id}
            GROUP BY 
                p.id, p.title, uu.avatar, p.first_name, p.last_name
        """
        
        return db_instance.retrieveSQLQueryOld(query)

    
    @staticmethod
    def fetchApplicablePortfolios(user_id, tenant_id):
        # print("debug -- fetchApplicablePortfolios", user_id, tenant_id )
        role_of_user = AuthDao.fetchRoleOfUserInTenant(user_id)
        print("debug -- fetchApplicablePortfolios 2", role_of_user )
        portfolio_info = PortfolioDao.fetchFullPortfoliosInfoV2(tenant_id=tenant_id)
        # print("debug -- fetchApplicablePortfolios 3", portfolio_info )
        # print("debug -- fetchApplicablePortfolios cond", AuthRoles.ORG_LEADER.name )
        # if role_of_user == AuthRoles.ORG_ADMIN.name or role_of_user == AuthRoles.ORG_LEADER.name:
        #     return portfolio_info
        if (role_of_user in ALL_ROLES):
            # return portfolio_info
            portfolio_opl = PortfolioDao.fetchPortfolioLeaders(user_id=user_id,tenant_id=tenant_id)
            # print("debug -- fetchApplicablePortfolios 4", portfolio_opl )
          
            if len(portfolio_opl) > 0:
                # Extract parent portfolio IDs
                parent_portfolio_ids = [portfolio['id'] for portfolio in portfolio_opl]
                
                # Fetch child portfolios up to 4 levels deep
                child_portfolios = PortfolioDao.fetchChildPortfoliosRecursive(
                    # user_id=user_id,
                    tenant_id=tenant_id,
                    parent_portfolio_ids=parent_portfolio_ids
                )
                print("debug -- fetchChildPortfoliosRecursive", parent_portfolio_ids, child_portfolios)
                existing_ids = {p['id'] for p in portfolio_opl}
                portfolio_opl.extend([c for c in child_portfolios if c['id'] not in existing_ids])
                print("debug -- fetchApplicablePortfolios 5", portfolio_opl )
                return portfolio_opl
            else:
                return portfolio_info
        else:
            return []

    @staticmethod
    def fetchProjectIdsForPortfolio(portfolio_id):
        query = f"""
            SELECT 
                wp.id AS project_id,
                wp.title as project_title
            FROM 
                workflow_project wp
            JOIN 
                projects_portfolio pp ON wp.portfolio_id_id = pp.id
            WHERE 
                pp.id = {portfolio_id};
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchPortfoliosOfRoadmaps(tenant_id):
        query = f"""
            SELECT 
                pp.id,
                pp.title,
                ARRAY_AGG(rrp.roadmap_id) AS roadmap_ids
            FROM roadmap_roadmapportfolio AS rrp
            LEFT JOIN projects_portfolio AS pp ON pp.id = rrp.portfolio_id
            where pp.tenant_id_id = {tenant_id}
            GROUP BY pp.id, pp.title
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def fetchPortfoliosOfProjectsForTenant(tenant_id, projects_list=True):
        condition = ""
        if projects_list:
            condition = """
            ,ARRAY_AGG(wp.id) AS project_ids
            """
        query = f"""
            SELECT 
                pp.id AS portfolio_id,
                pp.title AS portfolio_title
                {condition}
            FROM 
                projects_portfolio pp
            LEFT JOIN 
                workflow_project wp ON wp.portfolio_id_id = pp.id
            WHERE 
                pp.tenant_id_id = {tenant_id}
                AND wp.archived_on IS NULL
                AND wp.parent_id is not NULL
            GROUP BY 
                pp.id, pp.title
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def fetchPortfolioDetailsForApplicableProjectsForUser(tenant_id, projects_list, projects_needed=True):
        if not projects_list:
            return
        project_id_str = f"({', '.join(map(str, projects_list))})"
        extra_projection = ""
        if projects_needed:
            extra_projection = ",  wp.id as project_id, wp.title as project_title"
        query = f"""
        select pp.id, pp.title as portfolio_title {extra_projection}
        from workflow_project as wp
        left JOIN projects_portfolio pp ON wp.portfolio_id_id = pp.id
        where wp.id in {project_id_str} AND pp.tenant_id_id = {tenant_id};
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            return None
    
    @staticmethod
    def fetchPortfolioIdAndTitle(tenantID,eligibleProjects):
        if not eligibleProjects:
            return
        _data = PortfolioDao.fetchPortfolioDetailsForApplicableProjectsForUser(tenant_id=tenantID, projects_list=eligibleProjects)
        # Use a dictionary to ensure unique portfolios based on `id`
        portfolio_details = {}
        for _d in _data:
            if _d["id"] not in portfolio_details:
                portfolio_details[_d["id"]] = {"id": _d["id"], "portfolio_title": _d["portfolio_title"]}

        # Convert the dictionary values to a JSON array (list of objects)
        return list(portfolio_details.values())
                
    
    def fetchullPortfoliosInfo(tenant_id):
        query = f"""
        select id, title, first_name as portfolio_leader_first_name, last_name as portfolio_leader_last_name
        from projects_portfolio where tenant_id_id = {tenant_id}
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    def fetchFullPortfoliosInfoV2(tenant_id):
        query = f"""
            SELECT 
                pp.id,
                pp.title,
                pp.parent_id,
                pp.first_name AS portfolio_leader_first_name,
                pp.last_name AS portfolio_leader_last_name,
                COUNT(DISTINCT wp.id) AS project_count,
                COUNT(DISTINCT rrp.roadmap_id) AS roadmap_count,
                MAX(CASE WHEN atd.id IS NOT NULL THEN 'true' ELSE 'false' END) AS is_test_data
            FROM 
                projects_portfolio pp
            LEFT JOIN 
                workflow_projectportfolio wpp ON wpp.portfolio_id = pp.id
            LEFT JOIN 
                workflow_project wp 
                ON wp.id = wpp.project_id
                AND wp.parent_id IS not NULL
                and wp.tenant_id_id = {tenant_id}
            LEFT JOIN 
                roadmap_roadmapportfolio rrp ON rrp.portfolio_id = pp.id
            LEFT JOIN
                    adminapis_test_data atd
                    ON atd.table_pk = pp.id
                AND atd.table_name = 'portfolio'
                AND atd.tenant_id = pp.tenant_id_id
           
            WHERE 
                pp.tenant_id_id = {tenant_id}
            GROUP BY 
                pp.id, pp.title, pp.first_name, pp.last_name
        """
        return db_instance.retrieveSQLQueryOld(query)
        
    
    # @staticmethod
    # def fetchApplicablePortfolios(user_id, tenant_id):
    #     print("debug -- fetchApplicablePortfolios", user_id, tenant_id )
    #     role_of_user = AuthDao.fetchRoleOfUserInTenant(user_id)
    #     print("debug -- fetchApplicablePortfolios 2", role_of_user )
    #     portfolio_info = PortfolioDao.fetchullPortfoliosInfo(tenant_id=tenant_id)
    #     print("debug -- fetchApplicablePortfolios 3", portfolio_info )
    #     if role_of_user == AuthRoles.ORG_ADMIN.name or role_of_user == AuthRoles.ORG_LEADER.name:
    #         return portfolio_info
    #     if role_of_user == AuthRoles.PORTFOLIO_LEADER.name:
    #         # return portfolio_info
    #         portfolio_opl = PortfolioDao.fetchPortfolioLeaders(user_id=user_id,tenant_id=tenant_id)
    #         print("debug -- fetchApplicablePortfolios 4", portfolio_opl )
    #         if len(portfolio_opl) > 0:
    #             return portfolio_opl
    #         else:
    #             return portfolio_info
    #     else:
    #         return []
        
        
        

    @staticmethod
    def fetchPortfoliosOfRoadmaps(tenant_id):
        query = f"""
            SELECT 
                pp.id,
                pp.title,
                ARRAY_AGG(rrp.roadmap_id) AS roadmap_ids
            FROM roadmap_roadmapportfolio AS rrp
            LEFT JOIN projects_portfolio AS pp ON pp.id = rrp.portfolio_id
            where pp.tenant_id_id = {tenant_id}
            GROUP BY pp.id, pp.title
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def fetchPortfoliosOfProjectsForTenant(tenant_id, projects_list=True):
        condition = ""
        if projects_list:
            condition = """
            ,ARRAY_AGG(wp.id) AS project_ids
            """
        query = f"""
            SELECT 
                pp.id AS portfolio_id,
                pp.title AS portfolio_title
                {condition}
            FROM 
                projects_portfolio pp
            LEFT JOIN 
                workflow_project wp ON wp.portfolio_id_id = pp.id
            WHERE 
                pp.tenant_id_id = {tenant_id}
                AND wp.archived_on IS NULL
                AND wp.parent_id is not NULL
            GROUP BY 
                pp.id, pp.title
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def getKeyResultsOfPortfolios(tenantID, eligibleProjects):
        project_id_str = f"({', '.join(map(str, eligibleProjects))})"
        query = f"""
        select pp.id, pp.title as portfolio_title,  ARRAY_AGG(wpkpi.name) AS key_results from workflow_project as wp
        left join workflow_projectkpi as wpkpi on wpkpi.project_id = wp.id
        left JOIN projects_portfolio pp ON wp.portfolio_id_id = pp.id
        where wp.id in {project_id_str} AND pp.tenant_id_id = {tenantID} 
        GROUP BY pp.id, pp.title;
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    
    @staticmethod
    def fetchPortfolioById(id):

        query = f"""
            SELECT 
                pp.id AS portfolio_id,
                pp.title AS portfolio_title
                
            FROM 
                projects_portfolio pp
            WHERE 
                pp.id = {id}
        """
        res = db_instance.retrieveSQLQueryOld(query)
        if len(res) > 0:
            return res[0]
        return None
    
    
    @staticmethod
    def fetchAllPortfoliosForProject(project_id,tenant_id):
        query = f"""
            SELECT pp.id, pp.title AS portfolio_title
            FROM workflow_projectportfolio wpp
            JOIN projects_portfolio pp ON wpp.portfolio_id = pp.id
            WHERE wpp.project_id = {project_id} 
            AND pp.tenant_id_id = {tenant_id};
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            return None
        
        
    @staticmethod
    def fetchAllPortfoliosForRoadmap(roadmap_id,tenant_id):
        query = f"""
        SELECT pp.id,pp.title as portfolio_title
        FROM roadmap_roadmapportfolio AS rrp
        JOIN projects_portfolio AS pp ON pp.id = rrp.portfolio_id
        WHERE pp.tenant_id_id = {tenant_id}
        AND rrp.roadmap_id = {roadmap_id}
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            return None
        
    @staticmethod
    def getPortfolioNameById(portfolio_id,tenant_id):
        query =f"""
        select id,title,parent_id,tango_analysis from projects_portfolio
        where id = {portfolio_id} and tenant_id_id = {tenant_id}
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            return None


    
    @staticmethod
    def fetchPortfolioContext(portfolio_ids: list[int],tenant_id: int, projection_attrs: list[str] = ["id","title"], take_child: bool = True):
        try:
            if not portfolio_ids:
                return []

            if not projection_attrs:
                projection_attrs = ["id", "title", "industry", "technology_stack","description", "business_goals", "kpis", "budgets", "sponsors","strategic_priorities"]

            select_clauses = []
            joins = set()
            group_by_clauses = set()

            for attr in projection_attrs:
                mapping = PORTFOLIO_ATTRIBUTE_MAP.get(attr)
                if not mapping:
                    continue
                select_clauses.append(mapping["column"])
                if "join" in mapping:
                    joins.add(mapping["join"])
                if mapping.get("group_by", True):
                    base_col = mapping["column"].split(" AS ")[0]
                    group_by_clauses.add(base_col)

            select_clause_str = ",\n                ".join(select_clauses)
            join_clause_str = "\n            ".join(joins)
            group_by_clause = f"\n            GROUP BY {', '.join(group_by_clauses)}" if group_by_clauses else ""

            portfolio_ids_str = ", ".join(map(str, portfolio_ids))

            parent_query = f"""
                SELECT 
                    {select_clause_str}
                FROM projects_portfolio AS p
                {join_clause_str}
                WHERE p.id IN ({portfolio_ids_str})
                AND p.tenant_id_id = {tenant_id}
                {group_by_clause};
            """

            # print("--debug portfoliocontext query------", parent_query)
            parent_rows = db_instance.retrieveSQLQueryOld(parent_query) or []
            if not take_child: #no subportfolio(s) info
                return parent_rows
            
            parent_map = {row["id"]: row for row in parent_rows}


            # print("--debug parent map------", parent_map)

            # 2️⃣ Fetch sub-portfolios (child + sub-child) for each parent
            results = []
            for pid in portfolio_ids:
                sub_query = f"""
                    WITH RECURSIVE sub_hierarchy AS (
                        SELECT 
                            id, title, description, industry, business_goals, technology_stack
                        FROM projects_portfolio
                        WHERE parent_id = {pid} AND tenant_id_id = {tenant_id}

                        UNION ALL

                        SELECT 
                            p.id, p.title, p.description, p.industry, p.business_goals, p.technology_stack
                        FROM projects_portfolio p
                        INNER JOIN sub_hierarchy sh ON p.parent_id = sh.id
                        WHERE p.tenant_id_id = {tenant_id}
                    )
                    SELECT * FROM sub_hierarchy;
                """
                sub_rows = db_instance.retrieveSQLQueryOld(sub_query) or []

                results.append({
                    "portfolio_id": pid,
                    "portfolio_info": parent_map.get(int(pid), {}),
                    "sub_portfolios": sub_rows
                })

            return results

        except Exception as e:
            print("--debug error in fetchPortfolioContext---------", str(e))
            return []