"""
mbrain_verdicts — observability proxy for the Expo Trading Runtime UI.

Read-only HTTP-only adapter. Routes:

  GET /api/mbrain/verdicts/list   — list open verdicts (signal feed)
  GET /api/mbrain/verdicts/{id}   — verdict inspector (full pipeline)
  GET /api/mbrain/verdicts/sweep  — refresh on demand: sweep popular
                                    (asset × horizon) pairs through the
                                    side-car heavy-compute, normalize,
                                    return inspector-ready cards.
                                    No commit. No persistence in side-car.

Constraints (preserved from M1/M2/M3):
  • read-only against trading_os
  • HTTP-only via side-car
  • no synthetic data
  • no production fusion influence
  • no /api/verdict/commit
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Query, HTTPException

from modules.mbrain_integrity.normalize import (
    normalize_verdict_to_decision, reconstruct_survival,
)
from modules.mbrain_integrity.replay import fetch_verdict_via_chart

UPSTREAM = os.environ.get(
    "TRADING_TERMINAL_UPSTREAM", "http://localhost:8002",
).rstrip("/")

router = APIRouter(prefix="/api/mbrain/verdicts", tags=["mbrain-verdicts"])


# ─────────────────────────────────────────────────────────────────────
# Inspector card shape (additive — does not touch existing endpoints)
# ─────────────────────────────────────────────────────────────────────

def _build_inspector_card(verdict: Dict[str, Any]) -> Dict[str, Any]:
    """Decorate the v1 normalized decision with UI-friendly fields:
    transparency badges, suppression reasons, stage progression labels."""
    d = normalize_verdict_to_decision(verdict)
    stages = d.get("stages") or {}

    # UI badges — what made this verdict end up where it is
    badges: List[Dict[str, str]] = []
    final_dir = d.get("final_action") or "HOLD"
    after_meta = (stages.get("after_meta_brain") or {}).get("direction") or "HOLD"
    raw = (stages.get("raw") or {}).get("direction") or "HOLD"

    if final_dir == "HOLD" and raw != "HOLD":
        # signal was suppressed
        badges.append({
            "type": "SUPPRESSED",
            "label": "Signal suppressed",
            "tone": "warn",
        })
        if after_meta == "HOLD" and raw != "HOLD":
            badges.append({
                "type": "META_DOWNGRADE",
                "label": "Downgraded by Meta-Brain",
                "tone": "warn",
            })
    if d.get("blocked"):
        badges.append({
            "type": "BLOCKED",
            "label": "Blocked by rules",
            "tone": "block",
        })
    if final_dir != "HOLD" and final_dir != raw:
        badges.append({
            "type": "DIRECTION_FLIP",
            "label": f"Direction flipped {raw}→{final_dir}",
            "tone": "alert",
        })

    return {
        "verdictId": d.get("_verdictId"),
        "symbol": d.get("symbol"),
        "horizon": d.get("timeframe"),
        "ts": d.get("ts"),
        "regime": d.get("regime"),
        "modelId": d.get("modelId"),
        "final_action": final_dir,
        "blocked": d.get("blocked"),
        "block_reason": d.get("block_reason") or [],
        "confidence_final": d.get("confidence_final"),
        "risk": d.get("risk"),
        "stages": {
            stage: {
                "direction": (info or {}).get("direction"),
                "confidence": (info or {}).get("confidence"),
                "expectedReturn": (info or {}).get("expectedReturn"),
                "collapsed_to_hold": (info or {}).get("collapsed_to_hold", False),
            }
            for stage, info in stages.items()
        },
        "reason_chain": d.get("reason_chain") or [],
        "badges": badges,
        "raw_appliedRules": verdict.get("appliedRules") or [],
        "raw_adjustments": verdict.get("adjustments") or [],
        "_source": "verdict_v2",
    }


# ─────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────

@router.get("/list")
async def list_verdicts(
    limit: int = Query(50, ge=1, le=200),
    status: str = Query("OPEN", pattern="^(OPEN|CLOSED|ALL)$"),
):
    """Pulls open verdicts from the side-car and returns them as
    inspector-ready cards. Currently the side-car only persists OPEN
    rows when /api/verdict/commit is called — in the audit-only mode
    we run we have an empty list. The /sweep endpoint generates fresh
    cards on demand."""
    url = f"{UPSTREAM}/api/verdict/open"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return {"ok": True, "n": 0, "cards": [],
                        "note": f"upstream returned {r.status_code}"}
            body = r.json()
            verdicts = body.get("verdicts") or []
            cards = [_build_inspector_card(v) for v in verdicts[:limit]]
            return {"ok": True, "n": len(cards), "cards": cards}
    except Exception as e:
        return {"ok": False, "n": 0, "cards": [], "error": str(e)}


@router.get("/sweep")
async def sweep_now(
    assets: str = Query("BTC,ETH,SOL,BNB,XRP,DOGE",
                        description="comma-separated asset list"),
    horizons: str = Query("1D,7D,30D"),
    range_: str = Query("7d", alias="range"),
    timeout_seconds: float = Query(120.0, ge=10.0, le=300.0),
):
    """On-demand fresh evaluation. Triggers the side-car heavy-compute
    pipeline for each (asset, horizon) and returns inspector cards.
    Slow first call (~18s per asset+horizon, then cached).
    No persistence in side-car. Read-only."""
    a_list = [x.strip() for x in assets.split(",") if x.strip()]
    h_list = [x.strip() for x in horizons.split(",") if x.strip()]
    if not a_list or not h_list:
        raise HTTPException(400, "assets and horizons required")

    cards: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []
    started = time.time()

    with httpx.Client() as client:
        for asset in a_list:
            for hz in h_list:
                v = fetch_verdict_via_chart(asset, range_, hz, client,
                                            timeout=timeout_seconds)
                if v is None:
                    failures.append({"asset": asset, "horizon": hz,
                                     "reason": "fetch_failed"})
                    continue
                cards.append(_build_inspector_card(v))

    return {
        "ok": True,
        "n": len(cards),
        "elapsed_ms": int((time.time() - started) * 1000),
        "cards": cards,
        "failures": failures,
        "_constraints": [
            "http_only", "read_only",
            "no_commit", "no_persistence_in_side_car",
            "no_synthetic_outputs", "no_production_fusion_influence",
        ],
    }


@router.get("/{verdict_id}")
async def get_verdict_by_id(verdict_id: str):
    """Fetch one verdict by id (only works after /api/verdict/commit
    has populated the side-car store — in audit mode use /sweep instead)."""
    url = f"{UPSTREAM}/api/verdict/{verdict_id}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url)
            if r.status_code == 404:
                raise HTTPException(404, "verdict_not_found")
            if r.status_code != 200:
                raise HTTPException(r.status_code, "upstream_error")
            body = r.json()
            v = body.get("verdict")
            if not isinstance(v, dict):
                raise HTTPException(502, "upstream_malformed_payload")
            return {"ok": True, "card": _build_inspector_card(v)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"upstream_error: {e}")
