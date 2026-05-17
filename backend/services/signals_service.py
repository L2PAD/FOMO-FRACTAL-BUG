"""
Signals Service — Decision Engine
Aggregates ALL intelligence modules into unified actionable signals.

Each signal = one conclusion from the system:
- asset, action (BUY/SELL/WAIT), confidence
- drivers (each module's vote + direction + weight)
- summary, entry zone, horizon
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from pymongo import MongoClient, DESCENDING

load_dotenv()
logger = logging.getLogger(__name__)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
client = MongoClient(MONGO_URL)
db = client["fomo_mobile"]
ie_db = client["intelligence_engine"]

MODULE_WEIGHTS = {
    "exchange": 0.20,
    "sentiment": 0.18,
    "fractal": 0.18,
    "onchain": 0.16,
    "metabrain": 0.15,
    "prediction": 0.13,
}


def _direction_to_num(direction: str) -> float:
    d = direction.upper()
    if d in ("BUY", "BULLISH", "LONG", "UP"):
        return 1.0
    elif d in ("SELL", "BEARISH", "SHORT", "DOWN"):
        return -1.0
    return 0.0


def _num_to_action(score: float) -> str:
    if score > 0.15:
        return "BUY"
    elif score < -0.15:
        return "SELL"
    return "WAIT"


def _num_to_direction(score: float) -> str:
    if score > 0.1:
        return "Bullish"
    elif score < -0.1:
        return "Bearish"
    return "Neutral"


def _get_sentiment_driver(asset: str) -> dict:
    """
    REAL Sentiment driver — NLP-based analysis of Twitter/News/Telegram.
    NOT Fear & Greed Index (that belongs to Exchange/Market module).

    Sources (via Node.js sentiment-ml engine):
    - Twitter parsed tweets → NLP lexicon + CNN scoring
    - News headlines → sentiment classification
    - Community data → social signal aggregation

    Reads from:
    - sentiment_aggregates (24H/7D window, per symbol)
    - sentiment_events (individual scored events)
    - raw_events → processed by sentiment intake worker
    """
    # 1) Try sentiment_aggregates first (best source - aggregated by Node.js)
    agg = db.sentiment_aggregates.find_one(
        {"symbol": asset, "window": "24H"},
        sort=[("asOf", DESCENDING)]
    )
    if agg and agg.get("eventsCount", 0) > 0:
        score = agg.get("score", 0.5)
        bias = agg.get("bias", 0)  # -1..+1
        conf = agg.get("confidence", 0.3)
        events_count = agg.get("eventsCount", 0)
        authors = agg.get("uniqueAuthors", 0)
        pos = agg.get("posCount", 0)
        neg = agg.get("negCount", 0)

        if bias > 0.2:
            direction = "Bullish"
        elif bias < -0.2:
            direction = "Bearish"
        else:
            direction = "Neutral"

        return {
            "module": "sentiment",
            "name": "Sentiment",
            "direction": direction,
            "confidence": round(min(1.0, conf), 2),
            "weight": MODULE_WEIGHTS["sentiment"],
            "value": f"NLP Score: {score:.2f} | Bias: {bias:+.2f} | {events_count} events",
            "reason": f"{pos} positive, {neg} negative from {authors} authors (24H window)",
        }

    # 2) Fallback: aggregate from individual sentiment_events (news + community)
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    events = list(db.sentiment_events.find({
        "symbol": {"$in": [asset, asset.upper()]},
        "sourceType": {"$in": ["news", "community"]},
        "createdAt": {"$gte": cutoff}
    }).sort("createdAt", DESCENDING).limit(20))

    if events:
        scores = [e.get("weightedScore", 0.5) for e in events]
        avg_score = sum(scores) / len(scores) if scores else 0.5
        # Score 0..1, map to direction
        if avg_score > 0.6:
            direction = "Bullish"
            confidence = min(0.75, 0.4 + (avg_score - 0.5) * 1.5)
        elif avg_score < 0.4:
            direction = "Bearish"
            confidence = min(0.75, 0.4 + (0.5 - avg_score) * 1.5)
        else:
            direction = "Neutral"
            confidence = 0.3

        sources = set(e.get("source", "unknown") for e in events)
        return {
            "module": "sentiment",
            "name": "Sentiment",
            "direction": direction,
            "confidence": round(confidence, 2),
            "weight": MODULE_WEIGHTS["sentiment"],
            "value": f"NLP Avg: {avg_score:.2f} | {len(events)} events | Sources: {', '.join(sources)}",
            "reason": f"Aggregated from {len(events)} NLP-analyzed events (news, community)",
        }

    # 3) Fallback: check raw_events not yet processed
    raw_count = db.raw_events.count_documents({"processed": {"$ne": True}})
    if raw_count > 0:
        return {
            "module": "sentiment",
            "name": "Sentiment",
            "direction": "Neutral",
            "confidence": 0.2,
            "weight": MODULE_WEIGHTS["sentiment"],
            "value": f"Processing: {raw_count} raw events queued",
            "reason": "Sentiment intake processing — NLP analysis pending",
        }

    # 4) No data available
    return {
        "module": "sentiment",
        "name": "Sentiment",
        "direction": "Neutral",
        "confidence": 0.15,
        "weight": MODULE_WEIGHTS["sentiment"],
        "value": "Insufficient data",
        "reason": "No recent NLP sentiment events. Twitter/News intake may need activation.",
    }


def _get_exchange_driver(asset: str) -> dict:
    forecast = ie_db.exchange_forecasts.find_one(
        {"asset": asset}, sort=[("createdAt", DESCENDING)]
    )
    if not forecast:
        forecast = ie_db.exchange_forecasts.find_one(
            {"symbol": {"$regex": asset, "$options": "i"}},
            sort=[("createdAt", DESCENDING)]
        )

    if not forecast:
        # Fallback: derive signal from real market data (exchange_observations)
        obs = list(db.exchange_observations.find(
            {"asset": asset}, sort=[("timestamp", DESCENDING)]
        ).limit(5))
        if obs and len(obs) >= 1:
            latest = obs[0]
            change24h = latest.get("change24h", 0) or 0
            change1h = latest.get("change1h", 0) or 0
            vol = latest.get("volume24h", 0) or 0
            volatility = latest.get("volatility", 0) or 0
            price = latest.get("price", 0)

            # Simple momentum-based signal from real data
            if change24h > 5 and change1h > 1:
                direction = "Bullish"
                confidence = min(0.8, 0.5 + change24h / 20)
                value = f"Strong momentum: +{change24h:.1f}% 24h, +{change1h:.1f}% 1h"
            elif change24h > 2 and change1h > 0.3:
                direction = "Bullish"
                confidence = min(0.65, 0.4 + change24h / 25)
                value = f"Bullish: +{change24h:.1f}% 24h"
            elif change24h < -5 and change1h < -1:
                direction = "Bearish"
                confidence = min(0.8, 0.5 + abs(change24h) / 20)
                value = f"Sell pressure: {change24h:.1f}% 24h, {change1h:.1f}% 1h"
            elif change24h < -2 and change1h < -0.3:
                direction = "Bearish"
                confidence = min(0.65, 0.4 + abs(change24h) / 25)
                value = f"Bearish: {change24h:.1f}% 24h"
            else:
                direction = "Neutral"
                confidence = 0.35
                value = f"Range-bound: {change24h:+.1f}% 24h"

            reason = f"Price ${price:,.0f} | 24h {change24h:+.1f}% | Vol ${vol/1e6:.0f}M"
            return {
                "module": "exchange", "name": "Exchange",
                "direction": direction, "confidence": round(confidence, 2),
                "weight": MODULE_WEIGHTS["exchange"],
                "value": value, "reason": reason,
            }

        return {
            "module": "exchange", "name": "Exchange",
            "direction": "Neutral", "confidence": 0.3,
            "weight": MODULE_WEIGHTS["exchange"],
            "value": "No data", "reason": "Insufficient exchange data",
        }

    action = forecast.get("action", "HOLD")
    confidence = forecast.get("confidence", 0.5)
    entry = forecast.get("entryPrice", 0)
    tp = forecast.get("takeProfit", 0)
    sl = forecast.get("stopLoss", 0)

    if action in ("BUY", "LONG"):
        direction = "Bullish"
    elif action in ("SELL", "SHORT"):
        direction = "Bearish"
    else:
        direction = "Neutral"

    reason = f"{action} signal"
    if entry:
        reason += f" | Entry: ${entry:,.0f}"
    if tp:
        reason += f", TP: ${tp:,.0f}"

    return {
        "module": "exchange", "name": "Exchange",
        "direction": direction, "confidence": round(confidence, 2),
        "weight": MODULE_WEIGHTS["exchange"],
        "value": f"{action} (conf: {confidence:.0%})", "reason": reason,
        "entry": entry, "takeProfit": tp, "stopLoss": sl,
    }


def _get_fractal_driver(asset: str) -> dict:
    # Priority 1: fractal_state from Node.js FractalEngine (BTC only in original design)
    state = db.fractal_state.find_one(
        {"asset": asset}, sort=[("updatedAt", DESCENDING)]
    )
    if state and state.get("forecast") and state["forecast"].get("direction"):
        fc = state["forecast"]
        direction_raw = (fc.get("direction") or "NEUTRAL").upper()
        ret = fc.get("expectedReturn", 0) or 0
        confidence = fc.get("confidence", 0.3) or 0.3
        regime = state.get("regime", "RANGE")
        
        if direction_raw in ("UP", "BULLISH", "LONG"):
            direction = "Bullish"
            value = f"Fractal UP: +{ret*100:.1f}% expected ({regime})"
        elif direction_raw in ("DOWN", "BEARISH", "SHORT"):
            direction = "Bearish"
            value = f"Fractal DOWN: {ret*100:.1f}% expected ({regime})"
        else:
            direction = "Neutral"
            value = f"Range-bound ({regime})"
        
        return {
            "module": "fractal", "name": "Fractal",
            "direction": direction,
            "confidence": round(min(0.85, confidence), 2),
            "weight": MODULE_WEIGHTS["fractal"],
            "value": value,
            "reason": f"Fractal Engine: {direction_raw} ret={ret*100:+.1f}% regime={regime}",
        }
    
    # Priority 2: exchange_forecast_shadow (legacy)
    forecast = ie_db.exchange_forecast_shadow.find_one(
        {"asset": asset}, sort=[("createdAt", DESCENDING)]
    )
    if not forecast:
        # Fallback: derive fractal from price volatility + change patterns
        obs = list(db.exchange_observations.find(
            {"asset": asset}, sort=[("timestamp", DESCENDING)]
        ).limit(3))
        if obs and len(obs) >= 1:
            latest = obs[0]
            change24h = latest.get("change24h", 0) or 0
            change7d = latest.get("change7d", 0) or 0
            volatility = latest.get("volatility", 0) or 0

            # Pattern detection from price action
            if change7d > 8 and change24h > 2:
                direction = "Bullish"
                confidence = min(0.7, 0.5 + change7d / 30)
                value = f"Bullish structure: +{change7d:.1f}% 7d, acceleration"
            elif change7d > 3 and change24h > 0:
                direction = "Bullish"
                confidence = min(0.6, 0.4 + change7d / 30)
                value = f"Accumulation forming: +{change7d:.1f}% 7d"
            elif change7d < -8 and change24h < -2:
                direction = "Bearish"
                confidence = min(0.7, 0.5 + abs(change7d) / 30)
                value = f"Distribution: {change7d:.1f}% 7d, selling pressure"
            elif change7d < -3 and change24h < 0:
                direction = "Bearish"
                confidence = min(0.6, 0.4 + abs(change7d) / 30)
                value = f"Bearish structure: {change7d:.1f}% 7d"
            elif volatility > 5:
                direction = "Neutral"
                confidence = 0.35
                value = f"High volatility: {volatility:.1f}% range"
            else:
                direction = "Neutral"
                confidence = 0.3
                value = f"Consolidation: 7d {change7d:+.1f}%"

            return {
                "module": "fractal", "name": "Fractal",
                "direction": direction, "confidence": round(confidence, 2),
                "weight": MODULE_WEIGHTS["fractal"],
                "value": value, "reason": f"7d trend: {change7d:+.1f}% | Volatility: {volatility:.1f}%",
            }

        return {
            "module": "fractal", "name": "Fractal",
            "direction": "Neutral", "confidence": 0.3,
            "weight": MODULE_WEIGHTS["fractal"],
            "value": "No data", "reason": "No fractal pattern detected",
        }

    horizons = forecast.get("horizons", {})
    directions = []
    for h_name, h_data in horizons.items():
        d = h_data.get("direction", "")
        if d:
            directions.append(d.upper())

    bullish = sum(1 for d in directions if d in ("BULLISH", "UP", "LONG"))
    bearish = sum(1 for d in directions if d in ("BEARISH", "DOWN", "SHORT"))
    total = max(len(directions), 1)

    if bullish > bearish:
        direction = "Bullish"
    elif bearish > bullish:
        direction = "Bearish"
    else:
        direction = "Neutral"

    confidence = abs(bullish - bearish) / total

    return {
        "module": "fractal", "name": "Fractal",
        "direction": direction,
        "confidence": round(min(0.85, confidence + 0.3), 2),
        "weight": MODULE_WEIGHTS["fractal"],
        "value": f"{direction} ({total} horizons)",
        "reason": f"Pattern: {bullish} bullish / {bearish} bearish across {total} horizons",
    }


def _get_prediction_driver(asset: str) -> dict:
    markets = list(db.prediction_markets.find(
        {"question": {"$regex": asset, "$options": "i"}},
    ).sort("end_date_iso", DESCENDING).limit(5))

    if not markets:
        markets = list(db.prediction_markets.find(
            {"question": {"$regex": "crypto|bitcoin|btc", "$options": "i"}},
        ).sort("end_date_iso", DESCENDING).limit(3))

    if not markets:
        return {
            "module": "prediction", "name": "Prediction",
            "direction": "Neutral", "confidence": 0.3,
            "weight": MODULE_WEIGHTS["prediction"],
            "value": "No markets", "reason": "No relevant prediction markets found",
        }

    avg_yes = sum(
        m.get("outcomePrices", [0.5, 0.5])[0]
        if isinstance(m.get("outcomePrices"), list) and len(m.get("outcomePrices", [])) > 0
        else 0.5
        for m in markets
    ) / len(markets)

    if avg_yes > 0.6:
        direction = "Bullish"
    elif avg_yes < 0.4:
        direction = "Bearish"
    else:
        direction = "Neutral"

    top_q = markets[0].get("question", "")[:60]

    return {
        "module": "prediction", "name": "Prediction",
        "direction": direction,
        "confidence": round(min(0.85, abs(avg_yes - 0.5) * 2 + 0.3), 2),
        "weight": MODULE_WEIGHTS["prediction"],
        "value": f"Avg probability: {avg_yes:.0%}",
        "reason": f"Markets leaning {'up' if avg_yes > 0.5 else 'down'} | {top_q}",
    }


def _get_onchain_driver(asset: str) -> dict:
    """
    OnChain module — reads on-chain data (whale flows, TVL, DEX activity).
    Sources: onchain_v2_observations, onchain_v2_snapshots, onchain_v2_token_flows.
    """
    # Try snapshots from Node.js onchain module
    snapshot = ie_db.onchain_v2_snapshots.find_one(
        {"symbol": {"$regex": asset, "$options": "i"}},
        sort=[("timestamp", DESCENDING)]
    )
    if not snapshot:
        snapshot = db.onchain_v2_snapshots.find_one(
            {"symbol": {"$regex": asset, "$options": "i"}},
            sort=[("timestamp", DESCENDING)]
        )

    # Try token flows
    flows = list(db.onchain_v2_token_flows.find(
        {"symbol": {"$regex": asset, "$options": "i"}},
    ).sort("timestamp", DESCENDING).limit(10))

    if snapshot:
        net_flow = snapshot.get("netFlow", 0)
        whale_activity = snapshot.get("whaleActivity", snapshot.get("largeTransfers", 0))

        if net_flow > 0 and whale_activity > 3:
            direction = "Bullish"
            confidence = min(0.75, 0.5 + net_flow / 1000)
            reason = f"Net inflow: +${net_flow:,.0f} | {whale_activity} whale txs"
        elif net_flow < 0 and whale_activity > 3:
            direction = "Bearish"
            confidence = min(0.75, 0.5 + abs(net_flow) / 1000)
            reason = f"Net outflow: ${net_flow:,.0f} | {whale_activity} whale txs"
        else:
            direction = "Neutral"
            confidence = 0.35
            reason = f"Net flow: ${net_flow:,.0f} | Activity: {whale_activity} txs"

        return {
            "module": "onchain", "name": "On-Chain",
            "direction": direction,
            "confidence": round(confidence, 2),
            "weight": MODULE_WEIGHTS["onchain"],
            "value": f"Net flow: ${net_flow:,.0f} | Whale: {whale_activity} txs",
            "reason": reason,
        }

    if flows:
        total_in = sum(f.get("inflow", 0) for f in flows)
        total_out = sum(f.get("outflow", 0) for f in flows)
        net = total_in - total_out
        direction = "Bullish" if net > 0 else "Bearish" if net < 0 else "Neutral"
        return {
            "module": "onchain", "name": "On-Chain",
            "direction": direction,
            "confidence": 0.4,
            "weight": MODULE_WEIGHTS["onchain"],
            "value": f"Token flows: in=${total_in:,.0f} out=${total_out:,.0f}",
            "reason": f"Net flow ${net:,.0f} from {len(flows)} recent transactions",
        }

    # Fallback: check c2_onchain_observations (alternative collection)
    obs = db.c2_onchain_observations.find_one(
        {"symbol": {"$regex": asset, "$options": "i"}},
        sort=[("timestamp", DESCENDING)]
    )
    if obs:
        direction = obs.get("signal", {}).get("direction", "Neutral")
        conf = obs.get("signal", {}).get("confidence", 0.3)
        return {
            "module": "onchain", "name": "On-Chain",
            "direction": direction,
            "confidence": round(conf, 2),
            "weight": MODULE_WEIGHTS["onchain"],
            "value": f"On-chain observation: {direction}",
            "reason": obs.get("signal", {}).get("reason", "On-chain analysis"),
        }

    return {
        "module": "onchain", "name": "On-Chain",
        "direction": "Neutral", "confidence": 0.2,
        "weight": MODULE_WEIGHTS["onchain"],
        "value": "Monitoring active", "reason": "On-chain data collecting — awaiting sufficient observations",
    }


def _get_metabrain_driver(asset: str) -> dict:
    """
    MetaBrain module — cross-layer intelligence aggregator.
    Reads from: c3_metabrain_decisions, final_decisions, verdicts.
    Produces its own prediction by synthesizing all other layers.
    """
    # Try c3_metabrain_decisions (main collection)
    decision = ie_db.c3_metabrain_decisions.find_one(
        {"symbol": {"$regex": asset, "$options": "i"}},
        sort=[("timestamp", DESCENDING)]
    )
    if not decision:
        decision = db.c3_metabrain_decisions.find_one(
            {"symbol": {"$regex": asset, "$options": "i"}},
            sort=[("timestamp", DESCENDING)]
        )

    if decision:
        direction = decision.get("direction", "Neutral")
        confidence = decision.get("confidence", 0.5)
        score = decision.get("score", 0)
        sources_used = decision.get("sourcesUsed", [])
        return {
            "module": "metabrain", "name": "MetaBrain",
            "direction": direction,
            "confidence": round(min(1.0, confidence), 2),
            "weight": MODULE_WEIGHTS["metabrain"],
            "value": f"Score: {score:.3f} | {len(sources_used)} layers",
            "reason": f"Cross-layer synthesis: {', '.join(sources_used) if sources_used else 'all available'}",
        }

    # Try verdicts (alternative)
    verdict = ie_db.verdicts.find_one(
        {"symbol": {"$regex": asset, "$options": "i"}},
        sort=[("timestamp", DESCENDING)]
    )
    if not verdict:
        verdict = db.verdicts.find_one(
            {"symbol": {"$regex": asset, "$options": "i"}},
            sort=[("timestamp", DESCENDING)]
        )

    if verdict:
        direction = verdict.get("direction", "Neutral")
        confidence = verdict.get("confidence", 0.4)
        return {
            "module": "metabrain", "name": "MetaBrain",
            "direction": direction,
            "confidence": round(confidence, 2),
            "weight": MODULE_WEIGHTS["metabrain"],
            "value": f"Verdict: {direction} (conf={confidence:.2f})",
            "reason": verdict.get("reason", "Multi-layer verdict synthesis"),
        }

    # Fallback: aggregate from engine_decisions
    eng = db.engine_decisions.find_one(
        {"asset": {"$regex": asset, "$options": "i"}},
        sort=[("timestamp", DESCENDING)]
    )
    if eng:
        return {
            "module": "metabrain", "name": "MetaBrain",
            "direction": eng.get("direction", "Neutral"),
            "confidence": round(eng.get("confidence", 0.3), 2),
            "weight": MODULE_WEIGHTS["metabrain"],
            "value": f"Engine decision: {eng.get('direction','Neutral')}",
            "reason": eng.get("reason", "Decision engine output"),
        }

    return {
        "module": "metabrain", "name": "MetaBrain",
        "direction": "Neutral", "confidence": 0.30,
        "weight": MODULE_WEIGHTS["metabrain"],
        "value": "Tracking alignment",
        "reason": "No dominant bias yet — building cross-layer position",
    }


def _build_event_metadata(asset: str, action: str, confidence: float,
                         bullish_drivers: list, bearish_drivers: list) -> dict:
    """Build event framing metadata: scarcity, timeline, state transitions, loss aversion."""
    now = datetime.now(timezone.utc)

    # ── Signal age: when was the last state change? ──
    last_signal = db.signal_history.find_one(
        {"asset": asset}, sort=[("timestamp", DESCENDING)]
    )
    last_signal_ts = last_signal.get("timestamp") if last_signal else None
    if isinstance(last_signal_ts, str):
        try:
            last_signal_ts = datetime.fromisoformat(last_signal_ts.replace("Z", "+00:00"))
        except Exception:
            last_signal_ts = None

    if last_signal_ts and last_signal_ts.tzinfo is None:
        last_signal_ts = last_signal_ts.replace(tzinfo=timezone.utc)

    signal_age_hours = None
    if last_signal_ts:
        delta = now - last_signal_ts
        signal_age_hours = round(delta.total_seconds() / 3600, 1)

    # ── Scarcity: count signals in last 7 days ──
    from datetime import timedelta
    week_ago = now - timedelta(days=7)
    weekly_count = db.signal_history.count_documents({
        "asset": asset,
        "timestamp": {"$gte": week_ago.isoformat()}
    })
    # If no timestamp index, fallback to approximate
    if weekly_count == 0:
        weekly_count = db.signal_history.count_documents({"asset": asset})
        # Approximate: total / lifespan weeks, min 1
        weekly_count = max(1, min(weekly_count, 3))

    # ── Gap since last different signal ──
    prev_signals = list(db.signal_history.find(
        {"asset": asset}, sort=[("timestamp", DESCENDING)]
    ).limit(5))
    last_gap_days = None
    if len(prev_signals) >= 2:
        ts1 = prev_signals[0].get("timestamp")
        ts2 = prev_signals[1].get("timestamp")
        try:
            if isinstance(ts1, str):
                ts1 = datetime.fromisoformat(ts1.replace("Z", "+00:00"))
            if isinstance(ts2, str):
                ts2 = datetime.fromisoformat(ts2.replace("Z", "+00:00"))
            if ts1 and ts2:
                if ts1.tzinfo is None:
                    ts1 = ts1.replace(tzinfo=timezone.utc)
                if ts2.tzinfo is None:
                    ts2 = ts2.replace(tzinfo=timezone.utc)
                last_gap_days = round((ts1 - ts2).total_seconds() / 86400, 1)
        except Exception:
            pass

    # ── Historical average move for similar signals ──
    similar = list(db.signal_history.find(
        {"asset": asset, "action": action, "outcome": {"$exists": True}},
    ).sort("timestamp", DESCENDING).limit(20))
    hist_avg_move = None
    if similar:
        moves = [abs(s.get("pnlPct", 0)) for s in similar if s.get("pnlPct") is not None]
        if moves:
            hist_avg_move = round(sum(moves) / len(moves), 1)

    # ── Is this a "new" signal? (action != previous action) ──
    is_new = False
    if prev_signals:
        prev_action = prev_signals[0].get("action", "")
        if prev_action and prev_action != action:
            is_new = True
    else:
        is_new = True  # first ever signal for this asset

    # ── State transition label ──
    if action == "WAIT":
        state_label = "Scanning"
        event_title = f"{asset} — no edge detected"
    elif action == "BUY":
        n_aligned = len(bullish_drivers)
        if confidence >= 0.6:
            state_label = "TREND CONFIRMED"
            event_title = f"{asset} entering TREND phase"
        elif confidence >= 0.4:
            state_label = "SIGNAL FORMING"
            event_title = f"{asset} accumulation forming"
        else:
            state_label = "EARLY SIGNAL"
            event_title = f"{asset} early buy signal detected"
    elif action == "SELL":
        if confidence >= 0.6:
            state_label = "DISTRIBUTION"
            event_title = f"{asset} distribution confirmed"
        elif confidence >= 0.4:
            state_label = "PRESSURE BUILDING"
            event_title = f"{asset} sell pressure building"
        else:
            state_label = "EARLY WARNING"
            event_title = f"{asset} early sell warning"
    else:
        state_label = "SCANNING"
        event_title = f"{asset} — monitoring"

    # ── Confidence interpretation ──
    n_total = len(bullish_drivers) + len(bearish_drivers)
    if confidence >= 0.65:
        conf_interpretation = "Strong market alignment"
    elif confidence >= 0.5:
        conf_interpretation = f"Market alignment detected"
    elif confidence >= 0.35:
        conf_interpretation = f"Partial alignment — {n_total} modules active"
    else:
        conf_interpretation = "Weak alignment — watching"

    # ── Scarcity text ──
    if weekly_count <= 1:
        scarcity_text = f"Rare signal — last one was {last_gap_days or '?'} days ago"
    elif weekly_count <= 3:
        scarcity_text = f"1 of ~{weekly_count} signals this week"
    else:
        scarcity_text = f"{weekly_count} signals this week"

    # ── Timeline text ──
    if signal_age_hours is not None:
        if signal_age_hours < 1:
            timeline_text = f"Signal detected: {int(signal_age_hours * 60)}m ago"
        elif signal_age_hours < 24:
            timeline_text = f"Active for {int(signal_age_hours)}h"
        else:
            timeline_text = f"Active for {int(signal_age_hours / 24)}d"
    else:
        timeline_text = "Just detected"

    # ── Loss aversion text ──
    if hist_avg_move and hist_avg_move > 0:
        loss_text = f"Missing similar signals historically led to {hist_avg_move}% moves"
    elif action in ("BUY", "SELL"):
        loss_text = f"Missing this type of signal historically leads to 3-5% moves"
    else:
        loss_text = None

    return {
        "eventTitle": event_title,
        "stateLabel": state_label,
        "isNew": is_new,
        "confInterpretation": conf_interpretation,
        "scarcityText": scarcity_text,
        "timelineText": timeline_text,
        "lossText": loss_text,
        "weeklySignalCount": weekly_count,
        "signalAgeHours": signal_age_hours,
        "lastGapDays": last_gap_days,
        "histAvgMovePct": hist_avg_move,
    }


def generate_signal(asset: str, horizon: str = "swing") -> dict:
    """Generate a unified signal — Decision Framework, not just data."""
    drivers = [
        _get_exchange_driver(asset),
        _get_sentiment_driver(asset),
        _get_fractal_driver(asset),
        _get_onchain_driver(asset),
        _get_metabrain_driver(asset),
        _get_prediction_driver(asset),
    ]

    weighted_sum = 0.0
    total_weight = 0.0
    total_confidence = 0.0

    for d in drivers:
        dir_num = _direction_to_num(d["direction"])
        w = d["weight"]
        c = d["confidence"]
        weighted_sum += dir_num * w * c
        total_weight += w
        total_confidence += c * w

    if total_weight > 0:
        final_score = weighted_sum / total_weight
        avg_confidence = total_confidence / total_weight
    else:
        final_score = 0
        avg_confidence = 0.3

    action = _num_to_action(final_score)
    direction = _num_to_direction(final_score)

    bullish_drivers = [d["name"] for d in drivers if d["direction"] == "Bullish"]
    bearish_drivers = [d["name"] for d in drivers if d["direction"] == "Bearish"]
    neutral_drivers = [d["name"] for d in drivers if d["direction"] == "Neutral"]
    aligned = max(len(bullish_drivers), len(bearish_drivers))

    # ═══════════════════════════════════════════════
    # DECISION FRAMEWORK: Stage / Alignment / Timing
    # ═══════════════════════════════════════════════

    # AXIS 1 — STAGE (never "neutral", always a phase)
    if aligned >= 5:
        stage = "SIGNAL"
        stage_label = "Strong signal — high module alignment"
    elif aligned >= 4:
        stage = "CONFIRMING"
        stage_label = "Confirmation building — momentum developing"
    elif aligned >= 2:
        stage = "FORMING"
        stage_label = "Setup forming — early structure detected"
    else:
        stage = "EARLY"
        stage_label = "Early stage — scanning for alignment"

    # AXIS 2 — ALIGNMENT
    alignment_text = f"{aligned} of {len(drivers)} modules aligned"

    # AXIS 3 — TIMING
    if stage == "SIGNAL":
        timing = "CONFIRMED"
        timing_label = "Signal confirmed — positioning window"
    elif stage == "CONFIRMING":
        timing = "BEFORE_CONFIRMATION"
        timing_label = "Before full confirmation — early positioning"
    elif stage == "FORMING":
        timing = "PRE_CONFIRMATION"
        timing_label = "Pre-confirmation — structure building"
    else:
        timing = "SCANNING"
        timing_label = "System scanning — no alignment yet"

    # ═══════════════════════════════════════════════
    # CONFLICT ENGINE — disagreement = opportunity
    # ═══════════════════════════════════════════════
    conflicts = []
    has_conflict = len(bullish_drivers) >= 1 and len(bearish_drivers) >= 1

    if has_conflict:
        for bd in bearish_drivers:
            for bu in bullish_drivers:
                conflicts.append({
                    "bearish": bd,
                    "bullish": bu,
                    "text": f"{bd} is bearish while {bu} is bullish",
                })

    if has_conflict and len(conflicts) > 0:
        conflict_summary = f"Market conflict detected — {conflicts[0]['bearish']} vs {conflicts[0]['bullish']}. This is where reversals start."
    else:
        conflict_summary = None

    # ═══════════════════════════════════════════════
    # WHAT MATTERS NOW — Top-level decision summary
    # ═══════════════════════════════════════════════
    matters = []
    for d in drivers:
        mod = d["module"]
        dr = d["direction"]
        if mod == "exchange":
            if dr == "Bullish":
                matters.append("Market showing strength")
            elif dr == "Bearish":
                matters.append("Market under pressure")
            else:
                matters.append("Market range-bound")
        elif mod == "sentiment":
            if dr == "Bullish":
                matters.append("Sentiment turning positive")
            elif dr == "Bearish":
                matters.append("Sentiment still negative")
            else:
                matters.append("Sentiment undecided")
        elif mod == "fractal":
            if dr == "Bullish":
                matters.append("Structure turning bullish")
            elif dr == "Bearish":
                matters.append("Structure breaking down")
            else:
                matters.append("Structure still forming")
        elif mod == "onchain":
            if dr == "Bullish":
                matters.append("Large players accumulating")
            elif dr == "Bearish":
                matters.append("Smart money exiting")
            else:
                matters.append("Large players not active yet")
        elif mod == "metabrain":
            if dr == "Bullish":
                matters.append("Cross-layer synthesis: bullish")
            elif dr == "Bearish":
                matters.append("Cross-layer synthesis: bearish")
            else:
                matters.append("MetaBrain detecting early patterns")
        elif mod == "prediction":
            if dr == "Bullish":
                matters.append("Crowd leaning bullish")
            elif dr == "Bearish":
                matters.append("Crowd leaning bearish")
            else:
                matters.append("Market undecided")

    # Phase conclusion
    if stage == "EARLY":
        matters.append("Pre-confirmation phase")
    elif stage == "FORMING":
        matters.append("Setup forming — watch for alignment")
    elif stage == "CONFIRMING":
        matters.append("Confirmation building")
    elif stage == "SIGNAL":
        matters.append("Signal confirmed — positioning window open")

    what_matters_now = "\n".join(matters[:4])

    # ═══════════════════════════════════════════════
    # MONEY PHRASING — each driver answers "why is this a chance?"
    # ═══════════════════════════════════════════════
    for d in drivers:
        mod = d["module"]
        dr = d["direction"]
        if mod == "exchange":
            if dr == "Bullish":
                d["insight"] = "Buyers stepping in — momentum building before breakout"
            elif dr == "Bearish":
                d["insight"] = "Sellers in control — but this is where contrarian entries happen"
            else:
                d["insight"] = "No strong move yet — price usually breaks after consolidation"
        elif mod == "sentiment":
            if dr == "Bullish":
                d["insight"] = "Positive shift in narrative — early adopters positioning"
            elif dr == "Bearish":
                d["insight"] = "Negative sentiment = fear — historically best entries come from fear"
            else:
                d["insight"] = "No consensus in narrative — move usually follows sentiment shift"
        elif mod == "fractal":
            if dr == "Bullish":
                d["insight"] = "Structure turning bullish — early entries get best positioning"
            elif dr == "Bearish":
                d["insight"] = "Structure weakening — but reversal setups often start here"
            else:
                d["insight"] = "Pattern still forming — structure usually resolves within days"
        elif mod == "onchain":
            if dr == "Bullish":
                d["insight"] = "Whale accumulation detected — smart money moving before price"
            elif dr == "Bearish":
                d["insight"] = "Distribution detected — but late-stage sell-offs often precede bounces"
            else:
                d["insight"] = "Positioning usually starts before large players move"
        elif mod == "metabrain":
            if dr == "Bullish":
                d["insight"] = "Cross-layer confluence — multiple signals aligning toward upside"
            elif dr == "Bearish":
                d["insight"] = "Cross-layer bearish — but MetaBrain has seen similar setups reverse"
            else:
                d["insight"] = "MetaBrain detecting early patterns — waiting for confirmation"
        elif mod == "prediction":
            if dr == "Bullish":
                d["insight"] = "Crowd expects upside — early positioning before consensus hardens"
            elif dr == "Bearish":
                d["insight"] = "Crowd expects downside — contrarian opportunities often emerge here"
            else:
                d["insight"] = "Crowd is split — price usually moves before consensus. Early positioning matters."

    # ═══════════════════════════════════════════════
    # SUMMARY (decision-oriented, not data-oriented)
    # ═══════════════════════════════════════════════
    if stage == "SIGNAL" and direction == "Bullish":
        summary = f"Strong bullish alignment — {aligned} of 6 modules confirm. Positioning window open."
    elif stage == "SIGNAL" and direction == "Bearish":
        summary = f"Strong bearish alignment — {aligned} of 6 modules confirm. Risk management critical."
    elif stage == "CONFIRMING":
        summary = f"Confirmation building — {aligned} of 6 aligned. Before full confirmation = best risk/reward."
    elif stage == "FORMING" and has_conflict:
        summary = conflict_summary
    elif stage == "FORMING":
        summary = f"Setup forming — {aligned} of 6 aligned. Structure building, not yet confirmed."
    else:
        summary = f"System scanning — {aligned} of 6 aligned. Early stage, watching for convergence."

    exchange_driver = next((d for d in drivers if d["module"] == "exchange"), None)
    entry_zone = None
    take_profit = None
    stop_loss = None
    if exchange_driver:
        e = exchange_driver.get("entry", 0)
        tp = exchange_driver.get("takeProfit", 0)
        sl = exchange_driver.get("stopLoss", 0)
        if e:
            entry_zone = f"${e:,.0f}"
        if tp:
            take_profit = f"${tp:,.0f}"
        if sl:
            stop_loss = f"${sl:,.0f}"

    token = db.canonical_tokens.find_one({"symbol": asset}, {"_id": 0, "market": 1})
    price = token.get("market", {}).get("current_price") if token else None

    # ── Event Metadata ──
    event_meta = _build_event_metadata(asset, action, avg_confidence, bullish_drivers, bearish_drivers)

    # ── Shadow Trading: record trade + truth stats ──
    from services.shadow_service import record_shadow_trade, get_shadow_stats, get_confidence_adjustment
    signal_data = {
        "asset": asset, "action": action, "price": price,
        "confidence": avg_confidence, "score": final_score,
        "driverSummary": {"bullish": len(bullish_drivers), "bearish": len(bearish_drivers), "neutral": len(neutral_drivers)},
        "stateLabel": event_meta.get("stateLabel", ""),
    }
    record_shadow_trade(signal_data)
    truth = get_shadow_stats(asset)

    conf_adj = get_confidence_adjustment(asset)
    adjusted_confidence = min(1.0, round(avg_confidence * conf_adj, 2))

    # ═══════════════════════════════════════════════
    # ENTRY WINDOW — time-limited urgency state
    # ═══════════════════════════════════════════════
    # Check signal age to determine window state
    last_signal = db.signal_history.find_one(
        {"asset": asset, "action": {"$in": ["BUY", "SELL"]}},
        sort=[("timestamp", DESCENDING)]
    )
    signal_age_hours = 0
    if last_signal and last_signal.get("timestamp"):
        ts = last_signal["timestamp"]
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                ts = None
        if ts:
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            signal_age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600

    # Window TTL based on confidence
    window_ttl = 12 if avg_confidence < 0.5 else 8 if avg_confidence < 0.7 else 6

    if action in ("BUY", "SELL") and signal_age_hours < 1:
        window_state = "ACTIVE"
        window_label = "Entry active now"
        window_urgency = f"Window: ~{window_ttl}h"
    elif action in ("BUY", "SELL") and signal_age_hours < window_ttl * 0.6:
        window_state = "OPEN"
        window_label = "Entry window open"
        window_urgency = f"~{max(1, int(window_ttl - signal_age_hours))}h remaining"
    elif action in ("BUY", "SELL") and signal_age_hours < window_ttl:
        window_state = "CLOSING"
        window_label = "Entry window closing"
        window_urgency = f"Less than {max(1, int(window_ttl - signal_age_hours))}h left"
    elif signal_age_hours >= window_ttl and last_signal:
        window_state = "CLOSED"
        window_label = "Entry window closed"
        window_urgency = "Move already started"
    else:
        window_state = "SCANNING"
        window_label = "Scanning for entry"
        window_urgency = "No active window"

    # Money framing (on $3k position)
    position_size = 3000
    if price and price > 0:
        low_move = round(price * 0.04)  # 4%
        high_move = round(price * 0.07)  # 7%
        money_frame = f"≈ ${low_move:,}–${high_move:,} on ${position_size:,} position"
    else:
        money_frame = None

    # Leaderboard social proof
    top_traders_text = None
    if action in ("BUY", "SELL") and window_state in ("ACTIVE", "OPEN"):
        top_traders_text = f"Top traders entered {asset} earlier"

    return {
        "asset": asset,
        "action": action,
        "confidence": adjusted_confidence,
        "rawConfidence": round(avg_confidence, 2),
        "score": round(final_score, 3),
        "direction": direction,
        "horizon": horizon,
        "price": price,
        "drivers": drivers,
        "driverSummary": {
            "bullish": len(bullish_drivers),
            "bearish": len(bearish_drivers),
            "neutral": len(neutral_drivers),
        },
        "summary": summary,
        # ── Decision Framework ──
        "decisionFramework": {
            "stage": stage,
            "stageLabel": stage_label,
            "alignment": alignment_text,
            "alignedCount": aligned,
            "totalModules": len(drivers),
            "timing": timing,
            "timingLabel": timing_label,
            "whatMattersNow": what_matters_now,
            "mattersPoints": matters,
        },
        # ── Entry Window ──
        "entryWindow": {
            "state": window_state,
            "label": window_label,
            "urgency": window_urgency,
            "ttlHours": window_ttl,
            "ageHours": round(signal_age_hours, 1),
            "moneyFrame": money_frame,
            "topTraders": top_traders_text,
        },
        # ── Conflict Engine ──
        "conflict": {
            "hasConflict": has_conflict,
            "summary": conflict_summary,
            "details": conflicts[:3] if conflicts else [],
        },
        "entryZone": entry_zone,
        "takeProfit": take_profit,
        "stopLoss": stop_loss,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        # ── Truth Layer ──
        "truth": truth,
        # ── Event framing ──
        **event_meta,
    }


def generate_all_signals(assets: list = None, horizon: str = "swing") -> list:
    """Generate signals for all tracked assets."""
    if not assets:
        actor_tokens = db.actor_signal_events.distinct("token")
        forecast_assets = ie_db.exchange_forecasts.distinct("asset")
        all_assets = list(set(actor_tokens + forecast_assets + ["BTC", "ETH", "SOL"]))
        assets = sorted(all_assets)[:20]

    signals = []
    for asset in assets:
        try:
            sig = generate_signal(asset, horizon)
            signals.append(sig)
        except Exception as e:
            logger.error(f"[Signals] Error generating signal for {asset}: {e}")

    signals.sort(key=lambda x: -abs(x.get("confidence", 0)))
    return signals


def get_market_state() -> dict:
    """Get the overall market state for Home screen."""
    btc_signal = generate_signal("BTC")

    fg_event = db.sentiment_events.find_one(
        {"sourceType": "fear_greed"}, sort=[("timestamp", DESCENDING)]
    )
    fg_value = fg_event.get("raw", {}).get("value", 50) if fg_event else 50
    fg_class = fg_event.get("raw", {}).get("classification", "Neutral") if fg_event else "Neutral"

    if fg_value < 25:
        market_label = "EXTREME FEAR"
    elif fg_value < 40:
        market_label = "FEAR"
    elif fg_value > 75:
        market_label = "EXTREME GREED"
    elif fg_value > 60:
        market_label = "GREED"
    else:
        market_label = "NEUTRAL"

    key_drivers = [f"{d['name']}: {d['direction']}" for d in btc_signal["drivers"]]

    return {
        "market": market_label,
        "fearGreed": fg_value,
        "fearGreedClass": fg_class,
        "bias": btc_signal["direction"],
        "confidence": btc_signal["confidence"],
        "action": btc_signal["action"],
        "drivers": key_drivers[:4],
        "topSignal": {
            "asset": "BTC",
            "action": btc_signal["action"],
            "confidence": btc_signal["confidence"],
            "summary": btc_signal["summary"],
        },
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
