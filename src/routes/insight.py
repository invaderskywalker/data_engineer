from flask import Blueprint
from src.controller.insight import InsightController

insightRoute = Blueprint("insight", __name__, url_prefix="/trmeric_ai")

controller = InsightController()


@insightRoute.route("/insight/project/update/<project_id>", methods=["POST"])
def createInsightForProjectUpdate(project_id):
    return controller.createInsightForProjectUpdate(project_id)
