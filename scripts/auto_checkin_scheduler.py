import time
import random
from typing import List, Dict, Any
import asyncio
from datetime import datetime, timezone, timedelta
import os
from api.state import state
from api.utils import get_utc_timestamp, debug_log
from scripts.session_refresh import refresh_session_token, log

# Scheduler configuration constants
INITIAL_DELAY_SECONDS = 5
RUN_INITIAL_CYCLE = False
MIN_MS_BETWEEN_RUNS = 3600  # 3.6 seconds for testing (would be 3600 for 1 hour in production)
MAX_MS_BETWEEN_RUNS = 18000  # 18 seconds for testing (would be 18000 for 5 hours in production)
MIN_USER_DELAY_MS = 0
MAX_USER_DELAY_MS = 60  # 10 minutes max delay between users for stealth

def get_users() -> List[Dict[str, Any]]:
    """Get list of users from global state"""
    return state.get_data('autoCheckinUsers') or []

async def run_autocheckin(user: Dict[str, Any]) -> None:
    """Process auto checkin for a single user by refreshing their session token.
    
    Args:
        user: Dictionary containing user data including email and checkin token.
    """
    email = user.get('email')
    token = user.get('checkintoken')
    
    if not email or not token:
        debug_log(f"Missing email or token for user")
        return
        
    debug_log(f"Running auto checkin for {email}")
    
    new_token = refresh_session_token(email, token)
    users = state.get_data('autoCheckinUsers') or []
    current_time = get_utc_timestamp()
    
    for stored_user in users:
        if stored_user.get('email') == email:
            if new_token:
                debug_log(f"Token refresh successful for {email}")
                stored_user.update({
                    'checkintoken': new_token,
                    'checkinReport': 'Normal',
                    'checkinReportTime': current_time
                })
            else:
                debug_log(f"Token refresh failed for {email}")
                stored_user.update({
                    'checkinReport': 'Fail',
                    'checkinReportTime': current_time
                })
            break
            
    state.set_data('autoCheckinUsers', users)

async def start_autocheckin_cycle() -> None:
    """Main scheduler loop that processes users at random intervals.
    
    Implements a stealth-based approach:
    1. Randomizes the delay between processing cycles
    2. Shuffles user order each cycle
    3. Adds random delays between processing each user
    """
    debug_log("\nStarting auto checkin scheduler")
    debug_log(f"Initial delay: {INITIAL_DELAY_SECONDS} seconds")
    debug_log(f"Run initial cycle: {RUN_INITIAL_CYCLE}")
    
    await asyncio.sleep(INITIAL_DELAY_SECONDS)
    
    if not RUN_INITIAL_CYCLE:
        next_run_ms = random.randint(int(MIN_MS_BETWEEN_RUNS * 1000), int(MAX_MS_BETWEEN_RUNS * 1000)) / 1000
        next_run_seconds = next_run_ms
        next_run_time = datetime.now(timezone.utc) + timedelta(seconds=next_run_seconds)
        state.set_data('next_cycle_run_time', next_run_time.isoformat())
        debug_log(f"Waiting {next_run_seconds:.2f} seconds before first cycle")
        debug_log(f"Next run scheduled for: {next_run_time.isoformat()}")
        await asyncio.sleep(next_run_seconds)
    
    while True:
        debug_log("\nStarting new auto checkin cycle")
        
        users = get_users()
        random.shuffle(users)
        
        debug_log(f"Processing {len(users)} users")
        
        for user in users:
            delay_ms = random.randint(MIN_USER_DELAY_MS, int(MAX_USER_DELAY_MS))
            delay_sec = delay_ms / 1000
            
            debug_log(f"Waiting {delay_sec:.2f} seconds before processing next user")
            await asyncio.sleep(delay_sec)
            
            await run_autocheckin(user)
        
        next_run_ms = random.randint(int(MIN_MS_BETWEEN_RUNS * 1000), int(MAX_MS_BETWEEN_RUNS * 1000)) / 1000
        next_run_seconds = next_run_ms
        next_run_time = datetime.now(timezone.utc) + timedelta(seconds=next_run_seconds)
        state.set_data('next_cycle_run_time', next_run_time.isoformat())
        
        debug_log(f"Cycle complete. Waiting {next_run_seconds:.2f} seconds before next cycle")
        debug_log(f"Next run scheduled for: {next_run_time.isoformat()}")
        await asyncio.sleep(next_run_seconds)

async def start_scheduler() -> None:
    """Entry point for the auto checkin scheduler.
    
    Runs continuously, restarting the cycle if an error occurs.
    """
    try:
        await start_autocheckin_cycle()
    except Exception as e:
        debug_log(f"Error in auto checkin scheduler: {str(e)}")
        await start_scheduler()

if __name__ == "__main__":
    asyncio.run(start_scheduler()) 