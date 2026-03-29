from src.trmeric_database.Database import db_instance
from src.trmeric_api.logging.AppLogger import appLogger


class StatsDao:

    # -----------------------------
    # Core Helper
    # -----------------------------
    @staticmethod
    def _get_domain_stats(table_prefix: str):
        """
        Example prefixes:
            workflow_project
            workflow_roadmap
            workflow_idea
            workflow_portfolio
        """

        query = f"""
        WITH table_stats AS (
            SELECT
                relname,
                n_live_tup AS estimated_rows,
                pg_total_relation_size(relid) AS total_bytes
            FROM pg_stat_user_tables
            WHERE relname LIKE '%{table_prefix}%'
        ),
        column_counts AS (
            SELECT
                table_name,
                COUNT(*) AS column_count
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name LIKE '%{table_prefix}%'
            GROUP BY table_name
        )
        SELECT
            ts.relname AS table_name,
            ts.estimated_rows,
            ts.total_bytes,
            COALESCE(cc.column_count, 0) AS column_count
        FROM table_stats ts
        LEFT JOIN column_counts cc
            ON ts.relname = cc.table_name;
        """

        tables = db_instance.retrieveSQLQueryOld(query)

        total_rows = 0
        total_bytes = 0
        total_columns = 0

        for t in tables:
            total_rows += t.get("estimated_rows", 0) or 0
            total_bytes += t.get("total_bytes", 0) or 0
            total_columns += t.get("column_count", 0) or 0

        return {
            "table_count": len(tables),
            "tables": tables,
            "total_rows": total_rows,
            "total_bytes": total_bytes,
            "total_columns": total_columns
        }

    # -----------------------------
    # Tenant Count
    # -----------------------------
    @staticmethod
    def _get_tenant_count():
        query = "SELECT COUNT(*) AS tenant_count FROM tenant_tenant;"
        res = db_instance.retrieveSQLQueryOld(query)
        return res[0]["tenant_count"] if res else 1

    # -----------------------------
    # Public Domain APIs
    # -----------------------------
    @staticmethod
    def GetProjectStats():
        return StatsDao._build_domain_summary("workflow_project")

    @staticmethod
    def GetRoadmapStats():
        return StatsDao._build_domain_summary("roadmap_roadmap")

    @staticmethod
    def GetIdeaStats():
        return StatsDao._build_domain_summary("idea")

    @staticmethod
    def GetPortfolioStats():
        return StatsDao._build_domain_summary("portfolio")
    
    @staticmethod
    def GetCombinedStats():
        return {
            "Project": StatsDao.GetProjectStats(),
            "Roadmap": StatsDao.GetRoadmapStats(),
            "Idea": StatsDao.GetIdeaStats(),
            "Portfolio": StatsDao.GetPortfolioStats(),
        }
        
    # -----------------------------
    # Relationship Density Helper
    # -----------------------------
    @staticmethod
    def _get_relationship_density(prefix: str, parent_table: str, parent_id_col: str = "id"):
        query = f"""
        WITH parent_count AS (
            SELECT COUNT(*) AS total_parents
            FROM {parent_table}
        )
        SELECT
            s.relname AS table_name,
            s.n_live_tup AS estimated_rows,
            ROUND(
                s.n_live_tup::numeric / NULLIF(pc.total_parents, 0),
                2
            ) AS avg_rows_per_parent
        FROM pg_stat_user_tables s
        JOIN parent_count pc ON TRUE
        JOIN information_schema.columns c
            ON c.table_name = s.relname
        WHERE s.relname LIKE '%{prefix}%'
        AND c.column_name = '{parent_id_col}'
        AND c.table_schema = 'public'
        GROUP BY s.relname, s.n_live_tup, pc.total_parents
        ORDER BY avg_rows_per_parent DESC;
        """

        return db_instance.retrieveSQLQueryOld(query)


    # -----------------------------
    # Final Aggregation
    # -----------------------------
    @staticmethod
    def _build_domain_summary(prefix: str):
        try:
            tenant_count = StatsDao._get_tenant_count()
            domain_stats = StatsDao._get_domain_stats(prefix)

            total_rows = domain_stats["total_rows"]
            total_columns = domain_stats["total_columns"]
            avg_rows_per_tenant = total_rows / tenant_count if tenant_count else 0

            # -----------------------------
            # Relationship Density Logic
            # -----------------------------
            parent_table = None
            parent_id_col = None

            if prefix == "workflow_project":
                parent_table = "workflow_project"
                parent_id_col = "project_id"

            elif prefix == "roadmap_roadmap":
                parent_table = "roadmap_roadmap"
                parent_id_col = "roadmap_id"

            elif prefix == "idea":
                parent_table = "idea_concept"
                parent_id_col = "concept_id"

            elif prefix == "portfolio":
                parent_table = "portfolio"
                parent_id_col = "portfolio_id"

            relationship_density = []
            if parent_table and parent_id_col:
                relationship_density = StatsDao._get_relationship_density(
                    prefix=prefix,
                    parent_table=parent_table,
                    parent_id_col=parent_id_col
                )

            return {
                "domain_prefix": prefix,
                "tenant_count": tenant_count,
                "table_count": domain_stats["table_count"],
                "total_tables": domain_stats["tables"],

                "total_columns": total_columns,
                # "total_estimated_rows": total_rows,

                "avg_rows_per_tenant": avg_rows_per_tenant,
                "relationship_density": relationship_density
            }

        except Exception as e:
            appLogger.error(f"StatsDao error for {prefix}: {e}")
            return {}
