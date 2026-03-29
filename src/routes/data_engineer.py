from flask import Blueprint
from src.api.middleware.AuthandLogMiddleware import AuthAndLogMiddleware
from src.controller.data_engineer_controller import (
    DataEngineerConnectionController,
    DataEngineerSessionController,
    DataEngineerRunController,
)

dataEngineerRoute = Blueprint("data_engineer", __name__, url_prefix="/de")

_conn = DataEngineerConnectionController()
_sess = DataEngineerSessionController()
_run  = DataEngineerRunController()


# ─── Connections ─────────────────────────────────────────────────────────────

@dataEngineerRoute.route("/connections", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def list_connections():
    return _conn.list_connections()


@dataEngineerRoute.route("/connections/<conn_id>", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def get_connection(conn_id):
    return _conn.get_connection(conn_id)


@dataEngineerRoute.route("/connections", methods=["POST"])
@AuthAndLogMiddleware.authenticate_and_log
def create_connection():
    return _conn.create_connection()


@dataEngineerRoute.route("/connections/<conn_id>", methods=["DELETE"])
@AuthAndLogMiddleware.authenticate_and_log
def delete_connection(conn_id):
    return _conn.delete_connection(conn_id)


@dataEngineerRoute.route("/connections/<conn_id>/test", methods=["POST"])
@AuthAndLogMiddleware.authenticate_and_log
def test_saved_connection(conn_id):
    return _conn.test_saved_connection(conn_id)


@dataEngineerRoute.route("/connections/test", methods=["POST"])
@AuthAndLogMiddleware.authenticate_and_log
def test_raw_connection():
    return _conn.test_raw_connection()


@dataEngineerRoute.route("/connections/<conn_id>/schema", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def get_schema(conn_id):
    return _conn.get_schema(conn_id)


@dataEngineerRoute.route("/connections/<conn_id>/schema/refresh", methods=["POST"])
@AuthAndLogMiddleware.authenticate_and_log
def refresh_schema(conn_id):
    return _conn.refresh_schema(conn_id)


# ─── Ask ─────────────────────────────────────────────────────────────────────

@dataEngineerRoute.route("/connections/<conn_id>/ask", methods=["POST"])
@AuthAndLogMiddleware.authenticate_and_log
def ask(conn_id):
    return _run.ask(conn_id)


# ─── Sessions ────────────────────────────────────────────────────────────────

@dataEngineerRoute.route("/sessions", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def list_sessions():
    return _sess.list_sessions()


@dataEngineerRoute.route("/sessions/<session_id>", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def get_session(session_id):
    return _sess.get_session(session_id)


# ─── Runs ─────────────────────────────────────────────────────────────────────

@dataEngineerRoute.route("/runs/<run_id>", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def get_run(run_id):
    return _run.get_run(run_id)


@dataEngineerRoute.route("/runs/<run_id>/download", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def download_sheet(run_id):
    return _run.download_sheet(run_id)
