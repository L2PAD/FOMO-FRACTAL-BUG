"""
Root Event Model - Core Intelligence Layer

Architecture:
articles → event_updates → root_events

A root_event is the story itself (e.g., "BlackRock Bitcoin ETF")
An event_update is a new manifestation of that story
An article is a source document

This prevents event duplication drift where:
- Same story gets 40+ duplicate events over time
- Analytics become unreliable
- Feed becomes noisy
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
import hashlib
import re


class LifecycleStage(str, Enum):
    EMERGING = "emerging"
    ACTIVE = "active"
    DECLINING = "declining"
    RESOLVED = "resolved"


class EventUpdateType(str, Enum):
    INITIAL = "initial"
    DEVELOPMENT = "development"
    CONFIRMATION = "confirmation"
    REACTION = "reaction"
    RESOLUTION = "resolution"


class RootEvent(BaseModel):
    """
    Root Event - The canonical story/narrative unit
    
    Example:
    - title: "BlackRock Bitcoin ETF"
    - entities: ["blackrock", "bitcoin", "sec"]
    - topics: ["etf", "regulation", "institutional"]
    """
    id: str = Field(..., description="Unique identifier (re_xxx)")
    title: str = Field(..., description="Canonical title")
    canonical_name: str = Field(..., description="URL-safe slug")
    summary: Optional[str] = Field(None, description="AI-generated summary")
    
    # Classification
    entities: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    event_type: Optional[str] = Field(None, description="funding, unlock, listing, etc.")
    
    # Scores
    importance_score: float = Field(0.0, ge=0, le=100)
    max_importance: float = Field(0.0, description="Peak importance ever reached")
    
    # Lifecycle
    lifecycle_stage: LifecycleStage = Field(LifecycleStage.EMERGING)
    
    # Metadata
    first_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    update_count: int = Field(0)
    source_count: int = Field(0)
    
    # Linking
    narrative_ids: List[str] = Field(default_factory=list, description="Parent narratives")
    related_root_events: List[str] = Field(default_factory=list)
    
    class Config:
        use_enum_values = True


class EventUpdate(BaseModel):
    """
    Event Update - A new manifestation of a root event
    
    Example:
    - root_event: "BlackRock Bitcoin ETF"
    - title: "BlackRock ETF approved by SEC"
    - update_type: "confirmation"
    """
    id: str = Field(..., description="Unique identifier (eu_xxx)")
    root_event_id: str = Field(..., description="Parent root event")
    
    # Content
    title: str
    summary: Optional[str] = None
    key_points: List[str] = Field(default_factory=list)
    
    # Classification
    update_type: EventUpdateType = Field(EventUpdateType.DEVELOPMENT)
    entities_mentioned: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    
    # Scores
    sentiment: Optional[str] = Field(None, description="positive/negative/neutral")
    sentiment_score: float = Field(0.0, ge=-1, le=1)
    importance_delta: float = Field(0.0, description="Change in importance")
    confidence_score: float = Field(0.0, ge=0, le=1)
    rumor_score: float = Field(0.0, ge=0, le=1)
    
    # Sources
    source_count: int = Field(0)
    article_ids: List[str] = Field(default_factory=list)
    primary_source: Optional[str] = None
    
    # Timeline
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_date: Optional[datetime] = Field(None, description="When event actually happened")
    
    class Config:
        use_enum_values = True


class RootEventService:
    """
    Service for managing root events and updates
    """
    
    def __init__(self, db):
        self.db = db
        self.root_events = db.root_events
        self.event_updates = db.event_updates
    
    async def find_or_create_root_event(
        self,
        title: str,
        entities: List[str],
        topics: List[str],
        similarity_threshold: float = 0.7
    ) -> RootEvent:
        """
        Find existing root event or create new one
        Uses entity/topic overlap for matching
        """
        # Try to find existing root event
        existing = await self._find_similar_root_event(
            title, entities, topics, similarity_threshold
        )
        
        if existing:
            return RootEvent(**existing)
        
        # Create new root event
        root_event = RootEvent(
            id=self._generate_id("re"),
            title=title,
            canonical_name=self._slugify(title),
            entities=entities,
            topics=topics
        )
        
        await self.root_events.insert_one(root_event.dict())
        return root_event
    
    async def add_update(
        self,
        root_event_id: str,
        title: str,
        summary: str = None,
        sentiment_score: float = 0.0,
        confidence_score: float = 0.0,
        rumor_score: float = 0.0,
        article_ids: List[str] = None,
        update_type: EventUpdateType = EventUpdateType.DEVELOPMENT
    ) -> EventUpdate:
        """
        Add new update to root event
        """
        update = EventUpdate(
            id=self._generate_id("eu"),
            root_event_id=root_event_id,
            title=title,
            summary=summary,
            sentiment_score=sentiment_score,
            confidence_score=confidence_score,
            rumor_score=rumor_score,
            article_ids=article_ids or [],
            source_count=len(article_ids) if article_ids else 0,
            update_type=update_type
        )
        
        await self.event_updates.insert_one(update.dict())
        
        # Update root event
        await self._update_root_event_stats(root_event_id, update)
        
        return update
    
    async def get_timeline(self, root_event_id: str) -> List[EventUpdate]:
        """
        Get all updates for a root event, sorted by time
        """
        cursor = self.event_updates.find(
            {"root_event_id": root_event_id}
        ).sort("created_at", 1)
        
        updates = await cursor.to_list(length=1000)
        return [EventUpdate(**u) for u in updates]
    
    async def get_root_events_by_narrative(
        self, 
        narrative_id: str,
        limit: int = 50
    ) -> List[RootEvent]:
        """
        Get root events belonging to a narrative
        """
        cursor = self.root_events.find(
            {"narrative_ids": narrative_id}
        ).sort("last_updated", -1).limit(limit)
        
        events = await cursor.to_list(length=limit)
        return [RootEvent(**e) for e in events]
    
    async def merge_root_events(
        self,
        source_id: str,
        target_id: str
    ) -> RootEvent:
        """
        Merge two root events (when duplicates are found)
        All updates from source are moved to target
        """
        # Move all updates
        await self.event_updates.update_many(
            {"root_event_id": source_id},
            {"$set": {"root_event_id": target_id}}
        )
        
        # Get source for entity/topic merge
        source = await self.root_events.find_one({"id": source_id})
        
        if source:
            # Merge entities and topics
            await self.root_events.update_one(
                {"id": target_id},
                {
                    "$addToSet": {
                        "entities": {"$each": source.get("entities", [])},
                        "topics": {"$each": source.get("topics", [])}
                    }
                }
            )
            
            # Delete source
            await self.root_events.delete_one({"id": source_id})
        
        # Return updated target
        target = await self.root_events.find_one({"id": target_id})
        return RootEvent(**target)
    
    async def _find_similar_root_event(
        self,
        title: str,
        entities: List[str],
        topics: List[str],
        threshold: float
    ) -> Optional[Dict]:
        """
        Find root event with similar entities/topics
        """
        if not entities:
            return None
        
        # Find by entity overlap
        cursor = self.root_events.find({
            "entities": {"$in": entities},
            "lifecycle_stage": {"$ne": "resolved"}
        }).limit(100)
        
        candidates = await cursor.to_list(length=100)
        
        best_match = None
        best_score = 0
        
        for candidate in candidates:
            score = self._calculate_similarity(
                entities, topics,
                candidate.get("entities", []),
                candidate.get("topics", [])
            )
            if score > threshold and score > best_score:
                best_score = score
                best_match = candidate
        
        return best_match
    
    async def _update_root_event_stats(
        self,
        root_event_id: str,
        update: EventUpdate
    ):
        """
        Update root event statistics after new update
        """
        # Calculate new importance
        importance_change = update.importance_delta if update.importance_delta else 5
        
        await self.root_events.update_one(
            {"id": root_event_id},
            {
                "$inc": {
                    "update_count": 1,
                    "source_count": update.source_count,
                    "importance_score": importance_change
                },
                "$set": {
                    "last_updated": datetime.now(timezone.utc),
                    "lifecycle_stage": "active"
                },
                "$max": {
                    "max_importance": update.importance_delta or 0
                }
            }
        )
    
    @staticmethod
    def _calculate_similarity(
        entities1: List[str],
        topics1: List[str],
        entities2: List[str],
        topics2: List[str]
    ) -> float:
        """
        Calculate similarity score based on entity/topic overlap
        """
        if not entities1 or not entities2:
            return 0.0
        
        # Entity overlap (weighted more heavily)
        entity_overlap = len(set(entities1) & set(entities2))
        entity_score = entity_overlap / max(len(entities1), len(entities2))
        
        # Topic overlap
        topic_overlap = len(set(topics1) & set(topics2)) if topics1 and topics2 else 0
        topic_score = topic_overlap / max(len(topics1), len(topics2), 1)
        
        # Weighted combination
        return 0.7 * entity_score + 0.3 * topic_score
    
    @staticmethod
    def _generate_id(prefix: str) -> str:
        """Generate unique ID with prefix"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        hash_part = hashlib.md5(timestamp.encode()).hexdigest()[:8]
        return f"{prefix}_{hash_part}"
    
    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to URL-safe slug"""
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[\s_-]+', '-', text)
        return text.strip('-')[:100]
