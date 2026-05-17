"""
FOMO Crypto Activities Layer
============================
Unified activity feed for crypto ecosystem events:
- Airdrops, Points Programs, Campaigns
- Testnets, Mainnets, Launches
- Listings, Delistings, Launchpools
- Partnerships, Integrations, Upgrades

Sources: Dropstab, DropsEarn, CryptoRank

Collections:
- crypto_activities

Endpoints:
- GET /api/activities - List all activities
- GET /api/activities/active - Active activities
- GET /api/activities/upcoming - Upcoming activities
- GET /api/activities/trending - Trending by score
- GET /api/projects/{id}/activities - Project activities
- GET /api/campaigns - Active campaigns (airdrops, points, quests)
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/api/activities", tags=["Activities"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


# Activity Categories
ACTIVITY_CATEGORIES = [
    "launch",      # mainnet, testnet, token launch, IDO/IEO
    "campaign",    # points program, incentive, liquidity mining, staking
    "exchange",    # listing, delisting, launchpool, launchpad
    "ecosystem",   # partnership, integration, upgrade, fork
    "community",   # airdrop, NFT mint, governance vote
    "development"  # testnet, devnet, SDK release, protocol upgrade
]

# Activity Types (detailed)
ACTIVITY_TYPES = [
    "mainnet", "testnet", "airdrop", "launchpool", "launchpad",
    "ido", "ieo", "staking", "points_program", "liquidity_mining",
    "integration", "partnership", "listing", "delisting", "upgrade",
    "nft_mint", "governance", "fork", "sdk_release", "devnet",
    "token_launch", "incentive_campaign", "quest"
]

# Activity Status
ACTIVITY_STATUS = ["upcoming", "active", "ended"]


def calculate_activity_score(activity: dict) -> int:
    """
    Calculate activity score (0-100).
    
    Components:
    - 40% reward_weight (estimated value)
    - 25% project_rank (tier)
    - 20% difficulty_inverse (easier = higher score)
    - 15% social_mentions (engagement)
    """
    score = 50  # Base score
    
    # Reward weight
    reward = activity.get("reward", "")
    if reward:
        if any(x in reward.lower() for x in ["airdrop", "token", "$"]):
            score += 20
        elif any(x in reward.lower() for x in ["points", "nft"]):
            score += 10
    
    # Type weight
    activity_type = activity.get("type", "")
    type_weights = {
        "airdrop": 25, "launchpool": 20, "ido": 20, "ieo": 18,
        "points_program": 15, "testnet": 12, "mainnet": 15,
        "listing": 10, "staking": 8, "quest": 8
    }
    score += type_weights.get(activity_type, 5)
    
    # Difficulty inverse (easier = higher)
    difficulty = activity.get("difficulty", "medium")
    diff_weights = {"easy": 10, "medium": 5, "hard": 0}
    score += diff_weights.get(difficulty, 5)
    
    # Cap at 100
    return min(score, 100)


# ═══════════════════════════════════════════════════════════════
# ACTIVITIES LIST
# ═══════════════════════════════════════════════════════════════

@router.get("")
async def list_activities(
    category: Optional[str] = Query(None, description="Filter by category"),
    type: Optional[str] = Query(None, description="Filter by activity type"),
    status: Optional[str] = Query(None, description="Filter: upcoming, active, ended"),
    project: Optional[str] = Query(None, description="Filter by project"),
    difficulty: Optional[str] = Query(None, description="Filter: easy, medium, hard"),
    chain: Optional[str] = Query(None, description="Filter by blockchain"),
    search: Optional[str] = Query(None, description="Search in title/description"),
    sort_by: str = Query("score", description="Sort: score, date, reward"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    List all crypto activities with filters.
    
    Categories: launch, campaign, exchange, ecosystem, community, development
    Types: airdrop, launchpool, testnet, points_program, listing, etc.
    Status: upcoming, active, ended
    """
    from server import db
    
    skip = (page - 1) * limit
    now = datetime.now(timezone.utc)
    
    query = {}
    
    if category:
        query["category"] = category
    if type:
        query["type"] = type
    if project:
        query["project_id"] = {"$regex": project, "$options": "i"}
    if difficulty:
        query["difficulty"] = difficulty
    if chain:
        query["chain"] = {"$regex": chain, "$options": "i"}
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]
    
    # Status filter
    if status == "upcoming":
        query["start_date"] = {"$gt": now.isoformat()}
    elif status == "active":
        query["$and"] = [
            {"$or": [{"start_date": {"$lte": now.isoformat()}}, {"start_date": {"$exists": False}}]},
            {"$or": [{"end_date": {"$gte": now.isoformat()}}, {"end_date": {"$exists": False}}]}
        ]
    elif status == "ended":
        query["end_date"] = {"$lt": now.isoformat()}
    
    # Sort
    sort_field = {"score": "score", "date": "start_date", "reward": "reward_value"}.get(sort_by, "score")
    sort_dir = -1  # Descending
    
    cursor = db.crypto_activities.find(query).sort(sort_field, sort_dir).skip(skip).limit(limit)
    activities = await cursor.to_list(limit)
    
    total = await db.crypto_activities.count_documents(query)
    
    items = []
    for act in activities:
        items.append({
            "id": act.get("id", str(act.get("_id", ""))),
            "project_id": act.get("project_id"),
            "project_name": act.get("project_name"),
            "project_logo": act.get("project_logo"),
            "title": act.get("title"),
            "description": act.get("description", "")[:200],
            "category": act.get("category"),
            "type": act.get("type"),
            "status": act.get("status", "active"),
            "chain": act.get("chain"),
            "reward": act.get("reward"),
            "difficulty": act.get("difficulty"),
            "start_date": act.get("start_date"),
            "end_date": act.get("end_date"),
            "source": act.get("source"),
            "source_url": act.get("source_url"),
            "score": act.get("score", 50),
            "tags": act.get("tags", [])
        })
    
    return {
        "ts": ts_now(),
        "page": page,
        "limit": limit,
        "total": total,
        "filters": {
            "categories": ACTIVITY_CATEGORIES,
            "types": ACTIVITY_TYPES,
            "status_options": ACTIVITY_STATUS
        },
        "items": items,
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# ACTIVE ACTIVITIES
# ═══════════════════════════════════════════════════════════════

@router.get("/active")
async def get_active_activities(
    category: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get currently active activities (started, not ended).
    """
    from server import db
    
    now = datetime.now(timezone.utc)
    
    query = {
        "$or": [
            {"status": "active"},
            {
                "$and": [
                    {"$or": [{"start_date": {"$lte": now.isoformat()}}, {"start_date": {"$exists": False}}]},
                    {"$or": [{"end_date": {"$gte": now.isoformat()}}, {"end_date": {"$exists": False}}, {"end_date": None}]}
                ]
            }
        ]
    }
    
    if category:
        query["category"] = category
    if type:
        query["type"] = type
    
    cursor = db.crypto_activities.find(query).sort("score", -1).limit(limit)
    activities = await cursor.to_list(limit)
    
    items = []
    for act in activities:
        items.append({
            "id": act.get("id", str(act.get("_id", ""))),
            "project_id": act.get("project_id"),
            "project_name": act.get("project_name"),
            "title": act.get("title"),
            "type": act.get("type"),
            "category": act.get("category"),
            "status": act.get("status", "active"),
            "reward": act.get("reward"),
            "difficulty": act.get("difficulty"),
            "end_date": act.get("end_date"),
            "score": act.get("score", 50),
            "source_url": act.get("source_url")
        })
    
    return {
        "ts": ts_now(),
        "status": "active",
        "count": len(items),
        "items": items,
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# UPCOMING ACTIVITIES
# ═══════════════════════════════════════════════════════════════

@router.get("/upcoming")
async def get_upcoming_activities(
    days: int = Query(30, ge=1, le=90, description="Days ahead"),
    category: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get upcoming activities (not yet started).
    """
    from server import db
    
    now = datetime.now(timezone.utc)
    future = now + timedelta(days=days)
    
    query = {
        "start_date": {
            "$gte": now.isoformat(),
            "$lte": future.isoformat()
        }
    }
    
    if category:
        query["category"] = category
    if type:
        query["type"] = type
    
    cursor = db.crypto_activities.find(query).sort("start_date", 1).limit(limit)
    activities = await cursor.to_list(limit)
    
    items = []
    for act in activities:
        items.append({
            "id": act.get("id", str(act.get("_id", ""))),
            "project_id": act.get("project_id"),
            "project_name": act.get("project_name"),
            "title": act.get("title"),
            "type": act.get("type"),
            "category": act.get("category"),
            "reward": act.get("reward"),
            "start_date": act.get("start_date"),
            "end_date": act.get("end_date"),
            "score": act.get("score", 50)
        })
    
    return {
        "ts": ts_now(),
        "status": "upcoming",
        "days_ahead": days,
        "count": len(items),
        "items": items,
        "_meta": {"cache_sec": 600}
    }


# ═══════════════════════════════════════════════════════════════
# TRENDING ACTIVITIES
# ═══════════════════════════════════════════════════════════════

@router.get("/trending")
async def get_trending_activities(
    period: str = Query("week", description="Period: day, week, month"),
    limit: int = Query(20, ge=1, le=50)
):
    """
    Get trending activities by score and engagement.
    """
    from server import db
    
    now = datetime.now(timezone.utc)
    
    # Period filter
    if period == "day":
        since = now - timedelta(days=1)
    elif period == "week":
        since = now - timedelta(days=7)
    else:
        since = now - timedelta(days=30)
    
    query = {
        "$or": [
            {"status": "active"},
            {"created_at": {"$gte": since.isoformat()}}
        ]
    }
    
    cursor = db.crypto_activities.find(query).sort("score", -1).limit(limit)
    activities = await cursor.to_list(limit)
    
    items = []
    for i, act in enumerate(activities):
        items.append({
            "rank": i + 1,
            "id": act.get("id", str(act.get("_id", ""))),
            "project_id": act.get("project_id"),
            "project_name": act.get("project_name"),
            "title": act.get("title"),
            "type": act.get("type"),
            "category": act.get("category"),
            "reward": act.get("reward"),
            "score": act.get("score", 50),
            "status": act.get("status", "active")
        })
    
    return {
        "ts": ts_now(),
        "period": period,
        "count": len(items),
        "items": items,
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# CAMPAIGNS (Airdrops, Points, Quests)
# ═══════════════════════════════════════════════════════════════

@router.get("/campaigns")
async def get_campaigns(
    type: Optional[str] = Query(None, description="Filter: airdrop, points_program, quest, testnet"),
    status: str = Query("active", description="Status: active, upcoming, all"),
    chain: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get active campaigns - airdrops, points programs, quests, testnets.
    """
    from server import db
    
    now = datetime.now(timezone.utc)
    
    # Campaign types
    campaign_types = ["airdrop", "points_program", "quest", "testnet", "incentive_campaign", "staking"]
    
    query = {
        "type": {"$in": campaign_types}
    }
    
    if type:
        query["type"] = type
    
    if status == "active":
        query["$or"] = [
            {"status": "active"},
            {
                "$and": [
                    {"$or": [{"start_date": {"$lte": now.isoformat()}}, {"start_date": {"$exists": False}}]},
                    {"$or": [{"end_date": {"$gte": now.isoformat()}}, {"end_date": {"$exists": False}}, {"end_date": None}]}
                ]
            }
        ]
    elif status == "upcoming":
        query["start_date"] = {"$gt": now.isoformat()}
    
    if chain:
        query["chain"] = {"$regex": chain, "$options": "i"}
    if difficulty:
        query["difficulty"] = difficulty
    
    cursor = db.crypto_activities.find(query).sort("score", -1).limit(limit)
    campaigns = await cursor.to_list(limit)
    
    items = []
    for camp in campaigns:
        items.append({
            "id": camp.get("id", str(camp.get("_id", ""))),
            "project_id": camp.get("project_id"),
            "project_name": camp.get("project_name"),
            "project_logo": camp.get("project_logo"),
            "title": camp.get("title"),
            "description": camp.get("description", "")[:300],
            "type": camp.get("type"),
            "status": camp.get("status", "active"),
            "chain": camp.get("chain"),
            "reward": camp.get("reward"),
            "estimated_reward": camp.get("estimated_reward"),
            "difficulty": camp.get("difficulty"),
            "steps_count": camp.get("steps_count"),
            "participants": camp.get("participants"),
            "start_date": camp.get("start_date"),
            "end_date": camp.get("end_date"),
            "source": camp.get("source"),
            "source_url": camp.get("source_url"),
            "guide_url": camp.get("guide_url"),
            "score": camp.get("score", 50),
            "tags": camp.get("tags", [])
        })
    
    return {
        "ts": ts_now(),
        "status_filter": status,
        "count": len(items),
        "campaign_types": campaign_types,
        "items": items,
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# PROJECT ACTIVITIES
# ═══════════════════════════════════════════════════════════════

@router.get("/project/{project_id}")
async def get_project_activities(
    project_id: str,
    status: Optional[str] = Query(None, description="Filter: active, upcoming, ended"),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get all activities for a specific project.
    """
    from server import db
    
    query = {
        "$or": [
            {"project_id": project_id},
            {"project_id": {"$regex": project_id, "$options": "i"}}
        ]
    }
    
    now = datetime.now(timezone.utc)
    if status == "active":
        query["$and"] = query.get("$and", []) + [
            {"$or": [{"start_date": {"$lte": now.isoformat()}}, {"start_date": {"$exists": False}}]},
            {"$or": [{"end_date": {"$gte": now.isoformat()}}, {"end_date": {"$exists": False}}]}
        ]
    elif status == "upcoming":
        query["start_date"] = {"$gt": now.isoformat()}
    elif status == "ended":
        query["end_date"] = {"$lt": now.isoformat()}
    
    cursor = db.crypto_activities.find(query).sort("start_date", -1).limit(limit)
    activities = await cursor.to_list(limit)
    
    items = []
    for act in activities:
        items.append({
            "id": act.get("id"),
            "title": act.get("title"),
            "type": act.get("type"),
            "category": act.get("category"),
            "status": act.get("status", "active"),
            "reward": act.get("reward"),
            "start_date": act.get("start_date"),
            "end_date": act.get("end_date"),
            "source_url": act.get("source_url"),
            "score": act.get("score", 50)
        })
    
    return {
        "ts": ts_now(),
        "project_id": project_id,
        "count": len(items),
        "activities": items,
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# ACTIVITY DETAIL
# ═══════════════════════════════════════════════════════════════

@router.get("/{activity_id}")
async def get_activity_detail(activity_id: str):
    """
    Get detailed activity information.
    """
    from server import db
    
    activity = await db.crypto_activities.find_one({
        "$or": [
            {"id": activity_id},
            {"_id": activity_id}
        ]
    })
    
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    activity.pop("_id", None)
    
    return {
        "ts": ts_now(),
        "activity": activity,
        "_meta": {"cache_sec": 300}
    }
