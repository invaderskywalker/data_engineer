import logging
from logging.handlers import RotatingFileHandler


REQUEST_LOG_PATH = "logs/request.log"

requestHandler = RotatingFileHandler(REQUEST_LOG_PATH, maxBytes=100000, backupCount=1)
requestHandler.setFormatter(logging.Formatter("%(message)s"))


requestLogger = logging.getLogger("request_logger")
requestLogger.setLevel(logging.INFO)
requestLogger.addHandler(requestHandler)
