"""
FOMO Growth OS v2 — Gamified Growth + Anti-Abuse + Seasons + Leaderboard
=========================================================================
ONE USER → ONE CODE → ONE LEADERBOARD → CROSS-PLATFORM

Architecture:
- CodeEngine: REFERRAL / PROMO / INFLUENCER (unified)
- ScoreEngine: weighted scoring (signup=1, paid=5, retained=3)
- SeasonEngine: monthly seasons, rank, rewards
- LeaderboardEngine: real-time ranking with delta
- AntiAbuseEngine: device fingerprint, cooldown, suspicious detection
- RewardEngine: tiered access (NOT money) + seasonal prizes
- ShareEngine: PnL cards, deep links, viral triggers
"""
import os
import hashlib
import secrets
import string
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING, ASCENDING
from motor.motor_asyncio import AsyncIOMotorClient
import logging

logger = logging.getLogger(__name__)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "fomo_mobile")
APP_URL = os.getenv("APP_URL", "https://expo-telegram-web.preview.emergentagent.com")
BOT_USERNAME = "FOMO_mini_bot"

_sync = MongoClient(MONGO_URL)[DB_NAME]
_async = AsyncIOMotorClient(MONGO_URL)[DB_NAME]

# ═══════════════════════════════════════════
# COLLECTIONS
# ═══════════════════════════════════════════
codes = _sync["growth_codes"]
events = _sync["growth_events"]
seasons_col = _sync["growth_seasons"]
leaderboard = _sync["growth_leaderboard"]
rewards = _sync["growth_rewards"]
users = _sync["users"]
unified = _sync["unified_users"]

# Indexes
codes.create_index("code", unique=True)
codes.create_index("owner_id")
events.create_index([("referrer_code", 1), ("status", 1)])
events.create_index("referred_user_id")
events.create_index([("season_id", 1), ("referrer_code", 1)])
leaderboard.create_index([("season_id", 1), ("score", DESCENDING)])
leaderboard.create_index([("season_id", 1), ("user_id", 1)], unique=True)
seasons_col.create_index("status")

# ═══════════════════════════════════════════
# SCORING CONFIG
# ═══════════════════════════════════════════
SCORE_SIGNUP = 1
SCORE_PAID = 5
SCORE_RETAINED_7D = 3

MILESTONE_REWARDS = [
    {"paid": 1, "reward": "3 days PRO", "label": "+3 days PRO", "days": 3},
    {"paid": 3, "reward": "7 days PRO", "label": "+7 days PRO", "days": 7},
    {"paid": 7, "reward": "30 days PRO", "label": "+30 days PRO", "days": 30},
]

SEASON_REWARDS = {
    "top_1": {"reward": "365 days PRO", "label": "1 year PRO", "days": 365},
    "top_3": {"reward": "90 days PRO", "label": "90 days PRO", "days": 90},
    "top_10": {"reward": "30 days PRO", "label": "30 days PRO", "days": 30},
}

COOLDOWN_HOURS = 48  # Hours before referral is confirmed


# ═══════════════════════════════════════════
# SEASON ENGINE
# ═══════════════════════════════════════════
def _now():
    return datetime.now(timezone.utc)


def get_current_season() -> dict:
    """Get or create current monthly season."""
    now = _now()
    season_id = f"season_{now.strftime('%Y_%m')}"

    existing = seasons_col.find_one({"_id": season_id})
    if existing:
        return existing

    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month == 12:
        end = start.replace(year=now.year + 1, month=1) - timedelta(seconds=1)
    else:
        end = start.replace(month=now.month + 1) - timedelta(seconds=1)

    season = {
        "_id": season_id,
        "name": now.strftime("%B %Y"),
        "start_at": start.isoformat(),
        "end_at": end.isoformat(),
        "status": "ACTIVE",
        "rewards": SEASON_REWARDS,
        "created_at": _now().isoformat(),
    }
    seasons_col.insert_one(season)
    return season


