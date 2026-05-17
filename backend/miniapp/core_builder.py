"""
MiniApp Core Builder — Decision Delivery Layer
================================================
Aggregates all system signals into a single MiniAppCoreResponse.

Sources:
  - exchange_forecasts (latest forecast + aggregator)
  - sentiment_adapter (weighted sentiment)
  - fractal_adapter (fractal signal)
  - ml_overlay.catastrophic_risk (risk score)
  - notification_events (recent alerts)
  - price_provider (current price via yfinance)
"""

from datetime import datetime, timezone, timedelta


async def build_core(db, asset: str = "BTC") -> dict:
    """
    Build the unified MiniAppCoreResponse for a given asset.
    All data comes from existing system — no new inventions.
    """
    asset_upper = asset.upper()
    symbol = f"{asset_upper}USDT"

    # ── 1. Latest forecast (with aggregator shadow data) ──
    forecast = await _fetch_latest_forecast(db, symbol)

    # ── 2. Sentiment ──
    sentiment = _fetch_sentiment(db, asset_upper)

    # ── 3. Fractal ──
    fractal = _fetch_fractal(db, asset_upper)

    # ── 4. ML Risk ──
    ml_risk = await _fetch_ml_risk(db, symbol)

    # ── 5. Current price ──
    current_price = _fetch_current_price(asset_upper)

    # ── 6. Recent alerts ──
    alerts = await _fetch_alerts(db, asset_upper)

    # ── 7. Polymarket edge ──
    polymarket = await _fetch_polymarket_edge(db, asset_upper)

    # ── Build decision ──
    decision = _build_decision(forecast)
    market = _build_market(forecast, current_price)
    signals = _build_signals(forecast, sentiment, fractal, ml_risk)

    return {
        "asset": asset_upper,
        "decision": decision,
        "market": market,
        "signals": signals,
        "polymarket": polymarket,
        "alerts": alerts,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def _fetch_latest_forecast(db, symbol: str) -> dict:
    """Get the most recent exchange forecast for the symbol."""
    try:
        doc = await db.exchange_forecasts.find_one(
            {"symbol": symbol},
            {"_id": 0, "direction": 1, "confidence": 1, "horizon": 1,
             "symbol": 1, "createdAt": 1,
             "audit.scoreRaw": 1, "audit.scoreFinal": 1,
             "audit.regime": 1, "audit.decision_trace": 1,
             "audit.decision_v2": 1, "audit.forecast_v2": 1,
             "audit.aggregator_v1": 1, "audit.aggregator_live": 1,
             "audit.convergence": 1,
             "outcome": 1},
            sort=[("createdAt", -1)],
        )
        return doc or {}
    except Exception:
        return {}


def _fetch_sentiment(db, asset: str) -> dict:
    """Sync call to sentiment adapter."""
    try:
        from forecast.system.sentiment_adapter import fetch_sentiment_for_asset
        return fetch_sentiment_for_asset(db.delegate, asset)
    except Exception:
        return {"score": 0.0, "confidence": 0.0, "source_count": 0}


def _fetch_fractal(db, asset: str) -> dict:
    """Sync call to fractal adapter."""
    try:
        from forecast.system.fractal_adapter import fetch_fractal_signal
        return fetch_fractal_signal(db.delegate, asset)
    except Exception:
        return {"signal": 0.0, "confidence": 0.0, "direction": "NEUTRAL", "horizon": "N/A"}


async def _fetch_ml_risk(db, symbol: str) -> dict:
    """Get ML catastrophic risk prediction for latest forecast."""
    try:
        from ml_overlay.catastrophic_risk import predict_catastrophic_risk
        doc = await db.exchange_forecasts.find_one(
            {"symbol": symbol},
            {"_id": 0, "direction": 1, "confidence": 1, "horizon": 1,
             "audit": 1, "symbol": 1},
            sort=[("createdAt", -1)],
        )
        if not doc:
            return {"level": "unknown", "score": 0.0}
        result = predict_catastrophic_risk(doc)
        score = result.get("catastrophic_risk", 0.0)
        level = "high" if score > 0.6 else ("medium" if score > 0.3 else "low")
        return {"level": level, "score": round(score, 4)}
    except Exception:
        return {"level": "unknown", "score": 0.0}


def _fetch_current_price(asset: str) -> float:
    """Get current price via yfinance cache."""
    try:
        from forecast.price_provider import get_price
        import time
        now_ms = int(time.time() * 1000)
        price = get_price(asset, now_ms)
        return price or 0.0
    except Exception:
        return 0.0


async def _fetch_alerts(db, asset: str, limit: int = 10) -> list:
    """Get recent notification events relevant to the asset."""
    try:
        from notifications.storage.event_repo import get_recent_events
        events = await get_recent_events(limit=50)

        alerts = []
        for ev in events:
            # Filter by asset relevance
            ev_asset = ev.get("asset", "") or ev.get("data", {}).get("asset", "")
            ev_type = ev.get("type", "")
            ev_msg = ev.get("message", "") or ev.get("data", {}).get("message", "")

            # Include if asset matches or it's a system-wide event
            if ev_asset.upper() == asset or ev_type.startswith("system.") or ev_type.startswith("aggregator."):
                impact = _classify_impact(ev)
                alert_type = _classify_alert_type(ev_type)
                alerts.append({
                    "type": alert_type,
                    "message": ev_msg or _generate_alert_message(ev),
                    "impact": impact,
                    "timestamp": ev.get("timestamp", ""),
                    "event_type": ev_type,
                })
                if len(alerts) >= limit:
                    break

        return alerts
    except Exception:
        return []


async def _fetch_polymarket_edge(db, asset: str) -> dict:
    """Get latest Polymarket edge data for the asset."""
    try:
        # Look for recent prediction market data
        doc = await db.prediction_markets.find_one(
            {"$or": [
                {"question": {"$regex": asset, "$options": "i"}},
                {"asset": asset.upper()},
            ]},
            {"_id": 0},
            sort=[("updatedAt", -1)],
        )
        if doc:
            market_prob = doc.get("yes_price", 0.5)
            model_prob = doc.get("model_prob", 0.5) or doc.get("fair_yes_prob", 0.5)
            edge = round(model_prob - market_prob, 4)
            action = "BUY_YES" if edge > 0.05 else ("BUY_NO" if edge < -0.05 else "SKIP")
            return {
                "market": doc.get("question", f"{asset} prediction"),
                "market_prob": round(market_prob, 4),
                "model_prob": round(model_prob, 4),
                "edge": edge,
                "action": action,
            }
        return {
            "market": f"No active {asset} markets",
            "market_prob": 0,
            "model_prob": 0,
            "edge": 0,
            "action": "SKIP",
        }
    except Exception:
        return {
            "market": f"No active {asset} markets",
            "market_prob": 0,
            "model_prob": 0,
            "edge": 0,
            "action": "SKIP",
        }


def _build_decision(forecast: dict) -> dict:
    """Build the top-level decision from forecast data."""
    # Prefer aggregator output if available
    agg = forecast.get("audit", {}).get("aggregator_v1", {}) or {}
    agg_live = forecast.get("audit", {}).get("aggregator_live", {}) or {}
    dv2 = forecast.get("audit", {}).get("decision_v2", {}) or {}

    # Use aggregator if it was actually used in live
    if agg_live.get("used") and agg:
        direction = agg.get("direction", "NEUTRAL")
        confidence = agg.get("confidence", 0.5)
        score = agg.get("final_score", 0)
    elif dv2:
        direction = dv2.get("direction", forecast.get("direction", "NEUTRAL"))
        confidence = dv2.get("confidence", forecast.get("confidence", 0.5))
        score = dv2.get("score", 0)
    else:
        direction = forecast.get("direction", "NEUTRAL")
        confidence = forecast.get("confidence", 0.5)
        score = forecast.get("audit", {}).get("scoreFinal", 0) or 0

    # Map direction to action
    action_map = {"LONG": "BUY", "SHORT": "SELL", "NEUTRAL": "WAIT"}
    action = action_map.get(direction, "WAIT")

    # Determine strength
    conf = float(confidence) if confidence else 0.5
    abs_score = abs(float(score)) if score else 0
    if conf >= 0.75 or abs_score >= 0.7:
        strength = "EXTREME"
    elif conf >= 0.55 or abs_score >= 0.4:
        strength = "HIGH_CONVICTION"
    else:
        strength = "NORMAL"

    if action == "WAIT":
        strength = "NORMAL"

    return {
        "action": action,
        "strength": strength,
        "confidence": round(conf * 100),
    }


def _build_market(forecast: dict, current_price: float) -> dict:
    """Build market context from forecast data."""
    horizon = forecast.get("horizon", "7D")
    dv2 = forecast.get("audit", {}).get("decision_v2", {}) or {}
    fv2 = forecast.get("audit", {}).get("forecast_v2", {}) or {}
    convergence = forecast.get("audit", {}).get("convergence", {}) or {}
    regime = forecast.get("audit", {}).get("regime", "UNKNOWN")

    direction = forecast.get("direction", "NEUTRAL")
    dir_map = {"LONG": "BULLISH", "SHORT": "BEARISH", "NEUTRAL": "NEUTRAL"}
    market_direction = dir_map.get(direction, "NEUTRAL")

    # Expected move
    score_raw = float(forecast.get("audit", {}).get("scoreRaw", 0) or 0)
    expected_move_pct = round(score_raw * 10, 2)  # rough approximation

    # Price range estimation
    range_pct = abs(expected_move_pct) if expected_move_pct else 3.0
    range_low = round(current_price * (1 - range_pct / 100), 2) if current_price else 0
    range_high = round(current_price * (1 + range_pct / 100), 2) if current_price else 0

    # Story generation
    story = _generate_story(direction, regime, forecast)

    return {
        "current_price": round(current_price, 2),
        "horizon": horizon,
        "expected_move_pct": expected_move_pct,
        "direction": market_direction,
        "scenario": {
            "type": _infer_scenario_type(direction, regime),
            "probability": round(float(forecast.get("confidence", 0.5)) * 100),
            "range_low": range_low,
            "range_high": range_high,
        },
        "story": story,
    }


def _build_signals(forecast: dict, sentiment: dict, fractal: dict, ml_risk: dict) -> dict:
    """Build signals breakdown from all modules."""
    agg = forecast.get("audit", {}).get("aggregator_v1", {}) or {}
    components = agg.get("components", {})

    # Exchange signal
    exchange_score = components.get("exchange", 0)
    exchange_dir = "bullish" if exchange_score > 0.05 else ("bearish" if exchange_score < -0.05 else "neutral")

    # OnChain (from notifications / whale data if available)
    # Approximation: use exchange divergence or score direction
    onchain_strength = abs(exchange_score) * 0.6

    # Sentiment
    sent_score = sentiment.get("score", 0)
    sent_trend = "positive" if sent_score > 0.1 else ("negative" if sent_score < -0.1 else "neutral")

    # Fractal
    fractal_signal = fractal.get("signal", 0)

    return {
        "exchange": {
            "direction": exchange_dir,
            "strength": round(abs(exchange_score), 4),
        },
        "onchain": {
            "whale_flow": "inflow" if exchange_score < -0.1 else ("outflow" if exchange_score > 0.1 else "neutral"),
            "strength": round(onchain_strength, 4),
        },
        "sentiment": {
            "trend": sent_trend,
            "delta": round(sent_score, 4),
        },
        "twitter": {
            "narrative": _infer_narrative(forecast),
            "intensity": round(abs(sent_score) * 10, 1),
        },
        "ml_risk": ml_risk,
    }


def _generate_story(direction: str, regime: str, forecast: dict) -> str:
    """Generate a concise one-liner market story."""
    regime_context = {
        "TREND_UP": "uptrend continuation",
        "TREND_DOWN": "downtrend pressure",
        "RANGE": "range-bound market",
        "ACCUMULATION": "accumulation phase",
        "DISTRIBUTION": "distribution phase",
    }
    regime_desc = regime_context.get(regime, "mixed conditions")

    if direction == "LONG":
        return f"Bullish setup in {regime_desc}. Key signals align for upside."
    elif direction == "SHORT":
        return f"Bearish pressure with {regime_desc}. Multiple signals point down."
    else:
        return f"Neutral stance amid {regime_desc}. No strong conviction either way."


def _infer_scenario_type(direction: str, regime: str) -> str:
    if direction == "NEUTRAL":
        return "range"
    if regime in ("TREND_UP", "TREND_DOWN"):
        return "continuation"
    return "breakdown"


def _infer_narrative(forecast: dict) -> str:
    """Infer Twitter narrative from forecast context."""
    regime = forecast.get("audit", {}).get("regime", "")
    direction = forecast.get("direction", "NEUTRAL")
    if direction == "SHORT":
        return "Risk-off sentiment, fear dominates"
    elif direction == "LONG":
        return "Accumulation narrative gaining traction"
    return "Mixed narratives, no clear trend"


def _classify_impact(event: dict) -> str:
    ev_type = event.get("type", "")
    if "whale" in ev_type or "divergence" in ev_type:
        data = event.get("data", {})
        direction = data.get("direction", "")
        if direction:
            return direction.lower()
        return "bearish"
    if "sentiment" in ev_type:
        delta = event.get("data", {}).get("delta", 0)
        return "bullish" if delta > 0 else "bearish"
    if "risk" in ev_type or "degradation" in ev_type:
        return "bearish"
    if "signal" in ev_type:
        data = event.get("data", {})
        return data.get("direction", "neutral").lower()
    return "neutral"


def _classify_alert_type(ev_type: str) -> str:
    if "whale" in ev_type or "onchain" in ev_type:
        return "whale"
    if "sentiment" in ev_type:
        return "sentiment"
    if "exchange" in ev_type or "divergence" in ev_type:
        return "exchange"
    if "risk" in ev_type or "ml_risk" in ev_type:
        return "risk"
    if "aggregator" in ev_type:
        return "system"
    return "other"


def _generate_alert_message(event: dict) -> str:
    ev_type = event.get("type", "")
    data = event.get("data", {})

    if "whale" in ev_type:
        amount = data.get("amount", "")
        return f"Whale transfer detected: {amount}"
    if "sentiment" in ev_type:
        delta = data.get("delta", 0)
        return f"Sentiment shift: {delta:+.1f}%"
    if "risk" in ev_type:
        score = data.get("risk_score", 0)
        return f"ML Risk updated: {score:.2f}"
    if "divergence" in ev_type:
        return "Exchange divergence detected"
    if "aggregator" in ev_type and "signal" in ev_type:
        direction = data.get("direction", "")
        return f"Aggregator signal: {direction}"

    return ev_type.replace(".", " ").title()
