

from flask import Blueprint
from src.controller.tango import TangoController
from src.trmeric_api.middleware.AuthandLogMiddleware import AuthAndLogMiddleware


internalRoutes = Blueprint("internal", __name__,
                        url_prefix="/trmeric_ai")

tangoController = TangoController()




@internalRoutes.route("/internal/company_info", methods= ["POST"])
def tangoCompanyInfo():
    return tangoController.tangoCompanyInfo()