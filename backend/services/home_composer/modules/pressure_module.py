"""`pressure` slot — SPA-shape pressure object derived from sig.drivers.

Pure assembly: maps drivers list to {net, exchange, onchain, sentiment,
twitter, mlRisk, direction, summary} as the SPA expects.
"""
from __future__ import annotations

from typing import Any, Dict

from ..contracts import HomeContext


def _map_dir(raw):
    r = (raw or "Neutral").upper()
    if r in ("UP", "BULLISH", "BUY"): return "BULLISH"
    if r in ("DOWN", "BEARISH", "SELL"): return "BEARISH"
    if r in ("MIXED", "CONFLICT"): return "MIXED"
    return "NEUTRAL"


def _pick(drivers_list, name_keywords):
    for d in drivers_list:
        nm = (d.get("name", "") or d.get("module", "") or "").lower()
        if any(kw in nm for kw in name_keywords):
            return d
    return {}


def assemble(ctx: HomeContext) -> Dict[str, Any]:
    sig = ctx.sig or {}
    drivers_list = sig.get("drivers", []) or []

    ex = _pick(drivers_list, ["exchange", "price", "market"])
    on = _pick(drivers_list, ["on-chain", "onchain", "chain"])
    sent = _pick(drivers_list, ["sentiment"])
    twt = _pick(drivers_list, ["twitter", "social"])

    net_dir = _map_dir(sig.get("direction"))
    conf = float(sig.get("confidence", 0) or 0)
    risk_level = "LOW" if conf > 0.6 else "MEDIUM" if conf > 0.3 else "HIGH"

    return {
        "net": {
            "direction": net_dir,
            "summary": sig.get("summary", ""),
        },
        "exchange": {
            "direction": _map_dir(ex.get("direction")),
            "score": round(float(ex.get("confidence", 0) or 0) * 100),
        },
        "onchain": {
            "direction": _map_dir(on.get("direction")),
            "score": round(float(on.get("confidence", 0) or 0) * 100),
        },
        "sentiment": {
            "direction": _map_dir(sent.get("direction")),
            "score": round(float(sent.get("confidence", 0) or 0) * 100),
        },
        "twitter": {
            "label": (twt.get("insight") or twt.get("reason") or "Tracking social chatter"),
        },
        "mlRisk": {"level": risk_level},
        # Legacy flat fields (kept for older consumers / inject-scripts).
        "direction": net_dir.title(),
        "summary": sig.get("summary", ""),
    }
