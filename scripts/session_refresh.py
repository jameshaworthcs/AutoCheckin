from typing import List, Dict, Any, Optional, Union
from api.state import state
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup
import os
import json
from api.checkout_client import CheckOutClient, CheckOutAPIError
from api.utils import get_utc_timestamp, debug_log

# Get the checkin URL from environment variables
CHECKIN_URL = os.getenv("CHECKIN_URL", "https://checkin.york.ac.uk")


def log(email: str, state: str, message: str) -> None:
    """
    Log session refresh events to the CheckOut API

    Args:
        email: User's email address
        state: Status of the operation ('Normal', 'Fail', etc.)
        message: Detailed message about the operation
    """
    debug_log(f"\nLogging event to CheckOut API")
    debug_log(f"Email: {email}")
    debug_log(f"State: {state}")
    debug_log(f"Message: {message}")

    try:
        client = CheckOutClient()
        payload = {"email": email, "state": state, "message": message}

        debug_log(f"Making POST request to log endpoint")
        # debug_log(f"Payload: {payload}")

        response = client.post("log", payload)

        debug_log(f"Log request successful")

    except CheckOutAPIError as e:
        debug_log(f"Error logging to CheckOut API: {str(e)}")
        # debug_log(f"Status code: {e.status_code}")
        # debug_log(f"Response data: {e.response_data}")


def refresh_session_token(
    email: str, checkin_token: str, get_csrf_and_events: bool = False
) -> Optional[Union[str, Dict[str, Any]]]:
    """
    Refresh a user's session token by accessing checkin.york.ac.uk

    Args:
        email: User's email address
        checkin_token: Current checkin token (prestostudent_session)
        get_csrf_and_events: Whether to return CSRF token and events along with the session token

    Returns:
        Optional[Union[str, Dict[str, Any]]]:
            - If get_csrf_and_events=False: New session token if successful, None if failed
            - If get_csrf_and_events=True: Dict with new_token, csrf_token, and events if successful, None if failed
    """
    debug_log(f"\nStarting session refresh for {email}")
    # debug_log(f"Current token: {checkin_token[:30]}...")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Accept": "text/html",
        "Accept-Encoding": "gzip, deflate, br",
        "Cookie": f"prestostudent_session={checkin_token}",
    }

    try:
        # Fetch the self-registration page
        debug_log("Making request to checkin.york.ac.uk/selfregistration")

        req = requests.get(
            f"{CHECKIN_URL}/selfregistration",
            headers=headers,
        )

        # debug_log(f"Response status code: {req.status_code}")

        # Get new session token from cookies
        cookies = req.cookies
        if "prestostudent_session" not in cookies:
            debug_log("No prestostudent_session cookie in response")
            log(email, "Fail", "Session refresh fail - No new session token")
            return None

        new_token = cookies["prestostudent_session"]
        # debug_log(f"New token received: {new_token[:30]}...")

        # Parse the page content
        debug_log("Parsing response content")
        soup = BeautifulSoup(req.content.decode(), "html.parser")
        title = soup.find("title").text

        # debug_log(f"Page title: {title}")

        # Verify page title
        if title == "Please log in to continue...":
            debug_log("Session expired - login page detected")
            log(email, "Fail", "Session refresh fail - Session expired")
            return None

        if title != "Check-In":
            debug_log(f"Unexpected page title: {title}")
            log(email, "Fail", f"Parser title fail - Unexpected page title: {title}")
            return None

        # Verify user email matches
        name_elements = soup.find_all(
            "span", {"class": "side-menu-title side-menu-name"}
        )
        if not name_elements:
            debug_log("Could not find user email in page")
            log(email, "Fail", "Session refresh fail - Could not find user email")
            return None

        page_email = name_elements[0].text.strip()
        # debug_log(f"Found email in page: {page_email}")

        if page_email != email:
            debug_log(f"Email mismatch: expected {email}, got {page_email}")
            log(
                email,
                "Fail",
                "Email mismatch - Checkout user email does not match Checkin account",
            )
            return None

        # Extract CSRF token and events if requested
        if get_csrf_and_events:
            debug_log("Extracting CSRF token and events")
            csrf_token = soup.find("meta", {"name": "csrf-token"})["content"]
            events = []

            classes = soup.find_all(
                "section", {"class": "box-typical box-typical-padding"}
            )
            if classes and not classes[0].text.__contains__(
                "There is currently no activity for which you can register yourself."
            ):
                for _class in classes:
                    time = _class.find_all("div", {"class": "col-md-4"})[0].text.strip()
                    start, end = time.split(" - ")
                    start = datetime.strptime(
                        datetime.now().strftime("%y %m %d ") + start, "%y %m %d %H:%M"
                    )
                    end = datetime.strptime(
                        datetime.now().strftime("%y %m %d ") + end, "%y %m %d %H:%M"
                    )

                    event = {
                        "start_time": start.isoformat(),
                        "end_time": end.isoformat(),
                        "activity": _class.find_all("div", {"class": "col-md-4"})[
                            1
                        ].text.strip(),
                        "lecturer": _class.find_all("div", {"class": "col-md-4"})[
                            2
                        ].text.strip(),
                        "space": _class.find_all("div", {"class": "col-md-4"})[
                            3
                        ].text.strip(),
                        "status": "unknown",
                        "id": _class.get("data-activities-id"),
                    }

                    options = _class.find_all(
                        "div", {"class": "selfregistration_status"}
                    )
                    for o in options:
                        if o.get("class")[-1] == "hidden":
                            continue

                        widget = o.find("div", {"class": "widget-simple-sm-bottom"})
                        if widget is not None:
                            event["status"] = o.find(
                                "div", {"class": "widget-simple-sm-bottom"}
                            ).text.strip()
                            continue

                        event["status"] = "NotPresent"
                        break

                    events.append(event)

            # debug_log(f"Found {len(events)} events")
            # debug_log(f"CSRF token: {csrf_token}")

        # Notify CheckOut API about the token update
        try:
            debug_log("Notifying CheckOut API about token update")

            client = CheckOutClient()
            update_payload = {
                "email": email,
                "oldtoken": checkin_token,
                "newtoken": new_token,
            }

            # debug_log(f"Update payload: {update_payload}")

            response = client.post("update", update_payload)
            changed_rows = response.get("result", {}).get("changedRows", 0)

            # debug_log(f"Token update response: {response}")
            # debug_log(f"Rows updated: {changed_rows}")

            if changed_rows == 0:
                debug_log("Token update successful but no rows changed")
                log(
                    email,
                    "Fail",
                    "Session refresh fail - Token updated but user record not found",
                )
                # Still continue as we have a valid token

            debug_log("Token update notification successful")

        except CheckOutAPIError as e:
            debug_log(f"Error notifying token update: {str(e)}")
            # debug_log(f"Status code: {e.status_code}")
            # debug_log(f"Response data: {e.response_data}")
            # Continue even if update notification fails, as we still want to use the new token

        debug_log("Session refresh successful")
        log(email, "Normal", "Session refresh success")

        if get_csrf_and_events:
            return {"new_token": new_token, "csrf_token": csrf_token, "events": events}
        return new_token

    except Exception as e:
        # debug_log(f"Error during session refresh: {str(e)}")
        debug_log("Error during session refresh")
        return None


