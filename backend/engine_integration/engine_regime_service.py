"""
Engine Regime Service — E5.5
=============================
Determines the global market regime (background state).
Regime types: bull_trend, bear_trend, accumulation, distribution, rotation, neutral_chop.

Regime is higher-level than Setup — the same setup reads differently in different regimes.
"""


def _clamp01(v):
    return max(0.0, min(1.0, v))


def _status(conf):
    if conf >= 0.75:
        return "confirmed"
    if conf >= 0.55:
        return "active"
    if conf >= 0.35:
        return "forming"
    return "weak"


# ─── Individual Regime Detectors ───

def _detect_bull_trend(cex, sm, ent, token, scores):
    score = 0.0
    drivers = []

    if scores.get("cex_score", 50) >= 60:
        score += 0.20
        drivers.append("CEX flow structure bullish")

    if scores.get("smart_money_score", 50) >= 55:
        score += 0.20
        drivers.append("Smart money positioning constructive")

    if ent.get("pressure_balance") == "bullish":
        score += 0.15
        drivers.append("Entity pressure balance bullish")

    if str(token.get("regime")) == "accumulation" and token.get("confidence", 0) >= 60:
        score += 0.15
        drivers.append("Token structure strong and accumulating")

    if str(token.get("pattern", "")).startswith("strong_bullish"):
        score += 0.10
        drivers.append("Strong bullish token pattern")

    net_flow = sm.get("net_flow", 0)
    if net_flow > 100_000_000:
        score += 0.10
        drivers.append("Significant capital inflow")

    inv = ["Exchange deposit pressure overwhelms outflows", "Token regime shifts to distribution"]

    return {"type": "bull_trend", "confidence": round(_clamp01(score), 3), "drivers": drivers, "invalidation": inv}


def _detect_bear_trend(cex, sm, ent, token, scores):
    score = 0.0
    drivers = []

    if cex.get("pressure_bias") == "bearish":
        score += 0.20
        drivers.append("Exchange deposit pressure bearish")

    if ent.get("bearish_actors", 0) > ent.get("bullish_actors", 0):
        score += 0.15
        drivers.append("Bearish actors dominate")

    if str(token.get("regime")) == "distribution":
        score += 0.20
        drivers.append("Token regime distribution")

    if scores.get("smart_money_score", 50) < 45:
        score += 0.15
        drivers.append("Smart money weak or negative")

    if cex.get("inventory_state") == "growing":
        score += 0.10
        drivers.append("Exchange inventory growing — supply accumulating")

    inv = ["Smart money conviction rises sharply", "Exchange outflows accelerate"]

    return {"type": "bear_trend", "confidence": round(_clamp01(score), 3), "drivers": drivers, "invalidation": inv}


def _detect_accumulation(cex, sm, ent, token, scores):
    score = 0.0
    drivers = []

    conviction = sm.get("conviction", 0)
    if conviction >= 45:
        score += 0.20
        drivers.append(f"Smart money accumulation (conviction {conviction}%)")

    if cex.get("inventory_state") == "shrinking":
        score += 0.20
        drivers.append("Exchange inventory shrinking — outflows dominant")

    accum = ent.get("accumulation_actors", 0)
    if accum >= 2:
        score += 0.15
        drivers.append(f"{accum} entities in accumulation mode")

    if str(token.get("regime")) == "accumulation":
        score += 0.15
        drivers.append("Token positioning constructive")

    if cex.get("stablecoin_bias") == "buying_power":
        score += 0.10
        drivers.append("Stablecoin buying power present")

    inv = ["Exchange deposits accelerate", "Bearish actor pressure rises", "Token regime shifts bearish"]

    return {"type": "accumulation", "confidence": round(_clamp01(score), 3), "drivers": drivers, "invalidation": inv}


