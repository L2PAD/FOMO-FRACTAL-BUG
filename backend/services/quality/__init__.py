"""
FOMO Truth Lane — Quality Layer (additive-only).

Ported from FOMO-ML/FOMO-ML-2 bash scripts (data_integrity_guard.sh,
accumulation_monitor.sh, pre_truth_check.sh, resolve_timing helper).

Rules:
  - Read-only over brain/resolver/signal logic.
  - Mutates ONLY `prediction_outcomes` (sets `corrupted=true` + reason).
  - Idempotent.
  - Never deletes. Never recomputes resolveAt on existing outcomes.

Env:
  RESOLVE_TIMING_MODE = "v1" (default) | "v2"
    v1 = legacy: resolveAt = predictedAt + horizon
    v2 = truth-lane: resolveAt = ceil_utc_midnight(predictedAt + horizon) + 30min
"""
from .resolve_timing import (
    compute_resolve_at,
    ceil_utc_midnight_plus,
    floor_utc_midnight,
    expected_entry_bar_ts_daily,
    diff_modes,
    HORIZON_MS,
)
from .integrity_guard import IntegrityGuard, integrity_guard
from .accumulation_monitor import AccumulationMonitor, accumulation_monitor
from .pre_truth_check import PreTruthCheck, pre_truth_check

__all__ = [
    "compute_resolve_at",
    "ceil_utc_midnight_plus",
    "floor_utc_midnight",
    "expected_entry_bar_ts_daily",
    "diff_modes",
    "HORIZON_MS",
    "IntegrityGuard",
    "integrity_guard",
    "AccumulationMonitor",
    "accumulation_monitor",
    "PreTruthCheck",
    "pre_truth_check",
]
