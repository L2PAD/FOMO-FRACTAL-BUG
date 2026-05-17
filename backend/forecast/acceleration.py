"""
Data Acceleration — Block 11
==============================
Sub-daily bucket system + Information Delta Guard.

Slot windows (UTC):
  00h: 00:00-05:59
  06h: 06:00-11:59
  12h: 12:00-17:59
  18h: 18:00-23:59

Guarantees:
  - 4 generation slots per day per asset
  - Information Delta Guard prevents duplicate-information rows
  - Each row carries quality_score for downstream filtering
  - Overlap groups mark temporally overlapping evaluation windows
"""

from datetime import datetime, timezone

# Slot boundaries: (start_hour, slot_label)
SLOTS = [
    (0, "00h"),
    (6, "06h"),
    (12, "12h"),
    (18, "18h"),
]


def get_current_slot() -> str:
    """Return the current 6-hour slot label (e.g., '06h')."""
    hour = datetime.now(timezone.utc).hour
    for i in range(len(SLOTS) - 1, -1, -1):
        if hour >= SLOTS[i][0]:
            return SLOTS[i][1]
    return SLOTS[0][1]


def get_current_bucket() -> str:
    """Return sub-daily bucket string: 'YYYY-MM-DD_HHh'."""
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    slot = get_current_slot()
    return f"{date_str}_{slot}"


def get_bucket_date(bucket: str) -> str:
    """Extract date portion from bucket (handles both old and new format)."""
    return bucket.split("_")[0]


def get_bucket_slot(bucket: str) -> str:
    """Extract slot from bucket. Returns 'daily' for old format."""
    parts = bucket.split("_")
    return parts[1] if len(parts) > 1 else "daily"


def get_overlap_group(asset: str, horizon: str, bucket: str) -> str:
    """Generate overlap group ID for overlapping evaluation windows."""
    date = get_bucket_date(bucket)
    return f"{asset}_{horizon}_{date}"


def compute_feature_delta(current_features: dict, last_features: dict) -> float:
    """Compute information delta between current and last feature set.

    Returns a float in [0, 1+] where:
      < 0.05 = skip (duplicate information)
      0.05-0.10 = low-quality sample
      > 0.10 = informative sample
    """
    if not current_features or not last_features:
        return 1.0  # No comparison possible → assume informative

    keys = ["ret_1d", "ret_7d", "ret_14d", "volatility", "momentum"]
    deltas = []

    for k in keys:
        curr = current_features.get(k, 0.0)
        prev = last_features.get(k, 0.0)
        if abs(prev) > 1e-8:
            deltas.append(abs(curr - prev) / max(abs(prev), 1e-6))
        else:
            deltas.append(abs(curr - prev) * 100)  # scale small values

    return sum(deltas) / len(deltas) if deltas else 1.0


def compute_quality_score(
    feature_delta: float,
    regime_changed: bool,
    volatility_shift: float,
) -> float:
    """Compute row quality score [0, 1] for dataset filtering.

    quality = 0.4 * feature_delta + 0.3 * regime_change + 0.3 * vol_shift
    """
    fd = min(1.0, feature_delta / 0.20)  # normalize: 0.20 delta → 1.0
    rc = 1.0 if regime_changed else 0.0
    vs = min(1.0, abs(volatility_shift) / 0.5)  # normalize: 0.5 shift → 1.0

    score = 0.4 * fd + 0.3 * rc + 0.3 * vs
    return round(max(0.0, min(1.0, score)), 4)


# Minimum information delta to generate a forecast
MIN_FEATURE_DELTA = 0.03
