"""
Data Engineer API controller.

Handles all /de/* endpoints:
  - Connections CRUD + test
  - Schema snapshot retrieval
  - Sessions list/detail
  - Runs list/detail
  - Ask (creates a run, fires agent in background thread)
"""
import traceback
import threading
from datetime import datetime, timezone

from flask import request, jsonify

from src.api.logging.AppLogger import appLogger
from src.database.Database import db_instance
from src.database.dao.data_engineer_dao import (
    DEConnectionDAO,
    DESchemaSnapshotDAO,
    DESessionDAO,
    DERunDAO,
)
from src.services.data_engineer.schema_introspection import (
    test_connection as _test_conn,
    introspect_schema,
)
from src.s3.s3 import S3Service
from src.utils.socketio_init import SocketInitializer


def _user_id() -> str:
    """Extract user_id from the decoded JWT on request."""
    decoded = getattr(request, "decoded", {})
    return str(decoded.get("user_id", "anonymous"))


def _decrypt(val: str) -> str:
    return db_instance.deanonymize_text_from_base64(val)


def _encrypt(val: str) -> str:
    return db_instance.encrypt_text_to_base64(val)


def _emit_step(run_id: str, step_type: str, message: str, **extra):
    """Emit a WebSocket agent_step event to the run's room."""
    try:
        sio = SocketInitializer().get_socketio()
        payload = {
            "type": step_type,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **extra,
        }
        sio.emit("agent_step", payload, room=run_id)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Connections
# ─────────────────────────────────────────────────────────────────────────────