def close_season(season_id: str):
    """End season, apply rewards, archive."""
    season = seasons_col.find_one({"_id": season_id})
    if not season or season["status"] != "ACTIVE":
        return {"ok": False, "error": "Season not active"}

    # Get top performers
    top = list(leaderboard.find({"season_id": season_id}).sort("score", DESCENDING).limit(10))

    applied = []
    for i, entry in enumerate(top):
        rank = i + 1
        if rank == 1:
            reward_key = "top_1"
        elif rank <= 3:
            reward_key = "top_3"
        elif rank <= 10:
            reward_key = "top_10"
        else:
            continue

        reward = SEASON_REWARDS[reward_key]
        _apply_pro_days(entry["user_id"], reward["days"])

        rewards.insert_one({
            "user_id": entry["user_id"],
            "season_id": season_id,
            "rank": rank,
            "reward_type": reward["reward"],
            "status": "APPLIED",
            "applied_at": _now().isoformat(),
        })
        applied.append({"rank": rank, "user_id": entry["user_id"], "reward": reward["label"]})

    seasons_col.update_one({"_id": season_id}, {"$set": {"status": "ENDED", "ended_at": _now().isoformat()}})
    return {"ok": True, "rewards_applied": len(applied), "details": applied}


# ═══════════════════════════════════════════
# CODE ENGINE
# ═══════════════════════════════════════════
def _short_code(seed: str) -> str:
    return "FOMO-" + hashlib.md5(seed.encode()).hexdigest()[:4].upper()


def _random_code(prefix: str = "", length: int = 6) -> str:
    chars = string.ascii_uppercase + string.digits
    c = "".join(secrets.choice(chars) for _ in range(length))
    return f"{prefix}-{c}" if prefix else c


def ensure_code(user_id: str, email: str = "") -> str:
    """ONE code per user, cross-platform."""
    existing = codes.find_one({"owner_id": user_id, "type": "REFERRAL"})
    if existing:
        return existing["code"]

    # Migrate legacy
    user = users.find_one({"_id": user_id}) or users.find_one({"email": email})
    uni = unified.find_one({"email": email}) if email else None
    legacy = (user or {}).get("referrals", {}).get("code") or (uni or {}).get("referralCode")

    code = legacy or _short_code(user_id)
    attempt = 0
    while codes.find_one({"code": code}) and attempt < 10:
        code = _short_code(f"{user_id}_{attempt}")
        attempt += 1

    codes.insert_one({
        "code": code, "type": "REFERRAL", "owner_id": user_id, "owner_email": email,
        "created_at": _now().isoformat(), "used_count": 0, "active": True,
    })

    if user:
        users.update_one({"_id": user_id}, {"$set": {"referrals.code": code}})
    if uni:
        unified.update_one({"email": email}, {"$set": {"referralCode": code}})
    return code


def ensure_tg_code(telegram_id: str) -> str:
    uni = unified.find_one({"telegramChatId": telegram_id})
    if uni:
        return ensure_code(f"tg_{telegram_id}", uni.get("email", ""))
    existing = codes.find_one({"owner_id": f"tg_{telegram_id}", "type": "REFERRAL"})
    if existing:
        return existing["code"]
    return ensure_code(f"tg_{telegram_id}")


# ═══════════════════════════════════════════
# ANTI-ABUSE ENGINE
# ═══════════════════════════════════════════
def _check_suspicious(referrer_id: str, referred_id: str, meta: dict = None) -> list:
    """Check for abuse signals. Returns list of flags."""
    flags = []
    meta = meta or {}

    # Self-referral
    if referrer_id == referred_id:
        flags.append("SELF_REFERRAL")

    # Same device fingerprint
    fp = meta.get("device_fingerprint", "")
    if fp:
        existing = events.find_one({"meta.device_fingerprint": fp, "referrer_code": {"$exists": True}})
        if existing:
            flags.append("SAME_DEVICE")

    # Same IP cluster
    ip = meta.get("ip", "")
    if ip:
        recent = events.count_documents({
            "meta.ip": ip,
            "event_type": "SIGNUP",
            "created_at": {"$gte": (_now() - timedelta(hours=24)).isoformat()}
        })
        if recent >= 3:
            flags.append("IP_CLUSTER")

    # Burst pattern (too many signups from same referrer in short time)
    recent_signups = events.count_documents({
        "referrer_user_id": referrer_id,
        "event_type": "SIGNUP",
        "created_at": {"$gte": (_now() - timedelta(hours=1)).isoformat()}
    })
    if recent_signups >= 5:
        flags.append("BURST_PATTERN")

    return flags


