"""
DAO for Data Engineer tables: de_connections, de_schema_snapshots, de_sessions, de_runs.
Uses db_instance (Peewee/psycopg2 layer) for raw parameterised queries.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from src.database.Database import db_instance


class DEConnectionDAO:

    @staticmethod
    def create(user_id: str, name: str, host_enc: str, port: int, database: str,
               username_enc: str, password_enc: str, ssl: bool) -> str:
        conn_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        db_instance.executeSQLQuery(
            """
            INSERT INTO de_connections
                (id, user_id, name, host, port, database, username, password, ssl, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', %s)
            """,
            (conn_id, user_id, name, host_enc, port, database, username_enc, password_enc, ssl, now),
        )
        return conn_id

    @staticmethod
    def list_by_user(user_id: str) -> list:
        return db_instance.execute_query_safe(
            """
            SELECT id, user_id, name, host, port, database, username,
                   ssl, status, created_at, last_connected_at,
                   (SELECT COUNT(*) FROM de_schema_snapshots ss
                    WHERE ss.connection_id = c.id AND ss.is_current = true) AS table_count
            FROM de_connections c
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (user_id,),
        )

    @staticmethod
    def get_by_id(conn_id: str, user_id: str) -> Optional[dict]:
        rows = db_instance.execute_query_safe(
            """
            SELECT id, user_id, name, host, port, database, username,
                   ssl, status, created_at, last_connected_at
            FROM de_connections
            WHERE id = %s AND user_id = %s
            """,
            (conn_id, user_id),
        )
        return rows[0] if rows else None

    @staticmethod
    def get_by_id_with_password(conn_id: str, user_id: str) -> Optional[dict]:
        """Returns the row including the encrypted password (for internal use only)."""
        rows = db_instance.execute_query_safe(
            """
            SELECT id, user_id, name, host, port, database, username, password,
                   ssl, status, created_at, last_connected_at
            FROM de_connections
            WHERE id = %s AND user_id = %s
            """,
            (conn_id, user_id),
        )
        return rows[0] if rows else None

    @staticmethod
    def update_status(conn_id: str, status: str):
        db_instance.executeSQLQuery(
            "UPDATE de_connections SET status = %s, last_connected_at = %s WHERE id = %s",
            (status, datetime.now(timezone.utc), conn_id),
        )

    @staticmethod
    def delete(conn_id: str, user_id: str):
        db_instance.executeSQLQuery(
            "DELETE FROM de_connections WHERE id = %s AND user_id = %s",
            (conn_id, user_id),
        )


class DESchemaSnapshotDAO:

    @staticmethod
    def upsert(connection_id: str, schema_json: dict, semantic_layer: dict) -> str:
        import json
        # Mark old snapshots as stale
        db_instance.executeSQLQuery(
            "UPDATE de_schema_snapshots SET is_current = false WHERE connection_id = %s",
            (connection_id,),
        )
        snapshot_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        db_instance.executeSQLQuery(
            """
            INSERT INTO de_schema_snapshots (id, connection_id, schema_json, semantic_layer, is_current, created_at)
            VALUES (%s, %s, %s, %s, true, %s)
            """,
            (snapshot_id, connection_id, json.dumps(schema_json), json.dumps(semantic_layer), now),
        )
        return snapshot_id

    @staticmethod
    def get_current(connection_id: str) -> Optional[dict]:
        rows = db_instance.execute_query_safe(
            """
            SELECT id, connection_id, schema_json, semantic_layer, created_at
            FROM de_schema_snapshots
            WHERE connection_id = %s AND is_current = true
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (connection_id,),
        )
        return rows[0] if rows else None

    @staticmethod
    def get_table_count(connection_id: str) -> int:
        rows = db_instance.execute_query_safe(
            """
            SELECT schema_json
            FROM de_schema_snapshots
            WHERE connection_id = %s AND is_current = true
            ORDER BY created_at DESC LIMIT 1
            """,
            (connection_id,),
        )
        if not rows:
            return 0
        schema_json = rows[0].get("schema_json") or {}
        return len(schema_json.get("tables", []))


class DESessionDAO:

    @staticmethod
    def create(user_id: str, connection_id: str, title: Optional[str] = None) -> str:
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        db_instance.executeSQLQuery(
            """
            INSERT INTO de_sessions (id, user_id, connection_id, title, created_at, last_active_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (session_id, user_id, connection_id, title, now, now),
        )
        return session_id

    @staticmethod
    def get_by_id(session_id: str, user_id: str) -> Optional[dict]:
        rows = db_instance.execute_query_safe(
            """
            SELECT s.id, s.user_id, s.connection_id, c.name AS connection_name,
                   s.title, s.created_at, s.last_active_at,
                   COUNT(r.id) AS run_count
            FROM de_sessions s
            JOIN de_connections c ON c.id = s.connection_id
            LEFT JOIN de_runs r ON r.session_id = s.id
            WHERE s.id = %s AND s.user_id = %s
            GROUP BY s.id, c.name
            """,
            (session_id, user_id),
        )
        return rows[0] if rows else None

    @staticmethod
    def list_by_user(user_id: str, connection_id: Optional[str] = None) -> list:
        if connection_id:
            return db_instance.execute_query_safe(
                """
                SELECT s.id, s.user_id, s.connection_id, c.name AS connection_name,
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
            SELECT s.id, s.user_id, s.connection_id, c.name AS connection_name,
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
    def update_title(session_id: str, title: str):
        db_instance.executeSQLQuery(
            "UPDATE de_sessions SET title = %s WHERE id = %s",
            (title, session_id),
        )

    @staticmethod
    def touch(session_id: str):
        db_instance.executeSQLQuery(
            "UPDATE de_sessions SET last_active_at = %s WHERE id = %s",
            (datetime.now(timezone.utc), session_id),
        )


class DERunDAO:

    @staticmethod
    def create(session_id: str, connection_id: str, question: str) -> str:
        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        db_instance.executeSQLQuery(
            """
            INSERT INTO de_runs (id, session_id, connection_id, question, status, created_at)
            VALUES (%s, %s, %s, %s, 'pending', %s)
            """,
            (run_id, session_id, connection_id, question, now),
        )
        return run_id

    @staticmethod
    def get_by_id(run_id: str) -> Optional[dict]:
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
    def list_by_session(session_id: str) -> list:
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
    def mark_running(run_id: str):
        db_instance.executeSQLQuery(
            "UPDATE de_runs SET status = 'running' WHERE id = %s",
            (run_id,),
        )

    @staticmethod
    def complete(run_id: str, answer_text: str, queries_executed: list,
                 table_data: dict, chart_spec: dict, sheet_s3_key: Optional[str]):
        import json
        now = datetime.now(timezone.utc)
        db_instance.executeSQLQuery(
            """
            UPDATE de_runs
            SET status = 'done',
                answer_text = %s,
                queries_executed = %s,
                table_data = %s,
                chart_spec = %s,
                sheet_s3_key = %s,
                completed_at = %s
            WHERE id = %s
            """,
            (
                answer_text,
                json.dumps(queries_executed),
                json.dumps(table_data) if table_data else None,
                json.dumps(chart_spec) if chart_spec else None,
                sheet_s3_key,
                now,
                run_id,
            ),
        )

    @staticmethod
    def fail(run_id: str, error_message: str):
        now = datetime.now(timezone.utc)
        db_instance.executeSQLQuery(
            """
            UPDATE de_runs
            SET status = 'error', error_message = %s, completed_at = %s
            WHERE id = %s
            """,
            (error_message, now, run_id),
        )
