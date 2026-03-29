from flask import Blueprint
from src.controller.pins import PinsController
from src.trmeric_api.middleware.AuthandLogMiddleware import AuthAndLogMiddleware


pinBoardRoute = Blueprint("pinboard", __name__, url_prefix="/trmeric_ai/pins/v2")
controller = PinsController()



@pinBoardRoute.route("/list", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def listPins():
    return controller.listPins()

