

from src.database.ai_dao import DAO_REGISTRY
from typing import Dict, Any
from src.utils.helper.common import MyJSON

def build_llm_schema_summary(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converts DAO manifest into LLM-safe semantic schema hints.
    No SQL. No column names. No joins.
    """
    summary = {}

    for section, meta in manifest.items():
        summary[section] = {
            "description": meta.get("important_info_to_be_understood_by_llm"),
            "detailed_sql_mapping_with_fields_for_understanding": meta.get("sql_mapping", []),
        }

    return summary

def render_dao_schema_block(
    entity_key: str,
    dao_class,
) -> str:
    """
    Builds a readable LLM schema block for a DAO.
    """
    manifest = dao_class.get_available_attributes()
    schema_hint = build_llm_schema_summary(manifest)

    return f"""
    -----------------------------------------
    {entity_key.replace('_', ' ').title()} — Semantic Data Overview
    (For understanding what information exists, NOT how to query it)

    {MyJSON.dumps(schema_hint)}
    -----------------------------------------
    """

# Which agent function unlocks which DAO
AGENT_FN_TO_DAO_KEYS = {
    "fetch_projects_data_using_project_agent": ["project"],
    "fetch_roadmaps_data_using_roadmap_agent": ["roadmap"],
    "list_issues_aka_bug_enhancement": ["issues_aka_bug_enhancement"],

    # 🔥 Tango
    "fetch_tango_conversations": ["tango_conversation"],
    "fetch_tango_stats": ["tango_stats"],
}


def get_ai_dao_ability_details(allowed_fn_maps) -> str:
    """
    Builds LLM-readable DAO schema context
    based on which agent functions are allowed.
    """
    more_defs_ai_dao_parts = ""

    for fn_name in allowed_fn_maps:
        dao_keys = AGENT_FN_TO_DAO_KEYS.get(fn_name, [])

        for dao_key in dao_keys:
            dao_cls = DAO_REGISTRY.get(dao_key)
            if not dao_cls:
                continue

            more_defs_ai_dao_parts += render_dao_schema_block(
                entity_key=dao_key,
                dao_class=dao_cls,
            )

    return more_defs_ai_dao_parts



def clean_html_output(text: str) -> str:
    """
    Removes markdown code fences like ```html ... ```
    and returns pure HTML.
    """
    if not text:
        return text

    text = text.strip()

    # Case 1: ```html ... ```
    if text.startswith("```"):
        # remove starting ```
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
        
        # remove ending ```
        if text.endswith("```"):
            text = text[:-3]

    return text.strip()


