#!/usr/bin/env python3
"""
P1.1: CLI funnel report — human-readable view of /api/access/funnel &
/api/access/blocks-heatmap directly from Mongo (no auth needed locally).

Usage:
  python scripts/funnel_report.py --days 7
  python scripts/funnel_report.py --days 7 --heatmap
"""
import asyncio
import os
import sys
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv()
from motor.motor_asyncio import AsyncIOMotorClient

# Reuse the same logic as the HTTP endpoint
from routes.funnel_analytics import (
    FUNNEL_STEPS, _session_step_times, _by_intent_counts, _diagnose
)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "fomo_db")


def _bar(pct: float, width: int = 20) -> str:
    filled = int(pct * width)
    return "█" * filled + "░" * (width - filled)


async def _run_funnel(db, days: int, platform: str):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # Counts
    counts = {}
    for s in FUNNEL_STEPS:
        if s == "converted":
            counts[s] = await db["checkout_sessions"].count_documents({
                "status": "completed", "completed_at": {"$gte": since},
            })
        else:
            counts[s] = await db["web_funnel_events"].count_documents({
                "event": s, "timestamp": {"$gte": since}, "platform": platform,
            })

    # Avg time-to-next
    step_times = await _session_step_times(db, since, platform)
    avg_times = {s: (sum(a) / len(a) if a else None) for s, a in step_times.items()}

    first = counts.get(FUNNEL_STEPS[0], 0) or 0
    print(f"\n═══════════ WEB FUNNEL — last {days}d ═══════════")
    prev = None
    biggest_drop = None
    for s in FUNNEL_STEPS:
        c = counts[s]
        rate_str = ""
        if prev is not None and prev > 0:
            rate = c / prev
            rate_str = f"→ {rate*100:5.1f}%"
            if c > 0 and (biggest_drop is None or rate < biggest_drop[2]):
                biggest_drop = (FUNNEL_STEPS[FUNNEL_STEPS.index(s) - 1], s, rate)
        bar = _bar(c / first if first > 0 else 0)
        at = avg_times.get(s)
        at_s = f"avg next: {at:.0f}s" if at else ""
        print(f"  {s:<26} {c:>6} {bar}  {rate_str:<10} {at_s}")
        prev = c

    if first > 0:
        print(f"\n  Overall: {counts.get('converted', 0)}/{first} = {counts.get('converted', 0) / first * 100:.2f}% visitor → paid")

    if biggest_drop:
        drop_from, drop_to, rate = biggest_drop
        at = avg_times.get(drop_from) or 0
        print(f"\n  ⚠ Biggest drop: {drop_from} → {drop_to} ({rate*100:.0f}%)")
        diag = _diagnose(drop_from, drop_to, rate, at)
        print(f"  → {diag}")

    # By intent
    print("\n─── By intent (authed users) ─────────────────")
    by_intent = await _by_intent_counts(db, since)
    for bucket in ["COLD", "WARM", "HOT", "VERY_HOT", "UNKNOWN"]:
        b = by_intent.get(bucket, {})
        if not b or b.get("visits", 0) == 0:
            continue
        print(f"  {bucket:<10}  visits={b['visits']:>4}  converted={b['converted']:>3}  conv={b['conversion']*100:.2f}%")
    print("═" * 53)


async def _run_heatmap(db, days: int):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    total = await db["web_funnel_events"].distinct(
        "guest_session_id", {"event": "web_visit_guest", "timestamp": {"$gte": since}}
    )
    tcount = len(total) or 1

    view_stats, click_stats = {}, {}
    async for row in db["web_funnel_events"].aggregate([
        {"$match": {"event": "web_block_viewed_locked", "timestamp": {"$gte": since}}},
        {"$group": {"_id": "$block_key", "count": {"$sum": 1},
                    "sessions": {"$addToSet": "$guest_session_id"}}}
    ]):
        view_stats[row["_id"]] = (row["count"], len(row.get("sessions") or []))
    async for row in db["web_funnel_events"].aggregate([
        {"$match": {"event": "web_cta_click", "timestamp": {"$gte": since}}},
        {"$group": {"_id": "$block_key", "count": {"$sum": 1}}}
    ]):
        click_stats[row["_id"]] = row["count"]

    all_blocks = (set(view_stats) | set(click_stats)) - {""}
    rows = []
    for b in all_blocks:
        lv, us = view_stats.get(b, (0, 0))
        c = click_stats.get(b, 0)
        view_rate = us / tcount if tcount > 0 else 0
        unlock_rate = c / lv if lv > 0 else 0
        impact = lv * unlock_rate
        rows.append((b, us, lv, view_rate, c, unlock_rate, impact))
    rows.sort(key=lambda r: r[6], reverse=True)

    print(f"\n═══════════ BLOCK HEATMAP — last {days}d ═══════════")
    print(f"  total visitors: {tcount}")
    print(f"  {'block':<22} {'sessions':>9} {'locked':>8} {'view%':>7} {'clicks':>7} {'unlock%':>8} {'impact':>7}")
    for r in rows:
        print(f"  {r[0]:<22} {r[1]:>9} {r[2]:>8} {r[3]*100:>6.1f}% {r[4]:>7} {r[5]*100:>7.1f}% {r[6]:>7.2f}")
    if not rows:
        print("  (no locked blocks seen yet)")
    print("═" * 53)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--platform", default="web")
    parser.add_argument("--heatmap", action="store_true", help="Show block heatmap too")
    args = parser.parse_args()

    db = AsyncIOMotorClient(MONGO_URL)[DB_NAME]
    await _run_funnel(db, args.days, args.platform)
    if args.heatmap:
        await _run_heatmap(db, args.days)


if __name__ == "__main__":
    asyncio.run(main())
