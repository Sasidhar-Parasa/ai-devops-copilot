"""
Session Manager — Tracks per-session conversation state.
Handles the "copilot flow": remember what we're mid-deploying,
what info has been collected, what's still missing.
"""
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# In-memory session store (fine for single-instance / demo)
_sessions: Dict[str, Dict[str, Any]] = {}
SESSION_TTL = 3600  # 1 hour


def get_session(session_id: str) -> Dict[str, Any]:
    """Get or create a session."""
    now = time.time()
    if session_id not in _sessions:
        _sessions[session_id] = _new_session(session_id)
    session = _sessions[session_id]
    session["last_access"] = now
    _evict_old_sessions(now)
    return session


def update_session(session_id: str, **kwargs):
    """Update session fields."""
    session = get_session(session_id)
    session.update(kwargs)


def clear_deploy_context(session_id: str):
    """Clear deployment-in-progress context after completion."""
    session = get_session(session_id)
    session["pending_intent"] = None
    session["pending_repo_url"] = None
    session["pending_app_name"] = None
    session["pending_version"] = None


def get_pending_deploy(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Returns pending deployment context if we're mid-conversation.
    e.g. user said 'deploy myapp' and we asked for repo URL.
    """
    session = get_session(session_id)
    if session.get("pending_intent") == "deploy_request" and session.get("pending_app_name"):
        return {
            "app_name": session["pending_app_name"],
            "version":  session.get("pending_version", "latest"),
        }
    return None


def set_pending_deploy(session_id: str, app_name: str, version: str = "latest"):
    update_session(session_id,
                   pending_intent="deploy_request",
                   pending_app_name=app_name,
                   pending_version=version)


def _new_session(session_id: str) -> Dict[str, Any]:
    return {
        "session_id": session_id,
        "created_at": time.time(),
        "last_access": time.time(),
        "pending_intent": None,
        "pending_repo_url": None,
        "pending_app_name": None,
        "pending_version": None,
        "deployment_history": [],
    }


def _evict_old_sessions(now: float):
    expired = [k for k, v in _sessions.items() if now - v["last_access"] > SESSION_TTL]
    for k in expired:
        del _sessions[k]
