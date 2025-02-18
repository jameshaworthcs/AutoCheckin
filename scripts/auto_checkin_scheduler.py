import time
import random
from typing import List, Dict, Any
import asyncio
from datetime import datetime, timezone, timedelta
import os
from api.state import state
from api.utils import get_utc_timestamp, debug_log
from scripts.session_refresh import refresh_session_token, log

# Scheduler Configuration Constants
# ------------------------------
# Initial delay before starting the scheduler
INITIAL_DELAY_SECONDS = 5

# Whether to run a cycle immediately on startup or wait for the first interval
RUN_INITIAL_CYCLE = False

# Time between automated check-in cycles (in seconds)
MIN_SECONDS_BETWEEN_RUNS = 3600  # 1 hour
MAX_SECONDS_BETWEEN_RUNS = 18000  # 5 hours

# For testing, uncomment these values:
# MIN_SECONDS_BETWEEN_RUNS = 3.6   # 3.6 seconds for testing
# MAX_SECONDS_BETWEEN_RUNS = 18    # 18 seconds for testing

# Random delay between processing individual users (in milliseconds)
# This helps avoid detection by spreading out requests
MIN_USER_DELAY_MS = 0
MAX_USER_DELAY_MS = 600000  # 10 minutes max delay between users for stealth


def get_users() -> List[Dict[str, Any]]:
    """Retrieve the list of users configured for automatic check-ins from global state.

    Returns:
        List[Dict[str, Any]]: List of user dictionaries containing email and check-in tokens.
        Returns empty list if no users are configured.
    """
    return state.get_data("autoCheckinUsers") or []


async def run_autocheckin(user: Dict[str, Any]) -> None:
    """Process automatic check-in for a single user by refreshing their session token.

    Updates the user's check-in status and token in global state after the attempt.

    Args:
        user: Dictionary containing user data with required fields:
            - email: User's email address
            - checkintoken: Current check-in token for the user

    Side effects:
        - Updates user's token and check-in status in global state
        - Logs debug information about the check-in attempt
    """
    email = user.get("email")
    token = user.get("checkintoken")

    if not email or not token:
        debug_log(f"Missing email or token for user")
        return

    debug_log(f"Running auto checkin for {email}")

    new_token = refresh_session_token(email, token)
    users = state.get_data("autoCheckinUsers") or []
    current_time = get_utc_timestamp()

    for stored_user in users:
        if stored_user.get("email") == email:
            if new_token:
                debug_log(f"Token refresh successful for {email}")
                stored_user.update(
                    {
                        "checkintoken": new_token,
                        "checkinReport": "Normal",
                        "checkinReportTime": current_time,
                    }
                )
            else:
                debug_log(f"Token refresh failed for {email}")
                stored_user.update(
                    {"checkinReport": "Fail", "checkinReportTime": current_time}
                )
            break

    state.set_data("autoCheckinUsers", users)


async def start_autocheckin_cycle() -> None:
    """Main scheduler loop that processes users at random intervals.

    Implements a stealth-based approach to avoid detection:
    1. Uses random delays between processing cycles (MIN_SECONDS_BETWEEN_RUNS to MAX_SECONDS_BETWEEN_RUNS)
    2. Randomizes user processing order each cycle
    3. Adds random delays between processing each user (MIN_USER_DELAY_MS to MAX_USER_DELAY_MS)

    The function runs indefinitely until interrupted, maintaining the check-in schedule.
    Updates the next scheduled run time in global state for monitoring.
    """
    debug_log("\nStarting auto checkin scheduler")
    debug_log(f"Initial delay: {INITIAL_DELAY_SECONDS} seconds")
    debug_log(f"Run initial cycle: {RUN_INITIAL_CYCLE}")

    await asyncio.sleep(INITIAL_DELAY_SECONDS)

    if not RUN_INITIAL_CYCLE:
        # Calculate and wait for first run if not running immediately
        next_run_ms = (
            random.randint(
                int(MIN_SECONDS_BETWEEN_RUNS * 1000),
                int(MAX_SECONDS_BETWEEN_RUNS * 1000),
            )
            / 1000
        )
        next_run_seconds = next_run_ms
        next_run_time = datetime.now(timezone.utc) + timedelta(seconds=next_run_seconds)
        state.set_data("next_cycle_run_time", next_run_time.isoformat())
        debug_log(f"Waiting {next_run_seconds:.2f} seconds before first cycle")
        debug_log(f"Next run scheduled for: {next_run_time.isoformat()}")
        await asyncio.sleep(next_run_seconds)

    while True:
        debug_log("\nStarting new auto checkin cycle")

        # Get and shuffle users for random processing order
        users = get_users()
        random.shuffle(users)

        debug_log(f"Processing {len(users)} users")

        for user in users:
            # Add random delay between processing each user
            delay_ms = random.randint(MIN_USER_DELAY_MS, int(MAX_USER_DELAY_MS))
            delay_sec = delay_ms / 1000

            debug_log(f"Waiting {delay_sec:.2f} seconds before processing next user")
            await asyncio.sleep(delay_sec)

            await run_autocheckin(user)

        # Schedule next cycle with random delay
        next_run_ms = (
            random.randint(
                int(MIN_SECONDS_BETWEEN_RUNS * 1000),
                int(MAX_SECONDS_BETWEEN_RUNS * 1000),
            )
            / 1000
        )
        next_run_seconds = next_run_ms
        next_run_time = datetime.now(timezone.utc) + timedelta(seconds=next_run_seconds)
        state.set_data("next_cycle_run_time", next_run_time.isoformat())

        debug_log(
            f"Cycle complete. Waiting {next_run_seconds:.2f} seconds before next cycle"
        )
        debug_log(f"Next run scheduled for: {next_run_time.isoformat()}")
        await asyncio.sleep(next_run_seconds)


async def start_scheduler() -> None:
    """Entry point for the auto check-in scheduler.

    Runs the scheduler continuously, automatically restarting if an error occurs.
    This provides resilience against temporary failures and ensures the service
    keeps running.

    Note: This function will run indefinitely until the program is terminated.
    """
    try:
        await start_autocheckin_cycle()
    except Exception as e:
        debug_log(f"Error in auto checkin scheduler: {str(e)}")
        await start_scheduler()


if __name__ == "__main__":
    asyncio.run(start_scheduler())
