"""
Edge Builder — Money Layer
==========================
Converts Decision Engine output into edge signals.
Edge = model_probability - market_probability

Sources:
  - prediction_markets collection (primary, when available)
  - Bridge markets (synthetic from decision_history when prediction_markets empty)
  - Decision Engine (model probability)
"""

from datetime import datetime, timezone


def _clamp(x, lo=0.0, hi=1.0):
    return max(min(x, hi), lo)


def _confidence_tier(confidence: float) -> str:
    """Map confidence to tier label."""
    if confidence >= 0.80:
        return "EXTREME"
    if confidence >= 0.65:
        return "HIGH_CONVICTION"
    return "STANDARD"


def _ttl_hours(edge_val: float, confidence: float) -> int:
    """Calculate edge TTL in hours."""
    base = 12
    if abs(edge_val) > 0.20:
        base = 6
    elif abs(edge_val) > 0.15:
        base = 8
    if confidence >= 0.80:
        base = max(base - 2, 4)
    elif confidence < 0.55:
        base = min(base + 6, 24)
    return base


def _decision_to_probability(decision_doc: dict) -> float:
    """Convert decision action + confidence into a probability."""
    action = decision_doc.get("decision", "WAIT")
    confidence = float(decision_doc.get("confidence", 50)) / 100.0
    if action == "BUY":
        return _clamp(0.5 + confidence * 0.45)
    if action == "SELL":
        return _clamp(0.5 - confidence * 0.45)
    return 0.5


def _build_reason(decision_doc: dict) -> list:
    """Extract human-readable reasons from decision reasoning."""
    reasons = []
    action = decision_doc.get("decision", "WAIT")
    fusion = decision_doc.get("fusion", {})
    raw_reasoning = decision_doc.get("reasoning", [])

    if action == "SELL":
        reasons.append("Model indicates downside bias")
    elif action == "BUY":
        reasons.append("Model indicates upside bias")
    else:
        reasons.append("Model sees no clear direction")

    strength = fusion.get("strength", "normal")
    aligned = fusion.get("alignedSignals", 0)
    if aligned >= 2:
        reasons.append(f"{aligned} signal sources aligned {fusion.get('direction', 'neutral')}")
    if strength == "high":
        reasons.append("High conviction from signal fusion")

    for r in raw_reasoning:
        r_lower = r.lower()
        if "whale inflow" in r_lower:
            reasons.append("Whale inflows suggest distribution")
            break
        if "whale outflow" in r_lower:
            reasons.append("Whale outflows suggest accumulation")
            break

    for r in raw_reasoning:
        if "sentiment" in r.lower() and "bearish" in r.lower():
            reasons.append("Sentiment weakening")
            break
        if "sentiment" in r.lower() and "bullish" in r.lower():
            reasons.append("Sentiment strengthening")
            break

    for r in raw_reasoning:
        if "ml risk" in r.lower() and ("high" in r.lower() or "very high" in r.lower()):
            reasons.append("Elevated model uncertainty")
            break

    return reasons[:5]


def _generate_question(asset: str, entry_price: float, action: str) -> str:
    """Generate a market-style question from a decision."""
    if not entry_price:
        return f"Will {asset} move significantly?"
    if action in ("BUY", "LONG"):
        target = round(entry_price * 1.05, -1 if entry_price > 100 else 0)
        return f"{asset} above ${_fmt_price(target)} this week?"
    elif action in ("SELL", "SHORT"):
        target = round(entry_price * 0.95, -1 if entry_price > 100 else 0)
        return f"{asset} below ${_fmt_price(target)} this week?"
    return f"{asset} stays range-bound?"


def _fmt_price(v):
    if v >= 10000:
        return f"{v / 1000:.0f}k"
    if v >= 1000:
        return f"{v / 1000:.1f}k"
    return f"{v:.0f}"


