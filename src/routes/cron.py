from flask import Blueprint
from src.controller.cron import CronController
from src.controller.cronV2 import CronControllerV2
from src.trmeric_api.middleware.InternalApisAuth import InternalApisAuth

cronBP = Blueprint("cron", __name__, url_prefix="/trmeric_ai/cron")

controller = CronController()
controllerV2 = CronControllerV2()


@cronBP.route("/integration/update", methods=["POST"])
@InternalApisAuth.authenticate_and_log
def cronUpdateIntegration():
    return controller.integrationDataUpdate()


@cronBP.route("/integration/summary/update", methods=["POST"])
@InternalApisAuth.authenticate_and_log
def cronIntegrationSummaryUpdate():
    return controller.cronIntegrationSummaryUpdate()


@cronBP.route("/integration/user/update", methods=["POST"])
@InternalApisAuth.authenticate_and_log
def cronUpdateIntegrationUser():
    return controller.integrationDataUpdateUser()


@cronBP.route("/signal/create", methods=["POST"])
@InternalApisAuth.authenticate_and_log
def cronSignalCreate():
    return controller.signalCreate()


@cronBP.route("/daily/run", methods=["POST"])
@InternalApisAuth.authenticate_and_log
def dailyRunCron():
    return controller.dailyCronRun()

@cronBP.route("/hourly/run", methods=["POST"])
@InternalApisAuth.authenticate_and_log
def hourlyCronRun():
    return controller.hourlyCronRun()


@cronBP.route("/precache", methods=["POST"])
@InternalApisAuth.authenticate_and_log
def precacheForce():
    return controller.precache_force()


# @cronBP.route("/create/knowledge", methods=["POST"])
# @InternalApisAuth.authenticate_and_log
# def createKnowledge():
#     return controller.createKnowledge()

@cronBP.route("/create/knowledge/v1", methods=["POST"])
@InternalApisAuth.authenticate_and_log
def createKnowledge():
    return controller.createKnowledge()


@cronBP.route("/trigger_notif_mail", methods=["POST"])
# @InternalApisAuth.authenticate_and_log
def trigger_notif_mail():
    return controller.trigger_notif_mail()


@cronBP.route("/v2/run", methods=["POST"])
@InternalApisAuth.authenticate_and_log
def v2Run():
    return controllerV2.v2Run()


