"""
ML Overlay — Gate Functions

Gate pipeline:
  r_ml_cap    = cap(r_ml_raw)
  r_ml_dir    = direction_lock(r_rule, r_ml_cap, conf_rule)
  r_ml_smooth = smooth(prev, r_ml_dir)
  r_ml_used   = weight_by_regime(r_ml_smooth, risk_off_prob, regime)
  r_final     = r_rule + r_ml_used
"""

import numpy as np
from ml_overlay.config import HORIZONS

# Per-horizon gate thresholds
GATE_CFG = {
    "7D": {
        "cap": 0.05,
        "r_strong": 0.025,
        "c_strong": 0.20,
        "delta_max": 0.015,
        "w_base": 1.0,
    },
    "30D": {
        "cap": 0.08,
        "r_strong": 0.05,
        "c_strong": 0.18,
        "delta_max": 0.02,
        "w_base": 0.8,
    },
}


def gate_cap(r_ml_raw: float, horizon: str) -> tuple[float, bool]:
    """Gate #1: Cap correction within ±capH."""
    cap = GATE_CFG.get(horizon, {}).get("cap", 0.05)
    capped = abs(r_ml_raw) > cap
    return float(np.clip(r_ml_raw, -cap, cap)), capped


def gate_direction_lock(
    r_rule: float,
    r_ml_cap: float,
    conf_rule: float,
    horizon: str,
) -> tuple[float, str]:
    """
    Gate #2: Prevent ML from flipping direction when rule is strong.
    Returns (r_ml_dir, gate_action).
    gate_action: 'PASS' | 'CLAMP' | 'ZERO'
    """
    cfg = GATE_CFG.get(horizon, {})
    r_strong = cfg.get("r_strong", 0.025)
    c_strong = cfg.get("c_strong", 0.20)

    strong_rule = abs(r_rule) >= r_strong or conf_rule >= c_strong

    if not strong_rule:
        return r_ml_cap, "PASS"

    # Check if ML would flip direction
    r_final_candidate = r_rule + r_ml_cap
    if np.sign(r_rule) != 0 and np.sign(r_final_candidate) != np.sign(r_rule):
        # Try direction-preserving clamp
        limit = abs(r_rule) * 0.75
        r_ml_dir = float(np.clip(r_ml_cap, -limit, limit))

        # Re-check
        if np.sign(r_rule + r_ml_dir) != np.sign(r_rule):
            return 0.0, "ZERO"
        return r_ml_dir, "CLAMP"

    return r_ml_cap, "PASS"


def gate_smooth(
    r_ml_dir: float,
    r_ml_prev: float | None,
    horizon: str,
) -> tuple[float, str]:
    """
    Gate #3: Stability/smoothing to prevent day-to-day jitter.
    Returns (r_ml_smooth, gate_action).
    """
    if r_ml_prev is None:
        return r_ml_dir, "FIRST"

    cfg = GATE_CFG.get(horizon, {})
    delta_max = cfg.get("delta_max", 0.015)

    delta = r_ml_dir - r_ml_prev
    if abs(delta) > delta_max:
        r_ml_smooth = r_ml_prev + float(np.clip(delta, -delta_max, delta_max))
        return r_ml_smooth, "SMOOTHED"

    return r_ml_dir, "PASS"


def gate_regime_weight(
    r_ml_smooth: float,
    horizon: str,
    risk_off_prob: float = 0.0,
    regime: str = "TREND",
) -> tuple[float, float, str]:
    """
    Gate #4: Regime-aware weight.
    Returns (r_ml_used, weight, gate_action).
    """
    cfg = GATE_CFG.get(horizon, {})
    w_base = cfg.get("w_base", 1.0)

    # Risk-off dampening
    w_risk = float(np.clip(1.0 - risk_off_prob, 0.25, 1.0))

    # Regime dampening
    regime_weights = {
        "TREND": 1.0,
        "STRONG_TREND": 1.0,
        "RANGE": 0.6,
        "HIGH_VOL": 0.6,
        "CRASH": 0.3,
    }
    w_regime = regime_weights.get(regime, 0.8)

    w_total = w_base * w_risk * w_regime
    r_ml_used = r_ml_smooth * w_total

    return r_ml_used, w_total, f"w={w_total:.2f}"


def apply_full_pipeline(
    r_rule: float,
    r_ml_raw: float,
    conf_rule: float,
    horizon: str,
    r_ml_prev: float | None = None,
    risk_off_prob: float = 0.0,
    regime: str = "TREND",
) -> dict:
    """
    Run full gate pipeline: cap → dirlock → smooth → regime weight.
    Returns detailed decision log.
    """
    # Gate 1: Cap
    r_ml_cap, was_capped = gate_cap(r_ml_raw, horizon)

    # Gate 2: Direction lock
    r_ml_dir, dir_action = gate_direction_lock(r_rule, r_ml_cap, conf_rule, horizon)

    # Gate 3: Smooth
    r_ml_smooth, smooth_action = gate_smooth(r_ml_dir, r_ml_prev, horizon)

    # Gate 4: Regime weight
    r_ml_used, weight, regime_action = gate_regime_weight(
        r_ml_smooth, horizon, risk_off_prob, regime
    )

    # Final
    r_final = r_rule + r_ml_used

    return {
        "r_rule": round(float(r_rule), 6),
        "r_ml_raw": round(float(r_ml_raw), 6),
        "r_ml_cap": round(float(r_ml_cap), 6),
        "r_ml_dir": round(float(r_ml_dir), 6),
        "r_ml_smooth": round(float(r_ml_smooth), 6),
        "r_ml_used": round(float(r_ml_used), 6),
        "r_final": round(float(r_final), 6),
        "weight": round(float(weight), 3),
        "gates": {
            "cap": {"applied": was_capped, "value": round(float(r_ml_cap), 6)},
            "dirLock": {"action": dir_action, "value": round(float(r_ml_dir), 6)},
            "smooth": {"action": smooth_action, "value": round(float(r_ml_smooth), 6)},
            "regime": {"action": regime_action, "weight": round(float(weight), 3)},
        },
        "directionPreserved": bool(
            np.sign(r_rule) == 0 or np.sign(r_final) == np.sign(r_rule)
        ),
    }