def _market_prob_bridge(asset: str, action: str) -> float:
    """
    Synthetic market probability — represents what "the crowd" would price.
    Slightly contrarian to the model to create edge opportunities.
    """
    base = {
        "BTC": 0.55,
        "ETH": 0.52,
        "SOL": 0.50,
    }.get(asset, 0.50)

    if action in ("BUY", "LONG"):
        return _clamp(base - 0.05)
    if action in ("SELL", "SHORT"):
        return _clamp(base + 0.08)
    return base


async def build_edge(db) -> dict:
    """Build edge data from prediction_markets or bridge from decision_history."""

    pm_count = await db.prediction_markets.count_documents({})

    if pm_count > 0:
        return await _build_from_prediction_markets(db)

    return await _build_from_bridge(db)


async def _build_from_prediction_markets(db) -> dict:
    """Build edge from real prediction_markets collection with Priority v2 scoring."""
    from miniapp.edge_priority import calculate_priority, priority_label

    cursor = db.prediction_markets.find({}, {"_id": 0}).sort("updatedAt", -1).limit(30)
    edges = []

    # Pre-fetch latest decisions for priority scoring
    decision_cache = {}
    for asset in ["BTC", "ETH", "SOL"]:
        dec = await db.decision_history.find_one(
            {"asset": asset}, {"_id": 0},
            sort=[("timestamp", -1)],
        )
        if dec:
            decision_cache[asset] = dec

    async for doc in cursor:
        mp = float(doc.get("yes_price", 0.5))
        mdl = float(doc.get("model_prob", 0.5))
        edge = round(mdl - mp, 4)
        if abs(edge) < 0.05:
            continue
        direction = "BUY" if edge > 0 else "SELL"
        asset = doc.get("asset", "")
        confidence = float(doc.get("decision_confidence", 50)) / 100.0

        reasons = []
        action = doc.get("decision_action", "")
        if action in ("BUY", "SELL"):
            reasons.append(f"Model predicts {action.lower()} bias")
        if abs(edge) > 0.15:
            reasons.append("Large divergence between model and market")
        elif abs(edge) > 0.10:
            reasons.append("Moderate model-market divergence")
        threshold = doc.get("threshold", 0)
        current = doc.get("current_price", 0)
        if threshold and current:
            dist = abs(threshold - current) / current * 100
            reasons.append(f"Threshold {_fmt_price(threshold)} is {dist:.1f}% from current")
        if doc.get("volume", 0) > 100000:
            reasons.append("High volume market")
        reasons.append(f"Market prices at {int(mp*100)}%, model at {int(mdl*100)}%")

        # Priority v2 scoring
        dec = decision_cache.get(asset, {})
        decision_type = dec.get("decisionType", "NORMAL")
        fusion = dec.get("fusion", {})
        timestamp = dec.get("timestamp", doc.get("updatedAt", ""))

        pscore = calculate_priority(
            edge=edge,
            confidence=confidence,
            fusion=fusion,
            edge_direction=direction,
            timestamp=timestamp,
            decision_type=decision_type,
        )

        edges.append({
            "asset": asset,
            "question": doc.get("question", ""),
            "marketProbability": round(mp, 3),
            "modelProbability": round(mdl, 3),
            "edge": round(edge, 3),
            "direction": direction,
            "confidence": round(confidence, 2),
            "confidenceTier": _confidence_tier(confidence),
            "ttlHours": _ttl_hours(edge, confidence),
            "priorityScore": pscore,
            "priorityLabel": priority_label(pscore),
            "decisionType": decision_type,
            "reason": reasons[:5],
            "volume": doc.get("volume", 0),
            "source": "polymarket",
        })

    # Sort by priority score (v2)
    edges.sort(key=lambda x: x["priorityScore"], reverse=True)
    if not edges:
        return _no_edge_response()

    return {"status": "ACTIVE", "best": edges[0], "markets": edges[:10], "source": "polymarket"}


