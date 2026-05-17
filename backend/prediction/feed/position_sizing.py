"""
Position Sizing Engine — computes how much to bet, not just what to bet on.

Pipeline:
  1. Compute edge quality (edge * confidence * liquidity * execution)
  2. Compute raw sizing score (edge + confidence + execution + structure + project)
  3. Map to size band (TINY/SMALL/MEDIUM/LARGE/MAX)
  4. Apply caps (liquidity, volatility, event risk, expiry, slippage, correlation)
  5. Apply hard blockers (zero-size on dangerous signals)
  6. Apply confidence gate on size
  7. Normalize to final band + reasons
"""
import math
import logging
from datetime import datetime, timezone

logger = logging.getLogger("feed.position_sizing")

# ── Size bands ──
SIZE_BANDS = {
    "TINY":   0.0025,
    "SMALL":  0.0075,
    "MEDIUM": 0.015,
    "LARGE":  0.025,
    "MAX":    0.04,
}

# ── Confidence numeric mapping ──
CONF_NUM = {"high": 0.8, "medium": 0.55, "low": 0.3}

# ── Hard blocker thresholds ──
MIN_LIQUIDITY = 500
MAX_SLIPPAGE_RISK = 0.85
MIN_CONFIDENCE_FOR_ENTRY = 0.4


def compute_position_sizing(event: dict, overlay: dict,
                            structure_analysis: dict | None = None) -> dict:
    """Compute position sizing for an event's best pick.

    Returns sizing dict with sizeLabel, sizeFraction, edgeQuality,
    caps breakdown, and human-readable reasons.
    """
    bp = overlay.get("best_pick")
    if not bp:
        return _no_position("No best pick")

    action = overlay.get("action", "WATCH")
    if action in ("WATCH", "AVOID"):
        return _no_position("Action is WATCH/AVOID")

    # Extract inputs
    edge = abs(bp.get("edge", 0))
    confidence_str = overlay.get("confidence", "low")
    confidence = CONF_NUM.get(confidence_str, 0.3)
    exec_info = bp.get("execution", {}) or {}
    slippage_risk = _slippage_score(exec_info)
    exec_quality = _execution_quality(exec_info)
    struct_quality = _structure_quality(structure_analysis)
    liquidity = _event_liquidity(event)
    hours_left = _hours_to_expiry(event.get("end_date"))
    event_type = event.get("event_type", "other")

    reasons = []

    # ── 1. Edge Quality ──
    eq = compute_edge_quality(edge, confidence, liquidity, exec_quality)

    # ── 2. Hard Blockers ──
    if confidence < MIN_CONFIDENCE_FOR_ENTRY:
        return _no_position("Confidence too low for entry", eq)

    if liquidity < MIN_LIQUIDITY:
        return _no_position("Liquidity too low for entry", eq)

    if slippage_risk > MAX_SLIPPAGE_RISK:
        return _no_position("Slippage risk too high", eq)

    # ── 3. Raw sizing score ──
    raw_score = _clamp(
        edge * 0.35
        + confidence * 0.25
        + exec_quality * 0.20
        + struct_quality * 0.10
        + 0.6 * 0.10  # project quality placeholder
    )

    raw_label, raw_fraction = _score_to_band(raw_score)

    # ── 4. Caps ──
    liq_cap, liq_reason = _liquidity_cap(liquidity)
    vol_cap, vol_reason = _volatility_cap(exec_info.get("spread_pct", 0))
    event_cap, event_reason = _event_risk_cap(event_type)
    expiry_cap, expiry_reason = _expiry_cap(hours_left)
    slip_cap, slip_reason = _slippage_cap(slippage_risk)

    total_cap = liq_cap * vol_cap * event_cap * expiry_cap * slip_cap

    # ── 5. Apply caps to fraction ──
    final_fraction = raw_fraction * total_cap

    # ── 6. Confidence gate on size ──
    if confidence < 0.5:
        final_fraction = min(final_fraction, SIZE_BANDS["TINY"])
        reasons.append("Low confidence limits size to TINY")

    # ── 7. Normalize to band ──
    final_label = _fraction_to_label(final_fraction)

    # ── Build reasons ──
    if edge > 0.08:
        reasons.append("Strong edge supports size")
    elif edge > 0.04:
        reasons.append("Moderate edge")

    if confidence >= 0.6:
        reasons.append("Model confidence sufficient")
    elif confidence >= 0.5:
        reasons.append("Moderate confidence")

    if exec_quality > 0.65:
        reasons.append("Good execution quality")

    for cap_val, cap_reason in [(liq_cap, liq_reason), (vol_cap, vol_reason),
                                 (event_cap, event_reason), (expiry_cap, expiry_reason),
                                 (slip_cap, slip_reason)]:
        if cap_val < 1.0:
            reasons.append(cap_reason)

    return {
        "size_label": final_label,
        "size_fraction": round(final_fraction, 4),
        "size_pct": round(final_fraction * 100, 2),
        "edge_quality": eq["label"],
        "edge_quality_score": eq["score"],
        "conviction": _conviction_label(raw_score),
        "raw_score": round(raw_score, 4),
        "caps": {
            "liquidity": liq_cap,
            "volatility": vol_cap,
            "event_risk": event_cap,
            "expiry": expiry_cap,
            "slippage": slip_cap,
        },
        "reasons": reasons[:5],
    }


