"""
R1.1 — Research V2 Scoring
Interprets snapshot into structured domains:
  - Market State (regime, volatility, liquidity, flow, stress)
  - Risk Pressure (0..1)
  - Horizon Bias (short/mid/swing)
  - Dominant Forces (top 3 drivers)
  - Execution Implications (what to do / avoid)
"""

from typing import Dict, List, Any


# ═══════════════════════════════════════════════════════════════
# MARKET STATE
# ═══════════════════════════════════════════════════════════════

def compute_market_state(snapshot: dict) -> Dict[str, Any]:
    """Extract 5 market domains from labs."""
    labs = snapshot.get("labs", {})

    def _domain(lab_key: str, fallback_state: str = "UNKNOWN"):
        lab = labs.get(lab_key, {})
        return {
            "state": lab.get("state", fallback_state),
            "confidence": round(lab.get("confidence", 0), 2),
        }

    return {
        "regime": _domain("regime", "RANGE"),
        "volatility": _domain("volatility", "NORMAL_VOL"),
        "liquidity": _domain("liquidity", "NORMAL_LIQUIDITY"),
        "flow": _domain("flow", "BALANCED"),
        "stress": _domain("marketStress", "NORMAL"),
    }


# ═══════════════════════════════════════════════════════════════
# RISK PRESSURE
# ═══════════════════════════════════════════════════════════════

_RISK_STATES = {
    "THIN_LIQUIDITY": 0.8, "LIQUIDITY_GAPS": 0.9,
    "MANIPULATION": 0.9, "MANIPULATION_RISK": 0.7, "ANOMALY": 0.6,
    "STRESSED": 0.7, "PANIC": 0.95, "CHAOTIC": 0.8,
    "DEGRADED": 0.6, "UNTRUSTED": 0.8,
    "CASCADE_RISK": 0.9, "FRAGILE": 0.7,
}


def compute_risk_pressure(snapshot: dict) -> Dict[str, Any]:
    """Aggregate risk from labs, divergence, data quality."""
    labs = snapshot.get("labs", {})
    radar = snapshot.get("radar", {})
    health = snapshot.get("health", {})

    # Labs-based risk
    risk_scores = []
    drivers = []

    for key in ["liquidity", "manipulation", "marketStress", "dataQuality", "stability"]:
        lab = labs.get(key, {})
        state = lab.get("state", "")
        conf = lab.get("confidence", 0)
        risk_val = _RISK_STATES.get(state, 0)
        if risk_val > 0:
            weighted = risk_val * conf
            risk_scores.append(weighted)
            if weighted >= 0.4:
                drivers.append(_risk_driver_label(key, state))

    # Divergence density from radar
    div = radar.get("divergence", {})
    avg_div = div.get("avgDivergence", 0)
    if avg_div > 0.3:
        risk_scores.append(avg_div)
        drivers.append("Cross-venue divergence elevated")

    # Health-based risk
    h_status = health.get("status", "UNKNOWN")
    if h_status not in ("HEALTHY", "healthy"):
        risk_scores.append(0.5)
        drivers.append("System health degraded")

    # Aggregate
    if risk_scores:
        score = min(1.0, sum(risk_scores) / max(1, len(risk_scores)) * 1.3)
    else:
        score = 0.1

    score = round(score, 2)

    if score > 0.65:
        level = "HIGH"
    elif score > 0.35:
        level = "MID"
    else:
        level = "LOW"

    return {"score": score, "level": level, "drivers": drivers[:5]}


def _risk_driver_label(key: str, state: str) -> str:
    labels = {
        "liquidity": "Liquidity thin",
        "manipulation": "Manipulation risk",
        "marketStress": "Market stress elevated",
        "dataQuality": "Data quality degraded",
        "stability": "System instability",
    }
    return labels.get(key, f"{key}: {state}")


# ═══════════════════════════════════════════════════════════════
# HORIZON BIAS
# ═══════════════════════════════════════════════════════════════

