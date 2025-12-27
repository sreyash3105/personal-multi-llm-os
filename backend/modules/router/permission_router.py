"""
permission_router.py (Phase C2)

Read-only API endpoints for permission introspection.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Query

from backend.modules.security.permission_manager import (
    get_active_permissions,
    get_permission_usage_log,
    get_permission_stats,
)

router = APIRouter()


@router.get("/api/permissions/stats")
def get_permissions_stats(profile_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    """
    Get permission statistics.
    """
    return get_permission_stats(profile_id)


@router.get("/api/permissions/active")
def list_active_permissions(
    profile_id: str = Query(...),
    include_expired: bool = Query(False),
    limit: int = Query(50, ge=1, le=1000),
) -> List[Dict[str, Any]]:
    """
    List active permissions for a profile.
    """
    return get_active_permissions(
        profile_id=profile_id,
        include_expired=include_expired,
        limit=limit,
    )


@router.get("/api/permissions/{permission_id}/usage")
def get_permission_usage(
    permission_id: int,
    limit: int = Query(100, ge=1, le=1000),
) -> List[Dict[str, Any]]:
    """
    Get usage log for a specific permission.
    """
    return get_permission_usage_log(permission_id=permission_id, limit=limit)