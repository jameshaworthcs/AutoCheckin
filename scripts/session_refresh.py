from typing import List, Dict, Any, Optional
from api.state import state
from datetime import datetime

def get_all_refresh_sessions() -> List[Dict[str, Any]]:
    """Refresh all sessions for all users"""
    sessions = state.get_data('autoCheckinUsers') or []
    state.set_data('last_all_session_refresh', datetime.utcnow().isoformat())
    return sessions

def get_refresh_session_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Refresh a specific session by email"""
    sessions = get_all_refresh_sessions()
    session = next((session for session in sessions if session.get('email') == email), None)
    if session is not None:
        state.set_data('last_individual_session_refresh', datetime.utcnow().isoformat())
    return session 