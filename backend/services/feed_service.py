"""
FEED SERVICE — Polymarket Intelligence Feed
============================================

Reads from Prediction module's Polymarket feed + Exchange forecasts.
No Meta Brain dependency.
"""
import logging
import os
from datetime import datetime, timezone
from pymongo import MongoClient, DESCENDING
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "test_database")
INTEL_DB = "intelligence_engine"

_client = MongoClient(MONGO_URL)
_db = _client[DB_NAME]
_intel_db = _client[INTEL_DB]


def _build_market_cards(events: list, asset: str, limit: int = 10) -> list:
    """Transform Polymarket events into mobile-friendly market cards."""
    cards = []
    for ev in events[:limit]:
        if asset and ev.get("asset_group") and ev.get("asset_group") != asset:
            continue
        
        # Top market from the event
        markets = ev.get("markets", [])
        top_market = markets[0] if markets else {}
        
        # Determine direction from overlay
        overlay = ev.get("overlay", {})
        decision = overlay.get("action", "WATCH") if overlay else "WATCH"
        fair_prob = overlay.get("fair_prob")
        
        yes_price = top_market.get("yes_price", 0.5)
        no_price = top_market.get("no_price", 0.5)
        
        # Calculate edge
        edge_pct = 0
        if fair_prob and yes_price:
            edge_pct = round((fair_prob - yes_price) * 100, 1)
        
        # Direction from edge
        direction = "BULLISH" if edge_pct > 3 else "BEARISH" if edge_pct < -3 else "NEUTRAL"
        
        # Priority
        vol_24h = ev.get("volume_24h", 0)
        if vol_24h > 100000 or abs(edge_pct) > 10:
            priority = "key"
        elif vol_24h > 10000 or abs(edge_pct) > 5:
            priority = "secondary"
        else:
            priority = "noise"
        
        # Impact
        impact = "HIGH" if abs(edge_pct) > 10 else "MED" if abs(edge_pct) > 5 else "LOW"
        
        cards.append({
            "id": ev.get("event_id", ""),
            "type": "polymarket",
            "asset": ev.get("asset_group", "CRYPTO"),
            "source": "prediction",
            "direction": direction,
            "impact": impact,
            "impactPct": edge_pct,
            "title": ev.get("title", ""),
            "summary": top_market.get("question", ev.get("title", "")),
            "timestamp": _format_end_date(ev.get("end_date")),
            "affectsSignal": "supports" if edge_pct > 5 else "weakens" if edge_pct < -5 else "neutral",
            "priority": priority,
            # Polymarket-specific fields
            "market": {
                "eventId": ev.get("event_id"),
                "slug": ev.get("slug", ""),
                "image": ev.get("image", ""),
                "yesPrice": round(yes_price, 3),
                "noPrice": round(no_price, 3),
                "volume": round(ev.get("volume", 0)),
                "volume24h": round(ev.get("volume_24h", 0)),
                "liquidity": round(ev.get("liquidity", 0)),
                "marketsCount": ev.get("markets_count", 1),
                "endDate": ev.get("end_date"),
                "eventType": ev.get("event_type", ""),
                "category": ev.get("category", ""),
                "decision": decision,
                "edge": edge_pct,
                "fairProb": round(fair_prob * 100, 1) if fair_prob else None,
                "topMarkets": [
                    {
                        "id": m.get("market_id"),
                        "question": m.get("question", ""),
                        "yesPrice": round(m.get("yes_price", 0.5), 3),
                        "noPrice": round(m.get("no_price", 0.5), 3),
                        "volume": round(m.get("volume", 0)),
                    }
                    for m in markets[:5]
                ],
            },
            # AI explanation fields
            "whyMatters": _generate_why_matters(ev, edge_pct, decision),
            "modelInterpretation": _generate_interpretation(ev, edge_pct, fair_prob, yes_price),
        })
    
    return cards


