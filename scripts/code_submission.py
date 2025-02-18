from typing import List, Dict, Any, Optional
import os
import requests
from datetime import datetime
from api.state import state
from api.checkout_client import CheckOutClient, CheckOutAPIError
from scripts.session_refresh import refresh_session_token, log
from api.utils import get_utc_timestamp, debug_log

# Get the checkin URL from environment variables
CHECKIN_URL = os.getenv('CHECKIN_URL', 'https://checkin.york.ac.uk')


def get_codes() -> List[str]:
    """Fetch and sort available checkin codes from the CheckOut API.

    Retrieves all available codes from active sessions and sorts them by reputation score,
    which is based on successful usage count.

    Returns:
        List[str]: List of checkin codes sorted by reputation score (most successful first).
    """
    debug_log("\nFetching codes from CheckOut API")

    try:
        client = CheckOutClient()
        response = client.get("codes/yrk/cs/2")

        debug_log("Parsing response from CheckOut API")

        if response.get("status_code") == 403:
            debug_log("Access forbidden")
            return []

        session_count = response.get("sessionCount", 0)
        if not session_count:
            debug_log("No active sessions found")
            return []

        codes = []
        sessions = response.get("sessions", [])

        debug_log(f"Found {len(sessions)} sessions")

        for session in sessions:
            session_codes = session.get("codes", [])
            codes.extend(session_codes)

        # Sort by reputation score (usage count)
        codes.sort(key=lambda x: x.get("count", 0), reverse=True)
        sorted_checkin_codes = [str(code.get("checkinCode")) for code in codes]

        debug_log(f"Extracted {len(sorted_checkin_codes)} codes")

        return sorted_checkin_codes

    except CheckOutAPIError as e:
        debug_log(f"Error fetching codes: {str(e)}")
        return []


def try_code(event_id: str, code: str, session_token: str, csrf_token: str) -> bool:
    """Attempt to use a checkin code for a specific event.

    Makes an authenticated request to the CheckOut API to submit a code for an event.

    Args:
        event_id: ID of the event to try the code for
        code: Checkin code to try
        session_token: Current session token for authentication
        csrf_token: CSRF token for request validation

    Returns:
        bool: True if code was accepted, False if invalid or error occurred
    """
    debug_log(f"\nTrying code for event {event_id}")
    debug_log(f"Code: {code}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate, br",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": f"{CHECKIN_URL}/selfregistration",
        "Cookie": f"XSRF-TOKEN={csrf_token}; prestostudent_session={session_token}",
    }

    data = {
        "code": code,
        "_token": csrf_token,
    }

    try:
        response = requests.post(
            f"{CHECKIN_URL}/api/selfregistration/{event_id}/present",
            headers=headers,
            data=data,
        )

        debug_log(f"Response status code: {response.status_code}")

        if response.status_code == 422:  # Invalid code
            debug_log("Invalid code")
            return False

        if response.status_code != 200:
            debug_log(f"Error response: {response.text}")
            return False

        debug_log("Code accepted successfully")
        return True

    except Exception as e:
        debug_log(f"Error trying code: {str(e)}")
        return False


def try_codes_for_user(email: str, current_token: str) -> None:
    """Process checkin codes for all unchecked events of a user.

    For each event where the user is not marked as present:
    1. Tries each available code in order of reputation score
    2. Stops trying codes for an event once one succeeds
    3. Logs successful checkins to the system
    4. Updates the stored session token in global state

    Args:
        email: User's email address
        current_token: User's current session token
    """
    debug_log(f"\nStarting code submission for {email}")

    result = refresh_session_token(email, current_token, get_csrf_and_events=True)
    if not result:
        debug_log("Failed to refresh session token")
        return

    new_token = result["new_token"]
    csrf_token = result["csrf_token"]

    # Update the stored session token in global state
    stored_users = state.get_data("autoCheckinUsers") or []
    for user in stored_users:
        if user.get("email") == email:
            user["checkintoken"] = new_token
            user["checkinReportTime"] = get_utc_timestamp()
            break
    state.set_data("autoCheckinUsers", stored_users)

    debug_log(f"CSRF token: {csrf_token}")
    events = result["events"]

    debug_log(f"Found {len(events)} events")

    codes = get_codes()
    if not codes:
        debug_log("No codes available")
        return

    for event in events:
        if event["status"] in ["Present", "Present Late"]:
            debug_log(f"Skipping event {event['activity']} - already present")
            continue

        debug_log(f"\nProcessing event: {event['activity']}")

        for code in codes:
            success = try_code(event["id"], code, new_token, csrf_token)
            if success:
                debug_log(f"Successfully checked into {event['activity']}")
                log(
                    email,
                    "Checkin",
                    f"Checked into {event['activity']} with code {code}",
                )
                break


def try_codes_for_all_users() -> Dict[str, Any]:
    """Process checkin codes for all registered users.

    Attempts to check in each user to their unchecked events using available codes.
    Updates the global state with the results.

    Returns:
        Dict[str, Any]: Summary containing total users, processed count, and timestamp
    """
    debug_log("\nStarting code submission for all users")

    users = state.get_data("autoCheckinUsers") or []
    debug_log(f"Found {len(users)} users")

    processed = 0
    for user in users:
        email = user.get("email")
        token = user.get("checkintoken")

        if not email or not token:
            debug_log("Skipping user - missing email or token")
            continue

        try_codes_for_user(email, token)
        processed += 1

    result = {
        "total_users": len(users),
        "processed_users": processed,
        "timestamp": datetime.utcnow().isoformat(),
    }

    state.set_data("last_code_submission", result)
    return result
