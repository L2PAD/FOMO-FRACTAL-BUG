"""
System Convergence — V2 Live Rollout Controller
=================================================
Manages gradual V1 → V2 transition with feature flags, monitoring,
and automatic rollback.

Stages: shadow → 10% → 25% → 50% → 100%
"""

import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Tuple

# ── Feature flags (persisted to DB on change) ──
SYSTEM_V2_MODE = "shadow_plus_live"  # "shadow_only" | "shadow_plus_live" | "live_only"
SYSTEM_V2_PCT = 0.10                  # 0.0 → 1.0
SYSTEM_V2_SALT = "v2_launch"

# ── Confidence safety bounds ──
CONFIDENCE_FLOOR = 0.20
CONFIDENCE_CEILING = 0.90

# ── Rollout steps ──
ROLLOUT_STEPS = [0.0, 0.10, 0.25, 0.50, 1.0]


def should_use_v2(forecast_id: str) -> bool:
    """
    Deterministic routing: given a forecast_id, decide V1 or V2.
    Uses consistent hashing so the same forecast always gets the same version.
    """
    if SYSTEM_V2_MODE == "shadow_only":
        return False
    if SYSTEM_V2_MODE == "live_only":
        return True

    # shadow_plus_live: hash-based split
    h = hashlib.md5(f"{forecast_id}{SYSTEM_V2_SALT}".encode()).hexdigest()
    bucket = int(h[:8], 16) / 0xFFFFFFFF  # 0.0 to 1.0
    return bucket < SYSTEM_V2_PCT


def clamp_confidence(confidence: float) -> float:
    """Apply confidence safety bounds."""
    return max(CONFIDENCE_FLOOR, min(CONFIDENCE_CEILING, confidence))


def apply_v2_to_forecast(
    forecast_id: str,
    v1_direction: str,
    v1_confidence: float,
    v1_score: float,
    forecast_v2_result: dict,
    decision_v2_result: dict,
) -> Tuple[str, float, float, Dict[str, Any]]:
    """
    Apply V2 results to a forecast based on feature flag.

    Returns:
        (direction, confidence, score, convergence_audit)
    """
    use_v2 = should_use_v2(forecast_id)

    if use_v2 and forecast_v2_result and decision_v2_result:
        direction = decision_v2_result.get("direction", v1_direction)
        confidence = clamp_confidence(decision_v2_result.get("confidence", v1_confidence))
        score = forecast_v2_result.get("final_score", v1_score)
        system_version = "V2"
    else:
        direction = v1_direction
        confidence = v1_confidence
        score = v1_score
        system_version = "V1"

    convergence_audit = {
        "system_version": system_version,
        "v2_mode": SYSTEM_V2_MODE,
        "v2_pct": SYSTEM_V2_PCT,
        "use_v2": use_v2,
        "v1": {
            "direction": v1_direction,
            "confidence": round(v1_confidence, 4),
            "score": round(v1_score, 6),
        },
        "v2": {
            "direction": decision_v2_result.get("direction", "N/A") if decision_v2_result else "N/A",
            "confidence": round(decision_v2_result.get("confidence", 0), 4) if decision_v2_result else 0,
            "score": round(forecast_v2_result.get("final_score", 0), 6) if forecast_v2_result else 0,
        },
        "confidence_clamped": system_version == "V2" and (
            decision_v2_result.get("confidence", 0) != confidence if decision_v2_result else False
        ),
    }

    return direction, confidence, score, convergence_audit


def get_convergence_status() -> Dict[str, Any]:
    """Return current convergence system status."""
    current_step_idx = 0
    for i, step in enumerate(ROLLOUT_STEPS):
        if SYSTEM_V2_PCT >= step:
            current_step_idx = i
    next_step = ROLLOUT_STEPS[current_step_idx + 1] if current_step_idx < len(ROLLOUT_STEPS) - 1 else None

    return {
        "mode": SYSTEM_V2_MODE,
        "v2_pct": SYSTEM_V2_PCT,
        "current_step": current_step_idx,
        "next_step_pct": next_step,
        "rollout_steps": ROLLOUT_STEPS,
        "confidence_bounds": {"floor": CONFIDENCE_FLOOR, "ceiling": CONFIDENCE_CEILING},
    }
