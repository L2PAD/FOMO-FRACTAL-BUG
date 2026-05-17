#!/usr/bin/env python3
"""
ROLLING FORECAST BACKFILL
==========================
For each past day D in [today-N, today], compute what the fractal cosine-
similarity engine WOULD HAVE PREDICTED using only data available up to D.
Store each forecast as a snapshot in `fractal_rolling_snapshots` collection.

The chart renders these snapshots as a continuous "predicted line" which,
when overlaid on real candles, visually shows where the model diverged
from reality (model says X, market actually did Y).

This is the proper walk-forward visualization the user requested.
"""

from __future__ import annotations

import os
import sys
import math
import hashlib
import argparse
from datetime import datetime, timedelta, timezone

import numpy as np
from pymongo import MongoClient, UpdateOne, ASCENDING, DESCENDING

# ─────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME   = os.environ.get("DB_NAME", "fomo_mobile")
COLL_NAME = "fractal_rolling_snapshots"

ASSET = "BTC"
TIMEFRAME = "1d"
WINDOW_LEN = 120          # current window length for similarity search
FORWARD_DAYS = 30         # how many days each snapshot looks forward
TOP_K = 10                # number of historical analogs to pool
STRIDE_DAYS = 3           # one snapshot every N days back-in-history
DEFAULT_BACKFILL_DAYS = 365  # how far back to backfill
MIN_HISTORY_FOR_MATCH = 180  # minimum candles needed before any analog search
ANALOG_RETURN_CLIP = 0.50    # ±50 % clip on single-analog forward ratio
SOURCE_TAG = "rolling_v1"


# ─────────────────────────────────────────────────────────────────────
# LOADERS
# ─────────────────────────────────────────────────────────────────────
def load_btc_candles(client: MongoClient) -> list[dict]:
    """Load BTC daily candles from fractal_canonical_ohlcv sorted by ts."""
    coll = client[DB_NAME].fractal_canonical_ohlcv
    cursor = coll.find(
        {"meta.symbol": ASSET, "meta.timeframe": TIMEFRAME},
        {"ts": 1, "ohlcv": 1, "_id": 0},
    ).sort("ts", ASCENDING)
    out = []
    for d in cursor:
        ohlcv = d.get("ohlcv") or {}
        ts = d.get("ts")
        if not ts or not ohlcv:
            continue
        try:
            close = float(ohlcv.get("c") or 0)
        except (TypeError, ValueError):
            continue
        if close <= 0:
            continue
        if isinstance(ts, datetime):
            iso = ts.replace(tzinfo=timezone.utc).strftime("%Y-%m-%d") if ts.tzinfo is None else ts.astimezone(timezone.utc).strftime("%Y-%m-%d")
        else:
            iso = str(ts)[:10]
        out.append({"t": iso, "c": close})
    return out


# ─────────────────────────────────────────────────────────────────────
# COSINE-SIMILARITY ENGINE (same maths as Node fractal v2.1)
# ─────────────────────────────────────────────────────────────────────
def log_returns(closes: np.ndarray) -> np.ndarray:
    """Compute daily log returns."""
    return np.diff(np.log(closes))


def find_analogs(
    lr: np.ndarray,
    cur_idx: int,
    window_len: int,
    forward_days: int,
    top_k: int,
) -> list[dict]:
    """
    Find top-K windows of `window_len` log-returns most similar (cosine)
    to the window ending at cur_idx, with constraint that each analog has
    at least `forward_days` future data after its end.
    """
    if cur_idx < window_len:
        return []
    cur = lr[cur_idx - window_len: cur_idx]
    cur_norm = np.linalg.norm(cur)
    if cur_norm == 0:
        return []

    matches: list[tuple[float, int]] = []
    n = lr.size
    last_valid_end = n - forward_days
    min_gap = window_len   # don't look at heavily-overlapping windows
    for end in range(window_len, last_valid_end):
        if abs(end - cur_idx) < min_gap:
            continue
        seg = lr[end - window_len: end]
        sn = np.linalg.norm(seg)
        if sn == 0:
            continue
        sim = float(np.dot(cur, seg) / (cur_norm * sn))
        matches.append((sim, end))
    matches.sort(key=lambda x: -x[0])
    return [{"sim": s, "endIdx": e} for s, e in matches[:top_k]]


