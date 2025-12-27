"""
confirmation_router.py (Phase B)

Handles confirmation flow for perception-gated actions.
Provides endpoints for submitting confirmations and managing pending actions.
"""

from __future__ import annotations

import uuid
import time
import threading
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.config import CONFIRMATION_TTL_SECONDS, CONFIRMATION_CLEANUP_INTERVAL_SECONDS
from backend.modules.telemetry.history import history_logger

router = APIRouter()

# In-memory store for pending confirmations
# In production, this would be persistent storage
_pending_confirmations: Dict[str, Dict[str, Any]] = {}
_pending_lock = threading.Lock()

# Cleanup thread
_cleanup_thread: Optional[threading.Thread] = None
_cleanup_stop_event = threading.Event()

class ConfirmationSubmit(BaseModel):
    token: str
    decision: str  # "confirm" or "cancel"

def generate_confirmation_token() -> str:
    """Generate a unique token for confirmation requests."""
    return str(uuid.uuid4())

def create_confirmation_request(
    message: str,
    action_data: Dict[str, Any],
    confidence_metadata: Dict[str, Any],
    ttl_seconds: Optional[int] = None
) -> Dict[str, Any]:
    """
    Create a confirmation request for low-confidence perception results.

    Args:
        message: Human-readable message for confirmation
        action_data: Data about the action being confirmed
        confidence_metadata: Confidence assessment details
        ttl_seconds: Time-to-live in seconds (default from config)

    Returns:
        Confirmation request dict
    """
    token = generate_confirmation_token()
    ttl = ttl_seconds or CONFIRMATION_TTL_SECONDS
    expires_at = time.time() + ttl

    with _pending_lock:
        _pending_confirmations[token] = {
            "action_data": action_data,
            "confidence_metadata": confidence_metadata,
            "message": message,
            "created_at": time.time(),
            "expires_at": expires_at,
            "used": False,  # Prevent replay
        }

    # Log confirmation creation
    try:
        history_logger.log({
            "kind": "confirmation_created",
            "token": token,
            "message": message,
            "confidence_level": confidence_metadata.get("confidence_level"),
            "confidence_score": confidence_metadata.get("confidence_score"),
            "ttl_seconds": ttl,
            "expires_at": expires_at,
        })
    except Exception:
        pass  # Logging failure shouldn't break confirmation

    return {
        "status": "confirmation_required",
        "token": token,
        "message": message,
        "confidence_level": confidence_metadata.get("confidence_level"),
        "confidence_score": confidence_metadata.get("confidence_score"),
        "expires_at": expires_at,
    }

def get_pending_confirmation(token: str) -> Dict[str, Any] | None:
    """Retrieve pending confirmation by token."""
    with _pending_lock:
        confirmation = _pending_confirmations.get(token)
        if confirmation and time.time() > confirmation.get("expires_at", 0):
            # Expired, remove it
            _pending_confirmations.pop(token, None)
            return None
        return confirmation


def _cleanup_expired_confirmations() -> int:
    """Remove expired confirmations. Returns count removed."""
    now = time.time()
    expired_tokens = []
    with _pending_lock:
        expired_tokens = [
            token for token, data in _pending_confirmations.items()
            if now > data.get("expires_at", 0)
        ]
        for token in expired_tokens:
            _pending_confirmations.pop(token, None)

    # Log cleanup outside lock
    for token in expired_tokens:
        try:
            history_logger.log({
                "kind": "confirmation_expired",
                "token": token,
                "message": "Confirmation expired and removed",
            })
        except Exception:
            pass

    return len(expired_tokens)


def _cleanup_worker():
    """Background worker to periodically clean up expired confirmations."""
    while not _cleanup_stop_event.is_set():
        try:
            removed_count = _cleanup_expired_confirmations()
            if removed_count > 0:
                print(f"[CONFIRMATION] Cleaned up {removed_count} expired confirmations")
        except Exception as e:
            print(f"[CONFIRMATION] Cleanup error: {e}")

        _cleanup_stop_event.wait(CONFIRMATION_CLEANUP_INTERVAL_SECONDS)


def start_cleanup_worker():
    """Start the background cleanup worker."""
    global _cleanup_thread
    if _cleanup_thread is None or not _cleanup_thread.is_alive():
        _cleanup_stop_event.clear()
        _cleanup_thread = threading.Thread(target=_cleanup_worker, daemon=True)
        _cleanup_thread.start()


