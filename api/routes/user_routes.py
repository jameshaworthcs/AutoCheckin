from flask import Blueprint, request
from api.utils import create_response
from scripts.session_refresh import (
    get_all_refresh_sessions,
    get_refresh_session_by_email,
)
from api.fetch_users import fetch_users
from scripts.code_submission import try_codes_for_all_users, get_codes
from scripts.attendance_scheduler import (
    fetch_all_users_attendance,
    fetch_user_attendance_by_email,
)

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
        # Get optional year and week parameters
        year = request.args.get("year")
        week = request.args.get("week")

        # Convert to integers if provided
        year = int(year) if year else None
        week = int(week) if week else None

        fetch_all_users_attendance(force_run=True, year=year, week=week)

        # Include the year and week in the response message
        message = "Attendance fetch completed successfully"
        if year and week:
            message = (
                f"Attendance fetch for year {year}, week {week} completed successfully"
            )
        elif year:
            message = f"Attendance fetch for year {year} completed successfully"
        elif week:
            message = f"Attendance fetch for week {week} completed successfully"

        return create_response(
            message=message, data={"success": True, "year": year, "week": week}
        )
    except Exception as e:
        return create_response(
            success=False,
            message="Attendance fetch failed",
            error=str(e),
            status_code=500,
        )


@session_bp.route("/fetch-attendance-by-user", methods=["GET"])
def fetch_attendance_by_user():
    """Trigger attendance fetch for a specific user by email"""
    email = request.args.get("email")

    if not email:
        return create_response(
            success=False,
            message="Email parameter is required",
            error="Missing email parameter",
            status_code=400,
        )

    try:
        # Get optional year and week parameters
        year = request.args.get("year")
        week = request.args.get("week")

        # Convert to integers if provided
        year = int(year) if year else None
        week = int(week) if week else None

        success = fetch_user_attendance_by_email(
            email, force_run=True, year=year, week=week
        )

        if success:
            # Include the year and week in the response message
            message = f"Attendance fetch for {email} completed successfully"
            if year and week:
                message = f"Attendance fetch for {email} for year {year}, week {week} completed successfully"
            elif year:
                message = f"Attendance fetch for {email} for year {year} completed successfully"
            elif week:
                message = f"Attendance fetch for {email} for week {week} completed successfully"

            return create_response(
                message=message,
                data={"success": True, "email": email, "year": year, "week": week},
            )
        else:
            return create_response(
                success=False,
                message=f"Attendance fetch for {email} failed",
                error="User not found or fetch failed",
                status_code=404,
            )
    except Exception as e:
        return create_response(
            success=False,
            message=f"Attendance fetch for {email} failed",
            error=str(e),
            status_code=500,
        )


weekNumberMapping = (
    [
        {"weekCommencing": "2024-09-16", "weekEnding": "2024-09-22", "weekNumber": "F"},
        {"weekCommencing": "2024-09-23", "weekEnding": "2024-09-29", "weekNumber": "1"},
        {"weekCommencing": "2024-09-30", "weekEnding": "2024-10-06", "weekNumber": "2"},
        {"weekCommencing": "2024-10-07", "weekEnding": "2024-10-13", "weekNumber": "3"},
        {"weekCommencing": "2024-10-14", "weekEnding": "2024-10-20", "weekNumber": "4"},
        {"weekCommencing": "2024-10-21", "weekEnding": "2024-10-27", "weekNumber": "5"},
        {"weekCommencing": "2024-10-28", "weekEnding": "2024-11-03", "weekNumber": "C"},
        {"weekCommencing": "2024-11-04", "weekEnding": "2024-11-10", "weekNumber": "6"},
        {"weekCommencing": "2024-11-11", "weekEnding": "2024-11-17", "weekNumber": "7"},
        {"weekCommencing": "2024-11-18", "weekEnding": "2024-11-24", "weekNumber": "8"},
        {"weekCommencing": "2024-11-25", "weekEnding": "2024-12-01", "weekNumber": "9"},
        {
            "weekCommencing": "2024-12-02",
            "weekEnding": "2024-12-08",
            "weekNumber": "10",
        },
        {
            "weekCommencing": "2024-12-09",
            "weekEnding": "2024-12-15",
            "weekNumber": "11",
        },
        {"weekCommencing": "2024-12-16", "weekEnding": "2024-12-22", "weekNumber": "V"},
        {"weekCommencing": "2024-12-23", "weekEnding": "2024-12-29", "weekNumber": "V"},
        {"weekCommencing": "2024-12-30", "weekEnding": "2025-01-05", "weekNumber": "V"},
        {
            "weekCommencing": "2025-01-06",
            "weekEnding": "2025-01-12",
            "weekNumber": "RV",
        },
        {
            "weekCommencing": "2025-01-13",
            "weekEnding": "2025-01-19",
            "weekNumber": "RA",
        },
        {
            "weekCommencing": "2025-01-20",
            "weekEnding": "2025-01-26",
            "weekNumber": "RA",
        },
        {
            "weekCommencing": "2025-01-27",
            "weekEnding": "2025-02-02",
            "weekNumber": "RA",
        },
        {
            "weekCommencing": "2025-02-03",
            "weekEnding": "2025-02-09",
            "weekNumber": "Rf",
        },
        {"weekCommencing": "2025-02-10", "weekEnding": "2025-02-16", "weekNumber": "1"},
        {"weekCommencing": "2025-02-17", "weekEnding": "2025-02-23", "weekNumber": "2"},
        {"weekCommencing": "2025-02-24", "weekEnding": "2025-03-02", "weekNumber": "3"},
        {"weekCommencing": "2025-03-03", "weekEnding": "2025-03-09", "weekNumber": "4"},
        {"weekCommencing": "2025-03-10", "weekEnding": "2025-03-16", "weekNumber": "5"},
        {"weekCommencing": "2025-03-17", "weekEnding": "2025-03-23", "weekNumber": "6"},
        {"weekCommencing": "2025-03-24", "weekEnding": "2025-03-30", "weekNumber": "7"},
        {"weekCommencing": "2025-03-31", "weekEnding": "2025-04-06", "weekNumber": "8"},
        {"weekCommencing": "2025-04-07", "weekEnding": "2025-04-13", "weekNumber": "V"},
        {"weekCommencing": "2025-04-14", "weekEnding": "2025-04-20", "weekNumber": "V"},
        {"weekCommencing": "2025-04-21", "weekEnding": "2025-04-27", "weekNumber": "9"},
        {
            "weekCommencing": "2025-04-28",
            "weekEnding": "2025-05-04",
            "weekNumber": "10",
        },
        {
            "weekCommencing": "2025-05-05",
            "weekEnding": "2025-05-11",
            "weekNumber": "11",
        },
        {
            "weekCommencing": "2025-05-12",
            "weekEnding": "2025-05-18",
            "weekNumber": "RV",
        },
        {
            "weekCommencing": "2025-05-19",
            "weekEnding": "2025-05-25",
            "weekNumber": "RA",
        },
        {
            "weekCommencing": "2025-05-26",
            "weekEnding": "2025-06-01",
            "weekNumber": "RA",
        },
        {
            "weekCommencing": "2025-06-02",
            "weekEnding": "2025-06-08",
            "weekNumber": "RA",
        },
    ],
)

