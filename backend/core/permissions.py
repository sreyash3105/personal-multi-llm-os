from __future__ import annotations

from typing import Dict, Any, List, Optional

from backend.modules.security.permission_manager import (
    get_active_permissions,
    get_permission_usage_log,
    get_permission_stats,
)


def get_permissions_stats(profile_id: Optional[str] = None) -> Dict[str, Any]:
    return get_permission_stats(profile_id)


def list_active_permissions(
    profile_id: str,
    include_expired: bool = False,
    limit: int = 50
) -> List[Dict[str, Any]]:
    if not profile_id or not profile_id.strip():
        raise ValueError("profile_id must be non-empty string")
    return get_active_permissions(
        profile_id=profile_id,
        include_expired=include_expired,
        limit=limit,
    )


def get_permission_usage_request(
    permission_id: int,
    limit: int = 100
) -> List[Dict[str, Any]]:
    return get_permission_usage_log(permission_id=permission_id, limit=limit)
