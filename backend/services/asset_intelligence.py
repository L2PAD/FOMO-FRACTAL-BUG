"""
Asset Intelligence Service — Every asset has a status, score, and story.

Provides:
  - System Picks (top 3-5 by MetaBrain scoring)
  - Asset Intelligence (deep dive per asset)
  - Watchlist persistence
  - Search with live status
"""

import os
import logging
from datetime import datetime, timezone
from pymongo import MongoClient
from services.meta_brain_service import build_snapshot

logger = logging.getLogger(__name__)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "test_database")
client = MongoClient(MONGO_URL)
db = client[DB_NAME]

ALL_ASSETS = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK",
              "MATIC", "UNI", "ATOM", "LTC", "FIL", "NEAR", "APT", "ARB", "OP", "INJ"]

STATUSES = {
    "CORE": {"label": "Core Position", "color": "#FFFFFF", "icon": "shield-checkmark"},
    "EARLY": {"label": "Early Signal", "color": "#00E676", "icon": "flash"},
    "CONFIRMATION": {"label": "Confirmation", "color": "#448AFF", "icon": "checkmark-circle"},
    "ROTATION": {"label": "Rotation Setup", "color": "#FF9100", "icon": "swap-horizontal"},
    "TRAP": {"label": "Trap", "color": "#FF5252", "icon": "warning"},
    "NEUTRAL": {"label": "Neutral", "color": "#666", "icon": "ellipse"},
}


def _classify_asset(snapshot: dict, asset: str) -> dict:
    """Classify an asset into a status with score and reasons."""
    signal = snapshot.get("signal", {})
    drivers = snapshot.get("drivers", {})
    trade = snapshot.get("trade", {})

    action = signal.get("action", "WAIT")
    confidence = signal.get("confidence", 0)
    fg = drivers.get("sentiment", {}).get("fearGreed", 50)
    social = drivers.get("social", {})
    exchange = drivers.get("exchange", {})
    netflow = drivers.get("onchain", {}).get("stablecoinNetflow", 0)

    # Score
    score = confidence * 0.4
    reasons = []

    # Exchange contribution
    exch_dir = exchange.get("direction", "Neutral")
    exch_conf = exchange.get("confidence", 0)
    if exch_dir == "Bullish":
        score += exch_conf * 0.2
        reasons.append("Exchange flows positive")
    elif exch_dir == "Bearish":
        score += exch_conf * 0.15
        reasons.append("Exchange distribution active")

    # Sentiment
    if fg <= 25:
        score += 0.15
        reasons.append("Extreme fear — contrarian zone")
    elif fg <= 35:
        score += 0.08
        reasons.append("Fear rising — opportunity forming")
    elif fg >= 75:
        score += 0.1
        reasons.append("Euphoria — caution zone")
    elif fg >= 65:
        score += 0.05
        reasons.append("Greed rising")

    # Social
    if social.get("direction") == "Bullish" and social.get("confidence", 0) > 0.4:
        score += 0.1
        reasons.append("Social attention accelerating")

    # Onchain
    if netflow and netflow > 5_000_000:
        score += 0.08
        reasons.append("Capital inflow detected")
    elif netflow and netflow < -5_000_000:
        score += 0.05
        reasons.append("Capital outflow — watch closely")

    if not reasons:
        reasons.append("No strong signals yet")

    # Status classification
    if asset == "BTC":
        status = "CORE"
    elif fg >= 70 and action == "SELL":
        status = "TRAP"
    elif fg <= 30 and action == "BUY":
        status = "EARLY"
    elif social.get("direction") == "Bullish" and social.get("confidence", 0) > 0.4:
        status = "EARLY"
    elif exch_dir == "Bullish" and confidence > 0.4:
        status = "CONFIRMATION"
    elif netflow and abs(netflow) > 5_000_000:
        status = "ROTATION"
    elif score > 0.3:
        status = "EARLY"
    else:
        status = "NEUTRAL"

    # Direction
    if action == "BUY":
        direction = "LONG"
    elif action == "SELL":
        direction = "SHORT"
    else:
        direction = "LONG" if score > 0.25 else "NEUTRAL"

    status_meta = STATUSES.get(status, STATUSES["NEUTRAL"])

    return {
        "symbol": asset,
        "status": status,
        "statusLabel": status_meta["label"],
        "statusColor": status_meta["color"],
        "statusIcon": status_meta["icon"],
        "score": round(score, 2),
        "confidence": round(confidence * 100),
        "direction": direction,
        "action": action,
        "reasons": reasons[:3],
        "shortReason": reasons[0] if reasons else "No signal",
    }