# ═══════════════════════════════════════════
# REFERRAL EVENT TRACKING
# ═══════════════════════════════════════════
def track_click(code: str, meta: dict = None):
    """Track referral link click."""
    events.insert_one({
        "referrer_code": code, "event_type": "CLICK",
        "status": "TRACKED", "meta": meta or {}, "created_at": _now().isoformat(),
    })


def track_signup(code: str, referred_user_id: str, meta: dict = None):
    """Track referred user signup. Status = PENDING until payment."""
    code_doc = codes.find_one({"code": code})
    if not code_doc:
        return {"ok": False, "error": "Invalid code"}

    referrer_id = code_doc["owner_id"]

    # Already signed up via this code?
    existing = events.find_one({"referred_user_id": referred_user_id, "event_type": "SIGNUP"})
    if existing:
        return {"ok": False, "error": "Already referred"}

    flags = _check_suspicious(referrer_id, referred_user_id, meta)
    status = "SUSPICIOUS" if flags else "PENDING"

    season = get_current_season()
    events.insert_one({
        "referrer_code": code, "referrer_user_id": referrer_id,
        "referred_user_id": referred_user_id,
        "event_type": "SIGNUP", "status": status,
        "score_awarded": SCORE_SIGNUP if not flags else 0,
        "suspicious_flags": flags,
        "season_id": season["_id"],
        "meta": meta or {},
        "created_at": _now().isoformat(),
    })

    if not flags:
        _update_score(referrer_id, season["_id"], SCORE_SIGNUP)
        codes.update_one({"code": code}, {"$inc": {"used_count": 1}})

    return {"ok": True, "status": status, "flags": flags}


def track_payment(referred_user_id: str, amount: float = 19.0):
    """Track payment from referred user. Starts cooldown for confirmation."""
    signup_event = events.find_one({
        "referred_user_id": referred_user_id, "event_type": "SIGNUP"
    })
    if not signup_event:
        return

    # Already tracked payment?
    existing = events.find_one({
        "referred_user_id": referred_user_id, "event_type": "PAID_REFERRAL"
    })
    if existing:
        return

    season = get_current_season()
    confirm_at = _now() + timedelta(hours=COOLDOWN_HOURS)

    events.insert_one({
        "referrer_code": signup_event["referrer_code"],
        "referrer_user_id": signup_event["referrer_user_id"],
        "referred_user_id": referred_user_id,
        "event_type": "PAID_REFERRAL",
        "status": "PAID_PENDING",
        "score_awarded": 0,  # awarded after confirmation
        "amount": amount,
        "season_id": season["_id"],
        "confirm_after": confirm_at.isoformat(),
        "created_at": _now().isoformat(),
    })


def confirm_pending_payments():
    """Cron job: confirm payments after cooldown (48-72h). Awards score + milestone rewards."""
    now = _now()
    pending = list(events.find({
        "event_type": "PAID_REFERRAL", "status": "PAID_PENDING",
        "confirm_after": {"$lte": now.isoformat()}
    }))

    confirmed = 0
    for evt in pending:
        # Re-check suspicious
        signup = events.find_one({
            "referred_user_id": evt["referred_user_id"], "event_type": "SIGNUP"
        })
        if signup and signup.get("status") == "SUSPICIOUS":
            events.update_one({"_id": evt["_id"]}, {"$set": {"status": "REJECTED"}})
            continue

        events.update_one({"_id": evt["_id"]}, {"$set": {
            "status": "CONFIRMED", "confirmed_at": now.isoformat(), "score_awarded": SCORE_PAID,
        }})

        _update_score(evt["referrer_user_id"], evt["season_id"], SCORE_PAID)
        _check_milestone_reward(evt["referrer_user_id"])
        confirmed += 1

    return {"confirmed": confirmed, "total_pending": len(pending)}


# ═══════════════════════════════════════════
# SCORE + LEADERBOARD ENGINE
# ═══════════════════════════════════════════
def _update_score(user_id: str, season_id: str, points: int):
    """Add points to user's season score and update rank."""
    result = leaderboard.find_one_and_update(
        {"season_id": season_id, "user_id": user_id},
        {
            "$inc": {"score": points},
            "$set": {"updated_at": _now().isoformat()},
            "$setOnInsert": {"created_at": _now().isoformat()},
        },
        upsert=True, return_document=True,
    )
    # Also update lifetime score on user
    users.update_one({"_id": user_id}, {"$inc": {"lifetime_score": points}})
    _recalculate_ranks(season_id)
    return result


