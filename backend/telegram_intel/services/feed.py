"""
Telegram Intel - Feed Service
Version: 1.0.0

Proxy to existing implementation in telegram_lite.
"""

import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone, timedelta
from telegram_intel.services.channel import is_ad_post

logger = logging.getLogger(__name__)


async def get_feed_v2(
    db,
    actor_id: str = "default",
    page: int = 1,
    limit: int = 50,
    window_days: int = 30,
    language: str = None,
    has_media: bool = None,
    min_views: int = None,
    sort_by: str = "date",
) -> Dict[str, Any]:
    """Get feed posts for actor"""
    try:
        # Get watchlist
        watchlist = await db.tg_watchlist.find(
            {"$or": [
                {"actorId": actor_id},
                {"actorId": "a_public"},
                {"actorId": "default"},
                {"actorId": {"$exists": False}}
            ]},
            {"username": 1, "_id": 0}
        ).to_list(500)
        
        usernames = list(set(w.get("username") for w in watchlist if w.get("username")))
        
        if not usernames:
            return {"ok": True, "items": [], "total": 0, "page": page, "pages": 1, "message": "No channels in watchlist"}
        
        # Filter by language — get only channels with matching language
        if language and language.strip().upper() in ("EN", "RU", "UA"):
            lang_channels = await db.tg_channel_states.find(
                {"username": {"$in": usernames}, "language": language.strip().upper()},
                {"_id": 0, "username": 1}
            ).to_list(500)
            usernames = [c["username"] for c in lang_channels]
            if not usernames:
                return {"ok": True, "items": [], "total": 0, "page": page, "pages": 1, "message": "No channels match language filter"}
        
        # Build post query
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        post_filter = {"username": {"$in": usernames}, "date": {"$gte": cutoff}}
        
        if has_media:
            post_filter["hasMedia"] = True
        if min_views and min_views > 0:
            post_filter["views"] = {"$gte": min_views}
        
        # Sort
        sort_key = "date"
        sort_dir = -1
        if sort_by == "views":
            sort_key = "views"
        elif sort_by == "forwards":
            sort_key = "forwards"
        elif sort_by == "reactions":
            sort_key = "reactions.total"
        
        total = await db.tg_posts.count_documents(post_filter)
        
        # Diversified feed: ensure mix of channels on every page
        # Fetch top posts per channel, then merge by sort key
        n_channels = max(len(usernames), 1)
        per_ch = max((limit * 3) // n_channels, 3)  # fetch enough per channel
        
        all_posts = []
        for uname in usernames:
            ch_filter = {**post_filter, "username": uname}
            ch_posts = await db.tg_posts.find(ch_filter).sort([(sort_key, sort_dir)]).limit(per_ch).to_list(per_ch)
            all_posts.extend(ch_posts)
        
        # Sort merged posts by sort key
        def get_sort_val(p):
            if sort_key == "reactions.total":
                r = p.get("reactions", {})
                return r.get("total", 0) if isinstance(r, dict) else (r if isinstance(r, (int, float)) else 0)
            return p.get(sort_key, 0)
        
        all_posts.sort(key=get_sort_val, reverse=(sort_dir == -1))
        
        # Pagination on the diversified result
        skip = (page - 1) * limit
        posts = all_posts[skip:skip + limit]
        
        # Build channel metadata lookup
        ch_map = {}
        for u in usernames:
            ch = await db.tg_channel_states.find_one(
                {"username": u},
                {"_id": 0, "username": 1, "title": 1, "avatarUrl": 1, "sector": 1, "sectorColor": 1, "aiSummary": 1}
            )
            if ch:
                ai = ch.get("aiSummary") or {}
                ch_map[u] = {
                    "title": ch.get("title", u),
                    "avatarUrl": ch.get("avatarUrl"),
                    "sector": ch.get("sector") or ai.get("sector"),
                    "sectorColor": ch.get("sectorColor") or ai.get("sectorColor"),
                }

        # Get read/pin state for actor
        state_keys = [f"{p.get('username')}:{p.get('messageId')}" for p in posts]
        feed_states = {}
        if state_keys:
            states = await db.tg_feed_state.find(
                {"actorId": {"$in": [actor_id, "default"]}, "postKey": {"$in": state_keys}},
                {"_id": 0}
            ).to_list(500)
            for s in states:
                feed_states[s.get("postKey", "")] = s

        # Batch-load media assets for posts with media
        media_posts = [(p.get("username"), p.get("messageId")) for p in posts if p.get("hasMedia")]
        media_map = {}
        if media_posts:
            media_filter = {"$or": [{"username": u, "messageId": m, "status": "READY"} for u, m in media_posts]}
            media_assets = await db.tg_media_assets.find(media_filter, {"_id": 0}).to_list(200)
            for ma in media_assets:
                media_map[f"{ma.get('username')}:{ma.get('messageId')}"] = ma

        # Build response
        items = []
        for p in posts:
            reactions = p.get("reactions", {})
            if isinstance(reactions, int):
                reactions = {"total": reactions, "top": [], "extraCount": 0}
            elif isinstance(reactions, dict):
                items_list = reactions.get("items", [])
                reactions = {
                    "total": reactions.get("total", 0),
                    "top": items_list[:3],
                    "extraCount": max(len(items_list) - 3, 0)
                }
            
            uname = p.get("username", "")
            ch = ch_map.get(uname, {})
            post_key = f"{uname}:{p.get('messageId')}"
            state = feed_states.get(post_key, {})

            # Media info
            media_asset = media_map.get(post_key)
            media_info = None
            if media_asset:
                raw_url = media_asset.get("url", "")
                if raw_url.startswith("/tg/media/"):
                    raw_url = "/api/telegram-intel/media/" + raw_url[len("/tg/media/"):]
                media_info = {
                    "url": raw_url,
                    "kind": media_asset.get("kind"),
                    "w": media_asset.get("w"),
                    "h": media_asset.get("h"),
                }

            items.append({
                "messageId": p.get("messageId"),
                "username": uname,
                "date": str(p.get("date", "")),
                "text": p.get("text", ""),
                "views": p.get("views", 0),
                "forwards": p.get("forwards", 0),
                "replies": p.get("replies", 0),
                "reactions": reactions,
                "hasMedia": p.get("hasMedia", False),
                "media": media_info,
                "isAd": p.get("isAd") or is_ad_post(p.get("text", "")),
                "feedScore": 0.0,
                "isPinned": state.get("isPinned", False),
                "pinnedInChannel": p.get("pinnedInChannel", False),
                "isRead": state.get("isRead", False),
                "channelTitle": ch.get("title", uname),
                "channelAvatar": ch.get("avatarUrl"),
                "channelSector": ch.get("sector"),
                "channelSectorColor": ch.get("sectorColor"),
            })
        
        pages = (total + limit - 1) // limit if total > 0 else 1
        
        return {
            "ok": True,
            "items": items,
            "total": total,
            "page": page,
            "pages": pages,
            "hasMore": page < pages,
            "watchlistCount": len(usernames),
        }
    except Exception as e:
        logger.error(f"Feed error: {e}")
        return {"ok": False, "error": str(e), "items": [], "total": 0}


async def get_feed_stats(db, actor_id: str = "default", hours: int = 24) -> Dict[str, Any]:
    """Get feed statistics"""
    try:
        watchlist = await db.tg_watchlist.find(
            {"$or": [{"actorId": actor_id}, {"actorId": "a_public"}, {"actorId": "default"}]},
            {"username": 1, "_id": 0}
        ).to_list(500)
        
        usernames = list(set(w.get("username") for w in watchlist if w.get("username")))
        channels_count = len(usernames)
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        posts_count = await db.tg_posts.count_documents(
            {"username": {"$in": usernames}, "date": {"$gte": cutoff}}
        ) if usernames else 0
        
        media_count = await db.tg_media_assets.count_documents(
            {"username": {"$in": usernames}}
        ) if usernames else 0
        
        pinned_count = await db.tg_feed_state.count_documents({"isPinned": True})
        
        return {
            "ok": True,
            "channelsInFeed": channels_count,
            "postsToday": posts_count,
            "mediaCount": media_count,
            "avgViews": 0,
            "pinnedCount": pinned_count,
            "unreadCount": 0,
            "hoursWindow": hours
        }
    except Exception as e:
        logger.error(f"Feed stats error: {e}")
        return {"ok": False, "error": str(e)}


async def get_feed_summary(db, hours: int = 24, llm_key: Optional[str] = None, actor_id: str = "default") -> Dict[str, Any]:
    """Get AI-generated feed summary using OpenAI (filtered by feed channels)"""
    if not llm_key:
        return {
            "ok": True,
            "summary": None,
            "postsAnalyzed": 0,
            "channelsCount": 0,
            "hoursWindow": hours,
            "error": "LLM not configured"
        }

    try:
        # Get watchlist channels
        watchlist = await db.tg_watchlist.find(
            {"$or": [{"actorId": actor_id}, {"actorId": "a_public"}, {"actorId": "default"}]},
            {"username": 1, "_id": 0}
        ).to_list(500)
        usernames = list(set(w.get("username") for w in watchlist if w.get("username")))

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        post_filter = {"date": {"$gte": cutoff}}
        if usernames:
            post_filter["username"] = {"$in": usernames}
        posts = await db.tg_posts.find(
            post_filter,
            {"_id": 0, "username": 1, "text": 1, "views": 1, "forwards": 1, "date": 1}
        ).sort("views", -1).limit(30).to_list(30)

        if not posts:
            return {
                "ok": True,
                "summary": f"No posts in the last {hours} hours.",
                "postsAnalyzed": 0,
                "channelsCount": 0,
                "hoursWindow": hours,
            }

        channels = set(p.get("username", "") for p in posts)
        posts_text = []
        for p in posts[:20]:
            text = (p.get("text") or "")[:300]
            if text:
                posts_text.append(f"[@{p.get('username')}] {text}")

        prompt = f"""Analyze these {len(posts_text)} Telegram channel posts from the last {hours}h. 
Write a concise intelligence briefing (3-4 sentences) highlighting:
- Key themes and narratives
- Notable signals or breaking news
- Market sentiment if applicable

Posts:
{chr(10).join(posts_text[:15])}"""

        try:
            from openai import OpenAI
            client = OpenAI(api_key=llm_key)
            r = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a crypto/tech intelligence analyst. Provide concise, actionable summaries of Telegram channel activity. Be specific about trends and signals. Respond in 3-4 sentences max."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=250
            )
            summary_text = r.choices[0].message.content.strip()
        except Exception as llm_err:
            logger.error(f"LLM call error: {llm_err}")
            summary_text = None

        return {
            "ok": True,
            "summary": summary_text,
            "postsAnalyzed": len(posts),
            "channelsCount": len(channels),
            "hoursWindow": hours,
        }
    except Exception as e:
        logger.error(f"Feed summary error: {e}")
        return {
            "ok": True,
            "summary": None,
            "postsAnalyzed": 0,
            "channelsCount": 0,
            "hoursWindow": hours,
            "error": str(e)
        }
