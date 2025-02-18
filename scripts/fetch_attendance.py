import os
from typing import Optional, Dict, List, Tuple
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from api.utils import debug_log

# Get the checkin URL from environment variables
CHECKIN_URL = os.getenv("CHECKIN_URL", "https://checkin.york.ac.uk")


def parse_activity(activity_section: BeautifulSoup) -> Dict[str, Optional[str]]:
    """Parse a single activity section from the attendance page.

    Args:
        activity_section: BeautifulSoup object containing a single activity

    Returns:
        Dict containing activity details including reference, location,
        lecturer name, start/finish times, and attendance state
    """
    # Get activity reference (name)
    activity_reference = (
        activity_section.find("div", {"class": "cont-in"})
        .get_text(strip=True)
        .split("\n")[0]
    )

    # Get start and finish times
    time_div = activity_section.find("div", {"class": "time"}).get_text(strip=True)
    start_time, finish_time = time_div.split(" - ")

    # Get attendance state
    status_div = activity_section.find("div", {"class": "activity-status"})
    status_class = status_div.get("class", [])[
        -1
    ]  # Get the last class which contains the status
    attendance_state = {
        "activity-status-present": "present",
        "activity-status-absent-unapproved": "absent",
        "activity-status-undetermined": "unknown",
    }.get(status_class, "unknown")

    # Get location and lecturer name
    meta_li = (
        activity_section.find("ul", {"class": "meta"}).find("li").get_text(strip=True)
    )
    location = None
    lecturer_name = None

    if meta_li != "Unknown Staff":
        # Split by comma and handle the case where there might be commas in the lecturer name
        parts = meta_li.split(",", 1)
        location = parts[0].strip()
        lecturer_name = parts[1].strip() if len(parts) > 1 else None

    return {
        "activityReference": activity_reference,
        "location": location,
        "lecturerName": lecturer_name,
        "startTime": start_time,
        "finishTime": finish_time,
        "attendanceState": attendance_state,
    }


def fetch_attendance_page(
    session_token: str, email: str, year: int, week: int
) -> Tuple[Optional[BeautifulSoup], Optional[List[Dict[str, Optional[str]]]]]:
    """Fetch attendance data from the checkin portal for a specific year and week.

    Args:
        session_token: Current checkin token (prestostudent_session)
        email: User's email address to validate against the page
        year: Academic year (e.g., 2023)
        week: Week number

    Returns:
        Tuple containing:
            - BeautifulSoup object of the page
            - List of parsed activities
        Returns (None, None) if fetch fails or session is invalid
    """
    debug_log(f"\nFetching attendance data for {email} - year {year}, week {week}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Accept": "text/html",
        "Accept-Encoding": "gzip, deflate, br",
        "Cookie": f"prestostudent_session={session_token}",
    }

    try:
        # Fetch the attendance page
        debug_log(f"Making request to {CHECKIN_URL}/attendance/{year}/{week}")

        response = requests.get(
            f"{CHECKIN_URL}/attendance/{year}/{week}", headers=headers
        )

        debug_log(f"Response status code: {response.status_code}")

        if response.status_code != 200:
            debug_log("Failed to fetch attendance page")
            return None, None

        # Parse the page content
        debug_log("Parsing response content")
        soup = BeautifulSoup(response.content.decode(), "html.parser")

        # Verify we got a valid page by checking title
        title = soup.find("title").text
        debug_log(f"Page title: {title}")

        if title == "Please log in to continue...":
            debug_log("Session expired - login page detected")
            return None, None

        # Verify the email matches
        page_email = soup.find("span", {"class": "side-menu-title side-menu-name"})
        if not page_email:
            debug_log("Could not find email in page")
            return None, None

        page_email_text = page_email.text.strip()
        if page_email_text != email:
            debug_log(f"Email mismatch: expected {email}, got {page_email_text}")
            return None, None

        # Parse activities
        activities = []
        activity_sections = soup.find_all("section", {"class": "activity-line-action"})

        for activity_section in activity_sections:
            activity = parse_activity(activity_section)
            activities.append(activity)

        debug_log(f"Found {len(activities)} activities")
        return soup, activities

    except Exception as e:
        debug_log(f"Error fetching attendance page: {str(e)}")
        return None, None


if __name__ == "__main__":
    # Test the function with a sample session token
    test_token = "redacted"
    test_email = "redacted"
    current_year = datetime.now().year
    current_week = datetime.now().isocalendar()[1]

    soup, activities = fetch_attendance_page(
        test_token, test_email, current_year, current_week
    )
    if activities:
        print("Successfully fetched attendance page. Activities found:")
        for activity in activities:
            print("\nActivity:")
            for key, value in activity.items():
                print(f"{key}: {value}")
    else:
        print("Failed to fetch attendance page")
