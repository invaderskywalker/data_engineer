from flask import Blueprint
from src.controller.roadmap import RoadmapController
from src.trmeric_api.middleware.AuthandLogMiddleware import AuthAndLogMiddleware


roadmapRoutesBP = Blueprint(
    "roadmapBP", __name__, url_prefix="/trmeric_ai/roadmap")

controller = RoadmapController()


@roadmapRoutesBP.route("/business_case/create", methods=["POST"])
@AuthAndLogMiddleware.authenticate_and_log
def businessCaseTemplateCreate():
    return controller.businessCaseTemplateCreate()


@roadmapRoutesBP.route("/business_case/create/financial", methods=["POST"])
@AuthAndLogMiddleware.authenticate_and_log
def businessCaseTemplateCreateFinancial():
    return controller.businessCaseTemplateCreateFinanial()


@roadmapRoutesBP.route("/creation/tracker/<roadmap_id>", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def roadmapCreationFlowTracker(roadmap_id):
    return controller.roadmapCreationFlowTracker(roadmap_id)


@roadmapRoutesBP.route("/insights/fetch", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def fetchRoadmapInsights():
    return controller.fetchRoadmapInsights()



@roadmapRoutesBP.route("/auto_create_roadmap", methods=["POST"])
def autoCreateRoadmaps():
    return controller.autoCreateRoadmaps()

