from flask import jsonify
from typing import Any, Optional
from datetime import datetime, timezone

def create_response(success: bool = True, 
                   data: Any = None, 
                   message: str = "", 
                   error: Optional[str] = None,
                   status_code: int = 200) -> tuple:
    """
    Create a standardized API response
    """
    response = {
        "success": success,
        "message": message,
        "data": data
    }
    
    if error:
        response["error"] = error
        
    return jsonify(response), status_code

def get_utc_timestamp() -> str:
    """Get current UTC timestamp in ISO format with milliseconds"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z" 