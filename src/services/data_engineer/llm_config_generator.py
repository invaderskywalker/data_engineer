"""
LLM Config Generator.

Takes a raw schema_json (from schema_introspection) and calls OpenAI GPT-4o to:
  1. Write a one-line description for each table and its columns.
  2. Generate a semantic layer: business term → SQL expression mappings.
  3. Generate 5-8 suggested starter questions for the user.

Returns the enriched schema_json (descriptions filled in) and a semantic_layer dict.
"""
import json
import os
import traceback

from openai import OpenAI
from dotenv import load_dotenv

from src.api.logging.AppLogger import appLogger

load_dotenv()
_client = OpenAI(api_key=os.getenv("OPENAI_KEY"))


def _schema_summary_for_llm(schema_json: dict, max_tables: int = 30) -> str:
    """Produce a compact text representation of the schema for the LLM prompt."""
    lines = []
    for tbl in schema_json.get("tables", [])[:max_tables]:
        cols = ", ".join(
            f"{c['name']} ({c['type']}{'  PK' if c['is_pk'] else ''}{'  FK→' + c['references'] if c.get('is_fk') else ''})"
            for c in tbl.get("columns", [])
        )
        lines.append(f"TABLE {tbl['name']} (~{tbl.get('row_count_estimate', 0):,} rows): {cols}")
    return "\n".join(lines)


def generate_config(schema_json: dict) -> tuple[dict, dict]:
    """
    Returns (enriched_schema_json, semantic_layer).

    enriched_schema_json — same shape as input but tables[].description is filled.
    semantic_layer — {
        "business_terms": {"revenue": "SUM(orders.total) WHERE status='completed'", ...},
        "suggested_questions": ["...", ...]
    }
    """
    schema_text = _schema_summary_for_llm(schema_json)

    prompt = f"""You are a senior data analyst. You have been given a PostgreSQL database schema.

SCHEMA:
{schema_text}

Your tasks:
1. Write a one-line plain-English description for EACH table. Be specific to what the data likely represents.
2. Identify 5-10 common business terms (e.g. "revenue", "active users", "churn rate") and write the SQL expression that computes each one from the schema. Only include terms that are clearly supported by the schema.
3. Generate 6 high-value natural-language questions a business user might ask about this data.

Respond in JSON only — no markdown fences — with this exact structure:
{{
  "table_descriptions": {{
    "<table_name>": "<one-line description>",
    ...
  }},
  "business_terms": {{
    "<term>": "<SQL expression>",
    ...
  }},
  "suggested_questions": [
    "<question 1>",
    ...
  ]
}}"""

    try:
        response = _client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        parsed = json.loads(content)
    except Exception as e:
        appLogger.error({
            "event": "de_llm_config_generator_failed",
            "error": str(e),
            "traceback": traceback.format_exc(),
        })
        # Fallback: return schema as-is with empty semantic layer
        return schema_json, {"business_terms": {}, "suggested_questions": []}

    # Enrich schema_json table descriptions
    table_descs = parsed.get("table_descriptions", {})
    enriched_tables = []
    for tbl in schema_json.get("tables", []):
        tbl_copy = dict(tbl)
        tbl_copy["description"] = table_descs.get(tbl["name"], "")
        enriched_tables.append(tbl_copy)

    enriched_schema = dict(schema_json)
    enriched_schema["tables"] = enriched_tables

    semantic_layer = {
        "business_terms": parsed.get("business_terms", {}),
        "suggested_questions": parsed.get("suggested_questions", []),
    }

    return enriched_schema, semantic_layer