from datetime import datetime


def get_iso_week_number(date_str):
    """
    Convert a date string to ISO week number within the year.

    Args:
        date_str (str): Date string in format 'YYYY-MM-DD'

    Returns:
        tuple: (year, week_number)
    """
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    year = date_obj.year
    week = date_obj.isocalendar()[1]
    return year, week


@session_bp.route("/fetch-prior-attendance", methods=["GET"])
def fetch_prior_attendance():
    """
    Fetch attendance data for weeks defined in weekNumberMapping.
    Uses weekCommencing dates to calculate ISO week numbers.

    Query Parameters:
        email (str): Email of the user to fetch attendance for (required unless fetchall=true)
        fetchall (bool): If true, fetch for all users instead of a specific email
    """
    email = request.args.get("email")
    fetch_all = request.args.get("fetchall", "false").lower() == "true"

    if not email and not fetch_all:
        return create_response(
            success=False,
            message="Either email parameter or fetchall=true is required",
            error="Missing required parameters",
            status_code=400,
        )

    results = []
    errors = []

    try:
        # Get the actual list from the weekNumberMapping tuple
        mapping_list = (
            weekNumberMapping[0]
            if isinstance(weekNumberMapping, tuple)
            else weekNumberMapping
        )

        # Process each week in the mapping
        for week_data in mapping_list:
            # Access dictionary items directly instead of using .get()
            if "weekCommencing" not in week_data:
                continue

            week_commencing = week_data["weekCommencing"]
            week_number_label = week_data.get("weekNumber", "")

            # Calculate ISO year and week number from the weekCommencing date
            year, week_number = get_iso_week_number(week_commencing)

            try:
                if fetch_all:
                    # Fetch for all users
                    fetch_all_users_attendance(
                        force_run=True, year=year, week=week_number
                    )
                    results.append(
                        {
                            "weekCommencing": week_commencing,
                            "weekNumber": week_number_label,
                            "isoYear": year,
                            "isoWeek": week_number,
                            "status": "success",
                        }
                    )
                else:
                    # Fetch for specific user
                    success = fetch_user_attendance_by_email(
                        email, force_run=True, year=year, week=week_number
                    )
                    status = "success" if success else "failed"
                    results.append(
                        {
                            "weekCommencing": week_commencing,
                            "weekNumber": week_number_label,
                            "isoYear": year,
                            "isoWeek": week_number,
                            "status": status,
                        }
                    )
            except Exception as e:
                errors.append(
                    {
                        "weekCommencing": week_commencing,
                        "weekNumber": week_number_label,
                        "isoYear": year,
                        "isoWeek": week_number,
                        "error": str(e),
                    }
                )

        # Determine overall success based on errors
        success = len(errors) == 0
        message = "Prior attendance fetch completed"
        if email:
            message = f"Prior attendance fetch for {email} completed"

        # Get the total number of weeks in the mapping
        total_weeks = len(mapping_list)

        return create_response(
            success=success,
            message=message,
            data={
                "results": results,
                "errors": errors,
                "totalWeeks": total_weeks,
                "successfulFetches": len(results),
                "failedFetches": len(errors),
            },
            status_code=200 if success else 207,  # 207 Multi-Status if partial success
        )

    except Exception as e:
        return create_response(
            success=False,
            message="Prior attendance fetch failed",
            error=str(e),
            status_code=500,
        )
