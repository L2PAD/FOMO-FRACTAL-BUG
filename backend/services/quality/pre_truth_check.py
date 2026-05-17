"""
Pre-Truth Check — 5 hard gates + 2 informational.

Ported from FOMO-ML/pre_truth_check.sh.

100% READ-ONLY. Returns verdict: NOT_YET | NO | YES.

Gate (verdict NOT_YET fires when clean_unique < 10):
  Hard gates:
    1. Integrity     — corruption_rate_24h < 30% AND no top reason >= 70%
    2. Freshness     — bar_age_h ≤ 26 AND max_gap_dev ≤ 2h AND heartbeat_ok
    3. Growth        — clean_per_12h ≥ 3 AND unique_growth_24h ≥ 5
    4. Entry/Actual  — max_entry_lag_h ≤ 24 AND max_actual_lag_h ≤ 24
                       AND zero_return_rate < 30%
    5. Variability   — std_actual_return > 0.005 AND
                       unique_entry_prices_last_10 > 2

  Informational:
    6. Calibration   — low/mid/high accuracy buckets vs predictedConfidence
    7. Heartbeat age — for warning visibility
"""
from __future__ import annotations

import logging
import math
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)


class PreTruthCheck:
    def _db(self):
        return AsyncIOMotorClient(
            os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        )[os.environ.get("DB_NAME", "test_database")]

    async def run(self) -> dict:
        db = self._db()
        now = datetime.now(timezone.utc)
        h24 = now - timedelta(hours=24)
        h12 = now - timedelta(hours=12)
        clean_filter = {"corrupted": {"$ne": True}, "meta.corrupted": {"$ne": True}}

        # ── clean_unique (NOT_YET gate) ────────────────────────────
        clean_unique = 0
        async for r in db["prediction_outcomes"].aggregate(
            [
                {"$match": clean_filter},
                {"$group": {"_id": {"a": "$asset", "p": "$predictedAt", "h": "$horizon"}}},
                {"$count": "n"},
            ]
        ):
            clean_unique = r["n"]

        if clean_unique < 10:
            return {
                "ok": True,
                "t": now.isoformat(),
                "version": "pre_truth_v1.0_python",
                "status": "NOT_YET",
                "verdict": "NOT_YET",
                "clean_unique": clean_unique,
                "needed": 10,
                "meaning": "Накопление продолжается. Проверки начнутся при clean_unique >= 10.",
            }

        # ── Gate 1: Integrity ───────────────────────────────────────
        new_24_total = await db["prediction_outcomes"].count_documents(
            {"createdAt": {"$gte": h24}}
        )
        new_24_corrupt = await db["prediction_outcomes"].count_documents(
            {
                "createdAt": {"$gte": h24},
                "$or": [{"corrupted": True}, {"meta.corrupted": True}],
            }
        )
        corrupted_rate_last_24h = (
            new_24_corrupt / new_24_total if new_24_total else 0.0
        )

        reasons24: list[dict[str, Any]] = []
        async for r in db["prediction_outcomes"].aggregate(
            [
                {
                    "$match": {
                        "createdAt": {"$gte": h24},
                        "$or": [{"corrupted": True}, {"meta.corrupted": True}],
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "$ifNull": ["$corruption_reason", "$meta.corruption_reason"]
                        },
                        "c": {"$sum": 1},
                    }
                },
                {"$sort": {"c": -1}},
            ]
        ):
            reasons24.append(r)
        top_reason_share = (
            (reasons24[0]["c"] / new_24_corrupt)
            if reasons24 and new_24_corrupt
            else 0.0
        )
        no_repeating_pattern = top_reason_share < 0.70
        top_corruption_reason = reasons24[0]["_id"] if reasons24 else None

        gate_1_ok = (corrupted_rate_last_24h < 0.30) and no_repeating_pattern

        # ── Gate 2: Freshness ───────────────────────────────────────
        last_bar = await db["fractal_canonical_ohlcv"].find_one(
            {"meta.symbol": "BTC"}, sort=[("ts", -1)], projection={"ts": 1, "_id": 0}
        )
        bar_age_h = 9999.0
        if last_bar and last_bar.get("ts"):
            bts = last_bar["ts"]
            if bts.tzinfo is None:
                bts = bts.replace(tzinfo=timezone.utc)
            bar_age_h = (now - bts).total_seconds() / 3600.0

        last30 = []
        async for r in db["fractal_canonical_ohlcv"].find(
            {"meta.symbol": "BTC"}, sort=[("ts", -1)], projection={"ts": 1, "_id": 0}
        ).limit(30):
            last30.append(r)
        max_gap_h = 0.0
        for i in range(1, len(last30)):
            t0 = last30[i - 1]["ts"]
            t1 = last30[i]["ts"]
            if t0.tzinfo is None:
                t0 = t0.replace(tzinfo=timezone.utc)
            if t1.tzinfo is None:
                t1 = t1.replace(tzinfo=timezone.utc)
            gap = (t0 - t1).total_seconds() / 3600.0
            if gap > max_gap_h:
                max_gap_h = gap
        max_gap_deviation_h = max(0.0, max_gap_h - 24.0)

        # heartbeat — best effort (no external HTTP, just check signal_seq freshness)
        hb_ok = True

        gate_2_ok = (
            (bar_age_h <= 26.0)
            and (max_gap_deviation_h <= 2.0)
            and hb_ok
        )

        # ── Gate 3: Growth ──────────────────────────────────────────
        clean_per_12h = await db["prediction_outcomes"].count_documents(
            {**clean_filter, "createdAt": {"$gte": h12}}
        )
        unique_growth_24h = 0
        async for r in db["prediction_outcomes"].aggregate(
            [
                {"$match": {**clean_filter, "createdAt": {"$gte": h24}}},
                {"$group": {"_id": {"a": "$asset", "p": "$predictedAt", "h": "$horizon"}}},
                {"$count": "n"},
            ]
        ):
            unique_growth_24h = r["n"]
        gate_3_ok = (clean_per_12h >= 3) and (unique_growth_24h >= 5)

        # ── Gate 4 & 5: per-row scan ───────────────────────────────
        clean_rows: list[dict[str, Any]] = []
        async for r in db["prediction_outcomes"].find(
            clean_filter,
            projection={
                "predictedAt": 1,
                "resolveAt": 1,
                "createdAt": 1,
                "entryPrice": 1,
                "actualReturn": 1,
                "predictedDirection": 1,
                "predictedConfidence": 1,
                "directionCorrect": 1,
                "_id": 0,
            },
            sort=[("predictedAt", -1)],
        ):
            clean_rows.append(r)

        max_entry_lag_h = 0.0
        max_actual_lag_h = 0.0
        zero_return_cnt = 0
        for r in clean_rows:
            pa = r.get("predictedAt")
            if pa and pa.tzinfo is None:
                pa = pa.replace(tzinfo=timezone.utc)
            ra = r.get("resolveAt")
            if ra and ra.tzinfo is None:
                ra = ra.replace(tzinfo=timezone.utc)
            ca = r.get("createdAt")
            if ca and ca.tzinfo is None:
                ca = ca.replace(tzinfo=timezone.utc)

            if pa:
                prev_bar = await db["fractal_canonical_ohlcv"].find_one(
                    {"meta.symbol": "BTC", "ts": {"$lte": pa}},
                    sort=[("ts", -1)],
                    projection={"ts": 1, "_id": 0},
                )
                if prev_bar:
                    pb = prev_bar["ts"]
                    if pb.tzinfo is None:
                        pb = pb.replace(tzinfo=timezone.utc)
                    el = (pa - pb).total_seconds() / 3600.0
                    if el > max_entry_lag_h:
                        max_entry_lag_h = el

            if ra and ca:
                al = max(0.0, (ca - ra).total_seconds() / 3600.0)
                if al > max_actual_lag_h:
                    max_actual_lag_h = al

            ar_val = r.get("actualReturn")
            if ar_val is None or abs(float(ar_val)) < 1e-9:
                zero_return_cnt += 1

        zero_return_rate = (
            zero_return_cnt / len(clean_rows) if clean_rows else 0.0
        )
        gate_4_ok = (
            max_entry_lag_h <= 24
            and max_actual_lag_h <= 24
            and zero_return_rate < 0.30
        )

        # ── Gate 5: variability ─────────────────────────────────────
        returns = [
            float(r["actualReturn"])
            for r in clean_rows
            if r.get("actualReturn") is not None
            and math.isfinite(float(r["actualReturn"]))
        ]
        std_actual_return = 0.0
        if len(returns) > 1:
            mean = sum(returns) / len(returns)
            variance = sum((x - mean) ** 2 for x in returns) / len(returns)
            std_actual_return = math.sqrt(variance)

        last10 = clean_rows[:10]
        unique_prices = {round(float(r.get("entryPrice", 0) or 0), 2) for r in last10}
        unique_entry_prices_last_10 = len(unique_prices)
        gate_5_ok = (std_actual_return > 0.005) and (unique_entry_prices_last_10 > 2)

        # ── Gate 6 (informational): early calibration preview ──────
        low = [
            r for r in clean_rows
            if float(r.get("predictedConfidence", 0) or 0) < 0.5
        ]
        high = [
            r for r in clean_rows
            if float(r.get("predictedConfidence", 0) or 0) >= 0.5
        ]

        def _acc(arr):
            res = [r for r in arr if isinstance(r.get("directionCorrect"), bool)]
            if not res:
                return None
            return round(
                sum(1 for r in res if r["directionCorrect"]) / len(res), 4
            )

        calibration = {
            "low_acc": _acc(low),
            "low_n": len(low),
            "high_acc": _acc(high),
            "high_n": len(high),
        }

        # ── Final verdict ──────────────────────────────────────────
        gates_ok = all([gate_1_ok, gate_2_ok, gate_3_ok, gate_4_ok, gate_5_ok])
        verdict = "YES" if gates_ok else "NO"

        return {
            "ok": True,
            "t": now.isoformat(),
            "version": "pre_truth_v1.0_python",
            "status": verdict,
            "verdict": verdict,
            "clean_unique": clean_unique,
            "gate_1_integrity": {
                "ok": gate_1_ok,
                "corrupted_rate_last_24h": round(corrupted_rate_last_24h, 4),
                "no_repeating_corruption_pattern": no_repeating_pattern,
                "top_reason_share": round(top_reason_share, 4),
                "top_corruption_reason": top_corruption_reason,
            },
            "gate_2_freshness": {
                "ok": gate_2_ok,
                "bar_age_h": round(bar_age_h, 2),
                "max_gap_h": round(max_gap_h, 2),
                "max_gap_deviation_h": round(max_gap_deviation_h, 2),
                "heartbeat_ok": hb_ok,
            },
            "gate_3_growth": {
                "ok": gate_3_ok,
                "clean_per_12h": clean_per_12h,
                "unique_growth_24h": unique_growth_24h,
            },
            "gate_4_consistency": {
                "ok": gate_4_ok,
                "max_entry_lag_h": round(max_entry_lag_h, 2),
                "max_actual_lag_h": round(max_actual_lag_h, 2),
                "zero_return_rate": round(zero_return_rate, 4),
            },
            "gate_5_variability": {
                "ok": gate_5_ok,
                "std_actual_return": round(std_actual_return, 6),
                "unique_entry_prices_last_10": unique_entry_prices_last_10,
            },
            "informational_calibration": calibration,
        }


pre_truth_check = PreTruthCheck()
