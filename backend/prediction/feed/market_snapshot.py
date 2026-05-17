"""
Market Snapshot — tracks price/liquidity state + freshness.

Stores snapshots in MongoDB for historical analysis.
Tracks freshness: how stale is the current data?
"""
import time
import logging
from datetime import datetime, timezone

logger = logging.getLogger("feed.snapshot")


def build_snapshot(market: dict) -> dict:
    """Build a snapshot from normalized market data."""
    now = datetime.now(timezone.utc)
    return {
        "market_id": market["market_id"],
        "event_id": market.get("event_id", ""),
        "timestamp": now.isoformat(),
        "ts_epoch": time.time(),
        "yes_price": market.get("yes_price", 0),
        "no_price": market.get("no_price", 0),
        "best_bid": market.get("best_bid", 0),
        "best_ask": market.get("best_ask", 0),
        "spread": market.get("spread", 0),
        "volume": market.get("volume", 0),
        "liquidity": market.get("liquidity", 0),
        "source": "gamma",
    }


def compute_freshness(snapshot_ts_epoch: float) -> dict:
    """Compute freshness info from a snapshot timestamp."""
    now = time.time()
    age_seconds = now - snapshot_ts_epoch
    stale = age_seconds > 300  # >5 min = stale

    if age_seconds < 60:
        label = "live"
    elif age_seconds < 180:
        label = "recent"
    elif age_seconds < 600:
        label = "delayed"
    else:
        label = "stale"

    return {
        "age_seconds": round(age_seconds),
        "stale": stale,
        "label": label,
    }
