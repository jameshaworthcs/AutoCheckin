from flask import jsonify
from typing import Any, Optional
from datetime import datetime, timezone
import os
import json
import threading
from contextlib import contextmanager


def create_response(
    success: bool = True,
    data: Any = None,
    message: str = "",
    error: Optional[str] = None,
    status_code: int = 200,
) -> tuple:
    """
    Create a standardized API response
    """
    response = {"success": success, "message": message, "data": data}

    if error:
        response["error"] = error

    return jsonify(response), status_code


def get_utc_timestamp() -> str:
    """Get current UTC timestamp in ISO format with milliseconds"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def debug_log(message: str) -> None:
    """Print debug messages only when FLASK_DEBUG is enabled"""
    if os.getenv("FLASK_DEBUG") == "1":
        print(f"[DEBUG] {message}")


# Lock for synchronizing access to user.json
_user_data_lock = threading.Lock()
_USER_JSON_PATH = os.path.join("data", "user.json")

@contextmanager
def _lock_user_data():
    """Context manager to acquire and release the user data lock."""
    _user_data_lock.acquire()
    try:
        yield
    finally:
        _user_data_lock.release()

USER_FILE = "user.json"
LOG_LIMIT = 100 # Limit the number of log entries stored

def read_local_user_data():
    """Reads user data from user.json, creating the file with defaults if it doesn't exist."""
    if not os.path.exists(USER_FILE):
        # Create default structure if file doesn't exist
        default_data = {
            "email": "",
            "token": "",
            "codes_url": "",
            "codes_url_suffix": "api/app/active/yrk/cs/2", # Sensible default
            "last_session_refresh": None,
            "last_code_attempt": None,
            "available_untried_codes": [],
            "tried_codes": [],
            "logs": [] # Initialize logs array
        }
        write_local_user_data(default_data) # Write defaults
        return default_data
    try:
        with open(USER_FILE, "r") as f:
            data = json.load(f)
            # Ensure essential keys exist, add if missing
            if "email" not in data: data["email"] = ""
            if "token" not in data: data["token"] = ""
            if "codes_url" not in data: data["codes_url"] = ""
            if "codes_url_suffix" not in data: data["codes_url_suffix"] = "api/app/active/yrk/cs/2"
            if "last_session_refresh" not in data: data["last_session_refresh"] = None
            if "last_code_attempt" not in data: data["last_code_attempt"] = None
            if "available_untried_codes" not in data: data["available_untried_codes"] = []
            if "tried_codes" not in data: data["tried_codes"] = []
            if "logs" not in data: data["logs"] = [] # Ensure logs key exists
            return data
    except (json.JSONDecodeError, IOError) as e:
        debug_log(f"Error reading {USER_FILE}: {e}. Returning default structure.")
        # Return default structure on error
        return {
            "email": "", "token": "", "codes_url": "",
            "codes_url_suffix": "api/app/active/yrk/cs/2",
            "last_session_refresh": None, "last_code_attempt": None,
            "available_untried_codes": [], "tried_codes": [], "logs": []
        }


def write_local_user_data(data):
    """Writes user data to user.json."""
    try:
        # Ensure logs don't exceed the limit
        if "logs" in data and len(data["logs"]) > LOG_LIMIT:
            # Keep the latest LOG_LIMIT entries (assuming newest are appended)
            data["logs"] = data["logs"][-LOG_LIMIT:]

        with open(USER_FILE, "w") as f:
            json.dump(data, f, indent=4)
        return True # Indicate success
    except IOError as e:
        debug_log(f"Error writing to {USER_FILE}: {e}")
        return False # Indicate failure

def add_local_log(message, status="info"):
    """Adds a log entry to user.json."""
    try:
        user_data = read_local_user_data()
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "status": status # e.g., 'success', 'error', 'info'
        }
        if "logs" not in user_data:
            user_data["logs"] = []
        user_data["logs"].append(log_entry)
        # Keep the latest LOG_LIMIT entries immediately after adding
        user_data["logs"] = user_data["logs"][-LOG_LIMIT:]
        write_local_user_data(user_data)
        debug_log(f"Local Log ({status}): {message}") # Also log to debug
    except Exception as e:
        debug_log(f"Failed to add local log: {e}")
