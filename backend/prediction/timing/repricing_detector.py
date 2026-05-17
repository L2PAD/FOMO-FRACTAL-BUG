"""
Repricing Detector — determines where the market is in its repricing lifecycle.

8 states: fresh_mispricing, early_repricing, active_repricing, late_repricing,
          overheated, fair_value, stalled, panic_move

Enhanced with:
  - acceleration detection (move_1h >> avg move rate)
  - order book stress proxy (spread widening + liquidity drop)
  - volume confirmation scoring
"""


def analyze(current_prob: float, fair_prob: float, volume: float,
            liquidity: float, spread: float, deltas: dict) -> dict:
    """
    Determine repricing state from current market vs fair value + historical moves.

    Args:
        current_prob: current implied probability
        fair_prob: model fair probability
        volume, liquidity, spread: current market microstructure
        deltas: from snapshot_service.compute_deltas()

    Returns:
        dict with repricing_state, move_1h/6h/24h, speed_score,
              volume_confirmation, pricing_penalty, acceleration,
              stress_signal, reasons
    """
    edge = fair_prob - current_prob
    abs_edge = abs(edge)

    move_1h = deltas.get("delta_1h", 0)
    move_6h = deltas.get("delta_6h", 0)
    move_24h = deltas.get("delta_24h", 0)
    vol_delta_1h = deltas.get("volume_delta_1h", 0)
    vol_delta_6h = deltas.get("volume_delta_6h", 0)
    snap_count = deltas.get("snap_count", 0)

    # --- Speed score: how fast is the market moving ---
    speed_score = _speed_score(move_1h, move_6h, move_24h)

    # --- Volume confirmation ---
    volume_confirmation = _volume_confirmation(vol_delta_1h, vol_delta_6h, volume)

    # --- Acceleration: is 1h move disproportionately fast vs 6h average ---
    acceleration = _acceleration(move_1h, move_6h)

    # --- Stress signal: spread widening + liquidity drop ---
    liq_delta_6h = deltas.get("liquidity_delta_6h", 0)
    stress_signal = _stress_signal(spread, liquidity, vol_delta_6h, liq_delta_6h)

    reasons = []
    pricing_penalty = 0.0

    # --- State assignment ---
    # No snapshots yet: use edge-only heuristic
    if snap_count < 2:
        if abs_edge >= 0.10:
            state = "fresh_mispricing"
            reasons.append("Large edge detected, no history yet")
        elif abs_edge >= 0.05:
            state = "early_repricing"
            reasons.append("Moderate edge, awaiting snapshot history")
        else:
            state = "fair_value"
            reasons.append("Edge is small, market near fair value")
            pricing_penalty = 0.06
        return _result(state, move_1h, move_6h, move_24h, speed_score,
                       volume_confirmation, pricing_penalty, acceleration,
                       stress_signal, reasons)

    # Panic move: very fast 1h move + weak volume confirmation
    if abs(move_1h) >= 0.15 and volume_confirmation < 0.35:
        state = "panic_move"
        pricing_penalty = 0.20
        reasons.append("Sharp move lacks volume confirmation — likely emotional")
        if stress_signal > 0.5:
            reasons.append("Market stress elevated (spread widening / liquidity drop)")
        return _result(state, move_1h, move_6h, move_24h, speed_score,
                       volume_confirmation, pricing_penalty, acceleration,
                       stress_signal, reasons)

    # Fresh mispricing: large edge + market barely moved
    if abs_edge >= 0.10 and abs(move_6h) < 0.03:
        state = "fresh_mispricing"
        reasons.append("Large edge remains while market has barely moved")
        if acceleration > 0.6:
            reasons.append("Acceleration detected — window may narrow soon")
        return _result(state, move_1h, move_6h, move_24h, speed_score,
                       volume_confirmation, pricing_penalty, acceleration,
                       stress_signal, reasons)

    # Early repricing: decent edge + small moves beginning
    if abs_edge >= 0.07 and 0.02 <= abs(move_6h) < 0.07:
        state = "early_repricing"
        pricing_penalty = 0.03
        reasons.append("Market has started repricing but edge remains")
        if volume_confirmation >= 0.6:
            reasons.append("Move is supported by volume")
        return _result(state, move_1h, move_6h, move_24h, speed_score,
                       volume_confirmation, pricing_penalty, acceleration,
                       stress_signal, reasons)

    # Active repricing: moderate edge + significant moves
    if abs_edge >= 0.04 and 0.07 <= abs(move_6h) < 0.15:
        state = "active_repricing"
        pricing_penalty = 0.08
        reasons.append("Market is repricing actively")
        if acceleration > 0.5:
            reasons.append("Repricing is accelerating")
        return _result(state, move_1h, move_6h, move_24h, speed_score,
                       volume_confirmation, pricing_penalty, acceleration,
                       stress_signal, reasons)

    # Late repricing: small remaining edge + large move already happened
    if abs_edge > 0.02 and abs(move_6h) >= 0.15:
        state = "late_repricing"
        pricing_penalty = 0.14
        reasons.append("Much of the thesis may already be getting priced in")
        return _result(state, move_1h, move_6h, move_24h, speed_score,
                       volume_confirmation, pricing_penalty, acceleration,
                       stress_signal, reasons)

    # Overheated: tiny edge + large move
    if abs_edge <= 0.02 and abs(move_6h) >= 0.10:
        state = "overheated"
        pricing_penalty = 0.18
        reasons.append("Move is extended relative to remaining edge")
        return _result(state, move_1h, move_6h, move_24h, speed_score,
                       volume_confirmation, pricing_penalty, acceleration,
                       stress_signal, reasons)

    # Stalled: decent edge but market refuses to move
    if abs_edge >= 0.08 and abs(move_24h) < 0.015 and volume_confirmation < 0.35:
        state = "stalled"
        pricing_penalty = 0.03
        reasons.append("Thesis exists but repricing has not started — watch for catalyst")
        return _result(state, move_1h, move_6h, move_24h, speed_score,
                       volume_confirmation, pricing_penalty, acceleration,
                       stress_signal, reasons)

    # Fair value
    if abs_edge <= 0.03:
        state = "fair_value"
        pricing_penalty = 0.08
        reasons.append("Market appears close to fair value")
        return _result(state, move_1h, move_6h, move_24h, speed_score,
                       volume_confirmation, pricing_penalty, acceleration,
                       stress_signal, reasons)

    # Default: early repricing
    state = "early_repricing"
    pricing_penalty = 0.03
    reasons.append("Edge exists with moderate market movement")
    return _result(state, move_1h, move_6h, move_24h, speed_score,
                   volume_confirmation, pricing_penalty, acceleration,
                   stress_signal, reasons)


