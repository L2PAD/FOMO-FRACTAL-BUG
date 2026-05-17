"""
Contextual Paywall — Signal Loop integration.

Not a screen. Not a popup. A *state machine* that resolves the right copy
based on user behavior:

    COLD  → first contact        → "Unlock full signal breakdown"
    WARM  → engaged              → "You're seeing signals early — unlock exact entry & timing"
    HOT   → felt the pain        → "You were early — but missed the move"

State inputs come from analytics_events (Growth Layer G1).
Copy lives in DB (`paywall_copy` collection) so it can be tuned
without a release.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Literal, TypedDict

from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

PaywallState = Literal["cold", "warm", "hot"]
Surface = Literal["hero", "edge", "missed", "feed", "push", "unknown"]


# ─── Thresholds (tune via paywall_copy doc) ───────────────────────────
DEFAULT_THRESHOLDS = {
    "warm_edge_open": 2,
    "warm_hero_tap": 2,
    "lookback_hours": 72,  # Only recent behavior counts
}

DEFAULT_COPY: dict[PaywallState, dict[str, str]] = {
    "cold": {
        "headline": "Unlock full signal breakdown",
        "subline": "See the exact entry, timing and strength behind every setup.",
        "cta": "Unlock",
    },
    "warm": {
        "headline": "You're seeing signals early — unlock exact entry & timing",
        "subline": "PRO shows you where to enter and when the move starts.",
        "cta": "Unlock entry",
    },
    "hot": {
        "headline": "You were early — but missed the move",
        "subline": "Unlock entry timing so you catch the next one.",
        "cta": "Unlock timing",
    },
}


class PaywallContext(TypedDict, total=False):
    ok: bool
    state: PaywallState
    surface: Surface
    headline: str
    subline: str
    cta: str
    reason: str                 # Why this state was chosen (audit)
    signals: dict               # Raw counts used in resolution
    is_subscribed: bool         # If true, frontend hides paywall


# ─── Resolver ─────────────────────────────────────────────────────────
class PaywallResolver:
    """Reads analytics + subscription state, returns contextual copy."""

    def _db(self):
        return AsyncIOMotorClient(
            os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        )[os.environ.get("DB_NAME", "test_database")]

    # ── Config ────────────────────────────────────────────────────────
    async def get_config(self) -> dict:
        db = self._db()
        doc = await db["paywall_copy"].find_one({"type": "config"}, {"_id": 0})
        if not doc:
            doc = {"type": "config", "thresholds": DEFAULT_THRESHOLDS, "copy": DEFAULT_COPY}
        # Merge missing keys with defaults (forward-compat)
        thresholds = {**DEFAULT_THRESHOLDS, **(doc.get("thresholds") or {})}
        copy = {
            state: {**DEFAULT_COPY[state], **((doc.get("copy") or {}).get(state) or {})}
            for state in ("cold", "warm", "hot")
        }
        return {"thresholds": thresholds, "copy": copy}

    async def set_copy(self, state: PaywallState, patch: dict) -> dict:
        if state not in ("cold", "warm", "hot"):
            raise ValueError(f"Invalid state: {state}")
        db = self._db()
        cfg = await self.get_config()
        cfg["copy"][state] = {**cfg["copy"][state], **patch}
        await db["paywall_copy"].update_one(
            {"type": "config"},
            {"$set": {"type": "config", "copy": cfg["copy"], "thresholds": cfg["thresholds"]}},
            upsert=True,
        )
        return cfg["copy"][state]

    async def set_thresholds(self, patch: dict) -> dict:
        db = self._db()
        cfg = await self.get_config()
        cfg["thresholds"] = {**cfg["thresholds"], **patch}
        await db["paywall_copy"].update_one(
            {"type": "config"},
            {"$set": {"type": "config", "copy": cfg["copy"], "thresholds": cfg["thresholds"]}},
            upsert=True,
        )
        return cfg["thresholds"]

    # ── Subscription check ───────────────────────────────────────────
    async def is_subscribed(self, user_id: str) -> bool:
        if not user_id:
            return False
        db = self._db()
        sub = await db["subscriptions"].find_one(
            {"user_id": user_id, "status": {"$in": ["active", "trialing"]}},
            {"_id": 0},
        )
        if sub:
            return True
        u = await db["users"].find_one(
            {"$or": [{"user_id": user_id}, {"_id": user_id}]},
            {"plan_status": 1, "plan": 1, "_id": 0},
        )
        if u and (u.get("plan_status") == "pro" or (u.get("plan") or "").upper() == "PRO"):
            return True
        return False

    # ── Behavior signals ─────────────────────────────────────────────
    async def load_signals(self, user_id: str, *, lookback_hours: int) -> dict:
        """Load raw counts of the events that matter for paywall state.

        The analytics_events collection in this codebase has two shapes
        (historic + new), we accept both:
            - user_id | userId
            - ts (ISO) | created_at | createdAt (dt) | timestamp (dt)
            - properties | context
        """
        if not user_id:
            return {"edge_open": 0, "hero_tap": 0, "missed_seen": 0, "hero_view": 0}

        db = self._db()
        cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        cutoff_iso = cutoff_dt.isoformat()

        pipeline = [
            {
                "$match": {
                    "$and": [
                        {
                            "$or": [
                                {"user_id": user_id},
                                {"userId": user_id},
                            ]
                        },
                        {
                            "event": {
                                "$in": [
                                    "edge_open",
                                    "signal_hero_tap",
                                    "missed_seen",
                                    "signal_hero_view",
                                ]
                            }
                        },
                        {
                            "$or": [
                                {"ts": {"$gte": cutoff_iso}},
                                {"created_at": {"$gte": cutoff_iso}},
                                {"createdAt": {"$gte": cutoff_dt}},
                                {"timestamp": {"$gte": cutoff_dt}},
                            ]
                        },
                    ]
                }
            },
            {"$group": {"_id": "$event", "n": {"$sum": 1}}},
        ]
        out = {"edge_open": 0, "hero_tap": 0, "missed_seen": 0, "hero_view": 0}
        try:
            async for row in db["analytics_events"].aggregate(pipeline):
                key = row["_id"]
                if key == "signal_hero_tap":
                    out["hero_tap"] = row["n"]
                elif key == "signal_hero_view":
                    out["hero_view"] = row["n"]
                elif key == "edge_open":
                    out["edge_open"] = row["n"]
                elif key == "missed_seen":
                    out["missed_seen"] = row["n"]
        except Exception as e:
            logger.warning(f"paywall signals query failed: {e}")
        return out

    # ── Resolve ──────────────────────────────────────────────────────
    async def resolve(self, *, user_id: str, surface: Surface = "edge") -> PaywallContext:
        cfg = await self.get_config()
        thresholds = cfg["thresholds"]
        copy = cfg["copy"]

        # Subscribed users never see paywall
        subscribed = await self.is_subscribed(user_id) if user_id else False
        if subscribed:
            return {
                "ok": True,
                "state": "cold",  # arbitrary, not shown
                "surface": surface,
                "headline": "",
                "subline": "",
                "cta": "",
                "reason": "subscribed",
                "signals": {},
                "is_subscribed": True,
            }

        signals = await self.load_signals(user_id, lookback_hours=thresholds["lookback_hours"])

        # HOT beats WARM beats COLD
        state: PaywallState = "cold"
        reason = "first_contact"
        if signals["missed_seen"] >= 1:
            state = "hot"
            reason = "missed_seen"
        elif signals["edge_open"] >= thresholds["warm_edge_open"]:
            state = "warm"
            reason = f"edge_open>={thresholds['warm_edge_open']}"
        elif signals["hero_tap"] >= thresholds["warm_hero_tap"]:
            state = "warm"
            reason = f"hero_tap>={thresholds['warm_hero_tap']}"

        c = copy[state]
        return {
            "ok": True,
            "state": state,
            "surface": surface,
            "headline": c["headline"],
            "subline": c.get("subline", ""),
            "cta": c.get("cta", "Unlock"),
            "reason": reason,
            "signals": signals,
            "is_subscribed": False,
        }

    # ── Identity loop (post-conversion) ──────────────────────────────
    async def identity_message(self, user_id: str) -> dict:
        """
        "You're now ahead of X% of users" — based on
        total_subscribers / total_users ratio, inverted.
        Floor at 85% so it always feels strong.

        Includes `hero_override` when user converted within last 24h:
        the next Hero screen shows "You're early again" instead of a generic pitch.
        """
        db = self._db()
        try:
            total_users = await db["users"].count_documents({})
            active_subs = await db["subscriptions"].count_documents(
                {"status": {"$in": ["active", "trialing"]}}
            )
        except Exception:
            total_users, active_subs = 0, 0

        if total_users <= 0:
            pct = 92
        else:
            free_share = max(0.0, (total_users - active_subs) / total_users)
            pct = int(round(free_share * 100))
            pct = max(85, min(99, pct))  # clamp 85–99%

        # Return-loop: Hero override for freshly-converted users
        hero_override = None
        try:
            user = await db["users"].find_one(
                {"$or": [{"user_id": user_id}, {"_id": user_id}]},
                {"just_converted_at": 1, "conversion_state": 1, "_id": 0},
            )
            if user and user.get("just_converted_at"):
                converted_at = datetime.fromisoformat(user["just_converted_at"].replace("Z", "+00:00"))
                age_hours = (datetime.now(timezone.utc) - converted_at).total_seconds() / 3600
                if age_hours <= 24:
                    hero_override = {
                        "headline": "🔥 You're early again",
                        "subline": "The signal engine is yours — first setup incoming.",
                        "ttl_hours": round(24 - age_hours, 1),
                    }
        except Exception as e:
            logger.warning(f"hero_override lookup failed: {e}")

        return {
            "ok": True,
            "user_id": user_id,
            "percent_ahead": pct,
            "headline": f"You're now ahead of {pct}% of users",
            "subline": "Early signals. Exact timing. Your edge.",
            "hero_override": hero_override,
        }

    # ── Conversion funnel (state-level) ──────────────────────────────
    async def conversion_funnel(self, hours: int = 24) -> dict:
        """
        Full paywall-to-payment funnel by state:
            paywall_view → paywall_click → checkout_open → payment_success

        Reveals which state actually monetises. Expect HOT ≫ WARM > COLD.
        """
        db = self._db()
        cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_iso = cutoff_dt.isoformat()

        # 1. Views + clicks (from analytics_events)
        funnel = {s: {"view": 0, "click": 0, "checkout": 0, "paid": 0} for s in ("cold", "warm", "hot", "unknown")}
        try:
            ev_pipeline = [
                {
                    "$match": {
                        "$and": [
                            {
                                "event": {
                                    "$in": ["edge_paywall_view", "edge_paywall_click", "payment_success"]
                                }
                            },
                            {
                                "$or": [
                                    {"ts": {"$gte": cutoff_iso}},
                                    {"created_at": {"$gte": cutoff_iso}},
                                    {"createdAt": {"$gte": cutoff_dt}},
                                    {"timestamp": {"$gte": cutoff_dt}},
                                ]
                            },
                        ]
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "event": "$event",
                            "state": {
                                "$ifNull": [
                                    "$properties.state",
                                    {"$ifNull": ["$context.state", "unknown"]},
                                ]
                            },
                        },
                        "n": {"$sum": 1},
                    }
                },
            ]
            async for row in db["analytics_events"].aggregate(ev_pipeline):
                e = row["_id"]["event"]
                s = row["_id"]["state"] or "unknown"
                if s not in funnel:
                    s = "unknown"
                if e == "edge_paywall_view":
                    funnel[s]["view"] = row["n"]
                elif e == "edge_paywall_click":
                    funnel[s]["click"] = row["n"]
                elif e == "payment_success":
                    funnel[s]["paid"] = row["n"]

            # 2. Checkout openings (from checkout_sessions collection)
            cs_pipeline = [
                {"$match": {"created_at": {"$gte": cutoff_iso}}},
                {
                    "$group": {
                        "_id": {"$ifNull": ["$attribution.state", "unknown"]},
                        "n": {"$sum": 1},
                    }
                },
            ]
            async for row in db["checkout_sessions"].aggregate(cs_pipeline):
                s = row["_id"] or "unknown"
                if s not in funnel:
                    s = "unknown"
                funnel[s]["checkout"] = row["n"]
        except Exception as e:
            logger.warning(f"conversion funnel query failed: {e}")

        def rate(num: int, den: int) -> float:
            return round((num / den) * 100.0, 2) if den else 0.0

        out = {"ok": True, "hours": hours, "funnel": funnel, "rates": {}}
        for s in ("cold", "warm", "hot"):
            out["rates"][s] = {
                "click_rate": rate(funnel[s]["click"], funnel[s]["view"]),            # view→click
                "checkout_rate": rate(funnel[s]["checkout"], funnel[s]["click"]),     # click→checkout
                "conversion_rate": rate(funnel[s]["paid"], funnel[s]["checkout"]),    # checkout→paid
                "end_to_end": rate(funnel[s]["paid"], funnel[s]["view"]),             # view→paid
            }
        return out

    # ── KPI funnel ───────────────────────────────────────────────────
    async def funnel_kpi(self, hours: int = 24) -> dict:
        """
        Conversion funnel by trigger state. Reads `context.state` or
        `properties.state` from analytics_events (both shapes supported).
        """
        db = self._db()
        cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_iso = cutoff_dt.isoformat()
        pipeline = [
            {
                "$match": {
                    "$and": [
                        {"event": {"$in": ["edge_paywall_view", "edge_paywall_click"]}},
                        {
                            "$or": [
                                {"ts": {"$gte": cutoff_iso}},
                                {"created_at": {"$gte": cutoff_iso}},
                                {"createdAt": {"$gte": cutoff_dt}},
                                {"timestamp": {"$gte": cutoff_dt}},
                            ]
                        },
                    ]
                }
            },
            {
                "$group": {
                    "_id": {
                        "event": "$event",
                        "state": {
                            "$ifNull": [
                                "$properties.state",
                                {"$ifNull": ["$context.state", "unknown"]},
                            ]
                        },
                    },
                    "n": {"$sum": 1},
                }
            },
        ]
        views = {"cold": 0, "warm": 0, "hot": 0, "unknown": 0}
        clicks = {"cold": 0, "warm": 0, "hot": 0, "unknown": 0}
        try:
            async for row in db["analytics_events"].aggregate(pipeline):
                e = row["_id"]["event"]
                s = row["_id"]["state"] or "unknown"
                if s not in views:
                    s = "unknown"
                (clicks if e == "edge_paywall_click" else views)[s] = row["n"]
        except Exception as e:
            logger.warning(f"paywall funnel query failed: {e}")

        def rate(num: int, den: int) -> float:
            return round((num / den) * 100.0, 2) if den else 0.0

        return {
            "ok": True,
            "hours": hours,
            "views": views,
            "clicks": clicks,
            "click_through_rate": {
                "cold": rate(clicks["cold"], views["cold"]),
                "warm": rate(clicks["warm"], views["warm"]),
                "hot": rate(clicks["hot"], views["hot"]),
            },
        }


# Singleton
paywall_resolver = PaywallResolver()
