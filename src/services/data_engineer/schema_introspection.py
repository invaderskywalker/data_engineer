"""
Schema introspection service.

Connects to a user's Postgres database (read-only intent) using psycopg2,
queries information_schema and pg_stat_user_tables, then returns a structured
schema_json dict ready to be stored in de_schema_snapshots.
"""
import traceback
import psycopg2
import psycopg2.extras
from typing import Optional

from src.api.logging.AppLogger import appLogger


# ─── helpers ────────────────────────────────────────────────────────────────

def _build_dsn(host: str, port: int, database: str, username: str, password: str, ssl: bool) -> dict:
    return dict(
        host=host,
        port=port,
        dbname=database,
        user=username,
        password=password,
        connect_timeout=10,
        sslmode="require" if ssl else "disable",
        options="-c statement_timeout=30000",   # 30s hard limit
    )


def _open_conn(host: str, port: int, database: str, username: str, password: str, ssl: bool):
    dsn = _build_dsn(host, port, database, username, password, ssl)
    return psycopg2.connect(**dsn)


# ─── public interface ────────────────────────────────────────────────────────

def test_connection(host: str, port: int, database: str,
                    username: str, password: str, ssl: bool) -> tuple[bool, str, int]:
    """
    Returns (success, message, table_count).
    """
    try:
        conn = _open_conn(host, port, database, username, password, ssl)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")
        table_count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return True, f"Connected to {database} on {host}", table_count
    except Exception as e:
        appLogger.warning({"event": "de_test_connection_failed", "error": str(e)})
        return False, str(e), 0


def introspect_schema(host: str, port: int, database: str,
                      username: str, password: str, ssl: bool) -> dict:
    """
    Returns a schema_json dict:
    {
      "tables": [
        {
          "name": "...",
          "columns": [{name, type, nullable, is_pk, is_fk, references?}],
          "row_count_estimate": int,
          "sample_rows": [list of dicts, max 3],
          "description": ""   # filled in by LLM later
        }
      ],
      "relationships": [
        {"from": "table.col", "to": "table.col", "type": "many-to-one"}
      ]
    }
    """
    conn = _open_conn(host, port, database, username, password, ssl)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # ── 1. columns + PK info ─────────────────────────────────────────
        cur.execute("""
            SELECT
                c.table_name,
                c.column_name,
                c.data_type,
                c.is_nullable,
                CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END AS is_pk
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT ku.table_name, ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku
                  ON tc.constraint_name = ku.constraint_name
                 AND tc.table_schema    = ku.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = 'public'
            ) pk ON pk.table_name = c.table_name AND pk.column_name = c.column_name
            WHERE c.table_schema = 'public'
              AND c.table_name NOT IN (
                  SELECT viewname FROM pg_views WHERE schemaname = 'public'
              )
            ORDER BY c.table_name, c.ordinal_position
        """)
        col_rows = cur.fetchall()

        # ── 2. foreign keys ──────────────────────────────────────────────
        cur.execute("""
            SELECT
                kcu.table_name  AS from_table,
                kcu.column_name AS from_col,
                ccu.table_name  AS to_table,
                ccu.column_name AS to_col
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema    = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
             AND ccu.table_schema    = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = 'public'
        """)
        fk_rows = cur.fetchall()

        # ── 3. row count estimates ───────────────────────────────────────
        cur.execute("""
            SELECT relname AS table_name, n_live_tup AS row_count_estimate
            FROM pg_stat_user_tables
            WHERE schemaname = 'public'
        """)
        row_count_map = {r["table_name"]: r["row_count_estimate"] for r in cur.fetchall()}

        # ── build FK lookup ──────────────────────────────────────────────
        fk_lookup: dict[tuple, str] = {}
        relationships = []
        for fk in fk_rows:
            from_key = (fk["from_table"], fk["from_col"])
            ref = f"{fk['to_table']}.{fk['to_col']}"
            fk_lookup[from_key] = ref
            relationships.append({
                "from": f"{fk['from_table']}.{fk['from_col']}",
                "to": ref,
                "type": "many-to-one",
            })

        # ── build tables dict ────────────────────────────────────────────
        tables_map: dict[str, dict] = {}
        for row in col_rows:
            tname = row["table_name"]
            if tname not in tables_map:
                tables_map[tname] = {
                    "name": tname,
                    "columns": [],
                    "row_count_estimate": row_count_map.get(tname, 0),
                    "sample_rows": [],
                    "description": "",
                }
            fk_ref = fk_lookup.get((tname, row["column_name"]))
            tables_map[tname]["columns"].append({
                "name": row["column_name"],
                "type": row["data_type"],
                "nullable": row["is_nullable"] == "YES",
                "is_pk": bool(row["is_pk"]),
                "is_fk": fk_ref is not None,
                **({"references": fk_ref} if fk_ref else {}),
            })

        # ── 4. sample rows (max 3 per table) ────────────────────────────
        for tname in list(tables_map.keys())[:50]:   # cap at 50 tables for perf
            try:
                cur.execute(f'SELECT * FROM "{tname}" LIMIT 3')   # noqa: S608
                samples = cur.fetchall()
                tables_map[tname]["sample_rows"] = [dict(r) for r in samples]
            except Exception:
                pass   # ignore if table is not readable

        cur.close()
        conn.close()

        return {
            "tables": list(tables_map.values()),
            "relationships": relationships,
        }

    except Exception as e:
        conn.close()
        appLogger.error({
            "event": "de_introspect_schema_failed",
            "error": str(e),
            "traceback": traceback.format_exc(),
        })
        raise
