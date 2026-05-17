"""Trading routes — Virtual trading execution."""
from fastapi import APIRouter, Depends, Body
from typing import Optional
from routes.auth import get_current_user
from services.virtual_trading import (
    open_position, close_position, get_positions, get_portfolio_summary,
)
from services.ingestion import ensure_fresh_data

router = APIRouter()


@router.get("/trading/bootstrap")
def get_trading_bootstrap(user=Depends(get_current_user)):
    uid = str(user.get("_id", ""))
    summary = get_portfolio_summary(uid)
    return {
        "status": "ACTIVE",
        "hasAccess": True,
        "modules": {"markets": True, "trade": True, "positions": True},
        "portfolio": summary,
    }


@router.post("/trading/open")
def open_trade(
    asset: str = Body(...),
    action: str = Body(...),
    entry_price: Optional[float] = Body(default=None),
    confidence: Optional[float] = Body(default=None),
    source: str = Body(default="signal"),
    user=Depends(get_current_user),
):
    uid = str(user.get("_id", ""))
    result = open_position(uid, asset, action, entry_price, confidence, source)
    return result


@router.post("/trading/close")
def close_trade(
    position_id: str = Body(..., alias="positionId"),
    user=Depends(get_current_user),
):
    uid = str(user.get("_id", ""))
    return close_position(uid, position_id)


@router.get("/trading/positions")
def get_user_positions(
    status: str = "OPEN",
    user=Depends(get_current_user),
):
    uid = str(user.get("_id", ""))
    positions = get_positions(uid, status)
    return {"ok": True, "positions": positions}


@router.get("/trading/portfolio")
def get_portfolio(user=Depends(get_current_user)):
    uid = str(user.get("_id", ""))
    return {"ok": True, **get_portfolio_summary(uid)}
