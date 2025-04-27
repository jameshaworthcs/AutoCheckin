import os
import requests
import time 
from bs4 import BeautifulSoup
from typing import Dict, Any, List, Tuple, Optional, Set # Updated typing
from datetime import datetime

from api.utils import (
    read_local_user_data,
    write_local_user_data,
    get_utc_timestamp,
    debug_log,
    add_local_log,
)

# Get the checkin URL from environment variables
CHECKIN_URL = os.getenv("CHECKIN_URL", "https://checkin.york.ac.uk")


def _parse_events_from_html(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """Helper to parse event data from the selfregistration page HTML."""
    events = []
    try:
        classes = soup.find_all(
            "section", {"class": "box-typical box-typical-padding"}
        )
        if classes and not classes[0].text.__contains__(
            "There is currently no activity for which you can register yourself."
        ):
            for _class in classes:
                cols = _class.find_all("div", {"class": "col-md-4"})
                if len(cols) < 4: continue # Skip malformed event sections
                
                time_str = cols[0].text.strip()
                start_str, end_str = time_str.split(" - ") if " - " in time_str else (None, None)
                start_dt, end_dt = None, None
                try:
                    # Attempt to parse time assuming current date
                    date_prefix = datetime.now().strftime("%y %m %d ")
                    if start_str: start_dt = datetime.strptime(date_prefix + start_str, "%y %m %d %H:%M")
                    if end_str: end_dt = datetime.strptime(date_prefix + end_str, "%y %m %d %H:%M")
                except ValueError:
                    debug_log(f"Could not parse event time: {time_str}")

                event_id = _class.get("data-activities-id")
                if not event_id: continue # Skip if no event ID

                event = {
                    "start_time": start_dt.isoformat() if start_dt else None,
                    "end_time": end_dt.isoformat() if end_dt else None,
                    "activity": cols[1].text.strip(),
                    "lecturer": cols[2].text.strip(),
                    "space": cols[3].text.strip(),
                    "status": "unknown",
                    "id": event_id,
                }

                # Determine status
                options = _class.find_all("div", {"class": "selfregistration_status"})
                status_found = False
                for o in options:
                    if "hidden" in o.get("class", []): continue # Skip hidden status divs
                    
                    widget = o.find("div", {"class": "widget-simple-sm-bottom"})
                    if widget is not None:
                        event["status"] = widget.text.strip()
                        status_found = True
                        break
                    # Check for the button case (implies NotPresent)
                    if o.find("button", {"class": "btn btn-default"}):
                         event["status"] = "NotPresent"
                         status_found = True
                         break
                         
                if not status_found:
                     event["status"] = "Unknown" # Default if parsing fails

                events.append(event)
    except Exception as e:
        debug_log(f"Error parsing events from HTML: {e}")
        # Return potentially partially parsed list

    return events

def refresh_local_user_session() -> Dict[str, Any]:
    """Refreshes the session token for the single local user stored in user.json.
    Also attempts to extract CSRF token and current events.

    Reads user data, attempts to refresh the token via CHECKIN_URL,
    and updates user.json with the new token and timestamp on success.

    Returns:
        Dict[str, Any]: A dictionary indicating success status and potentially an error message,
                      new token, csrf token, and events list.
                      On success: {'success': True, 'new_token': ..., 'csrf_token': ..., 'events': [...]}.
                      On failure: {'success': False, 'error': 'Reason...'}.
    """
    debug_log("Attempting local user session refresh (including CSRF/Events).")

    user_data = read_local_user_data()
    email = user_data.get("email")
    current_token = user_data.get("token")

    if not email or not current_token:
        debug_log("Local user data missing email or token.")
        add_local_log("Session Refresh: Failed - Email or token not configured.", status="error")
        return {"success": False, "error": "Local user email or token not configured."}

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Accept": "text/html",
        "Accept-Encoding": "gzip, deflate, br",
        "Cookie": f"prestostudent_session={current_token}",
    }

    try:
        req = requests.get(
            f"{CHECKIN_URL}/selfregistration",
            headers=headers,
            timeout=15,
        )
        req.raise_for_status()

        cookies = req.cookies
        if "prestostudent_session" not in cookies:
            debug_log("No prestostudent_session cookie in response during refresh.")
            add_local_log("Session Refresh: Failed - No new session token received.", status="error")
            return {"success": False, "error": "Session refresh failed - No new session token received."}

        new_token = cookies["prestostudent_session"]

        soup = BeautifulSoup(req.content.decode('utf-8', 'ignore'), "html.parser")
        title_tag = soup.find("title")
        title = title_tag.text if title_tag else ""

        if title == "Please log in to continue...":
            debug_log("Session expired - login page detected during refresh.")
            add_local_log("Session Refresh: Failed - Session expired (login page detected).", status="error")
            return {"success": False, "error": "Session refresh failed - Session expired (login page detected)."}

        if title != "Check-In":
            debug_log(f"Unexpected page title during refresh: {title}")
            add_local_log(f"Session Refresh: Failed - Unexpected page title: {title}.", status="error")
            return {"success": False, "error": f"Session refresh failed - Unexpected page title: {title}"}

        name_elements = soup.find_all("span", {"class": "side-menu-title side-menu-name"})
        page_email = name_elements[0].text.strip() if name_elements else None

        if page_email != email:
            debug_log(f"Email mismatch during refresh: expected {email}, got {page_email}")
            add_local_log(f"Session Refresh: Failed - Email mismatch (Expected {email}, got {page_email}).", status="error")
            return {"success": False, "error": "Session refresh failed - Email mismatch detected."}

        # --- Extract CSRF and Events --- 
        csrf_token_tag = soup.find("meta", {"name": "csrf-token"})
        csrf_token = csrf_token_tag["content"] if csrf_token_tag else None
        events = _parse_events_from_html(soup)
        debug_log(f"Extracted CSRF: {csrf_token is not None}, Found {len(events)} events.")
        # ------------------------------

        # --- Success --- 
        debug_log(f"Local session refresh successful for {email}.")
        current_time = get_utc_timestamp()
        
        user_data["token"] = new_token
        user_data["last_session_refresh"] = current_time
        # Store events if needed, though they are likely transient
        # user_data["last_known_events"] = events 
        
        if write_local_user_data(user_data):
            debug_log("Successfully updated user.json with new token and timestamp.")
            add_local_log(f"Session Refresh: Successful for {email}.", status="success")
            return {
                 "success": True,
                 "new_token": new_token,
                 "csrf_token": csrf_token,
                 "events": events
             }
        else:
            debug_log("Session refresh successful, but failed to write updated user.json.")
            add_local_log("Session Refresh: Succeeded, but failed to save user.json.", status="error")
            # Still return the tokens/events even if save failed, caller might handle it
            return {
                "success": False, # Indicate failure because save failed
                "error": "Failed to save updated session to user.json.",
                "new_token": new_token,
                "csrf_token": csrf_token,
                "events": events
            }

    except requests.exceptions.RequestException as e:
        error_msg = f"HTTP Error during session refresh: {e}"
        debug_log(error_msg)
        add_local_log(f"Session Refresh: Failed - {error_msg}", status="error")
        return {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = f"Unexpected error during session refresh: {e}"
        debug_log(error_msg)
        add_local_log(f"Session Refresh: Failed - {error_msg}", status="error")
        return {"success": False, "error": error_msg}


# --- Code Submission Logic --- START

def try_code(event_id: str, code: str, session_token: str, csrf_token: str) -> bool:
    """Attempts to use a checkin code for a specific event ID.
    
    NOTE: Copied and slightly adapted from scripts/code_submission.py for local use.
    """
    debug_log(f"Local mode: Trying code {code} for event {event_id}")

    if not csrf_token:
        debug_log("Local mode: try_code failed - Missing CSRF token.")
        return False

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate, br",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": f"{CHECKIN_URL}/selfregistration",
        "Cookie": f"XSRF-TOKEN={csrf_token}; prestostudent_session={session_token}",
        "X-CSRF-TOKEN": csrf_token # Often required header as well
    }

    data = {
        "code": code,
        "_token": csrf_token, # Sometimes needed in body too
    }

    submit_url = f"{CHECKIN_URL}/api/selfregistration/{event_id}/present"
    
    try:
        response = requests.post(submit_url, headers=headers, data=data, timeout=10)
        debug_log(f"Local mode: try_code response status for event {event_id}, code {code}: {response.status_code}")

        if response.status_code == 422:  # Invalid code (Unprocessable Entity)
            debug_log(f"Local mode: Code {code} invalid for event {event_id}.")
            return False
        
        # Consider other error codes? 409 (Conflict - already checked in?)
        # 401/403 (Unauthorized - session/csrf issue?)
        if response.status_code == 401 or response.status_code == 403:
             debug_log(f"Local mode: Authorization error ({response.status_code}) trying code {code}.")
             # Session might be truly dead, even if refresh seemed okay?
             return False 

        if response.status_code != 200:
            debug_log(f"Local mode: Unexpected status {response.status_code} trying code {code}. Response: {response.text[:200]}")
            return False

        # Assume 200 means success
        debug_log(f"Local mode: Code {code} accepted for event {event_id}.")
        return True

    except requests.exceptions.RequestException as e:
        debug_log(f"Local mode: HTTP error trying code {code} for event {event_id}: {e}")
        return False
    except Exception as e:
         debug_log(f"Local mode: Unexpected error trying code {code} for event {event_id}: {e}")
         return False


