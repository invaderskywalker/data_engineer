import time
import jwt
from flask import request, Response
from functools import wraps
from src.trmeric_api.logging.RequestLogger import requestLogger
from src.trmeric_api.logging.AppLogger import appLogger
import traceback

def _cors_preflight_response():
    response = Response(status=200)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    response.headers["Access-Control-Max-Age"] = "86400"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = (
        "Authorization, Content-Type, Tenant-User-Token"
    )
    return response

class AuthAndLogMiddleware:
    @staticmethod
    def authenticate_and_log(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.method == "OPTIONS":
                return _cors_preflight_response()
            # Log request
            request_info = {
                "event": "before_request",
                "method": request.method,
                "path": request.path,
                "data": request.get_data(as_text=True),
                "timestamp": time.time()
            }

            # Attempt to decode the JWT token from the headers
            tenant_user_token = request.headers.get("Tenant-User-Token")
            if tenant_user_token:
                try:
                    decoded = jwt.JWT().decode(tenant_user_token, do_verify=False)
                    request.decoded = decoded
                    request_info['decoded'] = decoded
                except Exception as e:
                    appLogger.error({
                        "function": "AuthAndLogMiddleware",
                        "marker": "auth",
                        "error": e,
                        "traceback": traceback.format_exc()
                    })
                    request_info['error'] = str(e)
                    requestLogger.error(request_info)
                    return {"message": "Invalid token", "details": str(e)}, 401
            else:
                request_info['error'] = 'No token provided'
                requestLogger.warning(request_info)
                return {"message": "Authentication token is missing"}, 401

            # Log the valid request
            requestLogger.info(request_info)

            # Proceed with the actual request
            return f(*args, **kwargs)

        return decorated_function
