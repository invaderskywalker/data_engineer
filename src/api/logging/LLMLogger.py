import logging
import time
import json
from logging.handlers import RotatingFileHandler
import os
from .TimingLogger import start_timer, stop_timer
import uuid
from datetime import datetime
from src.s3.s3 import S3Service

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Set up the LLM logger
LLM_LOG_PATH = "logs/llm.log"
llm_handler = RotatingFileHandler(LLM_LOG_PATH, maxBytes=1000000, backupCount=5)
llm_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))

llmLogger = logging.getLogger("llm_logger")
llmLogger.setLevel(logging.INFO)
llmLogger.addHandler(llm_handler)

def truncate_text(text, max_length=1000):
    """Truncate text to specified length with ellipsis if needed"""
    if text and len(text) > max_length:
        return text[:max_length] + "..."
    return text

def log_llm_request(model_name, function_name, prompt, options, user_id=None, tenant_id=None):
    """Log an LLM request before it's sent"""
    timer_id = start_timer("llm_request", 
                           model=model_name, 
                           function=function_name, 
                           user_id=user_id, 
                           tenant_id=tenant_id)
    
    log_entry = {
        "event": "llm_request",
        "model": model_name,
        "function": function_name,
        "timestamp": time.time(),
        "prompt_preview": truncate_text(prompt),
        "max_tokens": options.max_tokens,
        "temperature": options.temperature,
        "user_id": user_id,
        "tenant_id": tenant_id
    }
    
    llmLogger.info(json.dumps(log_entry))
    
    # Store the complete prompt for S3 logging later
    requests_by_timer_id[timer_id] = {
        "timestamp": datetime.now().isoformat(),
        "model": model_name,
        "function": function_name,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "prompt": prompt,
        "options": options.__dict__
    }
    
    return timer_id

def log_llm_response(timer_id, response_text, prompt_tokens, completion_tokens, total_tokens):
    """Log an LLM response after it's received"""
    duration = stop_timer(timer_id)  # This also logs to the timing logger
    
    # Get the metadata from the stored request
    request_data = requests_by_timer_id.get(timer_id, {})
    function_name = request_data.get("function", "unspecified_function")
    user_id = request_data.get("user_id")
    tenant_id = request_data.get("tenant_id")
    
    log_entry = {
        "event": "llm_response",
        "function": function_name,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "duration_ms": round(duration * 1000, 2) if duration else None,
        "response_preview": truncate_text(response_text),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens
    }
    
    llmLogger.info(json.dumps(log_entry))
    
    # Save complete log to S3
    if timer_id in requests_by_timer_id:
        request_data = requests_by_timer_id[timer_id]
        save_complete_log_to_s3(
            request_data["tenant_id"],
            request_data["user_id"],
            request_data["function"],
            request_data["prompt"],
            response_text,
            prompt_tokens,
            completion_tokens,
            request_data["model"],
            request_data["options"]
        )
        # Clean up stored request data
        del requests_by_timer_id[timer_id]

# Dictionary to store request data by timer_id
requests_by_timer_id = {}

def save_complete_log_to_s3(tenant_id, user_id, function_name, prompt, response, prompt_tokens, completion_tokens, model, options):
    """Save complete LLM input/output to a text file and upload to S3"""
    if not tenant_id or not user_id:
        return  # Skip logging if tenant_id or user_id is missing
    
    try:
        # Generate a unique identifier
        unique_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create the log content
        log_content = f"""
========== LLM INTERACTION LOG ==========
Timestamp: {timestamp}
Tenant ID: {tenant_id}
User ID: {user_id}
Function: {function_name}
Model: {model}
Options: {json.dumps(options, indent=2)}

---------- PROMPT ----------
{prompt}

---------- RESPONSE ----------
{response}

---------- METRICS ----------
Prompt Tokens: {prompt_tokens}
Completion Tokens: {completion_tokens}
Total Tokens: {prompt_tokens + completion_tokens}
=======================================
"""
        
        # Create local file path
        logs_dir = "logs/complete_logs"
        os.makedirs(logs_dir, exist_ok=True)
        file_name = f"{tenant_id}_{user_id}_{function_name}_{timestamp}_{unique_id}.txt"
        local_path = os.path.join(logs_dir, file_name)
        
        # Write to local file
        with open(local_path, 'w') as f:
            f.write(log_content)
        
        # Upload to S3
        s3_key = f"llm_logs/{tenant_id}/{user_id}/{function_name}/{file_name}"
        s3_service = S3Service()
        # s3_service.upload_file(local_path, s3_key)
        
        # Clean up local file after successful upload
        os.remove(local_path)
        
    except Exception as e:
        llmLogger.error(f"Error saving complete log to S3: {str(e)}")