def _speed_score(m1h, m6h, m24h):
    score = abs(m1h) * 0.5 + abs(m6h) * 0.35 + abs(m24h) * 0.15
    return max(0, min(1, round(score * 5, 4)))


def _volume_confirmation(vol_d1h, vol_d6h, volume):
    """Higher = more confirmed by volume."""
    if volume < 1000:
        return 0.1
    ratio = 0.5
    if vol_d1h >= 1.5:
        ratio = 0.9
    elif vol_d1h >= 0.8:
        ratio = 0.75
    elif vol_d1h >= 0.3:
        ratio = 0.6
    elif vol_d1h >= 0:
        ratio = 0.45
    else:
        ratio = 0.25
    # Adjust by 6h trend
    if vol_d6h >= 0.5:
        ratio = min(1.0, ratio + 0.1)
    elif vol_d6h < -0.3:
        ratio = max(0, ratio - 0.1)
    return round(ratio, 4)


def _acceleration(move_1h, move_6h):
    """Detect if 1h move is disproportionately fast relative to 6h."""
    if abs(move_6h) < 0.01:
        return min(1.0, abs(move_1h) * 10)
    ratio = abs(move_1h) / abs(move_6h)
    # 1h move > 50% of 6h move = high acceleration
    if ratio >= 0.7:
        return min(1.0, round(ratio, 4))
    return round(max(0, ratio * 0.8), 4)


def _stress_signal(spread, liquidity, vol_delta_6h, liq_delta_6h=0):
    """Order book stress proxy: spread widening + liquidity drop."""
    stress = 0.0
    if spread >= 0.12:
        stress += 0.4
    elif spread >= 0.08:
        stress += 0.25
    elif spread >= 0.05:
        stress += 0.1

    if liquidity < 3000:
        stress += 0.3
    elif liquidity < 10000:
        stress += 0.15

    if vol_delta_6h < -0.3:
        stress += 0.2  # liquidity draining

    # Liquidity draining = strong stress signal
    if liq_delta_6h < -0.2:
        stress += 0.25
    elif liq_delta_6h < -0.1:
        stress += 0.1

    return round(min(1.0, stress), 4)


def _result(state, m1h, m6h, m24h, speed, vol_conf, penalty, accel, stress, reasons):
    return {
        "repricing_state": state,
        "move_1h": round(m1h, 4),
        "move_6h": round(m6h, 4),
        "move_24h": round(m24h, 4),
        "speed_score": speed,
        "volume_confirmation": vol_conf,
        "pricing_penalty": round(penalty, 4),
        "acceleration": accel,
        "stress_signal": stress,
        "reasons": reasons,
    }
