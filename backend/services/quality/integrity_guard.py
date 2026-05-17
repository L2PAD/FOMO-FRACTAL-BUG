"""
Data Integrity Guard — Clean Data Filter Spec v1.1.

Ported from FOMO-ML/data_integrity_guard.sh.

Mutates ONLY `prediction_outcomes` (sets `corrupted=true` + reason).
NEVER deletes. NEVER mutates anything else. Idempotent.

Rules:
  R1 (semantic): entryBarTs == floor_utc_midnight(predictedAt) - 1 day
                 (the bar D becomes available only after D+1 00:00 UTC,
                  so latest closed bar at any intraday prediction is D-1)
  R2 (strict):   actualBar must cover resolveAt — barEnd ≥ resolveAt - 1h
                 AND |actualBarTs - resolveAt| ≤ MAX_ACTUAL_LAG_H (24h)
  R3:            horizon delta within tolerance window per horizon
  R4:            zero-return artefact (|actualReturn| < 1e-9)
  R5:            duplicate-entry-price clusters (>=3 outcomes with identical
                 entryPrice within 1 hour)
"""
from __future__ import annotations

import logging
import os
from collections import Counter
from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorClient

from .resolve_timing import (
    HORIZON_MS,
    expected_entry_bar_ts_daily,
)

logger = logging.getLogger(__name__)

MAX_ACTUAL_LAG_H = 24

# Hours-window per horizon (entry to resolve must fall in this band)
HORIZON_WIN_H: dict[str, tuple[int, int]] = {
    "1D":  (18, 48),
    "24H": (18, 48),
    "7D":  (144, 192),
    "30D": (696, 744),
}


