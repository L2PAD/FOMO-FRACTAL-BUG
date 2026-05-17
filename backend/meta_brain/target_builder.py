from __future__ import annotations
import math


def build_targets(
    price_now: float,
    direction: str,
    confidence: float,
    volatility: float,
) -> dict:
    """Build realistic price targets with adaptive sizing.

    Targets adapt to market conditions:
    - Higher in trending/volatile markets
    - Lower in flat/calm markets
    """
    # Scale annualized volatility to period-specific
    daily_vol = volatility / math.sqrt(365)
    vol_7d = volatility * math.sqrt(7 / 365)
    vol_30d = volatility * math.sqrt(30 / 365)

    # TUNING 5: adaptive base move = volatility * confidence
    base_move = volatility * confidence

    move_1d = max(0.005, base_move * 0.5)
    move_7d = max(0.015, base_move * 1.2)
    move_30d = max(0.04, base_move * 2.5)

    # Cap maximum moves for sanity
    move_1d = min(move_1d, 0.03)    # max 3% per day
    move_7d = min(move_7d, 0.08)    # max 8% per week
    move_30d = min(move_30d, 0.15)  # max 15% per month

    sign = 0
    if direction == "LONG":
        sign = 1
    elif direction == "SHORT":
        sign = -1

    return {
        "1d": {
            "target": round(price_now * (1 + sign * move_1d), 2),
            "expReturn": round(sign * move_1d, 4),
        },
        "7d": {
            "target": round(price_now * (1 + sign * move_7d), 2),
            "expReturn": round(sign * move_7d, 4),
        },
        "30d": {
            "target": round(price_now * (1 + sign * move_30d), 2),
            "expReturn": round(sign * move_30d, 4),
        },
    }
