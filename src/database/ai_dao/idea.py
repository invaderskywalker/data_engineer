from typing import List, Dict, Any, Optional, Union

from src.database.Database import db_instance
from src.api.logging.AppLogger import appLogger

from .base import BaseDAOQueryBuilder
from .intel import FieldIntel


class IdeaDaoV3:
    """Modular, attribute-level DAO for idea / concept data (v3 unified schema exposure)."""

    # ==============================================================
    # FIELD REGISTRY
    # ==============================================================

    FIELD_REGISTRY = {

        # ----------------------------------------------------------
        # CORE
        # ----------------------------------------------------------
        "core": {
            "description": "Primary idea identity and metadata.",
            "table": "idea_concept",
            "alias": "ic",
            "fields": {
                "idea_id": "ic.id AS idea_id",
                "idea_title": "ic.title AS idea_title",
                "idea_description": "ic.elaborate_description AS idea_description",
                "idea_rank": "ic.rank AS idea_rank",
                "idea_budget": "ic.budget AS idea_budget",
                "start_date": "ic.start_date AS idea_start_date",
                "end_date": "ic.end_date",
                "owner": "ic.owner",
                "org_strategy_align": "ic.org_strategy_align",
                "category_str": "ic.category AS category_str",
                "objectives": "ic.objectives",
                "idea_created_at": "ic.created_on AS idea_created_at",
            },
            "intel": {
                # "idea_title": {"type": "text"},
                # "category": {"type": "text"},
                "idea_budget": {"type": "number"},
                "idea_rank": {"type": "number"},
                "start_date": {"type": "date"},
                "end_date": {"type": "date"},
                "created_on": {"type": "date"},
            },
        },

        # ----------------------------------------------------------
        # CONSTRAINTS
        # ----------------------------------------------------------
        "constraints": {
            "description": "Constraints attached to idea.",
            "table": "idea_conceptconstraints",
            "alias": "icc",
            "fields": {
                "idea_id": "icc.concept_id AS idea_id",
                "constraint_name": "icc.name AS constraint_name",
                "constraint_type": """CASE
                    WHEN icc.type = 1 THEN 'cost'
                    WHEN icc.type = 2 THEN 'risk'
                    WHEN icc.type = 3 THEN 'resource'
                    ELSE 'other'
                END AS constraint_type""",
            },
            "intel": {
                "constraint_type": {
                    "type": "enum",
                    "column": "icc.type",
                    "mapping": {
                        "cost": 1,
                        "risk": 2,
                        "resource": 3,
                        "other": 4,
                    }
                },
                "constraint_name": {"type": "text"},
            },
        },

        # ----------------------------------------------------------
        # KPIs
        # ----------------------------------------------------------
        "kpis": {
            "description": "KPIs associated with idea.",
            "table": "idea_conceptkpi",
            "alias": "ick",
            "fields": {
                "idea_id": "ick.concept_id AS idea_id",
                "kpi_title_str": "ick.title AS kpi_title_str",
                "weightage": "ick.weightage",
                "baseline_value": "ick.baseline_value",
            },
            "intel": {
                "kpi_title_str": {"type": "text"},
                "weightage": {"type": "number"},
                "baseline_value": {"type": "number"},
            },
        },

        # ----------------------------------------------------------
        # PORTFOLIOS
        # ----------------------------------------------------------
        "portfolios": {
            "description": "Portfolios associated with idea.",
            "table": "idea_conceptportfolio",
            "alias": "icp",
            "joins": [
                "JOIN projects_portfolio p ON icp.portfolio_id = p.id"
            ],
            "fields": {
                "idea_id": "icp.concept_id AS idea_id",
                "portfolio_id": "p.id AS portfolio_id",
                "portfolio_title": "p.title AS portfolio_title",
                # "portfolio_rank": "icp.portfolio_rank",
            },
        },

        # # ----------------------------------------------------------
        # # ROADMAPS
        # # ----------------------------------------------------------
        # "children_roadmaps": {
        #     "description": "Roadmaps derived from ideas",
        #     "table": "roadmap_roadmapideamap",
        #     "alias": "rim",
        #     "joins": [
        #         "JOIN roadmap_roadmap rm ON rim.roadmap_id = rm.id"
        #     ],
        #     "fields": {
        #         "idea_id": "rim.idea_id AS idea_id",
        #         "roadmap_id": "rm.id AS roadmap_id",
        #         "roadmap_title": "rm.title AS roadmap_title",
        #     },
        #     "intel": {
        #         "roadmap_title": {"type": "text"},
        #     },
        # },

        # ----------------------------------------------------------
        # BUSINESS MEMBERS
        # ----------------------------------------------------------
        "business_members": {
            "description": "Business sponsors linked to idea.",
            "table": "idea_conceptbusinessmember",
            "alias": "icbm",
            "joins": [
                "JOIN projects_portfoliobusiness pb ON icbm.portfolio_business_id = pb.id"
            ],
            "fields": {
                "idea_id": "icbm.concept_id AS idea_id",
                "sponsor_first_name": "pb.sponsor_first_name",
                "sponsor_last_name": "pb.sponsor_last_name",
            },
            "intel": {
                "sponsor_first_name": {"type": "pii_text"},
                "sponsor_last_name": {"type": "pii_text"},
            },
        },
    }

    # ==============================================================
    # CORE
    # ==============================================================

    @staticmethod
    def fetch_core(
        idea_ids: Optional[List[int]] = None,
        tenant_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        time_bucket: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> List[Dict]:

        meta = IdeaDaoV3._get_section("core")
        intel = meta.get("intel", {})
        all_fields = meta["fields"]

        where = ["ic.tenant_id = %s"]
        params: List[Any] = [tenant_id]

        if idea_ids:
            where.append("ic.id = ANY(%s)")
            params.append(idea_ids)

        normalized_filters = FieldIntel.normalize_filters(
            filters or {}, intel, all_fields, meta["alias"]
        )

        bucket_interval = bucket_field = bucket_alias_field = None
        if isinstance(time_bucket, dict):
            bucket_field = time_bucket.get("field", "created_on")
            bucket_interval = time_bucket.get("interval", "month")
            bucket_alias_field = time_bucket.get("alias") or bucket_field
        elif isinstance(time_bucket, str):
            bucket_field = "created_on"
            bucket_interval = time_bucket
            bucket_alias_field = bucket_field

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=meta["alias"],
            table_name=meta["table"],
            fields=all_fields,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
            order_by=order_by,
            limit=limit,
            time_bucket=bucket_interval,
            time_bucket_field=bucket_field,
            bucket_alias_field=bucket_alias_field,
        )

        results = db_instance.execute_query_safe(query, params_tuple)
        return FieldIntel.post_process(results, intel)

    # ==============================================================
    # EVIDENCE FETCHERS (ROADMAP STYLE)
    # ==============================================================

    @staticmethod
    def fetch_constraints(
        idea_ids: List[int],
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
    ) -> List[Dict]:

        meta = IdeaDaoV3._get_section("constraints")
        intel = meta.get("intel", {})
        all_fields = meta["fields"]

        where = ["icc.concept_id = ANY(%s)"]
        params = [idea_ids]

        normalized_filters = FieldIntel.normalize_filters(
            filters or {}, intel, all_fields, meta["alias"]
        )

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=meta["alias"],
            table_name=meta["table"],
            fields=all_fields,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
        )
        return db_instance.execute_query_safe(query, params_tuple)

    @staticmethod
    def fetch_kpis(
        idea_ids: List[int],
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
    ) -> List[Dict]:

        meta = IdeaDaoV3._get_section("kpis")
        all_fields = meta["fields"]

        where = ["ick.concept_id = ANY(%s)"]
        params = [idea_ids]

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=meta["alias"],
            table_name=meta["table"],
            fields=all_fields,
            selected_fields=fields,
            where_clauses=where,
            params=params,
        )
        return db_instance.execute_query_safe(query, params_tuple)

    @staticmethod
    def fetch_portfolios(
        idea_ids: List[int],
        fields: Optional[List[str]] = None,
    ) -> List[Dict]:

        meta = IdeaDaoV3._get_section("portfolios")
        all_fields = meta["fields"]

        where = ["icp.concept_id = ANY(%s)"]
        params = [idea_ids]

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=meta["alias"],
            table_name=meta["table"],
            joins=meta.get("joins"),
            fields=all_fields,
            selected_fields=fields,
            where_clauses=where,
            params=params,
        )
        return db_instance.execute_query_safe(query, params_tuple)

    @staticmethod
    def fetch_roadmaps(
        idea_ids: List[int],
        fields: Optional[List[str]] = None,
    ) -> List[Dict]:

        meta = IdeaDaoV3._get_section("children_roadmaps")
        all_fields = meta["fields"]

        where = ["rim.idea_id = ANY(%s)"]
        params = [idea_ids]

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=meta["alias"],
            table_name=meta["table"],
            joins=meta.get("joins"),
            fields=all_fields,
            selected_fields=fields,
            where_clauses=where,
            params=params,
        )
        return db_instance.execute_query_safe(query, params_tuple)

    @staticmethod
    def fetch_business_members(
        idea_ids: List[int],
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
    ) -> List[Dict]:

        meta = IdeaDaoV3._get_section("business_members")
        intel = meta.get("intel", {})
        all_fields = meta["fields"]

        where = ["icbm.concept_id = ANY(%s)"]
        params = [idea_ids]

        normalized_filters = FieldIntel.normalize_filters(
            filters or {}, intel, all_fields, meta["alias"]
        )

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=meta["alias"],
            table_name=meta["table"],
            joins=meta.get("joins"),
            fields=all_fields,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
        )

        results = db_instance.execute_query_safe(query, params_tuple)
        return FieldIntel.post_process(results, intel)

    # ==============================================================
    # INTERNAL
    # ==============================================================

    @staticmethod
    def _get_section(section: str) -> Dict[str, Any]:
        try:
            return IdeaDaoV3.FIELD_REGISTRY[section]
        except KeyError as exc:
            raise ValueError(f"Unknown idea section: {section}") from exc

    # ==============================================================
    # PUBLIC MANIFEST
    # ==============================================================

    @staticmethod
    def get_available_attributes() -> Dict[str, Any]:
        return IDEA_DATA_MANIFEST


# ==============================================================
# AUTO-GENERATE MANIFEST
# ==============================================================
IDEA_DATA_MANIFEST: Dict[str, Any] = {}

for section, meta in IdeaDaoV3.FIELD_REGISTRY.items():
    fn = getattr(IdeaDaoV3, f"fetch_{section}", None)
    if not fn:
        appLogger.warning(f"IdeaDaoV3: missing fetch_{section}")
        continue

    IDEA_DATA_MANIFEST[section] = {
        "dao_function": fn,
        "important_info_to_be_understood_by_llm": meta["description"],
        "description": meta["description"],
        "fields": list(meta["fields"].keys()),
        "sql_mapping": meta["fields"],
        "filters": meta.get("extra_filters", {}),
        "intel": meta.get("intel") or {},
    }
