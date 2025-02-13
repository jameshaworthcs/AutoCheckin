from flask import Blueprint
from api.utils import create_response
from scripts.session_refresh import get_all_refresh_sessions, get_refresh_session_by_email
from api.fetch_users import fetch_users

session_bp = Blueprint('session', __name__)

@session_bp.route('/refresh', methods=['GET'])
def get_all_sessions():
    """Refresh all checkin sessions for all users"""
    sessions = get_all_refresh_sessions()
    return create_response(
        message="Checkin sessions refreshed successfully",
        data={"sessions": sessions}
    )

@session_bp.route('/refresh-session/<email>', methods=['GET'])
def get_session(email: str):
    """Refresh a specific checkin session for a user"""
    session = get_refresh_session_by_email(email)
    if session is None:
        return create_response(
            success=False,
            message="Session not found",
            error=f"No checkin session found for email: {email}",
            status_code=404
        )
    
    return create_response(
        message="Checkin session refreshed successfully",
        data={"session": session}
    )

@session_bp.route('/fetch-users', methods=['GET'])
def trigger_fetch_users():
    """Trigger a new fetch of users from the CheckOut API"""
    success = fetch_users()
    return create_response(
        success=success,
        message="User fetch completed" if success else "User fetch failed",
        data={"success": success}
    ) 