from flask import Blueprint
from api.utils import create_response
from scripts.session_refresh import (
    get_all_refresh_sessions,
    get_refresh_session_by_email,
)
from api.fetch_users import fetch_users
from scripts.code_submission import try_codes_for_all_users, get_codes
from scripts.attendance_scheduler import fetch_all_users_attendance

session_bp = Blueprint("session", __name__)


@session_bp.route("/refresh", methods=["GET"])
def get_all_sessions():
    """Refresh all checkin sessions for all users"""
    sessions = get_all_refresh_sessions()
    return create_response(
        message="Checkin sessions refreshed successfully", data={"sessions": sessions}
    )


@session_bp.route("/refresh-session/<email>", methods=["GET"])
def get_session(email: str):
    """Refresh a specific checkin session for a user"""
    session = get_refresh_session_by_email(email)
    if session is None:
        return create_response(
            success=False,
            message="Session not found",
            error=f"No checkin session found for email: {email}",
            status_code=404,
        )

    return create_response(
        message="Checkin session refreshed successfully", data={"session": session}
    )


@session_bp.route("/fetch-users", methods=["GET"])
def trigger_fetch_users():
    """Trigger a new fetch of users from the CheckOut API"""
    success = fetch_users()
    return create_response(
        success=success,
        message="User fetch completed" if success else "User fetch failed",
        data={"success": success},
    )


@session_bp.route("/try-codes", methods=["GET"])
def try_codes():
    """Try available codes for all users"""
    result = try_codes_for_all_users()
    return create_response(message="Code submission completed", data=result)


@session_bp.route("/codes", methods=["GET"])
def get_available_codes():
    """Get available codes from CheckOut API"""
    codes = get_codes()
    return create_response(
        message="Available codes retrieved successfully", data={"codes": sorted(codes)}
    )


@session_bp.route("/fetch-attendance", methods=["GET"])
def fetch_attendance():
    """Trigger attendance fetch for all users"""
    try:
        fetch_all_users_attendance(force_run=True)
        return create_response(
            message="Attendance fetch completed successfully",
            data={"success": True}
        )
    except Exception as e:
        return create_response(
            success=False,
            message="Attendance fetch failed",
            error=str(e),
            status_code=500
        )
