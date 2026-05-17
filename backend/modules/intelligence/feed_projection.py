"""
Feed Projection Layer

CRITICAL for UI performance.

Feed cannot be built from 10 collections on-the-fly.
This is a pre-computed, denormalized projection optimized for feed display.

Architecture:
events → narratives → scoring → FEED_CARDS

Each feed card is self-contained:
- No joins required
- Instant serialization
- Index-optimized queries
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
import hashlib


class FeedCardType(str, Enum):
    """Type of feed card"""
    EVENT = "event"
    NARRATIVE = "narrative"
    UNLOCK = "unlock"
    FUNDING = "funding"
    LISTING = "listing"
    ALERT = "alert"


class FeedCardPriority(str, Enum):
    """Display priority"""
    BREAKING = "breaking"  # Top of feed, highlighted
    HIGH = "high"          # Prominent display
    NORMAL = "normal"      # Standard display
    LOW = "low"            # Collapsed/hidden


class FeedCard(BaseModel):
    """
    Pre-computed feed card - ready for instant display
    
    This is the canonical feed item model.
    All feed queries should hit this collection, not source collections.
    """
    id: str = Field(..., description="Unique card ID")
    
    # Source reference
    root_event_id: Optional[str] = None
    narrative_id: Optional[str] = None
    source_type: str = Field("event", description="event/narrative/unlock/funding")
    
    # Display content (pre-computed)
    title: str
    summary: Optional[str] = None
    title_ru: Optional[str] = Field(None, description="Russian translation")
    summary_ru: Optional[str] = None
    
    # Card type and priority
    card_type: FeedCardType = Field(FeedCardType.EVENT)
    priority: FeedCardPriority = Field(FeedCardPriority.NORMAL)
    
    # Entities (denormalized for display)
    entities: List[Dict] = Field(
        default_factory=list,
        description="[{id, name, symbol, type, role}]"
    )
    primary_symbol: Optional[str] = Field(None, description="Main asset symbol")
    
    # Narrative context
    narrative: Optional[str] = Field(None, description="Parent narrative name")
    narrative_momentum: Optional[float] = None
    
    # Scores (pre-computed)
    sentiment: str = Field("neutral", description="positive/negative/neutral")
    sentiment_score: float = Field(0.0, ge=-1, le=1)
    importance: float = Field(0.0, ge=0, le=100)
    impact: float = Field(0.0, ge=0, le=100)
    confidence: float = Field(0.0, ge=0, le=1)
    fomo_score: float = Field(0.0, ge=0, le=100)
    
    # Visual elements
    image_url: Optional[str] = None
    icon: Optional[str] = None  # emoji or icon name
    color: Optional[str] = None  # hex color for highlight
    
    # Stats (for social proof)
    source_count: int = Field(0)
    update_count: int = Field(0)
    view_count: int = Field(0)
    
    # Timeline
    event_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = Field(None, description="Auto-archive time")
    
    # Indexing
    tags: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    
    # Archive flag
    is_archived: bool = Field(False)
    archive_reason: Optional[str] = None
    
    class Config:
        use_enum_values = True


class FeedProjectionService:
    """
    Service for managing feed projections
    
    Responsibilities:
    - Create feed cards from events
    - Update cards when sources change
    - Manage card lifecycle (archive, expire)
    - Provide fast feed queries
    """
    
    def __init__(self, db):
        self.db = db
        self.feed_cards = db.feed_cards
        
        # Priority thresholds
        self.BREAKING_THRESHOLD = 90
        self.HIGH_THRESHOLD = 70
        self.LOW_THRESHOLD = 30
    
    async def ensure_indexes(self):
        """Create indexes for fast queries"""
        await self.feed_cards.create_index("id", unique=True)
        await self.feed_cards.create_index("root_event_id")
        await self.feed_cards.create_index("narrative_id")
        await self.feed_cards.create_index("card_type")
        await self.feed_cards.create_index("priority")
        await self.feed_cards.create_index("fomo_score")
        await self.feed_cards.create_index("event_time")
        await self.feed_cards.create_index("is_archived")
        await self.feed_cards.create_index([("entities.symbol", 1)])
        await self.feed_cards.create_index([("tags", 1)])
        
        # Compound indexes for common queries
        await self.feed_cards.create_index([
            ("is_archived", 1),
            ("priority", -1),
            ("event_time", -1)
        ])
        await self.feed_cards.create_index([
            ("is_archived", 1),
            ("card_type", 1),
            ("event_time", -1)
        ])
    
    async def create_card_from_event(
        self,
        event: Dict,
        narrative: Dict = None
    ) -> FeedCard:
        """
        Create feed card from root event
        
        This is the main projection method.
        Called when events are created/updated.
        """
        # Determine priority
        fomo_score = event.get("fomo_score", 0)
        priority = FeedCardPriority.NORMAL
        
        if fomo_score >= self.BREAKING_THRESHOLD:
            priority = FeedCardPriority.BREAKING
        elif fomo_score >= self.HIGH_THRESHOLD:
            priority = FeedCardPriority.HIGH
        elif fomo_score <= self.LOW_THRESHOLD:
            priority = FeedCardPriority.LOW
        
        # Determine card type
        event_type = event.get("event_type", "news")
        card_type = self._map_event_type(event_type)
        
        # Extract entities for display
        entities = []
        primary_symbol = None
        
        event_entities = event.get("event_entities", [])
        for ee in event_entities:
            entities.append({
                "id": ee.get("entity_id"),
                "name": ee.get("entity_name"),
                "symbol": ee.get("entity_symbol"),
                "type": ee.get("entity_type"),
                "role": ee.get("role")
            })
            # Set primary symbol from first asset
            if ee.get("entity_type") == "asset" and not primary_symbol:
                primary_symbol = ee.get("entity_symbol")
        
        # Sentiment label
        sentiment_score = event.get("sentiment_score", 0)
        sentiment = "neutral"
        if sentiment_score > 0.2:
            sentiment = "positive"
        elif sentiment_score < -0.2:
            sentiment = "negative"
        
        # Visual styling
        color = None
        if priority == FeedCardPriority.BREAKING:
            color = "#ef4444" if sentiment == "negative" else "#22c55e"
        
        # Create card
        card = FeedCard(
            id=self._generate_card_id(event.get("id")),
            root_event_id=event.get("id"),
            source_type="event",
            title=event.get("title", ""),
            summary=event.get("summary"),
            card_type=card_type,
            priority=priority,
            entities=entities,
            primary_symbol=primary_symbol,
            narrative=narrative.get("name") if narrative else None,
            narrative_id=narrative.get("id") if narrative else None,
            narrative_momentum=narrative.get("momentum_score") if narrative else None,
            sentiment=sentiment,
            sentiment_score=sentiment_score,
            importance=event.get("importance_score", 0),
            impact=event.get("impact_score", 0),
            confidence=event.get("confidence_score", 0),
            fomo_score=fomo_score,
            color=color,
            source_count=event.get("source_count", 0),
            update_count=event.get("update_count", 0),
            event_time=event.get("first_seen", datetime.now(timezone.utc)),
            tags=event.get("entities", []),
            topics=event.get("topics", [])
        )
        
        # Upsert
        await self.feed_cards.update_one(
            {"root_event_id": event.get("id")},
            {"$set": card.dict()},
            upsert=True
        )
        
        return card
    
    async def get_feed(
        self,
        limit: int = 50,
        offset: int = 0,
        card_type: FeedCardType = None,
        min_fomo: float = 0,
        entity_symbol: str = None,
        narrative_id: str = None,
        include_archived: bool = False
    ) -> List[FeedCard]:
        """
        Get feed cards with filtering
        
        This is THE feed query method.
        Optimized for fast UI rendering.
        """
        query = {}
        
        if not include_archived:
            query["is_archived"] = False
        
        if card_type:
            query["card_type"] = card_type.value
        
        if min_fomo > 0:
            query["fomo_score"] = {"$gte": min_fomo}
        
        if entity_symbol:
            query["entities.symbol"] = entity_symbol.upper()
        
        if narrative_id:
            query["narrative_id"] = narrative_id
        
        cursor = self.feed_cards.find(query).sort([
            ("priority", -1),  # Breaking first
            ("event_time", -1)  # Then by time
        ]).skip(offset).limit(limit)
        
        cards = await cursor.to_list(length=limit)
        return [FeedCard(**c) for c in cards]
    
    async def get_breaking_feed(self, limit: int = 10) -> List[FeedCard]:
        """
        Get breaking/high priority cards only
        
        For "Top Stories" section
        """
        return await self.get_feed(
            limit=limit,
            min_fomo=self.HIGH_THRESHOLD
        )
    
    async def get_entity_feed(
        self,
        symbol: str,
        limit: int = 30
    ) -> List[FeedCard]:
        """
        Get feed for specific asset/entity
        
        For entity detail pages
        """
        return await self.get_feed(
            limit=limit,
            entity_symbol=symbol
        )
    
    async def get_narrative_feed(
        self,
        narrative_id: str,
        limit: int = 30
    ) -> List[FeedCard]:
        """
        Get feed for specific narrative
        
        For narrative detail pages
        """
        return await self.get_feed(
            limit=limit,
            narrative_id=narrative_id
        )
    
    async def archive_old_cards(self, days: int = 90):
        """
        Archive cards older than specified days
        
        Should run as scheduled job
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        result = await self.feed_cards.update_many(
            {
                "event_time": {"$lt": cutoff},
                "is_archived": False,
                "priority": {"$ne": FeedCardPriority.BREAKING.value}  # Keep breaking forever
            },
            {
                "$set": {
                    "is_archived": True,
                    "archive_reason": f"Auto-archived after {days} days"
                }
            }
        )
        
        return result.modified_count
    
    async def increment_view(self, card_id: str):
        """
        Increment view count
        
        For analytics
        """
        await self.feed_cards.update_one(
            {"id": card_id},
            {"$inc": {"view_count": 1}}
        )
    
    def _map_event_type(self, event_type: str) -> FeedCardType:
        """Map event type to card type"""
        mapping = {
            "funding": FeedCardType.FUNDING,
            "unlock": FeedCardType.UNLOCK,
            "listing": FeedCardType.LISTING,
            "delisting": FeedCardType.LISTING,
            "hack": FeedCardType.ALERT,
            "exploit": FeedCardType.ALERT,
            "regulation": FeedCardType.ALERT,
        }
        return mapping.get(event_type, FeedCardType.EVENT)
    
    @staticmethod
    def _generate_card_id(event_id: str) -> str:
        """Generate card ID from event ID"""
        return f"fc_{event_id}" if event_id else f"fc_{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:12]}"


