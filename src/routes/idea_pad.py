from flask import Blueprint
from src.controller.idea_pad import IdeaPadController
from src.trmeric_api.middleware.AuthandLogMiddleware import AuthAndLogMiddleware

ideaBP = Blueprint("idea_pad", __name__, url_prefix="/trmeric_ai/idea_pad")

controller = IdeaPadController()


@ideaBP.route("/create_ideas", methods=["POST"])
def generateIdeas():
    return controller.generateIdeas()


@ideaBP.route("/enhance_idea", methods=["POST"])
def enhanceIdea():
    return controller.enhanceIdea()


@ideaBP.route("/create_roadmap", methods=["POST"])
def createRoadmapFromIdea():
    return controller.createRoadmapFromIdea()


@ideaBP.route("/chats", methods=["GET"])
@AuthAndLogMiddleware.authenticate_and_log
def fetchUserIdeaChats():
    return controller.fetchUserIdeaChats()
