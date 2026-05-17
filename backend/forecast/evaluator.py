"""
Forecast Evaluator v4.1
========================
Handles both legacy 3-state (LONG/SHORT/NEUTRAL) and
new 5-state (STRONG_BULL/MILD_BULL/NEUTRAL/MILD_BEAR/STRONG_BEAR) directions.

Evaluation is separate for:
- direction correctness (was the bias right?)
- target accuracy (was the price target close?)
- strength correctness (was mild/strong classification right?)
"""

from forecast import Horizon, OutcomeLabel, OUTCOME_THRESHOLD
from forecast.price_provider import get_price

BULLISH_CLASSES = {"LONG", "STRONG_BULL", "MILD_BULL"}
BEARISH_CLASSES = {"SHORT", "STRONG_BEAR", "MILD_BEAR"}


def evaluate_forecast(doc: dict) -> dict | None:
    """Evaluate a single forecast record against actual price."""
    horizon = Horizon(doc["horizon"])
    threshold = OUTCOME_THRESHOLD[horizon]

    actual_price = get_price(doc["asset"], doc["evaluateAfter"])
    if actual_price is None:
        return {
            "evaluatedAt": doc["evaluateAfter"],
            "actualPriceAtEval": None,
            "errorPct": None,
            "outcome": OutcomeLabel.NO_DATA.value,
            "reason": "PRICE_SOURCE_MISSING",
            "label": OutcomeLabel.NO_DATA.value,
        }

    entry = doc["entryPrice"]
    target = doc["targetPrice"]
    direction = doc["direction"]  # Legacy: LONG/SHORT/NEUTRAL
    direction_class = doc.get("directionClass")  # v4.1: 5-state

    real_move_pct = (actual_price - entry) / entry * 100

    # Direction evaluation (works for both 3-state and 5-state)
    if direction in BULLISH_CLASSES:
        error_pct = (actual_price - target) / target * 100
        target_hit = actual_price >= target
        dir_match = actual_price > entry
    elif direction in BEARISH_CLASSES:
        error_pct = (target - actual_price) / target * 100
        target_hit = actual_price <= target
        dir_match = actual_price < entry
    else:
        error_pct = abs(real_move_pct)
        target_hit = abs(real_move_pct) < 0.5
        dir_match = abs(real_move_pct) < 1.0

    # Outcome mapping
    if target_hit:
        outcome = OutcomeLabel.TP
    elif dir_match:
        outcome = OutcomeLabel.WEAK
    elif abs(real_move_pct) > threshold:
        outcome = OutcomeLabel.FP
    else:
        outcome = OutcomeLabel.FN

    # v4.1: Extra evaluation metrics
    strength_class = None
    if direction_class:
        is_strong = direction_class.startswith("STRONG_")
        is_mild = direction_class.startswith("MILD_")
        if is_strong:
            strength_class = "strong_correct" if dir_match else "strong_wrong"
        elif is_mild:
            strength_class = "mild_correct" if dir_match else "mild_wrong"
        else:
            strength_class = "neutral"

    return {
        "evaluatedAt": doc["evaluateAfter"],
        "actualPriceAtEval": round(actual_price, 2),
        "errorPct": round(error_pct, 2),
        "realMovePct": round(real_move_pct, 2),
        "directionMatch": dir_match,
        "hit": target_hit,
        "outcome": outcome.value,
        "label": outcome.value,
        "strengthClass": strength_class,
    }
