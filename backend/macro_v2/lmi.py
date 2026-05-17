"""Liquidity Migration Index — measures capital flow direction."""
import math
from .config import EPSILON


def _ema(values, span):
    """Simple EMA over a list of floats."""
    if not values:
        return 0
    alpha = 2 / (span + 1)
    ema = values[0]
    for v in values[1:]:
        ema = alpha * v + (1 - alpha) * ema
    return ema


def compute_lmi(series, horizon=7):
    """Compute Liquidity Migration Index from series.
    
    LMI_raw = 1.0 * ΔBTC_dom + 1.2 * ΔStable_dom
    LMI_fg  = LMI_raw + 0.3 * (0.5 - fearGreedNormalized)
    LMI = clamp(LMI_fg * 10, -100, +100)
    
    Fear & Greed adjusts LMI: extreme fear pushes toward safety inflow.
    """
    if len(series) < max(horizon + 2, 14):
        return {"lmi": 0, "deltaBtcDom7d": 0, "deltaStableDom7d": 0, "state": "NEUTRAL"}

    # Extract dom series
    btc_doms = [p["btcDom"] for p in series]
    stable_doms = [p["stableDom"] for p in series]

    # Current values
    btc_now = btc_doms[-1]
    stable_now = stable_doms[-1]

    # EMA of 7 days ago window
    btc_ema_7ago = _ema(btc_doms[:-horizon], span=7) if len(btc_doms) > horizon else btc_doms[0]
    stable_ema_7ago = _ema(stable_doms[:-horizon], span=7) if len(stable_doms) > horizon else stable_doms[0]

    delta_btc = btc_now - btc_ema_7ago
    delta_stable = stable_now - stable_ema_7ago

    lmi_raw = 1.0 * delta_btc + 1.2 * delta_stable

    # Fear & Greed adjustment: extreme fear → push toward safety
    fg = series[-1].get("fearGreed", 50)
    fg_normalized = fg / 100.0  # 0=fear, 1=greed
    fg_adjustment = 0.3 * (0.5 - fg_normalized)  # fear pushes positive (safety inflow)
    lmi_adjusted = lmi_raw + fg_adjustment

    lmi = max(-100, min(100, round(lmi_adjusted * 10)))

    if lmi >= 20:
        state = "INFLOW_TO_SAFETY"
    elif lmi <= -20:
        state = "OUTFLOW_FROM_SAFETY"
    else:
        state = "NEUTRAL"

    return {
        "lmi": lmi,
        "deltaBtcDom7d": round(delta_btc, 2),
        "deltaStableDom7d": round(delta_stable, 2),
        "state": state,
    }
