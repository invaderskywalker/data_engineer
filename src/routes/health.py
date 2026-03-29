from flask import Blueprint

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

