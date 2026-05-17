"""
Shadow Trading Service — Truth Layer for FOMO Signals
Records every BUY/SELL signal as virtual trades at 3 horizons (6h/24h/72h).
Resolves outcomes, computes winrate, feeds back into confidence.
"""
import logging
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING
import os

logger = logging.getLogger(__name__)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
_client = MongoClient(MONGO_URL)
_db = _client["fomo_mobile"]
shadows = _db["shadow_trades"]

shadows.create_index([("symbol", 1), ("status", 1)])
shadows.create_index([("resolveAt", 1), ("status", 1)])
shadows.create_index([("symbol", 1), ("resolvedAt", DESCENDING)])
shadows.create_index([("symbol", 1), ("predictedAt", DESCENDING)])

HORIZONS = [
    {"label": "6h", "hours": 6},
    {"label": "24h", "hours": 24},
    {"label": "72h", "hours": 72},
]
DEDUPE_WINDOW_HOURS = 2


def record_shadow_trade(signal: dict) -> list:
    """Record BUY/SELL as shadow trades at multiple horizons. Dedupe by 2h window."""
    action = signal.get("action", "WAIT").upper()
    if action == "WAIT":
        return []

    symbol = signal.get("asset", "BTC")
    price = signal.get("price")
    if not price or price <= 0:
        return []

    now = datetime.now(timezone.utc)
    dedupe_cutoff = (now - timedelta(hours=DEDUPE_WINDOW_HOURS)).isoformat()
    direction = "LONG" if action == "BUY" else "SHORT"

    # Dedupe: skip if same symbol+direction trade created within last 2h
    recent = shadows.find_one({
        "symbol": symbol,
        "direction": direction,
        "predictedAt": {"$gte": dedupe_cutoff},
    })
    if recent:
        return []

    trades = []
    for h in HORIZONS:
        trade = {
            "symbol": symbol,
            "direction": direction,
            "action": action,
            "entryPrice": price,
            "confidence": signal.get("confidence", 0),
            "score": signal.get("score", 0),
            "drivers": signal.get("driverSummary", {}),
            "stateLabel": signal.get("stateLabel", ""),
            "predictedAt": now.isoformat(),
            "resolveAt": (now + timedelta(hours=h["hours"])).isoformat(),
            "status": "PENDING",
            "horizon": h["label"],
        }
        shadows.insert_one(trade)
        trades.append(trade)

    logger.info(f"[Shadow] 3 trades recorded: {symbol} {action} @ {price}")
    return trades


def resolve_matured_trades() -> dict:
    """Resolve trades where resolveAt <= now."""
    now = datetime.now(timezone.utc)
    pending = list(shadows.find({
        "status": "PENDING",
        "resolveAt": {"$lte": now.isoformat()},
    }))

    if not pending:
        return {"resolved": 0}

    resolved_count = 0
    for trade in pending:
        symbol = trade["symbol"]
        entry = trade["entryPrice"]
        exit_price = _get_current_price(symbol)
        if not exit_price:
            continue

        direction = trade.get("direction", "LONG")
        if direction == "LONG":
            pnl_pct = round((exit_price - entry) / entry * 100, 2)
        else:
            pnl_pct = round((entry - exit_price) / entry * 100, 2)

        shadows.update_one({"_id": trade["_id"]}, {"$set": {
            "exitPrice": exit_price,
            "pnlPct": pnl_pct,
            "success": pnl_pct > 0,
            "status": "RESOLVED",
            "resolvedAt": now.isoformat(),
        }})
        resolved_count += 1
        logger.info(f"[Shadow] Resolved: {symbol} {trade.get('horizon')} {direction} pnl={pnl_pct}%")

    return {"resolved": resolved_count}


def get_shadow_stats(symbol: str = None, horizon: str = "24h") -> dict:
    """Get truth stats: winRate, avgPnl, streak, recent outcomes."""
    query = {"status": "RESOLVED", "horizon": horizon}
    if symbol:
        query["symbol"] = symbol

    resolved = list(shadows.find(query).sort("resolvedAt", DESCENDING).limit(50))
    if not resolved:
        return {
            "totalTrades": 0, "winRate": 0, "avgPnl": 0,
            "lastOutcome": None, "streak": 0, "wins": 0, "losses": 0,
            "recent": [], "learning": True,
        }

    wins = [t for t in resolved if t.get("success")]
    total = len(resolved)
    win_rate = round(len(wins) / total, 2) if total else 0
    avg_pnl = round(sum(t.get("pnlPct", 0) for t in resolved) / total, 2) if total else 0

    # Streak
    streak = 0
    if resolved:
        first_result = resolved[0].get("success")
        for t in resolved:
            if t.get("success") == first_result:
                streak += 1
            else:
                break
        if not first_result:
            streak = -streak

    # Recent outcomes (last 10 pnl values)
    recent = [round(t.get("pnlPct", 0), 1) for t in resolved[:10]]

    last = resolved[0]
    last_outcome = {
        "symbol": last.get("symbol"), "direction": last.get("direction"),
        "pnlPct": last.get("pnlPct"), "success": last.get("success"),
        "resolvedAt": last.get("resolvedAt"),
    }

    return {
        "totalTrades": total, "winRate": win_rate, "avgPnl": avg_pnl,
        "lastOutcome": last_outcome, "streak": streak,
        "wins": len(wins), "losses": total - len(wins),
        "recent": recent, "learning": False,
    }


def get_confidence_adjustment(symbol: str) -> float:
    """Feedback loop: adjust confidence based on recent truth."""
    stats = get_shadow_stats(symbol, "24h")
    if stats["totalTrades"] < 5:
        return 1.0  # Not enough data
    wr = stats["winRate"]
    if wr >= 0.65:
        return 1.1
    elif wr >= 0.5:
        return 1.0
    elif wr >= 0.4:
        return 0.9
    else:
        return 0.8


def get_recent_trades(symbol: str = None, limit: int = 20) -> list:
    """Get recent shadow trades."""
    query = {}
    if symbol:
        query["symbol"] = symbol
    return list(shadows.find(query, {"_id": 0}).sort("predictedAt", DESCENDING).limit(limit))


def _get_current_price(symbol: str) -> float | None:
    token = _db.canonical_tokens.find_one({"symbol": symbol}, {"market.current_price": 1})
    if token and token.get("market"):
        return token["market"].get("current_price")
    return None
