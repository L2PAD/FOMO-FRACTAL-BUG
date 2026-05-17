"""
Telegram Intel - Channel Add Service
Search and add channels from Telegram via MTProto.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Dict, Any

logger = logging.getLogger(__name__)


def _clean_username(raw: str) -> str:
    """Extract clean username from various formats"""
    raw = raw.strip()
    raw = re.sub(r'^https?://(t\.me|telegram\.me)/', '', raw)
    raw = raw.lstrip('@')
    raw = raw.split('/')[0].split('?')[0]
    return raw.lower()


async def search_channel_on_telegram(db, username: str) -> Dict[str, Any]:
    """Search for a channel — first in DB (username+title), then on Telegram (username + global search)"""
    clean = _clean_username(username)
    if not clean:
        return {"ok": False, "error": "Empty query"}

    # Check if already in our DB by username OR title
    existing = await db.tg_channel_states.find_one(
        {"$or": [
            {"username": clean},
            {"title": {"$regex": re.escape(username.strip()), "$options": "i"}},
        ]},
        {"_id": 0, "username": 1, "title": 1, "participantsCount": 1,
         "avatarUrl": 1, "sector": 1, "about": 1, "stage": 1, "fomoScore": 1}
    )
    if existing:
        return {
            "ok": True,
            "found": True,
            "source": "database",
            "channel": existing
        }

    # Not in DB — search on Telegram via MTProto
    try:
        from ..api.admin import get_mtproto_client, MTPROTO_AVAILABLE
        if not MTPROTO_AVAILABLE:
            return {"ok": False, "error": "Telegram connection not available"}

        client = get_mtproto_client()
        if not await client.is_connected():
            connected = await client.connect(db=db)
            if not connected:
                return {"ok": False, "error": "Cannot connect to Telegram"}

        # Try exact username first
        info = await client.get_channel_info(clean)
        if info and "error" not in info:
            return {
                "ok": True,
                "found": True,
                "source": "telegram",
                "channel": {
                    "username": clean,
                    "title": info.get("title", clean),
                    "participantsCount": info.get("participantsCount", 0),
                    "about": info.get("about", ""),
                    "isChannel": info.get("isChannel", True),
                }
            }

        # Username not found — try global search by title/name
        results = await client.search_global(username.strip(), limit=5)
        if results:
            return {
                "ok": True,
                "found": True,
                "source": "telegram_search",
                "channels": results,
            }

        return {
            "ok": True,
            "found": False,
            "source": "telegram",
            "error": "Channel not found"
        }
    except Exception as e:
        logger.error(f"Telegram search error for @{clean}: {e}")
        return {"ok": False, "error": str(e)}


async def add_channel_from_telegram(db, username: str) -> Dict[str, Any]:
    """Add a new channel to tracking: fetch info, messages, compute metrics"""
    clean = _clean_username(username)
    if not clean:
        return {"ok": False, "error": "Empty username"}

    # Check if already exists
    existing = await db.tg_channel_states.find_one({"username": clean})
    if existing:
        return {"ok": True, "status": "already_exists", "username": clean}

    try:
        from ..api.admin import get_mtproto_client, MTPROTO_AVAILABLE
        if not MTPROTO_AVAILABLE:
            return {"ok": False, "error": "Telegram connection not available"}

        client = get_mtproto_client()
        if not await client.is_connected():
            connected = await client.connect(db=db)
            if not connected:
                return {"ok": False, "error": "Cannot connect to Telegram"}

        now = datetime.now(timezone.utc)

        # Fetch channel info
        info = await client.get_channel_info(clean)
        if not info or "error" in info:
            return {"ok": False, "error": info.get("error", "Channel not found") if info else "Channel not found"}

        # Create channel record
        await db.tg_channel_states.update_one(
            {"username": clean},
            {
                "$set": {
                    "username": clean,
                    "title": info["title"],
                    "about": info.get("about", ""),
                    "participantsCount": info["participantsCount"],
                    "isChannel": info["isChannel"],
                    "lastMtprotoFetch": now,
                    "updatedAt": now,
                    "stage": "QUALIFIED",
                },
                "$setOnInsert": {"createdAt": now},
            },
            upsert=True,
        )

        # Download avatar
        try:
            avatar_url = await client.download_profile_photo(clean)
            if avatar_url:
                await db.tg_channel_states.update_one(
                    {"username": clean},
                    {"$set": {"avatarUrl": avatar_url}}
                )
        except Exception:
            pass

        # Fetch messages with media
        messages_count = 0
        try:
            msgs = await client.get_channel_messages(clean, limit=50, db=db)
            if msgs:
                for msg in msgs:
                    d = msg.get("date")
                    if isinstance(d, str):
                        try:
                            msg["date"] = datetime.fromisoformat(d)
                        except Exception:
                            pass
                    await db.tg_posts.update_one(
                        {"username": clean, "messageId": msg["messageId"]},
                        {"$set": {**msg, "username": clean, "updatedAt": now},
                         "$setOnInsert": {"createdAt": now}},
                        upsert=True,
                    )
                messages_count = len(msgs)
        except Exception as e:
            logger.warning(f"Message fetch error for @{clean}: {e}")

        # Detect language
        try:
            from langdetect import detect, DetectorFactory
            DetectorFactory.seed = 0
            posts = await db.tg_posts.find(
                {"username": clean, "text": {"$ne": None}},
                {"_id": 0, "text": 1}
            ).sort("date", -1).limit(10).to_list(10)
            combined = ' '.join([p['text'] for p in posts if p.get('text') and len(p['text']) > 20])
            if combined and len(combined) > 30:
                detected = detect(combined[:2000])
                lang_map = {'ru': 'RU', 'uk': 'UA', 'en': 'EN'}
                lang = lang_map.get(detected, 'EN')
            else:
                lang = 'EN'
            await db.tg_channel_states.update_one(
                {"username": clean},
                {"$set": {"language": lang}}
            )
        except Exception:
            await db.tg_channel_states.update_one(
                {"username": clean},
                {"$set": {"language": "EN"}}
            )

        # Write members history
        try:
            from ..services.members_history import write_members_history
            await write_members_history(db, clean, info["participantsCount"])
        except Exception:
            pass

        # Compute metrics
        try:
            from ..services.metrics import compute_channel_metrics
            await compute_channel_metrics(db, clean)
        except Exception as e:
            logger.warning(f"Metrics compute error for @{clean}: {e}")

        # Channel is added but NOT auto-added to watchlist
        # User decides whether to add to favorites themselves

        return {
            "ok": True,
            "status": "added",
            "username": clean,
            "title": info["title"],
            "members": info["participantsCount"],
            "messages": messages_count,
        }
    except Exception as e:
        logger.error(f"Add channel error for @{clean}: {e}")
        return {"ok": False, "error": str(e)}
