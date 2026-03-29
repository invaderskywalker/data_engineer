from flask import Blueprint # type: ignore
from src.controller.provider import ProviderController
from src.trmeric_api.middleware.AuthandLogMiddleware import AuthAndLogMiddleware


providerBP = Blueprint("provider", __name__, url_prefix="/trmeric_ai/provider")

controller = ProviderController()

@providerBP.route("/opportunity/update", methods=["POST"])
def updateOpportunityRoute():
    return controller.updateOpportunity()


@providerBP.route("/bbdb/text/enhance", methods=["POST"])
@AuthAndLogMiddleware.authenticate_and_log
def enhanceQuantumDataRoute():
    return controller.enhanceQuantumData()