def compute_forward_curve(
    closes: np.ndarray,
    analogs: list[dict],
    forward_days: int,
) -> list[float]:
    """Median forward ratio path across analogs."""
    paths = []
    n = closes.size
    for a in analogs:
        ei = int(a["endIdx"])
        if ei + forward_days >= n or ei <= 0:
            continue
        base = float(closes[ei])
        if base <= 0:
            continue
        seg = closes[ei: ei + forward_days + 1]
        if seg.size != forward_days + 1:
            continue
        ratios = seg / base
        ratios = np.clip(
            ratios,
            1.0 - ANALOG_RETURN_CLIP,
            1.0 + ANALOG_RETURN_CLIP,
        )
        paths.append(ratios.astype(float))
    if not paths:
        return []
    stack = np.vstack(paths)
    curve = np.median(stack, axis=0).tolist()
    curve[0] = 1.0
    return curve


# ─────────────────────────────────────────────────────────────────────
# SNAPSHOT BUILDER
# ─────────────────────────────────────────────────────────────────────
def build_snapshot(
    asset: str,
    horizon_days: int,
    as_of_iso: str,
    as_of_price: float,
    forecast_curve: list[float],
    analog_count: int,
) -> dict:
    """Build a snapshot doc matching what the frontend's
    LivePredictionChart.fetchSnapshots() expects."""
    as_of_dt = datetime.strptime(as_of_iso, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    # Build forecast points: day-by-day ratio × as_of_price.
    # Skip day 0 (anchor = as_of_price) → frontend already has that as candle.
    series = []
    for i, ratio in enumerate(forecast_curve):
        ts = (as_of_dt + timedelta(days=i)).strftime("%Y-%m-%dT00:00:00Z")
        series.append({"t": ts, "v": round(as_of_price * float(ratio), 4)})

    if not series:
        return {}

    # Derive a coarse "stance" from forecast direction (last vs first)
    if forecast_curve:
        ret = forecast_curve[-1] - 1.0
        if ret > 0.02:
            stance = "BULLISH"
            conf = min(0.9, 0.5 + abs(ret) * 2)
        elif ret < -0.02:
            stance = "BEARISH"
            conf = min(0.9, 0.5 + abs(ret) * 2)
        else:
            stance = "HOLD"
            conf = 0.5 + abs(ret) * 5
    else:
        stance = "HOLD"
        conf = 0.5

    # Stable hash for dedup
    h = hashlib.sha1(
        f"{asset}|{horizon_days}|{as_of_iso}|{round(as_of_price, 2)}|{round(series[-1]['v'], 2)}".encode()
    ).hexdigest()[:16]

    return {
        "asset":       asset,
        "view":        "hybrid",
        "horizonDays": int(horizon_days),
        "asOf":        as_of_dt.isoformat().replace("+00:00", "Z"),
        "asOfDate":    as_of_iso,
        "asOfPrice":   float(round(as_of_price, 4)),
        "series":      series,
        "metadata": {
            "stance":       stance,
            "confidence":   float(round(conf, 3)),
            "analogCount":  int(analog_count),
            "source":       SOURCE_TAG,
        },
        "hash":      h,
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


# ─────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=DEFAULT_BACKFILL_DAYS,
                    help="how many days back to backfill (default 365)")
    ap.add_argument("--stride", type=int, default=STRIDE_DAYS,
                    help="snapshot every N days (default 3)")
    ap.add_argument("--horizon", type=int, default=FORWARD_DAYS,
                    help="forecast horizon per snapshot (default 30)")
    ap.add_argument("--window", type=int, default=WINDOW_LEN,
                    help="similarity window length (default 120)")
    ap.add_argument("--topk", type=int, default=TOP_K,
                    help="top-K analogs to median (default 10)")
    ap.add_argument("--wipe", action="store_true",
                    help="wipe existing rolling snapshots first")
    args = ap.parse_args()

    print(f"[rolling-backfill] connecting {MONGO_URL}/{DB_NAME}")
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    coll = db[COLL_NAME]
    coll.create_index([("asset", ASCENDING), ("horizonDays", ASCENDING), ("asOfDate", DESCENDING)])

    if args.wipe:
        deleted = coll.delete_many({"metadata.source": SOURCE_TAG})
        print(f"[rolling-backfill] wiped {deleted.deleted_count} existing {SOURCE_TAG} docs")

    candles = load_btc_candles(client)
    print(f"[rolling-backfill] loaded {len(candles)} BTC daily candles "
          f"({candles[0]['t']} .. {candles[-1]['t']})")
    if len(candles) < MIN_HISTORY_FOR_MATCH + args.window + args.horizon:
        print("[rolling-backfill] not enough history")
        sys.exit(1)

    closes = np.array([c["c"] for c in candles], dtype=float)
    lr     = log_returns(closes)
    # lr index i corresponds to candle index i+1
    n      = closes.size

    # Last candle index
    last_idx = n - 1

    # We will backfill for indices [last_idx - days .. last_idx], stride
    start_idx = max(args.window + args.horizon, last_idx - args.days)

    snapshots_to_save: list[dict] = []
    print(f"[rolling-backfill] computing snapshots from idx {start_idx} to {last_idx} stride={args.stride}")
    saved = 0
    skipped = 0
    for cur_idx in range(start_idx, last_idx + 1, args.stride):
        # We need cur_idx - window candles for the current window,
        # and forecast_days candles in future of cur_idx — but for true
        # walk-forward we DON'T peek into future of cur_idx.  Instead,
        # we look in [0 .. cur_idx - forecast] for past analogs that
        # had at least forecast_days of future data at THEIR time.
        as_of_iso   = candles[cur_idx]["t"]
        as_of_price = closes[cur_idx]

        # Find analogs in the past portion of lr ending strictly before cur_idx
        # We slice lr to only the prefix that was known at as_of date.
        # lr[i] corresponds to ratio between closes[i+1] / closes[i].
        # The current window ends at lr index (cur_idx - 1).
        cur_lr_end = cur_idx - 1
        if cur_lr_end < args.window:
            skipped += 1
            continue
        # Restrict to lr[: cur_lr_end + 1] but the find_analogs function
        # uses the full array, so build a slice + adjust top-K to require
        # forward data only INSIDE the slice (no future peek).
        slice_lr     = lr[: cur_lr_end + 1]
        slice_closes = closes[: cur_idx + 1]
        analogs = find_analogs(
            slice_lr,
            cur_idx=cur_lr_end + 1,    # find_analogs uses cur_idx as upper bound
            window_len=args.window,
            forward_days=args.horizon,
            top_k=args.topk,
        )
        if not analogs:
            skipped += 1
            continue

        curve = compute_forward_curve(slice_closes, analogs, args.horizon)
        if not curve:
            skipped += 1
            continue

        snap = build_snapshot(
            asset=ASSET,
            horizon_days=args.horizon,
            as_of_iso=as_of_iso,
            as_of_price=as_of_price,
            forecast_curve=curve,
            analog_count=len(analogs),
        )
        if not snap:
            skipped += 1
            continue
        snapshots_to_save.append(snap)
        saved += 1

    print(f"[rolling-backfill] built {saved} snapshots, skipped {skipped}")

    if not snapshots_to_save:
        print("[rolling-backfill] nothing to save")
        return

    ops = []
    for s in snapshots_to_save:
        ops.append(UpdateOne(
            {"asset": s["asset"], "view": s["view"], "horizonDays": s["horizonDays"], "asOfDate": s["asOfDate"]},
            {"$set": s},
            upsert=True,
        ))
    r = coll.bulk_write(ops, ordered=False)
    print(f"[rolling-backfill] upserted={r.upserted_count} modified={r.modified_count}")

    # Show coverage
    cnt = coll.count_documents({"asset": ASSET, "metadata.source": SOURCE_TAG})
    first = coll.find_one({"asset": ASSET, "metadata.source": SOURCE_TAG}, sort=[("asOfDate", ASCENDING)])
    last  = coll.find_one({"asset": ASSET, "metadata.source": SOURCE_TAG}, sort=[("asOfDate", DESCENDING)])
    print(f"\n[rolling-backfill] DONE. Coverage: {cnt} snapshots "
          f"({first['asOfDate']} .. {last['asOfDate']})")


if __name__ == "__main__":
    main()
