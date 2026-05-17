"""
Telegram Intel - Channel Service
Version: 1.0.0
"""

import logging
import re
from typing import Any, Dict, Optional

import re

logger = logging.getLogger(__name__)

# Ad detection patterns
AD_PATTERNS = re.compile(
    r'#реклама|#ad\b|#advertisement|#sponsored|#промо|#promo|'
    r'\breклама\b|\badvertisement\b|\bsponsored\b|\bпартнерский\b|\bпромо\b|\bpromo\b',
    re.IGNORECASE
)

def is_ad_post(text: str) -> bool:
    """Detect if a post is an advertisement"""
    if not text:
        return False
    return bool(AD_PATTERNS.search(text))


def _score_to_tier(score):
    if score >= 80: return "S"
    if score >= 65: return "A"
    if score >= 50: return "B"
    if score >= 35: return "C"
    return "D"


def _score_to_label(score):
    if score >= 80: return "Excellent"
    if score >= 65: return "Good"
    if score >= 50: return "Average"
    if score >= 35: return "Below Avg"
    return "Poor"


async def get_channel_full(db, username: str) -> Dict[str, Any]:
    """Get full channel data"""
    try:
        clean = username.lower().replace("@", "").strip()
        
        channel = await db.tg_channel_states.find_one(
            {"username": clean},
            {"_id": 0}
        )
        
        if not channel:
            return {"ok": False, "error": "Channel not found"}
        
        posts = await db.tg_posts.find(
            {"username": clean},
            {"_id": 0}
        ).sort("date", -1).limit(100).to_list(100)
        
        # Batch-load media assets for posts with media
        media_posts = [(p.get("username"), p.get("messageId")) for p in posts if p.get("hasMedia")]
        media_map = {}
        if media_posts:
            media_filter = {"$or": [{"username": u, "messageId": m, "status": "READY"} for u, m in media_posts]}
            media_assets = await db.tg_media_assets.find(media_filter, {"_id": 0}).to_list(200)
            for ma in media_assets:
                media_map[f"{ma.get('username')}:{ma.get('messageId')}"] = ma
        
        # Format posts with reactions and media
        formatted_posts = []
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
            
            # Get media info from tg_media_assets
            post_key = f"{p.get('username')}:{p.get('messageId')}"
            media_asset = media_map.get(post_key)
            media_info = None
            if media_asset:
                raw_url = media_asset.get("url", "")
            # Normalize media URL to use the API endpoint
                if raw_url.startswith("/tg/media/"):
                    raw_url = "/api/telegram-intel/media/" + raw_url[len("/tg/media/"):]
                media_info = {
                    "url": raw_url,
                    "kind": media_asset.get("kind"),
                    "w": media_asset.get("w"),
                    "h": media_asset.get("h"),
                }
            
            formatted_posts.append({
                "messageId": p.get("messageId"),
                "date": str(p.get("date", "")),
                "text": p.get("text", ""),
                "views": p.get("views", 0),
                "forwards": p.get("forwards", 0),
                "replies": p.get("replies", 0),
                "reactions": reactions,
                "hasMedia": p.get("hasMedia", False),
                "media": media_info,
                "isAd": p.get("isAd") or is_ad_post(p.get("text", "")),
            })
        
        members = channel.get("participantsCount", 0) or 0
        engagement = channel.get("engagement", 0.1)
        stability_val = channel.get("stability", 0.7)
        fraud = channel.get("fraud", 0.2)
        ppd = channel.get("postsPerDay", 1)
        g7 = channel.get("growth7", 0) or 0
        g30 = channel.get("growth30", 0) or 0

        result = {
            "ok": True,
            "channel": {
                "username": channel.get("username"),
                "title": channel.get("title"),
                "members": members,
                "avatarUrl": channel.get("avatarUrl"),
                "avatarColor": channel.get("avatarColor"),
                "type": "Group" if channel.get("isChannel") is False else "Channel",
                "about": channel.get("about", ""),
                "sector": channel.get("sector"),
                "sectorColor": channel.get("sectorColor"),
                "tags": channel.get("tags", []),
            },
            "metrics": {
                "utilityScore": channel.get("utilityScore", 50),
                "tier": channel.get("tier") or (_score_to_tier(channel.get("utilityScore", 50))),
                "tierLabel": channel.get("tierLabel") or (_score_to_label(channel.get("utilityScore", 50))),
                "members": members,
                "engagementRate": engagement,
                "stability": stability_val,
                "fraudRisk": fraud,
            },
            "posts": formatted_posts,
            "network": {"outgoing": [], "incoming": []},
            "activity": {
                "engagementRate": engagement,
                "stability": stability_val,
                "postsPerDay": ppd,
                "avgReach24h": int(members * engagement) if members else 0,
            },
            "growth": {
                "growth7": g7,
                "growth30": g30,
            },
            "healthSafety": {
                "fraudRisk": fraud,
                "stability": stability_val,
                "trustScore": round((1 - fraud) * 100),
            },
            "snapshot": {
                "utility": channel.get("utilityScore", 50),
                "engagement": engagement,
                "stability": stability_val,
                "fraud": fraud,
                "growth7": g7,
                "growth30": g30,
            },
            "aiSummary": channel.get("aiSummary"),
            "productAnalysis": channel.get("productAnalysis"),
        }

        # Add members timeline
        try:
            from telegram_lite.members_history import get_members_history
            members_timeline = await get_members_history(db, clean, days=90)
            result["membersTimeline"] = [
                {"date": m.get("date"), "members": m.get("members", 0)}
                for m in members_timeline
            ]
        except Exception:
            result["membersTimeline"] = []

        # Add related channels
        try:
            sector = channel.get("sector")
            # Try sector-based matching first with regex for broader match
            related = []
            if sector:
                # Use regex to match similar sectors
                sector_words = [w for w in sector.split() if len(w) > 3]
                if sector_words:
                    pattern = "|".join(sector_words)
                    related = await db.tg_channel_states.find(
                        {"username": {"$ne": channel.get("username")}, "sector": {"$regex": pattern, "$options": "i"}},
                        {"_id": 0, "username": 1, "title": 1, "participantsCount": 1, "avatarUrl": 1, "sector": 1, "sectorColor": 1, "fomoScore": 1, "activityLabel": 1}
                    ).sort("fomoScore", -1).limit(5).to_list(5)
            
            # Fallback: return all other channels sorted by score
            if not related:
                related = await db.tg_channel_states.find(
                    {"username": {"$ne": channel.get("username")}},
                    {"_id": 0, "username": 1, "title": 1, "participantsCount": 1, "avatarUrl": 1, "sector": 1, "sectorColor": 1, "fomoScore": 1, "activityLabel": 1}
                ).sort("fomoScore", -1).limit(5).to_list(5)
            
            result["relatedChannels"] = related
        except Exception:
            result["relatedChannels"] = []

        return result
    except Exception as e:
        logger.error(f"Channel error: {e}")
        return {"ok": False, "error": str(e)}


