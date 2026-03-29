import logging
from logging.handlers import RotatingFileHandler

APPLICATION_LOG_PATH = "logs/application.log"
appHandler = RotatingFileHandler(
    APPLICATION_LOG_PATH, maxBytes=10*1024*1024, backupCount=10)
appHandler.setFormatter(logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s"))
appLogger = logging.getLogger("app_logger")
appLogger.setLevel(logging.INFO)
appLogger.addHandler(appHandler)



ERROR_LOG_PATH = "logs/error.log"
errorHandler = RotatingFileHandler(ERROR_LOG_PATH, maxBytes=10*1024*1024, backupCount=10)
errorHandler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
errorLogger = logging.getLogger("app_logger")
errorLogger.setLevel(logging.INFO)
errorLogger.addHandler(errorHandler)



DEBUG_LOG_PATH = "logs/debug.log"

debugHandler = RotatingFileHandler(
    DEBUG_LOG_PATH, maxBytes=100000, backupCount=1)
debugHandler.setFormatter(logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s"))

debugLogger = logging.getLogger("debugLogger")
debugLogger.setLevel(logging.INFO)
debugLogger.addHandler(debugHandler)


VERBOSE_LOG_PATH = "logs/verbose.log"

verboseHandler = RotatingFileHandler(
    VERBOSE_LOG_PATH, maxBytes=100000, backupCount=1)
verboseHandler.setFormatter(logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s"))

verboseLogger = logging.getLogger("verboseLogger")
verboseLogger.setLevel(logging.INFO)
verboseLogger.addHandler(verboseHandler)


FN_IO_TIMER_LOG_PATH = "logs/io_time.log"
fn_io_timer_handler = RotatingFileHandler(FN_IO_TIMER_LOG_PATH, maxBytes=10*1024*1024, backupCount=10)
fn_io_timer_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
fn_io_timer_logger = logging.getLogger("fn_io_timer_logger")
fn_io_timer_logger.setLevel(logging.INFO)
fn_io_timer_logger.addHandler(fn_io_timer_handler)


#################

# STATS_LOG_PATH = "logs/stats.log"

# appHandler1 = RotatingFileHandler(
#     STATS_LOG_PATH, maxBytes=100000, backupCount=1)
# appHandler1.setFormatter(logging.Formatter(
#     "%(asctime)s - %(levelname)s - %(message)s"))

# statsLogger = logging.getLogger("app_logger")
# statsLogger.setLevel(logging.INFO)
# statsLogger.addHandler(appHandler1)
