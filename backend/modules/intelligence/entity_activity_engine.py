"""
Entity Activity Engine
======================

Tracks entity activity level based on real events:
- Funding rounds
- Partnerships
- Product launches
- Token listings
- Token unlocks
- Governance events
- GitHub activity

НЕ просто news count!

Activity Score = Σ (event_weight × recency_decay)

Collections:
    entity_activity_scores - Current activity scores
    entity_activity_history - Historical for trends
"""

import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Activity event weights
ACTIVITY_WEIGHTS = {
    "funding_round": 3.0,        # Most important
    "partnership": 2.0,
    "product_launch": 2.5,
    "token_listing": 2.0,
    "token_unlock": 1.5,
    "governance": 1.0,
    "github_release": 1.5,
    "news_mention": 0.5,        # Base weight
    "social_spike": 0.3
}

# Decay half-life in days
ACTIVITY_DECAY_HALFLIFE = 14


class EntityActivityEngine:
    """
    Engine for calculating entity activity scores.
    
    Tracks real business events, not just news.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        
        # Main collections
        self.activity_scores = db.entity_activity_scores
        self.activity_history = db.entity_activity_history
        
        # Source collections
        self.funding_rounds = db.cryptorank_funding
        self.token_unlocks = db.tokenunlocks_schedule
        self.events = db.news_events
        self.root_events = db.root_events
        self.graph_nodes = db.graph_nodes
        self.projects = db.intel_projects
    
    async def ensure_indexes(self):
        """Create indexes."""
        await self.activity_scores.create_index("entity_key", unique=True)
        await self.activity_scores.create_index("entity_type")
        await self.activity_scores.create_index("total_score")
        
        await self.activity_history.create_index([("entity_key", 1), ("date", -1)])
        
        logger.info("[ActivityEngine] Indexes created")
    
    # ═══════════════════════════════════════════════════════════════
    # CORE CALCULATION
    # ═══════════════════════════════════════════════════════════════
    
    async def calculate_entity_activity(
        self,
        entity_type: str,
        entity_id: str
    ) -> Dict[str, Any]:
        """
        Calculate activity score based on real events.
        """
        entity_key = f"{entity_type}:{entity_id}"
        now = datetime.now(timezone.utc)
        cutoff_30d = now - timedelta(days=30)
        cutoff_7d = now - timedelta(days=7)
        
        activities = []
        total_score = 0
        
        # 1. Funding Rounds
        if entity_type == "project":
            funding = await self._get_project_funding(entity_id, cutoff_30d)
            for event in funding:
                weight = ACTIVITY_WEIGHTS["funding_round"]
                # Boost for larger rounds
                amount = event.get("amount_usd", 0)
                if amount > 10_000_000:
                    weight *= 1.5
                elif amount > 50_000_000:
                    weight *= 2.0
                
                days_old = (now - event.get("date", now)).total_seconds() / 86400
                decay = self._calculate_decay(days_old)
                score = weight * decay
                total_score += score
                
                activities.append({
                    "type": "funding_round",
                    "amount": amount,
                    "date": event.get("date"),
                    "score": round(score, 2)
                })
        
        elif entity_type == "fund":
            # For funds, count investments made
            investments = await self._get_fund_investments(entity_id, cutoff_30d)
            for event in investments:
                weight = ACTIVITY_WEIGHTS["funding_round"] * 0.8  # Slightly less than receiving
                days_old = (now - event.get("date", now)).total_seconds() / 86400
                decay = self._calculate_decay(days_old)
                score = weight * decay
                total_score += score
                
                activities.append({
                    "type": "investment_made",
                    "project": event.get("project"),
                    "date": event.get("date"),
                    "score": round(score, 2)
                })
        
        # 2. Token Unlocks (projects only)
        if entity_type == "project":
            unlocks = await self._get_token_unlocks(entity_id, cutoff_30d)
            for unlock in unlocks:
                weight = ACTIVITY_WEIGHTS["token_unlock"]
                # Boost for larger unlocks
                value = unlock.get("value_usd", 0)
                if value > 10_000_000:
                    weight *= 1.5
                
                days_old = (now - unlock.get("date", now)).total_seconds() / 86400
                decay = self._calculate_decay(days_old)
                score = weight * decay
                total_score += score
                
                activities.append({
                    "type": "token_unlock",
                    "value_usd": value,
                    "date": unlock.get("date"),
                    "score": round(score, 2)
                })
        
        # 3. News/Events Activity
        news_score = await self._calculate_news_activity(entity_type, entity_id, cutoff_30d, cutoff_7d)
        total_score += news_score.get("score", 0)
        
        activities.append({
            "type": "news_mentions",
            "count_30d": news_score.get("count_30d", 0),
            "count_7d": news_score.get("count_7d", 0),
            "score": round(news_score.get("score", 0), 2)
        })
        
        # 4. Check for major events (launches, partnerships)
        major_events = await self._check_major_events(entity_type, entity_id, cutoff_30d)
        for event in major_events:
            weight = ACTIVITY_WEIGHTS.get(event.get("type"), 1.0)
            days_old = (now - event.get("date", now)).total_seconds() / 86400
            decay = self._calculate_decay(days_old)
            score = weight * decay
            total_score += score
            
            activities.append({
                "type": event.get("type"),
                "title": event.get("title"),
                "date": event.get("date"),
                "score": round(score, 2)
            })
        
        # Normalize to 0-100
        # Calibration: score of 10 raw = 100 normalized
        normalized_score = min(100, (total_score / 10) * 100)
        
        # Calculate velocity (7d vs 30d)
        recent_score = sum(
            a["score"] for a in activities
            if a.get("date") and a.get("date") >= cutoff_7d
        )
        old_score = total_score - recent_score
        velocity = recent_score - (old_score / 3.3)  # Expected 7d from 30d
        
        result = {
            "entity_key": entity_key,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "total_score": round(normalized_score, 2),
            "raw_score": round(total_score, 3),
            "velocity": round(velocity, 2),
            "activity_count": len([a for a in activities if a.get("score", 0) > 0]),
            "activities": sorted(activities, key=lambda x: x.get("score", 0), reverse=True)[:10],
            "updated_at": now.isoformat()
        }
        
        # Store
        await self.activity_scores.update_one(
            {"entity_key": entity_key},
            {"$set": result},
            upsert=True
        )
        
        # Store history
        await self._store_history(entity_key, normalized_score, velocity)
        
        logger.debug(f"[ActivityEngine] {entity_key}: score={normalized_score:.1f}")
        
        return result
    
    async def _get_project_funding(
        self,
        project_id: str,
        since: datetime
    ) -> List[Dict]:
        """Get funding rounds for a project."""
        funding = []
        
        # Check cryptorank_funding
        cursor = self.funding_rounds.find({
            "$or": [
                {"project_slug": project_id},
                {"project_name": {"$regex": project_id, "$options": "i"}}
            ]
        }).limit(20)
        
        async for round in cursor:
            date_str = round.get("date")
            if date_str:
                try:
                    date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    if date.tzinfo is None:
                        date = date.replace(tzinfo=timezone.utc)
                    if date >= since:
                        funding.append({
                            "amount_usd": round.get("amount_usd", 0),
                            "date": date,
                            "round_type": round.get("round_type")
                        })
                except:
                    pass
        
        return funding
    
    async def _get_fund_investments(
        self,
        fund_id: str,
        since: datetime
    ) -> List[Dict]:
        """Get investments made by a fund."""
        investments = []
        
        cursor = self.funding_rounds.find({
            "$or": [
                {"lead_investors": {"$regex": fund_id, "$options": "i"}},
                {"investors": {"$regex": fund_id, "$options": "i"}}
            ]
        }).limit(30)
        
        async for round in cursor:
            date_str = round.get("date")
            if date_str:
                try:
                    date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    if date.tzinfo is None:
                        date = date.replace(tzinfo=timezone.utc)
                    if date >= since:
                        investments.append({
                            "project": round.get("project_name"),
                            "date": date,
                            "amount": round.get("amount_usd", 0)
                        })
                except:
                    pass
        
        return investments
    
    async def _get_token_unlocks(
        self,
        project_id: str,
        since: datetime
    ) -> List[Dict]:
        """Get token unlock events."""
        unlocks = []
        
        cursor = self.token_unlocks.find({
            "$or": [
                {"project_slug": project_id},
                {"symbol": {"$regex": project_id, "$options": "i"}}
            ]
        }).limit(20)
        
        async for unlock in cursor:
            date_str = unlock.get("unlock_date")
            if date_str:
                try:
                    date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    if date.tzinfo is None:
                        date = date.replace(tzinfo=timezone.utc)
                    if date >= since:
                        unlocks.append({
                            "value_usd": unlock.get("value_usd", 0),
                            "date": date
                        })
                except:
                    pass
        
        return unlocks
    
    async def _calculate_news_activity(
        self,
        entity_type: str,
        entity_id: str,
        cutoff_30d: datetime,
        cutoff_7d: datetime
    ) -> Dict:
        """Calculate news-based activity score."""
        # Count news mentions
        count_30d = await self.events.count_documents({
            "primary_assets": {"$regex": entity_id, "$options": "i"},
            "created_at": {"$gte": cutoff_30d}
        })
        
        count_7d = await self.events.count_documents({
            "primary_assets": {"$regex": entity_id, "$options": "i"},
            "created_at": {"$gte": cutoff_7d}
        })
        
        # Also check root_events
        count_30d += await self.root_events.count_documents({
            "entities": {"$regex": entity_id, "$options": "i"},
            "first_seen": {"$gte": cutoff_30d}
        })
        
        count_7d += await self.root_events.count_documents({
            "entities": {"$regex": entity_id, "$options": "i"},
            "first_seen": {"$gte": cutoff_7d}
        })
        
        # Score: log scale for news mentions
        if count_30d > 0:
            score = ACTIVITY_WEIGHTS["news_mention"] * math.log(1 + count_30d) * 2
        else:
            score = 0
        
        return {
            "count_30d": count_30d,
            "count_7d": count_7d,
            "score": score
        }
    
    async def _check_major_events(
        self,
        entity_type: str,
        entity_id: str,
        since: datetime
    ) -> List[Dict]:
        """Check for major events (launches, partnerships)."""
        major_events = []
        now = datetime.now(timezone.utc)
        
        # Look for specific event types in root_events
        keywords = {
            "product_launch": ["launch", "mainnet", "live", "release", "v2", "upgrade"],
            "partnership": ["partnership", "partner", "integrate", "collaboration"],
            "token_listing": ["listing", "listed", "trading", "exchange"]
        }
        
        cursor = self.root_events.find({
            "entities": {"$regex": entity_id, "$options": "i"},
            "first_seen": {"$gte": since}
        }).limit(50)
        
        async for event in cursor:
            title = event.get("title", "").lower()
            
            for event_type, kws in keywords.items():
                if any(kw in title for kw in kws):
                    date = event.get("first_seen", now)
                    if isinstance(date, str):
                        try:
                            date = datetime.fromisoformat(date.replace("Z", "+00:00"))
                        except:
                            date = now
                    
                    if date.tzinfo is None:
                        date = date.replace(tzinfo=timezone.utc)
                    
                    major_events.append({
                        "type": event_type,
                        "title": event.get("title"),
                        "date": date
                    })
                    break
        
        return major_events
    
    def _calculate_decay(self, days_old: float) -> float:
        """Calculate recency decay."""
        return math.pow(0.5, days_old / ACTIVITY_DECAY_HALFLIFE)
    
    async def _store_history(
        self,
        entity_key: str,
        score: float,
        velocity: float
    ):
        """Store in history."""
        now = datetime.now(timezone.utc)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        await self.activity_history.update_one(
            {"entity_key": entity_key, "date": today},
            {"$set": {
                "entity_key": entity_key,
                "date": today,
                "score": score,
                "velocity": velocity
            }},
            upsert=True
        )
    
    # ═══════════════════════════════════════════════════════════════
    # BATCH UPDATE
    # ═══════════════════════════════════════════════════════════════
    
    async def update_all_entities(
        self,
        entity_types: List[str] = None,
        limit: int = 300
    ) -> Dict[str, Any]:
        """Batch update activity scores."""
        start = datetime.now(timezone.utc)
        
        if entity_types is None:
            entity_types = ["project", "fund", "exchange"]
        
        results = {
            "processed": 0,
            "active": 0,
            "errors": 0,
            "by_type": {}
        }
        
        for entity_type in entity_types:
            type_count = 0
            
            cursor = self.graph_nodes.find({
                "entity_type": entity_type
            }).limit(limit // len(entity_types))
            
            async for node in cursor:
                try:
                    result = await self.calculate_entity_activity(
                        entity_type,
                        node.get("entity_id")
                    )
                    
                    results["processed"] += 1
                    type_count += 1
                    
                    if result.get("total_score", 0) > 10:
                        results["active"] += 1
                        
                except Exception as e:
                    logger.error(f"[ActivityEngine] Error for {node.get('entity_id')}: {e}")
                    results["errors"] += 1
            
            results["by_type"][entity_type] = type_count
        
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        results["elapsed_seconds"] = round(elapsed, 2)
        
        logger.info(
            f"[ActivityEngine] Updated {results['processed']} entities "
            f"({results['active']} active) in {elapsed:.1f}s"
        )
        
        return results
    
    # ═══════════════════════════════════════════════════════════════
    # QUERY METHODS
    # ═══════════════════════════════════════════════════════════════
    
    async def get_entity_activity(
        self,
        entity_type: str,
        entity_id: str
    ) -> Optional[Dict]:
        """Get activity score for an entity."""
        entity_key = f"{entity_type}:{entity_id}"
        
        score = await self.activity_scores.find_one(
            {"entity_key": entity_key},
            {"_id": 0}
        )
        
        if not score:
            score = await self.calculate_entity_activity(entity_type, entity_id)
        
        return score
    
    async def get_most_active(
        self,
        entity_type: str = None,
        limit: int = 20
    ) -> List[Dict]:
        """Get most active entities."""
        query = {}
        if entity_type:
            query["entity_type"] = entity_type
        
        cursor = self.activity_scores.find(
            query,
            {"_id": 0}
        ).sort("total_score", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_accelerating(
        self,
        entity_type: str = None,
        limit: int = 20
    ) -> List[Dict]:
        """Get entities with highest velocity (accelerating activity)."""
        query = {"velocity": {"$gt": 0}}
        if entity_type:
            query["entity_type"] = entity_type
        
        cursor = self.activity_scores.find(
            query,
            {"_id": 0}
        ).sort("velocity", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get activity statistics."""
        total = await self.activity_scores.count_documents({})
        active = await self.activity_scores.count_documents({"total_score": {"$gt": 10}})
        accelerating = await self.activity_scores.count_documents({"velocity": {"$gt": 0}})
        
        # By type
        pipeline = [
            {"$group": {
                "_id": "$entity_type",
                "count": {"$sum": 1},
                "avg_score": {"$avg": "$total_score"},
                "max_score": {"$max": "$total_score"}
            }}
        ]
        
        type_stats = await self.activity_scores.aggregate(pipeline).to_list(10)
        
        return {
            "total_tracked": total,
            "active": active,
            "accelerating": accelerating,
            "by_type": {
                stat["_id"]: {
                    "count": stat["count"],
                    "avg_score": round(stat["avg_score"], 1),
                    "max_score": round(stat["max_score"], 1)
                }
                for stat in type_stats if stat["_id"]
            }
        }


# ═══════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════

_activity_engine: Optional[EntityActivityEngine] = None


def get_activity_engine(db: AsyncIOMotorDatabase = None) -> EntityActivityEngine:
    """Get or create activity engine."""
    global _activity_engine
    if db is not None:
        _activity_engine = EntityActivityEngine(db)
    return _activity_engine
