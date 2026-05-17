"""
Entry Timing Engine — determines when and how to enter a market.

6 entry actions: enter_now, enter_limit, wait_retrace, wait_confirmation,
                 too_late, do_not_enter

Enhanced with:
  - chase_risk: risk of overpaying (late entry)
  - miss_risk: risk of losing edge by waiting
"""


def decide(edge: float, confidence: float, alignment: float,
           repricing_state: str, spread: float, liquidity: float,
           resolution_risk: float, action: str, acceleration: float = 0,
           speed_score: float = 0) -> dict:
    """
    Determine entry timing from repricing state + market conditions.

    Returns:
        dict with entry_action, urgency, order_type, entry_score,
              chase_risk, miss_risk, note
    """
    # --- Hard blocks ---
    if action == "AVOID":
        return _result("do_not_enter", "low", "wait", 0, 0, 0, "Recommendation is avoid")

    if resolution_risk >= 0.50:
        return _result("do_not_enter", "low", "wait", 0, 0, 0, "Resolution risk too high for entry")

    if liquidity < 2000:
        return _result("do_not_enter", "low", "wait", 0, 0, 0, "Liquidity insufficient for execution")

    # --- Chase risk: how much we'd overpay ---
    chase_risk = _chase_risk(repricing_state, speed_score, spread)

    # --- Miss risk: how much edge we lose by waiting ---
    miss_risk = _miss_risk(repricing_state, acceleration, edge)

    # --- Entry score ---
    score = _entry_score(edge, confidence, alignment, resolution_risk,
                         spread, liquidity, repricing_state)

    # --- State-based routing ---
    if repricing_state in ("overheated", "panic_move"):
        return _result("too_late", "low", "wait", score, chase_risk, miss_risk,
                        "Move is too extended for a clean entry")

    if repricing_state == "late_repricing":
        return _result("wait_retrace", "low", "wait", score, chase_risk, miss_risk,
                        "Thesis may be valid, but price is not ideal")

    if repricing_state == "active_repricing":
        return _result("enter_limit", "medium", "limit", score, chase_risk, miss_risk,
                        "Use passive entry while repricing is underway")

    if repricing_state in ("fresh_mispricing", "early_repricing"):
        if spread < 0.03 and liquidity >= 10000:
            return _result("enter_now", "high", "market", score, chase_risk, miss_risk,
                            "Good entry window with remaining edge")
        return _result("enter_limit", "high", "limit", score, chase_risk, miss_risk,
                        "Entry window open — use limit due to spread")

    if repricing_state == "stalled":
        return _result("wait_confirmation", "low", "wait", score, chase_risk, miss_risk,
                        "Wait for market confirmation before entering")

    if repricing_state == "fair_value":
        return _result("do_not_enter", "low", "wait", score, chase_risk, miss_risk,
                        "Market near fair value — no edge for entry")

    # Default
    return _result("wait_retrace", "low", "wait", score, chase_risk, miss_risk,
                    "Entry conditions not compelling")


def _entry_score(edge, conf, align, res_risk, spread, liq, state):
    score = 0
    score += _edge_score(edge)
    score += conf * 0.25
    score += align * 0.15
    score -= res_risk * 0.20
    score -= _micro_penalty(spread, liq)
    score -= _state_penalty(state)
    return round(max(0, min(1, score)), 4)


def _edge_score(edge):
    ae = abs(edge)
    if ae >= 0.18: return 0.35
    if ae >= 0.12: return 0.28
    if ae >= 0.08: return 0.20
    if ae >= 0.04: return 0.10
    return 0.03


def _micro_penalty(spread, liq):
    p = 0
    if spread >= 0.08: p += 0.16
    elif spread >= 0.05: p += 0.09
    elif spread >= 0.03: p += 0.04
    if liq < 3000: p += 0.08
    elif liq < 10000: p += 0.04
    return p


def _state_penalty(state):
    return {
        "fresh_mispricing": 0,
        "early_repricing": 0.03,
        "active_repricing": 0.08,
        "late_repricing": 0.16,
        "overheated": 0.24,
        "panic_move": 0.24,
        "stalled": 0.06,
        "fair_value": 0.12,
    }.get(state, 0.10)


def _chase_risk(repricing_state, speed_score, spread):
    """Risk of overpaying by entering now."""
    risk = 0
    if repricing_state in ("late_repricing", "overheated"):
        risk += 0.4
    elif repricing_state == "active_repricing":
        risk += 0.2
    elif repricing_state == "panic_move":
        risk += 0.6

    risk += speed_score * 0.2
    risk += min(spread * 3, 0.2)
    return round(min(1.0, risk), 4)


def _miss_risk(repricing_state, acceleration, edge):
    """Risk of missing the opportunity by waiting."""
    risk = 0
    if repricing_state == "fresh_mispricing" and acceleration > 0.4:
        risk += 0.5  # edge may compress fast
    elif repricing_state == "early_repricing":
        risk += 0.3
    elif repricing_state == "stalled":
        risk += 0.1  # low urgency

    risk += min(abs(edge) * 2, 0.3)
    risk += acceleration * 0.2
    return round(min(1.0, risk), 4)


def _result(action, urgency, order_type, score, chase, miss, note):
    return {
        "entry_action": action,
        "urgency": urgency,
        "order_type": order_type,
        "entry_score": score,
        "chase_risk": chase,
        "miss_risk": miss,
        "note": note,
    }