def _recalculate_ranks(season_id: str):
    """Recalculate ranks for a season."""
    entries = list(leaderboard.find({"season_id": season_id}).sort("score", DESCENDING))
    for i, entry in enumerate(entries):
        prev_rank = entry.get("rank", 0)
        new_rank = i + 1
        delta = prev_rank - new_rank if prev_rank else 0
        leaderboard.update_one({"_id": entry["_id"]}, {"$set": {
            "rank": new_rank, "previous_rank": prev_rank, "delta": delta,
        }})


def get_leaderboard(season_id: str = None, limit: int = 20) -> list:
    """Get leaderboard for a season."""
    if not season_id:
        season_id = get_current_season()["_id"]
    entries = list(leaderboard.find(
        {"season_id": season_id}, {"_id": 0}
    ).sort("score", DESCENDING).limit(limit))

    # Enrich with user names
    for e in entries:
        user = users.find_one({"_id": e["user_id"]}, {"name": 1, "email": 1})
        e["name"] = (user or {}).get("name", "User")
        e["email_masked"] = _mask_email((user or {}).get("email", ""))
    return entries


def _mask_email(email: str) -> str:
    if not email or "@" not in email:
        return "***"
    parts = email.split("@")
    return parts[0][:2] + "***@" + parts[1]


def get_user_rank(user_id: str, season_id: str = None) -> dict:
    if not season_id:
        season_id = get_current_season()["_id"]
    entry = leaderboard.find_one({"season_id": season_id, "user_id": user_id}, {"_id": 0})
    if not entry:
        return {"rank": 0, "score": 0, "delta": 0}
    return entry


# ═══════════════════════════════════════════
# MILESTONE REWARD ENGINE
# ═══════════════════════════════════════════
def _check_milestone_reward(user_id: str):
    """Check and apply milestone rewards based on paid referrals."""
    paid_count = events.count_documents({
        "referrer_user_id": user_id, "event_type": "PAID_REFERRAL", "status": "CONFIRMED",
    })

    for milestone in MILESTONE_REWARDS:
        if paid_count >= milestone["paid"]:
            existing = rewards.find_one({
                "user_id": user_id, "reward_type": milestone["reward"], "source": "milestone",
            })
            if not existing:
                _apply_pro_days(user_id, milestone.get("days", 0))
                rewards.insert_one({
                    "user_id": user_id, "reward_type": milestone["reward"],
                    "source": "milestone", "label": milestone["label"],
                    "status": "APPLIED", "applied_at": _now().isoformat(),
                })
                logger.info(f"[Growth] Milestone reward: {user_id} → {milestone['label']}")


def _apply_pro_days(user_id: str, days: int):
    """Apply PRO days to user."""
    if days <= 0:
        return
    # Find current expiry or set from now
    user = users.find_one({"_id": user_id})
    current_expires = None
    if user:
        sub = user.get("subscription", {})
        exp_str = sub.get("trialExpires") or sub.get("renewsAt")
        if exp_str:
            try:
                current_expires = datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
            except Exception:
                pass

    base = max(current_expires or _now(), _now())
    new_expires = base + timedelta(days=days)

    users.update_one({"_id": user_id}, {"$set": {
        "plan": "PRO",
        "access.fullSignals": True, "access.edge": True, "access.fullIntel": True,
        "subscription.trialExpires": new_expires.isoformat(),
    }})


