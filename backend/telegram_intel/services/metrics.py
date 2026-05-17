"""
Telegram Intel - Metrics Computation Engine
Calculates all derived metrics for channels: engagement, growth, activity, 
avgReach, fomoScore, redFlags, sector, etc.
"""
import logging
import re
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from collections import Counter

logger = logging.getLogger(__name__)


# ─── Activity Label ──────────────────────────────────────────────────
def compute_activity_label(posts_per_day: float) -> str:
    if posts_per_day >= 10: return "Very High"
    if posts_per_day >= 5: return "High"
    if posts_per_day >= 1: return "Medium"
    if posts_per_day >= 0.3: return "Low"
    return "Dormant"


# ─── Red Flags Count ─────────────────────────────────────────────────
def compute_red_flags(fraud: float, engagement: float, stability: float) -> int:
    flags = 0
    if fraud > 0.6: flags += 2
    elif fraud > 0.35: flags += 1
    if engagement > 0.5: flags += 1  # suspiciously high
    if stability < 0.3: flags += 1
    return flags


# ─── FOMO Score (0-100) ──────────────────────────────────────────────
def compute_fomo_score(
    members: int,
    engagement: float,
    growth7: float,
    stability: float,
    fraud: float,
    posts_per_day: float,
) -> int:
    """Composite quality score based on multiple signals"""
    score = 0.0
    # Members weight (0-25)
    if members >= 1_000_000: score += 25
    elif members >= 100_000: score += 20
    elif members >= 10_000: score += 15
    elif members >= 1_000: score += 8
    else: score += 3

    # Engagement weight (0-20) 
    eng_pct = min(engagement * 100, 20)
    score += eng_pct

    # Growth weight (0-20)
    if growth7 > 5: score += 20
    elif growth7 > 2: score += 15
    elif growth7 > 0.5: score += 10
    elif growth7 > 0: score += 5
    else: score += 2

    # Stability weight (0-15)
    score += stability * 15

    # Activity consistency (0-10)
    if 1 <= posts_per_day <= 20: score += 10
    elif posts_per_day > 0.3: score += 5
    else: score += 1

    # Fraud penalty (0 to -10)
    score -= fraud * 10

    return max(0, min(100, round(score)))


# ─── Channel Type Label ──────────────────────────────────────────────
def compute_type_label(is_channel: bool, members: int) -> str:
    if is_channel:
        if members >= 100_000: return "Mega Channel"
        return "Channel"
    else:
        if members >= 100_000: return "Supergroup"
        return "Group"


