from src.api.logging.RequestLogger import requestLogger


def logResponseInfo(responseInfo):
    requestLogger.info(responseInfo)