async def _build_from_bridge(db) -> dict:
    """Build edge from decision_history when no prediction_markets data."""
    from miniapp.edge_priority import calculate_priority, priority_label

    assets = ["BTC", "ETH", "SOL"]
    edges = []

    for asset in assets:
        latest = await db.decision_history.find_one(
            {"asset": asset, "decision": {"$in": ["BUY", "SELL"]}, "status": "pending"},
            {"_id": 0},
            sort=[("timestamp", -1)],
        )
        if not latest:
            latest = await db.decision_history.find_one(
                {"asset": asset, "decision": {"$in": ["BUY", "SELL"]}},
                {"_id": 0},
                sort=[("timestamp", -1)],
            )
        if not latest:
            latest = await db.decision_history.find_one(
                {"asset": asset},
                {"_id": 0},
                sort=[("timestamp", -1)],
            )
        if not latest:
            continue

        action = latest.get("decision", "WAIT")
        entry_price = float(latest.get("entryPrice", 0))
        confidence_raw = float(latest.get("confidence", 50)) / 100.0
        decision_type = latest.get("decisionType", "NORMAL")
        fusion = latest.get("fusion", {})
        timestamp = latest.get("timestamp", "")

        if action in ("WAIT", "AVOID"):
            model_prob = 0.5
            market_prob = _market_prob_bridge(asset, "NEUTRAL")
            edge = round(model_prob - market_prob, 3)
            if abs(edge) < 0.03:
                edge = 0.0

            edges.append({
                "asset": asset,
                "question": f"{asset} direction unclear",
                "marketProbability": round(market_prob, 3),
                "modelProbability": round(model_prob, 3),
                "edge": edge,
                "direction": "WAIT",
                "confidence": round(confidence_raw, 2),
                "reason": ["Model has no directional conviction", "Low edge environment — waiting for signal alignment"],
                "status": "watching",
                "priorityScore": 0.0,
                "priorityLabel": "WATCHING",
            })
            continue

        model_prob = _decision_to_probability(latest)
        market_prob = _market_prob_bridge(asset, action)
        edge = round(model_prob - market_prob, 3)
        direction = "BUY" if edge > 0 else "SELL"

        question = _generate_question(asset, entry_price, action)
        reasons = _build_reason(latest)

        pscore = calculate_priority(
            edge=edge, confidence=confidence_raw, fusion=fusion,
            edge_direction=direction, timestamp=timestamp,
            decision_type=decision_type,
        )

        edges.append({
            "asset": asset,
            "question": question,
            "marketProbability": round(market_prob, 3),
            "modelProbability": round(model_prob, 3),
            "edge": edge,
            "direction": direction,
            "confidence": round(confidence_raw, 2),
            "confidenceTier": _confidence_tier(confidence_raw),
            "ttlHours": _ttl_hours(edge, confidence_raw),
            "priorityScore": pscore,
            "priorityLabel": priority_label(pscore),
            "decisionType": decision_type,
            "reason": reasons,
        })

    # Sort: active edges by priority score (v2), then watching
    active = [e for e in edges if e.get("status") != "watching"]
    watching = [e for e in edges if e.get("status") == "watching"]
    active.sort(key=lambda x: x.get("priorityScore", 0), reverse=True)

    all_edges = active + watching

    if not active:
        return {
            "status": "NO_EDGE",
            "best": None,
            "markets": watching,
            "reason": "No active markets with sufficient divergence",
            "explanation": "Edge appears when model prediction and market price significantly diverge. All tracked assets are currently in WAIT mode.",
        }

    return {"status": "ACTIVE", "best": active[0], "markets": all_edges[:10]}


def _no_edge_response():
    return {
        "status": "NO_EDGE",
        "best": None,
        "markets": [],
        "reason": "No active markets with sufficient divergence",
        "explanation": "Edge appears when model prediction and market price significantly diverge. Check back when new signals arrive.",
    }
