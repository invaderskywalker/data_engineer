from flask import Blueprint
from src.controller.discovery import DiscoveryQnAController

discoveryQA = Blueprint("discovery", __name__, url_prefix="/trmeric_ai")

controller = DiscoveryQnAController()


@discoveryQA.route("/project_chat", methods=["POST"])
def projectChat():
    return controller.postDiscoveryAnswer()


@discoveryQA.route("/fetch/project_chat/<session_id>", methods=["GET"])
def fetchProjectChat(session_id):
    return controller.fetchDiscoveryChat(session_id)


@discoveryQA.route("/create_project_brief", methods=["POST"])
def createProjectBrief():
    return controller.createProjectBrief()
