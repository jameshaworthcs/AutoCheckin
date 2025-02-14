from typing import List, Dict, Any, Optional
from api.state import state
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup
import os
import json
from api.checkout_client import CheckOutClient, CheckOutAPIError

def log(email: str, state: str, message: str) -> None:
    """
    Log session refresh events to the CheckOut API
    
    Args:
        email: User's email address
        state: Status of the operation ('Normal', 'Fail', etc.)
        message: Detailed message about the operation
    """
    if os.getenv('FLASK_DEBUG') == '1':
        print(f"\n[DEBUG] Logging event to CheckOut API")
        print(f"[DEBUG] Email: {email}")
        print(f"[DEBUG] State: {state}")
        print(f"[DEBUG] Message: {message}")
    
    try:
        client = CheckOutClient()
        payload = {
            "email": email,
            "state": state,
            "message": message
        }
        
        if os.getenv('FLASK_DEBUG') == '1':
            print(f"[DEBUG] Making POST request to log endpoint")
            print(f"[DEBUG] Payload: {payload}")
        
        response = client.post('log', payload)
        
        if os.getenv('FLASK_DEBUG') == '1':
            print(f"[DEBUG] Log request successful")
        
    except CheckOutAPIError as e:
        if os.getenv('FLASK_DEBUG') == '1':
            print(f"[DEBUG] Error logging to CheckOut API: {str(e)}")
            if e.status_code:
                print(f"[DEBUG] Status code: {e.status_code}")
            if e.response_data:
                print(f"[DEBUG] Response data: {e.response_data}")

