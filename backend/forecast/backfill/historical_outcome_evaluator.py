"""
Historical Outcome Evaluator
==============================
Evaluates replay forecasts against actual realized prices.
Point-in-time: outcome price is taken at as_of + horizon_days.
"""


def evaluate_outcome(
    prices: dict[str, float],
    entry_price: float,
    outcome_date: str,
) -> dict | None:
    """
    Evaluate the actual market outcome for a replay case.
    Returns None if outcome price is unavailable.
    """
    actual_price = prices.get(outcome_date)
    if actual_price is None:
        # Try nearest earlier date (weekends/holidays)
        for d in sorted(prices.keys(), reverse=True):
            if d <= outcome_date:
                actual_price = prices[d]
                break

    if actual_price is None:
        return None

    real_move_pct = (actual_price - entry_price) / entry_price * 100

    if real_move_pct > 0.5:
        real_direction = "BULL"
    elif real_move_pct < -0.5:
        real_direction = "BEAR"
    else:
        real_direction = "FLAT"

    return {
        "actual_price": round(actual_price, 2),
        "real_move_pct": round(real_move_pct, 4),
        "real_direction": real_direction,
    }
