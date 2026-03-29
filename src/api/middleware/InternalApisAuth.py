import time
import jwt
from flask import request
from functools import wraps
from src.api.logging.RequestLogger import requestLogger
from src.api.logging.AppLogger import appLogger
import traceback


class InternalApisAuth:
    @staticmethod
    def authenticate_and_log(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            request_info = {
                "event": "before_request",
                "method": request.method,
                "path": request.path,
                "data": request.get_data(as_text=True),
                "timestamp": time.time()
            }

            client_secret = request.headers.get("client-secret")
            if client_secret:
                try:
                    if client_secret == "MY_SECRET":
                        request_info['internal'] = "internal"
                except Exception as e:
                    appLogger.error({
                        "function": "InternalApisAuth",
                        "marker": "auth",
                        "error": e,
                        "traceback": traceback.format_exc()
                    })
                    request_info['error'] = str(e)
                    requestLogger.error(request_info)
                    return {"message": "Invalid token", "details": str(e)}, 401
            else:
                request_info['error'] = 'No client secret provided'
                requestLogger.warning(request_info)
                return {"message": "Authentication token is missing"}, 401

            requestLogger.info(request_info)
            return f(*args, **kwargs)

        return decorated_function
