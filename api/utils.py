from flask import jsonify
from typing import Any, Optional

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