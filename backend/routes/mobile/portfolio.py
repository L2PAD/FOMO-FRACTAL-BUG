"""Analytical Portfolio API routes (NOT trade terminal)."""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional
from services.portfolio_service import (
    get_portfolio_strategy,
    open_portfolio,
    open_single_position,
    close_position,
    get_positions,
    get_performance,
)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/strategy")
async def portfolio_strategy(userId: str = Query("dev_user")):
    return get_portfolio_strategy(userId)


@router.post("/open")
async def portfolio_open(userId: str = Query("dev_user")):
    return open_portfolio(userId)


class OpenPositionBody(BaseModel):
    symbol: str

@router.post("/open-position")
async def portfolio_open_position(body: OpenPositionBody, userId: str = Query("dev_user")):
    return open_single_position(userId, body.symbol)


class ClosePositionBody(BaseModel):
    positionId: str

@router.post("/close-position")
async def portfolio_close_position(body: ClosePositionBody, userId: str = Query("dev_user")):
    return close_position(userId, body.positionId)


@router.get("/positions")
async def portfolio_positions(status: str = Query("OPEN"), userId: str = Query("dev_user")):
    return {"ok": True, "positions": get_positions(userId, status)}


@router.get("/performance")
async def portfolio_performance(userId: str = Query("dev_user")):
    return get_performance(userId)