# =============================================================================
# ARCHIVE MODELS (Phase E)
# =============================================================================

class ArchiveTier(str, Enum):
    """Archive tiers for data lifecycle"""
    HOT = "hot"      # 0-90 days, fast storage
    WARM = "warm"    # 90-365 days, slower storage
    ARCHIVE = "archive"  # >365 days, cold storage


class ArchivePolicy(BaseModel):
    """Policy for data archiving"""
    collection: str
    hot_days: int = 90
    warm_days: int = 365
    archive_after_days: int = 730  # 2 years
    
    # What to keep in hot storage
    keep_hot_if_fomo_above: Optional[float] = 80
    keep_hot_if_breaking: bool = True


DEFAULT_ARCHIVE_POLICIES = [
    ArchivePolicy(collection="feed_cards", hot_days=90, warm_days=365),
    ArchivePolicy(collection="root_events", hot_days=90, warm_days=365, keep_hot_if_breaking=True),
    ArchivePolicy(collection="event_updates", hot_days=30, warm_days=180),
    ArchivePolicy(collection="normalized_articles", hot_days=30, warm_days=90),
    ArchivePolicy(collection="raw_articles", hot_days=7, warm_days=30),
]


class ArchiveService:
    """
    Manages data lifecycle across hot/warm/archive tiers
    """
    
    def __init__(self, db):
        self.db = db
        self.policies = {p.collection: p for p in DEFAULT_ARCHIVE_POLICIES}
    
    async def get_tier(self, collection: str, doc: Dict) -> ArchiveTier:
        """
        Determine which tier a document belongs to
        """
        policy = self.policies.get(collection)
        if not policy:
            return ArchiveTier.HOT
        
        # Get document age
        created_at = doc.get("created_at") or doc.get("first_seen") or doc.get("event_time")
        if not created_at:
            return ArchiveTier.HOT
        
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        
        age_days = (datetime.now(timezone.utc) - created_at).days
        
        # Check for special retention
        if policy.keep_hot_if_breaking and doc.get("priority") == "breaking":
            return ArchiveTier.HOT
        
        if policy.keep_hot_if_fomo_above:
            if doc.get("fomo_score", 0) >= policy.keep_hot_if_fomo_above:
                return ArchiveTier.HOT
        
        # Determine tier by age
        if age_days <= policy.hot_days:
            return ArchiveTier.HOT
        elif age_days <= policy.warm_days:
            return ArchiveTier.WARM
        else:
            return ArchiveTier.ARCHIVE
    
    async def run_archive_job(self, collection: str) -> Dict:
        """
        Run archiving for a collection
        
        Moves documents between tiers based on policy
        """
        policy = self.policies.get(collection)
        if not policy:
            return {"error": "No policy for collection"}
        
        stats = {
            "collection": collection,
            "archived": 0,
            "warmed": 0,
            "kept_hot": 0
        }
        
        # This would actually move documents to different collections
        # or update a tier field
        # Implementation depends on storage strategy
        
        warm_cutoff = datetime.now(timezone.utc) - timedelta(days=policy.hot_days)
        archive_cutoff = datetime.now(timezone.utc) - timedelta(days=policy.warm_days)
        
        # Mark warm
        warm_result = await self.db[collection].update_many(
            {
                "created_at": {"$lt": warm_cutoff, "$gte": archive_cutoff},
                "archive_tier": {"$ne": "warm"}
            },
            {"$set": {"archive_tier": "warm"}}
        )
        stats["warmed"] = warm_result.modified_count
        
        # Mark archive
        archive_result = await self.db[collection].update_many(
            {
                "created_at": {"$lt": archive_cutoff},
                "archive_tier": {"$ne": "archive"},
                "priority": {"$ne": "breaking"}  # Never archive breaking
            },
            {"$set": {"archive_tier": "archive"}}
        )
        stats["archived"] = archive_result.modified_count
        
        return stats
