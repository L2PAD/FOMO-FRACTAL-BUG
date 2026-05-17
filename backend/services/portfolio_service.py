"""
Analytical Portfolio Service — Strategy positions, NOT trade execution.

Manages:
  - Portfolio snapshots (system recommendations)
  - Virtual positions (user "opened" analytically)
  - Live PnL calculation
  - Performance tracking
  - History
"""

import os
import logging
from datetime import datetime, timezone
from bson import ObjectId
from pymongo import MongoClient, DESCENDING

logger = logging.getLogger(__name__)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "test_database")
client = MongoClient(MONGO_URL)
db = client[DB_NAME]


def _get_current_price(symbol: str) -> float:
    """Get current price from multiple sources (prioritized)."""
    sym = symbol.upper()

    # 1. Try exchange_observations (real-time from Node.js WebSocket)
    try:
        obs = db.get_collection('exchange_observations').find_one(
            {'symbol': f'{sym}USDT'},
            sort=[('timestamp', DESCENDING)]
        )
        if obs:
            # Price is nested under market.price
            market = obs.get('market', {})
            if isinstance(market, dict):
                price = market.get('price')
                if price and float(price) > 0:
                    return float(price)
    except Exception:
        pass

    # 2. Try meta_brain snapshot
    try:
        from services.meta_brain_service import build_snapshot
        snap = build_snapshot(symbol)
        entry = snap.get("trade", {}).get("entry", "")
        if isinstance(entry, str):
            try:
                val = float(entry.replace("$", "").replace(",", "").strip())
                if val > 0:
                    return val
            except (ValueError, TypeError):
                pass
        if isinstance(entry, (int, float)) and entry > 0:
            return float(entry)
        price = snap.get("price", 0)
        if price and float(price) > 0:
            return float(price)
    except Exception:
        pass

    # 3. Try coingecko_cache
    try:
        cg = db.get_collection('coingecko_cache')
        cg_doc = cg.find_one({'symbol': sym.lower()})
        if cg_doc and cg_doc.get('current_price'):
            return float(cg_doc['current_price'])
    except Exception:
        pass

    return 0


def _str_id(doc):
    """Convert ObjectId to string."""
    if doc and "_id" in doc:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
    return doc


# ═══════════════════════════════════════════
#  PORTFOLIO STRATEGY (current recommendation)
# ═══════════════════════════════════════════

def get_portfolio_strategy(user_id: str) -> dict:
    """Get current portfolio strategy from feed intelligence."""
    from services.feed_intelligence import build_feed_intelligence
    feed = build_feed_intelligence("BTC")
    portfolio = feed.get("portfolio")
    if not portfolio:
        return {"ok": False, "error": "No portfolio available"}

    # Save as snapshot
    snapshot = {
        "userId": user_id,
        "createdAt": datetime.now(timezone.utc),
        "status": "ACTIVE",
        "positions": portfolio.get("positions", []),
        "metrics": portfolio.get("metrics", {}),
        "risk": portfolio.get("risk", {}),
    }

    # Upsert active snapshot
    db.portfolio_snapshots.update_one(
        {"userId": user_id, "status": "ACTIVE"},
        {"$set": snapshot},
        upsert=True,
    )

    snap_doc = db.portfolio_snapshots.find_one({"userId": user_id, "status": "ACTIVE"})
    snap_id = str(snap_doc["_id"]) if snap_doc else ""

    return {
        "ok": True,
        "snapshotId": snap_id,
        **portfolio,
    }


# ═══════════════════════════════════════════
#  OPEN / CLOSE POSITIONS
# ═══════════════════════════════════════════

def open_portfolio(user_id: str, snapshot_id: str = None) -> dict:
    """Open all positions from strategy snapshot."""
    snap = db.portfolio_snapshots.find_one({"userId": user_id, "status": "ACTIVE"})
    if not snap:
        return {"ok": False, "error": "No active strategy"}

    positions_data = snap.get("positions", [])
    opened = []

    for p in positions_data:
        symbol = p.get("asset", "")
        if not symbol:
            continue

        # Check if already open
        existing = db.portfolio_positions.find_one({
            "userId": user_id, "symbol": symbol, "status": "OPEN"
        })
        if existing:
            ex = _str_id(dict(existing))
            for k in ("openedAt", "closedAt"):
                if ex.get(k) and hasattr(ex[k], 'isoformat'):
                    ex[k] = ex[k].isoformat()
            opened.append(ex)
            continue

        entry_price = p.get("entryRaw", 0)
        if not entry_price:
            entry_price = _get_current_price(symbol)

        pos = {
            "userId": user_id,
            "snapshotId": str(snap["_id"]),
            "symbol": symbol,
            "side": p.get("direction", "LONG"),
            "role": p.get("role", "CORE"),
            "roleLabel": p.get("roleLabel", ""),
            "allocation": p.get("allocation", 0),
            "allocationPct": p.get("allocationPct", "0%"),
            "entryPrice": entry_price,
            "currentPrice": entry_price,
            "pnlPct": 0,
            "status": "OPEN",
            "openedAt": datetime.now(timezone.utc),
            "closedAt": None,
        }
        result = db.portfolio_positions.insert_one(pos)
        pos["id"] = str(result.inserted_id)
        if "_id" in pos:
            del pos["_id"]
        # Serialize datetimes
        for k in ("openedAt", "closedAt"):
            if pos.get(k) and hasattr(pos[k], 'isoformat'):
                pos[k] = pos[k].isoformat()
        opened.append(pos)

    return {"ok": True, "positions": opened, "count": len(opened)}


