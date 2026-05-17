"""
Telegram Intel - Extended API Routes
All endpoints required by the frontend that weren't in the base module.
Self-contained, queries only tg_* collections.
"""
import os
import re
import uuid
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)


def normalize_username(raw: str) -> str:
    """Normalize telegram username"""
    return raw.lower().replace("@", "").replace("https://t.me/", "").replace("t.me/", "").split("/")[0].split("?")[0].strip()


def format_title(username: str) -> str:
    """Generate title from username"""
    return username.replace("_", " ").replace("-", " ").title()


def avatar_color(username: str) -> str:
    """Deterministic color from username"""
    h = int(hashlib.md5(username.encode()).hexdigest()[:6], 16)
    return f"hsl({h % 360}, 70%, 55%)"


def activity_label(posts_per_day: float) -> str:
    if posts_per_day >= 10: return "Very High"
    if posts_per_day >= 5: return "High"
    if posts_per_day >= 1: return "Medium"
    return "Low"


def red_flags(fraud: float) -> list:
    flags = []
    if fraud > 0.6: flags.append("High fraud risk")
    if fraud > 0.4: flags.append("Elevated bot activity")
    return flags


def create_extended_router(module) -> APIRouter:
    """Create router with all extended endpoints. 
    `module` is the TelegramModule instance (gives access to db).
    """
    router = APIRouter(prefix="/api/telegram-intel", tags=["telegram-intel-ext"])

    async def get_db():
        return module.db

    # ─── Channel Overview ─────────────────────────────────────────────
    @router.get("/channel/{username}/overview")
    async def channel_overview(username: str):
        db = await get_db()
        if db is None:
            return {"ok": False, "error": "DB not connected"}
        cu = normalize_username(username)
        try:
            state = await db.tg_channel_states.find_one({"username": cu}, {"_id": 0})
            snapshot = None
            try:
                snapshot = await db.tg_score_snapshots.find_one(
                    {"username": cu}, {"_id": 0}, sort=[("date", -1)]
                )
            except Exception:
                pass

            if not state:
                return {"ok": False, "error": "NOT_FOUND", "message": f"Channel @{cu} not found"}

            posts = await db.tg_posts.find(
                {"username": cu}, {"_id": 0}
            ).sort("date", -1).limit(50).to_list(50)

            members = state.get("participantsCount", 0) or 0
            utility_score = snapshot.get("utility", 50) if snapshot else 50
            fraud_risk = snapshot.get("fraud", 0.2) if snapshot else 0.2
            stab = snapshot.get("stability", 0.7) if snapshot else 0.7
            engagement = snapshot.get("engagement", 0.1) if snapshot else 0.1
            ppd = snapshot.get("postsPerDay", 1) if snapshot else 1
            g7 = snapshot.get("growth7", 0) if snapshot else 0
            g30 = snapshot.get("growth30", 0) if snapshot else 0

            quality_likes = sum([
                1 if g7 > 0 else 0,
                1 if engagement > 0.05 else 0,
                1 if fraud_risk < 0.35 else 0,
                1 if stab > 0.55 else 0,
                1 if members > 5000 else 0,
            ])
            stars = min(5, max(0, round(utility_score / 20)))

            recent_posts = []
            for p in posts[:10]:
                pd = p.get("date")
                date_str = pd.isoformat() if isinstance(pd, datetime) else str(pd) if pd else datetime.now(timezone.utc).isoformat()
                mid = p.get("messageId")
                recent_posts.append({
                    "id": str(mid or uuid.uuid4()),
                    "messageId": mid,
                    "username": cu,
                    "date": date_str,
                    "text": p.get("text") or "",
                    "views": p.get("views", 0),
                    "forwards": p.get("forwards", 0),
                    "replies": p.get("replies", 0),
                    "reactions": p.get("reactions", 0),
                })

            result = {
                "ok": True,
                "profile": {
                    "username": cu,
                    "title": state.get("title") or format_title(cu),
                    "avatarUrl": state.get("avatarUrl"),
                    "avatarColor": avatar_color(cu),
                    "type": "Group" if state.get("isChannel") is False else "Channel",
                    "about": state.get("about") or "",
                },
                "topCards": {
                    "subscribers": members,
                    "viewsPerPost": int(members * engagement),
                    "messagesPerDay": ppd,
                    "activityLevel": activity_label(ppd),
                },
                "metrics": {
                    "utilityScore": utility_score,
                    "growth7": g7,
                    "growth30": g30,
                    "engagement": engagement,
                    "fraud": fraud_risk,
                    "stability": stab,
                },
                "qualitySignals": {"likes": quality_likes, "stars": stars},
                "audienceSnapshot": {
                    "total": members,
                    "growth7d": g7,
                    "growth30d": g30,
                    "engagementRate": engagement,
                },
                "activityOverview": {
                    "postsPerDay": ppd,
                    "activeDays": 7,
                    "consistency": stab,
                },
                "healthSafety": {
                    "fraudRisk": fraud_risk,
                    "stability": stab,
                    "redFlags": red_flags(fraud_risk),
                    "trustScore": round((1 - fraud_risk) * 100),
                },
                "aiSummary": state.get("aiSummary"),
                "eligibility": state.get("eligibility", {}),
                "network": {"inbound": [], "outbound": []},
                "recentPosts": recent_posts,
                "timeline": [],
            }

            # Add related channels
            try:
                sector = state.get("sector")
                related = []
                if sector:
                    sector_words = [w for w in sector.split() if len(w) > 3]
                    if sector_words:
                        pattern = "|".join(sector_words)
                        related = await db.tg_channel_states.find(
                            {"username": {"$ne": cu}, "sector": {"$regex": pattern, "$options": "i"}},
                            {"_id": 0, "username": 1, "title": 1, "participantsCount": 1, "avatarUrl": 1, "sector": 1, "sectorColor": 1, "fomoScore": 1}
                        ).sort("fomoScore", -1).limit(5).to_list(5)
                if not related:
                    related = await db.tg_channel_states.find(
                        {"username": {"$ne": cu}},
                        {"_id": 0, "username": 1, "title": 1, "participantsCount": 1, "avatarUrl": 1, "sector": 1, "sectorColor": 1, "fomoScore": 1}
                    ).sort("fomoScore", -1).limit(5).to_list(5)
                result["relatedChannels"] = related
            except Exception:
                result["relatedChannels"] = []

            return result
        except Exception as e:
            logger.error(f"Channel overview error: {e}")
            return {"ok": False, "error": str(e)}

    # ─── Watchlist Check ──────────────────────────────────────────────
    @router.get("/watchlist/check/{username}")
    async def watchlist_check(username: str, actorId: str = "default"):
        db = await get_db()
        if db is None:
            return {"ok": True, "inWatchlist": False}
        cu = normalize_username(username)
        try:
            doc = await db.tg_watchlist.find_one(
                {"username": cu, "$or": [{"actorId": actorId}, {"actorId": {"$exists": False}}]},
                {"_id": 0}
            )
            return {"ok": True, "inWatchlist": doc is not None}
        except Exception as e:
            return {"ok": False, "error": str(e), "inWatchlist": False}

    # ─── Feed Search ──────────────────────────────────────────────────
    @router.get("/feed/search")
    async def feed_search(
        q: str = "",
        actorId: str = "default",
        page: int = 1,
        limit: int = 30,
        days: int = 30,
        username: Optional[str] = None,
    ):
        """Search posts by keyword and/or filter by channel username.
        If username is provided, filter posts by that author.
        If q is provided, filter posts by text content.
        Both can be combined.
        """
        db = await get_db()
        if db is None:
            return {"ok": True, "items": [], "total": 0, "pages": 0}
        try:
            page = max(1, page)
            limit = max(1, min(limit, 50))
            skip = (page - 1) * limit
            days = max(1, min(days, 365))
            q = (q or "").strip()[:120]
            q = re.sub(r"\s+", " ", q)

            # If neither query nor username, return empty
            if not q and not username:
                return {"ok": True, "items": [], "total": 0, "pages": 0}

            since = datetime.now(timezone.utc) - timedelta(days=days)
            filt = {"date": {"$gte": since}}

            # Filter by author if username provided
            if username:
                cu = normalize_username(username)
                filt["username"] = cu
            else:
                # Search across all channels in watchlist
                wl = await db.tg_watchlist.find(
                    {"$or": [{"actorId": actorId}, {"actorId": "a_public"}, {"actorId": "default"}, {"actorId": {"$exists": False}}]},
                    {"username": 1, "_id": 0}
                ).to_list(500)
                usernames = list(set(w["username"] for w in wl if w.get("username")))
                if usernames:
                    filt["username"] = {"$in": usernames}

            # Filter by text content if q provided
            if q:
                filt["text"] = {"$regex": re.escape(q), "$options": "i"}

            total = await db.tg_posts.count_documents(filt)
            posts = await db.tg_posts.find(filt, {"_id": 0}).sort("date", -1).skip(skip).limit(limit).to_list(limit)

            ch_map = {}
            for u in set(p.get("username") for p in posts):
                ch = await db.tg_channel_states.find_one({"username": u}, {"_id": 0, "username": 1, "title": 1, "avatarUrl": 1, "sector": 1, "sectorColor": 1})
                if ch:
                    ch_map[u] = ch

            # Batch-load media assets
            media_posts = [(p.get("username"), p.get("messageId")) for p in posts if p.get("hasMedia")]
            media_map = {}
            if media_posts:
                media_filter = {"$or": [{"username": u, "messageId": m, "status": "READY"} for u, m in media_posts]}
                media_assets = await db.tg_media_assets.find(media_filter, {"_id": 0}).to_list(200)
                for ma in media_assets:
                    media_map[f"{ma.get('username')}:{ma.get('messageId')}"] = ma

            items = []
            for p in posts:
                uname = p.get("username")
                ch = ch_map.get(uname, {})
                reactions = p.get("reactions", {})
                if isinstance(reactions, int):
                    reactions = {"total": reactions, "top": [], "extraCount": 0}
                elif isinstance(reactions, dict):
                    items_list = reactions.get("items", [])
                    reactions = {"total": reactions.get("total", 0), "top": items_list[:3], "extraCount": max(len(items_list) - 3, 0)}

                pd = p.get("date")
                date_str = pd.isoformat() if isinstance(pd, datetime) else str(pd) if pd else ""

                post_key = f"{uname}:{p.get('messageId')}"
                media_asset = media_map.get(post_key)
                media_info = None
                if media_asset:
                    media_info = {
                        "url": media_asset.get("url"),
                        "kind": media_asset.get("kind"),
                        "w": media_asset.get("w"),
                        "h": media_asset.get("h"),
                    }

                items.append({
                    "messageId": p.get("messageId"),
                    "username": uname,
                    "date": date_str,
                    "text": p.get("text", ""),
                    "views": p.get("views", 0),
                    "forwards": p.get("forwards", 0),
                    "replies": p.get("replies", 0),
                    "reactions": reactions,
                    "hasMedia": p.get("hasMedia", False),
                    "media": media_info,
                    "feedScore": 0.0,
                    "pinnedInChannel": p.get("pinnedInChannel", False),
                    "channelTitle": ch.get("title", uname),
                    "channelAvatar": ch.get("avatarUrl"),
                    "channelSector": ch.get("sector"),
                    "channelSectorColor": ch.get("sectorColor"),
                })

            pages_count = max(1, (total + limit - 1) // limit)
            return {"ok": True, "q": q, "username": username, "items": items, "total": total, "page": page, "pages": pages_count}
        except Exception as e:
            logger.error(f"Feed search error: {e}")
            return {"ok": False, "error": str(e), "items": [], "total": 0}

    # ─── Helper: get watchlist usernames ─────────────────────────────
    async def _get_feed_usernames(db, actor_id: str = "default") -> list:
        """Get list of usernames in the user's feed/watchlist"""
        watchlist = await db.tg_watchlist.find(
            {"$or": [{"actorId": actor_id}, {"actorId": "a_public"}, {"actorId": "default"}]},
            {"username": 1, "_id": 0}
        ).to_list(500)
        return list(set(w.get("username") for w in watchlist if w.get("username")))

    # ─── Topics Momentum ──────────────────────────────────────────────
    @router.get("/topics/momentum")
    async def topics_momentum(limit: int = 20, hours: int = 24):
        db = await get_db()
        if db is None:
            return {"ok": True, "windowHours": hours, "topics": []}
        try:
            usernames = await _get_feed_usernames(db)
            from telegram_intel.services.metrics import extract_topics
            topics = await extract_topics(db, hours=hours, min_mentions=2, usernames=usernames or None)
            actual_hours = hours
            if not topics and hours < 72:
                actual_hours = min(hours * 3, 72)
                topics = await extract_topics(db, hours=actual_hours, min_mentions=2, usernames=usernames or None)
            return {"ok": True, "windowHours": actual_hours, "topics": topics[:limit]}
        except Exception as e:
            logger.error(f"Topic momentum error: {e}")
            return {"ok": True, "windowHours": hours, "topics": []}

    # ─── Cross-Channel Signals ────────────────────────────────────────
    @router.get("/signals/cross-channel")
    async def cross_channel_signals(window: int = 120, refresh: bool = False):
        db = await get_db()
        if db is None:
            return {"ok": True, "windowMinutes": window, "eventCount": 0, "events": []}
        try:
            usernames = await _get_feed_usernames(db)
            from telegram_intel.services.metrics import detect_cross_channel_signals
            events = await detect_cross_channel_signals(db, window_minutes=window, usernames=usernames or None)
            return {"ok": True, "windowMinutes": window, "eventCount": len(events), "events": events}
        except Exception as e:
            logger.error(f"Cross-channel signal error: {e}")
            return {"ok": True, "windowMinutes": window, "eventCount": 0, "events": []}

    # ─── Feed: Read / Pin ─────────────────────────────────────────────
    @router.post("/feed/me/read")
    async def mark_post_read(body: dict = None):
        db = await get_db()
        if db is None:
            return {"ok": False, "error": "DB not connected"}
        try:
            body = body or {}
            post_key = body.get("postKey", "")
            is_read = body.get("isRead", True)
            actor_id = body.get("actorId", "default")
            if not post_key:
                return {"ok": False, "error": "postKey required"}
            now = datetime.now(timezone.utc)
            await db.tg_feed_state.update_one(
                {"actorId": actor_id, "postKey": post_key},
                {"$set": {"actorId": actor_id, "postKey": post_key, "isRead": is_read, "updatedAt": now}},
                upsert=True,
            )
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @router.post("/feed/me/pin")
    async def toggle_post_pin(body: dict = None):
        db = await get_db()
        if db is None:
            return {"ok": False, "error": "DB not connected"}
        try:
            body = body or {}
            post_key = body.get("postKey", "")
            if not post_key:
                u = body.get("username", "")
                mid = body.get("messageId", "")
                if u and mid:
                    post_key = f"{u}:{mid}"
            is_pinned = body.get("isPinned", True)
            actor_id = body.get("actorId", "default")
            if not post_key:
                return {"ok": False, "error": "postKey or username+messageId required"}
            now = datetime.now(timezone.utc)
            await db.tg_feed_state.update_one(
                {"actorId": actor_id, "postKey": post_key},
                {"$set": {"actorId": actor_id, "postKey": post_key, "isPinned": is_pinned, "updatedAt": now}},
                upsert=True,
            )
            return {"ok": True, "postKey": post_key, "isPinned": is_pinned}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ─── Bot Endpoints (stubs – bot managed globally) ─────────────────
    @router.post("/bot/connect")
    async def bot_connect():
        return {"ok": False, "error": "Bot managed globally. Configure via platform settings."}

    @router.post("/bot/disconnect")
    async def bot_disconnect():
        return {"ok": False, "error": "Bot managed globally. Configure via platform settings."}

    @router.get("/bot/preferences")
    async def bot_preferences(actorId: str = "default"):
        return {"ok": True, "preferences": {"enabled": False, "actorId": actorId}}

    @router.post("/bot/test")
    async def bot_test():
        return {"ok": False, "error": "Bot managed globally. Use platform bot settings."}

    # ─── Helper: aggregate edges from tg_network_edges ─────────────
    async def _aggregate_edges(db, match_filter: dict, limit: int = 1000) -> list:
        """Aggregate raw network edges into {source, target, method, count, weight}"""
        pipeline = [
            {"$match": match_filter},
            {"$group": {
                "_id": {"from": "$from", "to": "$to", "method": "$method"},
                "count": {"$sum": 1},
                "weight": {"$sum": "$weight"},
            }},
            {"$project": {
                "_id": 0,
                "source": "$_id.from",
                "target": "$_id.to",
                "method": "$_id.method",
                "count": 1,
                "weight": 1,
            }},
            {"$limit": limit},
        ]
        return await db.tg_network_edges.aggregate(pipeline).to_list(limit)

    # ─── Network / Graph ──────────────────────────────────────────────
    @router.get("/network/list")
    async def network_list():
        db = await get_db()
        if db is None:
            return {"ok": True, "nodes": [], "edges": []}
        try:
            channels = await db.tg_channel_states.find(
                {"eligible": True}, {"_id": 0, "username": 1, "title": 1, "participantsCount": 1, "sector": 1}
            ).limit(200).to_list(200)
            nodes = [{"id": c["username"], "label": c.get("title", c["username"]), "size": c.get("participantsCount", 0), "sector": c.get("sector")} for c in channels]
            edges = await _aggregate_edges(db, {})
            return {"ok": True, "nodes": nodes, "edges": edges}
        except Exception as e:
            return {"ok": True, "nodes": [], "edges": []}

    @router.get("/channel/{username}/network/edges")
    async def channel_network_edges(username: str, days: int = 30):
        db = await get_db()
        if db is None:
            return {"ok": True, "inbound": [], "outbound": []}
        cu = normalize_username(username)
        try:
            inbound = await _aggregate_edges(db, {"to": cu}, 50)
            outbound = await _aggregate_edges(db, {"from": cu}, 50)
            return {"ok": True, "inbound": inbound, "outbound": outbound}
        except Exception as e:
            return {"ok": True, "inbound": [], "outbound": []}

    @router.get("/graph")
    async def graph_data(root: Optional[str] = None, depth: int = 2):
        db = await get_db()
        if db is None:
            return {"ok": True, "nodes": [], "edges": [], "stats": {}}
        try:
            # Step 1: Get direct edges involving root (aggregated from raw data)
            if root:
                cu = normalize_username(root)
                match = {"$or": [{"from": cu}, {"to": cu}]}
            else:
                match = {}
            
            direct_edges = await _aggregate_edges(db, match)
            
            # Collect all neighbor usernames
            edge_usernames = set()
            for e in direct_edges:
                edge_usernames.add(e.get("source"))
                edge_usernames.add(e.get("target"))
            
            # Step 2: Depth-2 — find cross-edges and reverse edges
            all_edges = list(direct_edges)
            if root and len(edge_usernames) > 1:
                neighbors = list(edge_usernames - {cu})
                if neighbors:
                    cross_edges = await _aggregate_edges(db, {
                        "from": {"$in": neighbors},
                        "to": {"$in": neighbors + [cu]}
                    }, 500)
                    existing = {(e["source"], e["target"], e["method"]) for e in all_edges}
                    for ce in cross_edges:
                        key = (ce["source"], ce["target"], ce["method"])
                        if key not in existing:
                            all_edges.append(ce)
                            existing.add(key)
                            edge_usernames.add(ce["source"])
                            edge_usernames.add(ce["target"])
            
            # Step 3: Build nodes
            if root:
                relevant = edge_usernames
            else:
                relevant = None
            
            ch_filter = {"username": {"$in": list(relevant)}} if relevant else {}
            channels = await db.tg_channel_states.find(
                ch_filter, {"_id": 0, "username": 1, "title": 1, "participantsCount": 1, "sector": 1}
            ).limit(200).to_list(200)
            
            nodes = []
            seen_ids = set()
            for c in channels:
                nodes.append({"id": c["username"], "label": c.get("title", c["username"]), "size": c.get("participantsCount", 0), "sector": c.get("sector")})
                seen_ids.add(c["username"])
            
            for u in edge_usernames:
                if u and u not in seen_ids:
                    nodes.append({"id": u, "label": u, "size": 0, "sector": None, "external": True})
                    seen_ids.add(u)
            
            return {"ok": True, "nodes": nodes, "edges": all_edges, "stats": {"nodeCount": len(nodes), "edgeCount": len(all_edges)}}
        except Exception as e:
            return {"ok": True, "nodes": [], "edges": [], "stats": {}}

    @router.get("/graph/stats")
    async def graph_stats():
        db = await get_db()
        if db is None:
            return {"ok": True, "totalNodes": 0, "totalEdges": 0}
        try:
            nodes = await db.tg_channel_states.count_documents({"eligible": True})
            edges = await db.tg_network_edges.count_documents({})
            return {"ok": True, "totalNodes": nodes, "totalEdges": edges}
        except Exception as e:
            return {"ok": True, "totalNodes": 0, "totalEdges": 0}

    # ─── Aggregate Stats (stats cards on entities page) ─────────────────
    @router.get("/stats/aggregate")
    async def aggregate_stats():
        db = await get_db()
        if db is None:
            return {"ok": True, "tracked": 0, "avgScore": 0, "highGrowth": 0, "highRisk": 0}
        try:
            from telegram_intel.services.metrics import compute_aggregate_stats
            stats = await compute_aggregate_stats(db)
            return {"ok": True, **stats}
        except Exception as e:
            return {"ok": True, "tracked": 0, "avgScore": 0, "highGrowth": 0, "highRisk": 0}

    # ─── Related Channels ─────────────────────────────────────────────
    @router.get("/channel/{username}/related")
    async def related_channels(username: str, limit: int = 5):
        db = await get_db()
        if db is None:
            return {"ok": True, "related": []}
        try:
            from telegram_intel.services.metrics import get_related_channels
            related = await get_related_channels(db, normalize_username(username), limit)
            return {"ok": True, "related": related}
        except Exception as e:
            return {"ok": True, "related": []}

    # ─── Channel Search (entities page) ───────────────────────────────
    @router.get("/channels/search")
    async def channels_search(q: str = "", limit: int = 20):
        db = await get_db()
        if db is None:
            return {"ok": True, "items": [], "total": 0}
        try:
            q = (q or "").strip()
            if not q:
                return {"ok": True, "items": [], "total": 0}
            filt = {"$or": [
                {"username": {"$regex": re.escape(q), "$options": "i"}},
                {"title": {"$regex": re.escape(q), "$options": "i"}},
            ]}
            channels = await db.tg_channel_states.find(filt, {"_id": 0}).limit(limit).to_list(limit)
            items = []
            for ch in channels:
                ai = ch.get("aiSummary") or {}
                items.append({
                    "username": ch.get("username"),
                    "title": ch.get("title"),
                    "avatarUrl": ch.get("avatarUrl"),
                    "members": ch.get("participantsCount", 0),
                    "sector": ch.get("sector") or ai.get("sector"),
                    "fomoScore": ch.get("fomoScore", 0),
                })
            return {"ok": True, "items": items, "total": len(items)}
        except Exception as e:
            return {"ok": True, "items": [], "total": 0}

    # ─── Channel Autocomplete (fast suggest) ──────────────────────────
    @router.get("/channels/autocomplete")
    async def channels_autocomplete(q: str = "", limit: int = 8):
        db = await get_db()
        if db is None:
            return {"ok": True, "suggestions": []}
        try:
            q = (q or "").strip()
            if len(q) < 1:
                return {"ok": True, "suggestions": []}
            filt = {"$or": [
                {"username": {"$regex": re.escape(q), "$options": "i"}},
                {"title": {"$regex": re.escape(q), "$options": "i"}},
            ]}
            channels = await db.tg_channel_states.find(
                filt,
                {"_id": 0, "username": 1, "title": 1, "avatarUrl": 1, "participantsCount": 1, "sector": 1, "sectorColor": 1}
            ).sort("fomoScore", -1).limit(limit).to_list(limit)
            suggestions = []
            for ch in channels:
                suggestions.append({
                    "username": ch.get("username"),
                    "title": ch.get("title") or ch.get("username"),
                    "avatarUrl": ch.get("avatarUrl"),
                    "members": ch.get("participantsCount", 0),
                    "sector": ch.get("sector"),
                    "sectorColor": ch.get("sectorColor"),
                })
            return {"ok": True, "suggestions": suggestions}
        except Exception as e:
            return {"ok": True, "suggestions": []}

    # ─── Admin: Compute All Metrics ───────────────────────────────────
    @router.post("/admin/metrics/compute")
    async def compute_metrics_all():
        db = await get_db()
        if db is None:
            return {"ok": False, "error": "DB not connected"}
        try:
            from telegram_intel.services.metrics import compute_all_metrics
            result = await compute_all_metrics(db)
            return result
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ─── Admin: Generate AI Summaries for all channels ────────────────
    @router.post("/admin/ai/generate-all")
    async def ai_generate_all():
        db = await get_db()
        if db is None:
            return {"ok": False, "error": "DB not connected"}
        llm_key = module.config.llm_api_key if hasattr(module, 'config') else None
        if not llm_key:
            llm_key = os.environ.get("OPENAI_API_KEY")
        if not llm_key:
            return {"ok": False, "error": "LLM not configured"}
        try:
            channels = await db.tg_channel_states.find(
                {"aiSummary": {"$exists": False}},
                {"_id": 0, "username": 1}
            ).to_list(100)
            generated = 0
            for ch in channels:
                try:
                    # Use the AI summary generation logic
                    cu = ch["username"]
                    state = await db.tg_channel_states.find_one({"username": cu}, {"_id": 0})
                    if not state:
                        continue
                    posts = await db.tg_posts.find(
                        {"username": cu}, {"_id": 0, "text": 1, "views": 1, "forwards": 1, "date": 1}
                    ).sort("date", -1).limit(20).to_list(20)
                    posts_text = [(p.get("text") or "")[:300] for p in posts if p.get("text")]
                    if not posts_text:
                        continue
                    title = state.get("title", cu)
                    members = state.get("participantsCount", 0)
                    prompt = f'Analyze Telegram channel @{cu} ("{title}", {members:,} subscribers).\nRecent {len(posts_text)} posts:\n' + chr(10).join(posts_text[:12]) + '\n\nProvide a JSON response with:\n- "text": 2-3 sentence overview\n- "sector": primary category (e.g. "Crypto News", "Tech", "Trading", "DeFi", "General")\n- "sectorSecondary": array of 2-3 secondary categories\n- "sectorColor": hex color\n- "spamLevel": "Low", "Medium" or "High"\n- "signalNoise": number 1-10\n- "contentExposure": array of 3-4 themes\n\nRespond with ONLY valid JSON.'
                    from openai import OpenAI as OAI
                    ai_client = OAI(api_key=llm_key)
                    r = ai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "system", "content": "You are a crypto/tech analyst. Return structured JSON."}, {"role": "user", "content": prompt}],
                        max_tokens=300
                    )
                    resp_text = r.choices[0].message.content.strip()
                    import json as json_mod
                    clean = resp_text.strip()
                    if clean.startswith("```"):
                        clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
                    ai_data = json_mod.loads(clean)
                    await db.tg_channel_states.update_one(
                        {"username": cu},
                        {"$set": {"aiSummary": ai_data, "aiSummaryUpdatedAt": datetime.now(timezone.utc)}}
                    )
                    generated += 1
                except Exception as ex:
                    logger.warning(f"AI gen for {ch['username']}: {ex}")
            return {"ok": True, "generated": generated}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ─── Channel AI Summary ───────────────────────────────────────────
    @router.get("/channel/{username}/ai-summary")
    async def channel_ai_summary(username: str):
        db = await get_db()
        if db is None:
            return {"ok": False, "error": "DB not connected"}

        llm_key = module.config.llm_api_key if hasattr(module, 'config') else None
        if not llm_key:
            llm_key = os.environ.get("OPENAI_API_KEY")
        if not llm_key:
            return {"ok": False, "error": "LLM not configured"}

        cu = normalize_username(username)
        try:
            state = await db.tg_channel_states.find_one({"username": cu}, {"_id": 0})
            if not state:
                return {"ok": False, "error": "Channel not found"}

            posts = await db.tg_posts.find(
                {"username": cu}, {"_id": 0, "text": 1, "views": 1, "forwards": 1, "date": 1}
            ).sort("date", -1).limit(20).to_list(20)

            posts_text = []
            for p in posts:
                text = (p.get("text") or "")[:300]
                if text:
                    posts_text.append(text)

            title = state.get("title", cu)
            members = state.get("participantsCount", 0)

            prompt = f"""Analyze Telegram channel @{cu} ("{title}", {members:,} subscribers).
Recent {len(posts_text)} posts:
{chr(10).join(posts_text[:12])}

Provide a JSON response with:
- "text": 2-3 sentence overview of the channel's content and quality
- "sector": primary content category (e.g. "Crypto News", "Tech", "Trading", "DeFi", "NFT", "Regulation", "General")
- "sectorSecondary": array of 2-3 secondary categories
- "sectorColor": hex color for the primary sector
- "spamLevel": "Low", "Medium" or "High"
- "signalNoise": number 1-10 (10 = high signal quality)
- "contentExposure": array of 3-4 content themes found in posts

Respond with ONLY valid JSON, no markdown."""

            try:
                from openai import OpenAI as OpenAIClient
                client_ai = OpenAIClient(api_key=llm_key)
                r = client_ai.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a crypto/tech intelligence analyst. Analyze Telegram channels and return structured JSON. Be specific and accurate."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=300
                )
                response_text = r.choices[0].message.content.strip()
            except Exception as llm_err:
                logger.error(f"Channel AI summary LLM error: {llm_err}")
                return {"ok": False, "error": str(llm_err)}

            import json as json_mod
            try:
                clean = response_text.strip()
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
                ai_data = json_mod.loads(clean)
            except Exception:
                ai_data = {
                    "text": response_text,
                    "sector": "General",
                    "sectorSecondary": [],
                    "sectorColor": "#6B7280",
                    "spamLevel": "Low",
                    "signalNoise": 7,
                    "contentExposure": ["General Topics"],
                }

            # Cache in DB
            await db.tg_channel_states.update_one(
                {"username": cu},
                {"$set": {
                    "aiSummary": ai_data,
                    "aiSummaryUpdatedAt": datetime.now(timezone.utc),
                }}
            )

            return {"ok": True, "username": cu, **ai_data}
        except Exception as e:
            logger.error(f"Channel AI summary error: {e}")
            return {"ok": False, "error": str(e)}

    return router
