from typing import List, Dict, Any, Optional
from src.database.Database import db_instance
from src.api.logging.AppLogger import appLogger
from .base import BaseDAOQueryBuilder
from .intel import FieldIntel


class BugEnhancementDaoV3:
    """
    Modular, attribute-level DAO for Bugs & Enhancements.
    Designed for AI-driven semantic querying (Lite version).
    """

    FIELD_REGISTRY = {
        "core": {
            "description": "Bug and enhancement records with status, priority, ownership, and resolution.",
            "table": "tango_bugenhancement",
            "alias": "be",
            "joins": [
                "LEFT JOIN users_user au_assignee ON be.assigned_to_id = au_assignee.id",
                "LEFT JOIN users_user au_creator ON be.created_by_id = au_creator.id",
                "LEFT JOIN users_user au_resolver ON be.resolved_by_id = au_resolver.id",
            ],
            "fields": {
                # 🔑 Identity
                "bug_enhancement_id": "be.id AS bug_enhancement_id",
                "custom_id": "be.custom_id",
                "type": "be.type",
                "status": "be.status",
                "priority": "be.priority",

                # 📝 Content
                "title": "be.title",
                "description": "be.description",
                "resolution_description": "be.resolution_description",

                # 👤 People
                "assigned_to_first_name": "au_assignee.first_name AS assigned_to_first_name",
                "assigned_to_last_name": "au_assignee.last_name AS assigned_to_last_name",
                "created_by_first_name": "au_creator.first_name AS created_by_first_name",
                "created_by_last_name": "au_creator.last_name AS created_by_last_name",
                "resolved_by_first_name": "au_resolver.first_name AS resolved_by_first_name",
                "resolved_by_last_name": "au_resolver.last_name AS resolved_by_last_name",

                # 🕒 Dates
                "created_on": "be.created_on",
                "updated_on": "be.updated_on",

                # 🧾 Activity (keep but optional)
                "comments": "be.comments",
                "transaction_history": "be.transaction_history",
            },
            "intel": {
                "type": {
                    "type": "enum",
                    "column": "be.type",
                    "mapping": {"bug": "bug", "enhancement": "enhancement"},
                },
                "status": {
                    "type": "enum",
                    "column": "be.status",
                    "mapping": {
                        "open": "open",
                        "in progress": "in_progress",
                        "resolved": "resolved",
                        "closed": "closed",
                    },
                },
                "priority": {
                    "type": "enum",
                    "column": "be.priority",
                    "mapping": {
                        "low": "low",
                        "medium": "medium",
                        "high": "high",
                        "critical": "critical",
                    },
                },
                "title": {"type": "text"},
                "description": {"type": "text"},
                "resolution_description": {"type": "text"},

                # 👤 PII
                "assigned_to_first_name": {"type": "pii_text", "column": "au_assignee.first_name"},
                "assigned_to_last_name": {"type": "pii_text", "column": "au_assignee.last_name"},
                "created_by_first_name": {"type": "pii_text", "column": "au_creator.first_name"},
                "created_by_last_name": {"type": "pii_text", "column": "au_creator.last_name"},
                "resolved_by_first_name": {"type": "pii_text", "column": "au_resolver.first_name"},
                "resolved_by_last_name": {"type": "pii_text", "column": "au_resolver.last_name"},

                # 📅 Dates
                "created_on": {"type": "date"},
                "updated_on": {"type": "date"},

                # 🧾 JSON cleanup
                "transaction_history": {
                    "type": "json_clean",
                    "exclude_prefixes": ["session", "internal", "debug"],
                },
            },
        }
    }

    # =====================================================
    # CORE FETCH
    # =====================================================
    @staticmethod
    def fetch_core(
        bug_enhancement_ids: Optional[List[int]] = None,
        tenant_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        print("fetch core be -- ", filters)

        meta = BugEnhancementDaoV3._get_section("core")
        intel = meta.get("intel", {})
        all_fields = meta["fields"]

        where = ["be.tenant_id = %s"]
        params: List[Any] = [tenant_id]

        if bug_enhancement_ids:
            where.append("be.id = ANY(%s)")
            params.append(bug_enhancement_ids)

        normalized_filters = FieldIntel.normalize_filters(
            filters=filters or {},
            intel=intel,
            fields=all_fields,
            alias=meta["alias"]
        )

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=meta["alias"],
            table_name=meta["table"],
            joins=meta.get("joins") or [],
            fields=all_fields,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
            order_by=order_by,
            limit=limit,
        )

        results = db_instance.execute_query_safe(query, params_tuple)
        return FieldIntel.post_process(results, intel)


    # =====================================================
    # INTERNAL UTIL
    # =====================================================
    @staticmethod
    def _get_section(section: str) -> Dict[str, Any]:
        try:
            return BugEnhancementDaoV3.FIELD_REGISTRY[section]
        except KeyError as exc:
            raise ValueError(f"Unknown data section: {section}") from exc

    # =====================================================
    # PUBLIC SCHEMA EXPOSURE
    # =====================================================
    @staticmethod
    def get_available_attributes() -> Dict[str, Any]:
        return BUG_ENHANCEMENT_DATA_MANIFEST


# ==============================================================
# AUTO-GENERATE MANIFEST
# ==============================================================
BUG_ENHANCEMENT_DATA_MANIFEST: Dict[str, Any] = {}
for section, meta in BugEnhancementDaoV3.FIELD_REGISTRY.items():
    dao_fn = getattr(BugEnhancementDaoV3, f"fetch_{section}", None)
    if not dao_fn:
        continue

    BUG_ENHANCEMENT_DATA_MANIFEST[section] = {
        "dao_function": dao_fn,
        "description": meta["description"],
        "important_info_to_be_understood_by_llm": meta["description"],
        "fields": list(meta["fields"].keys()),
        "sql_mapping": meta["fields"],
        "filters": {},
    }
