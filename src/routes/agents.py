from flask import Blueprint
from src.controller.agents import AgentsController
from src.trmeric_api.middleware.AuthandLogMiddleware import AuthAndLogMiddleware


trmericAIRoute = Blueprint("agents", __name__,
                        url_prefix="/trmeric_ai")

controller = AgentsController()


######## agents 

@trmericAIRoute.route("/agents/portfolios_management/portfolio/list", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def getPortfoiliosBudget():
    return controller.getPortfolioListWithBudgetInHierarchy()


@trmericAIRoute.route("/agents/portfolios_management/<category>", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def getAgentResponseForCategory(category):
    return controller.getAgentResponseForCategory(category)


@trmericAIRoute.route("/agents/portfolios_management/<category>/create/insight", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def createInsightForCategory(category):
    return controller.getPortfolioAgentInsightsForCategory( category)

@trmericAIRoute.route("/agents/spend/data/fetch", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def getSpendAnalysis():
    return controller.getRecentSpendAnalysis()

# @trmericAIRoute.route("/agents/send-mail", methods=["POST"])
# @AuthAndLogMiddleware.authenticate_and_log
# def sendMail():
#     return controller.send_mail()



@trmericAIRoute.route("/agents/portfolios_management/fetch/review_data", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def getProjectsReviewData():
    return controller.getProjectsReviewData()


@trmericAIRoute.route("/agents/fetch/file", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def fetchFileUploadedInAgent():
    return controller.fetchFileUploadedInAgent()


@trmericAIRoute.route("/agents/fetch/state", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def fetchStateFromAgent():
    return controller.fetchStateFromAgent()

@trmericAIRoute.route("/agents/fetch/schedule_agent_chat_full", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def fetchScheduleAgentChatFull():
    return controller.fetchScheduleAgentChatFull()

