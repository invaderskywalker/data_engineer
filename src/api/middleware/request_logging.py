import time
from flask import request
import jwt
from src.trmeric_api.logging.RequestLogger import requestLogger


class RequestLoggingMiddleware:
    @staticmethod
    def log_request_info():
        tenant_user_token = dict(request.headers).get("Tenant-User-Token")
        decoded = ""
        if (
            ("project_chat" in request.path)
            or ("tango/chat/project" in request.path)
            or ("tango/chat/provider" in request.path)
            or ("trmeric_ai/tango" in request.path)
            or ("trmeric_ai/qna" in request.path)
            or ("trmeric_ai/provider" in request.path)
            or ("trmeric_ai/idea_pad" in request.path)
        ) and ("testing" not in request.path):
            if request.method != "OPTIONS":
                decoded = jwt.JWT().decode(tenant_user_token, do_verify=False)
                request.decoded = decoded

        request_info = {
            "event": "before_request",
            "method": request.method,
            "path": request.path,
            "data": request.get_data(as_text=True),
            "timestamp": time.time(),
            "decoded": decoded,
        }
        requestLogger.info(request_info)
