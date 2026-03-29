from flask import Blueprint
from src.trmeric_api.middleware.AuthandLogMiddleware import AuthAndLogMiddleware
from src.controller.super_agent_controller import SuperAgentController
from src.controller.super_agent_analytics import SuperAgentAnalyticsController
from src.trmeric_api.middleware.InternalApisAuth import InternalApisAuth


superAgentAIRoute = Blueprint(
    "super_agent",
    __name__,
    url_prefix="/trmeric_ai/super"
)

controller = SuperAgentController()
analytics_controller = SuperAgentAnalyticsController()

# ─────────────────────────────────────────────────────────────────
# ADMIN ANALYTICS ENDPOINTS
# ─────────────────────────────────────────────────────────────────

@superAgentAIRoute.route("/admin/analytics/overview", methods=["GET"])
@InternalApisAuth.authenticate_and_log
def analytics_overview():
    """
    High-level dashboard metrics.
    Query params: start_date, end_date, tenant_id, user_id
    """
    return analytics_controller.get_analytics_overview()


@superAgentAIRoute.route("/admin/analytics/timeline", methods=["GET"])
@InternalApisAuth.authenticate_and_log
def analytics_timeline():
    """
    Execution timeline with bucketing.
    Query params: start_date, end_date, tenant_id, user_id, granularity (hour/day/week)
    """
    return analytics_controller.get_execution_timeline()


@superAgentAIRoute.route("/admin/analytics/patterns", methods=["GET"])
@InternalApisAuth.authenticate_and_log
def analytics_patterns():
    """
    Step type distribution and success rates.
    Query params: start_date, end_date, tenant_id, user_id
    """
    return analytics_controller.get_pattern_distribution()


@superAgentAIRoute.route("/admin/analytics/users", methods=["GET"])
@InternalApisAuth.authenticate_and_log
def analytics_users():
    """
    Per-user activity breakdown.
    Query params: start_date, end_date, tenant_id, limit
    """
    return analytics_controller.get_user_analytics()


@superAgentAIRoute.route("/admin/analytics/runs/detailed", methods=["GET"])
@InternalApisAuth.authenticate_and_log
def analytics_run_details():
    """
    Paginated runs with full plan details.
    Query params: start_date, end_date, tenant_id, user_id, agent_name, page, per_page
    """
    return analytics_controller.get_detailed_runs()


@superAgentAIRoute.route("/admin/analytics/agents", methods=["GET"])
@InternalApisAuth.authenticate_and_log
def analytics_agents():
    """
    Performance breakdown by agent.
    Query params: start_date, end_date, tenant_id
    """
    return analytics_controller.get_agent_breakdown()


@superAgentAIRoute.route("/admin/analytics/failures", methods=["GET"])
@InternalApisAuth.authenticate_and_log
def analytics_failures():
    """
    Failure analysis and debugging.
    Query params: start_date, end_date, tenant_id, limit
    """
    return analytics_controller.get_failure_analysis()


@superAgentAIRoute.route("/admin/analytics/tenants", methods=["GET"])
@InternalApisAuth.authenticate_and_log
def analytics_tenants():
    """
    Overview of all tenants.
    Query params: start_date, end_date
    """
    return analytics_controller.get_tenant_overview()


# ─────────────────────────────────────────────────────────────────
# EXISTING ENDPOINTS (Sessions & Runs)
# ─────────────────────────────────────────────────────────────────

@superAgentAIRoute.route("/sessions", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def list_sessions():
    """Lists all session_ids for the user."""
    return controller.get_sessions()


@superAgentAIRoute.route("/sessions/<session_id>/runs", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def get_runs_for_session(session_id):
    """Lists all runs inside a session."""
    return controller.get_runs_for_session(session_id)


@superAgentAIRoute.route("/runs/<run_id>", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def get_run_overview(run_id):
    """High-level metadata of a run."""
    return controller.get_run_overview(run_id)


@superAgentAIRoute.route("/runs/<run_id>/steps", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def get_run_steps(run_id):
    """Ordered execution steps of a run."""
    return controller.get_run_steps(run_id)


@superAgentAIRoute.route("/runs/<run_id>/events", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def get_run_events(run_id):
    """Flat list of thought / research / reasoning events."""
    return controller.get_run_events(run_id)


@superAgentAIRoute.route("/runs/<run_id>/events/tree", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def get_run_events_tree(run_id):
    """Nested event tree (parent-child)."""
    return controller.get_run_events_tree(run_id)


@superAgentAIRoute.route("/artifacts/download", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def download_artifact():
    """Returns a presigned S3 URL for downloading an artifact."""
    return controller.get_artifact_download_url()


@superAgentAIRoute.route("/artifacts/preview", methods=["GET", "OPTIONS"])
@AuthAndLogMiddleware.authenticate_and_log
def preview_artifact():
    """Preview artifact in browser."""
    return controller.preview_artifact()
