from __future__ import annotations

import threading
import time
from typing import Dict, Any, Optional, List
import uuid

from backend.core.config import CONFIRMATION_TTL_SECONDS, CONFIRMATION_CLEANUP_INTERVAL_SECONDS
from backend.modules.telemetry.history import history_logger

_pending_confirmations: Dict[str, Dict[str, Any]] = {}
_pending_lock = threading.Lock()

_cleanup_thread: Optional[threading.Thread] = None
_cleanup_stop_event = threading.Event()


def generate_confirmation_token() -> str:
    return str(uuid.uuid4())


def create_confirmation_request(
    message: str,
    action_data: Dict[str, Any],
    confidence_metadata: Dict[str, Any],
    ttl_seconds: Optional[int] = None
) -> Dict[str, Any]:
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
            "used": False,
        }

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
        pass

    return {
        "status": "confirmation_required",
        "token": token,
        "message": message,
        "confidence_level": confidence_metadata.get("confidence_level"),
        "confidence_score": confidence_metadata.get("confidence_score"),
        "expires_at": expires_at,
    }


def get_pending_confirmation(token: str) -> Dict[str, Any] | None:
    with _pending_lock:
        confirmation = _pending_confirmations.get(token)
        if confirmation and time.time() > confirmation.get("expires_at", 0):
            _pending_confirmations.pop(token, None)
            return None
        return confirmation


def _cleanup_expired_confirmations() -> int:
    now = time.time()
    expired_tokens = []
    with _pending_lock:
        expired_tokens = [
            token for token, data in _pending_confirmations.items()
            if now > data.get("expires_at", 0)
        ]
        for token in expired_tokens:
            _pending_confirmations.pop(token, None)

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
    while not _cleanup_stop_event.is_set():
        try:
            removed_count = _cleanup_expired_confirmations()
            if removed_count > 0:
                print(f"[CONFIRMATION] Cleaned up {removed_count} expired confirmations")
        except Exception as e:
            print(f"[CONFIRMATION] Cleanup error: {e}")

        _cleanup_stop_event.wait(CONFIRMATION_CLEANUP_INTERVAL_SECONDS)


def start_cleanup_worker():
    global _cleanup_thread
    if _cleanup_thread is None or not _cleanup_thread.is_alive():
        _cleanup_stop_event.clear()
        _cleanup_thread = threading.Thread(target=_cleanup_worker, daemon=True)
        _cleanup_thread.start()


def stop_cleanup_worker():
    _cleanup_stop_event.set()
    if _cleanup_thread and _cleanup_thread.is_alive():
        _cleanup_thread.join(timeout=5.0)


def submit_confirmation(token: str, decision: str) -> Dict[str, Any]:
    with _pending_lock:
        confirmation_data = _pending_confirmations.get(token)
        if not confirmation_data:
            return {"status": "error", "error": "Confirmation token not found or expired"}

        if confirmation_data.get("used", False):
            return {"status": "error", "error": "Confirmation already used"}

        confirmation_data["used"] = True
        _pending_confirmations.pop(token, None)

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
        return {"status": "error", "error": "Invalid decision. Must be 'confirm' or 'cancel'"}


def get_confirmation_status(token: str) -> Dict[str, Any]:
    confirmation_data = _pending_confirmations.get(token)
    if not confirmation_data:
        return {"status": "error", "error": "Confirmation token not found"}

    return {
        "status": "pending",
        "message": confirmation_data["message"],
        "confidence_level": confirmation_data["confidence_metadata"].get("confidence_level"),
        "confidence_score": confirmation_data["confidence_metadata"].get("confidence_score"),
    }


def cancel_pending_confirmation(token: str) -> Dict[str, Any]:
    with _pending_lock:
        confirmation_data = _pending_confirmations.get(token)
        if not confirmation_data:
            return {"status": "error", "error": "Confirmation token not found or expired"}

        _pending_confirmations.pop(token, None)

    try:
        history_logger.log({
            "kind": "confirmation_cancelled",
            "token": token,
            "message": confirmation_data["message"],
        })
    except Exception:
        pass

    return {"status": "cancelled", "message": "Pending confirmation cancelled"}


def get_confirmation_stats() -> Dict[str, Any]:
    now = time.time()
    active = 0
    expired = 0

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


def get_active_confirmations() -> List[Dict[str, Any]]:
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


start_cleanup_worker()

import atexit
atexit.register(stop_cleanup_worker)
