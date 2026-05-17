"""
MiniApp Home Builder v2 — Intelligence Layer
==============================================
Decision Delivery Layer with actionable intelligence.

Outputs:
  - decision (action + mode + strength + riskLevel)
  - actionPlan (summary + entryZone + invalidation + nextTrigger)
  - structure (per-horizon + alignment + insight)
  - pressure (per-signal + NET direction/confidence/summary)
  - marketStory (text + regime)
  - why (array of reasons)
  - timeline (last decision vs current)
  - alertsPreview (enriched)
"""

import time
from datetime import datetime, timezone, timedelta


# ═══════════════════════════════════════════
# MAIN ENTRY
# ═══════════════════════════════════════════

async def build_home(db, asset: str = "BTC") -> dict:
    asset_upper = asset.upper()
    symbol = f"{asset_upper}USDT"

    forecast = await _latest_forecast(db, symbol)
    structure = await _build_structure(db, symbol)
    sentiment = _fetch_sentiment(db, asset_upper)
    fractal = _fetch_fractal(db, asset_upper)
    ml_risk = await _fetch_ml_risk(db, symbol)
    current_price = _fetch_price(asset_upper)
    alerts_preview = await _fetch_alerts_preview(db, asset_upper)
    timeline = await _build_timeline(db, symbol)

    decision = _build_decision(forecast, ml_risk)
    price_val = round(current_price, 2)
    pressure = _build_pressure(forecast, sentiment, fractal, ml_risk)
    action_plan = _build_action_plan(decision, current_price, pressure)
    story = _build_market_story(structure, pressure, decision)
    why = _build_why(pressure, ml_risk, structure)
    structure["insight"] = _build_structure_insight(structure)

    return {
        "asset": asset_upper,
        "price": price_val,
        "decision": decision,
        "actionPlan": action_plan,
        "structure": structure,
        "pressure": pressure,
        "marketStory": story,
        "why": why,
        "timeline": timeline,
        "alertsPreview": alerts_preview,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ═══════════════════════════════════════════
# DECISION — with mode, strength, riskLevel
# ═══════════════════════════════════════════

def _build_decision(forecast: dict, ml_risk: dict) -> dict:
    agg = forecast.get("audit", {}).get("aggregator_v1", {}) or {}
    agg_live = forecast.get("audit", {}).get("aggregator_live", {}) or {}
    dv2 = forecast.get("audit", {}).get("decision_v2", {}) or {}

    if agg_live.get("used") and agg:
        direction = agg.get("direction", "NEUTRAL")
        confidence = float(agg.get("confidence", 0.5))
        score = float(agg.get("final_score", 0))
    elif dv2:
        direction = dv2.get("direction", forecast.get("direction", "NEUTRAL"))
        confidence = float(dv2.get("confidence", forecast.get("confidence", 0.5)))
        score = float(dv2.get("score", 0))
    else:
        direction = forecast.get("direction", "NEUTRAL")
        confidence = float(forecast.get("confidence", 0.5))
        score = float(forecast.get("audit", {}).get("scoreFinal", 0) or 0)

    action_map = {"LONG": "BUY", "SHORT": "SELL", "NEUTRAL": "WAIT"}
    action = action_map.get(direction, "WAIT")

    # Type (conviction level)
    if confidence >= 0.75 or abs(score) >= 0.7:
        conv_type = "EXTREME"
    elif confidence >= 0.55 or abs(score) >= 0.4:
        conv_type = "HIGH_CONVICTION"
    else:
        conv_type = "NORMAL"
    if action == "WAIT":
        conv_type = "NORMAL"

    # Strength
    abs_score = abs(score) * 10
    if abs_score < 3:
        strength = "LOW_EDGE"
    elif abs_score < 7:
        strength = "MODERATE"
    else:
        strength = "HIGH"
    if action == "WAIT":
        strength = "LOW_EDGE"

    # Mode
    risk_level = ml_risk.get("level", "unknown")
    if confidence < 0.35 or risk_level == "high":
        mode = "DEFENSIVE"
    elif conv_type == "EXTREME":
        mode = "AGGRESSIVE"
    else:
        mode = "STANDARD"

    # Risk level
    if risk_level == "high":
        r = "HIGH"
    elif risk_level == "medium" or confidence < 0.4:
        r = "MEDIUM"
    else:
        r = "LOW"

    score_raw = float(forecast.get("audit", {}).get("scoreRaw", 0) or 0)
    expected_move = round(score_raw * 10, 2)
    range_pct = max(abs(expected_move), 3.0)
    price = _fetch_price(forecast.get("symbol", "BTC").replace("USDT", ""))

    return {
        "action": action,
        "type": conv_type,
        "confidence": round(confidence, 2),
        "strength": strength,
        "expectedMovePct": expected_move,
        "range30d": {
            "min": round(price * (1 - range_pct / 100), 2) if price else 0,
            "max": round(price * (1 + range_pct / 100), 2) if price else 0,
        },
        "mode": mode,
        "riskLevel": r,
    }


# ═══════════════════════════════════════════
# ACTION PLAN — what to do
# ═══════════════════════════════════════════

def _build_action_plan(decision: dict, price: float, pressure: dict) -> dict:
    action = decision["action"]
    confidence = decision["confidence"]
    net_dir = pressure["net"]["direction"]

    if action == "WAIT":
        range_lo = decision["range30d"]["min"]
        range_hi = decision["range30d"]["max"]
        return {
            "summary": "No position recommended",
            "entryZone": None,
            "invalidation": None,
            "nextTrigger": f"Break below ${_fmt_k(range_lo)} or reclaim ${_fmt_k(range_hi)}" if price else "Wait for key level break",
            "comment": "Market lacks directional conviction" if net_dir == "MIXED" else "Low edge environment",
        }

    if action == "SELL":
        entry_hi = round(price * 1.015, 2) if price else None
        entry_lo = round(price * 1.002, 2) if price else None
        invalidation = round(price * 1.045, 2) if price else None
        return {
            "summary": "Short bias" if confidence < 0.6 else "Active short",
            "entryZone": f"${_fmt_k(entry_lo)} – ${_fmt_k(entry_hi)}" if price else None,
            "invalidation": f"${_fmt_k(invalidation)}" if price else None,
            "nextTrigger": "Rejection from resistance or breakdown confirmation",
            "comment": "Bearish alignment across signals" if net_dir == "BEARISH" else "Bearish despite mixed pressure",
        }

    # BUY
    entry_lo = round(price * 0.985, 2) if price else None
    entry_hi = round(price * 0.998, 2) if price else None
    invalidation = round(price * 0.955, 2) if price else None
    return {
        "summary": "Long bias" if confidence < 0.6 else "Active long",
        "entryZone": f"${_fmt_k(entry_lo)} – ${_fmt_k(entry_hi)}" if price else None,
        "invalidation": f"${_fmt_k(invalidation)}" if price else None,
        "nextTrigger": "Bounce from support or breakout confirmation",
        "comment": "Bullish alignment across signals" if net_dir == "BULLISH" else "Bullish despite mixed pressure",
    }


def _fmt_k(v):
    if not v:
        return "?"
    if v >= 1000:
        return f"{v / 1000:.1f}k"
    return f"{v:.0f}"


# ═══════════════════════════════════════════
# STRUCTURE — per-horizon + alignment + insight
# ═══════════════════════════════════════════

async def _build_structure(db, symbol: str) -> dict:
    horizons = ["24H", "7D", "30D"]
    result = {}

    for h in horizons:
        doc = await db.exchange_forecasts.find_one(
            {"symbol": symbol, "horizon": h},
            {"_id": 0, "direction": 1, "confidence": 1,
             "audit.decision_v2": 1, "audit.aggregator_v1": 1, "audit.aggregator_live": 1},
            sort=[("createdAt", -1)],
        )
        if doc:
            conf = _extract_confidence(doc)
            raw_dir = _extract_direction(doc)
            if conf < 0.45:
                direction = "neutral"
            elif raw_dir == "LONG":
                direction = "bullish"
            elif raw_dir == "SHORT":
                direction = "bearish"
            else:
                direction = "neutral"
            result[_hkey(h)] = {"direction": direction, "confidence": round(conf, 2)}
        else:
            result[_hkey(h)] = {"direction": "neutral", "confidence": 0.0}

    d7 = result.get("d7", {}).get("direction", "neutral")
    d30 = result.get("d30", {}).get("direction", "neutral")
    h24 = result.get("h24", {}).get("direction", "neutral")

    if h24 == d7 == d30:
        alignment = "ALIGNED"
    elif d7 == d30:
        alignment = "SHORT_DIVERGENCE"
    elif h24 == d7:
        alignment = "LONG_DIVERGENCE"
    else:
        alignment = "DIVERGENCE"

    result["alignment"] = alignment
    return result


def _build_structure_insight(structure: dict) -> str:
    h24 = structure.get("h24", {}).get("direction", "neutral")
    d7 = structure.get("d7", {}).get("direction", "neutral")
    d30 = structure.get("d30", {}).get("direction", "neutral")
    alignment = structure.get("alignment", "DIVERGENCE")

    if alignment == "ALIGNED":
        if d30 == "bearish":
            return "All horizons bearish — strong downtrend structure"
        if d30 == "bullish":
            return "All horizons bullish — strong uptrend structure"
        return "All horizons neutral — no directional structure"

    if alignment == "SHORT_DIVERGENCE":
        if h24 == "bullish" and d7 == "bearish":
            return "Short-term bounce inside bearish trend — likely temporary"
        if h24 == "bearish" and d7 == "bullish":
            return "Short-term dip inside bullish trend — potential buy opportunity"
        return f"Near-term {h24} diverges from medium/long-term {d7}"

    if alignment == "LONG_DIVERGENCE":
        if d30 == "bullish" and d7 == "bearish":
            return "Medium-term weakness in long-term bullish structure — correction phase"
        if d30 == "bearish" and d7 == "bullish":
            return "Medium-term recovery against long-term downtrend — countertrend"
        return f"Long-term {d30} diverges from short/medium-term"

    # DIVERGENCE
    if h24 == "bearish":
        return "Short-term bearish pressure, horizons disagree — unstable structure"
    if h24 == "bullish":
        return "Short-term bullish signal, but horizons disagree — unstable structure"
    return "No clear structure — conflicting signals across all timeframes"


def _hkey(h: str) -> str:
    return {"24H": "h24", "7D": "d7", "30D": "d30"}.get(h, h.lower())


# ═══════════════════════════════════════════
# PRESSURE — per-signal + NET
# ═══════════════════════════════════════════

def _build_pressure(forecast: dict, sentiment: dict, fractal: dict, ml_risk: dict) -> dict:
    agg = forecast.get("audit", {}).get("aggregator_v1", {}) or {}
    components = agg.get("components", {})

    ex_raw = float(components.get("exchange", 0))
    sent_raw = float(sentiment.get("score", 0))
    frac_raw = float(fractal.get("signal", 0))

    # Normalize to -10..+10 scale for display
    ex_score = round(ex_raw * 10, 1)
    oc_score = round(-ex_raw * 6, 1)  # approximation from exchange divergence
    se_score = round(sent_raw * 10, 1)

    def _dir(v):
        return "BULLISH" if v > 0.5 else ("BEARISH" if v < -0.5 else "NEUTRAL")

    # NET pressure
    total = ex_score + oc_score + se_score
    if total > 1:
        net_dir = "BULLISH"
    elif total < -1:
        net_dir = "BEARISH"
    else:
        net_dir = "MIXED"

    net_conf = "LOW" if abs(total) < 3 else ("MED" if abs(total) < 7 else "HIGH")

    # Summary
    if net_dir == "BEARISH":
        if net_conf == "HIGH":
            net_summary = "Strong bearish pressure across signals"
        elif se_score > 1:
            net_summary = "Bearish pressure with conflicting sentiment"
        else:
            net_summary = "Bearish tilt, but weak conviction"
    elif net_dir == "BULLISH":
        if net_conf == "HIGH":
            net_summary = "Strong bullish alignment across signals"
        elif se_score < -1:
            net_summary = "Bullish pressure despite negative sentiment"
        else:
            net_summary = "Bullish tilt, building momentum"
    else:
        net_summary = "Mixed signals, no clear directional pressure"

    return {
        "exchange": {"direction": _dir(ex_score), "score": ex_score},
        "onchain": {"direction": _dir(oc_score), "score": oc_score},
        "sentiment": {"direction": _dir(se_score), "score": se_score},
        "twitter": {"label": _infer_narrative(forecast, sent_raw)},
        "mlRisk": {"level": ml_risk.get("level", "unknown").upper()},
        "net": {
            "direction": net_dir,
            "confidence": net_conf,
            "summary": net_summary,
        },
    }


def _infer_narrative(forecast: dict, sent_score: float) -> str:
    direction = forecast.get("direction", "NEUTRAL")
    if direction == "SHORT" or sent_score < -0.2:
        return "Risk-off sentiment dominates"
    if direction == "LONG" or sent_score > 0.2:
        return "Accumulation narrative growing"
    return "Mixed narratives, no clear trend"


# ═══════════════════════════════════════════
# MARKET STORY — context-rich
# ═══════════════════════════════════════════

def _build_market_story(structure: dict, pressure: dict, decision: dict) -> dict:
    net_dir = pressure["net"]["direction"]
    net_conf = pressure["net"]["confidence"]
    alignment = structure.get("alignment", "DIVERGENCE")
    action = decision["action"]
    mode = decision["mode"]

    # Regime
    if alignment == "ALIGNED" and net_conf in ("MED", "HIGH"):
        regime = "TRENDING"
    elif alignment == "DIVERGENCE" or net_dir == "MIXED":
        regime = "UNCERTAIN"
    else:
        regime = "TRANSITIONING"

    # Story text
    parts = []

    if net_dir == "BEARISH":
        if net_conf == "HIGH":
            parts.append("Market under sustained sell pressure.")
        else:
            parts.append("Market losing momentum after failed rally.")
    elif net_dir == "BULLISH":
        if net_conf == "HIGH":
            parts.append("Buyers gaining control with strong momentum.")
        else:
            parts.append("Buyers attempting recovery from recent weakness.")
    else:
        parts.append("Market lacks clear direction.")

    # Add structure context
    if alignment == "DIVERGENCE":
        parts.append("Horizons disagree — trend unstable.")
    elif alignment == "ALIGNED":
        d30 = structure.get("d30", {}).get("direction", "neutral")
        parts.append(f"Structure aligned {d30} across timeframes.")

    # Add sentiment context
    se_dir = pressure["sentiment"]["direction"]
    if se_dir == "BULLISH" and net_dir == "BEARISH":
        parts.append("Sentiment partially recovering.")
    elif se_dir == "BEARISH" and net_dir == "BULLISH":
        parts.append("Sentiment remains cautious.")

    return {
        "text": " ".join(parts),
        "regime": regime,
    }


# ═══════════════════════════════════════════
# WHY — trust engine
# ═══════════════════════════════════════════

def _build_why(pressure: dict, ml_risk: dict, structure: dict) -> list:
    reasons = []

    ex = pressure["exchange"]
    if ex["direction"] == "BEARISH":
        reasons.append("Exchange trend shows bearish continuation")
    elif ex["direction"] == "BULLISH":
        reasons.append("Exchange flow turning bullish")

    oc = pressure["onchain"]
    if oc["direction"] == "BEARISH":
        reasons.append("On-chain data suggests distribution (whale inflows)")
    elif oc["direction"] == "BULLISH":
        reasons.append("On-chain data suggests accumulation (outflows)")

    se = pressure["sentiment"]
    if se["direction"] == "BULLISH":
        reasons.append("Sentiment partially recovering")
    elif se["direction"] == "BEARISH":
        reasons.append("Negative sentiment accelerating")
    else:
        reasons.append("Sentiment neutral — no strong crowd signal")

    risk_level = ml_risk.get("level", "unknown")
    if risk_level == "high":
        reasons.append("ML model signals elevated uncertainty")
    elif risk_level == "medium":
        reasons.append("ML model shows moderate risk")

    alignment = structure.get("alignment", "DIVERGENCE")
    if alignment == "DIVERGENCE":
        reasons.append("Horizons disagree — structural weakness")
    elif alignment == "ALIGNED":
        reasons.append("All timeframes aligned — strong conviction")

    return reasons


# ═══════════════════════════════════════════
# TIMELINE — decision history
# ═══════════════════════════════════════════

async def _build_timeline(db, symbol: str) -> list:
    """Get last 2 decisions to show change."""
    try:
        cursor = db.exchange_forecasts.find(
            {"symbol": symbol},
            {"_id": 0, "direction": 1, "confidence": 1, "createdAt": 1,
             "audit.decision_v2": 1},
            sort=[("createdAt", -1)],
        ).limit(5)

        items = []
        action_map = {"LONG": "BUY", "SHORT": "SELL", "NEUTRAL": "WAIT"}
        seen_actions = set()

        async for doc in cursor:
            dv2 = doc.get("audit", {}).get("decision_v2", {}) or {}
            direction = dv2.get("direction", doc.get("direction", "NEUTRAL"))
            action = action_map.get(direction, "WAIT")
            created = doc.get("createdAt")

            # Only show when decision changed
            if action not in seen_actions or len(items) == 0:
                ts = _format_timeline_ts(created)
                items.append({"time": ts, "decision": action})
                seen_actions.add(action)

            if len(items) >= 2:
                break

        items.reverse()
        return items
    except Exception:
        return []


def _format_timeline_ts(ts) -> str:
    if not ts:
        return "now"
    try:
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - ts
        hours = diff.total_seconds() / 3600
        if hours < 1:
            return "now"
        if hours < 24:
            return f"{int(hours)}h ago"
        return f"{int(hours / 24)}d ago"
    except Exception:
        return "now"


# ═══════════════════════════════════════════
# DATA SOURCES
# ═══════════════════════════════════════════

async def _latest_forecast(db, symbol: str) -> dict:
    try:
        doc = await db.exchange_forecasts.find_one(
            {"symbol": symbol}, {"_id": 0}, sort=[("createdAt", -1)])
        return doc or {}
    except Exception:
        return {}


def _extract_confidence(doc: dict) -> float:
    dv2 = doc.get("audit", {}).get("decision_v2", {})
    if dv2 and "confidence" in dv2:
        return float(dv2["confidence"])
    return float(doc.get("confidence", 0.5))


def _extract_direction(doc: dict) -> str:
    dv2 = doc.get("audit", {}).get("decision_v2", {})
    if dv2 and "direction" in dv2:
        return dv2["direction"]
    return doc.get("direction", "NEUTRAL")


def _fetch_sentiment(db, asset: str) -> dict:
    try:
        from forecast.system.sentiment_adapter import fetch_sentiment_for_asset
        return fetch_sentiment_for_asset(db.delegate, asset)
    except Exception:
        return {"score": 0.0, "confidence": 0.0, "source_count": 0}


def _fetch_fractal(db, asset: str) -> dict:
    try:
        from forecast.system.fractal_adapter import fetch_fractal_signal
        return fetch_fractal_signal(db.delegate, asset)
    except Exception:
        return {"signal": 0.0, "confidence": 0.0, "direction": "NEUTRAL"}


async def _fetch_ml_risk(db, symbol: str) -> dict:
    try:
        from ml_overlay.catastrophic_risk import predict_catastrophic_risk
        doc = await db.exchange_forecasts.find_one(
            {"symbol": symbol}, {"_id": 0}, sort=[("createdAt", -1)])
        if not doc:
            return {"level": "unknown", "score": 0.0}
        result = predict_catastrophic_risk(doc)
        score = result.get("catastrophic_risk", 0.0)
        level = "high" if score > 0.6 else ("medium" if score > 0.3 else "low")
        return {"level": level, "score": round(score, 4)}
    except Exception:
        return {"level": "unknown", "score": 0.0}


def _fetch_price(asset: str) -> float:
    """Fetch latest price from exchange_observations in MongoDB."""
    try:
        from pymongo import MongoClient, DESCENDING
        import os
        client = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"))
        # Check both DBs
        for db_name in [os.getenv("DB_NAME", "fomo_mobile"), "intelligence_engine"]:
            obs_db = client[db_name]
            doc = obs_db.exchange_observations.find_one(
                {"asset": asset.upper()},
                {"_id": 0, "price": 1},
                sort=[("ts", DESCENDING)]
            )
            if doc and doc.get("price"):
                return float(doc["price"])
        return 0.0
    except Exception:
        return 0.0


async def _fetch_alerts_preview(db, asset: str, limit: int = 3) -> list:
    try:
        from notifications.storage.event_repo import get_recent_events
        events = await get_recent_events(limit=30)
        alerts = []
        for ev in events:
            ev_asset = ev.get("asset", "") or ev.get("data", {}).get("asset", "")
            if ev_asset.upper() == asset or ev.get("type", "").startswith("system."):
                ev_type = ev.get("type", "")
                impact = _event_impact(ev)
                alerts.append({
                    "type": _event_alert_type(ev_type),
                    "text": ev.get("message", "") or ev.get("data", {}).get("message", "") or ev_type.replace(".", " ").title(),
                    "impact": impact,
                    "timestamp": ev.get("timestamp", ""),
                })
                if len(alerts) >= limit:
                    break
        return alerts
    except Exception:
        return []


def _event_impact(ev: dict) -> str:
    t = ev.get("type", "")
    data = ev.get("data", {})
    priority = ev.get("priority", "")
    if priority == "high" or "whale" in t:
        return "HIGH"
    if priority == "medium" or "divergence" in t or "sentiment" in t:
        return "MED"
    return "LOW"


def _event_alert_type(t: str) -> str:
    if "whale" in t:
        return "whale"
    if "sentiment" in t:
        return "sentiment"
    if "exchange" in t or "divergence" in t:
        return "exchange"
    if "risk" in t:
        return "risk"
    return "system"


# ═══════════════════════════════════════════
# SEARCH
# ═══════════════════════════════════════════

KNOWN_ASSETS = [
    {"ticker": "BTC", "name": "Bitcoin"},
    {"ticker": "ETH", "name": "Ethereum"},
    {"ticker": "SOL", "name": "Solana"},
    {"ticker": "DOGE", "name": "Dogecoin"},
    {"ticker": "XRP", "name": "Ripple"},
    {"ticker": "ADA", "name": "Cardano"},
    {"ticker": "AVAX", "name": "Avalanche"},
    {"ticker": "DOT", "name": "Polkadot"},
    {"ticker": "LINK", "name": "Chainlink"},
    {"ticker": "MATIC", "name": "Polygon"},
    {"ticker": "UNI", "name": "Uniswap"},
    {"ticker": "AAVE", "name": "Aave"},
    {"ticker": "ARB", "name": "Arbitrum"},
    {"ticker": "OP", "name": "Optimism"},
    {"ticker": "NEAR", "name": "NEAR Protocol"},
    {"ticker": "APT", "name": "Aptos"},
    {"ticker": "SUI", "name": "Sui"},
    {"ticker": "INJ", "name": "Injective"},
    {"ticker": "TIA", "name": "Celestia"},
    {"ticker": "PEPE", "name": "Pepe"},
]


def search_assets(query: str) -> list:
    if not query:
        return KNOWN_ASSETS[:6]
    q = query.upper()
    return [a for a in KNOWN_ASSETS if q in a["ticker"] or q in a["name"].upper()][:10]


# ═══════════════════════════════════════════
# FEED v2 — enriched with interpretation + decision context + grouping
# ═══════════════════════════════════════════

INTERPRETATION_MAP = {
    "onchain.whale": "Large capital movement detected",
    "onchain.whale_inflow": "Coins flowing to exchanges — potential sell pressure",
    "onchain.whale_outflow": "Coins leaving exchanges — supply tightening",
    "sentiment.spike": "Market sentiment shifting rapidly",
    "sentiment.spike_up": "Crowd turning bullish quickly",
    "sentiment.spike_down": "Fear spreading through market",
    "exchange.signal": "Exchange pressure detected",
    "exchange.divergence": "Exchange models disagree — caution",
    "ml.risk": "Model uncertainty increased",
    "aggregator.signal": "System decision engine triggered",
    "system.degradation": "Model performance degradation detected",
}


def _interpret_event(ev_type: str) -> str:
    for key, text in INTERPRETATION_MAP.items():
        if key in ev_type:
            return text
    return "Signal detected"


async def build_feed(db, limit: int = 30) -> dict:
    """Build enriched feed with interpretation, decision context, and time grouping."""
    try:
        from notifications.storage.event_repo import get_recent_events
        events = await get_recent_events(limit=limit)
    except Exception:
        events = []

    now_ts = datetime.now(timezone.utc)
    sections = {"now": [], "today": [], "earlier": []}
    counts = {"all": 0, "high": 0}

    for ev in events:
        ev_type = ev.get("type", "")
        ev_asset = ev.get("asset", "") or ev.get("data", {}).get("asset", "")
        impact = _event_impact(ev)
        direction = _event_direction(ev)

        item = {
            "asset": ev_asset.upper() if ev_asset else "",
            "source": _event_alert_type(ev_type),
            "type": ev_type,
            "direction": direction,
            "impact": impact,
            "title": _event_title(ev),
            "summary": ev.get("message", "") or ev.get("data", {}).get("message", "") or ev_type.replace(".", " ").title(),
            "interpretation": _interpret_event(ev_type),
            "timestamp": ev.get("timestamp", ""),
        }

        # Group by time
        try:
            ts = ev.get("timestamp", "")
            if isinstance(ts, str) and ts:
                evt_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            else:
                evt_time = now_ts
            diff_h = (now_ts - evt_time).total_seconds() / 3600
            if diff_h < 1:
                sections["now"].append(item)
            elif diff_h < 24:
                sections["today"].append(item)
            else:
                sections["earlier"].append(item)
        except Exception:
            sections["earlier"].append(item)

        counts["all"] += 1
        if impact == "HIGH":
            counts["high"] += 1

    return {
        "sections": [
            {"label": "Now", "items": sections["now"]},
            {"label": "Today", "items": sections["today"]},
            {"label": "Earlier", "items": sections["earlier"]},
        ],
        "counts": counts,
    }


def _event_direction(ev: dict) -> str:
    t = ev.get("type", "")
    data = ev.get("data", {})
    if "whale_inflow" in t or "spike_down" in t or "risk" in t:
        return "BEARISH"
    if "whale_outflow" in t or "spike_up" in t:
        return "BULLISH"
    if data.get("direction"):
        d = data["direction"].upper()
        if d in ("LONG", "BULLISH", "BUY"):
            return "BULLISH"
        if d in ("SHORT", "BEARISH", "SELL"):
            return "BEARISH"
    return "NEUTRAL"


def _event_title(ev: dict) -> str:
    t = ev.get("type", "")
    if "whale" in t:
        return "Whale movement detected"
    if "sentiment" in t:
        return "Sentiment shift"
    if "divergence" in t:
        return "Exchange divergence"
    if "risk" in t:
        return "Risk alert"
    if "aggregator" in t:
        return "System signal"
    return t.split(".")[-1].replace("_", " ").title() if "." in t else "Signal"


# ═══════════════════════════════════════════
# POLYMARKET
# ═══════════════════════════════════════════

async def build_polymarket(db) -> dict:
    try:
        cursor = db.prediction_markets.find({}, {"_id": 0}).sort("updatedAt", -1).limit(20)
        markets = []
        best_edge = None
        best_edge_abs = 0

        async for doc in cursor:
            mp = doc.get("yes_price", 0.5)
            mdl = doc.get("model_prob", 0.5) or doc.get("fair_yes_prob", 0.5)
            edge = round(mdl - mp, 4)
            action = "BUY_YES" if edge > 0.05 else ("BUY_NO" if edge < -0.05 else "SKIP")
            item = {
                "market": doc.get("question", "Unknown"),
                "category": doc.get("category", "crypto"),
                "market_prob": round(mp, 4),
                "model_prob": round(mdl, 4),
                "edge": edge,
                "action": action,
                "expiry": doc.get("expiry", ""),
            }
            markets.append(item)
            if abs(edge) > best_edge_abs:
                best_edge_abs = abs(edge)
                best_edge = item

        return {"spotlight": best_edge, "markets": markets}
    except Exception:
        return {"spotlight": None, "markets": []}
