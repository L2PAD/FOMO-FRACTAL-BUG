"""
Event Entity Registry
=====================

Links events to entities for:
- entity_event_timeline - все события для entity
- entity_momentum - активность entity во времени
- entity_narrative_exposure - в каких нарративах участвует entity

Architecture:
    events (root_events, news_events) 
        ↓
    event_entities (many-to-many link)
        ↓
    entities (projects, funds, persons, etc.)

Collections:
    event_entities:
        event_id: "evt_123"
        event_type: "news" | "root" | "topic" | "narrative"
        entity_type: "project" | "fund" | "person" | "exchange"
        entity_id: "arbitrum"
        entity_key: "project:arbitrum"
        role: "mentioned" | "primary" | "secondary" | "related"
        confidence: 0.95
        created_at: datetime
        
Usage:
    # Get all events for an entity
    events = await registry.get_entity_events("project", "arbitrum")
    
    # Get entity momentum (event count over time)
    momentum = await registry.get_entity_momentum("project", "arbitrum", days=30)
    
    # Link event to entities
    await registry.link_event_entities(event_id, entities)
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from enum import Enum
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class EntityRole(str, Enum):
    PRIMARY = "primary"      # Main entity of the event
    SECONDARY = "secondary"  # Important but not main
    MENTIONED = "mentioned"  # Just mentioned
    RELATED = "related"      # Derived/inferred relationship


class EventType(str, Enum):
    NEWS = "news"
    ROOT = "root"
    TOPIC = "topic"
    NARRATIVE = "narrative"
    FUNDING = "funding"
    UNLOCK = "unlock"
    LISTING = "listing"


class EventEntityLink(BaseModel):
    """Link between event and entity"""
    event_id: str
    event_type: EventType
    entity_type: str
    entity_id: str
    entity_key: str = Field(default="")  # {entity_type}:{entity_id}
    role: EntityRole = EntityRole.MENTIONED
    confidence: float = Field(0.5, ge=0, le=1)
    context: Optional[str] = None  # Why this entity is linked
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def __init__(self, **data):
        super().__init__(**data)
        if not self.entity_key:
            self.entity_key = f"{self.entity_type}:{self.entity_id}"


class EventEntityRegistry:
    """
    Registry for event-entity relationships.
    Enables entity-centric queries on event data.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.event_entities = db.event_entities
        self.root_events = db.root_events
        self.news_events = db.news_events
    
    async def ensure_indexes(self):
        """Create indexes for efficient queries"""
        # Primary indexes
        await self.event_entities.create_index([("event_id", 1), ("entity_key", 1)], unique=True)
        await self.event_entities.create_index("entity_key")
        await self.event_entities.create_index("event_id")
        
        # Query indexes
        await self.event_entities.create_index([("entity_type", 1), ("entity_id", 1)])
        await self.event_entities.create_index([("entity_key", 1), ("created_at", -1)])
        await self.event_entities.create_index([("entity_key", 1), ("event_type", 1)])
        await self.event_entities.create_index([("entity_key", 1), ("role", 1)])
        
        # Time-based
        await self.event_entities.create_index("created_at")
        
        logger.info("[EventEntityRegistry] Indexes created")
    
    async def link_event_entities(
        self,
        event_id: str,
        event_type: EventType,
        entities: List[Dict[str, Any]]
    ) -> int:
        """
        Link event to multiple entities.
        
        Args:
            event_id: ID of the event
            event_type: Type of event (news, root, etc.)
            entities: List of {entity_type, entity_id, role?, confidence?}
            
        Returns:
            Number of links created
        """
        if not entities:
            return 0
        
        created = 0
        now = datetime.now(timezone.utc)
        
        for entity in entities:
            entity_type = entity.get("entity_type") or entity.get("type")
            entity_id = entity.get("entity_id") or entity.get("id")
            
            if not entity_type or not entity_id:
                continue
            
            entity_key = f"{entity_type}:{entity_id}"
            role = entity.get("role", EntityRole.MENTIONED)
            confidence = entity.get("confidence", 0.5)
            
            link = {
                "event_id": event_id,
                "event_type": event_type.value if isinstance(event_type, EventType) else event_type,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "entity_key": entity_key,
                "role": role.value if isinstance(role, EntityRole) else role,
                "confidence": confidence,
                "context": entity.get("context"),
                "created_at": now
            }
            
            try:
                await self.event_entities.update_one(
                    {"event_id": event_id, "entity_key": entity_key},
                    {"$set": link},
                    upsert=True
                )
                created += 1
            except Exception as e:
                logger.error(f"[EventEntityRegistry] Failed to link {event_id} -> {entity_key}: {e}")
        
        return created
    
    async def get_entity_events(
        self,
        entity_type: str,
        entity_id: str,
        event_types: List[str] = None,
        roles: List[str] = None,
        limit: int = 100,
        days: int = None
    ) -> List[Dict[str, Any]]:
        """
        Get all events for an entity.
        
        Returns list of event links with event details.
        """
        entity_key = f"{entity_type}:{entity_id}"
        
        query = {"entity_key": entity_key}
        
        if event_types:
            query["event_type"] = {"$in": event_types}
        
        if roles:
            query["role"] = {"$in": roles}
        
        if days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            query["created_at"] = {"$gte": cutoff}
        
        cursor = self.event_entities.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
        
        return await cursor.to_list(limit)
    
    async def get_entity_momentum(
        self,
        entity_type: str,
        entity_id: str,
        days: int = 30,
        bucket_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get entity momentum - event count over time.
        
        Returns time series of event counts.
        """
        entity_key = f"{entity_type}:{entity_id}"
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Aggregate by time bucket
        pipeline = [
            {
                "$match": {
                    "entity_key": entity_key,
                    "created_at": {"$gte": cutoff}
                }
            },
            {
                "$group": {
                    "_id": {
                        "$dateTrunc": {
                            "date": "$created_at",
                            "unit": "hour",
                            "binSize": bucket_hours
                        }
                    },
                    "count": {"$sum": 1},
                    "primary_count": {
                        "$sum": {"$cond": [{"$eq": ["$role", "primary"]}, 1, 0]}
                    },
                    "avg_confidence": {"$avg": "$confidence"}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        result = await self.event_entities.aggregate(pipeline).to_list(1000)
        
        # Calculate momentum score
        total_events = sum(r["count"] for r in result)
        recent_events = sum(r["count"] for r in result[-7:]) if len(result) >= 7 else total_events
        
        momentum_score = 0
        if total_events > 0:
            # Higher weight for recent events
            momentum_score = min(100, (recent_events / max(total_events, 1)) * 100 + recent_events * 2)
        
        return {
            "entity_key": entity_key,
            "period_days": days,
            "total_events": total_events,
            "recent_events_7d": recent_events,
            "momentum_score": round(momentum_score, 1),
            "timeline": [
                {
                    "date": r["_id"].isoformat() if r["_id"] else None,
                    "count": r["count"],
                    "primary_count": r["primary_count"],
                    "avg_confidence": round(r["avg_confidence"], 2)
                }
                for r in result
            ]
        }
    
    async def get_entity_narrative_exposure(
        self,
        entity_type: str,
        entity_id: str
    ) -> Dict[str, Any]:
        """
        Get narratives/topics this entity is exposed to.
        """
        entity_key = f"{entity_type}:{entity_id}"
        
        # Group by event_type to find narratives/topics
        pipeline = [
            {"$match": {"entity_key": entity_key}},
            {
                "$group": {
                    "_id": "$event_type",
                    "count": {"$sum": 1},
                    "events": {"$push": "$event_id"}
                }
            }
        ]
        
        result = await self.event_entities.aggregate(pipeline).to_list(100)
        
        exposure = {
            "entity_key": entity_key,
            "event_types": {}
        }
        
        for r in result:
            exposure["event_types"][r["_id"]] = {
                "count": r["count"],
                "sample_events": r["events"][:5]
            }
        
        return exposure
    
    async def get_event_entities(
        self,
        event_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all entities linked to an event.
        """
        cursor = self.event_entities.find(
            {"event_id": event_id},
            {"_id": 0}
        ).sort("confidence", -1)
        
        return await cursor.to_list(100)
    
    async def get_co_occurring_entities(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Find entities that often appear in the same events.
        """
        entity_key = f"{entity_type}:{entity_id}"
        
        # Get events for this entity
        events = await self.event_entities.find(
            {"entity_key": entity_key},
            {"event_id": 1}
        ).to_list(500)
        
        event_ids = [e["event_id"] for e in events]
        
        if not event_ids:
            return []
        
        # Find other entities in these events
        pipeline = [
            {
                "$match": {
                    "event_id": {"$in": event_ids},
                    "entity_key": {"$ne": entity_key}
                }
            },
            {
                "$group": {
                    "_id": "$entity_key",
                    "count": {"$sum": 1},
                    "avg_confidence": {"$avg": "$confidence"},
                    "entity_type": {"$first": "$entity_type"},
                    "entity_id": {"$first": "$entity_id"}
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": limit}
        ]
        
        result = await self.event_entities.aggregate(pipeline).to_list(limit)
        
        return [
            {
                "entity_key": r["_id"],
                "entity_type": r["entity_type"],
                "entity_id": r["entity_id"],
                "co_occurrence_count": r["count"],
                "avg_confidence": round(r["avg_confidence"], 2)
            }
            for r in result
        ]
    
    async def backfill_from_news_events(self, limit: int = 1000) -> Dict[str, Any]:
        """
        Backfill event_entities from existing news_events.
        One-time migration task.
        """
        cursor = self.news_events.find({}).limit(limit)
        
        processed = 0
        linked = 0
        
        async for event in cursor:
            event_id = event.get("id")
            if not event_id:
                continue
            
            entities = []
            
            # Extract from primary_entities
            for entity in event.get("primary_entities", []):
                if isinstance(entity, str):
                    entities.append({
                        "entity_type": "unknown",
                        "entity_id": entity.lower(),
                        "role": EntityRole.PRIMARY,
                        "confidence": 0.9
                    })
                elif isinstance(entity, dict):
                    entities.append({
                        "entity_type": entity.get("type", "unknown"),
                        "entity_id": entity.get("id", "").lower(),
                        "role": EntityRole.PRIMARY,
                        "confidence": entity.get("confidence", 0.9)
                    })
            
            # Extract from primary_assets
            for asset in event.get("primary_assets", []):
                if isinstance(asset, str):
                    entities.append({
                        "entity_type": "project",
                        "entity_id": asset.lower(),
                        "role": EntityRole.PRIMARY,
                        "confidence": 0.85
                    })
            
            if entities:
                count = await self.link_event_entities(event_id, EventType.NEWS, entities)
                linked += count
            
            processed += 1
        
        logger.info(f"[EventEntityRegistry] Backfill: processed {processed} events, created {linked} links")
        
        return {
            "processed": processed,
            "links_created": linked
        }
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        total_links = await self.event_entities.count_documents({})
        
        # By event type
        type_pipeline = [
            {"$group": {"_id": "$event_type", "count": {"$sum": 1}}}
        ]
        type_result = await self.event_entities.aggregate(type_pipeline).to_list(20)
        
        # By entity type
        entity_pipeline = [
            {"$group": {"_id": "$entity_type", "count": {"$sum": 1}}}
        ]
        entity_result = await self.event_entities.aggregate(entity_pipeline).to_list(20)
        
        # By role
        role_pipeline = [
            {"$group": {"_id": "$role", "count": {"$sum": 1}}}
        ]
        role_result = await self.event_entities.aggregate(role_pipeline).to_list(10)
        
        # Unique entities
        unique_entities = len(await self.event_entities.distinct("entity_key"))
        unique_events = len(await self.event_entities.distinct("event_id"))
        
        return {
            "total_links": total_links,
            "unique_entities": unique_entities,
            "unique_events": unique_events,
            "by_event_type": {r["_id"]: r["count"] for r in type_result},
            "by_entity_type": {r["_id"]: r["count"] for r in entity_result},
            "by_role": {r["_id"]: r["count"] for r in role_result}
        }


# Singleton
_registry: Optional[EventEntityRegistry] = None


def get_event_entity_registry(db: AsyncIOMotorDatabase = None) -> EventEntityRegistry:
    """Get or create registry instance"""
    global _registry
    if db is not None:
        _registry = EventEntityRegistry(db)
    return _registry
