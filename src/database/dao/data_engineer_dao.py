"""
DAOs for the Data Engineer feature.

Tables: de_connections, de_schema_snapshots, de_sessions, de_runs
All reads use db_instance.execute_query_safe (parameterized, post-processed).
All writes use db_instance.executeSQLQuery.
"""

import json
from typing import Optional
from src.utils.myjson import MyJSON
from src.database.Database import db_instance


# ─────────────────────────────────────────────────────────────────────────────
# Connections
# ─────────────────────────────────────────────────────────────────────────────

class DEConnectionDAO:

    @staticmethod
    def list_by_user(user_id: str):
        return db_instance.execute_query_safe(
            """
            SELECT
                c.id, c.name, c.host, c.port, c.database, c.username,
                c.ssl, c.status, c.created_at, c.last_connected_at,
                COALESCE(jsonb_array_length(s.schema_json->'tables'), 0) AS table_count
            FROM de_connections c
            LEFT JOIN LATERAL (
                SELECT schema_json FROM de_schema_snapshots
                WHERE connection_id = c.id AND is_current = TRUE
                LIMIT 1
            ) s ON TRUE
            WHERE c.user_id = %s
            ORDER BY c.created_at DESC
            """,
            (user_id,),
        )

    @staticmethod
    def get_by_id(conn_id: str, user_id: str):
        rows = db_instance.execute_query_safe(
            """
            SELECT id, name, host, port, database, username,
                   ssl, status, created_at, last_connected_at
            FROM de_connections
            WHERE id = %s AND user_id = %s
            """,
            (conn_id, user_id),
        )
        return rows[0] if rows else None

    @staticmethod
    def get_by_id_with_password(conn_id: str, user_id: str):
        rows = db_instance.execute_query_safe(
            """
            SELECT id, name, host, port, database, username, password,
                   ssl, status, created_at, last_connected_at
            FROM de_connections
            WHERE id = %s AND user_id = %s
            """,
            (conn_id, user_id),
        )
        return rows[0] if rows else None

    @staticmethod
    def create(
        user_id: str,
        name: str,
        host_enc: str,
        port: int,
        database: str,
        username_enc: str,
        password_enc: str,
        ssl: bool,
    ) -> str:
        result = db_instance.executeSQLQuery(
            """
            INSERT INTO de_connections
                (user_id, name, host, port, database, username, password, ssl, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active')
            RETURNING id
            """,
            (user_id, name, host_enc, port, database, username_enc, password_enc, ssl),
            fetch="one",
        )
        return str(result[0])

    @staticmethod
    def update_status(conn_id: str, status: str):
        db_instance.executeSQLQuery(
            "UPDATE de_connections SET status = %s WHERE id = %s",
            (status, conn_id),
        )

    @staticmethod
    def delete(conn_id: str, user_id: str):
        db_instance.executeSQLQuery(
            "DELETE FROM de_connections WHERE id = %s AND user_id = %s",
            (conn_id, user_id),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Schema Snapshots
# ─────────────────────────────────────────────────────────────────────────────

class DESchemaSnapshotDAO:

    @staticmethod
    def get_table_count(conn_id: str) -> int:
        rows = db_instance.execute_query_safe(
            """
            SELECT COALESCE(jsonb_array_length(schema_json->'tables'), 0) AS table_count
            FROM de_schema_snapshots
            WHERE connection_id = %s AND is_current = TRUE
            LIMIT 1
            """,
            (conn_id,),
        )
        return rows[0]["table_count"] if rows else 0

    @staticmethod
    def get_current(conn_id: str):
        rows = db_instance.execute_query_safe(
            """
            SELECT id, connection_id, schema_json, semantic_layer, created_at
            FROM de_schema_snapshots
            WHERE connection_id = %s AND is_current = TRUE
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (conn_id,),
        )
        return rows[0] if rows else None

    @staticmethod
    def upsert(conn_id: str, schema_json: dict, semantic_layer: dict):
        # Mark previous snapshots as not current
        db_instance.executeSQLQuery(
            "UPDATE de_schema_snapshots SET is_current = FALSE WHERE connection_id = %s",
            (conn_id,),
        )
        db_instance.executeSQLQuery(
            """
            INSERT INTO de_schema_snapshots (connection_id, schema_json, semantic_layer, is_current)
            VALUES (%s, %s, %s, TRUE)
            """,
            (conn_id, MyJSON.dumps(schema_json), MyJSON.dumps(semantic_layer)),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Sessions
# ─────────────────────────────────────────────────────────────────────────────

class DESessionDAO:

    @staticmethod
    def list_by_user(user_id: str, connection_id: Optional[str] = None):
        if connection_id:
            return db_instance.execute_query_safe(
                """
                SELECT
                    s.id, s.connection_id, c.name AS connection_name,
                    s.title, s.created_at, s.last_active_at,
                    COUNT(r.id) AS run_count
                FROM de_sessions s
                JOIN de_connections c ON c.id = s.connection_id
                LEFT JOIN de_runs r ON r.session_id = s.id
                WHERE s.user_id = %s AND s.connection_id = %s
                GROUP BY s.id, c.name
                ORDER BY s.last_active_at DESC
                """,
                (user_id, connection_id),
            )
        return db_instance.execute_query_safe(
            """
            SELECT
                s.id, s.connection_id, c.name AS connection_name,
                s.title, s.created_at, s.last_active_at,
                COUNT(r.id) AS run_count
            FROM de_sessions s
            JOIN de_connections c ON c.id = s.connection_id
            LEFT JOIN de_runs r ON r.session_id = s.id
            WHERE s.user_id = %s
            GROUP BY s.id, c.name
            ORDER BY s.last_active_at DESC
            """,
            (user_id,),
        )

    @staticmethod
    def get_by_id(session_id: str, user_id: str):
        rows = db_instance.execute_query_safe(
            """
            SELECT s.id, s.connection_id, c.name AS connection_name,
                   s.title, s.created_at, s.last_active_at
            FROM de_sessions s
            JOIN de_connections c ON c.id = s.connection_id
            WHERE s.id = %s AND s.user_id = %s
            """,
            (session_id, user_id),
        )
        return rows[0] if rows else None

    @staticmethod
    def create(user_id: str, connection_id: str, title: str) -> str:
        result = db_instance.executeSQLQuery(
            """
            INSERT INTO de_sessions (user_id, connection_id, title)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (user_id, connection_id, title),
            fetch="one",
        )
        return str(result[0])

    @staticmethod
    def touch(session_id: str):
        db_instance.executeSQLQuery(
            "UPDATE de_sessions SET last_active_at = NOW() WHERE id = %s",
            (session_id,),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Runs
# ─────────────────────────────────────────────────────────────────────────────

class DERunDAO:

    @staticmethod
    def list_by_session(session_id: str):
        return db_instance.execute_query_safe(
            """
            SELECT id, session_id, connection_id, question, answer_text,
                   queries_executed, table_data, chart_spec, sheet_s3_key,
                   status, error_message, created_at, completed_at
            FROM de_runs
            WHERE session_id = %s
            ORDER BY created_at ASC
            """,
            (session_id,),
        )

    @staticmethod
    def get_by_id(run_id: str):
        rows = db_instance.execute_query_safe(
            """
            SELECT id, session_id, connection_id, question, answer_text,
                   queries_executed, table_data, chart_spec, sheet_s3_key,
                   status, error_message, created_at, completed_at
            FROM de_runs
            WHERE id = %s
            """,
            (run_id,),
        )
        return rows[0] if rows else None

    @staticmethod
    def create(session_id: str, connection_id: str, question: str) -> str:
        result = db_instance.executeSQLQuery(
            """
            INSERT INTO de_runs (session_id, connection_id, question, status)
            VALUES (%s, %s, %s, 'pending')
            RETURNING id
            """,
            (session_id, connection_id, question),
            fetch="one",
        )
        return str(result[0])

    @staticmethod
    def mark_running(run_id: str):
        db_instance.executeSQLQuery(
            "UPDATE de_runs SET status = 'running' WHERE id = %s",
            (run_id,),
        )

    @staticmethod
    def fail(run_id: str, error_message: str):
        db_instance.executeSQLQuery(
            """
            UPDATE de_runs
            SET status = 'failed', error_message = %s, completed_at = NOW()
            WHERE id = %s
            """,
            (error_message, run_id),
        )

    @staticmethod
    def complete(
        run_id: str,
        answer_text: str,
        queries_executed: list,
        table_data: Optional[dict],
        chart_spec: Optional[dict],
        sheet_s3_key: Optional[str],
    ):
        db_instance.executeSQLQuery(
            """
            UPDATE de_runs
            SET status = 'completed',
                answer_text = %s,
                queries_executed = %s,
                table_data = %s,
                chart_spec = %s,
                sheet_s3_key = %s,
                completed_at = NOW()
            WHERE id = %s
            """,
            (
                answer_text,
                MyJSON.dumps(queries_executed),
                MyJSON.dumps(table_data) if table_data is not None else None,
                MyJSON.dumps(chart_spec) if chart_spec is not None else None,
                sheet_s3_key,
                run_id,
            ),
        )
