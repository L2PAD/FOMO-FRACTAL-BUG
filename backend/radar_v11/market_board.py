"""
P2 — Market V2: Trade Bias Board
=================================
Execution Intelligence Board built on top of Radar output.
No new computations — just smart filtering and categorization.

Blocks:
  1. Market Pulse (aggregated context)
  2. Action Now (execution-ready)
  3. Early Build (pre-breakout)
  4. Structural Shift (regime changes)
  5. Risk Events (avoid)
"""

from typing import List, Dict, Any
import time
from collections import Counter

from .types import SpotRadarRow, Verdict, RiskLevel


# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

MAX_ACTION_NOW = 15
MAX_EARLY_BUILD = 25
MAX_STRUCT_SHIFT = 15
MAX_RISK_EVENTS = 15

FRESH_SEC = 600
ACTION_SETUP_MIN = 0.55
ACTION_CONV_MIN = 70
EARLY_SETUP_MIN = 0.40
EARLY_CONV_MIN = 55
EARLY_CONV_MAX = 69
DIV_MIN = 0.25
DIV_EXTREME = 0.85


# ═══════════════════════════════════════════════════════════════
# ROW SERIALIZATION
# ═══════════════════════════════════════════════════════════════

def _row_to_dict(row: SpotRadarRow) -> Dict[str, Any]:
    """Convert SpotRadarRow to dict for JSON response."""
    return row.model_dump(mode="json")


# ═══════════════════════════════════════════════════════════════
# MARKET PULSE
# ═══════════════════════════════════════════════════════════════

def build_market_pulse(rows: List[SpotRadarRow]) -> Dict[str, Any]:
    """Aggregate market context from radar rows."""
    ok_rows = [r for r in rows if r.integrity and r.integrity.status == "ok"]

    if not ok_rows:
        return {
            "bias": "NO_DATA",
            "counts": {"total": len(rows), "ok": 0, "buy": 0, "sell": 0, "watch": 0, "neutral": 0},
            "avg": {"conv": 0, "setup": 0, "div": 0, "risk": 0},
            "dominantHorizon": "auto",
        }

    buy = sum(1 for r in ok_rows if r.verdict == Verdict.BUY)
    sell = sum(1 for r in ok_rows if r.verdict == Verdict.SELL)
    watch = sum(1 for r in ok_rows if r.verdict == Verdict.WATCH)
    neutral = sum(1 for r in ok_rows if r.verdict == Verdict.NEUTRAL)

    avg_conv = sum(r.conviction for r in ok_rows) / len(ok_rows)
    avg_setup = sum((r.integrity.setupScore if r.integrity else 0) for r in ok_rows) / len(ok_rows)
    avg_div = sum(r.divergenceScore for r in ok_rows) / len(ok_rows)
    avg_risk = sum(r.features.risk for r in ok_rows) / len(ok_rows)

    # Dominant horizon
    horizons = Counter()
    for r in ok_rows:
        if r.horizons and r.horizons.primary:
            horizons[r.horizons.primary] += 1
    dominant = horizons.most_common(1)[0][0] if horizons else "auto"

    # Bias
    if buy > sell * 1.2 and buy >= 3:
        bias = "BULLISH"
    elif sell > buy * 1.2 and sell >= 3:
        bias = "BEARISH"
    elif buy + sell < 3:
        bias = "QUIET"
    else:
        bias = "MIXED"

    return {
        "bias": bias,
        "counts": {
            "total": len(rows), "ok": len(ok_rows),
            "buy": buy, "sell": sell, "watch": watch, "neutral": neutral,
        },
        "avg": {
            "conv": round(avg_conv, 1),
            "setup": round(avg_setup, 3),
            "div": round(avg_div, 3),
            "risk": round(avg_risk, 3),
        },
        "dominantHorizon": dominant,
    }


# ═══════════════════════════════════════════════════════════════
# BOARD BUILDER
# ═══════════════════════════════════════════════════════════════

