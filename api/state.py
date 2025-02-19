import json
import os
from typing import Dict, Any
from .checkout_client import CheckOutClient
from .utils import debug_log

STATE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "state.json"
)


class GlobalState:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GlobalState, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize the state file if it doesn't exist"""
        self.default_state = {
            "connected": False,
            "last_users_fetch": None,
            "last_all_session_refresh": None,
            "last_individual_session_refresh": None,
            "next_cycle_run_time": None,
            "last_attendance_fetch_run": None,
            "autoCheckinUsers": [],
        }

        # Create state file if it doesn't exist
        if not os.path.exists(STATE_FILE):
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            self._save_state(self.default_state)

    def _load_state(self) -> Dict[str, Any]:
        """Load state from JSON file"""
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return self.default_state.copy()

    def _save_state(self, state: Dict[str, Any]) -> None:
        """Save state to JSON file"""
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

    def set_connected(self, status: bool) -> None:
        state = self._load_state()
        if state["connected"] != status:
            state["connected"] = status
            self._save_state(state)
            debug_log(f"Connection status changed to: {status}")

    def is_connected(self) -> bool:
        return self._load_state()["connected"]

    def set_data(self, key: str, value: Any) -> None:
        state = self._load_state()
        debug_log(f"Setting state data for key: {key}")
        state[key] = value
        self._save_state(state)
        debug_log(f"State data after update - {key}: {value}")

    def get_data(self, key: str) -> Any:
        return self._load_state().get(key)

    def dump_state(self) -> None:
        """Debug method to dump entire state"""
        state = self._load_state()
        debug_log("\n=== CURRENT STATE DUMP ===")
        for key, value in state.items():
            debug_log(f"{key}: {value}")
        debug_log("=========================\n")


# Create a global instance
state = GlobalState()


def test_connection() -> bool:
    """Test connection to the checkout API"""
    client = CheckOutClient()
    return client.test_connection()


def fetch_and_update_state() -> bool:
    """
    Fetch users and update connection state based on the result

    Returns:
        bool: True if successful, False if failed
    """
    from .fetch_users import fetch_users  # Import here to avoid circular imports

    success = fetch_users()
    if not success:
        state.set_connected(False)
    return success


def connection_monitor() -> None:
    """Monitor connection status and fetch users periodically"""
    import time

    RETRY_INTERVAL = 60  # Retry every minute when disconnected
    UPDATE_INTERVAL = 3600  # Update every hour when connected

    while True:
        success = test_connection()
        state.set_connected(success)

        if success:
            # Try to fetch users immediately after connecting
            fetch_success = fetch_and_update_state()
            if fetch_success:
                time.sleep(UPDATE_INTERVAL)
            else:
                time.sleep(RETRY_INTERVAL)
        else:
            time.sleep(RETRY_INTERVAL)
