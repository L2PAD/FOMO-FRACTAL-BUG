"""
Engine Liquidity Map Service
=============================
Builds a structural liquidity map: magnet zones, void zones, target zones.
Uses CEX, entity, and token data to identify where price is likely to move.
Rule-based, no ML.
"""


def build_liquidity_map(context: dict, setup_engine: dict, regime_engine: dict) -> dict:
    """
    Build liquidity map from context + setup/regime.
    context: cex, smart_money, entities_summary, token, scores
    """
    cex = context.get("cex", {})
    ent = context.get("entities_summary", {})

    setup_type = setup_engine.get("primary", {}).get("type", "mixed")
    setup_conf = setup_engine.get("primary", {}).get("confidence", 0.30)
    regime_type = regime_engine.get("primary", {}).get("type", "neutral_chop")

    magnet_zones = []
    void_zones = []
    target_zones = []

    # ── Magnet Zones (areas price is pulled toward) ──

    # Liquidation cluster from CEX data
    shock = str(cex.get("liquidity_shock", "neutral"))
    if "bullish" in shock:
        magnet_zones.append({
            "type": "liquidation_cluster",
            "direction": "above",
            "strength": "high",
            "reason": "Bullish liquidity shock — short liquidation cluster above",
        })
    elif "bearish" in shock:
        magnet_zones.append({
            "type": "liquidation_cluster",
            "direction": "below",
            "strength": "high",
            "reason": "Bearish liquidity shock — long liquidation cluster below",
        })

    # Entity accumulation zone
    accum = ent.get("accumulation_actors", 0)
    if accum >= 3:
        magnet_zones.append({
            "type": "accumulation_zone",
            "direction": "support",
            "strength": "moderate" if accum < 5 else "high",
            "reason": f"{accum} entities in accumulation — demand zone forming",
        })

    # Stablecoin liquidity
    if cex.get("stablecoin_bias") == "buying_power":
        magnet_zones.append({
            "type": "stablecoin_liquidity",
            "direction": "above",
            "strength": "moderate",
            "reason": "Stablecoin buying power active — bid liquidity",
        })

    # ── Void Zones (thin liquidity, fast moves) ──

    inv_state = cex.get("inventory_state", "stable")
    if inv_state == "shrinking":
        void_zones.append({
            "type": "supply_vacuum",
            "direction": "above",
            "severity": "moderate",
            "reason": "Exchange inventory shrinking — thin sell-side liquidity",
        })

    # Low entity engagement = thin structural support
    b_actors = ent.get("bullish_actors", 0)
    r_actors = ent.get("bearish_actors", 0)
    total = b_actors + r_actors
    if total <= 2:
        void_zones.append({
            "type": "low_participation",
            "direction": "both",
            "severity": "low",
            "reason": "Low entity participation — thin structural liquidity",
        })

    # Distribution pressure creates void above
    if ent.get("distribution_actors", 0) >= 2 and inv_state == "growing":
        void_zones.append({
            "type": "distribution_wall",
            "direction": "above",
            "severity": "moderate",
            "reason": "Distribution entities + growing inventory — resistance zone",
        })

    # ── Target Zones (setup-implied targets) ──

    # Setup-based targets
    if setup_type == "liquidity_shock" and "bullish" in shock:
        conf = min(setup_conf * 0.9, 0.85)
        target_zones.append({
            "direction": "above",
            "confidence": round(conf, 2),
            "type": "liquidation_sweep",
            "reason": "Liquidity shock targets short liquidation cluster above",
        })
    elif setup_type == "liquidity_shock" and "bearish" in shock:
        conf = min(setup_conf * 0.9, 0.85)
        target_zones.append({
            "direction": "below",
            "confidence": round(conf, 2),
            "type": "liquidation_sweep",
            "reason": "Bearish shock targets long liquidation cluster below",
        })

    if setup_type == "smart_money_accumulation" and regime_type in ("accumulation", "bull_trend"):
        target_zones.append({
            "direction": "above",
            "confidence": round(min(setup_conf * 0.8, 0.75), 2),
            "type": "breakout_target",
            "reason": "SM accumulation inside bullish regime — breakout target",
        })

    if setup_type == "distribution_risk":
        target_zones.append({
            "direction": "below",
            "confidence": round(min(setup_conf * 0.85, 0.80), 2),
            "type": "breakdown_target",
            "reason": "Distribution risk — potential breakdown target",
        })

    if setup_type == "exchange_drain":
        target_zones.append({
            "direction": "above",
            "confidence": round(min(setup_conf * 0.7, 0.65), 2),
            "type": "supply_squeeze",
            "reason": "Exchange drain — supply squeeze target",
        })

    # Regime-based general target
    if regime_type == "bull_trend" and not target_zones:
        target_zones.append({
            "direction": "above",
            "confidence": 0.55,
            "type": "trend_continuation",
            "reason": "Bull trend regime — continuation target",
        })
    elif regime_type == "bear_trend" and not target_zones:
        target_zones.append({
            "direction": "below",
            "confidence": 0.55,
            "type": "trend_continuation",
            "reason": "Bear trend regime — continuation target",
        })

    # ── Summary ──
    has_magnets = len(magnet_zones) > 0
    has_targets = len(target_zones) > 0
    primary_direction = "above" if any(t["direction"] == "above" for t in target_zones) else "below" if any(t["direction"] == "below" for t in target_zones) else "neutral"

    if has_targets and has_magnets:
        summary = f"Liquidity structure supports {primary_direction} movement with {len(magnet_zones)} magnet zone(s)"
    elif has_magnets:
        summary = f"{len(magnet_zones)} magnet zone(s) detected — price attraction areas identified"
    elif has_targets:
        summary = f"Setup targets {primary_direction} — {len(target_zones)} target zone(s)"
    else:
        summary = "No significant liquidity structure detected"

    return {
        "magnet_zones": magnet_zones,
        "void_zones": void_zones,
        "target_zones": target_zones,
        "primary_direction": primary_direction,
        "summary": summary,
    }