def get_utc_timestamp() -> str:
    """Get current UTC timestamp in ISO format with milliseconds"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

def refresh_session_token(email: str, checkin_token: str) -> Optional[str]:
    """
    Refresh a user's session token by accessing checkin.york.ac.uk
    
    Args:
        email: User's email address
        checkin_token: Current checkin token (prestostudent_session)
        
    Returns:
        Optional[str]: New session token if successful, None if failed
    """
    if os.getenv('FLASK_DEBUG') == '1':
        print(f"\n[DEBUG] Starting session refresh for {email}")
        print(f"[DEBUG] Current token: {checkin_token[:30]}...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Accept": "text/html",
        "Accept-Encoding": "gzip, deflate, br",
        "Cookie": f"prestostudent_session={checkin_token}",
    }
    
    try:
        # Fetch the self-registration page
        if os.getenv('FLASK_DEBUG') == '1':
            print("[DEBUG] Making request to checkin.york.ac.uk/selfregistration")
        
        req = requests.get(
            "https://checkin.york.ac.uk/selfregistration",
            headers=headers,
        )
        
        if os.getenv('FLASK_DEBUG') == '1':
            print(f"[DEBUG] Response status code: {req.status_code}")
        
        # Get new session token from cookies
        cookies = req.cookies
        if 'prestostudent_session' not in cookies:
            if os.getenv('FLASK_DEBUG') == '1':
                print("[DEBUG] No prestostudent_session cookie in response")
            log(email, "Fail", "Session refresh fail - No new session token")
            return None
            
        new_token = cookies['prestostudent_session']
        if os.getenv('FLASK_DEBUG') == '1':
            print(f"[DEBUG] New token received: {new_token[:30]}...")
        
        # Parse the page content
        if os.getenv('FLASK_DEBUG') == '1':
            print("[DEBUG] Parsing response content")
        soup = BeautifulSoup(req.content.decode(), "html.parser")
        title = soup.find("title").text
        
        if os.getenv('FLASK_DEBUG') == '1':
            print(f"[DEBUG] Page title: {title}")
        
        # Verify page title
        if title == "Please log in to continue...":
            if os.getenv('FLASK_DEBUG') == '1':
                print("[DEBUG] Session expired - login page detected")
            log(email, "Fail", "Session refresh fail - Session expired")
            return None
            
        if title != "Check-In":
            if os.getenv('FLASK_DEBUG') == '1':
                print(f"[DEBUG] Unexpected page title: {title}")
            log(email, "Fail", f"Parser title fail - Unexpected page title: {title}")
            return None
            
        # Verify user email matches
        name_elements = soup.find_all("span", {"class": "side-menu-title side-menu-name"})
        if not name_elements:
            if os.getenv('FLASK_DEBUG') == '1':
                print("[DEBUG] Could not find user email in page")
            log(email, "Fail", "Session refresh fail - Could not find user email")
            return None
            
        page_email = name_elements[0].text.strip()
        if os.getenv('FLASK_DEBUG') == '1':
            print(f"[DEBUG] Found email in page: {page_email}")
            
        if page_email != email:
            if os.getenv('FLASK_DEBUG') == '1':
                print(f"[DEBUG] Email mismatch: expected {email}, got {page_email}")
            log(email, "Fail", "Email mismatch - Checkout user email does not match Checkin account")
            return None
            
        if os.getenv('FLASK_DEBUG') == '1':
            print("[DEBUG] Session refresh successful")
        log(email, "Normal", "Session refresh success")
        return new_token
        
    except Exception as e:
        if os.getenv('FLASK_DEBUG') == '1':
            print(f"[DEBUG] Error during session refresh: {str(e)}")
        log(email, "Fail", f"Session refresh fail - {str(e)}")
        return None

def update_stored_sessions(sessions: List[Dict[str, Any]], email: Optional[str] = None) -> None:
    """
    Update stored sessions with new tokens
    
    Args:
        sessions: List of user sessions
        email: Optional email to update single user, if None updates all users
    """
    if os.getenv('FLASK_DEBUG') == '1':
        print(f"\n[DEBUG] Starting stored sessions update")
        print(f"[DEBUG] Target email: {email if email else 'all users'}")
        print(f"[DEBUG] Number of sessions to process: {len(sessions)}")
    
    updated_sessions = []
    current_time = get_utc_timestamp()
    
    for session in sessions:
        current_email = session.get('email')
        current_token = session.get('checkintoken')
        
        if os.getenv('FLASK_DEBUG') == '1':
            print(f"\n[DEBUG] Processing session for {current_email}")
        
        # Skip if not the target email (when updating single user)
        if email is not None and current_email != email:
            if os.getenv('FLASK_DEBUG') == '1':
                print(f"[DEBUG] Skipping {current_email} - not target email")
            updated_sessions.append(session)
            continue
            
        if current_email and current_token:
            if os.getenv('FLASK_DEBUG') == '1':
                print(f"[DEBUG] Attempting to refresh token for {current_email}")
            new_token = refresh_session_token(current_email, current_token)
            if new_token:
                if os.getenv('FLASK_DEBUG') == '1':
                    print(f"[DEBUG] Token refresh successful for {current_email}")
                session.update({
                    'checkintoken': new_token,
                    'checkinReport': 'Normal',
                    'checkinReportTime': current_time
                })
            else:
                if os.getenv('FLASK_DEBUG') == '1':
                    print(f"[DEBUG] Token refresh failed for {current_email}")
                session.update({
                    'checkinReport': 'Fail',
                    'checkinReportTime': current_time
                })
        else:
            if os.getenv('FLASK_DEBUG') == '1':
                print(f"[DEBUG] Missing email or token for session")
                
        updated_sessions.append(session)
    
    if os.getenv('FLASK_DEBUG') == '1':
        print(f"\n[DEBUG] Updating global state with {len(updated_sessions)} sessions")
    state.set_data('autoCheckinUsers', updated_sessions)

def get_all_refresh_sessions() -> List[Dict[str, Any]]:
    """Refresh all sessions for all users"""
    if os.getenv('FLASK_DEBUG') == '1':
        print("\n[DEBUG] Starting refresh of all sessions")
    
    sessions = state.get_data('autoCheckinUsers') or []
    if os.getenv('FLASK_DEBUG') == '1':
        print(f"[DEBUG] Found {len(sessions)} sessions to refresh")
    
    update_stored_sessions(sessions)
    current_time = get_utc_timestamp()
    state.set_data('last_all_session_refresh', current_time)
    
    if os.getenv('FLASK_DEBUG') == '1':
        print("[DEBUG] All sessions refresh complete")
    return sessions

def get_refresh_session_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Refresh a specific session by email"""
    if os.getenv('FLASK_DEBUG') == '1':
        print(f"\n[DEBUG] Starting refresh for specific email: {email}")
    
    sessions = state.get_data('autoCheckinUsers') or []
    session = next((session for session in sessions if session.get('email') == email), None)
    
    if session is not None:
        if os.getenv('FLASK_DEBUG') == '1':
            print(f"[DEBUG] Found session for {email}, proceeding with refresh")
        update_stored_sessions(sessions, email)
        current_time = get_utc_timestamp()
        state.set_data('last_individual_session_refresh', current_time)
    else:
        if os.getenv('FLASK_DEBUG') == '1':
            print(f"[DEBUG] No session found for {email}")
    
    return session