# ─── Compute All Metrics for a Single Channel ────────────────────────
async def compute_channel_metrics(db, username: str) -> Dict[str, Any]:
    """Compute all derived metrics for a channel and update DB"""
    channel = await db.tg_channel_states.find_one({"username": username}, {"_id": 0})
    if not channel:
        return {"ok": False, "error": "not found"}

    members = channel.get("participantsCount", 0) or 0
    is_channel = channel.get("isChannel", True)

    # Get posts for metrics
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    posts_7d = await db.tg_posts.find(
        {"username": username, "date": {"$gte": week_ago}},
        {"_id": 0, "views": 1, "forwards": 1, "reactions": 1, "date": 1, "text": 1}
    ).to_list(500)

    posts_30d = await db.tg_posts.find(
        {"username": username, "date": {"$gte": month_ago}},
        {"_id": 0, "views": 1, "forwards": 1, "date": 1}
    ).to_list(1000)

    all_posts = await db.tg_posts.find(
        {"username": username},
        {"_id": 0, "views": 1, "forwards": 1, "date": 1}
    ).to_list(1000)

    # Posts per day (7d window)
    days_7 = max((now - week_ago).days, 1)
    posts_per_day_7d = len(posts_7d) / days_7

    # Posts per day (30d window)
    days_30 = max((now - month_ago).days, 1)
    posts_per_day_30d = len(posts_30d) / days_30

    ppd = posts_per_day_7d if posts_7d else posts_per_day_30d

    # Engagement rate
    total_views = sum(p.get("views", 0) for p in all_posts)
    avg_views = total_views / max(len(all_posts), 1)
    engagement = avg_views / max(members, 1) if members > 1 else 0.1
    engagement = min(engagement, 1.0)

    # Avg reach
    avg_reach = int(avg_views) if avg_views > 0 else int(members * 0.1) if members > 1 else 0

    # Growth (from members_history or estimate)
    growth7 = 0.0
    growth30 = 0.0
    sparkline = []
    try:
        history = await db.tg_channel_members_history.find(
            {"username": username}, {"_id": 0, "members": 1, "date": 1, "ts": 1}
        ).sort("ts", -1).limit(30).to_list(30)
        
        if len(history) >= 2:
            latest = history[0].get("members", 0)
            
            # Sparkline data (last 14 points, oldest first)
            sparkline = [h.get("members", 0) for h in reversed(history[:14])]
            
            # 7-day growth
            week_entry = None
            for h in history:
                ts = h.get("ts") or h.get("date")
                if isinstance(ts, datetime):
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if (now - ts).days >= 6:
                        week_entry = h
                        break
                elif isinstance(ts, str):
                    try:
                        d = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
                        if (now - d).days >= 6:
                            week_entry = h
                            break
                    except Exception:
                        pass
            if week_entry and week_entry.get("members", 0) > 0:
                growth7 = ((latest - week_entry["members"]) / week_entry["members"]) * 100
            
            # 30-day growth
            oldest = history[-1]
            if oldest.get("members", 0) > 0:
                growth30 = ((latest - oldest["members"]) / oldest["members"]) * 100
    except Exception as e:
        logger.warning(f"Growth calc error for {username}: {e}")

    # Stability (consistency of posting)
    if len(posts_30d) >= 2:
        dates = sorted([p.get("date") for p in posts_30d if isinstance(p.get("date"), datetime)])
        if len(dates) >= 2:
            gaps = [(dates[i+1] - dates[i]).total_seconds() / 3600 for i in range(len(dates)-1)]
            avg_gap = sum(gaps) / len(gaps) if gaps else 24
            stability = min(1.0, 24 / max(avg_gap, 1))
        else:
            stability = 0.5
    else:
        stability = 0.3

    # Fraud estimate (simple heuristic)
    fraud = 0.2  # default low
    if members > 0 and engagement < 0.01 and members > 50000:
        fraud = 0.5  # suspiciously low engagement
    if members > 0 and engagement > 0.4:
        fraud = 0.4  # suspiciously high engagement

    # Red flags
    red_flags = compute_red_flags(fraud, engagement, stability)

    # Activity label
    activity_label = compute_activity_label(ppd)

    # Type
    type_label = compute_type_label(is_channel, members)

    # Sector from AI summary
    ai = channel.get("aiSummary", {}) or {}
    sector = ai.get("sector")
    sector_color = ai.get("sectorColor")
    sector_secondary = ai.get("sectorSecondary", [])

    # FOMO Score
    fomo_score = compute_fomo_score(members, engagement, growth7, stability, fraud, ppd)

    metrics = {
        "type": type_label,
        "sector": sector,
        "sectorColor": sector_color,
        "sectorSecondary": sector_secondary,
        "members": members,
        "engagement": round(engagement, 4),
        "avgReach": avg_reach,
        "growth7": round(growth7, 2),
        "growth30": round(growth30, 2),
        "stability": round(stability, 3),
        "fraud": round(fraud, 3),
        "postsPerDay": round(ppd, 1),
        "activityLabel": activity_label,
        "redFlags": red_flags,
        "fomoScore": fomo_score,
        "utilityScore": fomo_score,
        "sparkline": sparkline,
        "tier": "S" if fomo_score >= 80 else "A" if fomo_score >= 65 else "B" if fomo_score >= 50 else "C" if fomo_score >= 35 else "D",
        "tierLabel": "Excellent" if fomo_score >= 80 else "Good" if fomo_score >= 65 else "Average" if fomo_score >= 50 else "Below Avg" if fomo_score >= 35 else "Poor",
        "metricsUpdatedAt": now,
    }

    # Update DB
    await db.tg_channel_states.update_one(
        {"username": username},
        {"$set": metrics}
    )

    return {"ok": True, "username": username, **metrics}


