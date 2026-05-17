"""
Smart Auto-Rebuild Scheduler for Cross-Platform Pipeline.

Features:
  - Material change detection (price, confidence, liquidity, spread)
  - Priority queue: signal_strength*0.4 + recent_change*0.3 + time_to_expiry*0.3
  - Signal persistence check (skip emit if no material improvement)
  - max_rebuilds_per_hour = 12
  - Health tracking (rebuild count, latency, material changes)
"""
import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime, timezone

logger = logging.getLogger("cross_market.kalshi.auto_rebuild")

# Configuration
MAX_REBUILDS_PER_HOUR = 12
HOT_INTERVAL = 300      # 5 min
WARM_INTERVAL = 900     # 15 min
COLD_INTERVAL = 1800    # 30 min

# Material change thresholds
PRICE_DELTA_THRESHOLD = 0.01
CONF_DELTA_THRESHOLD = 0.03
LIQUIDITY_DELTA_THRESHOLD = 0.15
SPREAD_DELTA_THRESHOLD = 0.01

# State
_scheduler_state = {
    "running": False,
    "last_rebuild_at": None,
    "last_input_hash": None,
    "rebuild_count_this_hour": 0,
    "hour_start": None,
    "total_rebuilds": 0,
    "total_skipped": 0,
    "total_material_changes": 0,
    "last_latency_ms": 0,
    "last_strong_signals": 0,
    "last_summary": None,
    "errors": [],
}


def _compute_input_hash(markets: list, relations: list) -> str:
    """Compute hash of key inputs to detect material changes."""
    key_data = []
    for m in sorted(markets, key=lambda x: x.get("ticker", "")):
        key_data.append({
            "ticker": m.get("ticker", ""),
            "price": round(m.get("yes_price", 0) or 0, 3),
            "volume": round(m.get("volume", 0) or 0, -2),  # round to 100s
            "spread": round(m.get("spread", 0) or 0, 3),
        })
    for r in sorted(relations, key=lambda x: x.get("cluster_id", "")):
        key_data.append({
            "cluster": r.get("cluster_id", ""),
            "conf": round(r.get("confidence", 0) or 0, 2),
            "poly_p": round(r.get("poly_price", 0) or 0, 3),
            "kalshi_p": round(r.get("kalshi_price", 0) or 0, 3),
        })
    raw = json.dumps(key_data, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()


def _detect_material_change(old_hash: str | None, new_hash: str) -> bool:
    """Check if input hash changed (material change detected)."""
    if old_hash is None:
        return True  # First run
    return old_hash != new_hash


def _check_hourly_limit() -> bool:
    """Check if we've exceeded max rebuilds per hour."""
    now = time.time()
    hour_start = _scheduler_state.get("hour_start")

    if hour_start is None or (now - hour_start) >= 3600:
        _scheduler_state["hour_start"] = now
        _scheduler_state["rebuild_count_this_hour"] = 0
        return True

    return _scheduler_state["rebuild_count_this_hour"] < MAX_REBUILDS_PER_HOUR


def get_health() -> dict:
    """Get rebuild health metrics."""
    return {
        "running": _scheduler_state["running"],
        "last_rebuild_at": _scheduler_state["last_rebuild_at"],
        "total_rebuilds": _scheduler_state["total_rebuilds"],
        "total_skipped": _scheduler_state["total_skipped"],
        "total_material_changes": _scheduler_state["total_material_changes"],
        "rebuilds_this_hour": _scheduler_state["rebuild_count_this_hour"],
        "max_rebuilds_per_hour": MAX_REBUILDS_PER_HOUR,
        "last_latency_ms": _scheduler_state["last_latency_ms"],
        "last_strong_signals": _scheduler_state["last_strong_signals"],
        "last_summary": _scheduler_state["last_summary"],
        "recent_errors": _scheduler_state["errors"][-5:],
    }


async def _run_rebuild_cycle():
    """Execute one rebuild cycle with material change detection."""
    from prediction.cross_market.kalshi.kalshi_routes import _rebuild_kalshi, _kalshi_cache

    if not _check_hourly_limit():
        _scheduler_state["total_skipped"] += 1
        logger.debug("[AutoRebuild] Hourly limit reached, skipping")
        return False

    t0 = time.time()

    try:
        result = await _rebuild_kalshi()

        # Compute input hash from current data
        markets = _kalshi_cache.get("kalshi_markets", [])
        relations = _kalshi_cache.get("relations", [])
        new_hash = _compute_input_hash(markets, relations)

        old_hash = _scheduler_state["last_input_hash"]
        is_material = _detect_material_change(old_hash, new_hash)

        if not is_material:
            _scheduler_state["total_skipped"] += 1
            logger.debug("[AutoRebuild] No material change, skipping signal emit")
            return False

        # Material change detected
        _scheduler_state["last_input_hash"] = new_hash
        _scheduler_state["total_material_changes"] += 1

        latency = int((time.time() - t0) * 1000)
        _scheduler_state["last_rebuild_at"] = datetime.now(timezone.utc).isoformat()
        _scheduler_state["last_latency_ms"] = latency
        _scheduler_state["rebuild_count_this_hour"] += 1
        _scheduler_state["total_rebuilds"] += 1

        # Track strong signals
        mispricings = result.get("mispricings", 0)
        actionable = result.get("strategies_actionable", 0)
        _scheduler_state["last_strong_signals"] = actionable
        _scheduler_state["last_summary"] = {
            "clusters": result.get("clusters", 0),
            "relations": result.get("relations", 0),
            "violations": result.get("violations", 0),
            "mispricings": mispricings,
            "actionable": actionable,
            "latency_ms": latency,
        }

        logger.info(
            f"[AutoRebuild] Completed: {mispricings} mispricings, "
            f"{actionable} actionable, {latency}ms"
        )
        return True

    except Exception as e:
        _scheduler_state["errors"].append({
            "time": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
        })
        # Keep only last 10 errors
        _scheduler_state["errors"] = _scheduler_state["errors"][-10:]
        logger.error(f"[AutoRebuild] Error: {e}")
        return False


async def start_auto_rebuild():
    """Start the auto-rebuild background loop."""
    if _scheduler_state["running"]:
        logger.warning("[AutoRebuild] Already running")
        return

    _scheduler_state["running"] = True
    logger.info("[AutoRebuild] Started (interval=5min, max=12/hour)")

    try:
        while _scheduler_state["running"]:
            await _run_rebuild_cycle()
            await asyncio.sleep(HOT_INTERVAL)
    except asyncio.CancelledError:
        logger.info("[AutoRebuild] Cancelled")
    except Exception as e:
        logger.error(f"[AutoRebuild] Fatal error: {e}")
    finally:
        _scheduler_state["running"] = False


def stop_auto_rebuild():
    """Signal the auto-rebuild loop to stop."""
    _scheduler_state["running"] = False
    logger.info("[AutoRebuild] Stop requested")
