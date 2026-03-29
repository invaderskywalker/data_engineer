from flask import Blueprint
from src.controller.project import ProjectController
from src.trmeric_api.middleware.AuthandLogMiddleware import AuthAndLogMiddleware


projectRoutesBP = Blueprint(
    "projectBP", __name__, url_prefix="/trmeric_ai/project")

controller = ProjectController()


@projectRoutesBP.route("/assist/key_accomplishments/<project_id>", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def tangoAssistCreateKeyAccomplishments(project_id):
    return controller.tangoAssistCreateKeyAccomplishments(project_id)


@projectRoutesBP.route("/assist/enhance/<assist_keyword>", methods=["POST"])
@AuthAndLogMiddleware.authenticate_and_log
def enhanceProjectCreateData(assist_keyword):
    return controller.enhanceProjectCreateData(assist_keyword)



@projectRoutesBP.route("/auto_create_project", methods=["POST"])
def autoCreateProjects():
    return controller.autoCreateProjects()


@projectRoutesBP.route("/create/org_strategies_for_tenant", methods=["POST"])
def update_projects_attributes_for_tenant():
    return controller.update_projects_attributes_for_tenant()