def compute_edge_quality(edge: float, confidence: float,
                         liquidity: float, exec_quality: float) -> dict:
    """Compute edge quality score — how trustworthy is the edge."""
    liq_score = _clamp(math.log10(max(liquidity, 1) + 1) / 6)

    score = _clamp(
        edge * 0.4
        + confidence * 0.25
        + liq_score * 0.15
        + exec_quality * 0.20
    )

    if score >= 0.55:
        label = "high"
    elif score >= 0.35:
        label = "medium"
    else:
        label = "low"

    return {"score": round(score, 4), "label": label}


# ── Cap functions ──

def _liquidity_cap(liquidity: float) -> tuple[float, str]:
    if liquidity < 5000:
        return 0.4, "Low liquidity limits size"
    if liquidity < 50000:
        return 0.7, "Moderate liquidity caps size"
    return 1.0, ""


def _volatility_cap(spread_pct: float) -> tuple[float, str]:
    if spread_pct > 10:
        return 0.6, "Wide spread indicates high volatility"
    if spread_pct > 5:
        return 0.8, "Elevated spread caps size"
    return 1.0, ""


def _event_risk_cap(event_type: str) -> tuple[float, str]:
    caps = {
        "etf": (1.0, ""),
        "price": (0.9, ""),
        "direction": (0.9, ""),
        "fdv": (0.6, "FDV markets are higher risk"),
        "launch": (0.6, "Launch markets are higher risk"),
        "macro": (0.75, "Macro events have wider uncertainty"),
    }
    return caps.get(event_type, (0.75, "Unknown market type limits size"))


def _expiry_cap(hours_left: float | None) -> tuple[float, str]:
    if hours_left is None:
        return 0.9, "Unknown expiry adds slight caution"
    if hours_left < 6:
        return 0.5, "Very near expiry limits size"
    if hours_left < 24:
        return 0.75, "Near expiry moderately limits size"
    return 1.0, ""


def _slippage_cap(slippage_risk: float) -> tuple[float, str]:
    if slippage_risk > 0.75:
        return 0.5, "High slippage risk limits size"
    if slippage_risk > 0.45:
        return 0.8, "Moderate slippage risk"
    return 1.0, ""


# ── Helpers ──

def _score_to_band(score: float) -> tuple[str, float]:
    if score < 0.35:
        return "TINY", SIZE_BANDS["TINY"]
    if score < 0.50:
        return "SMALL", SIZE_BANDS["SMALL"]
    if score < 0.65:
        return "MEDIUM", SIZE_BANDS["MEDIUM"]
    if score < 0.80:
        return "LARGE", SIZE_BANDS["LARGE"]
    return "MAX", SIZE_BANDS["MAX"]


def _fraction_to_label(fraction: float) -> str:
    if fraction < 0.004:
        return "TINY"
    if fraction < 0.011:
        return "SMALL"
    if fraction < 0.02:
        return "MEDIUM"
    if fraction < 0.032:
        return "LARGE"
    return "MAX"


def _conviction_label(score: float) -> str:
    if score >= 0.65:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def _execution_quality(exec_info: dict) -> float:
    style = exec_info.get("style", "")
    if style == "MARKET_OK":
        return 0.9
    if style == "LIMIT_PREFERRED":
        return 0.7
    if style == "LIMIT_ONLY":
        return 0.4
    return 0.5


def _slippage_score(exec_info: dict) -> float:
    risk = exec_info.get("slippage_risk", "medium")
    return {"low": 0.2, "medium": 0.5, "high": 0.8}.get(risk, 0.5)


def _structure_quality(analysis: dict | None) -> float:
    if not analysis:
        return 0.5
    return _clamp(analysis.get("ladder_quality", 0.5))


def _event_liquidity(event: dict) -> float:
    liq = event.get("liquidity", 0)
    if liq > 0:
        return liq
    markets = event.get("markets", [])
    return sum(m.get("liquidity", 0) for m in markets)


def _hours_to_expiry(end_date: str | None) -> float | None:
    if not end_date:
        return None
    try:
        end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        return max(0, (end - datetime.now(timezone.utc)).total_seconds() / 3600)
    except Exception:
        return None


def _clamp(v: float, lo: float = 0, hi: float = 1) -> float:
    return max(lo, min(hi, v))


def _no_position(reason: str, eq: dict | None = None) -> dict:
    return {
        "size_label": "NONE",
        "size_fraction": 0,
        "size_pct": 0,
        "edge_quality": eq["label"] if eq else "low",
        "edge_quality_score": eq["score"] if eq else 0,
        "conviction": "low",
        "raw_score": 0,
        "caps": {},
        "reasons": [reason],
    }
