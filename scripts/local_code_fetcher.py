# scripts/local_code_fetcher.py
import os
import time
import requests
import json
from typing import List, Set

from api.utils import (
    read_local_user_data,
    write_local_user_data,
    debug_log,
)

FETCH_INTERVAL_SECONDS = 10

def run_local_code_fetcher():
    """
    Periodically fetches codes from the user-defined URL and updates
    user.json with available, untried codes. Runs indefinitely.
    """
    debug_log("Starting local code fetcher background task.")
    while True:
        try:
            user_data = read_local_user_data()
            codes_url = user_data.get("codes_url")
            
            if not codes_url:
                debug_log("Local code fetcher: No codes_url configured in user.json. Sleeping.")
                time.sleep(FETCH_INTERVAL_SECONDS)
                continue

            # Fetch codes from the external URL
            fetched_codes: List[str] = []
            try:
                debug_log(f"Local code fetcher: Fetching codes from {codes_url}")
                response = requests.get(codes_url, timeout=10)
                response.raise_for_status()
                
                # --- Adapt parsing based on actual API response structure ---
                # Assuming response JSON is like: {"codes": ["111111", "222222"]}
                # Or maybe: {"sessions": [{"codes": [{"checkinCode": "111111"}, ...]}, ...]}
                
                data = response.json()
                
                # Example 1: Direct list under "codes" key
                if isinstance(data.get("codes"), list):
                     fetched_codes = [str(code) for code in data["codes"]]

                # Example 2: Nested structure like CheckOut API uses (adapt if needed)
                elif isinstance(data.get("sessions"), list):
                     all_session_codes = []
                     for session in data["sessions"]:
                         if isinstance(session.get("codes"), list):
                              all_session_codes.extend(
                                 [str(c.get("checkinCode")) for c in session["codes"] if c.get("checkinCode")]
                              )
                     fetched_codes = list(set(all_session_codes)) # Get unique codes

                else:
                     debug_log(f"Local code fetcher: Unexpected JSON structure from {codes_url}. Found keys: {list(data.keys())}")

                debug_log(f"Local code fetcher: Fetched {len(fetched_codes)} codes: {fetched_codes}")
                # ----------------------------------------------------------

            except requests.exceptions.RequestException as e:
                debug_log(f"Local code fetcher: HTTP error fetching codes from {codes_url}: {e}")
                # Continue to next iteration after sleep
            except json.JSONDecodeError as e:
                 debug_log(f"Local code fetcher: Error decoding JSON from {codes_url}: {e}")
            except Exception as e:
                debug_log(f"Local code fetcher: Unexpected error fetching codes: {e}")
                # Continue to next iteration after sleep


            # --- Update user.json ---
            if fetched_codes: # Only proceed if codes were actually fetched
                current_user_data = read_local_user_data() 
                if not current_user_data:
                    debug_log("Local code fetcher: Could not read user data after fetching codes. Skipping update.")
                    time.sleep(FETCH_INTERVAL_SECONDS)
                    continue

                # Get current sets
                tried_codes_set: Set[str] = set(current_user_data.get("tried_codes", []))
                current_untried_set: Set[str] = set(current_user_data.get("available_untried_codes", []))
                
                # Filter newly fetched codes
                added_count = 0
                newly_added_to_untried = set()
                for code in fetched_codes:
                    # Add if NOT in tried AND NOT already in untried
                    if code not in tried_codes_set and code not in current_untried_set:
                        newly_added_to_untried.add(code)
                        added_count += 1
                
                # Update the user data dictionary only if new codes were added
                if added_count > 0:
                    final_untried_set = current_untried_set.union(newly_added_to_untried)
                    current_user_data["available_untried_codes"] = sorted(list(final_untried_set))
                    # Ensure tried_codes is also stored sorted (might not be necessary here, but good practice)
                    current_user_data["tried_codes"] = sorted(list(tried_codes_set)) 
                    
                    debug_log(f"Local code fetcher: Added {added_count} new untried codes: {sorted(list(newly_added_to_untried))}. Total untried: {len(final_untried_set)}.")

                    if not write_local_user_data(current_user_data):
                        debug_log("Local code fetcher: Failed to write updated untried codes to user.json.")
                else:
                     debug_log(f"Local code fetcher: No new untried codes to add from fetch ({len(fetched_codes)} fetched).")
            # ----------------------

        except Exception as e:
            # Catch broad exceptions in the main loop to prevent thread death
            debug_log(f"Local code fetcher: Error in main loop: {e}")

        # Wait before the next fetch cycle
        time.sleep(FETCH_INTERVAL_SECONDS) 