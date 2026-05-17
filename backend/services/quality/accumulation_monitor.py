"""
Accumulation Monitor — observability-only (M1-M5 metrics).

Ported from FOMO-ML/accumulation_monitor.sh.

100% READ-ONLY. Does NOT mark or mutate anything.

Metrics:
  M1. clean_per_6h / clean_per_12h / clean_per_24h
  M2. unique_growth_24h (asset, predictedAt, horizon)
  M3. corruption_ratio_24h
  M4. time-since-first-clean / time-since-last-clean
  M5. canonical bar freshness (BTC last bar age, hours)

Plus TRUTH_PROTOCOL gate flags (clean_unique >= 50, etc.).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)


class AccumulationMonitor:
    def _db(self):
        return AsyncIOMotorClient(
            os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        )[os.environ.get("DB_NAME", "test_database")]

    async def snapshot(self) -> dict:
        db = self._db()
        now = datetime.now(timezone.utc)
        h6, h12, h24 = (now - timedelta(hours=n) for n in (6, 12, 24))

        clean_filter = {"corrupted": {"$ne": True}, "meta.corrupted": {"$ne": True}}

        # Core counts
        total = await db["prediction_outcomes"].estimated_document_count()
        clean_all = await db["prediction_outcomes"].count_documents(clean_filter)
        corrupt_all = await db["prediction_outcomes"].count_documents(
            {"$or": [{"corrupted": True}, {"meta.corrupted": True}]}
        )

        # clean_unique = (asset, predictedAt, horizon)
        unique_pipeline_all = [
            {"$match": clean_filter},
            {"$group": {"_id": {"a": "$asset", "p": "$predictedAt", "h": "$horizon"}}},
            {"$count": "n"},
        ]
        clean_unique = 0
        async for r in db["prediction_outcomes"].aggregate(unique_pipeline_all):
            clean_unique = r["n"]

        # M1
        async def _count(filt):
            return await db["prediction_outcomes"].count_documents(filt)

        clean_6 = await _count({**clean_filter, "createdAt": {"$gte": h6}})
        clean_12 = await _count({**clean_filter, "createdAt": {"$gte": h12}})
        clean_24 = await _count({**clean_filter, "createdAt": {"$gte": h24}})

        # M2: unique growth in 24h
        unique_24_pipeline = [
            {"$match": {**clean_filter, "createdAt": {"$gte": h24}}},
            {"$group": {"_id": {"a": "$asset", "p": "$predictedAt", "h": "$horizon"}}},
            {"$count": "n"},
        ]
        unique_growth_24h = 0
        async for r in db["prediction_outcomes"].aggregate(unique_24_pipeline):
            unique_growth_24h = r["n"]

        # M3: corruption ratio (24h window)
        new_24_total = await _count({"createdAt": {"$gte": h24}})
        new_24_corrupt = await _count(
            {
                "createdAt": {"$gte": h24},
                "$or": [{"corrupted": True}, {"meta.corrupted": True}],
            }
        )
        corruption_ratio_24h = (
            round(new_24_corrupt / new_24_total, 3) if new_24_total else None
        )

        # M4: time-since-first/last-clean
        first_clean = await db["prediction_outcomes"].find_one(
            clean_filter, sort=[("createdAt", 1)], projection={"createdAt": 1, "_id": 0}
        )
        last_clean = await db["prediction_outcomes"].find_one(
            clean_filter, sort=[("createdAt", -1)], projection={"createdAt": 1, "_id": 0}
        )
        hours_since_last_clean = None
        if last_clean and last_clean.get("createdAt"):
            lc = last_clean["createdAt"]
            if lc.tzinfo is None:
                lc = lc.replace(tzinfo=timezone.utc)
            hours_since_last_clean = round(
                (now - lc).total_seconds() / 3600.0, 2
            )

        # M5: canonical bar freshness (BTC)
        last_bar = await db["fractal_canonical_ohlcv"].find_one(
            {"meta.symbol": "BTC"}, sort=[("ts", -1)], projection={"ts": 1, "_id": 0}
        )
        bar_age_h = 9999.0
        if last_bar and last_bar.get("ts"):
            bts = last_bar["ts"]
            if bts.tzinfo is None:
                bts = bts.replace(tzinfo=timezone.utc)
            bar_age_h = round((now - bts).total_seconds() / 3600.0, 2)

        # Backlog visibility (meta_brain_outcomes)
        try:
            backlog_btc = await db["meta_brain_outcomes"].count_documents(
                {"asset": "BTC", "resolved": {"$ne": True}}
            )
            backlog_all = await db["meta_brain_outcomes"].count_documents(
                {"resolved": {"$ne": True}}
            )
        except Exception:
            backlog_btc, backlog_all = 0, 0

        # Status classification
        warnings: list[str] = []
        criticals: list[str] = []

        if bar_age_h > 36:
            criticals.append(f"BAR_FRESHNESS_CRITICAL:{bar_age_h}h")
        elif bar_age_h > 26:
            warnings.append(f"BAR_FRESHNESS_WARN:{bar_age_h}h")

        if clean_all > 0:
            if clean_6 == 0:
                warnings.append("NO_CLEAN_6H")
            if clean_12 == 0:
                criticals.append("NO_CLEAN_12H")
            if hours_since_last_clean is not None and hours_since_last_clean > 24:
                criticals.append(f"STALE_LAST_CLEAN:{hours_since_last_clean}h")

        pre_accumulation = clean_all == 0

        if clean_all >= 10:
            if unique_growth_24h < 5:
                warnings.append(f"UNIQUE_GROWTH_DEGRADED:{unique_growth_24h}")
            if unique_growth_24h == 0:
                criticals.append("UNIQUE_GROWTH_BLOCKED")

        if (
            new_24_total >= 5
            and corruption_ratio_24h is not None
            and corruption_ratio_24h > 0.5
        ):
            warnings.append(
                f"HIGH_CORRUPTION_RATIO:{int(corruption_ratio_24h * 100)}%"
            )

        status = "OK"
        if pre_accumulation:
            status = "PRE_ACCUMULATION"
        if warnings:
            status = "WARN"
        if criticals:
            status = "CRITICAL"

        gate = {
            "clean_unique_ge_50": clean_unique >= 50,
            "corruption_ratio_ok": (
                corruption_ratio_24h is None or corruption_ratio_24h < 0.2
            ),
            "bar_freshness_ok": bar_age_h <= 26,
            "growth_stable": unique_growth_24h >= 5 if clean_all >= 50 else None,
        }

        first_clean_at = (
            first_clean["createdAt"].isoformat()
            if first_clean and first_clean.get("createdAt")
            else None
        )
        last_bar_ts = (
            last_bar["ts"].isoformat()
            if last_bar and last_bar.get("ts")
            else None
        )

        return {
            "ok": True,
            "t": now.isoformat(),
            "status": status,
            "pre_accumulation": pre_accumulation,
            "total": total,
            "clean_total": clean_all,
            "clean_unique": clean_unique,
            "corrupt_total": corrupt_all,
            "M1_clean_6h": clean_6,
            "M1_clean_12h": clean_12,
            "M1_clean_24h": clean_24,
            "M2_unique_growth_24h": unique_growth_24h,
            "M3_new_24h_total": new_24_total,
            "M3_new_24h_corrupt": new_24_corrupt,
            "M3_corruption_ratio_24h": corruption_ratio_24h,
            "M4_hours_since_last_clean": hours_since_last_clean,
            "M4_first_clean_at": first_clean_at,
            "M5_bar_freshness_h": bar_age_h,
            "M5_last_bar_ts": last_bar_ts,
            "backlog_btc_unresolved": backlog_btc,
            "backlog_all_unresolved": backlog_all,
            "gate": gate,
            "warnings": warnings,
            "criticals": criticals,
        }


accumulation_monitor = AccumulationMonitor()
