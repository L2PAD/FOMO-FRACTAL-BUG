"""
Alignment Engine — cross-module divergence/convergence scoring.

Direction-aware: alignment is computed RELATIVE to the market direction.
  - For "above" markets: bullish signals = confirming
  - For "below" markets: bearish signals = confirming

Uses unified signal format from adapters: {bias, strength, confidence}

Output:
  - alignment_score (0-1, normalized)
  - conviction_modifier (positive = boost, negative = penalty)
  - conflict_flags (list of divergence descriptions)
  - biases (per-module)
  - reasoning (list of explainability strings)
"""


def compute_alignment(market: dict, exchange: dict | None, onchain: dict | None, sentiment: dict | None) -> dict:
    """
    Compute cross-module alignment relative to market direction.

    Args:
        market: must have 'comparator' ('above' or 'below')
        exchange: from exchange_adapter or None
        onchain: from onchain_adapter (unified: bias, strength, confidence) or None
        sentiment: from sentiment_adapter (unified: bias, strength, confidence) or None

    Returns:
        dict with alignment_score, conviction_modifier, conflict_flags, biases, reasoning
    """
    comparator = market.get("comparator", "above")
    confirming_direction = "bullish" if comparator == "above" else "bearish"
    opposing_direction = "bearish" if comparator == "above" else "bullish"

    biases = {}
    reasoning = []
    conflict_flags = []

    # --- Exchange bias ---
    if exchange:
        ex_dir = exchange.get("direction", "NEUTRAL").upper()
        dl_dir = exchange.get("decision_layer", {}).get("direction", "NEUTRAL").upper()

        if any(b in ex_dir for b in ("STRONG_BULL", "MILD_BULL")) or dl_dir == "LONG":
            biases["exchange"] = "bullish"
        elif any(b in ex_dir for b in ("STRONG_BEAR", "MILD_BEAR")) or dl_dir == "SHORT":
            biases["exchange"] = "bearish"
        else:
            biases["exchange"] = "neutral"

        reasoning.append(f"Exchange: {biases['exchange']} (dir={ex_dir})")
    else:
        reasoning.append("Exchange: unavailable")

    # --- OnChain bias (real data) ---
    if onchain:
        oc_bias = onchain.get("bias", onchain.get("flow", "neutral"))
        oc_strength = onchain.get("strength", 0)
        oc_conf = onchain.get("confidence", 0)
        biases["onchain"] = oc_bias

        signals = onchain.get("signals", [])
        sig_text = signals[0] if signals else f"flow={oc_bias}"
        reasoning.append(f"OnChain: {oc_bias} (str={oc_strength:.2f}, conf={oc_conf:.2f}) — {sig_text}")

        if oc_bias == opposing_direction and oc_strength > 0.3:
            conflict_flags.append(f"OnChain opposes market direction ({oc_bias} vs {confirming_direction})")
    else:
        reasoning.append("OnChain: unavailable")

    # --- Sentiment bias (real data) ---
    if sentiment:
        s_bias = sentiment.get("bias", sentiment.get("direction", "neutral"))
        s_strength = sentiment.get("strength", 0)
        s_conf = sentiment.get("confidence", 0)
        s_count = sentiment.get("signal_count", 0)
        biases["sentiment"] = s_bias

        reasoning.append(f"Sentiment: {s_bias} (str={s_strength:.2f}, conf={s_conf:.2f}, {s_count} signals)")

        if s_bias == opposing_direction and s_strength > 0.3:
            conflict_flags.append(f"Sentiment opposes market direction ({s_bias} vs {confirming_direction})")
    else:
        reasoning.append("Sentiment: unavailable")

    # --- Score alignment ---
    confirming = 0
    opposing = 0
    total = len(biases)

    # Weighted scoring: exchange counts more, onchain second, sentiment third
    weights = {"exchange": 1.2, "onchain": 1.0, "sentiment": 0.7}
    weighted_confirm = 0.0
    weighted_oppose = 0.0
    total_weight = 0.0

    for source, bias in biases.items():
        w = weights.get(source, 0.5)
        # Multiply by strength if available
        if source == "onchain" and onchain:
            w *= (0.5 + onchain.get("strength", 0.3))
        elif source == "sentiment" and sentiment:
            w *= (0.5 + sentiment.get("strength", 0.2))

        total_weight += w
        if bias == confirming_direction:
            confirming += 1
            weighted_confirm += w
        elif bias == opposing_direction:
            opposing += 1
            weighted_oppose += w

    if total == 0:
        return {
            "alignment_score": 0.5,
            "conviction_modifier": 0.0,
            "conflict_flags": [],
            "biases": {},
            "reasoning": ["No module data available"],
        }

    # Weighted alignment score
    if total_weight > 0:
        alignment_score = (weighted_confirm - weighted_oppose + total_weight) / (2 * total_weight)
    else:
        alignment_score = 0.5
    alignment_score = max(0.0, min(1.0, alignment_score))

    # Conviction modifier
    if confirming >= 2 and opposing == 0:
        conviction_modifier = 0.10
        reasoning.append("Strong confirmation across modules")
    elif confirming == 3 and opposing == 0:
        conviction_modifier = 0.14
        reasoning.append("Full module consensus")
    elif confirming >= 2 and opposing >= 1:
        conviction_modifier = 0.0
        reasoning.append("Partial confirmation with conflict")
    elif opposing >= 2:
        conviction_modifier = -0.12
        reasoning.append("Strong cross-module conflict")
    elif confirming == 1 and opposing == 0:
        conviction_modifier = 0.04
        reasoning.append("Single source confirms")
    else:
        conviction_modifier = 0.0
        reasoning.append("Inconclusive alignment")

    return {
        "alignment_score": round(alignment_score, 4),
        "conviction_modifier": round(conviction_modifier, 4),
        "conflict_flags": conflict_flags,
        "biases": biases,
        "reasoning": reasoning,
    }
