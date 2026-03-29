from flask import Blueprint,request
from src.controller.qna import QnaController

qnaRoute = Blueprint("qna", __name__, url_prefix="/trmeric_ai")

controller = QnaController()


@qnaRoute.route("/qna", methods=["POST"])
def postQNAChat():
    return controller.postQnaChat()


@qnaRoute.route("/qna/fetch/<session_id>/<_type>", methods=["GET"])
def fetch_qna_chat(session_id, _type, **kwargs):

    kwargs.update(request.args.to_dict(flat=True))
    print("--debug fetch_qna_chat kwargs--------",kwargs)
    return controller.fetchQnaChat(session_id, _type,**kwargs)


@qnaRoute.route("/qna/fetch/prefill/<session_id>/<_type>", methods=["GET"])
def fetch_qna_chat_prefill(session_id, _type):
    return controller.fetchQnaChatPrefill(session_id, _type)