class IntegrityGuard:
    def _db(self):
        return AsyncIOMotorClient(
            os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        )[os.environ.get("DB_NAME", "test_database")]

    async def _bar_ts_for_price(
        self,
        db,
        symbol: str,
        price: float | None,
        on_or_before_ts: datetime | None,
    ) -> datetime | None:
        """Find the canonical bar whose close == price, ts <= on_or_before_ts.
        Falls back to nearest bar on-or-before."""
        if price is None or on_or_before_ts is None:
            return None
        exact = await db["fractal_canonical_ohlcv"].find_one(
            {
                "meta.symbol": symbol,
                "ohlcv.c": {"$gte": price - 0.005, "$lte": price + 0.005},
                "ts": {"$lte": on_or_before_ts},
            },
            sort=[("ts", -1)],
            projection={"_id": 0, "ts": 1},
        )
        if exact:
            return exact["ts"]
        nearest = await db["fractal_canonical_ohlcv"].find_one(
            {
                "meta.symbol": symbol,
                "ts": {"$lte": on_or_before_ts},
                "ohlcv.c": {"$exists": True, "$ne": None},
            },
            sort=[("ts", -1)],
            projection={"_id": 0, "ts": 1},
        )
        return nearest["ts"] if nearest else None

    async def _scan_outcomes(self, dry_run: bool = False) -> dict:
        """Single sweep over currently-clean prediction_outcomes.

        Returns counts of marked rows + per-rule breakdown.
        Setting `dry_run=True` returns counts WITHOUT updating any documents.
        """
        db = self._db()
        scanned = 0
        marks: dict[str, list] = {
            "invalid_timestamps_or_prices": [],
            "entry_bar_not_found": [],
            "entry_not_latest_closed_bar": [],
            "actual_bar_not_found": [],
            "stale_actual_snapshot": [],
            "horizon_window_violation": [],
            "zero_return_artefact": [],
            "duplicate_entry_price_cluster": [],
        }
        # entryPrice clusters in 1-hour buckets per asset for R5
        clusters: dict[tuple, list] = {}

        cursor = db["prediction_outcomes"].find(
            {"corrupted": {"$ne": True}, "meta.corrupted": {"$ne": True}}
        )
        async for o in cursor:
            scanned += 1
            asset = o.get("asset") or "BTC"
            predicted_at = o.get("predictedAt")
            resolve_at = o.get("resolveAt")
            entry_price = o.get("entryPrice")
            actual_price = o.get("actualPrice")
            horizon = str(o.get("horizon", "1D")).upper()
            actual_return = o.get("actualReturn")

            def _coerce(d):
                if d is None:
                    return None
                if isinstance(d, datetime):
                    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
                if isinstance(d, str):
                    try:
                        return datetime.fromisoformat(d.replace("Z", "+00:00"))
                    except Exception:
                        return None
                return None

            predicted_at = _coerce(predicted_at)
            resolve_at = _coerce(resolve_at)

            if not predicted_at or not resolve_at or entry_price is None or actual_price is None:
                marks["invalid_timestamps_or_prices"].append(o["_id"])
                continue

            entry_bar = await self._bar_ts_for_price(db, asset, float(entry_price), predicted_at)
            actual_bar = await self._bar_ts_for_price(db, asset, float(actual_price), resolve_at)

            # ── R1: semantic entry bar check (daily lane only) ──
            if not entry_bar:
                marks["entry_bar_not_found"].append(o["_id"])
                continue
            if horizon in ("1D", "24H", "7D", "30D"):
                expected_entry = expected_entry_bar_ts_daily(predicted_at)
                if entry_bar.replace(tzinfo=timezone.utc) != expected_entry.replace(tzinfo=timezone.utc):
                    marks["entry_not_latest_closed_bar"].append(o["_id"])
                    continue

            # ── R2: actual bar must cover resolveAt ──
            if not actual_bar:
                marks["actual_bar_not_found"].append(o["_id"])
                continue
            actual_bar_utc = actual_bar.replace(tzinfo=timezone.utc) if actual_bar.tzinfo is None else actual_bar
            bar_end = actual_bar_utc + timedelta(days=1)
            lag_h = (actual_bar_utc - resolve_at).total_seconds() / 3600.0
            if bar_end < resolve_at - timedelta(hours=1):
                marks["stale_actual_snapshot"].append(o["_id"])
                continue
            if abs(lag_h) > MAX_ACTUAL_LAG_H:
                marks["stale_actual_snapshot"].append(o["_id"])
                continue

            # ── R3: horizon delta tolerance ──
            window = HORIZON_WIN_H.get(horizon, HORIZON_WIN_H["1D"])
            delta_h = (resolve_at - predicted_at).total_seconds() / 3600.0
            if not (window[0] <= delta_h <= window[1]):
                marks["horizon_window_violation"].append(o["_id"])
                continue

            # ── R4: zero return artefact ──
            if actual_return is not None and abs(float(actual_return)) < 1e-9:
                marks["zero_return_artefact"].append(o["_id"])
                continue

            # ── R5: cluster bucket ──
            bucket_hour = predicted_at.replace(minute=0, second=0, microsecond=0)
            key = (asset, bucket_hour, round(float(entry_price), 4))
            clusters.setdefault(key, []).append(o["_id"])

        # R5: any cluster with >= 3 outcomes — mark all but first
        for ids in clusters.values():
            if len(ids) >= 3:
                marks["duplicate_entry_price_cluster"].extend(ids[1:])

        # ── Apply marks (additive only) ──
        applied: dict[str, int] = {}
        if not dry_run:
            for reason, ids in marks.items():
                if not ids:
                    applied[reason] = 0
                    continue
                res = await db["prediction_outcomes"].update_many(
                    {"_id": {"$in": ids}},
                    {
                        "$set": {
                            "corrupted": True,
                            "corruption_reason": reason,
                            "corrupted_at": datetime.now(timezone.utc),
                        }
                    },
                )
                applied[reason] = res.modified_count
        else:
            applied = {k: len(v) for k, v in marks.items()}

        total_marked = sum(applied.values())
        return {
            "ok": True,
            "scanned": scanned,
            "total_marked": total_marked,
            "marked_by_reason": applied,
            "dry_run": dry_run,
        }

    async def run(self) -> dict:
        """Apply integrity guard sweep (idempotent)."""
        return await self._scan_outcomes(dry_run=False)

    async def dry_run(self) -> dict:
        """Inspect what would be marked without writing."""
        return await self._scan_outcomes(dry_run=True)

    async def inventory(self) -> dict:
        """Read-only: current corruption breakdown."""
        db = self._db()
        total = await db["prediction_outcomes"].estimated_document_count()
        corrupted = await db["prediction_outcomes"].count_documents(
            {"$or": [{"corrupted": True}, {"meta.corrupted": True}]}
        )
        clean = total - corrupted

        breakdown: Counter = Counter()
        async for row in db["prediction_outcomes"].aggregate(
            [
                {"$match": {"$or": [{"corrupted": True}, {"meta.corrupted": True}]}},
                {
                    "$group": {
                        "_id": {
                            "$ifNull": ["$corruption_reason", "$meta.corruption_reason"]
                        },
                        "n": {"$sum": 1},
                    }
                },
                {"$sort": {"n": -1}},
            ]
        ):
            breakdown[row["_id"] or "unknown"] = row["n"]
        return {
            "ok": True,
            "total": total,
            "clean": clean,
            "corrupted": corrupted,
            "corruption_ratio": round(corrupted / total, 4) if total else 0.0,
            "breakdown": dict(breakdown),
        }


integrity_guard = IntegrityGuard()
