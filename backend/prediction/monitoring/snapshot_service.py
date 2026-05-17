"""
Snapshot Service — persists market snapshots for repricing detection.

Stores implied_prob, volume, liquidity, spread at regular intervals.
Computes deltas (1h, 6h, 24h) from stored snapshots.

Collection: prediction_snapshots
"""
import os
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING


def _col():
    db = MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "intelligence_engine")]
    return db["prediction_snapshots"]


def save_snapshot(market_id: str, implied_prob: float, volume: float,
                  liquidity: float, spread: float) -> None:
    """Save a market snapshot."""
    _col().insert_one({
        "market_id": market_id,
        "timestamp": datetime.now(timezone.utc),
        "implied_prob": implied_prob,
        "volume": volume,
        "liquidity": liquidity,
        "spread": spread,
    })


def get_snapshots(market_id: str, hours: int = 24, limit: int = 100) -> list[dict]:
    """Get recent snapshots for a market within the given hour window."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    docs = list(_col().find(
        {"market_id": market_id, "timestamp": {"$gte": cutoff}},
        {"_id": 0},
    ).sort("timestamp", DESCENDING).limit(limit))
    return docs


def compute_deltas(market_id: str, current_prob: float, current_volume: float,
                   current_liquidity: float = 0) -> dict:
    """
    Compute price, volume, and liquidity deltas from stored snapshots.

    Returns:
        dict with delta_1h, delta_6h, delta_24h, volume_delta_1h,
              volume_delta_6h, liquidity_delta_6h, snap_count
    """
    now = datetime.now(timezone.utc)
    snapshots = get_snapshots(market_id, hours=25, limit=200)

    if not snapshots:
        return {
            "delta_1h": 0, "delta_6h": 0, "delta_24h": 0,
            "volume_delta_1h": 0, "volume_delta_6h": 0,
            "liquidity_delta_6h": 0,
            "snap_count": 0,
        }

    delta_1h = _find_delta(snapshots, now, current_prob, hours=1)
    delta_6h = _find_delta(snapshots, now, current_prob, hours=6)
    delta_24h = _find_delta(snapshots, now, current_prob, hours=24)

    vol_delta_1h = _find_volume_delta(snapshots, now, current_volume, hours=1)
    vol_delta_6h = _find_volume_delta(snapshots, now, current_volume, hours=6)
    liq_delta_6h = _find_liquidity_delta(snapshots, now, current_liquidity, hours=6)

    return {
        "delta_1h": round(delta_1h, 4),
        "delta_6h": round(delta_6h, 4),
        "delta_24h": round(delta_24h, 4),
        "volume_delta_1h": round(vol_delta_1h, 4),
        "volume_delta_6h": round(vol_delta_6h, 4),
        "liquidity_delta_6h": round(liq_delta_6h, 4),
        "snap_count": len(snapshots),
    }


def _find_delta(snapshots: list, now: datetime, current: float, hours: int) -> float:
    """Find the price change from ~N hours ago."""
    target = now - timedelta(hours=hours)
    best = None
    best_dist = float("inf")

    for s in snapshots:
        ts = s["timestamp"]
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        dist = abs((ts - target).total_seconds())
        if dist < best_dist:
            best_dist = dist
            best = s

    if not best or best_dist > hours * 3600 * 1.5:
        return 0
    return current - best.get("implied_prob", current)


def _find_volume_delta(snapshots: list, now: datetime, current_vol: float, hours: int) -> float:
    """Find volume change ratio from ~N hours ago."""
    target = now - timedelta(hours=hours)
    best = None
    best_dist = float("inf")

    for s in snapshots:
        ts = s["timestamp"]
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        dist = abs((ts - target).total_seconds())
        if dist < best_dist:
            best_dist = dist
            best = s

    if not best or best_dist > hours * 3600 * 1.5:
        return 0
    old_vol = best.get("volume", 0)
    if old_vol <= 0:
        return 0
    return (current_vol - old_vol) / old_vol


def cleanup_old_snapshots(days: int = 7) -> int:
    """Remove snapshots older than N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = _col().delete_many({"timestamp": {"$lt": cutoff}})
    return result.deleted_count


def _find_liquidity_delta(snapshots: list, now: datetime, current_liq: float, hours: int) -> float:
    """Find liquidity change ratio from ~N hours ago."""
    target = now - timedelta(hours=hours)
    best = None
    best_dist = float("inf")

    for s in snapshots:
        ts = s["timestamp"]
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        dist = abs((ts - target).total_seconds())
        if dist < best_dist:
            best_dist = dist
            best = s

    if not best or best_dist > hours * 3600 * 1.5:
        return 0
    old_liq = best.get("liquidity", 0)
    if old_liq <= 0:
        return 0
    return (current_liq - old_liq) / old_liq
