from flask import Blueprint, request
from api.utils import create_response
from scripts.test_auth import check_authentication

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/test', methods=['GET', 'POST'])
def test_auth():
    """
    Test endpoint to verify API key authentication
    Required header: x-checkout-key
    """
    try:
        # Get API key from header
        api_key = request.headers.get('x-checkout-key')
        
        result = check_authentication(api_key)
        
        return create_response(
            success=result['success'],
            message="Authentication Test Result",
            data=result['data'],
            error=result.get('error'),
            status_code=200 if result['success'] else 400
        )
        
    except Exception as e:
        return create_response(
            success=False,
            message="Authentication Test Error",
            error=str(e),
            status_code=500
        ) 