"""
Event Probability Engine — scenario-based probability computation.

Core formula:
  P(event) = P(bull) * P(hit|bull) + P(base) * P(hit|base) + P(bear) * P(hit|bear)

Design principles (Stage 2A):
  - probability = pure event likelihood (not polluted by confidence)
  - confidence = model trust level (separate axis)
  - risk_penalties = applied to scoring/decision, NOT to probability
  - regime affects confidence (mildly) and risk (strongly), not probability directly
"""
import math


# --- Regime confidence modifiers ---
REGIME_CONFIDENCE_MOD = {
    "TREND": 0.0,
    "RANGE": -0.05,
    "PULLBACK": -0.08,
    "TRANSITION": -0.15,
    "BREAKDOWN": -0.12,
    "UNKNOWN": -0.10,
}


def compute_probability(market: dict, exchange: dict | None, onchain: dict | None, sentiment: dict | None) -> dict:
    """
    Compute fair probability of a market event resolving YES.

    Returns dict with separated axes:
      - fair_yes_prob / fair_no_prob (pure probability)
      - model_confidence (how much to trust it)
      - uncertainty
      - structural_risk (reversal/breakdown/drawdown block)
      - regime
      - components (explainability)
    """
    base_prob = 0.5
    model_confidence = 0.3
    regime = "UNKNOWN"
    structural_risk = {"reversal_risk": 0, "breakdown_risk": 0, "drawdown_pressure": 0, "combined_risk": 0}

    if exchange and market.get("threshold") is not None:
        base_prob = _scenario_probability(market, exchange)
        model_confidence = exchange.get("confidence", 0.3)
        regime = exchange.get("regime", "UNKNOWN")
        structural_risk = exchange.get("structural_risk", structural_risk)

        # Regime softly adjusts confidence, NOT probability
        regime_mod = REGIME_CONFIDENCE_MOD.get(regime, -0.10)
        model_confidence = max(0.05, model_confidence + regime_mod)

    elif exchange and market.get("comparator") == "direction":
        # Direction bet: BTC Up or Down — use exchange regime + directional bias
        base_prob = _direction_probability(exchange)
        model_confidence = max(0.15, exchange.get("confidence", 0.25) * 0.7)
        regime = exchange.get("regime", "UNKNOWN")
        structural_risk = exchange.get("structural_risk", structural_risk)

    onchain_mod = _onchain_modifier(onchain) if onchain else 0.0
    sentiment_mod = _sentiment_modifier(sentiment) if sentiment else 0.0

    fair = base_prob + onchain_mod + sentiment_mod
    fair = max(0.02, min(0.98, fair))

    return {
        "fair_yes_prob": round(fair, 4),
        "fair_no_prob": round(1 - fair, 4),
        "model_confidence": round(model_confidence, 4),
        "uncertainty": round(1 - model_confidence, 4),
        "regime": regime,
        "structural_risk": structural_risk,
        "components": {
            "exchange_base": round(base_prob, 4),
            "onchain_modifier": round(onchain_mod, 4),
            "sentiment_modifier": round(sentiment_mod, 4),
        },
    }


def _scenario_probability(market: dict, exchange: dict) -> float:
    """
    Scenario-weighted probability that price crosses threshold.

    P(event) = sum over scenarios: P(scenario) * P(hit | scenario)

    Uses calibrated scenario probabilities from Exchange.
    """
    threshold = market["threshold"]
    entry_price = exchange.get("entry_price", 0)
    comparator = market.get("comparator", "above")
    scenarios = exchange.get("scenarios", {})

    if not entry_price or not scenarios:
        return 0.5

    threshold_move_pct = ((threshold - entry_price) / entry_price) * 100

    total_prob = 0.0
    total_weight = 0.0

    for stype in ("bullish", "base", "bearish"):
        s = scenarios.get(stype)
        if not s:
            continue

        scenario_prob = s.get("probability", 0)
        if scenario_prob <= 0:
            continue

        expected_move = s.get("expected_move_pct", 0)
        range_low = s.get("range_low_pct", expected_move - 2)
        range_high = s.get("range_high_pct", expected_move + 2)

        p_hit = _p_hit_given_scenario(threshold_move_pct, expected_move, range_low, range_high, comparator)
        total_prob += scenario_prob * p_hit
        total_weight += scenario_prob

    if total_weight > 0 and total_weight != 1.0:
        total_prob /= total_weight

    return max(0.02, min(0.98, total_prob))


def _p_hit_given_scenario(
    threshold_move_pct: float,
    expected_move: float,
    range_low: float,
    range_high: float,
    comparator: str,
) -> float:
    """
    Estimate P(price crosses threshold | scenario).
    Normal distribution centered on expected_move, spread from range.
    """
    spread = max(abs(range_high - range_low), 0.5)
    sigma = spread / 2.0

    z = (threshold_move_pct - expected_move) / sigma

    if comparator == "above":
        p = 1.0 - _normal_cdf(z)
    else:
        p = _normal_cdf(z)

    return max(0.01, min(0.99, p))


def _normal_cdf(z: float) -> float:
    """Standard normal CDF via error function."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2)))


def _direction_probability(exchange: dict) -> float:
    """
    For direction_bet (Up or Down) markets.
    Use exchange regime + directional scenarios to estimate P(up).
    """
    scenarios = exchange.get("scenarios", {})
    if not scenarios:
        return 0.50

    bull = scenarios.get("bullish", {})
    bear = scenarios.get("bearish", {})
    base = scenarios.get("base", {})

    # Weighted probability of positive move
    p_up = (
        bull.get("probability", 0.33) * 1.0
        + base.get("probability", 0.34) * 0.5
        + bear.get("probability", 0.33) * 0.0
    )
    return max(0.10, min(0.90, round(p_up, 4)))


def _onchain_modifier(onchain: dict) -> float:
    """On-chain flow modifier from real data: bounded ±0.06."""
    bias = onchain.get("bias", onchain.get("flow", "neutral"))
    strength = onchain.get("strength", 0.3)
    conf = onchain.get("confidence", 0.3)

    # Only modify if confidence > threshold
    if conf < 0.15:
        return 0.0

    base = min(strength, 0.8) * 0.075  # max ±0.06
    if bias == "bullish":
        return base
    elif bias == "bearish":
        return -base
    return 0.0


def _sentiment_modifier(sentiment: dict) -> float:
    """Sentiment modifier from real data: bounded ±0.05.
    Weaker than onchain to avoid narrative overweighting."""
    bias = sentiment.get("bias", sentiment.get("direction", "neutral"))
    strength = sentiment.get("strength", 0.2)
    conf = sentiment.get("confidence", 0.3)

    if conf < 0.15:
        return 0.0

    base = min(strength, 0.7) * 0.07  # max ±0.05
    if bias == "bullish":
        return base
    elif bias == "bearish":
        return -base
    return 0.0
