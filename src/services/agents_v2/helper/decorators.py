from functools import wraps
from datetime import datetime
import time
from typing import Callable, Any
from src.api.logging.AppLogger import appLogger, fn_io_timer_logger
import traceback

from typing import Callable, TypeVar, ParamSpec
from functools import wraps

P = ParamSpec("P")
R = TypeVar("R")

def log_function_io_and_time(func: Callable[P, R]) -> Callable[P, R]:
    """
    A decorator to log function input parameters, output, and execution time.
    Logs are written using appLogger with tenant_id, user_id, and function details.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs) -> Any:
        # Get start time
        start_time = time.time()
        start_time_str = datetime.fromtimestamp(start_time).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # till ms

        # Prepare log context
        log_context = {
            "function": func.__name__,
            "start_time": start_time_str,
            "tenant_id": getattr(self, 'tenant_id', None),
            "user_id": getattr(self, 'user_id', None),
        }
        
        input_params = {
            "args": [str(arg) for arg in args],
            "kwargs": {k: str(v) for k, v in kwargs.items()}
        }

        try:
            # Execute the function
            result = func(self, *args, **kwargs)
            end_time = time.time()
            end_time_str = datetime.fromtimestamp(end_time).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # till ms

            # Calculate execution time
            execution_time = end_time - start_time
            
            # Log output and execution time
            fn_io_timer_logger.info({
                "end_time": end_time_str,
                **log_context,
                "input_params": input_params,
                "execution_time_seconds": round(execution_time, 4),
            })
            
            return result
            
        except Exception as e:
            # Log error details
            end_time = time.time()
            end_time_str = datetime.fromtimestamp(end_time).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

            execution_time = end_time - start_time
            fn_io_timer_logger.error({
                "end_time": end_time_str,
                **log_context,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "execution_time_seconds": round(execution_time, 4),
            })
            raise  # Re-raise the exception after logging
        
    return wrapper
