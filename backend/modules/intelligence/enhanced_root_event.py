"""
Enhanced Root Event Model with Event Entities

Additions per architecture audit:
1. event_entities: Direct links to entities mentioned in event
2. Entity relationship types: primary/secondary/mentioned

Example:
  Event: "BlackRock Bitcoin ETF Approved by SEC"
  entities:
    - BlackRock (type: fund, role: primary)
    - Bitcoin (type: asset, role: primary)
    - SEC (type: regulator, role: primary)
    - Grayscale (type: fund, role: mentioned)
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
import hashlib


class EntityRole(str, Enum):
    """Role of entity in event"""
    PRIMARY = "primary"      # Main subject of the event
    SECONDARY = "secondary"  # Important but not main subject
    MENTIONED = "mentioned"  # Just mentioned in context


class EntityType(str, Enum):
    """Type of entity"""
    PROJECT = "project"
    ASSET = "asset"
    FUND = "fund"
    PERSON = "person"
    EXCHANGE = "exchange"
    REGULATOR = "regulator"
    EXTERNAL = "external"


class EventEntity(BaseModel):
    """
    Entity linked to an event
    
    This enables:
    - Graph auto-connection from events
    - Entity-based event filtering
    - Impact analysis per entity
    """
    entity_id: str = Field(..., description="Entity identifier")
    entity_type: EntityType
    entity_name: str = Field(..., description="Display name")
    entity_symbol: Optional[str] = Field(None, description="Ticker symbol if applicable")
    
    # Role in event
    role: EntityRole = Field(EntityRole.MENTIONED)
    
    # Context
    sentiment_for_entity: float = Field(0.0, ge=-1, le=1, description="Event sentiment toward this entity")
    impact_on_entity: float = Field(0.0, ge=0, le=100, description="Potential impact on entity")
    
    # Extraction metadata
    confidence: float = Field(0.5, ge=0, le=1, description="Extraction confidence")
    extracted_from: str = Field("title", description="title/content/ai")
    
    class Config:
        use_enum_values = True


class EnhancedRootEvent(BaseModel):
    """
    Enhanced Root Event with entity links
    
    Core principle: Event → Entities is the foundation for Graph
    """
    id: str = Field(..., description="Unique identifier (re_xxx)")
    title: str = Field(..., description="Canonical title")
    canonical_name: str = Field(..., description="URL-safe slug")
    summary: Optional[str] = Field(None, description="AI-generated summary")
    
    # Classification
    event_type: Optional[str] = Field(None, description="funding, unlock, listing, hack, regulation, etc.")
    topics: List[str] = Field(default_factory=list)
    
    # ═══════════════════════════════════════════════════════════════
    # NEW: Structured Entity Links
    # ═══════════════════════════════════════════════════════════════
    
    event_entities: List[EventEntity] = Field(
        default_factory=list,
        description="Structured entity links with roles"
    )
    
    # Legacy fields (kept for compatibility)
    entities: List[str] = Field(default_factory=list, description="Simple entity list")
    
    # ═══════════════════════════════════════════════════════════════
    
    # Scores (enhanced with impact)
    importance_score: float = Field(0.0, ge=0, le=100)
    impact_score: float = Field(0.0, ge=0, le=100, description="Market impact potential")
    max_importance: float = Field(0.0, description="Peak importance ever reached")
    sentiment_score: float = Field(0.0, ge=-1, le=1)
    confidence_score: float = Field(0.0, ge=0, le=1)
    rumor_score: float = Field(0.0, ge=0, le=1)
    fomo_score: float = Field(0.0, ge=0, le=100)
    
    # Lifecycle
    lifecycle_stage: str = Field("emerging")  # emerging, active, declining, resolved
    
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
    
    def get_primary_entities(self) -> List[EventEntity]:
        """Get entities with primary role"""
        return [e for e in self.event_entities if e.role == EntityRole.PRIMARY]
    
    def get_entities_by_type(self, entity_type: EntityType) -> List[EventEntity]:
        """Get entities of specific type"""
        return [e for e in self.event_entities if e.entity_type == entity_type]
    
    def get_asset_symbols(self) -> List[str]:
        """Get asset symbols for market correlation"""
        return [
            e.entity_symbol for e in self.event_entities 
            if e.entity_type == EntityType.ASSET and e.entity_symbol
        ]


class EventEntityExtractor:
    """
    Extract and classify entities from event content
    """
    
    # Known entity patterns
    FUND_INDICATORS = {"capital", "ventures", "labs", "fund", "vc", "holdings"}
    REGULATOR_INDICATORS = {"sec", "cftc", "fca", "occ", "ofac", "doj", "fbi"}
    EXCHANGE_INDICATORS = {"exchange", "binance", "coinbase", "kraken", "bybit", "okx"}
    
    def __init__(self, entity_registry=None):
        """
        Args:
            entity_registry: Database of known entities
        """
        self.registry = entity_registry
    
    def extract_entities(
        self,
        title: str,
        content: str = "",
        known_entities: List[str] = None
    ) -> List[EventEntity]:
        """
        Extract entities from event text
        
        Priority:
        1. Known entities from registry
        2. Pattern-matched entities
        3. NER-extracted entities (if available)
        """
        entities = []
        text = f"{title} {content}".lower()
        
        # Process known entities first
        if known_entities:
            for entity_name in known_entities:
                if entity_name.lower() in text:
                    entity = self._create_entity(
                        entity_name,
                        self._infer_entity_type(entity_name),
                        self._infer_role(entity_name, title),
                        confidence=0.9
                    )
                    entities.append(entity)
        
        # Pattern matching for regulators
        for regulator in self.REGULATOR_INDICATORS:
            if regulator in text:
                entity = self._create_entity(
                    regulator.upper(),
                    EntityType.REGULATOR,
                    self._infer_role(regulator, title),
                    confidence=0.85
                )
                if not self._entity_exists(entities, entity.entity_id):
                    entities.append(entity)
        
        return entities
    
    def _create_entity(
        self,
        name: str,
        entity_type: EntityType,
        role: EntityRole,
        confidence: float = 0.5,
        symbol: str = None
    ) -> EventEntity:
        """Create EventEntity instance"""
        return EventEntity(
            entity_id=self._generate_entity_id(name),
            entity_type=entity_type,
            entity_name=name,
            entity_symbol=symbol,
            role=role,
            confidence=confidence
        )
    
    def _infer_entity_type(self, name: str) -> EntityType:
        """Infer entity type from name"""
        name_lower = name.lower()
        
        if any(ind in name_lower for ind in self.FUND_INDICATORS):
            return EntityType.FUND
        if any(ind in name_lower for ind in self.REGULATOR_INDICATORS):
            return EntityType.REGULATOR
        if any(ind in name_lower for ind in self.EXCHANGE_INDICATORS):
            return EntityType.EXCHANGE
        
        # Check if it looks like a ticker
        if name.isupper() and len(name) <= 5:
            return EntityType.ASSET
        
        return EntityType.PROJECT
    
    def _infer_role(self, entity_name: str, title: str) -> EntityRole:
        """Infer entity role based on position in title"""
        title_lower = title.lower()
        entity_lower = entity_name.lower()
        
        # Primary if in first 50 chars of title
        title_start = title_lower[:50]
        if entity_lower in title_start:
            return EntityRole.PRIMARY
        
        # Secondary if in title at all
        if entity_lower in title_lower:
            return EntityRole.SECONDARY
        
        return EntityRole.MENTIONED
    
    def _entity_exists(self, entities: List[EventEntity], entity_id: str) -> bool:
        """Check if entity already in list"""
        return any(e.entity_id == entity_id for e in entities)
    
    @staticmethod
    def _generate_entity_id(name: str) -> str:
        """Generate consistent entity ID"""
        return hashlib.md5(name.lower().encode()).hexdigest()[:12]


class EnhancedRootEventService:
    """
    Enhanced service for managing root events with entity links
    """
    
    def __init__(self, db):
        self.db = db
        self.root_events = db.root_events
        self.event_updates = db.event_updates
        self.entity_extractor = EventEntityExtractor()
    
    async def create_or_update_event(
        self,
        title: str,
        entities: List[str],
        topics: List[str],
        scores: Dict = None,
        content: str = ""
    ) -> EnhancedRootEvent:
        """
        Create new root event or update existing
        
        Extracts and links entities automatically
        """
        # Extract structured entities
        event_entities = self.entity_extractor.extract_entities(
            title, content, entities
        )
        
        # Find or create root event
        existing = await self._find_similar(title, entities)
        
        if existing:
            # Update existing
            await self.root_events.update_one(
                {"id": existing["id"]},
                {
                    "$set": {
                        "event_entities": [e.dict() for e in event_entities],
                        "last_updated": datetime.now(timezone.utc),
                        **(scores or {})
                    },
                    "$inc": {"update_count": 1}
                }
            )
            updated = await self.root_events.find_one({"id": existing["id"]})
            return EnhancedRootEvent(**updated)
        
        # Create new
        event = EnhancedRootEvent(
            id=self._generate_id("re"),
            title=title,
            canonical_name=self._slugify(title),
            entities=entities,
            topics=topics,
            event_entities=event_entities,
            **(scores or {})
        )
        
        await self.root_events.insert_one(event.dict())
        return event
    
    async def get_events_by_entity(
        self,
        entity_id: str,
        role: EntityRole = None,
        limit: int = 50
    ) -> List[EnhancedRootEvent]:
        """
        Get events involving specific entity
        
        This is key for entity-centric feeds
        """
        query = {"event_entities.entity_id": entity_id}
        if role:
            query["event_entities.role"] = role.value
        
        cursor = self.root_events.find(query).sort(
            "last_updated", -1
        ).limit(limit)
        
        events = await cursor.to_list(length=limit)
        return [EnhancedRootEvent(**e) for e in events]
    
    async def get_entity_impact_timeline(
        self,
        entity_id: str,
        days: int = 30
    ) -> List[Dict]:
        """
        Get impact timeline for an entity
        
        Shows how events have affected this entity over time
        """
        from datetime import timedelta
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        pipeline = [
            {"$match": {
                "event_entities.entity_id": entity_id,
                "first_seen": {"$gte": cutoff}
            }},
            {"$unwind": "$event_entities"},
            {"$match": {"event_entities.entity_id": entity_id}},
            {"$project": {
                "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$first_seen"}},
                "impact": "$event_entities.impact_on_entity",
                "sentiment": "$event_entities.sentiment_for_entity",
                "event_id": "$id",
                "title": "$title"
            }},
            {"$sort": {"date": 1}}
        ]
        
        cursor = self.root_events.aggregate(pipeline)
        return await cursor.to_list(length=1000)
    
    async def _find_similar(
        self,
        title: str,
        entities: List[str]
    ) -> Optional[Dict]:
        """Find similar existing event"""
        if not entities:
            return None
        
        cursor = self.root_events.find({
            "entities": {"$in": entities},
            "lifecycle_stage": {"$ne": "resolved"}
        }).limit(50)
        
        candidates = await cursor.to_list(length=50)
        
        # Simple title similarity
        title_lower = title.lower()
        for candidate in candidates:
            candidate_title = candidate.get("title", "").lower()
            # Check for significant word overlap
            title_words = set(title_lower.split())
            candidate_words = set(candidate_title.split())
            overlap = len(title_words & candidate_words)
            if overlap >= 3:  # At least 3 common words
                return candidate
        
        return None
    
    @staticmethod
    def _generate_id(prefix: str) -> str:
        """Generate unique ID"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        hash_part = hashlib.md5(timestamp.encode()).hexdigest()[:8]
        return f"{prefix}_{hash_part}"
    
    @staticmethod
    def _slugify(text: str) -> str:
        """Convert to URL-safe slug"""
        import re
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[\s_-]+', '-', text)
        return text.strip('-')[:100]