def _detect_distribution(cex, sm, ent, token, scores):
    score = 0.0
    drivers = []

    if cex.get("pressure_bias") == "bearish":
        score += 0.15
        drivers.append("Deposit pressure bearish")

    if cex.get("inventory_state") == "growing":
        score += 0.15
        drivers.append("Exchange inventory growing")

    bearish = ent.get("bearish_actors", 0)
    if bearish >= 1:
        score += 0.15
        drivers.append(f"{bearish} bearish entities active")

    if str(token.get("regime")) == "distribution":
        score += 0.20
        drivers.append("Token distribution regime")

    if sm.get("conviction", 50) < 40:
        score += 0.10
        drivers.append("Smart money conviction weak")

    inv = ["Smart money inflow reverses trend", "Entity accumulation resumes"]

    return {"type": "distribution", "confidence": round(_clamp01(score), 3), "drivers": drivers, "invalidation": inv}


def _detect_rotation(cex, sm, ent, token, scores):
    score = 0.0
    drivers = []

    pattern = str(token.get("pattern", ""))
    if "rotation" in pattern or "diverge" in pattern:
        score += 0.25
        drivers.append("Token divergence / rotation pattern")

    lp = ent.get("lp_actors", 0)
    if lp >= 2:
        score += 0.15
        drivers.append(f"{lp} liquidity providers active — capital rotating")

    conv = sm.get("conviction", 50)
    if 35 <= conv <= 65:
        score += 0.10
        drivers.append("No strong directional conviction")

    score_vals = [scores.get(f"{m}_score", 50) for m in ["smart_money", "cex", "entities", "token"]]
    if max(score_vals) - min(score_vals) > 25:
        score += 0.15
        drivers.append("Module scores diverging — mixed signals")

    inv = ["Strong directional signal from multiple modules"]

    return {"type": "rotation", "confidence": round(_clamp01(score), 3), "drivers": drivers, "invalidation": inv}


def _detect_neutral_chop(cex, sm, ent, token, scores):
    score = 0.0
    drivers = []

    composite = scores.get("composite", 50)
    if 42 <= composite <= 58:
        score += 0.25
        drivers.append(f"Composite in neutral zone ({composite})")

    conv = sm.get("conviction", 50)
    if 40 <= conv <= 60:
        score += 0.15
        drivers.append("No strong smart money conviction")

    if ent.get("pressure_balance") == "neutral":
        score += 0.15
        drivers.append("Entity pressure balanced / neutral")

    shock = str(cex.get("liquidity_shock", "neutral"))
    if shock == "neutral":
        score += 0.10
        drivers.append("No liquidity shock")

    inv = ["Any module breaks strongly directional"]

    return {"type": "neutral_chop", "confidence": round(_clamp01(score), 3), "drivers": drivers, "invalidation": inv}


# ─── Main Regime Selector ───

def detect_regime(context: dict) -> dict:
    """
    Detect market regime from context.
    context must contain: cex, smart_money, entities_summary, token, scores
    """
    cex = context.get("cex", {})
    sm = context.get("smart_money", {})
    ent = context.get("entities_summary", {})
    token = context.get("token", {})
    scores = context.get("scores", {})

    candidates = [
        _detect_bull_trend(cex, sm, ent, token, scores),
        _detect_bear_trend(cex, sm, ent, token, scores),
        _detect_accumulation(cex, sm, ent, token, scores),
        _detect_distribution(cex, sm, ent, token, scores),
        _detect_rotation(cex, sm, ent, token, scores),
        _detect_neutral_chop(cex, sm, ent, token, scores),
    ]

    # Filter and sort by confidence
    valid = [c for c in candidates if c["confidence"] >= 0.15]
    valid.sort(key=lambda r: -r["confidence"])

    if not valid:
        return {
            "primary": {
                "type": "neutral_chop",
                "confidence": 0.30,
                "status": "active",
                "drivers": ["Insufficient signal strength to classify regime"],
                "invalidation": ["Any module breaks directional"],
            },
            "secondary": [],
        }

    primary = valid[0]
    primary["status"] = _status(primary["confidence"])

    secondary = []
    for c in valid[1:3]:
        secondary.append({
            "type": c["type"],
            "confidence": c["confidence"],
            "status": _status(c["confidence"]),
        })

    return {
        "primary": primary,
        "secondary": secondary,
    }
