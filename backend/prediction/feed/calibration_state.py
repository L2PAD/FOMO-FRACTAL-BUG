"""
Calibration State Service — determines if confidence is overconfident/underconfident.

Uses family-specific calibration buckets with global fallback.
In-memory cache (5min TTL).

Pipeline position: After base decision, alongside family confidence.
"""
import time
import logging

logger = logging.getLogger("feed.calibration_state")

# In-memory cache
_cal_cache: dict[str, dict] = {}
_global_cache: dict = {}
CACHE_TTL = 300  # 5 min


def get_calibration_state(family_key: str, confidence: float, db) -> dict:
    """Get calibration state for a given confidence + family.

    Falls back to global calibration if no family data.

    Returns:
        state: GOOD | OVER | UNDER | UNKNOWN
        adjustment: float (clamped ±0.1)
        adjusted_confidence: float
    """
    if db is None or confidence is None:
        return {"state": "UNKNOWN", "adjustment": 0, "adjusted_confidence": confidence or 0.5}

    conf_num = _conf_to_num(confidence) if isinstance(confidence, str) else confidence

    # Try family-specific buckets first
    buckets = _get_family_buckets(family_key, db)

    # Fallback to global if no family data
    if not buckets:
        buckets = _get_global_buckets(db)

    if not buckets:
        return {"state": "UNKNOWN", "adjustment": 0, "adjusted_confidence": conf_num}

    # Find matching bucket
    bucket = _find_bucket(buckets, conf_num)

    if not bucket or bucket.get("sample_size", 0) < 10:
        return {"state": "UNKNOWN", "adjustment": 0, "adjusted_confidence": conf_num}

    predicted = bucket.get("avg_predicted", conf_num)
    actual = bucket.get("actual_hit_rate", conf_num)
    diff = predicted - actual

    if abs(diff) < 0.05:
        state = "GOOD"
        adjustment = 0
    elif diff > 0.05:
        state = "OVER"
        adjustment = -min(diff, 0.1)  # Cap at -0.1
    else:
        state = "UNDER"
        adjustment = min(abs(diff), 0.1)  # Cap at +0.1

    adjusted = max(0, min(1, conf_num + adjustment))

    return {
        "state": state,
        "adjustment": round(adjustment, 4),
        "adjusted_confidence": round(adjusted, 4),
    }


def _get_family_buckets(family_key: str, db) -> list | None:
    """Get calibration buckets for a family (cached)."""
    if not family_key:
        return None

    cache_key = f"fam:{family_key}"
    cached = _cal_cache.get(cache_key)
    if cached and (time.time() - cached["ts"]) < CACHE_TTL:
        return cached["data"]

    try:
        report = db.calibration_reports.find_one(
            {"type": "latest"},
            {"_id": 0, "by_family": 1}
        )
        if report and report.get("by_family"):
            buckets = report["by_family"].get(family_key)
            _cal_cache[cache_key] = {"data": buckets, "ts": time.time()}
            return buckets
    except Exception as e:
        logger.debug(f"Family calibration lookup error: {e}")

    _cal_cache[cache_key] = {"data": None, "ts": time.time()}
    return None


def _get_global_buckets(db) -> list | None:
    """Get global calibration buckets (cached)."""
    global _global_cache

    if _global_cache and (time.time() - _global_cache.get("ts", 0)) < CACHE_TTL:
        return _global_cache.get("data")

    try:
        report = db.calibration_reports.find_one(
            {"type": "latest"},
            {"_id": 0, "global": 1}
        )
        if report and report.get("global"):
            _global_cache = {"data": report["global"], "ts": time.time()}
            return report["global"]
    except Exception as e:
        logger.debug(f"Global calibration lookup error: {e}")

    _global_cache = {"data": None, "ts": time.time()}
    return None


def _find_bucket(buckets: list, confidence: float) -> dict | None:
    """Find the calibration bucket that contains this confidence value."""
    for b in buckets:
        bucket_label = b.get("bucket", "")
        try:
            parts = bucket_label.split("-")
            if len(parts) == 2:
                lo = float(parts[0])
                hi = float(parts[1])
                if lo <= confidence < hi:
                    return b
        except (ValueError, IndexError):
            pass

    # Fallback: find closest by avg_predicted
    if buckets:
        return min(buckets, key=lambda b: abs(b.get("avg_predicted", 0.5) - confidence))
    return None


def _conf_to_num(conf_str: str) -> float:
    """Convert confidence string to numeric."""
    return {"high": 0.8, "medium": 0.55, "low": 0.3}.get(conf_str, 0.5)


def clear_cache():
    """Clear caches (for testing)."""
    _cal_cache.clear()
    global _global_cache
    _global_cache = {}
