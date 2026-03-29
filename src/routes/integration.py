from flask import Blueprint
from src.controller.integration import IntegrationController
from src.trmeric_api.middleware.AuthandLogMiddleware import AuthAndLogMiddleware


integrationRoute = Blueprint("integration", __name__,
                             url_prefix="/trmeric_ai/integration")

controller = IntegrationController()


@integrationRoute.route("/project/update", methods=["POST"])
def integrationUpdate():
    return controller.integrationUpdate()


@integrationRoute.route("/project/update/v2", methods=["POST"])
def integrationUpdateV2():
    return controller.integrationUpdateV2()


@integrationRoute.route("project/update/v3", methods=["POST"])
def integrationUpdateV3():
    return controller.integrationUpdateV3()


@integrationRoute.route("/refresh_token", methods=["POST"])
@AuthAndLogMiddleware.authenticate_and_log
def refreshIntegrationAccessToken():
    return controller.refreshIntegrationAccessToken()


@integrationRoute.route("/internal/refresh_token", methods=["POST"])
def internalRefreshIntegrationAccessToken():
    return controller.internalRefreshIntegrationAccessToken()


@integrationRoute.route("/fetch/projects/<integration_id>/<integration_type>/<resource_name>", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def fetchIntegrationSourceProjects(integration_id, integration_type, resource_name):
    return controller.fetchIntegrationSourceProjects(
        integration_id=integration_id,
        integration_type=integration_type,
        resource_name=resource_name
    )


@integrationRoute.route("/fetch/ado/info", methods=["POST"])
@AuthAndLogMiddleware.authenticate_and_log
def fetchAdoRequiredSources():
    return controller.fetchAdoRequiredSources()

# smartsheet fetch things -- sheet, workspace, folders


@integrationRoute.route("/fetch/smartsheet/<integration_type>/info", methods=["POST"])
@AuthAndLogMiddleware.authenticate_and_log
def fetchSmartsheetSources(integration_type):
    return controller.fetchSmartsheetSources(integration_type)


@integrationRoute.route("fetch/slack/<key>", methods=["POST"])
@AuthAndLogMiddleware.authenticate_and_log
def fetchSlackDataForIntegration(key):
    return controller.fetchSlackDataForIntegration(key)


#google drive resources : sheets, docs, pdfs, presentations,sheets
@integrationRoute.route("/fetch/drive/<type>/info", methods=["POST"])
@AuthAndLogMiddleware.authenticate_and_log
def fetchDriveRequiredSources(type):
    return controller.fetchGoogleDriveResourcesV2(type)


@integrationRoute.route("projects/fetch/<project_id>", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def fetchListforProjectIntegrations(project_id):
    return controller.fetchListforProjectIntegrations(project_id)



@integrationRoute.route("v2/project/data/fetch/<project_id>", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def fetchProjectDataforIntegration(project_id):
    return controller.fetchProjectDataforIntegration(project_id)



@integrationRoute.route("dummy/create", methods=["POST"])
@AuthAndLogMiddleware.authenticate_and_log
def createDummyDataAndIntegration():
    return controller.createDummyDataAndIntegration()



@integrationRoute.route("update_tr_data_from_integration", methods=["POST"])
@AuthAndLogMiddleware.authenticate_and_log
def updateTrmericDataFromIntegration():
    return controller.updateTrmericDataFromIntegration()


@integrationRoute.route("/<integration_type>/onprem/integrate", methods=["POST"])
@AuthAndLogMiddleware.authenticate_and_log
def integrateOnPrem(integration_type):
    return controller.integrateOnPrem(integration_type)

@integrationRoute.route("/<integration_type>/onprem/sources", methods=["POST"])
@AuthAndLogMiddleware.authenticate_and_log
def fetchOnPremSources(integration_type):
    return controller.fetchOnPremSources(integration_type)


@integrationRoute.route("/run_auto_status", methods=["POST"])
def run_auto_status():
    return controller.run_auto_status()
