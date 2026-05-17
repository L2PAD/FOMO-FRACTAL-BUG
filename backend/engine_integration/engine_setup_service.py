"""
Engine Setup Service — E2/E5
=============================
Detects market setup types from context signals.
Setup types: liquidity_shock, smart_money_accumulation, distribution_risk,
             exchange_drain, rotation, actor_conflict, otc_transfer, mixed.

Each setup has: type, confidence, priority, status, window, supports, contradictions, invalidation.
"""


def _clamp01(v):
    return max(0.0, min(1.0, v))


SETUP_WINDOWS = {
    "liquidity_shock": {"high": "2-8h", "mid": "6-24h", "low": "12-48h"},
    "smart_money_accumulation": {"high": "6-18h", "mid": "12-36h", "low": "24-72h"},
    "distribution_risk": {"high": "6-18h", "mid": "12-36h", "low": "24-72h"},
    "exchange_drain": {"high": "8-24h", "mid": "24-72h", "low": "48h+"},
    "rotation": {"high": "12-36h", "mid": "24-72h", "low": "48h+"},
    "actor_conflict": {"high": "4-12h", "mid": "4-24h", "low": "12-48h"},
    "otc_transfer": {"high": "6-24h", "mid": "12-48h", "low": "24h+"},
    "mixed": {"high": "24h+", "mid": "48h+", "low": "—"},
}


def _window(setup_type, conf):
    tier = "high" if conf >= 0.7 else "mid" if conf >= 0.45 else "low"
    return SETUP_WINDOWS.get(setup_type, SETUP_WINDOWS["mixed"]).get(tier, "—")


def _status(conf):
    if conf >= 0.75:
        return "confirmed"
    if conf >= 0.55:
        return "active"
    if conf >= 0.35:
        return "forming"
    return "weak"


# ─── Individual Setup Detectors ───

def _detect_liquidity_shock(cex, sm, ent, token, scores):
    supports, contras, inv = [], [], []
    score = 0.0

    shock = str(cex.get("liquidity_shock", "neutral"))
    if "bullish" in shock:
        score += 0.35
        supports.append("Bullish liquidity shock on exchanges")
    elif "bearish" in shock:
        score += 0.30
        supports.append("Bearish liquidity shock on exchanges")
    else:
        return None

    if cex.get("inventory_state") == "shrinking":
        score += 0.15
        supports.append("Exchange inventory shrinking")

    if sm.get("net_flow", 0) > 50_000_000:
        score += 0.15
        supports.append("Strong smart money inflow")

    if str(token.get("regime")) == "accumulation":
        score += 0.10
        supports.append("Token regime accumulation")

    if cex.get("stablecoin_bias") == "buying_power":
        score += 0.10
        supports.append("Stablecoin buying power")

    if cex.get("pressure_bias") == "bearish":
        score -= 0.10
        contras.append("Exchange deposit pressure bearish")
        inv.append("Exchange deposits continue rising")

    if scores.get("entities_score", 50) < 45:
        score -= 0.08
        contras.append("Weak entity participation")
        inv.append("Entity pressure weakens further")

    return {
        "type": "liquidity_shock",
        "confidence": round(_clamp01(score), 3),
        "priority": 1,
        "supports": supports,
        "contradictions": contras,
        "invalidation": inv,
    }


def _detect_smart_money_accumulation(cex, sm, ent, token, scores):
    supports, contras, inv = [], [], []
    score = 0.0

    conviction = sm.get("conviction", 0)
    if conviction < 45:
        return None

    score += min(conviction / 100, 0.35)
    supports.append(f"Smart money conviction {conviction}%")

    cap_weight = scores.get("components", {}).get("smart_money", {}).get("capital_weight", 0)
    if cap_weight > 60:
        score += 0.15
        supports.append("Strong capital weight")

    if cex.get("inventory_state") == "shrinking":
        score += 0.10
        supports.append("Exchange outflows active")

    if str(token.get("regime")) == "accumulation":
        score += 0.10
        supports.append("Token accumulation regime")

    accum_actors = ent.get("accumulation_actors", 0)
    if accum_actors >= 2:
        score += 0.10
        supports.append(f"{accum_actors} entities in accumulation")

    if cex.get("pressure_bias") == "bearish":
        score -= 0.10
        contras.append("Exchange deposit pressure rising")
        inv.append("Deposit pressure accelerates")

    return {
        "type": "smart_money_accumulation",
        "confidence": round(_clamp01(score), 3),
        "priority": 2,
        "supports": supports,
        "contradictions": contras,
        "invalidation": inv,
    }


