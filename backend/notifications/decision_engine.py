"""
Decision Engine — computes BUY/SELL/WAIT/AVOID from multi-layer signals.

Combines:
  - Exchange forecasts (direction, move%, scenario strength)
  - ML Risk overlay
  - OnChain signals (whale flows)
  - Sentiment spikes
  - System drift

Output: DecisionSignal with score, decision, confidence, reasoning.
"""
import os
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING


def _get_db():
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME", "intelligence_engine")
    return MongoClient(mongo_url)[db_name]


def compute_decision(asset: str, horizon: str = "30D") -> dict:
    """
    Compute a decision signal for an asset.

    Returns:
        {
            asset, decision, confidence, score, horizon,
            reasoning: [...], components: {...}, timestamp
        }
    """
    db = _get_db()
    asset = asset.upper()

    score = 0.0
    reasoning = []
    components = {}

    # ── 1. Exchange Forecast ──
    exchange_score, exchange_reasons, exchange_data = _score_exchange(db, asset, horizon)
    score += exchange_score
    reasoning.extend(exchange_reasons)
    components["exchange"] = exchange_data

    # ── 2. ML Risk ──
    ml_score, ml_reasons, ml_data = _score_ml_risk(db, asset, horizon)
    score += ml_score
    reasoning.extend(ml_reasons)
    components["ml_risk"] = ml_data

    # ── 3. OnChain (whale activity) ──
    onchain_score, onchain_reasons, onchain_data = _score_onchain(db, asset)
    score += onchain_score
    reasoning.extend(onchain_reasons)
    components["onchain"] = onchain_data

    # ── 4. Sentiment ──
    sentiment_score, sentiment_reasons, sentiment_data = _score_sentiment(db, asset)
    score += sentiment_score
    reasoning.extend(sentiment_reasons)
    components["sentiment"] = sentiment_data

    # ── 5. Drift ──
    drift_score, drift_reasons, drift_data = _score_drift(db, asset)
    score += drift_score
    reasoning.extend(drift_reasons)
    components["drift"] = drift_data

    # ── 6. Divergence check ──
    div_score, div_reasons, div_data = _check_divergence(db, asset)
    score += div_score
    reasoning.extend(div_reasons)
    components["divergence"] = div_data

    # ── 7. Signal Fusion (Exchange + OnChain + Sentiment alignment) ──
    fusion, fusion_boost = _compute_fusion(components)
    score += fusion_boost
    if fusion["strength"] != "normal":
        reasoning.insert(0, f"SIGNAL FUSION: {fusion['alignedSignals']} sources → {fusion['direction']} ({fusion['strength']})")
    components["fusion"] = fusion

    # ── Decision mapping ──
    score = round(score, 2)
    decision = _map_decision(score)
    confidence = min(100, round(abs(score) * 15))

    # Decision type based on fusion
    decision_type = "NORMAL"
    if fusion["strength"] == "extreme":
        decision_type = "EXTREME"
    elif fusion["strength"] == "high":
        decision_type = "HIGH_CONVICTION"

    horizon_label = "short" if horizon == "24H" else "mid" if horizon == "7D" else "long"

    return {
        "asset": asset,
        "decision": decision,
        "decisionType": decision_type,
        "confidence": confidence,
        "score": score,
        "horizon": horizon_label,
        "horizonRaw": horizon,
        "reasoning": reasoning,
        "components": components,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _map_decision(score: float) -> str:
    if score >= 4:
        return "BUY"
    elif score <= -4:
        return "SELL"
    elif abs(score) < 2:
        return "WAIT"
    else:
        return "AVOID"


# ── Component Scorers ──

def _score_exchange(db, asset: str, horizon: str):
    """Score based on exchange forecast."""
    col = db["exchange_forecasts"]
    doc = col.find_one(
        {"asset": asset, "horizon": horizon},
        {"_id": 0},
        sort=[("createdAt", DESCENDING)],
    )
    if not doc:
        return 0, ["Exchange: no forecast data"], {"available": False}

    raw_direction = (doc.get("direction") or "NEUTRAL").upper()
    # Normalize: SHORT/DOWN → BEARISH, LONG/UP → BULLISH
    direction_map = {"SHORT": "BEARISH", "LONG": "BULLISH", "DOWN": "BEARISH", "UP": "BULLISH"}
    direction = direction_map.get(raw_direction, raw_direction)
    move_pct = float(doc.get("expectedMovePct", 0) or 0)
    confidence = float(doc.get("confidence", 0) or 0)
    scenarios = doc.get("scenarios") or {}

    score = 0
    reasons = []

    # Direction
    if direction == "BULLISH":
        score += 2
        reasons.append(f"Exchange: bullish {horizon}")
    elif direction == "BEARISH":
        score -= 2
        reasons.append(f"Exchange: bearish {horizon}")
    else:
        reasons.append(f"Exchange: neutral {horizon}")

    # Move magnitude
    score += move_pct * 1.5

    # Scenario strength (dominant probability vs uniform 0.33)
    if scenarios:
        probs = []
        for s in scenarios.values() if isinstance(scenarios, dict) else scenarios:
            p = s.get("probability", 0) if isinstance(s, dict) else 0
            probs.append(p)
        if probs:
            dominant = max(probs)
            if dominant > 0.5:
                boost = (dominant - 0.33) * 5
                score += boost if direction == "BULLISH" else -boost if direction == "BEARISH" else 0

    # Confidence weight
    if confidence < 0.3:
        score *= 0.5
        reasons.append(f"Low confidence ({confidence:.0%}) — signal weakened")

    data = {
        "available": True,
        "direction": direction,
        "movePct": move_pct,
        "confidence": confidence,
        "subsccore": round(score, 2),
    }
    return round(score, 2), reasons, data


def _score_ml_risk(db, asset: str, horizon: str):
    """Score based on ML risk overlay."""
    col = db["exchange_forecasts"]
    doc = col.find_one(
        {"asset": asset, "horizon": horizon},
        {"_id": 0, "audit": 1},
        sort=[("createdAt", DESCENDING)],
    )
    if not doc:
        return 0, [], {"available": False}

    audit = doc.get("audit") or {}
    ml = audit.get("ml") or {}
    risk_score = float(ml.get("risk_score", 0) or 0)

    score = 0
    reasons = []

    if risk_score > 0.7:
        score -= 3
        reasons.append(f"ML risk: very high ({risk_score:.2f})")
    elif risk_score > 0.5:
        score -= 1.5
        reasons.append(f"ML risk: elevated ({risk_score:.2f})")
    elif risk_score > 0.3:
        score -= 0.5

    return round(score, 2), reasons, {"available": True, "riskScore": risk_score, "subsccore": round(score, 2)}


def _score_onchain(db, asset: str):
    """Score based on recent OnChain whale events."""
    col = db["notification_events"]
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    events = list(col.find(
        {"type": {"$in": ["onchain.whale.transfer", "onchain.smart_money.entry"]},
         "asset": asset, "timestamp": {"$gte": cutoff}},
        {"_id": 0, "payload": 1, "type": 1},
    ).sort("timestamp", -1).limit(5))

    if not events:
        return 0, [], {"available": False, "recentEvents": 0}

    score = 0
    reasons = []

    for e in events:
        p = e.get("payload", {})
        direction = p.get("direction", "")
        if direction == "inflow":
            score -= 1.5
        elif direction == "outflow":
            score += 1.5

    # Cap onchain influence
    score = max(-3, min(3, score))

    if score < 0:
        reasons.append(f"OnChain: whale inflow detected ({len(events)} events)")
    elif score > 0:
        reasons.append(f"OnChain: whale outflow detected ({len(events)} events)")

    return round(score, 2), reasons, {"available": True, "recentEvents": len(events), "subsccore": round(score, 2)}


def _score_sentiment(db, asset: str):
    """Score based on recent sentiment events."""
    col = db["notification_events"]
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()

    events = list(col.find(
        {"type": "sentiment.spike", "asset": asset, "timestamp": {"$gte": cutoff}},
        {"_id": 0, "payload": 1},
    ).sort("timestamp", -1).limit(3))

    if not events:
        return 0, [], {"available": False}

    total_delta = 0
    for e in events:
        delta = float(e.get("payload", {}).get("delta", 0))
        total_delta += delta

    score = 0
    reasons = []

    if total_delta > 0.3:
        score += 1.5
        reasons.append(f"Sentiment: bullish momentum (delta: +{total_delta:.2f})")
    elif total_delta < -0.3:
        score -= 1.5
        reasons.append(f"Sentiment: bearish momentum (delta: {total_delta:.2f})")

    return round(score, 2), reasons, {"available": True, "totalDelta": round(total_delta, 3), "subsccore": round(score, 2)}


def _score_drift(db, asset: str):
    """Score based on system drift signals."""
    col = db["notification_events"]
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()

    event = col.find_one(
        {"type": "exchange.drift.warning", "timestamp": {"$gte": cutoff}},
        {"_id": 0, "payload": 1},
        sort=[("timestamp", -1)],
    )

    if not event:
        return 0, [], {"available": False}

    drift_val = float(event.get("payload", {}).get("driftScore", 0))
    score = 0
    reasons = []

    if drift_val > 0.6:
        score -= 2
        reasons.append(f"Drift: high ({drift_val:.2f}) — predictions less reliable")
    elif drift_val > 0.4:
        score -= 1
        reasons.append(f"Drift: moderate ({drift_val:.2f})")

    return round(score, 2), reasons, {"available": True, "driftScore": drift_val, "subsccore": round(score, 2)}


def _check_divergence(db, asset: str):
    """Check if short and long-term forecasts disagree."""
    col = db["exchange_forecasts"]

    d7_doc = col.find_one(
        {"asset": asset, "horizon": "7D"}, {"_id": 0, "direction": 1},
        sort=[("createdAt", DESCENDING)]
    )
    d30_doc = col.find_one(
        {"asset": asset, "horizon": "30D"}, {"_id": 0, "direction": 1},
        sort=[("createdAt", DESCENDING)]
    )

    d7 = (d7_doc.get("direction", "") if d7_doc else "").upper()
    d30 = (d30_doc.get("direction", "") if d30_doc else "").upper()

    if d7 and d30 and d7 != "NEUTRAL" and d30 != "NEUTRAL" and d7 != d30:
        return -1, [f"Divergence: 7D={d7} vs 30D={d30} — conflicting signals"], {
            "detected": True, "7D": d7, "30D": d30
        }

    return 0, [], {"detected": False}


def _compute_fusion(components: dict) -> tuple:
    """
    Signal Fusion: checks if Exchange + OnChain + Sentiment align.
    Only these 3 sources participate. ML/Drift are penalties, not signals.

    Returns: (fusion_dict, score_boost)
    """
    directions = []

    # Exchange direction
    ex = components.get("exchange", {})
    if ex.get("available"):
        d = ex.get("direction", "NEUTRAL").upper()
        if d == "BULLISH":
            directions.append("bullish")
        elif d == "BEARISH":
            directions.append("bearish")

    # OnChain direction (inflow = bearish, outflow = bullish)
    oc = components.get("onchain", {})
    if oc.get("available") and oc.get("recentEvents", 0) > 0:
        sub = oc.get("subsccore", 0)
        if sub < 0:
            directions.append("bearish")
        elif sub > 0:
            directions.append("bullish")

    # Sentiment direction
    st = components.get("sentiment", {})
    if st.get("available"):
        delta = st.get("totalDelta", 0)
        if delta > 0.15:
            directions.append("bullish")
        elif delta < -0.15:
            directions.append("bearish")

    # Count alignment
    bullish = directions.count("bullish")
    bearish = directions.count("bearish")
    total = len(directions)

    aligned = max(bullish, bearish)
    direction = "bullish" if bullish > bearish else "bearish" if bearish > bullish else "neutral"

    # Determine strength
    if aligned >= 3:
        strength = "extreme"
        boost = 4 if direction == "bullish" else -4
    elif aligned >= 2:
        strength = "high"
        boost = 2 if direction == "bullish" else -2
    else:
        strength = "normal"
        boost = 0

    # Conflict penalty: equal opposing signals
    if bullish >= 1 and bearish >= 1 and bullish == bearish:
        boost = -1
        strength = "conflicted"
        direction = "mixed"

    fusion = {
        "alignedSignals": aligned,
        "direction": direction,
        "strength": strength,
        "sources": directions,
    }
    return fusion, round(boost, 2)