def get_system_picks() -> list[dict]:
    """Get top 3-5 system-recommended assets. Uses cache for speed."""
    # Check cache (60 sec TTL)
    cache_doc = db.cache.find_one({"key": "system_picks"})
    if cache_doc:
        ts = cache_doc.get("ts")
        if ts:
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - ts).total_seconds()
            if age < 120:  # 2 min cache
                return cache_doc.get("picks", [])

    # Only check core assets for speed (BTC, ETH, SOL + top 2)
    picks = []
    for asset in ["BTC", "ETH", "SOL", "DOGE", "LINK"]:
        try:
            snap = build_snapshot(asset)
            if not snap.get("ok"):
                continue
            classified = _classify_asset(snap, asset)
            picks.append(classified)
        except Exception as e:
            logger.warning(f"System pick failed for {asset}: {e}")

    picks.sort(key=lambda p: -p["score"])

    result = []
    used_statuses = set()
    for p in picks:
        if len(result) >= 4:
            break
        if p["status"] not in used_statuses or len(result) < 3:
            result.append(p)
            used_statuses.add(p["status"])

    # Cache result
    try:
        db.cache.update_one(
            {"key": "system_picks"},
            {"$set": {"picks": result, "ts": datetime.now(timezone.utc)}},
            upsert=True,
        )
    except Exception:
        pass

    return result


def get_asset_intelligence(symbol: str) -> dict:
    """Get deep intelligence for a specific asset."""
    snap = build_snapshot(symbol)
    if not snap.get("ok"):
        return {"ok": False, "error": "Asset not found"}

    classified = _classify_asset(snap, symbol)
    drivers = snap.get("drivers", {})
    trade = snap.get("trade", {})
    signal = snap.get("signal", {})

    # Parse entry price
    entry_raw = trade.get("entry", "")
    if isinstance(entry_raw, str):
        entry_clean = entry_raw.replace("$", "").replace(",", "").strip()
        try:
            entry_num = float(entry_clean)
        except (ValueError, TypeError):
            entry_num = 0
    else:
        entry_num = float(entry_raw) if entry_raw else 0

    # Build narrative
    status = classified["status"]
    if status == "CORE":
        narrative = f"{symbol} is the market anchor.\nSmart money starts here."
    elif status == "EARLY":
        narrative = f"{symbol} is quiet.\nPositioning is not."
    elif status == "CONFIRMATION":
        narrative = f"{symbol} is confirming.\nMomentum building."
    elif status == "TRAP":
        narrative = f"Everyone's in {symbol}.\nThat's the risk."
    elif status == "ROTATION":
        narrative = f"Capital rotating into {symbol}.\nBeta play forming."
    else:
        narrative = f"{symbol} is neutral.\nNo clear edge yet."

    # Module breakdown
    modules = []
    exch = drivers.get("exchange", {})
    modules.append({
        "name": "Exchange",
        "direction": exch.get("direction", "Neutral"),
        "confidence": round(exch.get("confidence", 0) * 100),
        "reason": exch.get("reason", "No data"),
    })

    sent = drivers.get("sentiment", {})
    fg = sent.get("fearGreed", 50)
    modules.append({
        "name": "Sentiment",
        "direction": "Bullish" if fg <= 30 else "Bearish" if fg >= 70 else "Neutral",
        "confidence": fg,
        "reason": f"Fear & Greed: {fg}",
    })

    social = drivers.get("social", {})
    modules.append({
        "name": "Social",
        "direction": social.get("direction", "Neutral"),
        "confidence": round(social.get("confidence", 0) * 100),
        "reason": "Attention " + ("rising" if social.get("direction") == "Bullish" else "flat"),
    })

    onchain = drivers.get("onchain", {})
    netflow = onchain.get("stablecoinNetflow", 0)
    modules.append({
        "name": "On-Chain",
        "direction": "Bullish" if netflow and netflow > 0 else "Bearish" if netflow and netflow < 0 else "Neutral",
        "confidence": min(abs(netflow or 0) / 20_000_000 * 100, 100),
        "reason": f"Netflow: {'$' + str(round(netflow/1e6, 1)) + 'M' if netflow else 'No data'}",
    })

    # Trade setup
    move_pct = max(classified["score"] * 0.15, 0.03)
    direction = classified["direction"]
    if direction == "LONG" and entry_num:
        target = round(entry_num * (1 + move_pct), 2)
        invalidation = round(entry_num * (1 - move_pct * 0.4), 2)
    elif direction == "SHORT" and entry_num:
        target = round(entry_num * (1 - move_pct), 2)
        invalidation = round(entry_num * (1 + move_pct * 0.4), 2)
    else:
        target = 0
        invalidation = 0

    def fmt(p):
        if not p:
            return "—"
        return f"${p:,.0f}" if p >= 1000 else f"${p:.2f}"

    horizon = signal.get("horizon", "swing")
    horizon_map = {"scalp": "15m", "intraday": "4H", "swing": "1D", "position": "1W", "macro": "1M"}

    return {
        "ok": True,
        "symbol": symbol,
        **classified,
        "narrative": narrative,
        "modules": modules,
        "tradeSetup": {
            "direction": direction,
            "entry": fmt(entry_num),
            "entryRaw": entry_num,
            "target": fmt(target),
            "invalidation": fmt(invalidation),
            "expectedMove": f"{'+' if direction == 'LONG' else '-'}{round(move_pct * 100, 1)}%",
            "tf": horizon_map.get(horizon, "1D"),
            "horizon": horizon,
        },
        "portfolioRole": classified["statusLabel"],
    }


