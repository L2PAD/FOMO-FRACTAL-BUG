"""Missed Signals & Activity Tracking routes."""
from fastapi import APIRouter, Query, Depends
from typing import Optional
from routes.auth import get_current_user
from services.asset_registry import normalize_symbol
from services.missed_engine import (
    mark_user_seen, mark_signal_exposure,
    get_missed_signals as get_honest_missed_signals,
)

router = APIRouter()


@router.get("/missed")
async def get_missed(asset: Optional[str] = Query(default=None), user=Depends(get_current_user)):
    user_id = str(user['_id'])
    asset_key = normalize_symbol(asset) if asset else None
    return get_honest_missed_signals(user_id, asset_key, limit=3)


@router.post("/activity/seen")
async def mark_seen(body: dict, user=Depends(get_current_user)):
    return {"ok": mark_user_seen(str(user['_id']), body.get('screen', 'home'))}


@router.post("/signal-exposure")
async def track_signal_exposure(body: dict, user=Depends(get_current_user)):
    signal_id = body.get('signalId', '')
    if not signal_id:
        return {"ok": False, "error": "signalId required"}
    return {"ok": mark_signal_exposure(str(user['_id']), signal_id, screen=body.get('screen', 'home'))}