# ═══════════════════════════════════════════
# APPLY CODE (unified)
# ═══════════════════════════════════════════
def apply_code(code: str, user_id: str, email: str = "", meta: dict = None) -> dict:
    """Apply any code (referral/promo/influencer). ONE function, all platforms."""
    code = code.strip().upper()
    if not code:
        return {"ok": False, "error": "Code is required"}

    # 1. Check growth_codes
    code_doc = codes.find_one({"code": code, "active": True})

    # 2. Fallback: legacy promo_codes
    if not code_doc:
        legacy = _sync.promo_codes.find_one({"code": code})
        if legacy:
            if legacy.get("used_by"):
                return {"ok": False, "error": "Code already used"}
            benefit = legacy.get("benefit", {})
            _sync.promo_codes.update_one({"code": code}, {"$set": {"used_by": user_id}})
            return {"ok": True, "message": "Promo applied!"}

    # 3. Fallback: legacy user referral code
    if not code_doc:
        referrer = users.find_one({"referrals.code": code})
        if referrer:
            code_doc = {"code": code, "type": "REFERRAL", "owner_id": referrer.get("_id", "")}

    if not code_doc:
        return {"ok": False, "error": "Invalid code"}

    # Self-referral
    if code_doc.get("owner_id") == user_id or code_doc.get("owner_email") == email:
        return {"ok": False, "error": "Cannot use your own code"}

    # Already used referral
    existing = events.find_one({"referred_user_id": user_id, "event_type": "SIGNUP"})
    if existing:
        return {"ok": False, "error": "You have already used a referral code"}

    # Track signup with anti-abuse
    result = track_signup(code, user_id, meta)
    if not result.get("ok"):
        return result

    # Mark user as referred
    users.update_one({"_id": user_id}, {"$set": {"referred_by": code_doc.get("owner_id")}})
    if email:
        unified.update_one({"email": email}, {"$set": {"referredBy": code_doc.get("owner_id")}})

    status = result.get("status", "PENDING")
    if status == "SUSPICIOUS":
        return {"ok": True, "message": "Code applied! Verification pending."}
    return {"ok": True, "message": "Referral applied! Welcome to FOMO."}


# ═══════════════════════════════════════════
# USER GROWTH PROFILE
# ═══════════════════════════════════════════
def get_growth_profile(user_id: str = None, email: str = None, telegram_id: str = None) -> dict:
    """Unified growth profile for any platform."""
    # Resolve identity
    if telegram_id and not user_id:
        user_id = f"tg_{telegram_id}"

    code = ensure_code(user_id, email or "")
    season = get_current_season()
    rank_data = get_user_rank(user_id, season["_id"])

    # Stats
    total_signups = events.count_documents({"referrer_user_id": user_id, "event_type": "SIGNUP"})
    confirmed_paid = events.count_documents({"referrer_user_id": user_id, "event_type": "PAID_REFERRAL", "status": "CONFIRMED"})
    pending_paid = events.count_documents({"referrer_user_id": user_id, "event_type": "PAID_REFERRAL", "status": "PAID_PENDING"})
    clicks = events.count_documents({"referrer_code": code, "event_type": "CLICK"})

    # Next milestone
    next_milestone = None
    for m in MILESTONE_REWARDS:
        if confirmed_paid < m["paid"]:
            next_milestone = {"need": m["paid"] - confirmed_paid, **m}
            break

    # Earned rewards
    earned = list(rewards.find({"user_id": user_id}, {"_id": 0}).sort("applied_at", DESCENDING).limit(10))

    return {
        "code": code,
        "shareUrl": f"{APP_URL}/r/{code}",
        "telegramLink": f"https://t.me/{BOT_USERNAME}/app?startapp=ref_{code}",
        "season": {"id": season["_id"], "name": season["name"], "status": season["status"]},
        "rank": rank_data.get("rank", 0),
        "seasonScore": rank_data.get("score", 0),
        "previousRank": rank_data.get("previous_rank", 0),
        "rankDelta": rank_data.get("delta", 0),
        "stats": {
            "clicks": clicks,
            "signups": total_signups,
            "paidConfirmed": confirmed_paid,
            "paidPending": pending_paid,
        },
        "milestones": MILESTONE_REWARDS,
        "nextMilestone": next_milestone,
        "earnedRewards": earned,
        "funnel": {
            "clicks": clicks,
            "signups": total_signups,
            "payments": confirmed_paid,
            "conversionRate": round(total_signups / max(clicks, 1) * 100, 1),
        },
    }


