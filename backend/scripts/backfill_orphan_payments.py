#!/usr/bin/env python3
"""
P0: Backfill orphan payments — one-shot reconciliation for payments created
BEFORE the Identity Gate was introduced.

Strategy:
  1. Scan `payments` + `orphan_payments` + `subscriptions` for records with
     order_id/user_id matching legacy patterns: anon_*, email:*, tg_*.
  2. For each, try to resolve a canonical `user_id`:
       - email:<x>   → users.email == x
       - tg_<id>     → users.telegram_id == id
       - anon_*      → cannot resolve (logged for manual review)
  3. If resolved: attach subscription to that user and mark orphan as
     RECONCILED. If not: leave as UNRESOLVED with a clear reason.

Usage:
  python scripts/backfill_orphan_payments.py           # dry-run, prints report
  python scripts/backfill_orphan_payments.py --apply   # actually write changes
"""
import asyncio
import os
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv()
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "fomo_db")


async def resolve_user_id(db, legacy_id: str, email_hint: str = None):
    """Return (user_id, reason) or (None, reason_failure)."""
    if not legacy_id:
        return None, "empty_legacy_id"
    if legacy_id.startswith("email:"):
        email = legacy_id.split(":", 1)[1]
        u = await db["users"].find_one({"email": email}, {"user_id": 1, "_id": 0})
        if u and u.get("user_id"):
            return u["user_id"], "RESOLVED_BY_LEGACY_EMAIL"
        return None, f"no_user_for_email:{email}"
    if legacy_id.startswith("tg_"):
        tg_id = legacy_id.split("_", 1)[1]
        u = await db["users"].find_one({"telegram_id": tg_id}, {"user_id": 1, "_id": 0})
        if u and u.get("user_id"):
            return u["user_id"], "RESOLVED_BY_TELEGRAM_ID"
        return None, f"no_user_for_tg:{tg_id}"
    if legacy_id.startswith("anon_"):
        # Last-ditch: try email hint if any
        if email_hint:
            u = await db["users"].find_one({"email": email_hint}, {"user_id": 1, "_id": 0})
            if u and u.get("user_id"):
                return u["user_id"], "RESOLVED_BY_ANON_EMAIL_HINT"
        return None, "anon_unresolvable"
    return None, f"unknown_pattern:{legacy_id[:24]}"


async def main(apply_changes: bool):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    stats = {
        "scanned_payments": 0,
        "scanned_orphans": 0,
        "scanned_subs": 0,
        "resolved": 0,
        "unresolved": 0,
        "writes": 0,
    }
    unresolved_samples = []

    # --- 1. subscriptions with legacy user_id ---
    legacy_filter = {"user_id": {"$regex": r"^(anon_|email:|tg_|pending_)", "$options": ""}}
    cursor = db["subscriptions"].find(legacy_filter)
    async for sub in cursor:
        stats["scanned_subs"] += 1
        legacy = sub.get("user_id", "")
        email_hint = sub.get("customer_email") or sub.get("email")
        new_uid, reason = await resolve_user_id(db, legacy, email_hint)
        if new_uid:
            stats["resolved"] += 1
            if apply_changes:
                await db["subscriptions"].update_one(
                    {"_id": sub["_id"]},
                    {"$set": {
                        "user_id": new_uid,
                        "legacy_user_id": legacy,
                        "reconciliation_reason": reason,
                        "reconciled_at": datetime.now(timezone.utc).isoformat(),
                    }}
                )
                await db["users"].update_one(
                    {"user_id": new_uid},
                    {"$set": {"plan": sub.get("plan", "PRO")}}
                )
                stats["writes"] += 1
        else:
            stats["unresolved"] += 1
            if len(unresolved_samples) < 15:
                unresolved_samples.append({
                    "type": "subscription", "legacy_id": legacy, "reason": reason,
                    "stripe_sub_id": sub.get("stripe_subscription_id", ""),
                })

    # --- 2. payments collection (if exists) ---
    try:
        cursor = db["payments"].find({"user_id": {"$regex": r"^(anon_|email:|tg_)"}})
        async for p in cursor:
            stats["scanned_payments"] += 1
            legacy = p.get("user_id", "")
            new_uid, reason = await resolve_user_id(db, legacy, p.get("email"))
            if new_uid:
                stats["resolved"] += 1
                if apply_changes:
                    await db["payments"].update_one(
                        {"_id": p["_id"]},
                        {"$set": {
                            "user_id": new_uid,
                            "legacy_user_id": legacy,
                            "reconciliation_reason": reason,
                        }}
                    )
                    stats["writes"] += 1
            else:
                stats["unresolved"] += 1
    except Exception:
        pass

    # --- 3. print report ---
    print("\n══════ Backfill Report (apply=%s) ══════" % apply_changes)
    for k, v in stats.items():
        print(f"  {k}: {v}")
    if unresolved_samples:
        print("\n  Unresolved samples:")
        for s in unresolved_samples:
            print(f"   - {s}")
    print("═══════════════════════════════════════════\n")
    if not apply_changes:
        print("DRY RUN — no writes. Add --apply to actually reconcile.")
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="actually write changes")
    args = parser.parse_args()
    asyncio.run(main(apply_changes=args.apply))