async def get_channel_list(db, limit: int = 50, offset: int = 0, sort_by: str = "fomoScore", q: Optional[str] = None, language: Optional[str] = None) -> Dict[str, Any]:
    """Get list of monitored channels with full metrics"""
    try:
        filt = {}
        if q and q.strip():
            q_clean = q.strip()
            filt = {"$or": [
                {"username": {"$regex": re.escape(q_clean), "$options": "i"}},
                {"title": {"$regex": re.escape(q_clean), "$options": "i"}},
                {"sector": {"$regex": re.escape(q_clean), "$options": "i"}},
            ]}
        if language and language.strip():
            lang_clean = language.strip().upper()
            if lang_clean in ("EN", "RU", "UA"):
                if filt:
                    filt = {"$and": [filt, {"language": lang_clean}]}
                else:
                    filt["language"] = lang_clean

        channels = await db.tg_channel_states.find(
            filt,
            {"_id": 0}
        ).sort(sort_by, -1).skip(offset).limit(limit).to_list(limit)
        
        total = await db.tg_channel_states.count_documents(filt)

        items = []
        for ch in channels:
            members = ch.get("participantsCount", 0) or ch.get("members", 0) or 0
            ai = ch.get("aiSummary") or {}
            fomo = ch.get("fomoScore") or ch.get("utilityScore", 0) or 0
            items.append({
                "username": ch.get("username"),
                "title": ch.get("title"),
                "avatarUrl": ch.get("avatarUrl"),
                "avatarColor": ch.get("avatarColor"),
                "type": ch.get("type") or ("Channel" if ch.get("isChannel", True) else "Group"),
                "sector": ch.get("sector") or ai.get("sector"),
                "sectorColor": ch.get("sectorColor") or ai.get("sectorColor"),
                "members": members,
                "avgReach": ch.get("avgReach", int(members * 0.1)),
                "growth7": ch.get("growth7", 0) or 0,
                "growth30": ch.get("growth30", 0) or 0,
                "activity": ch.get("activityLabel") or "Medium",
                "activityLabel": ch.get("activityLabel") or "Medium",
                "redFlags": ch.get("redFlags", 0) or 0,
                "fomoScore": fomo,
                "utilityScore": fomo,
                "stars": min(5, max(0, round(fomo / 20))),
                "engagement": ch.get("engagement", 0),
                "postsPerDay": ch.get("postsPerDay", 0),
                "fraud": ch.get("fraud", 0),
                "stability": ch.get("stability", 0),
                "language": ch.get("language", "EN"),
                "sparkline": ch.get("sparkline", []),
            })
        
        # Compute aggregate stats
        all_channels = await db.tg_channel_states.find(
            {}, {"_id": 0, "fomoScore": 1, "growth7": 1, "redFlags": 1}
        ).to_list(500)
        total_all = len(all_channels)
        scores = [c.get("fomoScore", 0) or 0 for c in all_channels]
        avg_score = round(sum(scores) / max(total_all, 1), 1)
        high_growth = sum(1 for c in all_channels if (c.get("growth7", 0) or 0) > 2)
        high_risk = sum(1 for c in all_channels if (c.get("redFlags", 0) or 0) >= 2)

        return {
            "ok": True,
            "items": items,
            "total": total,
            "stats": {
                "tracked": total_all,
                "avgUtility": avg_score,
                "avgScore": avg_score,
                "highGrowth": high_growth,
                "highRisk": high_risk,
            }
        }
    except Exception as e:
        logger.error(f"Channel list error: {e}")
        return {"ok": False, "error": str(e), "items": [], "total": 0, "stats": {"tracked": 0, "avgUtility": 0, "highGrowth": 0, "highRisk": 0}}
