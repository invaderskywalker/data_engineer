from flask import Blueprint
from src.controller.potential import PotentialController
from src.trmeric_api.middleware.AuthandLogMiddleware import AuthAndLogMiddleware


potentialRoute = Blueprint("potential", __name__,
                        url_prefix="/trmeric_ai")

controller = PotentialController()


# API routes
# 1. List resources count in portfolios
# 2. Insights on resources availability for portfolios
# 3. Insights on the resources table 


# resource_id insights: oneliner insights
# skill mapping
# insights

@potentialRoute.route("/potential/skills/list", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def getResourcesSkillMapping():
    return controller.getResourcesSkillMapping()


@potentialRoute.route("/potential/create/insight", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def createPotentialInsights():
    return controller.createPotentialInsights()


@potentialRoute.route("/potential/resource_info/<resource_id>", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def createResourceInsights(resource_id):
    return controller.createResourceInsights(resource_id)