# ═══════════════════════════════════════════
#  WATCHLIST
# ═══════════════════════════════════════════

def get_watchlist(user_id: str) -> list[str]:
    """Get user's watchlist."""
    doc = db.watchlists.find_one({"userId": user_id})
    if doc:
        return doc.get("assets", [])
    return ["BTC", "ETH", "SOL"]  # Default


def add_to_watchlist(user_id: str, symbol: str) -> list[str]:
    """Add asset to watchlist."""
    symbol = symbol.upper()
    db.watchlists.update_one(
        {"userId": user_id},
        {"$addToSet": {"assets": symbol}, "$set": {"updatedAt": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return get_watchlist(user_id)


def remove_from_watchlist(user_id: str, symbol: str) -> list[str]:
    """Remove asset from watchlist."""
    symbol = symbol.upper()
    db.watchlists.update_one(
        {"userId": user_id},
        {"$pull": {"assets": symbol}, "$set": {"updatedAt": datetime.now(timezone.utc)}},
    )
    return get_watchlist(user_id)


def search_assets(query: str) -> list[dict]:
    """Search assets with live status."""
    q = query.upper().strip()
    if not q:
        return []

    matches = [a for a in ALL_ASSETS if q in a][:8]
    results = []
    for asset in matches:
        try:
            snap = build_snapshot(asset)
            if snap.get("ok"):
                results.append(_classify_asset(snap, asset))
            else:
                results.append({"symbol": asset, "status": "NEUTRAL", "statusLabel": "Neutral",
                                "statusColor": "#666", "statusIcon": "ellipse", "score": 0,
                                "confidence": 0, "direction": "NEUTRAL", "action": "WAIT",
                                "reasons": ["No data"], "shortReason": "No data"})
        except Exception:
            results.append({"symbol": asset, "status": "NEUTRAL", "statusLabel": "Neutral",
                            "statusColor": "#666", "statusIcon": "ellipse", "score": 0,
                            "confidence": 0, "direction": "NEUTRAL", "action": "WAIT",
                            "reasons": ["Loading..."], "shortReason": "Loading..."})

    return results
