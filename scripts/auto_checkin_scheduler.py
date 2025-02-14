import time
import random
from typing import List, Dict, Any
import asyncio
from datetime import datetime, timezone
import os
from api.state import state
from scripts.session_refresh import refresh_session_token, get_utc_timestamp

# Scheduler configuration constants
INITIAL_DELAY_SECONDS = 5
RUN_INITIAL_CYCLE = True
MIN_HOURS_BETWEEN_RUNS = 1
MAX_HOURS_BETWEEN_RUNS = 5
MIN_USER_DELAY_MS = 0
MAX_USER_DELAY_MS = 600000  # 10 minutes max delay between users for stealth

def get_users() -> List[Dict[str, Any]]:
    """Retrieve registered users from the global state.
    
    Returns:
        List[Dict[str, Any]]: List of user dictionaries containing email and session tokens.
    """
    if os.getenv('FLASK_DEBUG') == '1':
        print("\n[DEBUG] Fetching users from stored data")
    
    users = state.get_data('autoCheckinUsers') or []
    
    if os.getenv('FLASK_DEBUG') == '1':
        print(f"[DEBUG] Found {len(users)} users")
    
    return users

async def run_autocheckin(user: Dict[str, Any]) -> None:
    """Process auto checkin for a single user by refreshing their session token.
    
    Args:
        user: Dictionary containing user data including email and checkin token.
    """
    email = user.get('email')
    token = user.get('checkintoken')
    
    if not email or not token:
        if os.getenv('FLASK_DEBUG') == '1':
            print(f"[DEBUG] Missing email or token for user")
        return
        
    if os.getenv('FLASK_DEBUG') == '1':
        print(f"[DEBUG] Running auto checkin for {email}")
    
    new_token = refresh_session_token(email, token)
    users = state.get_data('autoCheckinUsers') or []
    current_time = get_utc_timestamp()
    
    for stored_user in users:
        if stored_user.get('email') == email:
            if new_token:
                if os.getenv('FLASK_DEBUG') == '1':
                    print(f"[DEBUG] Token refresh successful for {email}")
                stored_user.update({
                    'checkintoken': new_token,
                    'checkinReport': 'Normal',
                    'checkinReportTime': current_time
                })
            else:
                if os.getenv('FLASK_DEBUG') == '1':
                    print(f"[DEBUG] Token refresh failed for {email}")
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
    if os.getenv('FLASK_DEBUG') == '1':
        print("\n[DEBUG] Starting auto checkin scheduler")
        print(f"[DEBUG] Initial delay: {INITIAL_DELAY_SECONDS} seconds")
        print(f"[DEBUG] Run initial cycle: {RUN_INITIAL_CYCLE}")
    
    await asyncio.sleep(INITIAL_DELAY_SECONDS)
    
    if not RUN_INITIAL_CYCLE:
        next_run_hours = random.randint(MIN_HOURS_BETWEEN_RUNS, MAX_HOURS_BETWEEN_RUNS)
        next_run_seconds = next_run_hours * 3600
        if os.getenv('FLASK_DEBUG') == '1':
            print(f"[DEBUG] Waiting {next_run_hours} hours before first cycle")
        await asyncio.sleep(next_run_seconds)
    
    while True:
        if os.getenv('FLASK_DEBUG') == '1':
            print("\n[DEBUG] Starting new auto checkin cycle")
        
        users = get_users()
        random.shuffle(users)
        
        if os.getenv('FLASK_DEBUG') == '1':
            print(f"[DEBUG] Processing {len(users)} users")
        
        for user in users:
            delay_ms = random.randint(MIN_USER_DELAY_MS, MAX_USER_DELAY_MS)
            delay_sec = delay_ms / 1000
            
            if os.getenv('FLASK_DEBUG') == '1':
                print(f"[DEBUG] Waiting {delay_sec:.2f} seconds before processing next user")
            await asyncio.sleep(delay_sec)
            
            await run_autocheckin(user)
        
        next_run_hours = random.randint(MIN_HOURS_BETWEEN_RUNS, MAX_HOURS_BETWEEN_RUNS)
        next_run_seconds = next_run_hours * 3600
        
        if os.getenv('FLASK_DEBUG') == '1':
            print(f"[DEBUG] Cycle complete. Waiting {next_run_hours} hours before next cycle")
        await asyncio.sleep(next_run_seconds)

async def start_scheduler() -> None:
    """Entry point for the auto checkin scheduler.
    
    Runs continuously, restarting the cycle if an error occurs.
    """
    try:
        await start_autocheckin_cycle()
    except Exception as e:
        if os.getenv('FLASK_DEBUG') == '1':
            print(f"[DEBUG] Error in auto checkin scheduler: {str(e)}")
        await start_scheduler()

if __name__ == "__main__":
    asyncio.run(start_scheduler()) 