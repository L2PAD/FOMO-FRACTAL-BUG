"""
Profile Builder — User Control Center
======================================
Aggregates user identity, plan, performance, favorites,
referral, promo, and settings into a single profile payload.

Data sources:
  - decision_history (performance stats)
  - miniapp_users (user identity + settings)
  - miniapp_favorites (favorite assets)
  - promo_codes / promo_redemptions
"""

from datetime import datetime, timezone


async def build_profile(db, telegram_id: str = None) -> dict:
    """Build complete profile payload for a miniapp user."""
    user = await _get_or_create_user(db, telegram_id)
    performance = await _build_performance(db)
    favorites = await _get_favorites(db, telegram_id)
    referral = _build_referral(user)
    promo = _build_promo(user)
    settings = await _get_settings(db, telegram_id)
    growth = await _build_growth(db, telegram_id, user)

    return {
        "user": {
            "telegramId": user.get("telegram_id", ""),
            "name": user.get("name", "Telegram User"),
            "username": user.get("username", ""),
            "photoUrl": user.get("photo_url", ""),
            "planStatus": user.get("plan_status", "free"),
            "planName": "PRO" if user.get("plan_status") == "active" else "FREE",
            "renewDate": user.get("renew_date"),
            "linkedGoogle": bool(user.get("google_email")),
            "linkedTelegram": bool(user.get("telegram_id")),
        },
        "performance": performance,
        "favorites": favorites,
        "referral": referral,
        "promo": promo,
        "settings": settings,
        "growth": growth,
    }


