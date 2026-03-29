from flask import Blueprint
from src.trmeric_api.middleware.AuthandLogMiddleware import AuthAndLogMiddleware
from src.controller.super_agent_controller import SuperAgentController

healthRoute = Blueprint(
    "health",
    __name__,
    url_prefix=""
)


# ─────────────────────────────────────────────
# Sessions (navigation level)
# ─────────────────────────────────────────────

@healthRoute.route("/health", methods=["GET"])
def checkHealth():
    return {"state": "healthy"}