# ═══════════════════════════════════════════
# SHARE ENGINE
# ═══════════════════════════════════════════
def build_share_card(user_id: str, asset: str = "BTC", pnl: float = 0) -> dict:
    code = ensure_code(user_id)
    if pnl > 2:
        msg = f"I caught {asset} early — +{pnl:.1f}%"
        cta = "Show how early works →"
    elif pnl > 0:
        msg = f"{asset} +{pnl:.1f}% — still early"
        cta = "Join before confirmation →"
    else:
        msg = f"Watching {asset} — forming setup"
        cta = "See what I see →"

    share_text = f"{msg}\n\nJoin FOMO — crypto intelligence.\n{APP_URL}/r/{code}?asset={asset}"

    return {
        "asset": asset, "pnl": pnl, "message": msg, "cta": cta,
        "shareText": share_text,
        "shareUrl": f"{APP_URL}/r/{code}?asset={asset}",
        "telegramShareUrl": f"https://t.me/share/url?url={APP_URL}/r/{code}?asset={asset}&text={msg}",
        "code": code,
    }


def get_share_triggers(user_id: str) -> list:
    """Smart share prompts based on PnL."""
    triggers = []
    positions = _sync.virtual_positions.find({
        "userId": user_id, "status": "CLOSED", "pnlPercent": {"$gt": 2}
    }).sort("closedAt", DESCENDING).limit(3)

    for pos in positions:
        triggers.append({
            "type": "pnl_share",
            "asset": pos.get("asset", "BTC"),
            "pnl": pos.get("pnlPercent", 0),
            "message": f"You caught {pos.get('asset')} early — +{pos.get('pnlPercent', 0):.1f}%",
            "cta": "Show how early works →",
        })
    return triggers


# ═══════════════════════════════════════════
# ADMIN FUNCTIONS
# ═══════════════════════════════════════════
def create_promo_group(name: str, count: int, prefix: str = "", benefit: dict = None,
                       referral_enabled: bool = False, reward_percent: int = 0) -> dict:
    """Admin: create promo/influencer codes."""
    group_id = f"grp_{secrets.token_hex(5)}"
    generated = []
    code_type = "INFLUENCER" if referral_enabled else "PROMO"
    if not benefit:
        benefit = {"type": "plan_upgrade", "reward": "pro_forever"}

    for _ in range(min(count, 500)):
        for _a in range(20):
            c = _random_code(prefix=prefix, length=6)
            if not codes.find_one({"code": c}):
                generated.append(c)
                break

    for c in generated:
        codes.insert_one({
            "code": c, "type": code_type, "group_id": group_id,
            "owner_id": None, "benefit": benefit,
            "referral_enabled": referral_enabled,
            "created_at": _now().isoformat(), "used_count": 0, "active": True,
        })

    _sync.growth_groups.insert_one({
        "group_id": group_id, "name": name, "type": code_type,
        "total_codes": len(generated), "created_at": _now().isoformat(),
    })

    return {"ok": True, "group_id": group_id, "generated": len(generated), "sample": generated[:5]}


def get_admin_overview() -> dict:
    """Admin: full growth stats."""
    season = get_current_season()
    return {
        "season": {"id": season["_id"], "name": season["name"], "status": season["status"]},
        "codes": {
            "total": codes.count_documents({}),
            "referral": codes.count_documents({"type": "REFERRAL"}),
            "promo": codes.count_documents({"type": "PROMO"}),
            "influencer": codes.count_documents({"type": "INFLUENCER"}),
        },
        "funnel": {
            "clicks": events.count_documents({"event_type": "CLICK"}),
            "signups": events.count_documents({"event_type": "SIGNUP"}),
            "paid_pending": events.count_documents({"event_type": "PAID_REFERRAL", "status": "PAID_PENDING"}),
            "paid_confirmed": events.count_documents({"event_type": "PAID_REFERRAL", "status": "CONFIRMED"}),
            "rejected": events.count_documents({"status": "REJECTED"}),
            "suspicious": events.count_documents({"status": "SUSPICIOUS"}),
        },
        "leaderboard_top5": get_leaderboard(season["_id"], limit=5),
    }


def get_suspicious_events(limit: int = 50) -> list:
    return list(events.find(
        {"$or": [{"status": "SUSPICIOUS"}, {"suspicious_flags": {"$ne": []}}]},
        {"_id": 0}
    ).sort("created_at", DESCENDING).limit(limit))


def approve_event(event_id: str):
    events.update_one({"_id": event_id}, {"$set": {"status": "CONFIRMED", "suspicious_flags": []}})
    return {"ok": True}


def reject_event(event_id: str):
    events.update_one({"_id": event_id}, {"$set": {"status": "REJECTED"}})
    return {"ok": True}
