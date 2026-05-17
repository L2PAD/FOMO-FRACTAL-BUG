"""
Feed Events Service — Retention Engine.

Generates a stream of events for the Feed screen:
  - Signal stage changes
  - Module alignment shifts
  - Outcomes (closed signals)
  - Pressure events (PRO positioning)
  - Market events (Polymarket)

ALL text comes from backend. UI just renders.
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING

logger = logging.getLogger(__name__)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "fomo_mobile")
client = MongoClient(MONGO_URL)
db = client[DB_NAME]


def _time_ago(dt) -> str:
    """Convert datetime to human-readable time ago."""
    if not dt:
        return "recently"
    now = datetime.now(timezone.utc)
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except Exception:
            return "recently"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    mins = int(delta.total_seconds() / 60)
    if mins < 1:
        return "just now"
    if mins < 60:
        return f"{mins}m ago"
    hours = mins // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def build_feed_events(asset: str = None, limit: int = 30) -> list:
    """Build retention-focused feed events from real system data."""
    events = []
    now = datetime.now(timezone.utc)

    # ══════════════════════════════════════
    # 1. SIGNAL EVENTS — from signal_history
    # ══════════════════════════════════════
    query = {}
    if asset:
        query["asset"] = asset.upper()

    signals = list(db.signal_history.find(query).sort("timestamp", DESCENDING).limit(10))
    for sig in signals:
        action = sig.get("action", "WAIT")
        a = sig.get("asset", "BTC")
        conf = sig.get("confidence", 0)
        ts = sig.get("timestamp")

        if action == "BUY":
            text = f"{a} entering accumulation phase — structure forming"
            icon = "signal"
        elif action == "SELL":
            text = f"{a} distribution detected — bearish pressure building"
            icon = "signal"
        else:
            text = f"{a} scanning — modules not aligned yet"
            icon = "scan"

        events.append({
            "id": f"sig_{sig.get('_id', '')}",
            "type": "signal",
            "icon": icon,
            "text": text,
            "detail": f"Confidence: {int(conf * 100)}%",
            "asset": a,
            "time": _time_ago(ts),
            "timestamp": ts.isoformat() if hasattr(ts, 'isoformat') else str(ts) if ts else now.isoformat(),
            "priority": "high" if action != "WAIT" else "normal",
        })

    # ══════════════════════════════════════
    # 2. OUTCOME EVENTS — closed signals with PnL
    # ══════════════════════════════════════
    closed = list(db.signal_history.find(
        {"outcome": {"$exists": True}, **({} if not asset else {"asset": asset.upper()})}
    ).sort("closeTs", DESCENDING).limit(5))

    for sig in closed:
        pnl = sig.get("pnlPct", 0)
        a = sig.get("asset", "BTC")
        outcome = sig.get("outcome", "")
        ts = sig.get("closeTs")

        if pnl and pnl > 0:
            text = f"Signal closed: {a} +{pnl:.1f}%"
            icon = "outcome_win"
        elif pnl and pnl < 0:
            text = f"Signal closed: {a} {pnl:.1f}%"
            icon = "outcome_loss"
        else:
            text = f"Signal closed: {a} — {outcome}"
            icon = "outcome"

        events.append({
            "id": f"out_{sig.get('_id', '')}",
            "type": "outcome",
            "icon": icon,
            "text": text,
            "detail": f"Outcome: {outcome}" if outcome else None,
            "asset": a,
            "time": _time_ago(ts),
            "timestamp": ts.isoformat() if hasattr(ts, 'isoformat') else str(ts) if ts else now.isoformat(),
            "priority": "high",
        })

    # ══════════════════════════════════════
    # 3. PRESSURE EVENTS — PRO activity (synthetic but useful)
    # ══════════════════════════════════════
    # Generate pressure events from recent shadow trades
    shadow_trades = list(db.shadow_trades.find(
        {**({} if not asset else {"symbol": asset.upper()})}
    ).sort("createdAt", DESCENDING).limit(5))

    for st in shadow_trades:
        a = st.get("symbol", "BTC")
        direction = st.get("direction", "long")
        ts = st.get("createdAt")
        events.append({
            "id": f"pr_{st.get('_id', '')}",
            "type": "pressure",
            "icon": "pressure",
            "text": f"PRO users positioning on {a} — {direction} setup detected",
            "detail": "Entry window active" if direction == "long" else "Risk management active",
            "asset": a,
            "time": _time_ago(ts),
            "timestamp": ts.isoformat() if hasattr(ts, 'isoformat') else str(ts) if ts else now.isoformat(),
            "priority": "medium",
        })

    # ══════════════════════════════════════
    # 4. SENTIMENT EVENTS — from NLP pipeline
    # ══════════════════════════════════════
    cutoff = now - timedelta(hours=24)
    sent_events = list(db.sentiment_events.find(
        {"sourceType": {"$in": ["news", "community"]}, "createdAt": {"$gte": cutoff}}
    ).sort("createdAt", DESCENDING).limit(5))

    for se in sent_events:
        score = se.get("weightedScore", 0.5)
        source = se.get("source", "unknown")
        ts = se.get("createdAt")
        raw = se.get("raw", {})
        title = raw.get("title", "")

        if score > 0.6:
            text = f"Positive sentiment detected from {source}"
        elif score < 0.4:
            text = f"Negative sentiment from {source}"
        else:
            text = f"Sentiment event from {source}"

        events.append({
            "id": f"sent_{se.get('_id', '')}",
            "type": "sentiment",
            "icon": "sentiment",
            "text": text,
            "detail": title[:60] if title else None,
            "asset": se.get("symbol", "CRYPTO"),
            "time": _time_ago(ts),
            "timestamp": ts.isoformat() if hasattr(ts, 'isoformat') else str(ts) if ts else now.isoformat(),
            "priority": "normal",
        })

    # ══════════════════════════════════════
    # 5. PREDICTION EVENTS — from Polymarket
    # ══════════════════════════════════════
    pred_markets = list(db.prediction_markets.find(
        {**({} if not asset else {"asset": {"$regex": asset, "$options": "i"}})}
    ).sort("_id", DESCENDING).limit(5))

    for pm in pred_markets:
        q = pm.get("question", pm.get("title", ""))[:70]
        prob = pm.get("current_price", pm.get("yes_price", 0.5))
        ts = pm.get("updatedAt", pm.get("createdAt"))

        if prob > 0.7:
            text = f"Market expects YES: {q}"
        elif prob < 0.3:
            text = f"Market expects NO: {q}"
        else:
            text = f"Market undecided: {q}"

        events.append({
            "id": f"pred_{pm.get('_id', '')}",
            "type": "prediction",
            "icon": "prediction",
            "text": text,
            "detail": f"Probability: {int(prob * 100)}%",
            "asset": pm.get("asset", "CRYPTO"),
            "time": _time_ago(ts) if ts else "recent",
            "timestamp": ts.isoformat() if hasattr(ts, 'isoformat') else str(ts) if ts else now.isoformat(),
            "priority": "normal",
        })

    # ══════════════════════════════════════
    # 6. USER-AWARE NUDGES — personalized retention events
    # ══════════════════════════════════════
    # Count user's signal views per asset
    view_counts = {}
    user_views = list(db.behavior_events.find(
        {"type": "signal_view", "createdAt": {"$gte": now - timedelta(hours=48)}}
    ).sort("createdAt", DESCENDING).limit(50))

    for v in user_views:
        sym = v.get("data", {}).get("symbol", "")
        if sym:
            view_counts[sym] = view_counts.get(sym, 0) + 1

    # Generate nudges for frequently viewed assets
    for sym, count in sorted(view_counts.items(), key=lambda x: -x[1])[:3]:
        if count >= 3:
            # Check if there was a recent move
            closed_sig = db.signal_history.find_one(
                {"asset": sym, "outcome": {"$exists": True}, "pnlPct": {"$gt": 0}},
                sort=[("closeTs", DESCENDING)]
            )
            if closed_sig and closed_sig.get("pnlPct"):
                pnl = closed_sig["pnlPct"]
                events.append({
                    "id": f"nudge_{sym}_{count}",
                    "type": "nudge",
                    "icon": "nudge",
                    "text": f"You viewed {count} {sym} setups — last one moved +{pnl:.1f}%",
                    "detail": "Don't just watch — position before the next move",
                    "asset": sym,
                    "time": "now",
                    "timestamp": now.isoformat(),
                    "priority": "high",
                })
            else:
                events.append({
                    "id": f"nudge_{sym}_{count}",
                    "type": "nudge",
                    "icon": "nudge",
                    "text": f"You've been watching {sym} — setup still active",
                    "detail": f"Viewed {count} times in 48h. PRO users already inside.",
                    "asset": sym,
                    "time": "now",
                    "timestamp": now.isoformat(),
                    "priority": "high",
                })

    # ══════════════════════════════════════
    # 7. SYSTEM EVENTS — always-on to avoid empty feed
    # ══════════════════════════════════════
    if not events:
        events.append({
            "id": "sys_scan",
            "type": "system",
            "icon": "scan",
            "text": "System scanning market conditions — monitoring for setups",
            "detail": "6 modules active across all assets",
            "asset": "ALL",
            "time": "now",
            "timestamp": now.isoformat(),
            "priority": "normal",
        })

    # Sort by timestamp (newest first), then limit
    events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return events[:limit]