def _build_exchange_events(asset: str) -> list:
    """Build signal events from Exchange forecasts."""
    events = []
    forecasts = list(_intel_db.exchange_forecasts.find(
        {"asset": asset.upper()} if asset else {},
    ).sort("createdAt", DESCENDING).limit(9))
    
    for fc in forecasts:
        direction = fc.get("direction", "NEUTRAL")
        conf = fc.get("confidence", 0)
        horizon = fc.get("horizon", "7D")
        entry = fc.get("entryPrice", 0)
        target = fc.get("targetPrice", 0)
        
        move_pct = 0
        if entry and target:
            move_pct = round(((target - entry) / entry) * 100, 2)
        
        d_state = "BULLISH" if "BULL" in direction else "BEARISH" if "BEAR" in direction else "NEUTRAL"
        
        events.append({
            "id": f"exchange_{fc.get('asset')}_{horizon}",
            "type": "signal",
            "asset": fc.get("asset", "BTC"),
            "source": "exchange",
            "direction": d_state,
            "impact": "HIGH" if conf > 0.7 else "MED" if conf > 0.4 else "LOW",
            "impactPct": move_pct,
            "title": f"Exchange {horizon}: {direction}",
            "summary": f"Forecast {fc.get('asset')} {horizon}: {direction} at {int(conf*100)}% confidence. Entry ${entry:,.0f} → Target ${target:,.0f}",
            "timestamp": _format_timestamp(fc.get("createdAt")),
            "affectsSignal": "supports" if d_state == "BULLISH" else "weakens" if d_state == "BEARISH" else "neutral",
            "priority": "key" if conf > 0.5 else "secondary",
        })
    
    return events


def _build_alerts() -> list:
    """Get prediction alerts from MongoDB."""
    alerts_data = list(_db.prediction_alerts.find().sort("created_at", DESCENDING).limit(5))
    alerts = []
    for a in alerts_data:
        alerts.append({
            "id": f"alert_{a.get('market_id')}",
            "type": "alert",
            "asset": "CRYPTO",
            "source": "prediction",
            "direction": "NEUTRAL",
            "impact": "HIGH" if a.get("priority") == "high" else "MED",
            "impactPct": round(a.get("actionability", 0) * 100, 1),
            "title": a.get("title", "Market Alert"),
            "summary": a.get("summary", ""),
            "timestamp": _format_timestamp(a.get("created_at")),
            "affectsSignal": "neutral",
            "priority": "key" if a.get("priority") == "high" else "secondary",
            "alert": {
                "type": a.get("alert_type"),
                "priority": a.get("priority"),
                "actionability": a.get("actionability", 0),
                "transition": a.get("transition", {}),
            },
        })
    return alerts


