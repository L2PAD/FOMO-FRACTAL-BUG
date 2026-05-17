"""
Seed `mbrain_shadow_eval` with realistic-looking data so the Phase B
Observability Dashboard becomes statistically meaningful (n ≥ 270).

Strategy
--------
* For each tick we call `evaluate_shadow(...)` (which talks live to the TA
  side-car via the gateway). Then we backdate the resulting row's `ts`
  to fall on a uniform schedule across the past 7 days so the dashboard's
  rolling 1h / 24h / 7d windows all light up.

* Legacy bias/confidence is simulated with a regime-aware random walk so
  the agreement / divergence rates aren't trivially uniform.

* Run order is asset × horizon (so 9 series), 30 ticks each → 270 rows.

* Rate limit: each evaluate_shadow makes 5 HTTP calls upstream. The TA
  side-car has a 200/min limit, so we throttle to keep things stable.

Usage:
    python /app/scripts/seed_shadow_evals.py [--ticks 30] [--clear] [--rps 4]
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import time
from datetime import datetime, timezone, timedelta

# Bootstrap Python path so `modules.*` resolves the same way as the API.
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, "backend", ".env"), override=True)

from pymongo import MongoClient  # noqa: E402

from modules.mbrain_adapters.ta_shadow_fusion import (  # noqa: E402
    evaluate_shadow,
    SHADOW_COLLECTION,
)

DB_NAME = os.environ.get("DB_NAME", "test_database")
ASSETS = ["BTC", "ETH", "SOL"]
HORIZONS = ["24H", "7D", "30D"]


def _mongo():
    return MongoClient(os.environ["MONGO_URL"])[DB_NAME]


def _legacy_walk():
    """Yield (bias, confidence) tuples that drift slowly so we get
    pockets of agreement and pockets of divergence rather than
    iid noise — same behaviour you see in production."""
    bias = random.choice(["bullish", "bearish", "neutral"])
    conf = random.uniform(0.45, 0.75)
    while True:
        # 15% chance per tick to flip bias
        if random.random() < 0.15:
            bias = random.choice(["bullish", "bearish", "neutral"])
        # Confidence drifts ±0.05
        conf = max(0.1, min(0.95, conf + random.uniform(-0.05, 0.05)))
        yield bias, round(conf, 3)


def seed(ticks_per_series: int = 30, clear: bool = False, rps: float = 4.0) -> None:
    db = _mongo()
    col = db[SHADOW_COLLECTION]

    if clear:
        deleted = col.delete_many({}).deleted_count
        print(f"[seed] cleared {deleted} prior rows")

    # Spread `ticks_per_series` ticks uniformly across the last 7 days.
    span_minutes = 60 * 24 * 7
    step_minutes = span_minutes / ticks_per_series
    now = datetime.now(timezone.utc)

    # Ensure mid-frequency density: also pack the last 60 ticks tightly
    # in the past 24h so the 24h window has good resolution.
    dense_minutes = 60 * 24
    dense_step = dense_minutes / max(1, int(ticks_per_series * 0.4))

    total = 0
    failed = 0
    ta_active_n = 0

    walks = {(a, h): _legacy_walk() for a in ASSETS for h in HORIZONS}
    sleep_per_call = 1.0 / max(0.1, rps)

    for tick in range(ticks_per_series):
        # First ~60% of ticks: spread across 7 days
        if tick < int(ticks_per_series * 0.6):
            offset_min = (ticks_per_series - tick) * step_minutes
        else:  # last 40%: dense in last 24h
            local_idx = tick - int(ticks_per_series * 0.6)
            offset_min = (int(ticks_per_series * 0.4) - local_idx) * dense_step

        ts = now - timedelta(minutes=offset_min, seconds=random.randint(0, 60))
        ts_iso = ts.isoformat()

        for asset in ASSETS:
            for horizon in HORIZONS:
                bias, conf = next(walks[(asset, horizon)])
                try:
                    rec = evaluate_shadow(
                        asset=asset,
                        horizon=horizon,
                        legacy_bias=bias,
                        legacy_confidence=conf,
                        persist=True,
                    )
                    rid = rec.get("_id")
                    if rid:
                        from bson import ObjectId
                        col.update_one(
                            {"_id": ObjectId(rid)}, {"$set": {"ts": ts_iso}}
                        )
                    if (rec.get("metrics") or {}).get("ta_active"):
                        ta_active_n += 1
                    total += 1
                except Exception as exc:
                    failed += 1
                    print(f"[seed] tick={tick} asset={asset} h={horizon} ERR: {exc}")
                time.sleep(sleep_per_call)

        if (tick + 1) % 5 == 0:
            print(f"[seed] tick {tick + 1}/{ticks_per_series} → {total} rows, ta_active={ta_active_n} ({100*ta_active_n/max(1,total):.1f}%)")

    final_n = col.count_documents({})
    print(f"[seed] DONE — wrote {total}, failed {failed}, ta_active={ta_active_n} ({100*ta_active_n/max(1,total):.1f}%), collection size: {final_n}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticks", type=int, default=30, help="ticks per (asset×horizon) series")
    ap.add_argument("--clear", action="store_true", help="wipe collection first")
    ap.add_argument("--rps", type=float, default=4.0, help="evaluate_shadow calls per second (each does 5 TA HTTP calls)")
    ns = ap.parse_args()
    seed(ticks_per_series=ns.ticks, clear=ns.clear, rps=ns.rps)

