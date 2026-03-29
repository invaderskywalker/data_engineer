## node_utils in same folder as base_agent which has class Super agent

import os
import json
from src.api.logging.AppLogger import appLogger, debugLogger
import subprocess
import tempfile
import os
import json
import traceback
from typing import Dict, Any
# ────────────────────────────────────────────────────────────
# NODE.JS EXECUTION UTILITY
# ────────────────────────────────────────────────────────────

def run_node_script(js_path: str, cwd: str) -> dict:
    """
    Runs a Node.js script using globally installed pptxgenjs.
    No per-workspace npm install needed.
    """
    try:
        # Point NODE_PATH to global modules so require("pptxgenjs") resolves
        env = os.environ.copy()
        global_node_modules = subprocess.run(
            ["npm", "root", "-g"],
            capture_output=True,
            text=True,
            timeout=10
        ).stdout.strip()
        env["NODE_PATH"] = global_node_modules

        result = subprocess.run(
            ["node", js_path],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=120,
            env=env
        )

        appLogger.info({
            "event": "node_script_executed",
            "returncode": result.returncode,
            "stdout": result.stdout[:500],
            "stderr": result.stderr[:500] if result.stderr else ""
        })

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "Node.js script timed out after 120 seconds"
        }
    except FileNotFoundError:
        return {
            "success": False,
            "stdout": "",
            "stderr": "node not found — ensure Node.js is installed in Docker image"
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e)
        }
        
        
def sanitize_js_strings(js_code: str) -> str:
    """
    Replace literal newlines inside JS string literals with \\n escape.
    The LLM occasionally wraps multi-line label text without escaping,
    which causes a SyntaxError and crashes Node.js.
    """
    result = []
    in_string = False
    quote_char = None
    i = 0

    while i < len(js_code):
        char = js_code[i]

        if not in_string:
            if char in ('"', "'"):
                in_string = True
                quote_char = char
            result.append(char)
        else:
            if char == '\\':
                result.append(char)
                i += 1
                if i < len(js_code):
                    result.append(js_code[i])
            elif char == quote_char:
                in_string = False
                quote_char = None
                result.append(char)
            elif char == '\n':
                # Literal newline inside string → replace with escape
                result.append('\\n')
            else:
                result.append(char)
        i += 1

    return ''.join(result)