def get_feed(asset: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Combined feed: Polymarket events + Exchange signals + Alerts.
    """
    all_events = []
    
    # 1. Polymarket events - read from prediction_markets in MongoDB
    try:
        markets_data = list(_db.prediction_markets.find().limit(50))
        
        for m in markets_data:
            market_id = m.get("market_id", "")
            question = m.get("question", "")
            if not question:
                continue
            
            yes_price = m.get("yes_price", 0.5)
            no_price = m.get("no_price", 0.5)
            volume = m.get("volume", 0)
            liquidity = m.get("liquidity", 0)
            action = m.get("decision_action", "WATCH")
            edge = m.get("edge", 0)
            confidence = m.get("decision_confidence", 0)
            fair_prob = m.get("model_prob")
            market_asset = m.get("asset", "CRYPTO")
            
            if asset and asset != "ALL" and market_asset != asset and market_asset != "CRYPTO":
                continue
            
            edge_pct = round(edge * 100, 1) if isinstance(edge, float) and abs(edge) < 1 else round(edge, 1)
            direction = "BULLISH" if edge_pct > 3 else "BEARISH" if edge_pct < -3 else "NEUTRAL"
            
            priority = "key" if abs(edge_pct) > 8 or action == "ENTER" else "secondary" if abs(edge_pct) > 3 or action == "WATCH" else "noise"
            impact = "HIGH" if abs(edge_pct) > 10 else "MED" if abs(edge_pct) > 5 else "LOW"
            
            all_events.append({
                "id": f"pm_{market_id}",
                "type": "polymarket",
                "asset": market_asset,
                "source": "prediction",
                "direction": direction,
                "impact": impact,
                "impactPct": edge_pct,
                "title": question[:80],
                "summary": f"{action} • Yes: {yes_price*100:.0f}¢ | No: {no_price*100:.0f}¢ | Edge: {edge_pct:+.1f}%",
                "timestamp": _format_timestamp(m.get("updatedAt")),
                "affectsSignal": "supports" if edge_pct > 5 else "weakens" if edge_pct < -5 else "neutral",
                "priority": priority,
                "market": {
                    "eventId": market_id,
                    "yesPrice": round(yes_price, 3),
                    "noPrice": round(no_price, 3),
                    "volume": round(volume) if volume else 0,
                    "liquidity": round(liquidity) if liquidity else 0,
                    "decision": action,
                    "edge": edge_pct,
                    "fairProb": round(fair_prob * 100, 1) if fair_prob else None,
                    "confidence": round(confidence * 100) if confidence else 0,
                },
                "whyMatters": _generate_why_matters({"volume_24h": volume, "title": question}, edge_pct, action),
                "modelInterpretation": _generate_interpretation({"title": question}, edge_pct, fair_prob, yes_price),
            })
        
        logger.info(f"[Feed] {len(all_events)} Polymarket events from prediction_markets")
    except Exception as e:
        logger.error(f"[Feed] Polymarket error: {e}")
    
    # 2. Exchange signals
    try:
        exchange_events = _build_exchange_events(asset)
        all_events.extend(exchange_events)
    except Exception as e:
        logger.error(f"[Feed] Exchange events error: {e}")
    
    # 3. Alerts
    try:
        alerts = _build_alerts()
        all_events.extend(alerts)
    except Exception as e:
        logger.error(f"[Feed] Alerts error: {e}")
    
    # Sort by priority then impact
    priority_order = {"key": 0, "secondary": 1, "noise": 2}
    all_events.sort(key=lambda e: (priority_order.get(e.get("priority", "noise"), 9), -abs(e.get("impactPct", 0))))
    
    # Deduplicate by id
    seen = set()
    unique = []
    for e in all_events:
        eid = e.get("id", "")
        if eid not in seen:
            seen.add(eid)
            unique.append(e)
    
    logger.info(f"[Feed] Total: {len(unique)} events for {asset}")
    return unique[:limit]


def get_feed_with_influence(asset: str) -> Dict[str, Any]:
    """Feed + influence data for Intelligence Summary."""
    feed = get_feed(asset, limit=30)
    
    # Calculate influence from events
    bullish = sum(1 for e in feed if e.get("direction") == "BULLISH")
    bearish = sum(1 for e in feed if e.get("direction") == "BEARISH")
    total = len(feed)
    
    direction = "BULLISH" if bullish > bearish else "BEARISH" if bearish > bullish else "NEUTRAL"
    confidence = max(bullish, bearish) / total if total > 0 else 0
    
    return {
        "signals": feed,
        "influence": {
            "direction": direction,
            "confidence": round(confidence, 2),
            "total_events": total,
            "bullish": bullish,
            "bearish": bearish,
        },
    }


def _format_end_date(end_date) -> str:
    """Format end date for display."""
    if not end_date:
        return "—"
    try:
        if isinstance(end_date, str):
            dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        else:
            dt = end_date
        now = datetime.now(timezone.utc)
        diff = dt - now
        if diff.days > 7:
            return f"{diff.days}d"
        elif diff.days > 0:
            return f"{diff.days}d {diff.seconds // 3600}h"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600}h"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60}m"
        else:
            return "ending"
    except Exception:
        return str(end_date)[:10]


def _format_timestamp(ts) -> str:
    """Format a timestamp for display."""
    if not ts:
        return "now"
    try:
        if isinstance(ts, datetime):
            now = datetime.now(timezone.utc)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            diff = now - ts
            if diff.days > 0:
                return f"{diff.days}d ago"
            elif diff.seconds > 3600:
                return f"{diff.seconds // 3600}h ago"
            else:
                return f"{diff.seconds // 60}m ago"
        return str(ts)[:16]
    except Exception:
        return "now"


def _generate_why_matters(event: dict, edge_pct: float, decision: str) -> str:
    """Generate explanation for why this market matters."""
    vol = event.get("volume_24h", 0)
    title = event.get("title", "")
    vol_str = f"${vol:,.0f}" if vol else "low"
    
    if abs(edge_pct) > 10:
        return f"Significant mispricing detected ({edge_pct:+.1f}%). 24h volume: {vol_str}. The market appears to undervalue this outcome."
    elif abs(edge_pct) > 5:
        return f"Moderate edge opportunity ({edge_pct:+.1f}%). Market volume at {vol_str} suggests active trading."
    elif decision == "AVOID":
        return f"Market showing volatility with limited edge. Current spread suggests monitoring, not entry."
    else:
        return f"Tracking market with {vol_str} in 24h volume. Waiting for clearer signal."


def _generate_interpretation(event: dict, edge_pct: float, fair_prob, yes_price: float) -> str:
    """Generate model interpretation."""
    if fair_prob and yes_price:
        return (
            f"Model estimates fair probability at {fair_prob*100:.0f}% vs market price of "
            f"{yes_price*100:.0f}%. Edge: {edge_pct:+.1f}pp. "
            f"{'Potential opportunity' if abs(edge_pct) > 5 else 'Within noise range'}."
        )
    return "Insufficient data for model comparison. Monitoring market dynamics."