def _detect_distribution_risk(cex, sm, ent, token, scores):
    supports, contras, inv = [], [], []
    score = 0.0

    if cex.get("pressure_bias") == "bearish":
        score += 0.20
        supports.append("Exchange deposit pressure rising")

    bearish_actors = ent.get("bearish_actors", 0)
    if bearish_actors >= 1:
        score += 0.15
        supports.append(f"{bearish_actors} bearish actor(s)")

    if str(token.get("regime")) == "distribution":
        score += 0.20
        supports.append("Token distribution regime")

    if cex.get("inventory_state") == "growing":
        score += 0.15
        supports.append("Exchange inventory growing")

    if score < 0.25:
        return None

    if sm.get("net_flow", 0) > 100_000_000:
        score -= 0.15
        contras.append("Strong smart money inflow contradicts")
        inv.append("Smart money accumulation overwhelms distribution")

    return {
        "type": "distribution_risk",
        "confidence": round(_clamp01(score), 3),
        "priority": 2,
        "supports": supports,
        "contradictions": contras,
        "invalidation": inv,
    }


def _detect_exchange_drain(cex, sm, ent, token, scores):
    supports, contras, inv = [], [], []
    score = 0.0

    if cex.get("inventory_state") == "shrinking":
        score += 0.30
        supports.append("Exchange inventory shrinking — supply leaving")

    net_liq = cex.get("net_liquidity", 0)
    if net_liq < -10000:
        score += 0.20
        supports.append("Net liquidity outflows from exchanges")

    if sm.get("net_flow", 0) > 50_000_000:
        score += 0.15
        supports.append("Smart money moving capital off exchanges")

    if score < 0.25:
        return None

    if cex.get("pressure_bias") == "bearish":
        score -= 0.10
        contras.append("Deposit pressure partially offsets drain")
        inv.append("Deposit pressure overwhelms outflows")

    return {
        "type": "exchange_drain",
        "confidence": round(_clamp01(score), 3),
        "priority": 3,
        "supports": supports,
        "contradictions": contras,
        "invalidation": inv,
    }


def _detect_rotation(cex, sm, ent, token, scores):
    supports, contras, inv = [], [], []
    score = 0.0

    pattern = str(token.get("pattern", ""))
    if "rotation" in pattern or "diverge" in pattern:
        score += 0.30
        supports.append("Token pattern shows rotation")

    lp_actors = ent.get("lp_actors", 0)
    if lp_actors >= 2:
        score += 0.20
        supports.append(f"{lp_actors} liquidity provision entities active")

    sm_conviction = sm.get("conviction", 50)
    if 35 <= sm_conviction <= 65:
        score += 0.10
        supports.append("Smart money conviction neutral — no strong direction")

    if score < 0.25:
        return None

    return {
        "type": "rotation",
        "confidence": round(_clamp01(score), 3),
        "priority": 4,
        "supports": supports,
        "contradictions": contras,
        "invalidation": inv,
    }