async def _get_or_create_user(db, telegram_id: str) -> dict:
    """Get or create miniapp user document. Enriches from bot_chats if available."""
    if telegram_id:
        user = await db.miniapp_users.find_one(
            {"telegram_id": telegram_id}, {"_id": 0}
        )
        if user:
            # Enrich from bot_chats if name is still default
            if user.get("name") in ("Telegram User", "", None):
                bot_chat = await db.miniapp_bot_chats.find_one(
                    {"chat_id": int(telegram_id)}, {"_id": 0}
                )
                if bot_chat:
                    real_name = bot_chat.get("first_name", "")
                    real_username = bot_chat.get("username", "")
                    if real_name:
                        user["name"] = real_name
                        user["username"] = real_username or user.get("username", "")
                        await db.miniapp_users.update_one(
                            {"telegram_id": telegram_id},
                            {"$set": {"name": real_name, "username": real_username}}
                        )
            return user
        # Create new — try to pull real data from bot_chats
        name = "Telegram User"
        username = ""
        try:
            bot_chat = await db.miniapp_bot_chats.find_one(
                {"chat_id": int(telegram_id)}, {"_id": 0}
            )
            if bot_chat:
                name = bot_chat.get("first_name", name)
                username = bot_chat.get("username", "")
        except Exception:
            pass
        new_user = {
            "telegram_id": telegram_id,
            "name": name,
            "username": username,
            "photo_url": "",
            "plan_status": "free",
            "renew_date": None,
            "google_email": None,
            "referral_code": f"FOMO-{telegram_id[-6:].upper()}",
            "promo_code": None,
            "promo_discount_text": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.miniapp_users.insert_one(new_user)
        new_user.pop("_id", None)
        return new_user

    return {
        "telegram_id": "",
        "name": "Guest",
        "username": "",
        "photo_url": "",
        "plan_status": "free",
        "referral_code": "FOMO-GUEST",
    }


async def _build_performance(db) -> dict:
    """Build performance stats from decision_history — directional accuracy only."""
    try:
        total = await db.decision_history.count_documents({})
        evaluated = await db.decision_history.count_documents({"status": "evaluated"})

        # Directional: only BUY/SELL
        dir_total = await db.decision_history.count_documents(
            {"status": "evaluated", "decision": {"$in": ["BUY", "SELL"]}}
        )
        dir_correct = await db.decision_history.count_documents(
            {"status": "evaluated", "decision": {"$in": ["BUY", "SELL"]}, "result": "correct"}
        )
        dir_accuracy = round(dir_correct / dir_total, 2) if dir_total > 0 else 0.0
        coverage = round(dir_total / evaluated, 2) if evaluated > 0 else 0.0

        # By type (directional only)
        by_type = {}
        pipeline = [
            {"$match": {"status": "evaluated", "decision": {"$in": ["BUY", "SELL"]}}},
            {
                "$group": {
                    "_id": "$decisionType",
                    "total": {"$sum": 1},
                    "correct": {
                        "$sum": {"$cond": [{"$eq": ["$result", "correct"]}, 1, 0]}
                    },
                }
            },
        ]
        async for doc in db.decision_history.aggregate(pipeline):
            dtype = doc["_id"] or "UNKNOWN"
            dtotal = doc["total"]
            dcorrect = doc["correct"]
            acc = round(dcorrect / dtotal, 2) if dtotal > 0 else 0.0
            by_type[dtype] = {"total": dtotal, "correct": dcorrect, "accuracy": acc}

        best_type = max(by_type.items(), key=lambda x: x[1]["accuracy"])[0] if by_type else "N/A"
        best_acc = by_type[best_type]["accuracy"] if best_type in by_type else 0.0
        worst_type = min(by_type.items(), key=lambda x: x[1]["accuracy"])[0] if by_type else "N/A"
        worst_acc = by_type[worst_type]["accuracy"] if worst_type in by_type else 0.0

        return {
            "totalDecisions": total,
            "evaluated": evaluated,
            "directionalTotal": dir_total,
            "directionalCorrect": dir_correct,
            "accuracy": dir_accuracy,
            "coverage": coverage,
            "bestType": best_type,
            "bestTypeAccuracy": best_acc,
            "worstType": worst_type,
            "worstTypeAccuracy": worst_acc,
        }
    except Exception:
        return {
            "totalDecisions": 0,
            "evaluated": 0,
            "correct": 0,
            "accuracy": 0.0,
            "bestType": "N/A",
            "bestTypeAccuracy": 0.0,
            "worstType": "N/A",
            "worstTypeAccuracy": 0.0,
        }


async def _get_favorites(db, telegram_id: str) -> list:
    """Get favorite assets for user with latest decision context."""
    fav_assets = ["BTC", "ETH", "SOL"]

    if telegram_id:
        favs = await db.miniapp_favorites.find(
            {"telegram_id": telegram_id}, {"_id": 0}
        ).to_list(length=20)
        if favs:
            fav_assets = [f.get("asset", "") for f in favs]

    result = []
    for asset in fav_assets:
        latest = await db.decision_history.find_one(
            {"asset": asset}, {"_id": 0, "decision": 1, "confidence": 1},
            sort=[("timestamp", -1)],
        )
        result.append({
            "asset": asset,
            "decision": latest.get("decision", "WAIT") if latest else "WAIT",
            "confidence": round(float(latest.get("confidence", 0)) / 100.0, 2) if latest else 0.0,
        })

    return result


def _build_referral(user: dict) -> dict:
    code = user.get("referral_code", "FOMO-GUEST")
    return {
        "code": code,
        "inviteLink": f"https://t.me/FOMO_mini_bot/app?startapp=ref_{code}",
        "invites": 0,
        "activePaidInvites": 0,
        "rewardText": "Invite 3 users → unlock PRO for 7 days",
    }


def _build_promo(user: dict) -> dict:
    return {
        "activeCode": user.get("promo_code"),
        "discountText": user.get("promo_discount_text"),
    }


async def _build_growth(db, telegram_id: str, user: dict) -> dict:
    """Build Growth OS data: season, rank, leaderboard, milestones — same logic as mobile app."""
    try:
        from services.growth_engine import (
            get_growth_profile,
            get_leaderboard,
        )
    except ImportError:
        return _default_growth(user)

    try:
        # Try to find unified user by telegram_id
        unified = await db.unified_users.find_one(
            {"telegram_id": telegram_id}, {"_id": 0}
        ) if telegram_id else None

        if not unified:
            return _default_growth(user)

        user_id = str(unified.get("_id", unified.get("userId", "")))
        if not user_id:
            return _default_growth(user)

        # Get growth profile (sync call to growth_engine)
        profile = get_growth_profile(user_id)
        if not profile:
            return _default_growth(user)

        # Get leaderboard
        lb = get_leaderboard(season=None, limit=10)

        return {
            "code": profile.get("code", user.get("referral_code", "")),
            "shareUrl": profile.get("shareUrl", ""),
            "telegramLink": profile.get("telegramLink", ""),
            "season": profile.get("season", {"name": "Season 1", "status": "active"}),
            "rank": profile.get("rank", 0),
            "seasonScore": profile.get("seasonScore", 0),
            "previousRank": profile.get("previousRank", 0),
            "rankDelta": profile.get("rankDelta", 0),
            "stats": profile.get("stats", {"clicks": 0, "signups": 0, "paidConfirmed": 0}),
            "milestones": profile.get("milestones", []),
            "nextMilestone": profile.get("nextMilestone"),
            "earnedRewards": profile.get("earnedRewards", []),
            "funnel": profile.get("funnel", {}),
            "leaderboard": lb if isinstance(lb, list) else (lb.get("entries", []) if isinstance(lb, dict) else []),
        }
    except Exception:
        return _default_growth(user)


def _default_growth(user: dict) -> dict:
    """Fallback growth data when growth engine is unavailable."""
    code = user.get("referral_code", "FOMO-GUEST")
    return {
        "code": code,
        "shareUrl": f"https://t.me/FOMO_mini_bot/app?startapp=ref_{code}",
        "telegramLink": f"https://t.me/FOMO_mini_bot?start={code}",
        "season": {"name": "Season 1", "status": "active"},
        "rank": 0,
        "seasonScore": 0,
        "previousRank": 0,
        "rankDelta": 0,
        "stats": {"clicks": 0, "signups": 0, "paidConfirmed": 0},
        "milestones": [
            {"paid": 1, "reward": "3 days PRO", "label": "First paid referral", "days": 3},
            {"paid": 3, "reward": "7 days PRO", "label": "3 paid referrals", "days": 7},
            {"paid": 7, "reward": "30 days PRO", "label": "7 paid referrals", "days": 30},
        ],
        "nextMilestone": {"need": 1, "paid": 0, "label": "First paid referral → 3 days PRO"},
        "earnedRewards": [],
        "funnel": {"clicks": 0, "signups": 0, "payments": 0, "conversionRate": 0},
        "leaderboard": [],
    }


async def _get_settings(db, telegram_id: str) -> dict:
    """Get notification/alert settings."""
    if not telegram_id:
        return _default_settings()

    doc = await db.miniapp_settings.find_one(
        {"telegram_id": telegram_id}, {"_id": 0}
    )
    if not doc:
        return _default_settings()

    return {
        "alertsEnabled": doc.get("alertsEnabled", True),
        "telegramDelivery": doc.get("telegramDelivery", True),
        "highConvictionOnly": doc.get("highConvictionOnly", False),
        "favoritesOnly": doc.get("favoritesOnly", False),
    }


def _default_settings():
    return {
        "alertsEnabled": True,
        "telegramDelivery": True,
        "highConvictionOnly": False,
        "favoritesOnly": False,
    }


async def add_favorite(db, telegram_id: str, asset: str) -> dict:
    """Add an asset to favorites."""
    existing = await db.miniapp_favorites.find_one(
        {"telegram_id": telegram_id, "asset": asset}
    )
    if existing:
        return {"success": True, "message": "Already in favorites"}

    await db.miniapp_favorites.insert_one({
        "telegram_id": telegram_id,
        "asset": asset,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "message": f"{asset} added to favorites"}


async def remove_favorite(db, telegram_id: str, asset: str) -> dict:
    """Remove an asset from favorites."""
    await db.miniapp_favorites.delete_one(
        {"telegram_id": telegram_id, "asset": asset}
    )
    return {"success": True, "message": f"{asset} removed from favorites"}


async def update_settings(db, telegram_id: str, settings: dict) -> dict:
    """Update notification/alert settings."""
    await db.miniapp_settings.update_one(
        {"telegram_id": telegram_id},
        {"$set": {
            "alertsEnabled": settings.get("alertsEnabled", True),
            "telegramDelivery": settings.get("telegramDelivery", True),
            "highConvictionOnly": settings.get("highConvictionOnly", False),
            "favoritesOnly": settings.get("favoritesOnly", False),
        }},
        upsert=True,
    )
    return {"success": True}


async def apply_promo(db, telegram_id: str, code: str) -> dict:
    """Apply a promo code."""
    code_upper = code.strip().upper()

    promo = await db.promo_codes.find_one(
        {"code": code_upper, "used_by": None}, {"_id": 0}
    )
    if not promo:
        return {"success": False, "message": "Invalid or already used promo code"}

    discount = promo.get("discount_percent", 0)
    display = f"{discount}% discount applied" if discount else "Promo applied"

    await db.promo_codes.update_one(
        {"code": code_upper},
        {"$set": {
            "used_by": telegram_id,
            "used_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    await db.miniapp_users.update_one(
        {"telegram_id": telegram_id},
        {"$set": {
            "promo_code": code_upper,
            "promo_discount_text": display,
        }},
    )

    return {"success": True, "message": display}
