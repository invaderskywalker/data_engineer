from src.trmeric_database.dao import db_instance,AuthDao
from src.trmeric_api.logging.AppLogger import appLogger
import json
import traceback
from typing import List, Dict, Optional


class TenantDaoV2:
    
    ATTRIBUTE_MAP: Dict[str, Dict] = {
        # === Basic Fields ===
        "id": {"table": "cr", "column": "cr.id"},
        "first_name": {"table": "cr", "column": "cr.first_name"},
        "last_name": {"table": "cr", "column": "cr.last_name"},
        "role": {"table": "cr", "column": "cr.role"},
        "experience_in": {"table": "cr", "column": "cr.experience"},
        "experience_years": {"table": "cr", "column": "cr.experience_years"},
        "primary_skill": {"table": "cr", "column": "cr.primary_skill"},
        "skills": {"table": "cr", "column": "cr.skills"},
        "is_external": {"table": "cr", "column": "cr.is_external"},
        "availability_time": {"table": "cr", "column": "cr.availability_time"},
        "country": {"table": "cr", "column": "cr.country"},
        "trmeric_user_id": {"table": "cr", "column": "cr.trmeric_user_id"},

        # === Current allocation computed via subquery ===
        "current_allocation": {
            "table": "crt",
            "column": """COALESCE((
                SELECT SUM(crt2.allocation)
                FROM capacity_resource_timeline crt2
                WHERE crt2.resource_id = cr.id
                AND CURRENT_DATE BETWEEN crt2.start_date AND crt2.end_date
            ), 0) AS current_allocation""",
            "join": "",
            "group_by": False
        },

        # === Projects (Subquery with JSONB) ===
        "past_projects": {
            "table": "crt",
            "column": """COALESCE((
                SELECT jsonb_agg(p ORDER BY p->>'end_date' DESC)
                FROM (
                    SELECT DISTINCT jsonb_build_object(
                        'project_id', crt2.trmeric_project_id,
                        'project_name', crt2.project_name,
                        'allocation', crt2.allocation,
                        'start_date', crt2.start_date,
                        'end_date', crt2.end_date
                    ) AS p
                    FROM capacity_resource_timeline crt2
                    WHERE crt2.resource_id = cr.id
                    AND crt2.trmeric_project_id IS NOT NULL
                    AND crt2.end_date < CURRENT_DATE
                ) sub
            ), '[]'::jsonb) AS past_projects""",
            "join": "",
            "group_by": False
        },
        
        "current_projects": {
            "table": "crt",
            "column": """COALESCE((
                SELECT jsonb_agg(p ORDER BY p->>'start_date' ASC)
                FROM (
                    SELECT DISTINCT jsonb_build_object(
                        'project_id', crt2.trmeric_project_id,
                        'project_name', crt2.project_name,
                        'allocation', crt2.allocation,
                        'start_date', crt2.start_date,
                        'end_date', crt2.end_date
                    ) AS p
                    FROM capacity_resource_timeline crt2
                    WHERE crt2.resource_id = cr.id
                    AND crt2.trmeric_project_id IS NOT NULL
                    AND CURRENT_DATE BETWEEN crt2.start_date AND crt2.end_date
                ) sub
            ), '[]'::jsonb) AS current_projects""",
            "join": "",
            "group_by": False
        },
        
        "future_projects": {
            "table": "crt",
            "column": """COALESCE((
                SELECT jsonb_agg(p ORDER BY p->>'start_date' ASC)
                FROM (
                    SELECT DISTINCT jsonb_build_object(
                        'project_id', crt2.trmeric_project_id,
                        'project_name', crt2.project_name,
                        'allocation', crt2.allocation,
                        'start_date', crt2.start_date,
                        'end_date', crt2.end_date
                    ) AS p
                    FROM capacity_resource_timeline crt2
                    WHERE crt2.resource_id = cr.id
                    AND crt2.trmeric_project_id IS NOT NULL
                    AND crt2.start_date > CURRENT_DATE
                ) sub
            ), '[]'::jsonb) AS future_projects""",
            "join": "",
            "group_by": False
        },

        "all_roadmaps": {
            "table": "crt",
            "column": """COALESCE((
                SELECT jsonb_agg(p ORDER BY p->>'start_date' ASC)
                FROM (
                    SELECT DISTINCT jsonb_build_object(
                        'roadmap_id', crt2.trmeric_roadmap_id,
                        'roadmap_name', crt2.roadmap_name,
                        'allocation', crt2.allocation,
                        'start_date', crt2.start_date,
                        'end_date', crt2.end_date
                    ) AS p
                    FROM capacity_resource_timeline crt2
                    WHERE crt2.resource_id = cr.id
                    AND crt2.trmeric_roadmap_id IS NOT NULL
                ) sub
            ), '[]'::jsonb) AS all_roadmaps""",
            "join": "",
            "group_by": False
        },

        # === Org Team Info ===
        "org_team": {
            "table": "crg",
            "column": """COALESCE((
                SELECT jsonb_agg(o)
                FROM (
                    SELECT DISTINCT jsonb_build_object(
                        'team_id', crg.id,
                        'org_team', crg.name,
                        'leader_first_name', leader.first_name,
                        'leader_last_name', leader.last_name
                    ) AS o
                    FROM capacity_resource_group_mapping crgm
                    JOIN capacity_resource_group crg ON crgm.group_id = crg.id
                    LEFT JOIN capacity_resource leader ON crg.leader_id = leader.id
                    WHERE crgm.resource_id = cr.id
                ) sub
            ), '[]'::jsonb) AS org_team""",
            "join": "",
            "group_by": False
        },
        
        "portfolio": {
            "table": "pf",
            "column": """COALESCE((
                SELECT jsonb_agg(distinct jsonb_build_object(
                    'portfolio_id', pf.id,
                    'portfolio_name', pf.title,
                    'portfolio_leader_first_name', pf.first_name,
                    'portfolio_leader_last_name', pf.last_name
                ))
                FROM capacity_resource_portfolio crp
                JOIN projects_portfolio pf ON pf.id = crp.portfolio_id
                WHERE crp.resource_id = cr.id
            ), '[]'::jsonb) AS portfolio""",
            "join": "",
            "group_by": False
        },


        # === External Provider Info ===
        "provider_company_name": {
            "table": "cep",
            "column": "cep.company_name AS external_company_name",
            "join": """LEFT JOIN capacity_external_providers AS cep 
                        ON cep.id = cr.external_provider_id 
                        AND cr.is_external = TRUE""",
            "group_by": False
        },
        "provider_company_address": {
            "table": "cep",
            "column": "cep.address AS external_company_address",
            "join": """LEFT JOIN capacity_external_providers AS cep 
                        ON cep.id = cr.external_provider_id 
                        AND cr.is_external = TRUE""",
            "group_by": False
        },
        "provider_company_website": {
            "table": "cep",
            "column": "cep.company_website AS external_company_website",
            "join": """LEFT JOIN capacity_external_providers AS cep 
                        ON cep.id = cr.external_provider_id 
                        AND cr.is_external = TRUE""",
            "group_by": False
        },
    }

    @staticmethod
    def fetchResourceDataWithProjectionAttrs(
        tenant_id: int,
        projection_attrs: List[str] = ["id", "first_name", "last_name", "country"],
        resource_ids: Optional[List[int]] = None,
        name: Optional[str] = None,
        primary_skill: Optional[str] = None,
        skill_keyword: Optional[str] = None,
        role: Optional[str] = None,
        is_external: Optional[bool] = None,
        external_company_name: Optional[str] = None,
        org_team_name: Optional[str] = None,
        org_team_id: Optional[int] = None,
        min_allocation: Optional[float] = None,
        max_allocation: Optional[float] = None,
        available_only: bool = False,
        portfolio_ids: Optional[List[int]] = None,
    ):
        try:
            select_clauses, joins, group_by_clauses = [], set(), set()
            where_conditions = [f"cr.tenant_id = {tenant_id}", "cr.is_active = TRUE"]

            requires_aggregation = any(
                "jsonb_agg" in TenantDaoV2.ATTRIBUTE_MAP.get(attr, {}).get("column", "")
                for attr in projection_attrs
            )

            if "trmeric_user_id" not in projection_attrs:
                projection_attrs.append('trmeric_user_id')
            if "role" not in projection_attrs:
                projection_attrs.append('role')

            # === SELECT CLAUSES & JOINS ===
            for attr in projection_attrs:
                mapping = TenantDaoV2.ATTRIBUTE_MAP.get(attr)
                if not mapping:
                    continue
                select_clauses.append(mapping["column"])
                if mapping.get("join"):
                    joins.add(mapping["join"])

                col = mapping["column"].split(" AS ")[0].strip()
                if requires_aggregation and "(" not in col:
                    # group_by_clauses.add(col)
                    # Always group by cr.id + every plain column from cr that is selected
                    group_by_clauses.add("cr.id")                     # <-- THIS IS THE KEY
                    if "(" not in col and col.startswith("cr."):
                        group_by_clauses.add(col)
                    
                if "cep." in col:
                    group_by_clauses.add(col)

            # === FILTERS ===
            if resource_ids:
                where_conditions.append(f"cr.id IN ({', '.join(map(str, resource_ids))})")
            if name:
                # matches first_name, last_name, or combined name
                where_conditions.append(
                    f"(LOWER(cr.first_name || ' ' || cr.last_name) LIKE LOWER('%{name}%') "
                    f"OR LOWER(cr.first_name) LIKE LOWER('%{name}%') "
                    f"OR LOWER(cr.last_name) LIKE LOWER('%{name}%'))"
                )
            # if name:
            #     parts = name.strip().split()
            #     first_name_raw = parts[0]
            #     last_name_raw = " ".join(parts[1:]) if len(parts) > 1 else None

            #     encrypted_fn = db_instance.encrypt_text_to_base64(first_name_raw)
            #     encrypted_ln = db_instance.encrypt_text_to_base64(last_name_raw) if last_name_raw else None

            #     conditions = [f"cr.first_name ILIKE '%{encrypted_fn}%'"]
            #     if encrypted_ln:
            #         conditions.append(f"cr.last_name ILIKE '%{encrypted_ln}%'")

            #     where_conditions.append(f"({' OR '.join(conditions)})")
            #     print("--debug where_conditions name-----", where_conditions)


            if primary_skill:
                where_conditions.append(f"LOWER(cr.primary_skill) LIKE LOWER('%{primary_skill}%')")
            if skill_keyword:
                where_conditions.append(f"LOWER(cr.skills) LIKE LOWER('%{skill_keyword}%')")
            if role:
                where_conditions.append(f"LOWER(cr.role) LIKE LOWER('%{role}%')")
            if is_external is not None:
                where_conditions.append(f"cr.is_external = {str(is_external).lower()}")
            if available_only:
                where_conditions.append("(cr.availability_time IS NULL OR cr.availability_time > NOW())")
            if external_company_name:
                where_conditions.append(f"LOWER(cep.company_name) LIKE LOWER('%{external_company_name}%')")

            # === Org Team Filters ===
            if org_team_name:
                where_conditions.append(
                    f"cr.id IN (SELECT crgm.resource_id "
                    f"FROM capacity_resource_group_mapping crgm "
                    f"JOIN capacity_resource_group crg ON crgm.group_id = crg.id "
                    f"WHERE LOWER(crg.name) LIKE LOWER('%{org_team_name}%'))"
                )
            if org_team_id:
                where_conditions.append(
                    f"cr.id IN (SELECT crgm.resource_id FROM capacity_resource_group_mapping crgm WHERE crgm.group_id = {org_team_id})"
                )
                
            # === Portfolio Filters (array support) ===
            if portfolio_ids:
                ids = ", ".join(str(pid) for pid in portfolio_ids)
                where_conditions.append(
                    f"cr.id IN (SELECT resource_id FROM capacity_resource_portfolio WHERE portfolio_id IN ({ids}))"
                )

            # === Allocation Filters (uses computed current_allocation subquery) ===
            if min_allocation is not None:
                where_conditions.append(f"""(
                    SELECT SUM(crt2.allocation)
                    FROM capacity_resource_timeline crt2
                    WHERE crt2.resource_id = cr.id
                    AND CURRENT_DATE BETWEEN crt2.start_date AND crt2.end_date
                ) >= {min_allocation}""")

            if max_allocation is not None:
                where_conditions.append(f"""(
                    SELECT SUM(crt2.allocation)
                    FROM capacity_resource_timeline crt2
                    WHERE crt2.resource_id = cr.id
                    AND CURRENT_DATE BETWEEN crt2.start_date AND crt2.end_date
                ) <= {max_allocation}""")

            # === Assemble Query ===
            select_clause = ",\n                ".join(select_clauses)
            join_clause = "\n            ".join(j for j in joins if j)
            where_clause = " AND ".join(where_conditions)
            group_by_clause = (
                f"\n            GROUP BY {', '.join(sorted(group_by_clauses))}"
                if group_by_clauses and requires_aggregation
                else ""
            )

            query = f"""
                SELECT
                    {select_clause}
                FROM capacity_resource AS cr
                {join_clause}
                WHERE {where_clause}
                {group_by_clause};
            """

            print("fetchResourceDataWithProjectionAttrs query:\n", query)
            res = db_instance.retrieveSQLQueryOld(query)
            for row in res:
                capacity_role = row.get("role",None) or None
                is_trmeric_user = row.get("trmeric_user_id",None) or None
                row.pop('role',None)
                row.pop('trmeric_user_id',None)

                if not is_trmeric_user:
                    row['role'] = f"As {capacity_role} in potential, not a trmeric user"
                    continue
                trmeric_roles = AuthDao.fetchAllRolesOfUserInTenant(user_id=is_trmeric_user)
                print("-----debug role as user: ",capacity_role, ", in trmeric: ", trmeric_roles)
                row['role'] = f"A trmeric user as {(' ,').join(trmeric_roles)} & also managed in potential as {capacity_role}"
            return res

        except Exception as e:
            appLogger.error({
                "function": "fetchResourceDataWithProjectionAttrs",
                "error": str(e),
                "trace": traceback.format_exc(),
                "data": {
                    "tenant_id": tenant_id,
                    "projection_attrs": projection_attrs
                }
            })
            return []


    @staticmethod
    def fetch_company(tenant_id: int) -> list:
        try:
            query = f"""
                SELECT *
                FROM public.tenant_company
                WHERE tenant_id = {tenant_id} AND deleted_on IS NULL;
            """
            res = db_instance.retrieveSQLQueryOld(query)
            company_info = {}
            if not res or len(res) == 0:
                return company_info
            company_info["name"] = res[0].get("name","")
            company_info["url"] = res[0].get("company_url",None) or None
            company_info["desc"] = res[0].get("description",None) or None
            company_info["business_units"] = (", ").join(res[0].get("business_units",[])) or []
            company_info["culture_values"] = res[0].get('culture_values',None) or None
            company_info["management_team"] = res[0].get("management_team",[]) or [] 
            company_info["citations"] = res[0].get("citations",[]) or []
            # company_info["ref_docs"] = res[0].get("doc_ids",[]) or []
            return company_info
        
        except Exception as e:
            appLogger.error(f"[TenantDaoV2.fetch_company] tenant_id={tenant_id}, error={e}")
            return []

    @staticmethod
    def fetch_company_industry(tenant_id: int) -> list:
        try:
            query = f"""
                SELECT 
                    tci.id AS company_industry_id,
                    tci.industry_id,
                    ti.name AS industry_name,
                    ti.trends,
                    ti.value_chain,
                    ti.function_kpis,
                    tci.citations
                FROM public.tenant_companyindustry tci
                INNER JOIN public.tenant_industry ti 
                    ON tci.industry_id = ti.id
                WHERE tci.deleted_on IS NULL 
                AND ti.deleted_on IS NULL
                and tci.tenant_id = {tenant_id};
            """
            res = db_instance.retrieveSQLQueryOld(query)
            company_industry_info = {}
            if not res or len(res) == 0:
                return company_industry_info
            company_industry_info["industry"] = res[0].get("industry_name",None) or None
            company_industry_info["trends"] = (" ,").join(res[0].get('trends',[])) or []
            company_industry_info["value_chain"] = res[0].get("value_chain",[]) or None
            company_industry_info["kpi(s)"] = res[0].get("function_kpis",{}) or None
            company_industry_info["citations"] = res[0].get("citations",[]) or None

            return company_industry_info
            
        except Exception as e:
            appLogger.error(f"[TenantDaoV2.fetch_company_industry] tenant_id={tenant_id}, error={e}")
            return []

    @staticmethod
    def fetch_company_performance(tenant_id: int) -> list:
        try:
            query = f"""
                SELECT id, tenant_id, period, revenue, profit, funding_raised, investor_info, citations
                FROM public.tenant_companyperformance
                WHERE tenant_id = {tenant_id} AND deleted_on IS NULL;
            """
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error(f"[TenantDaoV2.fetch_company_performance] tenant_id={tenant_id}, error={e}")
            return []

    @staticmethod
    def fetch_competitor(tenant_id: int) -> list:
        try:
            query = f"""
                SELECT *
                FROM public.tenant_competitor
                WHERE tenant_id = {tenant_id} AND deleted_on IS NULL;
            """
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error(f"[TenantDaoV2.fetch_competitor] tenant_id={tenant_id}, error={e}")
            return []

    @staticmethod
    def fetch_enterprise_strategy(tenant_id: int, title= '') -> list:
        try:
            query = f"""
                SELECT 
                    es.id, 
                    es.tenant_id, 
                    es.title, 
                    es.doc_ids, 
                    es.created_by_id, 
                    es.updated_by_id, 
                    es.created_on, 
                    es.updated_on,
                    (
                        SELECT json_agg(
                            json_build_object(
                                'id', ss.id,
                                'section_name', ss.section_name,
                                'content', ss.content,
                                'structured_content', ss.structured_content,
                                'created_on', ss.created_on,
                                'updated_on', ss.updated_on
                            )
                        )
                        FROM public.tenant_strategysection ss
                        WHERE ss.strategy_id = es.id
                    ) as sections
                FROM public.tenant_enterprisestrategy es
                WHERE es.tenant_id = {tenant_id}
            """
            if title:
                query += f" AND es.title ILIKE '%{title}%'"
            query += " ORDER BY es.created_on DESC"

            results = db_instance.retrieveSQLQueryOld(query)
            for result in results:
                if result.get("doc_ids") and isinstance(result["doc_ids"], str):
                    result["doc_ids"] = json.loads(result["doc_ids"])
                if result.get("sections") and isinstance(result["sections"], str):
                    result["sections"] = json.loads(result["sections"])
                elif result.get("sections") is None:
                    result["sections"] = []

            enterprise_strategy = []
            for result in results:
                enterprise_strategy.append({
                    "title": result.get("title","") or None,
                    "sections": [{"name": s.get("section_name"),"content": s.get('content')} for s in result.get("sections",[])] or [],
                    "ref_docs": result.get("doc_ids",[]) or None,
                })
            return enterprise_strategy
        except Exception as e:
            appLogger.error({
                "function": "fetch_enterprise_strategy",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": tenant_id
            })
            return []

    @staticmethod
    def fetch_industry(industry_ids: list = [], name='') -> list:
        try:
            if industry_ids:
                ids_str = "{" + ",".join(map(str, industry_ids)) + "}"
                query = f"""
                    SELECT *
                    FROM public.tenant_industry
                    WHERE deleted_on IS NULL AND id = ANY('{ids_str}'::int[]);
                """
            elif name:
                query = f"""
                    SELECT *
                    FROM public.tenant_industry
                    WHERE deleted_on IS NULL AND name = '{name}';
                """
            else:
                query = """
                    SELECT *
                    FROM public.tenant_industry
                    WHERE deleted_on IS NULL;
                """
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error(f"[TenantDaoV2.fetch_industry] industry_ids={industry_ids}, error={e}")
            return []

    @staticmethod
    def fetch_social_media(tenant_id: int) -> list:
        try:
            query = f"""
                SELECT id, tenant_id, platform, handle, latest_posts, last_updated
                FROM public.tenant_socialmedia
                WHERE tenant_id = {tenant_id} AND deleted_on IS NULL;
            """
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error(f"[TenantDaoV2.fetch_social_media] tenant_id={tenant_id}, error={e}")
            return []

    @staticmethod
    def fetch_all_industries() -> list:
        try:
            query = f"""
                SELECT id, name as industry_name
                FROM public.tenant_industry
                WHERE deleted_on IS NULL
            """
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error(f"[TenantDaoV2.fetch_all_industries], error={e}")
            return []

    @staticmethod
    def fetch_trucible_customer_context(tenant_id):
        return {
            "company_info": TenantDaoV2.fetch_company(tenant_id=tenant_id),
            "customer_industry_info": TenantDaoV2.fetch_company_industry(tenant_id),
            "company_enterprise_strategy": TenantDaoV2.fetch_enterprise_strategy(tenant_id),
            # "competitors": TenantDaoV2.fetch_competitor(tenant_id)
        }


    @staticmethod
    def fetch_saved_templates(
        projection_attrs: List[str] = ["id", "category","markdown"],
        tenant_id: int = None,
        category: str = None,
        order_clause: str = None,
        only_active: bool = True,
        limit: int = 2,
    ):
        try:
            # Build SELECT clauses from projection
            select_clauses = []
            for attr in projection_attrs:
                if attr == "id":
                    select_clauses.append("t.id")
                elif attr == "category":
                    select_clauses.append("t.category")
                elif attr == "markdown":
                    select_clauses.append("t.template_structure->>'markdown' AS markdown")
                elif attr == "version":
                    select_clauses.append("(t.template_structure->>'version')::int AS version")
                elif attr == "is_active":
                    select_clauses.append("(t.template_structure->>'is_active')::boolean AS is_active")
                elif attr == "created_on":
                    select_clauses.append("t.created_on")
                elif attr == "file_id":
                    select_clauses.append("t.file_id")
                
                # Add more as needed

            if not select_clauses:
                select_clauses = ["t.id", "t.category", "t.template_structure->>'markdown' AS markdown"]

            select_clause_str = ",\n                ".join(select_clauses)

            # Build WHERE conditions
            where_conditions = [f"t.tenant_id = {tenant_id}"]

            if category:
                where_conditions.append(f"t.category ILIKE '%{category}%'")
            if only_active:
                where_conditions.append("(t.template_structure->>'is_active')::boolean = true")

            where_clause_str = "\n                AND ".join(where_conditions)

            # Order and limit
            order_by_clause = f"\n            {order_clause}" if order_clause else "\n            ORDER BY t.created_on DESC"
            limit_clause = f"\n            LIMIT {limit}" if limit else ""

            query = f"""
                SELECT 
                    {select_clause_str}
                FROM public.tenant_filetemplates AS t
                WHERE {where_clause_str}
                {order_by_clause}
                {limit_clause};
            """

            # print("fetch_saved_templates query:\n", query)
            raw_results = db_instance.retrieveSQLQueryOld(query)
            return raw_results
        except Exception as e:
            appLogger.error(f"[TenantDaoV2.fetch_saved_templates] tenant_id={tenant_id}, error={e}")
            return []


    @staticmethod
    def fetch_portfolio_context(
        tenant_id: int,
        portfolio_ids: Optional[List[int]] = None,
    ) -> Dict:
        """
            Fetch portfolio context entries scoped to tenant and optionally filtered
            by portfolio_ids and content_types.
        """
        try:
            fields = [
                "pc.id",
                "pc.portfolio_id",
                "pc.content_type",
                "pc.title",
                "pc.summary",
                "pc.source_type",
                "pc.created_on",
            ]
            fields.append("pc.content")
            fields.append("pc.doc_ids")
            fields.append("pc.citations")

            query = f"""
                SELECT {", ".join(fields)},  p.title AS portfolio_title
                FROM tenant_portfoliocontext pc
                JOIN projects_portfolio p
                    ON p.id = pc.portfolio_id
                WHERE pc.tenant_id = {tenant_id}
            """
            # ✅ portfolio filter (f-string, no refactor)
            if portfolio_ids:
                portfolio_ids_str = ",".join(str(pid) for pid in portfolio_ids)
                query += f" AND pc.portfolio_id IN ({portfolio_ids_str})"
                
            query += " ORDER BY pc.portfolio_id, pc.created_on DESC"
            raw_results = db_instance.retrieveSQLQueryOld(query)
            # ✅ GROUP BY portfolio_id (added logic only)
            grouped = {}
            for row in raw_results:
                pid = row["portfolio_id"]

                if pid not in grouped:
                    grouped[pid] = {
                        "portfolio_id": pid,
                        "portfolio_title": row.get("portfolio_title"),
                        "items": []
                    }

                grouped[pid]["items"].append({
                    "id": row["id"],
                    "content_type": row["content_type"],
                    "title": row["title"],
                    "summary": row["summary"],
                    "content": row["content"],
                    "source_type": row["source_type"],
                    "doc_ids": row["doc_ids"],
                    "citations": row["citations"],
                    "created_on": row["created_on"],
                })

            return {
                "portfolio_context": list(grouped.values())
            }

        except Exception as e:
            appLogger.error(
                f"[TenantDaoV2.fetch_portfolio_context] tenant_id={tenant_id}, error={e}"
            )
            return {
                "portfolio_context": []
            }
            