# ─── Compute Metrics for ALL channels ────────────────────────────────
async def compute_all_metrics(db) -> Dict[str, Any]:
    """Compute metrics for all channels in DB"""
    channels = await db.tg_channel_states.find({}, {"_id": 0, "username": 1}).to_list(500)
    results = []
    for ch in channels:
        r = await compute_channel_metrics(db, ch["username"])
        results.append(r)
    return {"ok": True, "computed": len(results), "results": results}


# ─── Compute Aggregate Stats (for stats cards) ───────────────────────
async def compute_aggregate_stats(db) -> Dict[str, Any]:
    """Compute aggregate stats across all channels"""
    channels = await db.tg_channel_states.find(
        {}, {"_id": 0, "username": 1, "fomoScore": 1, "growth7": 1, "fraud": 1, "redFlags": 1}
    ).to_list(500)

    total = len(channels)
    if total == 0:
        return {"tracked": 0, "avgScore": 0, "highGrowth": 0, "highRisk": 0}

    scores = [ch.get("fomoScore", 0) or 0 for ch in channels]
    avg_score = round(sum(scores) / total, 1) if total else 0

    high_growth = sum(1 for ch in channels if (ch.get("growth7", 0) or 0) > 2)
    high_risk = sum(1 for ch in channels if (ch.get("redFlags", 0) or 0) >= 2)

    return {
        "tracked": total,
        "avgScore": avg_score,
        "highGrowth": high_growth,
        "highRisk": high_risk,
    }


# ─── Topic Extraction from Posts ──────────────────────────────────────
STOP_WORDS = {
    "the", "a", "an", "is", "was", "are", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "can", "could", "may", "might", "must", "that", "this",
    "these", "those", "i", "you", "he", "she", "it", "we", "they", "me",
    "him", "her", "us", "them", "my", "your", "his", "its", "our", "their",
    "what", "which", "who", "whom", "where", "when", "why", "how",
    "all", "each", "every", "both", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same", "so",
    "than", "too", "very", "just", "but", "and", "or", "if", "while",
    "with", "about", "against", "between", "through", "during", "before",
    "after", "above", "below", "to", "from", "up", "down", "in", "out",
    "on", "off", "over", "under", "for", "at", "by", "of", "as",
    "into", "like", "also", "new", "one", "two", "first", "last",
    "https", "http", "com", "org", "net", "t.me", "www", "html",
    "по", "на", "в", "и", "с", "не", "что", "как", "это", "за",
    "из", "от", "до", "но", "для", "уже", "при", "все", "его",
    "бы", "же", "то", "да", "нет", "или", "так", "ещё", "еще",
    "они", "мы", "вы", "он", "она", "оно", "их", "её",
}


