"""
Resolve Timing Helper — daily-bar physics alignment.

Phase X.F (FOMO-ML): with daily bars, bar D becomes "available" only AFTER
D+1 00:00 UTC. So an intraday prediction made on day D should resolve
against bars D+1, D+7, D+30 — at 00:00+30min UTC after the horizon ends.

    resolveAt = ceil_utc_midnight(predictedAt + horizonMs) + 30min

Modes (env RESOLVE_TIMING_MODE):
    "v1" (default) — legacy: resolveAt = predictedAt + horizon  (current prod)
    "v2"           — truth-lane: ceil-midnight + 30min

This module is HELPER-ONLY. It does NOT mutate scheduler/resolver
behaviour. To switch behaviour, set env RESOLVE_TIMING_MODE=v2 AND
explicitly call compute_resolve_at() from scheduler — production path
must be edited deliberately, not implicitly.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

# Horizon definitions (ms) — same as in data_integrity_guard.sh
HORIZON_MS: dict[str, int] = {
    "1D":  86_400_000,
    "24H": 86_400_000,
    "7D":  604_800_000,
    "30D": 2_592_000_000,
}


def _utc(dt: datetime | str) -> datetime:
    """Coerce input to tz-aware UTC datetime."""
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def floor_utc_midnight(dt: datetime | str) -> datetime:
    """Round DOWN to the start of the UTC day."""
    d = _utc(dt)
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


def ceil_utc_midnight_plus(dt: datetime | str, minutes_after: int = 30) -> datetime:
    """Round UP to next UTC midnight, then add `minutes_after` minutes.

    If `dt` is exactly at UTC midnight, ceil = dt + 1 day. This is intentional:
    bar D becomes available after D+1 00:00 UTC, so the resolve must be after.
    """
    d = _utc(dt)
    floor = floor_utc_midnight(d)
    if d <= floor:
        ceil_at_midnight = floor
    else:
        ceil_at_midnight = floor + timedelta(days=1)
    return ceil_at_midnight + timedelta(minutes=minutes_after)


def expected_entry_bar_ts_daily(predicted_at: datetime | str) -> datetime:
    """For ANY intraday prediction made on day D, the latest fully-closed
    daily bar is D-1. Bar D only becomes available after D+1 00:00 UTC.
    """
    floor_d = floor_utc_midnight(predicted_at)
    return floor_d - timedelta(days=1)


def compute_resolve_at(
    predicted_at: datetime | str,
    horizon: str = "1D",
    *,
    mode: str | None = None,
) -> datetime:
    """Single canonical entry point for resolveAt computation.

    Args:
        predicted_at: when the prediction was made.
        horizon: "1D" | "24H" | "7D" | "30D".
        mode: "v1" | "v2"; if None, reads env RESOLVE_TIMING_MODE (default v1).

    Returns:
        resolveAt (tz-aware UTC).
    """
    mode = (mode or os.environ.get("RESOLVE_TIMING_MODE", "v1")).lower()
    horizon_key = (horizon or "1D").upper()
    horizon_ms = HORIZON_MS.get(horizon_key, HORIZON_MS["1D"])

    base = _utc(predicted_at)
    flat = base + timedelta(milliseconds=horizon_ms)

    if mode == "v2":
        return ceil_utc_midnight_plus(flat, minutes_after=30)
    return flat  # v1 — legacy


def diff_modes(predicted_at: datetime | str, horizon: str = "1D") -> dict:
    """Diagnostic: show v1 vs v2 resolveAt for a given prediction."""
    pred = _utc(predicted_at)
    v1 = compute_resolve_at(pred, horizon, mode="v1")
    v2 = compute_resolve_at(pred, horizon, mode="v2")
    delta_h = (v2 - v1).total_seconds() / 3600.0
    return {
        "predicted_at": pred.isoformat(),
        "horizon": horizon.upper(),
        "v1_resolve_at": v1.isoformat(),
        "v2_resolve_at": v2.isoformat(),
        "delta_hours": round(delta_h, 4),
        "expected_entry_bar": expected_entry_bar_ts_daily(pred).isoformat(),
        "active_mode": os.environ.get("RESOLVE_TIMING_MODE", "v1"),
    }