def compute_horizon_bias(snapshot: dict, labs_v2_state: dict = None) -> Dict[str, Any]:
    """Derive short/mid/swing bias from radar + labs + Labs V2 state."""
    labs = snapshot.get("labs", {})
    radar = snapshot.get("radar", {})
    pulse = snapshot.get("pulse", {})

    regime = labs.get("regime", {}).get("state", "RANGE")
    momentum = labs.get("momentum", {}).get("state", "NEUTRAL")
    vol = labs.get("volatility", {}).get("state", "NORMAL_VOL")

    # Labs V2 state scores for enrichment
    v2_state = (labs_v2_state or {}).get("overallState", {})
    v2_scores = v2_state.get("scores", {})
    range_score = v2_scores.get("RANGE_CHOP", 0)
    breakout_score = v2_scores.get("BREAKOUT_ACTIVE", 0)
    dist_score = v2_scores.get("DISTRIBUTION", 0)

    # Radar stats
    spot = radar.get("spot", {})
    verdicts = spot.get("verdictDistribution", {})
    total = sum(verdicts.values()) if verdicts else 1
    buy_pct = verdicts.get("buy", 0) / max(1, total)
    sell_pct = verdicts.get("sell", 0) / max(1, total)

    pulse_bias = pulse.get("bias", "MIXED")

    # Short bias — enriched by Labs V2
    if range_score > 0.6:
        short_bias = "Selective / fade"
        short_conf = 0.55 + range_score * 0.2
    elif breakout_score > 0.6:
        short_bias = "Aggressive momentum"
        short_conf = 0.55 + breakout_score * 0.3
    elif dist_score > 0.5:
        short_bias = "Defensive / wait"
        short_conf = 0.6
    elif regime in ("RANGE", "INSIDE_RANGE") and vol == "LOW_VOL":
        short_bias = "Fade breakouts"
        short_conf = 0.7
    elif momentum in ("ACCELERATING",) and buy_pct > 0.15:
        short_bias = "Momentum continuation"
        short_conf = 0.65
    elif sell_pct > buy_pct * 1.5:
        short_bias = "Defensive / wait"
        short_conf = 0.6
    else:
        short_bias = "Selective entries"
        short_conf = 0.5

    # Mid bias — enriched by Labs V2
    if range_score > 0.6:
        mid_bias = "Mean reversion"
        mid_conf = 0.55 + range_score * 0.2
    elif breakout_score > 0.5:
        mid_bias = "Trend following"
        mid_conf = 0.55 + breakout_score * 0.25
    elif regime in ("TRENDING_UP",) and pulse_bias == "BULLISH":
        mid_bias = "Trend following"
        mid_conf = 0.7
    elif regime in ("TRANSITION", "CHAOTIC"):
        mid_bias = "Avoid trend trades"
        mid_conf = 0.6
    else:
        mid_bias = "Selective"
        mid_conf = 0.5

    # Swing bias
    if regime in ("TRANSITION", "CHAOTIC"):
        swing_bias = "Regime shift possible"
        swing_conf = 0.6
    elif regime in ("TRENDING_UP",) and buy_pct > 0.10:
        swing_bias = "Trend continuation"
        swing_conf = 0.55
    else:
        swing_bias = "No clear regime shift"
        swing_conf = 0.45

    return {
        "short": {"bias": short_bias, "confidence": round(short_conf, 2)},
        "mid": {"bias": mid_bias, "confidence": round(mid_conf, 2)},
        "swing": {"bias": swing_bias, "confidence": round(swing_conf, 2)},
    }


# ═══════════════════════════════════════════════════════════════
# DOMINANT FORCES
# ═══════════════════════════════════════════════════════════════

_ABNORMAL_STATES = {
    "STRESSED", "PANIC", "CHAOTIC", "THIN_LIQUIDITY", "MANIPULATION",
    "CASCADE_RISK", "FRAGILE", "DISTRIBUTION", "ACCUMULATION",
    "HIGH_VOL", "SELL_DOMINANT", "BUY_DOMINANT", "ACCELERATING",
    "TRANSITION", "ANOMALY", "DEGRADED", "UNTRUSTED",
}

