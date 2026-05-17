"""Brain Snapshot API — Single Source of Truth for Mobile + Web."""
from fastapi import APIRouter, Query
from typing import Optional
from services.meta_brain_service import build_snapshot, invalidate_cache

router = APIRouter()


@router.get("/brain/snapshot")
def get_snapshot(asset: Optional[str] = Query(default="BTC")):
    """
    Unified brain snapshot — THE SINGLE SOURCE OF TRUTH.
    All modules aggregated into one response.
    Mobile + Web consume this same output.
    """
    return build_snapshot(asset.upper() if asset else "BTC")


@router.post("/brain/refresh")
def refresh_snapshot(asset: Optional[str] = Query(default="BTC")):
    """Force refresh the brain snapshot (invalidate cache)."""
    invalidate_cache(asset.upper() if asset else None)
    return build_snapshot(asset.upper() if asset else "BTC")
