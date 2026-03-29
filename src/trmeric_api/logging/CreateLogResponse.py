from flask import (
    request,
)


def createLogResponseBody():
    responseInfo = {
        "event": "after_request",
        "method": request.method,
        "path": request.path,
        "status_code": 200,
        # "headers": dict(request.headers),
        "data": request.get_data(as_text=True),
        "response_body": "",
        "duration": None,
    }
    return responseInfo
