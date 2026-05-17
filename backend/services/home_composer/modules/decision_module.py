"""`decision` + `actionPlan` slots — MetaBrain enrichment heavy.

Replicates the EXACT bookkeeping of server.py, including:
  * confidence_01 default from sig, overridden by MetaBrain 30D + chart
  * expected move pct from MetaBrain 30D expectedReturn
  * range30d {min, max} from MetaBrain target + confidence band
  * SPA-safe stubs if MetaBrain unavailable
  * entryZone / invalidation parsing (dict|list|str|None)
  * strength enum from alignedCount
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from ..contracts import HomeContext


def _strength_label(aligned_cnt: int) -> str:
    if aligned_cnt >= 4:
        return "HIGH"
    if aligned_cnt >= 2:
        return "MEDIUM"
    return "LOW"


def _parse_entry_zone(raw_ez) -> Optional[str]:
    if isinstance(raw_ez, dict):
        mn = raw_ez.get("min") or raw_ez.get("low") or raw_ez.get("lower")
        mx = raw_ez.get("max") or raw_ez.get("high") or raw_ez.get("upper")
        if mn and mx:
            return f"${int(mn):,}\u2013${int(mx):,}"
        return raw_ez.get("label") or None
    if isinstance(raw_ez, (list, tuple)) and len(raw_ez) >= 2:
        if raw_ez[0] and raw_ez[1]:
            return f"${int(raw_ez[0] or 0):,}\u2013${int(raw_ez[1] or 0):,}"
        return None
    if isinstance(raw_ez, str):
        return raw_ez
    return None


def _parse_invalidation(raw_sl) -> Optional[str]:
    if isinstance(raw_sl, dict):
        return raw_sl.get("label") or (
            f"${int(raw_sl.get('price', 0)):,}" if raw_sl.get("price") else None
        )
    if isinstance(raw_sl, (int, float)) and raw_sl:
        return f"${int(raw_sl):,}"
    if isinstance(raw_sl, str):
        return raw_sl
    return None


def compute_metabrain_enrichment(ctx: HomeContext, cur_price: float) -> Dict[str, Any]:
    """Pure computation over pre-fetched metabrain + prediction payloads.

    Returns a dict with: confidence_01, exp_move_pct, range_min, range_max,
    meta_state, meta_state_text, meta_action_verb, meta_action_hint,
    meta_bias, meta_conviction, next_move_above, next_move_below.

    Mirrors server.py logic exactly.
    """
    sig = ctx.sig or {}
    confidence_01 = float(sig.get("confidence", 0) or 0)
    exp_move_pct = 0.0
    range_min = 0
    range_max = 0
    meta_state = None
    meta_state_text = None
    meta_action_verb = None
    meta_action_hint = None
    meta_bias = None
    meta_conviction = 0
    next_move_above = None
    next_move_below = None

    mb = ctx.metabrain or {}
    mb_h = (mb.get("horizons") or {}).get("30D") or {}
    if mb_h:
        confidence_01 = float(mb_h.get("confidence", confidence_01) or confidence_01)
        er = float(mb_h.get("expectedReturn", 0) or 0)
        exp_move_pct = round(er * 100, 1)
        target = float(mb_h.get("targetPrice", 0) or 0)
        if target <= 0 and cur_price > 0:
            target = cur_price * (1 + er)
        band = 0.06 + 0.10 * (1.0 - confidence_01)
        if target > 0:
            range_min = int(target * (1 - band))
            range_max = int(target * (1 + band))
        elif cur_price > 0:
            range_min = int(cur_price * (1 - band))
            range_max = int(cur_price * (1 + band))
        meta_state = mb_h.get("marketState")
        meta_conviction = round(float(mb_h.get("conviction", 0) or 0) * 100)
        _dir = (mb_h.get("direction", "NEUTRAL") or "NEUTRAL").upper()
        meta_bias = "Bullish" if _dir in ("UP", "BULLISH") else "Bearish" if _dir in ("DOWN", "BEARISH") else "Neutral"

    pp = ctx.prediction or {}
    ps = pp.get("summary") or {}
    if ps:
        meta_state = ps.get("marketState") or meta_state
        meta_state_text = ps.get("marketStateText")
        meta_action_verb = ps.get("actionVerb")
        meta_action_hint = ps.get("actionHint")
        if ps.get("confidence") is not None:
            confidence_01 = float(ps.get("confidence", 0)) / 100.0
        meta_conviction = ps.get("conviction", meta_conviction)
        meta_bias = ps.get("bias", meta_bias)
        nm = pp.get("nextMoveLevels") or {}
        next_move_above = nm.get("breakAbove")
        next_move_below = nm.get("breakBelow")

    # SPA-safe range stubs
    if range_min <= 0 or range_max <= 0:
        if cur_price > 0:
            range_min = int(cur_price * 0.92)
            range_max = int(cur_price * 1.08)
        else:
            range_min = 0
            range_max = 0

    return {
        "confidence_01": confidence_01,
        "exp_move_pct": exp_move_pct,
        "range_min": range_min,
        "range_max": range_max,
        "meta_state": meta_state,
        "meta_state_text": meta_state_text,
        "meta_action_verb": meta_action_verb,
        "meta_action_hint": meta_action_hint,
        "meta_bias": meta_bias,
        "meta_conviction": meta_conviction,
        "next_move_above": next_move_above,
        "next_move_below": next_move_below,
    }


def assemble_decision(ctx: HomeContext, enrichment: Dict[str, Any]) -> Dict[str, Any]:
    sig = ctx.sig or {}
    df = sig.get("decisionFramework", {}) or {}
    aligned_cnt = df.get("alignedCount", 0) or 0
    raw_conf = float(sig.get("confidence", 0) or 0)
    risk_level = "LOW" if raw_conf > 0.6 else "MEDIUM" if raw_conf > 0.3 else "HIGH"

    return {
        "action": sig.get("action", "WAIT"),
        "mode": df.get("stage", "EARLY"),
        "strength": _strength_label(aligned_cnt),
        "strengthCount": aligned_cnt,
        "riskLevel": risk_level,
        "confidence": enrichment["confidence_01"],
        "expectedMovePct": enrichment["exp_move_pct"],
        "range30d": {"min": enrichment["range_min"], "max": enrichment["range_max"]},
    }


def assemble_action_plan(ctx: HomeContext) -> Dict[str, Any]:
    sig = ctx.sig or {}
    ew = sig.get("entryWindow", {}) or {}
    return {
        "summary": sig.get("summary", "Scanning for alignment"),
        "entryZone": _parse_entry_zone(sig.get("entryZone")),
        "invalidation": _parse_invalidation(sig.get("stopLoss")),
        "nextTrigger": ew.get("label", "Monitoring"),
    }
