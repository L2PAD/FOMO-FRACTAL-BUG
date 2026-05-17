"""
Engine Flow Acceleration Service — Flow Momentum Layer
=======================================================
Detects acceleration/deceleration of capital flows.
States: bullish_acceleration, bearish_acceleration, liquidity_expansion, flow_exhaustion, neutral.
Uses velocity model: flow ratios across time windows.
"""


def _clamp01(v):
    return max(0.0, min(1.0, v))


def detect_flow_acceleration(context: dict) -> dict:
    """
    Detect flow momentum from context data.
    context: cex, smart_money, entities_summary, token, scores
    """
    cex = context.get("cex", {})
    sm = context.get("smart_money", {})
    ent = context.get("entities_summary", {})
    token = context.get("token", {})
    scores = context.get("scores", {})

    bullish_score = 0.0
    bearish_score = 0.0
    drivers = []
    exhaustion_signals = []

    # ── Smart Money velocity ──
    conviction = sm.get("conviction", 50)
    net_flow = sm.get("net_flow", 0)

    if conviction >= 65:
        bullish_score += 0.20
        drivers.append(f"Smart money conviction high ({conviction}%)")
    elif conviction <= 35:
        bearish_score += 0.15
        drivers.append(f"Smart money conviction weak ({conviction}%)")

    if net_flow > 100_000_000:
        bullish_score += 0.15
        drivers.append("Large smart money inflows active")
    elif net_flow < -50_000_000:
        bearish_score += 0.15
        drivers.append("Smart money outflows detected")

    # ── CEX velocity ──
    shock = str(cex.get("liquidity_shock", "neutral"))
    inv_state = cex.get("inventory_state", "stable")
    stablecoin = cex.get("stablecoin_bias", "neutral")
    pressure = cex.get("pressure_bias", "neutral")

    if "bullish" in shock:
        bullish_score += 0.20
        drivers.append("Bullish liquidity shock — exchange flows accelerating")
    elif "bearish" in shock:
        bearish_score += 0.20
        drivers.append("Bearish liquidity shock — outflows accelerating")

    if inv_state == "shrinking":
        bullish_score += 0.10
        drivers.append("Exchange inventory shrinking — supply acceleration")
    elif inv_state == "growing":
        bearish_score += 0.10
        drivers.append("Exchange inventory growing — supply building")

    if stablecoin == "buying_power":
        bullish_score += 0.10
        drivers.append("Stablecoin buying power expanding")

    if pressure == "bearish":
        bearish_score += 0.10

    # ── Entity velocity ──
    accum = ent.get("accumulation_actors", 0)
    dist = ent.get("distribution_actors", 0)
    b_high = ent.get("bullish_high_impact", 0)
    r_high = ent.get("bearish_high_impact", 0)

    if accum >= 3 and b_high >= 1:
        bullish_score += 0.15
        drivers.append(f"{accum} accumulating entities — actor momentum building")
    elif dist >= 2 and r_high >= 1:
        bearish_score += 0.15
        drivers.append(f"{dist} distributing entities — bearish momentum")

    # ── Token velocity ──
    regime = str(token.get("regime", "neutral"))
    positioning = token.get("positioning", 50)

    if regime == "accumulation" and positioning >= 70:
        bullish_score += 0.10
        drivers.append("Token positioning strongly bullish — momentum aligned")
    elif regime == "distribution" and positioning <= 30:
        bearish_score += 0.10
        drivers.append("Token positioning bearish — distribution momentum")

    # ── Exhaustion detection ──
    composite = scores.get("composite", 50)
    cex_score = scores.get("cex_score", 50)

    # High scores but weakening conviction = exhaustion
    if composite >= 65 and conviction < 50:
        exhaustion_signals.append("High composite but weakening conviction — flow exhaustion possible")
    if cex_score >= 75 and inv_state != "shrinking":
        exhaustion_signals.append("CEX score high but inventory not shrinking — momentum fading")

    # ── Determine state ──
    net = bullish_score - bearish_score
    total = bullish_score + bearish_score

    if exhaustion_signals and total > 0.30:
        state = "flow_exhaustion"
        strength = round(_clamp01(total * 0.6), 3)
        final_drivers = exhaustion_signals + drivers[:2]
    elif net >= 0.20:
        state = "bullish_acceleration"
        strength = round(_clamp01(bullish_score), 3)
        final_drivers = [d for d in drivers if "bearish" not in d.lower() and "weak" not in d.lower()][:5]
    elif net <= -0.15:
        state = "bearish_acceleration"
        strength = round(_clamp01(bearish_score), 3)
        final_drivers = [d for d in drivers if "bullish" not in d.lower() and "high" not in d.lower()][:5]
    elif stablecoin == "buying_power" and bullish_score >= 0.20:
        state = "liquidity_expansion"
        strength = round(_clamp01(bullish_score * 0.8), 3)
        final_drivers = [d for d in drivers if "stablecoin" in d.lower() or "liquidity" in d.lower() or "inflow" in d.lower()][:4]
    else:
        state = "neutral"
        strength = round(_clamp01(total * 0.5), 3)
        final_drivers = drivers[:3] if drivers else ["No significant flow acceleration detected"]

    # Velocity classification
    if strength >= 0.65:
        velocity = "high"
    elif strength >= 0.40:
        velocity = "moderate"
    else:
        velocity = "low"

    return {
        "state": state,
        "strength": strength,
        "velocity": velocity,
        "drivers": final_drivers,
    }