class DataEngineerConnectionController:

    def list_connections(self):
        try:
            user_id = _user_id()
            rows = DEConnectionDAO.list_by_user(user_id)

            connections = []
            for row in rows:
                connections.append({
                    "id": row["id"],
                    "name": row["name"],
                    "host": _decrypt(row["host"]),
                    "port": row["port"],
                    "database": row["database"],
                    "username": _decrypt(row["username"]),
                    "ssl": row["ssl"],
                    "status": row["status"],
                    "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
                    "last_connected_at": row["last_connected_at"].isoformat() if row.get("last_connected_at") else None,
                    "table_count": row.get("table_count", 0),
                })
            return jsonify(connections), 200

        except Exception as e:
            appLogger.error({"event": "de_list_connections", "error": str(e), "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error"}), 500

    def get_connection(self, conn_id: str):
        try:
            user_id = _user_id()
            row = DEConnectionDAO.get_by_id(conn_id, user_id)
            if not row:
                return jsonify({"error": "Connection not found"}), 404

            table_count = DESchemaSnapshotDAO.get_table_count(conn_id)
            return jsonify({
                "id": row["id"],
                "name": row["name"],
                "host": _decrypt(row["host"]),
                "port": row["port"],
                "database": row["database"],
                "username": _decrypt(row["username"]),
                "ssl": row["ssl"],
                "status": row["status"],
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
                "last_connected_at": row["last_connected_at"].isoformat() if row.get("last_connected_at") else None,
                "table_count": table_count,
            }), 200

        except Exception as e:
            appLogger.error({"event": "de_get_connection", "conn_id": conn_id, "error": str(e), "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error"}), 500

    def create_connection(self):
        try:
            user_id = _user_id()
            body = request.get_json(force=True) or {}

            # Parse connection string if provided
            conn_str = body.get("connection_string", "")
            if conn_str:
                parsed = _parse_connection_string(conn_str)
                if parsed:
                    body = {**body, **parsed}

            name = body.get("name", "").strip()
            host = body.get("host", "").strip()
            port = int(body.get("port", 5432))
            database = body.get("database", "").strip()
            username = body.get("username", "").strip()
            password = body.get("password", "").strip()
            ssl = bool(body.get("ssl", True))

            if not all([name, host, database, username, password]):
                return jsonify({"error": "name, host, database, username, password are required"}), 400

            # Test connection before saving
            success, message, table_count = _test_conn(host, port, database, username, password, ssl)
            if not success:
                return jsonify({"error": f"Could not connect: {message}"}), 422

            # Save with encrypted credentials
            conn_id = DEConnectionDAO.create(
                user_id=user_id,
                name=name,
                host_enc=_encrypt(host),
                port=port,
                database=database,
                username_enc=_encrypt(username),
                password_enc=_encrypt(password),
                ssl=ssl,
            )

            # Run schema introspection in background (non-blocking)
            def _introspect_bg():
                try:
                    from src.services.data_engineer.schema_introspection import introspect_schema
                    schema_json = introspect_schema(host, port, database, username, password, ssl)
                    DESchemaSnapshotDAO.upsert(conn_id, schema_json, {"business_terms": {}, "suggested_questions": []})
                    DEConnectionDAO.update_status(conn_id, "active")
                except Exception as exc:
                    appLogger.error({"event": "de_introspect_bg_failed", "conn_id": conn_id, "error": str(exc)})
                    DEConnectionDAO.update_status(conn_id, "error")

            threading.Thread(target=_introspect_bg, daemon=True).start()

            return jsonify({
                "id": conn_id,
                "name": name,
                "host": host,
                "port": port,
                "database": database,
                "username": username,
                "ssl": ssl,
                "status": "active",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_connected_at": None,
                "table_count": table_count,
            }), 201

        except Exception as e:
            appLogger.error({"event": "de_create_connection", "error": str(e), "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error"}), 500

    def delete_connection(self, conn_id: str):
        try:
            user_id = _user_id()
            row = DEConnectionDAO.get_by_id(conn_id, user_id)
            if not row:
                return jsonify({"error": "Connection not found"}), 404

            DEConnectionDAO.delete(conn_id, user_id)
            return "", 204

        except Exception as e:
            appLogger.error({"event": "de_delete_connection", "conn_id": conn_id, "error": str(e), "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error"}), 500

    def test_saved_connection(self, conn_id: str):
        """Ping an already-saved connection."""
        try:
            user_id = _user_id()
            row = DEConnectionDAO.get_by_id_with_password(conn_id, user_id)
            if not row:
                return jsonify({"error": "Connection not found"}), 404

            host = _decrypt(row["host"])
            username = _decrypt(row["username"])
            password = _decrypt(row["password"])

            success, message, _ = _test_conn(host, row["port"], row["database"], username, password, row["ssl"])

            status = "active" if success else "error"
            DEConnectionDAO.update_status(conn_id, status)

            return jsonify({"success": success, "message": message}), 200

        except Exception as e:
            appLogger.error({"event": "de_test_saved_connection", "conn_id": conn_id, "error": str(e), "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error"}), 500

    def test_raw_connection(self):
        """Test connection from raw form data without saving."""
        try:
            body = request.get_json(force=True) or {}

            conn_str = body.get("connection_string", "")
            if conn_str:
                parsed = _parse_connection_string(conn_str)
                if parsed:
                    body = {**body, **parsed}

            host = body.get("host", "").strip()
            port = int(body.get("port", 5432))
            database = body.get("database", "").strip()
            username = body.get("username", "").strip()
            password = body.get("password", "").strip()
            ssl = bool(body.get("ssl", True))

            if not all([host, database, username, password]):
                return jsonify({"success": False, "message": "host, database, username, password are required"}), 200

            success, message, table_count = _test_conn(host, port, database, username, password, ssl)
            return jsonify({"success": success, "message": message, "table_count": table_count}), 200

        except Exception as e:
            appLogger.error({"event": "de_test_raw_connection", "error": str(e), "traceback": traceback.format_exc()})
            return jsonify({"success": False, "message": "Internal error during connection test"}), 200

    def get_schema(self, conn_id: str):
        """Return cached schema snapshot; introspect if none exists yet."""
        try:
            user_id = _user_id()
            row = DEConnectionDAO.get_by_id_with_password(conn_id, user_id)
            if not row:
                return jsonify({"error": "Connection not found"}), 404

            snapshot = DESchemaSnapshotDAO.get_current(conn_id)
            if not snapshot:
                # Introspect on-demand (blocking)
                host = _decrypt(row["host"])
                username = _decrypt(row["username"])
                password = _decrypt(row["password"])
                schema_json = introspect_schema(host, row["port"], row["database"], username, password, row["ssl"])
                DESchemaSnapshotDAO.upsert(conn_id, schema_json, {"business_terms": {}, "suggested_questions": []})
                snapshot = DESchemaSnapshotDAO.get_current(conn_id)

            schema_data = snapshot["schema_json"] or {}
            semantic = snapshot.get("semantic_layer") or {}

            return jsonify({
                "tables": _strip_sample_rows(schema_data.get("tables", [])),
                "relationships": schema_data.get("relationships", []),
                "suggested_questions": semantic.get("suggested_questions", []),
            }), 200

        except Exception as e:
            appLogger.error({"event": "de_get_schema", "conn_id": conn_id, "error": str(e), "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error"}), 500

    def refresh_schema(self, conn_id: str):
        """Force re-introspection, bypassing cache."""
        try:
            user_id = _user_id()
            row = DEConnectionDAO.get_by_id_with_password(conn_id, user_id)
            if not row:
                return jsonify({"error": "Connection not found"}), 404

            host = _decrypt(row["host"])
            username = _decrypt(row["username"])
            password = _decrypt(row["password"])

            schema_json = introspect_schema(host, row["port"], row["database"], username, password, row["ssl"])
            DESchemaSnapshotDAO.upsert(conn_id, schema_json, {"business_terms": {}, "suggested_questions": []})
            snapshot = DESchemaSnapshotDAO.get_current(conn_id)
            semantic = snapshot.get("semantic_layer") or {}

            return jsonify({
                "tables": _strip_sample_rows(schema_json.get("tables", [])),
                "relationships": schema_json.get("relationships", []),
                "suggested_questions": semantic.get("suggested_questions", []),
            }), 200

        except Exception as e:
            appLogger.error({"event": "de_refresh_schema", "conn_id": conn_id, "error": str(e), "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Sessions
# ─────────────────────────────────────────────────────────────────────────────

class DataEngineerSessionController:

    def list_sessions(self):
        try:
            user_id = _user_id()
            connection_id = request.args.get("connection_id")
            rows = DESessionDAO.list_by_user(user_id, connection_id)
            return jsonify([_format_session(r) for r in rows]), 200

        except Exception as e:
            appLogger.error({"event": "de_list_sessions", "error": str(e), "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error"}), 500

    def get_session(self, session_id: str):
        try:
            user_id = _user_id()
            row = DESessionDAO.get_by_id(session_id, user_id)
            if not row:
                return jsonify({"error": "Session not found"}), 404

            runs = DERunDAO.list_by_session(session_id)
            result = _format_session(row)
            result["runs"] = [_format_run(r) for r in runs]
            return jsonify(result), 200

        except Exception as e:
            appLogger.error({"event": "de_get_session", "session_id": session_id, "error": str(e), "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Runs + Ask
# ─────────────────────────────────────────────────────────────────────────────

class DataEngineerRunController:

    def get_run(self, run_id: str):
        try:
            row = DERunDAO.get_by_id(run_id)
            if not row:
                return jsonify({"error": "Run not found"}), 404
            return jsonify(_format_run(row)), 200

        except Exception as e:
            appLogger.error({"event": "de_get_run", "run_id": run_id, "error": str(e), "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error"}), 500

    def ask(self, conn_id: str):
        try:
            user_id = _user_id()
            body = request.get_json(force=True) or {}

            question = (body.get("question") or "").strip()
            if not question:
                return jsonify({"error": "question is required"}), 400

            # Verify connection belongs to user
            conn_row = DEConnectionDAO.get_by_id_with_password(conn_id, user_id)
            if not conn_row:
                return jsonify({"error": "Connection not found"}), 404

            # Get or create session
            session_id = body.get("session_id")
            if session_id:
                sess = DESessionDAO.get_by_id(session_id, user_id)
                if not sess:
                    return jsonify({"error": "Session not found"}), 404
            else:
                title = question[:60]
                session_id = DESessionDAO.create(user_id, conn_id, title)

            # Create pending run
            run_id = DERunDAO.create(session_id, conn_id, question)
            DESessionDAO.touch(session_id)

            # Kick off agent in background thread
            threading.Thread(
                target=_run_agent,
                args=(run_id, conn_id, session_id, question, conn_row),
                daemon=True,
            ).start()

            return jsonify({
                "id": run_id,
                "session_id": session_id,
                "question": question,
                "answer_text": "",
                "queries_executed": [],
                "status": "running",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }), 200

        except Exception as e:
            appLogger.error({"event": "de_ask", "conn_id": conn_id, "error": str(e), "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error"}), 500

    def download_sheet(self, run_id: str):
        try:
            row = DERunDAO.get_by_id(run_id)
            if not row:
                return jsonify({"error": "Run not found"}), 404
            if not row.get("sheet_s3_key"):
                return jsonify({"error": "No spreadsheet available for this run"}), 404

            url = S3Service().generate_presigned_url(row["sheet_s3_key"], expiry=3600)
            if not url:
                return jsonify({"error": "Could not generate download URL"}), 500

            return jsonify({"download_url": url, "expires_in": 3600}), 200

        except Exception as e:
            appLogger.error({"event": "de_download_sheet", "run_id": run_id, "error": str(e), "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Background agent runner (stub — wire in your SQL agent here)
# ─────────────────────────────────────────────────────────────────────────────

def _run_agent(run_id: str, conn_id: str, session_id: str, question: str, conn_row: dict):
    """
    Background thread: runs the DataEngineer agent, writes results to de_runs,
    and emits WebSocket events throughout.

    This is a stub — plug in your SQL agent in the TODO block below.
    """
    try:
        DERunDAO.mark_running(run_id)
        _emit_step(run_id, "planning", "Analysing your question and schema…")

        # ── Load schema context ──────────────────────────────────────────
        snapshot = DESchemaSnapshotDAO.get_current(conn_id)
        if not snapshot:
            DERunDAO.fail(run_id, "No schema snapshot found. Please refresh the connection schema first.")
            _emit_step(run_id, "error", "No schema snapshot found.")
            return

        schema_json = snapshot["schema_json"]
        semantic_layer = snapshot.get("semantic_layer") or {}

        # ── TODO: call SQL agent here ────────────────────────────────────
        # from src.services.data_engineer.sql_agent import run as run_sql_agent
        # result = run_sql_agent(
        #     question=question,
        #     schema_json=schema_json,
        #     semantic_layer=semantic_layer,
        #     host=db_instance.deanonymize_text_from_base64(conn_row["host"]),
        #     port=conn_row["port"],
        #     database=conn_row["database"],
        #     username=db_instance.deanonymize_text_from_base64(conn_row["username"]),
        #     password=db_instance.deanonymize_text_from_base64(conn_row["password"]),
        #     ssl=conn_row["ssl"],
        #     on_step=lambda stype, msg, **kw: _emit_step(run_id, stype, msg, **kw),
        # )
        # DERunDAO.complete(
        #     run_id,
        #     answer_text=result["answer_text"],
        #     queries_executed=result["queries_executed"],
        #     table_data=result["table_data"],
        #     chart_spec=result["chart_spec"],
        #     sheet_s3_key=result.get("sheet_s3_key"),
        # )
        # _emit_step(run_id, "done", "Analysis complete")
        # ── END TODO ─────────────────────────────────────────────────────

        # Placeholder until agent is wired in
        DERunDAO.fail(run_id, "SQL agent not yet implemented. Wire in src/services/data_engineer/sql_agent.py.")
        _emit_step(run_id, "error", "SQL agent not yet implemented.")

    except Exception as e:
        appLogger.error({"event": "de_run_agent", "run_id": run_id, "error": str(e), "traceback": traceback.format_exc()})
        try:
            DERunDAO.fail(run_id, str(e))
            _emit_step(run_id, "error", f"Unexpected error: {e}")
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _format_session(row: dict) -> dict:
    return {
        "id": row["id"],
        "connection_id": row["connection_id"],
        "connection_name": row.get("connection_name", ""),
        "title": row.get("title") or "",
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "last_active_at": row["last_active_at"].isoformat() if row.get("last_active_at") else None,
        "run_count": row.get("run_count", 0),
    }


def _format_run(row: dict) -> dict:
    sheet_url = None
    if row.get("sheet_s3_key"):
        try:
            sheet_url = S3Service().generate_presigned_url(row["sheet_s3_key"], expiry=3600)
        except Exception:
            pass

    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "question": row["question"],
        "answer_text": row.get("answer_text") or "",
        "queries_executed": row.get("queries_executed") or [],
        "table_data": row.get("table_data"),
        "chart_spec": row.get("chart_spec"),
        "sheet_download_url": sheet_url,
        "status": row["status"],
        "error_message": row.get("error_message"),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "completed_at": row["completed_at"].isoformat() if row.get("completed_at") else None,
    }


def _strip_sample_rows(tables: list) -> list:
    """Remove sample_rows from the public schema response (don't expose raw data)."""
    result = []
    for tbl in tables:
        t = dict(tbl)
        t.pop("sample_rows", None)
        result.append(t)
    return result


def _parse_connection_string(conn_str: str) -> dict | None:
    """
    Parse a postgres:// URI into individual fields.
    Format: postgresql://user:password@host:port/database
    """
    try:
        from urllib.parse import urlparse
        parsed = urlparse(conn_str)
        if parsed.scheme not in ("postgresql", "postgres"):
            return None
        return {
            "host": parsed.hostname or "",
            "port": parsed.port or 5432,
            "database": parsed.path.lstrip("/") if parsed.path else "",
            "username": parsed.username or "",
            "password": parsed.password or "",
        }
    except Exception:
        return None