async def extract_topics(db, hours: int = 24, min_mentions: int = 2, usernames: list = None) -> List[Dict]:
    """Extract trending topics from recent posts (filtered by feed channels)"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    post_filter = {"date": {"$gte": cutoff}}
    if usernames:
        post_filter["username"] = {"$in": usernames}
    posts = await db.tg_posts.find(
        post_filter,
        {"_id": 0, "text": 1, "username": 1, "views": 1}
    ).to_list(500)

    if not posts:
        return []

    # Extract bigrams and key terms
    term_counter = Counter()
    term_channels = {}
    term_views = {}

    for p in posts:
        text = (p.get("text") or "").lower()
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'[^\w\s#$@]', ' ', text)
        words = [w for w in text.split() if len(w) > 2 and w not in STOP_WORDS]
        
        # Extract hashtags as topics
        hashtags = re.findall(r'#(\w+)', text)
        
        # Get key terms (single words + bigrams)
        terms = set()
        for h in hashtags:
            if len(h) > 2:
                terms.add(f"#{h}")
        
        # Bigrams
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            if len(bigram) > 6:
                terms.add(bigram)
        
        # Key single words (crypto-related)
        for w in words:
            if len(w) > 3 and (w.startswith('$') or w.startswith('#') or w[0].isupper() or w in {
                'bitcoin', 'btc', 'ethereum', 'eth', 'solana', 'sol', 'defi', 'nft',
                'token', 'crypto', 'blockchain', 'binance', 'coinbase', 'usdt', 'usdc',
            }):
                terms.add(w)

        uname = p.get("username", "")
        views = p.get("views", 0) or 0
        
        for t in terms:
            term_counter[t] += 1
            if t not in term_channels:
                term_channels[t] = set()
            term_channels[t].add(uname)
            term_views[t] = term_views.get(t, 0) + views

    # Filter and rank
    topics = []
    for term, count in term_counter.most_common(50):
        if count < min_mentions:
            continue
        channels = term_channels.get(term, set())
        total_views = term_views.get(term, 0)
        
        momentum = count * len(channels) * (1 + total_views / 10000)
        # Spiking: mentioned by 3+ channels OR high momentum relative to mentions
        is_spiking = len(channels) >= 3 or (count >= 5 and total_views > 50000)
        
        topics.append({
            "topic": term,
            "mentions": count,
            "channels": len(channels),
            "channelList": list(channels)[:5],
            "totalViews": total_views,
            "momentum": round(momentum, 1),
            "isSpiking": is_spiking,
        })

    topics.sort(key=lambda x: x["momentum"], reverse=True)

    # Store in DB
    now = datetime.now(timezone.utc)
    await db.topic_mentions.delete_many({})
    if topics:
        for t in topics[:30]:
            t["extractedAt"] = now
        await db.topic_mentions.insert_many([{**t} for t in topics[:30]])

    return topics[:20]


# ─── Cross-Channel Signal Detection ──────────────────────────────────
async def detect_cross_channel_signals(db, window_minutes: int = 120, usernames: list = None) -> List[Dict]:
    """Detect when multiple channels discuss the same entity/topic (filtered by feed channels)"""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    post_filter = {"date": {"$gte": cutoff}}
    if usernames:
        post_filter["username"] = {"$in": usernames}
    posts = await db.tg_posts.find(
        post_filter,
        {"_id": 0, "text": 1, "username": 1, "views": 1, "messageId": 1, "date": 1}
    ).to_list(500)

    if len(posts) < 2:
        return []

    # Extract named entities (tokens, projects, people)
    entity_map = {}
    
    # Crypto token patterns
    token_pattern = re.compile(r'\$([A-Z]{2,10})\b')
    mention_pattern = re.compile(r'@(\w{3,32})')
    
    for p in posts:
        text = p.get("text") or ""
        uname = p.get("username", "")
        
        entities = set()
        # Tokens
        for match in token_pattern.finditer(text):
            entities.add(match.group(0))
        
        # Key proper nouns (capitalized words that appear significant)
        words = text.split()
        for w in words:
            clean = re.sub(r'[^\w]', '', w)
            if len(clean) > 3 and clean[0].isupper() and clean.lower() not in STOP_WORDS:
                entities.add(clean)
        
        for ent in entities:
            if ent not in entity_map:
                entity_map[ent] = {"channels": set(), "posts": [], "views": 0}
            entity_map[ent]["channels"].add(uname)
            entity_map[ent]["posts"].append({
                "username": uname,
                "messageId": p.get("messageId"),
                "date": str(p.get("date", "")),
            })
            entity_map[ent]["views"] += p.get("views", 0) or 0

    # Filter: entity mentioned by 2+ channels
    signals = []
    now = datetime.now(timezone.utc)
    for entity, data in entity_map.items():
        if len(data["channels"]) >= 2:
            signals.append({
                "entity": entity,
                "mentions": len(data["posts"]),
                "channels": list(data["channels"]),
                "channelCount": len(data["channels"]),
                "totalViews": data["views"],
                "posts": data["posts"][:5],
                "strength": len(data["channels"]) * len(data["posts"]),
                "expiresAt": now + timedelta(hours=2),
            })

    signals.sort(key=lambda x: x["strength"], reverse=True)

    # Store
    await db.cross_channel_signals.delete_many({})
    if signals:
        await db.cross_channel_signals.insert_many([{**s} for s in signals[:20]])

    return signals[:10]


# ─── Alert Generation ─────────────────────────────────────────────────
async def generate_alerts(db, hours: int = 48, usernames: list = None) -> List[Dict]:
    """Generate alerts based on unusual activity (filtered by feed channels)"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    now = datetime.now(timezone.utc)
    alerts = []

    # Base filter for posts
    base_filter = {"date": {"$gte": cutoff}}
    if usernames:
        base_filter["username"] = {"$in": usernames}

    # 1. High-view posts
    high_view_posts = await db.tg_posts.find(
        {**base_filter, "views": {"$gte": 5000}},
        {"_id": 0, "username": 1, "views": 1, "text": 1, "messageId": 1}
    ).sort("views", -1).limit(5).to_list(5)
    
    for p in high_view_posts:
        alerts.append({
            "type": "high_engagement",
            "severity": "info",
            "title": f"High engagement on @{p['username']}",
            "message": f"Post received {p['views']:,} views",
            "username": p["username"],
            "messageId": p.get("messageId"),
            "createdAt": now,
        })

    # 2. Channels with many forwards (cross-posting signal)
    high_forward_posts = await db.tg_posts.find(
        {**base_filter, "forwards": {"$gte": 20}},
        {"_id": 0, "username": 1, "forwards": 1, "text": 1}
    ).sort("forwards", -1).limit(3).to_list(3)

    for p in high_forward_posts:
        alerts.append({
            "type": "viral_content",
            "severity": "warning",
            "title": f"Viral content from @{p['username']}",
            "message": f"Post forwarded {p['forwards']} times",
            "username": p["username"],
            "createdAt": now,
        })

    # 3. New channels added recently
    ch_filter = {"createdAt": {"$gte": cutoff}}
    if usernames:
        ch_filter["username"] = {"$in": usernames}
    new_channels = await db.tg_channel_states.find(
        ch_filter,
        {"_id": 0, "username": 1, "title": 1, "participantsCount": 1}
    ).to_list(10)

    for ch in new_channels:
        alerts.append({
            "type": "new_channel",
            "severity": "info",
            "title": f"New channel: {ch.get('title', ch['username'])}",
            "message": f"{ch.get('participantsCount', 0):,} members",
            "username": ch["username"],
            "createdAt": now,
        })

    # Store
    await db.tg_alerts.delete_many({"createdAt": {"$lt": cutoff}})
    if alerts:
        await db.tg_alerts.insert_many([{**a} for a in alerts])

    return alerts


# ─── Related Channels ─────────────────────────────────────────────────
async def get_related_channels(db, username: str, limit: int = 5) -> List[Dict]:
    """Find related channels based on sector similarity and co-mention"""
    channel = await db.tg_channel_states.find_one({"username": username}, {"_id": 0})
    if not channel:
        return []

    sector = channel.get("sector")
    
    # Find channels in same sector
    filt = {"username": {"$ne": username}}
    if sector:
        filt["sector"] = sector
    
    related = await db.tg_channel_states.find(
        filt,
        {"_id": 0, "username": 1, "title": 1, "participantsCount": 1, 
         "avatarUrl": 1, "sector": 1, "sectorColor": 1, "fomoScore": 1}
    ).sort("fomoScore", -1).limit(limit).to_list(limit)

    if not related:
        # Fallback: just return other channels
        related = await db.tg_channel_states.find(
            {"username": {"$ne": username}},
            {"_id": 0, "username": 1, "title": 1, "participantsCount": 1,
             "avatarUrl": 1, "sector": 1, "sectorColor": 1, "fomoScore": 1}
        ).sort("fomoScore", -1).limit(limit).to_list(limit)

    return related
