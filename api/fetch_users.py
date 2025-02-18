from typing import List, Dict, Any
from .checkout_client import CheckOutClient, CheckOutAPIError
from .state import state
from datetime import datetime


def fetch_users() -> bool:
    """
    Fetch users from the CheckOut API and update the global state

    Returns:
        bool: True if successful, False if failed
    """
    client = CheckOutClient()

    try:
        response = client.get("users")
        users = response.get("autoCheckinUsers", [])
        state.set_data("autoCheckinUsers", users)
        state.set_data("last_users_fetch", datetime.utcnow().isoformat())
        return True

    except CheckOutAPIError as e:
        print(f"Failed to fetch users: {str(e)}")
        return False