def open_single_position(user_id: str, symbol: str) -> dict:
    """Open a single position from strategy."""
    snap = db.portfolio_snapshots.find_one({"userId": user_id, "status": "ACTIVE"})
    if not snap:
        return {"ok": False, "error": "No active strategy"}

    # Find position in snapshot
    pos_data = None
    for p in snap.get("positions", []):
        if p.get("asset", "").upper() == symbol.upper():
            pos_data = p
            break

    if not pos_data:
        return {"ok": False, "error": f"{symbol} not in current strategy"}

    # Check if already open
    existing = db.portfolio_positions.find_one({
        "userId": user_id, "symbol": symbol.upper(), "status": "OPEN"
    })
    if existing:
        return {"ok": True, "position": _str_id(existing), "already_open": True}

    entry_price = pos_data.get("entryRaw", 0) or _get_current_price(symbol)

    pos = {
        "userId": user_id,
        "snapshotId": str(snap["_id"]),
        "symbol": symbol.upper(),
        "side": pos_data.get("direction", "LONG"),
        "role": pos_data.get("role", "CORE"),
        "roleLabel": pos_data.get("roleLabel", ""),
        "allocation": pos_data.get("allocation", 0),
        "allocationPct": pos_data.get("allocationPct", "0%"),
        "entryPrice": entry_price,
        "currentPrice": entry_price,
        "pnlPct": 0,
        "status": "OPEN",
        "openedAt": datetime.now(timezone.utc),
        "closedAt": None,
    }
    result = db.portfolio_positions.insert_one(pos)
    pos["id"] = str(result.inserted_id)

    return {"ok": True, "position": pos}


def close_position(user_id: str, position_id: str) -> dict:
    """Close a position."""
    try:
        oid = ObjectId(position_id)
    except Exception:
        return {"ok": False, "error": "Invalid position ID"}

    pos = db.portfolio_positions.find_one({"_id": oid, "userId": user_id})
    if not pos:
        return {"ok": False, "error": "Position not found"}

    if pos.get("status") == "CLOSED":
        return {"ok": True, "already_closed": True}

    current = _get_current_price(pos["symbol"])
    entry = pos.get("entryPrice", 0)
    pnl = round((current - entry) / entry * 100, 2) if entry else 0
    if pos.get("side") == "SHORT":
        pnl = -pnl

    db.portfolio_positions.update_one(
        {"_id": oid},
        {"$set": {
            "status": "CLOSED",
            "closedAt": datetime.now(timezone.utc),
            "currentPrice": current,
            "pnlPct": pnl,
        }}
    )

    return {"ok": True, "pnlPct": pnl, "symbol": pos["symbol"]}


# ═══════════════════════════════════════════
#  POSITIONS WITH LIVE PnL
# ═══════════════════════════════════════════

def get_positions(user_id: str, status: str = "OPEN") -> list[dict]:
    """Get positions with live PnL."""
    cursor = db.portfolio_positions.find(
        {"userId": user_id, "status": status.upper()}
    ).sort("openedAt", DESCENDING)

    positions = []
    for doc in cursor:
        pos = _str_id(doc)

        if status.upper() == "OPEN":
            # Update live PnL
            current = _get_current_price(pos["symbol"])
            entry = pos.get("entryPrice", 0)
            if current and entry:
                pnl = round((current - entry) / entry * 100, 2)
                if pos.get("side") == "SHORT":
                    pnl = -pnl
                pos["currentPrice"] = current
                pos["pnlPct"] = pnl

        # Clean datetime for JSON
        for k in ("openedAt", "closedAt"):
            if pos.get(k):
                pos[k] = pos[k].isoformat() if hasattr(pos[k], 'isoformat') else str(pos[k])

        positions.append(pos)

    return positions


# ═══════════════════════════════════════════
#  PERFORMANCE
# ═══════════════════════════════════════════

def get_performance(user_id: str) -> dict:
    """Get portfolio performance stats."""
    open_pos = get_positions(user_id, "OPEN")
    closed_pos = get_positions(user_id, "CLOSED")

    all_pos = open_pos + closed_pos

    total_pnl = 0
    wins = 0
    best = None
    worst = None

    for p in all_pos:
        pnl = p.get("pnlPct", 0)
        alloc = p.get("allocation", 0) / 100 if p.get("allocation") else 1 / max(len(all_pos), 1)
        total_pnl += pnl * alloc

        if pnl > 0:
            wins += 1
        if best is None or pnl > best.get("pnlPct", -999):
            best = p
        if worst is None or pnl < worst.get("pnlPct", 999):
            worst = p

    win_rate = round(wins / len(all_pos) * 100) if all_pos else 0

    return {
        "ok": True,
        "totalPnlPct": round(total_pnl, 2),
        "openCount": len(open_pos),
        "closedCount": len(closed_pos),
        "winRatePct": win_rate,
        "bestPosition": {"symbol": best["symbol"], "pnlPct": best["pnlPct"]} if best else None,
        "worstPosition": {"symbol": worst["symbol"], "pnlPct": worst["pnlPct"]} if worst else None,
        "positions": open_pos,
    }