_FORCE_EXPLANATIONS = {
    "regime": {"RANGE": "Market consolidating in range", "TRANSITION": "Regime shift underway", "TRENDING_UP": "Bullish trend active", "CHAOTIC": "No clear structure"},
    "volatility": {"HIGH_VOL": "Elevated price swings", "LOW_VOL": "Compressed volatility — breakout building"},
    "liquidity": {"THIN_LIQUIDITY": "Low liquidity — slippage risk", "DEEP_LIQUIDITY": "Deep books — stable execution"},
    "flow": {"SELL_DOMINANT": "Sellers controlling flow", "BUY_DOMINANT": "Buyers driving price"},
    "marketStress": {"STRESSED": "Elevated market stress", "PANIC": "Panic conditions detected"},
    "momentum": {"ACCELERATING": "Momentum building", "DECELERATING": "Momentum fading"},
    "whale": {"ACCUMULATION": "Whale accumulation detected", "DISTRIBUTION": "Whale distribution detected"},
    "manipulation": {"MANIPULATION": "Manipulation patterns active"},
    "participation": {"NARROW_PARTICIPATION": "Low market participation"},
}


def compute_dominant_forces(snapshot: dict) -> List[Dict[str, Any]]:
    """Top 3 market drivers by impact."""
    labs = snapshot.get("labs", {})
    forces = []

    for key, lab in labs.items():
        state = lab.get("state", "")
        conf = lab.get("confidence", 0)
        abnormal = 1.5 if state in _ABNORMAL_STATES else 1.0
        impact = round(conf * abnormal, 3)

        explanation = _FORCE_EXPLANATIONS.get(key, {}).get(state, "")
        if not explanation:
            explanation = lab.get("explain", {}).get("summary", f"{key}: {state}")

        forces.append({
            "name": key,
            "state": state,
            "impactScore": impact,
            "explanation": explanation,
        })

    # Add divergence as a force if multi-venue data exists
    radar = snapshot.get("radar", {})
    div_data = radar.get("divergence", {})
    avg_div = div_data.get("avgDivergence", 0)
    multi_venue_pct = div_data.get("multiVenuePct", 0)
    if avg_div > 0 and multi_venue_pct > 0:
        div_label = "HIGH" if avg_div > 0.6 else "MID" if avg_div > 0.3 else "LOW"
        forces.append({
            "name": "divergence",
            "state": div_label,
            "impactScore": round(avg_div * 1.2, 3),
            "explanation": f"Cross-venue divergence {div_label} ({int(multi_venue_pct)}% multi-venue)",
        })

    forces.sort(key=lambda f: f["impactScore"], reverse=True)
    return forces[:5]


# ═══════════════════════════════════════════════════════════════
# EXECUTION IMPLICATIONS
# ═══════════════════════════════════════════════════════════════

def compute_execution_implications(snapshot: dict, risk: dict, horizon: dict) -> Dict[str, Any]:
    """What this means for trading — NOT signals."""
    labs = snapshot.get("labs", {})
    regime = labs.get("regime", {}).get("state", "RANGE")
    liquidity = labs.get("liquidity", {}).get("state", "NORMAL")
    risk_level = risk.get("level", "LOW")

    # Style
    if regime in ("RANGE", "INSIDE_RANGE"):
        style = "Fade breakouts, mean-revert"
    elif regime in ("TRENDING_UP",):
        style = "Momentum continuation"
    elif regime in ("TRANSITION", "CHAOTIC"):
        style = "Reduce activity, wait for clarity"
    else:
        style = "Selective"

    # Avoid
    avoid = []
    if liquidity in ("THIN_LIQUIDITY", "LIQUIDITY_GAPS"):
        avoid.append("Illiquid alts")
    if risk_level == "HIGH":
        avoid.append("Leverage positions")
        avoid.append("Large size entries")
    if regime in ("CHAOTIC", "TRANSITION"):
        avoid.append("Trend-following setups")

    # Preferred instruments
    if liquidity in ("THIN_LIQUIDITY",):
        preferred = ["Spot (lower slippage)"]
    elif regime in ("TRENDING_UP", "TRENDING_DOWN"):
        preferred = ["Futures + Spot"]
    else:
        preferred = ["Spot"]

    # Risk controls
    controls = []
    if risk_level == "HIGH":
        controls.extend(["Reduce position size 30%", "Tighten stops"])
    elif risk_level == "MID":
        controls.append("Monitor closely, standard size")
    else:
        controls.append("Normal risk parameters")

    return {
        "style": style,
        "avoid": avoid,
        "preferredInstruments": preferred,
        "riskControls": controls,
    }