def _detect_actor_conflict(cex, sm, ent, token, scores):
    """E2: Actor Conflict as a setup type."""
    supports, contras, inv = [], [], []
    score = 0.0

    bullish = ent.get("bullish_actors", 0)
    bearish = ent.get("bearish_actors", 0)
    b_high = ent.get("bullish_high_impact", 0)
    r_high = ent.get("bearish_high_impact", 0)

    if bullish < 1 or bearish < 1:
        return None

    score += 0.25
    supports.append(f"{bullish} bullish vs {bearish} bearish actors")

    if b_high > 0 and r_high > 0:
        score += 0.25
        supports.append(f"High-impact actors on both sides ({b_high} bull, {r_high} bear)")
    elif b_high > 0 or r_high > 0:
        score += 0.10
        supports.append("High-impact actor on one side")

    module_scores = [
        scores.get("smart_money_score", 50),
        scores.get("cex_score", 50),
        scores.get("entities_score", 50),
        scores.get("token_score", 50),
    ]
    divergence = max(module_scores) - min(module_scores)
    if divergence > 30:
        score += 0.15
        supports.append(f"Module divergence {divergence} pts — conflicting signals")

    inv.append("One side gains dominant impact weight")
    inv.append("Smart money conviction breaks above 70%")

    return {
        "type": "actor_conflict",
        "confidence": round(_clamp01(score), 3),
        "priority": 2,
        "supports": supports,
        "contradictions": contras,
        "invalidation": inv,
    }


def _detect_otc_transfer(cex, sm, ent, token, scores, otc_data=None):
    supports, contras, inv = [], [], []
    score = 0.0

    trades = (otc_data or {}).get("trades", [])
    if not trades:
        return None

    best = max(trades, key=lambda t: t.get("confidence", 0))
    score += min(best.get("confidence", 0) * 0.5, 0.30)
    supports.append(f"OTC trade detected: {best.get('usd_value_fmt', '?')}")

    if len(trades) >= 2:
        score += 0.15
        supports.append(f"{len(trades)} OTC trades in window")

    if score < 0.20:
        return None

    inv.append("No follow-through in on-chain flows")

    return {
        "type": "otc_transfer",
        "confidence": round(_clamp01(score), 3),
        "priority": 5,
        "supports": supports,
        "contradictions": contras,
        "invalidation": inv,
    }


# ─── Main Setup Selector ───

def detect_all_setups(context: dict) -> dict:
    """
    Detect all market setups from context and select primary + secondary.

    context must contain: cex, smart_money, entities_summary, token, scores, otc_data (optional)
    """
    cex = context.get("cex", {})
    sm = context.get("smart_money", {})
    ent = context.get("entities_summary", {})
    token = context.get("token", {})
    scores = context.get("scores", {})
    otc = context.get("otc_data")

    candidates = []
    for detector in [
        lambda: _detect_liquidity_shock(cex, sm, ent, token, scores),
        lambda: _detect_smart_money_accumulation(cex, sm, ent, token, scores),
        lambda: _detect_distribution_risk(cex, sm, ent, token, scores),
        lambda: _detect_exchange_drain(cex, sm, ent, token, scores),
        lambda: _detect_rotation(cex, sm, ent, token, scores),
        lambda: _detect_actor_conflict(cex, sm, ent, token, scores),
        lambda: _detect_otc_transfer(cex, sm, ent, token, scores, otc),
    ]:
        result = detector()
        if result and result["confidence"] >= 0.20:
            candidates.append(result)

    if not candidates:
        return {
            "primary": {
                "type": "mixed",
                "confidence": 0.30,
                "priority": 10,
                "status": "active",
                "window": "—",
                "supports": ["No clear setup pattern detected"],
                "contradictions": [],
                "invalidation": ["Any strong directional signal emerges"],
            },
            "secondary": [],
        }

    # Sort: highest confidence first, then by priority (lower = higher priority)
    candidates.sort(key=lambda s: (-s["confidence"], s["priority"]))

    primary = candidates[0]
    primary["status"] = _status(primary["confidence"])
    primary["window"] = _window(primary["type"], primary["confidence"])

    secondary = []
    for c in candidates[1:4]:
        secondary.append({
            "type": c["type"],
            "confidence": c["confidence"],
            "status": _status(c["confidence"]),
        })

    return {"primary": primary, "secondary": secondary}
