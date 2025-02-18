import os
from typing import Dict


def check_authentication(provided_key: str) -> Dict:
    """
    Check if the provided API key matches the one in environment variables

    Args:
        provided_key (str): The API key provided in the request header

    Returns:
        dict: Result containing authentication status and any error messages
    """
    result = {"success": True, "data": {"authenticated": False}, "error": None}

    try:
        stored_key = os.getenv("CHECKOUT_API_KEY")

        if not stored_key:
            raise ValueError("CHECKOUT_API_KEY not configured in environment")

        if not provided_key:
            raise ValueError("No API key provided in request")

        result["data"]["authenticated"] = provided_key == stored_key

    except Exception as e:
        result["success"] = False
        result["error"] = str(e)

    return result
