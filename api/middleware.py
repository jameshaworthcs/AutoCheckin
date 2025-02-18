from functools import wraps
from flask import request, current_app
import os
from api.utils import create_response


def check_api_key():
    """Check if the request should be authenticated and validate API key"""
    # Skip authentication in development environment
    if os.getenv("FLASK_ENV") == "development":
        return None

    # (Don't) Skip authentication for specific endpoints that should be public
    # if request.endpoint == 'index':  # Allow root endpoint without auth
    #     return None

    api_key = request.headers.get("x-checkout-key")
    expected_api_key = os.getenv("CHECKOUT_API_KEY")

    if not api_key:
        return create_response(
            success=False,
            message="Authentication Failed",
            error="Missing x-checkout-key header",
            status_code=401,
        )

    if not expected_api_key:
        return create_response(
            success=False,
            message="Server Configuration Error",
            error="CHECKOUT_API_KEY not configured on server",
            status_code=500,
        )

    if api_key != expected_api_key:
        return create_response(
            success=False,
            message="Authentication Failed",
            error="Invalid API key",
            status_code=401,
        )

    return None


# Keep the decorator for specific routes if needed
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        result = check_api_key()
        if result is not None:
            return result
        return f(*args, **kwargs)

    return decorated_function