def update_stored_sessions(
    sessions: List[Dict[str, Any]], email: Optional[str] = None
) -> None:
    """
    Update stored sessions with new tokens

    Args:
        sessions: List of user sessions
        email: Optional email to update single user, if None updates all users
    """
    debug_log(f"\nStarting stored sessions update")
    debug_log(f"Target email: {email if email else 'all users'}")
    debug_log(f"Number of sessions to process: {len(sessions)}")

    updated_sessions = []
    current_time = get_utc_timestamp()

    for session in sessions:
        current_email = session.get("email")
        current_token = session.get("checkintoken")

        debug_log(f"\nProcessing session for {current_email}")

        # Skip if not the target email (when updating single user)
        if email is not None and current_email != email:
            debug_log(f"Skipping {current_email} - not target email")
            updated_sessions.append(session)
            continue

        if current_email and current_token:
            debug_log(f"Attempting to refresh token for {current_email}")
            new_token = refresh_session_token(current_email, current_token)
            if new_token:
                debug_log(f"Token refresh successful for {current_email}")
                session.update(
                    {
                        "checkintoken": new_token,
                        "checkinReport": "Normal",
                        "checkinReportTime": current_time,
                    }
                )
            else:
                debug_log(f"Token refresh failed for {current_email}")
                session.update(
                    {"checkinReport": "Fail", "checkinReportTime": current_time}
                )
        else:
            debug_log(f"Missing email or token for session")

        updated_sessions.append(session)

    debug_log(f"\nUpdating global state with {len(updated_sessions)} sessions")
    state.set_data("autoCheckinUsers", updated_sessions)


def get_all_refresh_sessions() -> List[Dict[str, Any]]:
    """Refresh all sessions for all users"""
    debug_log("\nStarting refresh of all sessions")

    sessions = state.get_data("autoCheckinUsers") or []
    debug_log(f"Found {len(sessions)} sessions to refresh")

    update_stored_sessions(sessions)
    current_time = get_utc_timestamp()
    state.set_data("last_all_session_refresh", current_time)

    debug_log("All sessions refresh complete")
    return sessions


def get_refresh_session_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Refresh a specific session by email"""
    debug_log(f"\nStarting refresh for specific email: {email}")

    sessions = state.get_data("autoCheckinUsers") or []
    session = next(
        (session for session in sessions if session.get("email") == email), None
    )

    if session is not None:
        debug_log(f"Found session for {email}, proceeding with refresh")
        update_stored_sessions(sessions, email)
        current_time = get_utc_timestamp()
        state.set_data("last_individual_session_refresh", current_time)
    else:
        debug_log(f"No session found for {email}")

    return session