def stop_cleanup_worker():
    """Stop the background cleanup worker."""
    _cleanup_stop_event.set()
    if _cleanup_thread and _cleanup_thread.is_alive():
        _cleanup_thread.join(timeout=5.0)

@router.post("/api/confirmation/submit")
def submit_confirmation(request: ConfirmationSubmit) -> Dict[str, Any]:
    """
    Submit a confirmation decision for a pending action.

    Returns the action data if confirmed, or cancellation status.
    """
    token = request.token
    decision = request.decision

    with _pending_lock:
        confirmation_data = _pending_confirmations.get(token)
        if not confirmation_data:
            raise HTTPException(status_code=404, detail="Confirmation token not found or expired")

        if confirmation_data.get("used", False):
            raise HTTPException(status_code=409, detail="Confirmation already used")

        # Mark as used and remove
        confirmation_data["used"] = True
        _pending_confirmations.pop(token, None)

    # Log the decision
    try:
        history_logger.log({
            "kind": "confirmation_submitted",
            "token": token,
            "decision": decision,
            "message": confirmation_data["message"],
            "confidence_level": confirmation_data["confidence_metadata"].get("confidence_level"),
        })
    except Exception:
        pass

    if decision == "confirm":
        return {
            "status": "confirmed",
            "action_data": confirmation_data["action_data"],
            "confidence_metadata": confirmation_data["confidence_metadata"],
        }
    elif decision == "cancel":
        return {
            "status": "cancelled",
            "message": "Action cancelled by user",
        }
    else:
        raise HTTPException(status_code=400, detail="Invalid decision. Must be 'confirm' or 'cancel'")

@router.get("/api/confirmation/pending/{token}")
def get_confirmation_status(token: str) -> Dict[str, Any]:
    """
    Check status of a pending confirmation.
    """
    if token not in _pending_confirmations:
        raise HTTPException(status_code=404, detail="Confirmation token not found")

    confirmation_data = _pending_confirmations[token]
    return {
        "status": "pending",
        "message": confirmation_data["message"],
        "confidence_level": confirmation_data["confidence_metadata"].get("confidence_level"),
        "confidence_score": confirmation_data["confidence_metadata"].get("confidence_score"),
    }

@router.delete("/api/confirmation/pending/{token}")
def cancel_pending_confirmation(token: str) -> Dict[str, Any]:
    """
    Cancel a pending confirmation without executing the action.
    """
    with _pending_lock:
        confirmation_data = _pending_confirmations.get(token)
        if not confirmation_data:
            raise HTTPException(status_code=404, detail="Confirmation token not found or expired")

        _pending_confirmations.pop(token, None)

    # Log cancellation
    try:
        history_logger.log({
            "kind": "confirmation_cancelled",
            "token": token,
            "message": confirmation_data["message"],
        })
    except Exception:
        pass

    return {"status": "cancelled", "message": "Pending confirmation cancelled"}


@router.get("/api/confirmation/stats")
def get_confirmation_stats() -> Dict[str, Any]:
    """
    Get read-only statistics about confirmations.
    """
    now = time.time()
    active = 0
    expired = 0
    total_created = 0  # Would need persistent storage for accurate count

    for token, data in _pending_confirmations.items():
        if now > data.get("expires_at", 0):
            expired += 1
        else:
            active += 1

    return {
        "active_confirmations": active,
        "expired_confirmations": expired,
        "total_in_memory": len(_pending_confirmations),
    }


@router.get("/api/confirmation/active")
def get_active_confirmations() -> List[Dict[str, Any]]:
    """
    Get list of active (non-expired) confirmations.
    """
    now = time.time()
    active = []
    with _pending_lock:
        for token, data in _pending_confirmations.items():
            if now <= data.get("expires_at", 0):
                active.append({
                    "token": token,
                    "message": data["message"],
                    "confidence_level": data["confidence_metadata"].get("confidence_level"),
                    "confidence_score": data["confidence_metadata"].get("confidence_score"),
                    "expires_at": data["expires_at"],
                    "created_at": data["created_at"],
                })
    return active


# Start cleanup worker on module import
start_cleanup_worker()

# Register cleanup on exit
import atexit
atexit.register(stop_cleanup_worker)