import threading
import time
import os
from typing import Dict, Any
from .checkout_client import CheckOutClient

class GlobalState:
    def __init__(self):
        self.connected = False
        self.data: Dict[str, Any] = {
            'last_users_fetch': None,
            'last_all_session_refresh': None,
            'last_individual_session_refresh': None,
            'next_cycle_run_time': None
        }
        self._lock = threading.Lock()
        
    def set_connected(self, status: bool) -> None:
        with self._lock:
            if self.connected != status:
                self.connected = status
                if os.getenv('FLASK_DEBUG') == '1':
                    print(f"Connection status changed to: {status}")
    
    def is_connected(self) -> bool:
        with self._lock:
            return self.connected
    
    def set_data(self, key: str, value: Any) -> None:
        with self._lock:
            self.data[key] = value
    
    def get_data(self, key: str) -> Any:
        with self._lock:
            return self.data.get(key)

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