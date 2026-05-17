"""
Recommendation Engine — full decision logic from 6 axes.

Actions: YES_NOW, NO_NOW, YES_SMALL, NO_SMALL, WAIT, WATCH, AVOID, GOOD_IDEA_BAD_PRICE
Conviction: HIGH, MEDIUM, LOW
Size: FULL, MEDIUM, SMALL, NONE

Decision axes:
  1. fair_prob / edge
  2. model_confidence
  3. alignment_score
  4. resolution_risk
  5. pricing_state
  6. structural_risk

Produces: action, conviction, size, why_now, why_not, reasoning
"""


def recommend(
    edge: float,
    fair_prob: float,
    model_confidence: float,
    alignment_score: float,
    resolution: dict,
    pricing: dict,
    structural_risk: dict,
    biases: dict | None = None,
    onchain: dict | None = None,
    sentiment: dict | None = None,
) -> dict:
    """
    Generate full recommendation for a prediction market.

    Returns dict with action, conviction, size, why_now, why_not, reasoning
    """
    net_edge = edge
    abs_edge = abs(net_edge)
    is_positive = net_edge > 0
    risk = structural_risk.get("combined_risk", 0)
    res_risk = resolution.get("resolution_risk_score", 0)
    tradable = resolution.get("tradable", True)
    market_state = pricing.get("market_state", "unknown")
    res_flags = resolution.get("flags", [])

    why_now = []
    why_not = []
    reasoning = []

    # --- AVOID: resolution risk too high ---
    if not tradable:
        why_not.append("Resolution risk too high to trade")
        why_not.extend([f"Flag: {f}" for f in res_flags])
        return _build("AVOID", "LOW", "NONE", why_now, why_not,
                       ["Market has high resolution/rules risk — do not enter"])

    # --- AVOID: stale or no edge ---
    if market_state == "stale_price":
        why_not.append("Price is stale — low volume/liquidity, unreliable")
        return _build("AVOID", "LOW", "NONE", why_now, why_not,
                       ["Market lacks meaningful price discovery"])

    if abs_edge < 0.03:
        reasoning.append(f"No meaningful edge: {net_edge:+.1%}")
        return _build("AVOID", "LOW", "NONE", why_now, why_not, reasoning)

    # --- Collect drivers (why_now) ---
    if abs_edge > 0.08:
        why_now.append(f"Significant edge: {net_edge:+.1%}")
    if model_confidence > 0.6:
        why_now.append(f"Model confidence: {model_confidence:.0%}")
    if alignment_score > 0.6:
        why_now.append("Cross-module alignment confirms direction")
    if market_state == "underpriced":
        why_now.append("Market hasn't caught up — opportunity window open")
    if market_state == "early_repricing":
        why_now.append("Market starting to reprice — momentum building")

    # --- Collect risks (why_not) ---
    if risk > 0.4:
        why_not.append(f"Structural risk elevated: {risk:.0%}")
    if res_risk > 0.15:
        why_not.append(f"Resolution risk: {res_risk:.0%}")
        why_not.extend([f"Flag: {f}" for f in res_flags[:2]])
    if alignment_score < 0.4:
        why_not.append("Cross-module signals conflicting")
    if model_confidence < 0.4:
        why_not.append(f"Low model confidence: {model_confidence:.0%}")
    if market_state == "overheated":
        why_not.append("Market overheated — implied already overshoots fair")
    if market_state == "late_repricing":
        why_not.append("Late repricing — most edge already captured")
    if market_state == "panic_move":
        why_not.append("Panic move — wait for stabilization")

    # --- OnChain-driven reasons ---
    if onchain:
        oc_bias = onchain.get("bias", "neutral")
        oc_strength = onchain.get("strength", 0)
        oc_signals = onchain.get("signals", [])
        if oc_bias == "bullish" and oc_strength > 0.3 and is_positive:
            why_now.append(f"OnChain confirms accumulation (str={oc_strength:.0%})")
        elif oc_bias == "bearish" and oc_strength > 0.3 and not is_positive:
            why_now.append(f"OnChain confirms distribution (str={oc_strength:.0%})")
        elif oc_bias != "neutral" and oc_strength > 0.3:
            direction_label = "bullish" if is_positive else "bearish"
            why_not.append(f"OnChain opposes thesis ({oc_bias} vs {direction_label})")
        for sig in oc_signals[:2]:
            reasoning.append(f"OnChain: {sig}")

    # --- Sentiment-driven reasons ---
    if sentiment:
        s_bias = sentiment.get("bias", "neutral")
        s_strength = sentiment.get("strength", 0)
        s_delta = sentiment.get("delta", 0)
        if s_bias == "bullish" and s_strength > 0.3 and is_positive:
            why_now.append("Sentiment aligns with expected outcome")
        elif s_bias == "bearish" and s_strength > 0.3 and not is_positive:
            why_now.append("Sentiment aligns with expected outcome")
        elif s_bias != "neutral" and s_strength > 0.4:
            why_not.append(f"Sentiment contradicts thesis ({s_bias})")
        # Narrative overheating check
        if s_strength > 0.7 and s_bias == ("bullish" if is_positive else "bearish"):
            why_not.append("Narrative may be overheated — late entry risk")

    # --- GOOD_IDEA_BAD_PRICE ---
    if abs_edge > 0.05 and model_confidence > 0.5 and market_state in ("overheated", "late_repricing", "priced_in"):
        reasoning.append("Strong thesis but price already reflects it")
        return _build("GOOD_IDEA_BAD_PRICE", "MEDIUM", "NONE", why_now, why_not, reasoning)

    # --- WAIT: panic or repricing too fast ---
    if market_state == "panic_move":
        reasoning.append("Sharp market move — wait for stabilization before entry")
        return _build("WAIT", "MEDIUM", "NONE", why_now, why_not, reasoning)

    # --- Core decision matrix ---
    direction = "YES" if is_positive else "NO"

    # HIGH conviction: strong edge + good confidence + good alignment + clean resolution
    if abs_edge > 0.10 and model_confidence > 0.55 and alignment_score > 0.45 and res_risk < 0.25:
        if risk < 0.4:
            conv = "HIGH"
            size = "MEDIUM" if risk > 0.25 else "FULL"
            reasoning.append(f"Strong setup: edge={net_edge:+.1%}, confidence={model_confidence:.0%}")
            return _build(f"{direction}_NOW", conv, size, why_now, why_not, reasoning)
        else:
            reasoning.append("Good edge but structural risk limits size")
            return _build(f"{direction}_SMALL", "MEDIUM", "SMALL", why_now, why_not, reasoning)

    # MEDIUM conviction: decent edge + moderate confidence
    if abs_edge > 0.05 and model_confidence > 0.4:
        if res_risk > 0.20 or risk > 0.45 or alignment_score < 0.35:
            reasoning.append("Edge present but risk factors limit conviction")
            return _build(f"{direction}_SMALL", "LOW", "SMALL", why_now, why_not, reasoning)
        reasoning.append(f"Moderate setup: edge={net_edge:+.1%}")
        return _build(f"{direction}_SMALL", "MEDIUM", "SMALL", why_now, why_not, reasoning)

    # WATCH: something interesting but not enough for entry
    if abs_edge > 0.03:
        reasoning.append("Potential developing — monitor for better entry or confirmation")
        return _build("WATCH", "LOW", "NONE", why_now, why_not, reasoning)

    return _build("AVOID", "LOW", "NONE", why_now, why_not, ["No actionable setup"])


def _build(action, conviction, size, why_now, why_not, reasoning):
    return {
        "action": action,
        "conviction": conviction,
        "size": size,
        "why_now": why_now,
        "why_not": why_not,
        "reasoning": reasoning,
    }