def try_local_user_codes() -> Dict[str, Any]:
    """Attempts to submit available untried codes for the local user's events.

    Refreshes session, gets events, gets available codes, tries them,
    updates user.json state. All codes available at the start of this run
    will be moved to the tried_codes list afterwards.

    Returns:
        Dict[str, Any]: Result summary including success status, message/error,
                      and statistics like codes tried, events processed, etc.
                      Example Success: {'success': True, 'message': '...', 'processed_events': ..., ...}
                      Example Failure: {'success': False, 'error': '...', ...}
    """
    start_time = time.time()
    debug_log("Starting local code submission process.")
    add_local_log("Code Submission: Process started.", status="info")

    # --- 0. Read Initial State --- 
    user_data = read_local_user_data() # Read initial data
    initial_untried_codes_set = set(user_data.get("available_untried_codes", []))
    initial_tried_codes_set = set(user_data.get("tried_codes", []))
    email = user_data.get("email", "Unknown")
    codes_to_try_in_loop = list(initial_untried_codes_set) # Use the initial list for trying

    # 1. Refresh Session & Get Events/CSRF
    refresh_result = refresh_local_user_session() 
    if not refresh_result.get("success"):
        error_msg = refresh_result.get("error", "Failed to refresh session before code submission.")
        debug_log(f"Code submission aborted: {error_msg}")
        # No need to log again, refresh_local_user_session already logged the specific error
        return {"success": False, "error": error_msg, "stats": {"duration_seconds": time.time() - start_time}}

    session_token = refresh_result.get("new_token")
    csrf_token = refresh_result.get("csrf_token")
    events = refresh_result.get("events", [])
    # user_data = read_local_user_data() # No need to re-read here unless refresh modifies it unexpectedly

    if not session_token or not csrf_token:
        error_msg = "Missing session or CSRF token after successful refresh."
        debug_log(f"Code submission aborted: {error_msg}")
        add_local_log(f"Code Submission: Failed - {error_msg}", status="error")
        return {"success": False, "error": error_msg, "stats": {"duration_seconds": time.time() - start_time}}

    # 2. Check if there are codes to try
    if not codes_to_try_in_loop:
        message = "No available untried codes found at start of run."
        debug_log(f"Code submission finished early: {message}")
        add_local_log(f"Code Submission: Finished - {message}", status="info")
        # Still update last_code_attempt timestamp and ensure lists are consistent
        final_user_data = read_local_user_data() # Read fresh before potentially writing
        final_user_data["last_code_attempt"] = get_utc_timestamp()
        # Ensure untried is empty and tried contains initial untried + initial tried
        final_user_data["available_untried_codes"] = [] 
        updated_tried = initial_tried_codes_set.union(initial_untried_codes_set)
        final_user_data["tried_codes"] = sorted(list(updated_tried))
        write_local_user_data(final_user_data)
        return {"success": True, "message": message, "stats": {"duration_seconds": time.time() - start_time, "events_found": len(events), "codes_available_start": 0}}

    debug_log(f"Found {len(codes_to_try_in_loop)} untried codes to process. Found {len(events)} events for user {email}.")

    # 3. Process Events and Try Codes
    processed_events_count = 0
    successful_submissions = 0
    codes_attempted_count = 0 # How many code *attempts* were made
    unique_codes_attempted_set = set() # Which unique codes were actually used in try_code
    used_codes_this_run = set() # Codes that resulted in a successful check-in
    failed_events = [] # Track events we failed to check in for

    for event in events:
        event_id = event.get("id")
        event_status = event.get("status", "Unknown")
        event_name = event.get("activity", f"Event ID {event_id}")

        if not event_id:
            debug_log(f"Skipping event with no ID: {event}")
            continue

        processed_events_count += 1

        if event_status == "Present":
            debug_log(f"Skipping event '{event_name}': Already marked as Present.")
            continue

        debug_log(f"Processing event '{event_name}' (Status: {event_status}). Attempting check-in.")
        event_checked_in = False
        codes_tried_for_this_event = 0
        for code in codes_to_try_in_loop: # Iterate through the codes available at the start
            if code in used_codes_this_run: # Don't retry a code used successfully *this run*
                continue
                
            codes_attempted_count += 1
            unique_codes_attempted_set.add(code) # Mark as attempted in this run
            codes_tried_for_this_event += 1
            
            success = try_code(event_id, code, session_token, csrf_token)

            if success:
                debug_log(f"Successfully checked in for event '{event_name}' with code {code}.")
                add_local_log(f"Code Submission: Success - Checked in for '{event_name}' with code {code}.", status="success")
                successful_submissions += 1
                event_checked_in = True
                used_codes_this_run.add(code) # Mark code as successfully used for this session
                break # Move to the next event
            else:
                # try_code logs the specific reason for failure (invalid, auth error, etc.)
                pass
                
        if not event_checked_in:
             debug_log(f"Failed to check in for event '{event_name}' after trying {codes_tried_for_this_event} available code(s).")
             add_local_log(f"Code Submission: Failed - Could not check in for '{event_name}' after trying {codes_tried_for_this_event} code(s).", status="warning")
             failed_events.append(event_name)


    # 4. Update User Data State - Move all initially untried codes to tried
    final_user_data = read_local_user_data() # Read again to ensure we have latest tried codes before merging
    
    # Combine existing tried codes with the codes that were untried at the start of this run
    current_tried_set = set(final_user_data.get("tried_codes", []))
    updated_tried_codes_set = current_tried_set.union(initial_untried_codes_set)
    
    # Update the lists in the dictionary
    final_user_data["tried_codes"] = sorted(list(updated_tried_codes_set))
    final_user_data["available_untried_codes"] = [] # Clear the untried list as requested
    final_user_data["last_code_attempt"] = get_utc_timestamp()

    save_success = write_local_user_data(final_user_data)
    if not save_success:
        save_error_msg = "Failed to update user.json state after submission attempt."
        debug_log(f"Code Submission Warning: {save_error_msg}")
        add_local_log(f"Code Submission: Warning - {save_error_msg}", status="warning")
        # Continue to return results, but flag the save failure

    # 5. Prepare and Return Result
    duration = time.time() - start_time
    summary_message = (
        f"Processed {processed_events_count} events. "
        f"Successfully checked in for {successful_submissions}. "
        f"Attempted {codes_attempted_count} code instances across events "
        f"({len(unique_codes_attempted_set)} unique codes from the initial {len(initial_untried_codes_set)} untried codes). "
        f"{len(initial_untried_codes_set)} codes moved from untried to tried."
    )
    if failed_events:
        summary_message += f" Failed check-in for: {', '.join(failed_events)}."
    if not save_success:
        summary_message += " Warning: Failed to save updated state to user.json."

    debug_log(f"Code submission process finished in {duration:.2f} seconds. {summary_message}")
    add_local_log(f"Code Submission: Process finished. {summary_message}", status="info")

    return {
        "success": True, # Process completed, state updated (even if save failed or checkins failed)
        "message": summary_message,
        "stats": {
            "duration_seconds": duration,
            "events_found": len(events),
            "events_processed": processed_events_count,
            "successful_submissions": successful_submissions,
            "codes_available_start": len(initial_untried_codes_set),
            "codes_attempted_count": codes_attempted_count,
            "unique_codes_attempted": len(unique_codes_attempted_set),
            "codes_moved_to_tried": len(initial_untried_codes_set),
            "codes_remaining_untried": 0, # Should always be 0 after this runs
            "failed_event_names": failed_events,
            "save_state_successful": save_success
        }
    }

# --- Code Submission Logic --- END
