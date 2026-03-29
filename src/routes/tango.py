from flask import Blueprint
from src.controller.tango import TangoController
from src.trmeric_api.middleware.AuthandLogMiddleware import AuthAndLogMiddleware


tangoRoutes = Blueprint("tango", __name__,
                        url_prefix="/trmeric_ai")

controller = TangoController()


@tangoRoutes.route("/tango", methods=["POST"])
def tangoChat():
    return controller.tangoChat()


@tangoRoutes.route("/tango/pin/initiate/chat", methods=["POST"])
def tangoPinboard():
    return controller.tangoPinboard()


### chat threads ##########

@tangoRoutes.route("/tango/chat/threads", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def fetchChatTitlesForUser():
    return controller.fetchChatTitlesForUser()

@tangoRoutes.route("/tango/chat/threads/<chat_id>", methods=["DELETE"])
@AuthAndLogMiddleware.authenticate_and_log
def deleteChatTitle(chat_id):
    return TangoController.deleteChatTitle(chat_id)

### / chat threads ##########



@tangoRoutes.route("/tango/collaboration/chats/<session_id>", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def fetchCollaborationChats(session_id):
    return controller.fetchCollaborationChats(session_id)


@tangoRoutes.route("/tango/onboarding/knowledge", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def fetchTangoOnboardingKnowledge():
    return controller.fetchTangoOnboardingKnowledge()


# for reinforcement learing
@tangoRoutes.route("/tango/reinforcement", methods=["GET", "POST"])
@AuthAndLogMiddleware.authenticate_and_log
def tangoRLLayer():
    return controller.tangoRLLayer()


@tangoRoutes.route("/tango/activity/fetch", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def fetchTangoActivity():
    return controller.tangoRecentActivity()




# @tangoRoutes.route("/internal/company_info", methods= ["POST"])
# def tangoCompanyInfo():
#     return controller.tangoCompanyInfo()
