from typing import Dict, Any, List
from datetime import datetime, timedelta
from api.state import state
from api.utils import get_utc_timestamp, debug_log
from scripts.fetch_attendance import fetch_attendance_page
from api.checkout_client import CheckOutClient


def should_run_fetch() -> bool:
    """Check if attendance fetch should run based on last run time.

    Returns:
        bool: True if it's been more than 24 hours since last run or if no previous run exists.
    """
    last_run = state.get_data("last_attendance_fetch_run")
    if not last_run:
        return True

    last_run_time = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
    now = datetime.now(last_run_time.tzinfo)

    return (now - last_run_time) > timedelta(days=1)


def update_user_attendance_data(
    user: Dict[str, Any], year: int, week: int, activities: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Update a user's attendance data for a specific year and week.

    Args:
        user: User dictionary containing sync and attendance data
        year: Academic year
        week: Week number
        activities: List of attendance activities to store

    Returns:
        Dict[str, Any]: Updated user dictionary with new attendance data
    """
    if "sync" not in user or user["sync"] is None:
        user["sync"] = {}

    if "attendanceData" not in user["sync"]:
        user["sync"]["attendanceData"] = {}

    year_str = str(year)
    week_str = str(week)

    if year_str not in user["sync"]["attendanceData"]:
        user["sync"]["attendanceData"][year_str] = {}

    user["sync"]["attendanceData"][year_str][week_str] = activities

    # Send the updated sync data to the CheckOutAPI
    client = CheckOutClient()
    sync_data = {
        "email": user["email"],
        "sync": {"attendanceData": user["sync"]["attendanceData"]},
    }
    try:
        client.post("update-sync", sync_data)
        debug_log(f"Successfully synced attendance data for {user['email']}")
    except Exception as e:
        debug_log(f"Failed to sync attendance data: {str(e)}")

    return user


def fetch_all_users_attendance(force_run: bool = False) -> None:
    """Fetch and update attendance data for all users in autoCheckinUsers.

    Args:
        force_run (bool): If True, bypasses the should_run_fetch check. Defaults to False.
    """
    debug_log("\nStarting attendance fetch for all users")
    state.dump_state()

    if not force_run and not should_run_fetch():
        debug_log("Skipping attendance fetch - last run was less than 24 hours ago")
        return

    users = state.get_data("autoCheckinUsers") or []
    debug_log(f"Found {len(users)} users")

    current_year = datetime.now().year
    current_week = datetime.now().isocalendar()[1]

    updated_users = []
    for user in users:
        email = user.get("email")
        token = user.get("checkintoken")

        if not email or not token:
            debug_log(f"Skipping user - missing email or token")
            updated_users.append(user)
            continue

        debug_log(f"\nFetching attendance for {email}")

        _, activities = fetch_attendance_page(token, email, current_year, current_week)
        if activities:
            debug_log(f"Successfully fetched {len(activities)} activities")
            user_copy = user.copy()
            updated_user = update_user_attendance_data(
                user_copy, current_year, current_week, activities
            )
            debug_log(f"Updated sync data for {email}")
            updated_users.append(updated_user)
        else:
            debug_log(f"Failed to fetch activities")
            updated_users.append(user)

    try:
        state.set_data("autoCheckinUsers", updated_users)
        state.set_data("last_attendance_fetch_run", get_utc_timestamp())
        state.dump_state()

    except Exception as e:
        debug_log(f"Error updating state: {str(e)}")

    debug_log("Attendance fetch complete")


def fetch_user_attendance_by_email(email: str, force_run: bool = False) -> bool:
    """Fetch and update attendance data for a specific user by email.

    Args:
        email (str): The email of the user to fetch attendance for
        force_run (bool): If True, bypasses the should_run_fetch check. Defaults to False.

    Returns:
        bool: True if the fetch was successful, False otherwise
    """
    debug_log(f"\nStarting attendance fetch for user: {email}")

    if not force_run and not should_run_fetch():
        debug_log("Skipping attendance fetch - last run was less than 24 hours ago")
        return False

    users = state.get_data("autoCheckinUsers") or []
    debug_log(f"Found {len(users)} users")

    current_year = datetime.now().year
    current_week = datetime.now().isocalendar()[1]

    user_found = False
    updated_users = []

    for user in users:
        user_email = user.get("email")

        if user_email != email:
            updated_users.append(user)
            continue

        user_found = True
        token = user.get("checkintoken")

        if not token:
            debug_log(f"Skipping user - missing token")
            updated_users.append(user)
            continue

        debug_log(f"Fetching attendance for {email}")

        _, activities = fetch_attendance_page(token, email, current_year, current_week)
        if activities:
            debug_log(f"Successfully fetched {len(activities)} activities")
            user_copy = user.copy()
            updated_user = update_user_attendance_data(
                user_copy, current_year, current_week, activities
            )
            debug_log(f"Updated sync data for {email}")
            updated_users.append(updated_user)
        else:
            debug_log(f"Failed to fetch activities")
            updated_users.append(user)

    if not user_found:
        debug_log(f"User with email {email} not found")
        return False

    try:
        state.set_data("autoCheckinUsers", updated_users)
        state.set_data("last_attendance_fetch_run", get_utc_timestamp())
        state.dump_state()
        return True
    except Exception as e:
        debug_log(f"Error updating state: {str(e)}")
        return False


if __name__ == "__main__":
    fetch_all_users_attendance()