def build_market_board(rows: List[SpotRadarRow]) -> Dict[str, Any]:
    """
    Categorize radar rows into 4 actionable blocks.
    Each row appears in at most ONE block (priority: risk > action > early > shift).
    """
    action_now = []
    early_build = []
    structural_shift = []
    risk_events = []

    used = set()

    # Pass 1: Risk Events (highest priority — remove from pool)
    for r in rows:
        if r.verdict == Verdict.DATA_GAP:
            continue

        is_risk = False

        # Integrity problems
        if r.integrity and r.integrity.status != "ok":
            is_risk = True

        # High risk
        if r.risk == RiskLevel.HIGH:
            is_risk = True

        # Extreme divergence
        if r.divergenceScore > DIV_EXTREME:
            is_risk = True

        # Stale data
        if r.integrity and r.integrity.dataFreshnessSec and r.integrity.dataFreshnessSec > FRESH_SEC:
            is_risk = True

        if is_risk:
            risk_events.append(r)
            used.add(r.symbol)

    # Pass 2: Action Now
    for r in rows:
        if r.symbol in used or r.verdict == Verdict.DATA_GAP:
            continue

        integrity_ok = r.integrity and r.integrity.status == "ok"
        setup = r.integrity.setupScore if r.integrity else 0
        fresh = r.integrity.dataFreshnessSec if r.integrity and r.integrity.dataFreshnessSec else 0

        if (integrity_ok
                and setup >= ACTION_SETUP_MIN
                and r.conviction >= ACTION_CONV_MIN
                and r.risk != RiskLevel.HIGH
                and fresh <= FRESH_SEC
                and r.verdict in (Verdict.BUY, Verdict.SELL, Verdict.WATCH)):
            action_now.append(r)
            used.add(r.symbol)

    # Pass 3: Structural Shift (divergence-driven or regime indicators)
    for r in rows:
        if r.symbol in used or r.verdict == Verdict.DATA_GAP:
            continue

        # Strong divergence signals structural change
        if r.divergenceScore >= 0.4 and r.conviction >= 45:
            structural_shift.append(r)
            used.add(r.symbol)
            continue

        # High compression + rising participation = structural setup
        if (r.features.compression > 0.6
                and r.features.volumeBuild > 0.5
                and r.conviction >= 50):
            structural_shift.append(r)
            used.add(r.symbol)

    # Pass 4: Early Build
    for r in rows:
        if r.symbol in used or r.verdict == Verdict.DATA_GAP:
            continue

        integrity_not_invalid = not r.integrity or r.integrity.status != "invalid"
        setup = r.integrity.setupScore if r.integrity else 0

        # Compression build-up
        if (integrity_not_invalid
                and setup >= EARLY_SETUP_MIN
                and EARLY_CONV_MIN <= r.conviction <= EARLY_CONV_MAX
                and r.features.compression > 0.35):
            early_build.append(r)
            used.add(r.symbol)
            continue

        # Divergence-based early signal
        if (r.divergenceScore >= DIV_MIN
                and r.horizons
                and r.horizons.short.conviction >= 55):
            early_build.append(r)
            used.add(r.symbol)

    # Sort each block
    action_now.sort(key=lambda r: (r.conviction, r.integrity.setupScore if r.integrity else 0), reverse=True)
    early_build.sort(key=lambda r: (r.horizons.short.conviction if r.horizons else r.conviction, r.conviction), reverse=True)
    structural_shift.sort(key=lambda r: (r.divergenceScore, r.conviction), reverse=True)
    risk_events.sort(key=lambda r: (r.features.risk, -(r.conviction)), reverse=True)

    # Trim
    action_now = action_now[:MAX_ACTION_NOW]
    early_build = early_build[:MAX_EARLY_BUILD]
    structural_shift = structural_shift[:MAX_STRUCT_SHIFT]
    risk_events = risk_events[:MAX_RISK_EVENTS]

    return {
        "ts": int(time.time()),
        "pulse": build_market_pulse(rows),
        "summary": {
            "totalScanned": len(rows),
            "actionCount": len(action_now),
            "earlyCount": len(early_build),
            "shiftCount": len(structural_shift),
            "riskCount": len(risk_events),
        },
        "actionNow": [_row_to_dict(r) for r in action_now],
        "earlyBuild": [_row_to_dict(r) for r in early_build],
        "structuralShift": [_row_to_dict(r) for r in structural_shift],
        "riskEvents": [_row_to_dict(r) for r in risk_events],
    }
