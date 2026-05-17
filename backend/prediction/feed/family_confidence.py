"""
Family Confidence Service — returns historical reliability for a market family.

Uses in-memory cache (5min TTL) to avoid DB hits on every request.
Applies Bayesian shrinkage normalization for small sample sizes.

Pipeline position: After base decision, before effective confidence.
"""
import time
import logging

logger = logging.getLogger("feed.family_confidence")

# In-memory cache: familyKey → {data, ts}
_cache: dict[str, dict] = {}
CACHE_TTL = 300  # 5 min


def get_family_confidence(family_key: str, db) -> dict:
    """Get historical reliability for a family.

    Returns:
        accuracy: float | None (normalized)
        strength: STRONG | MEDIUM | WEAK | UNKNOWN
        calibration: GOOD | OVER | UNDER | UNKNOWN
        sampleSize: int
    """
    if not family_key or db is None:
        return _unknown(0)

    # Check cache
    cached = _cache.get(family_key)
    if cached and (time.time() - cached["ts"]) < CACHE_TTL:
        return cached["data"]

    # Query family_performance collection
    try:
        data = db.family_performance.find_one(
            {"type": "family", "family_key": family_key},
            {"_id": 0}
        )
    except Exception as e:
        logger.debug(f"Family confidence DB error: {e}")
        return _unknown(0)

    if not data or data.get("sample_size", 0) < 3:
        result = _unknown(data.get("sample_size", 0) if data else 0)
        _cache[family_key] = {"data": result, "ts": time.time()}
        return result

    sample_size = data.get("sample_size", 0)
    raw_accuracy = data.get("correct_rate", 0.5)

    # Bayesian shrinkage normalization — prevent 3/3 = 100% → STRONG
    accuracy = _normalize_accuracy(raw_accuracy, sample_size)

    # Calibration error from family data
    avg_cal_error = data.get("avg_calibration_error", 0)
    avg_confidence = data.get("avg_confidence", 0.5)

    # Strength classification
    if sample_size < 10:
        strength = "UNKNOWN"
    elif accuracy > 0.60 and avg_cal_error < 0.08:
        strength = "STRONG"
    elif accuracy > 0.52:
        strength = "MEDIUM"
    else:
        strength = "WEAK"

    # Calibration classification
    if sample_size < 10:
        calibration = "UNKNOWN"
    elif avg_cal_error < 0.06:
        calibration = "GOOD"
    elif avg_confidence > accuracy:
        calibration = "OVER"
    else:
        calibration = "UNDER"

    result = {
        "accuracy": round(accuracy, 4),
        "strength": strength,
        "calibration": calibration,
        "sample_size": sample_size,
    }

    _cache[family_key] = {"data": result, "ts": time.time()}
    return result


def _normalize_accuracy(accuracy: float, sample_size: int) -> float:
    """Bayesian shrinkage: pull extreme values toward 0.5 for small samples.

    With n < 20, shrink toward 50%. This prevents 3/3 = 100% from being "STRONG".
    """
    if sample_size < 20:
        shrink = 0.5
        return accuracy * (1 - shrink) + 0.5 * shrink
    return accuracy


def _unknown(sample_size: int) -> dict:
    return {
        "accuracy": None,
        "strength": "UNKNOWN",
        "calibration": "UNKNOWN",
        "sample_size": sample_size,
    }


def clear_cache():
    """Clear the family confidence cache (for testing)."""
    _cache.clear()
