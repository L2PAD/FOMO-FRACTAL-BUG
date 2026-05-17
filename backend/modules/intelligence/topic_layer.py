"""
Topic Layer

Intermediate layer between Root Events and Narratives.

Architecture:
root_events → topics → narratives

Topics are more specific than narratives:
- Narrative: "Bitcoin ETF"
- Topics: "BlackRock ETF", "SEC Approval", "ETF Inflows"

This improves clustering and event-to-narrative mapping.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
import hashlib


class TopicStatus(str, Enum):
    """Topic lifecycle status"""
    EMERGING = "emerging"    # Just detected
    ACTIVE = "active"        # Ongoing coverage
    COOLING = "cooling"      # Less activity
    ARCHIVED = "archived"    # Historical


class Topic(BaseModel):
    """
    Topic - intermediate between events and narratives
    
    Example:
    - Topic: "BlackRock Bitcoin ETF Approval"
    - Parent Narrative: "Bitcoin ETF"
    - Events: [SEC filing, Approval news, Trading starts]
    """
    id: str = Field(..., description="Unique ID (topic_xxx)")
    name: str = Field(..., description="Topic name")
    canonical_name: str = Field(..., description="URL-safe slug")
    
    # Parent narrative
    narrative_id: Optional[str] = None
    narrative_name: Optional[str] = None
    
    # Classification
    keywords: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    primary_entity: Optional[str] = None
    
    # Status
    status: TopicStatus = Field(TopicStatus.EMERGING)
    
    # Metrics
    event_count: int = Field(0)
    article_count: int = Field(0)
    momentum_score: float = Field(0.0, ge=0, le=100)
    sentiment_avg: float = Field(0.0, ge=-1, le=1)
    importance_max: float = Field(0.0, ge=0, le=100)
    
    # Timeline
    first_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_event_time: Optional[datetime] = None
    
    # Metadata
    source_types: List[str] = Field(default_factory=list, description="news/twitter/telegram/etc")
    
    class Config:
        use_enum_values = True


class TopicEventLink(BaseModel):
    """Link between topic and root event"""
    topic_id: str
    event_id: str
    relevance_score: float = Field(0.5, ge=0, le=1)
    is_primary: bool = Field(False, description="Is this the primary topic for event")
    linked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TopicCluster(BaseModel):
    """
    Cluster of related topics
    
    Used for narrative detection
    """
    id: str
    topics: List[str] = Field(default_factory=list)
    suggested_narrative: Optional[str] = None
    coherence_score: float = Field(0.0, ge=0, le=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# TOPIC DETECTION PATTERNS
# =============================================================================

TOPIC_PATTERNS = {
    # ETF Topics
    "etf": {
        "keywords": ["etf", "exchange traded fund", "spot etf", "futures etf"],
        "narrative": "crypto_etf"
    },
    "blackrock_etf": {
        "keywords": ["blackrock", "ibit", "ishares"],
        "entities": ["blackrock", "bitcoin"],
        "narrative": "bitcoin_etf"
    },
    "grayscale_etf": {
        "keywords": ["grayscale", "gbtc", "ethe"],
        "entities": ["grayscale", "bitcoin", "ethereum"],
        "narrative": "crypto_etf"
    },
    
    # Regulatory Topics
    "sec_action": {
        "keywords": ["sec", "securities", "enforcement", "lawsuit", "settlement"],
        "entities": ["sec"],
        "narrative": "regulation"
    },
    "binance_regulation": {
        "keywords": ["binance", "cz", "doj", "cftc", "settlement"],
        "entities": ["binance"],
        "narrative": "exchange_regulation"
    },
    
    # Token Events
    "token_unlock": {
        "keywords": ["unlock", "vesting", "cliff", "token release"],
        "narrative": "tokenomics"
    },
    "airdrop": {
        "keywords": ["airdrop", "claim", "distribution", "retroactive"],
        "narrative": "airdrops"
    },
    
    # DeFi Topics
    "defi_exploit": {
        "keywords": ["exploit", "hack", "drained", "flash loan", "reentrancy"],
        "narrative": "defi_security"
    },
    "defi_tvl": {
        "keywords": ["tvl", "total value locked", "deposits", "protocol growth"],
        "narrative": "defi_growth"
    },
    
    # L2/Scaling
    "l2_launch": {
        "keywords": ["mainnet", "launch", "live", "l2", "layer 2", "rollup"],
        "narrative": "scaling"
    },
    "l2_airdrop": {
        "keywords": ["airdrop", "token launch", "tge"],
        "entities": ["arbitrum", "optimism", "zksync", "base", "blast"],
        "narrative": "l2_tokens"
    },
    
    # AI x Crypto
    "ai_crypto": {
        "keywords": ["ai", "artificial intelligence", "machine learning", "llm", "gpt"],
        "entities": ["tao", "fet", "rndr", "ocean", "near"],
        "narrative": "ai_crypto"
    },
    
    # Stablecoins
    "stablecoin_depeg": {
        "keywords": ["depeg", "depegged", "peg", "stablecoin crisis"],
        "narrative": "stablecoin_stability"
    },
    "stablecoin_regulation": {
        "keywords": ["stablecoin", "reserve", "audit", "backing"],
        "narrative": "stablecoin_regulation"
    },
}


class TopicService:
    """
    Service for managing topics
    """
    
    def __init__(self, db):
        self.db = db
        self.topics = db.topics
        self.topic_events = db.topic_events
        self.narratives = db.narratives
    
    async def ensure_indexes(self):
        """Create indexes"""
        await self.topics.create_index("id", unique=True)
        await self.topics.create_index("canonical_name")
        await self.topics.create_index("narrative_id")
        await self.topics.create_index("status")
        await self.topics.create_index([("momentum_score", -1)])
        await self.topics.create_index([("keywords", 1)])
        await self.topics.create_index([("entities", 1)])
        
        await self.topic_events.create_index([("topic_id", 1), ("event_id", 1)], unique=True)
        await self.topic_events.create_index("event_id")
    
    async def detect_topics_for_event(
        self,
        event_id: str,
        title: str,
        entities: List[str],
        content: str = ""
    ) -> List[Topic]:
        """
        Detect relevant topics for an event
        
        Returns list of matched topics
        """
        text = f"{title} {content}".lower()
        matched_topics = []
        
        # Check against patterns
        for pattern_id, pattern in TOPIC_PATTERNS.items():
            score = self._calculate_pattern_match(text, entities, pattern)
            
            if score > 0.3:  # Threshold
                # Find or create topic
                topic = await self._get_or_create_topic(pattern_id, pattern)
                
                # Link event to topic
                await self._link_event_to_topic(
                    topic_id=topic.id,
                    event_id=event_id,
                    relevance_score=score,
                    is_primary=(score > 0.7)
                )
                
                matched_topics.append(topic)
        
        return matched_topics
    
    def _calculate_pattern_match(
        self,
        text: str,
        entities: List[str],
        pattern: Dict
    ) -> float:
        """Calculate how well text matches a pattern"""
        score = 0.0
        matches = 0
        total_checks = 0
        
        # Check keywords
        keywords = pattern.get("keywords", [])
        if keywords:
            keyword_matches = sum(1 for kw in keywords if kw.lower() in text)
            if keyword_matches > 0:
                score += 0.4 * (keyword_matches / len(keywords))
                matches += keyword_matches
            total_checks += len(keywords)
        
        # Check entities
        pattern_entities = pattern.get("entities", [])
        if pattern_entities:
            entity_matches = sum(
                1 for pe in pattern_entities 
                if pe.lower() in [e.lower() for e in entities]
            )
            if entity_matches > 0:
                score += 0.6 * (entity_matches / len(pattern_entities))
                matches += entity_matches
            total_checks += len(pattern_entities)
        
        return min(1.0, score)
    
    async def _get_or_create_topic(
        self,
        pattern_id: str,
        pattern: Dict
    ) -> Topic:
        """Get existing topic or create new one"""
        topic_id = f"topic_{pattern_id}"
        
        existing = await self.topics.find_one({"id": topic_id})
        if existing:
            return Topic(**existing)
        
        # Create new topic
        narrative_id = pattern.get("narrative")
        narrative_name = None
        if narrative_id:
            narrative = await self.narratives.find_one({"canonical_name": narrative_id})
            if narrative:
                narrative_id = narrative.get("id")
                narrative_name = narrative.get("name")
        
        topic = Topic(
            id=topic_id,
            name=pattern_id.replace("_", " ").title(),
            canonical_name=pattern_id,
            narrative_id=narrative_id,
            narrative_name=narrative_name,
            keywords=pattern.get("keywords", []),
            entities=pattern.get("entities", [])
        )
        
        await self.topics.insert_one(topic.dict())
        return topic
    
    async def _link_event_to_topic(
        self,
        topic_id: str,
        event_id: str,
        relevance_score: float,
        is_primary: bool
    ):
        """Create event-topic link"""
        link = TopicEventLink(
            topic_id=topic_id,
            event_id=event_id,
            relevance_score=relevance_score,
            is_primary=is_primary
        )
        
        await self.topic_events.update_one(
            {"topic_id": topic_id, "event_id": event_id},
            {"$set": link.dict()},
            upsert=True
        )
        
        # Update topic metrics
        await self.topics.update_one(
            {"id": topic_id},
            {
                "$inc": {"event_count": 1},
                "$set": {
                    "last_updated": datetime.now(timezone.utc),
                    "last_event_time": datetime.now(timezone.utc)
                }
            }
        )
    
    async def get_topics_for_event(self, event_id: str) -> List[Dict]:
        """Get all topics linked to an event"""
        links = await self.topic_events.find(
            {"event_id": event_id}
        ).to_list(length=20)
        
        topic_ids = [l["topic_id"] for l in links]
        
        if not topic_ids:
            return []
        
        topics = await self.topics.find(
            {"id": {"$in": topic_ids}}
        ).to_list(length=20)
        
        return topics
    
    async def get_events_for_topic(
        self,
        topic_id: str,
        limit: int = 50
    ) -> List[str]:
        """Get event IDs for a topic"""
        links = await self.topic_events.find(
            {"topic_id": topic_id}
        ).sort("linked_at", -1).limit(limit).to_list(length=limit)
        
        return [l["event_id"] for l in links]
    
    async def update_topic_momentum(self, topic_id: str):
        """Update topic momentum based on recent activity"""
        # Count events in last 24h
        yesterday = datetime.now(timezone.utc) - timedelta(hours=24)
        
        recent_count = await self.topic_events.count_documents({
            "topic_id": topic_id,
            "linked_at": {"$gte": yesterday}
        })
        
        # Calculate momentum (simple formula)
        momentum = min(100, recent_count * 10)
        
        # Update status based on momentum
        status = TopicStatus.ACTIVE
        if momentum < 10:
            status = TopicStatus.COOLING
        elif momentum > 50:
            status = TopicStatus.ACTIVE
        
        await self.topics.update_one(
            {"id": topic_id},
            {"$set": {
                "momentum_score": momentum,
                "status": status.value,
                "last_updated": datetime.now(timezone.utc)
            }}
        )
    
    async def get_trending_topics(self, limit: int = 20) -> List[Dict]:
        """Get topics with highest momentum"""
        cursor = self.topics.find({
            "status": {"$ne": TopicStatus.ARCHIVED.value}
        }).sort("momentum_score", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def suggest_narrative_for_topic(self, topic_id: str) -> Optional[str]:
        """Suggest narrative for a topic based on keywords/entities"""
        topic = await self.topics.find_one({"id": topic_id})
        if not topic:
            return None
        
        keywords = topic.get("keywords", [])
        entities = topic.get("entities", [])
        
        # Find narratives with overlapping keywords/entities
        cursor = self.narratives.find({
            "$or": [
                {"keywords": {"$in": keywords}},
                {"topics": {"$in": [topic.get("canonical_name")]}}
            ]
        }).limit(5)
        
        narratives = await cursor.to_list(length=5)
        
        if narratives:
            return narratives[0].get("id")
        
        return None


# =============================================================================
# ROOT EVENT POPULATION SERVICE
# =============================================================================

class RootEventPopulationService:
    """
    Service to populate root_events from news_intelligence and other sources
    """
    
    def __init__(self, db):
        self.db = db
        self.root_events = db.root_events
        self.articles = db.normalized_articles
        self.raw_articles = db.raw_articles
        self.topic_service = TopicService(db)
    
    async def populate_from_articles(self, limit: int = 500) -> Dict:
        """
        Create root_events from normalized articles
        
        Groups similar articles into events
        """
        stats = {"processed": 0, "events_created": 0, "topics_linked": 0}
        
        # Get recent articles not yet processed
        cursor = self.articles.find({
            "root_event_id": {"$exists": False}
        }).sort("first_seen", -1).limit(limit)
        
        async for article in cursor:
            try:
                # Create or find root event for this article
                event = await self._create_or_link_event(article)
                
                if event:
                    # Detect topics
                    topics = await self.topic_service.detect_topics_for_event(
                        event_id=event["id"],
                        title=event.get("title", ""),
                        entities=event.get("entities", []),
                        content=event.get("summary", "")
                    )
                    
                    stats["topics_linked"] += len(topics)
                    
                    if event.get("_created"):
                        stats["events_created"] += 1
                
                stats["processed"] += 1
                
            except Exception as e:
                print(f"Error processing article: {e}")
        
        return stats
    
    async def _create_or_link_event(self, article: Dict) -> Optional[Dict]:
        """Create root event from article or link to existing"""
        title = article.get("title", "")
        entities = article.get("entities", [])
        
        if not title:
            return None
        
        # Try to find existing similar event
        existing = await self._find_similar_event(title, entities)
        
        if existing:
            # Update existing event
            await self.root_events.update_one(
                {"id": existing["id"]},
                {
                    "$inc": {"source_count": 1, "update_count": 1},
                    "$set": {"last_updated": datetime.now(timezone.utc)},
                    "$addToSet": {"source_urls": article.get("url")}
                }
            )
            
            # Link article to event
            await self.articles.update_one(
                {"_id": article["_id"]},
                {"$set": {"root_event_id": existing["id"]}}
            )
            
            return existing
        
        # Create new event
        event_id = self._generate_event_id()
        
        # Calculate scores
        from modules.intelligence.enhanced_scoring import enhanced_scoring_pipeline
        scores = enhanced_scoring_pipeline.score_article(
            title=title,
            content=article.get("content", ""),
            source=article.get("source", ""),
            entities=entities
        )
        
        event = {
            "id": event_id,
            "title": title,
            "canonical_name": self._slugify(title),
            "summary": article.get("summary") or article.get("content", "")[:500],
            "entities": entities,
            "event_entities": [],  # Will be populated
            "topics": [],
            "narrative_ids": [],
            "sentiment_score": scores.sentiment_score,
            "importance_score": scores.importance_score,
            "impact_score": scores.impact_score,
            "confidence_score": scores.confidence_score,
            "rumor_score": scores.rumor_score,
            "fomo_score": scores.fomo_score,
            "lifecycle_stage": "emerging",
            "source_count": 1,
            "update_count": 0,
            "source_urls": [article.get("url")] if article.get("url") else [],
            "first_seen": article.get("first_seen", datetime.now(timezone.utc)),
            "last_updated": datetime.now(timezone.utc),
            "_created": True
        }
        
        await self.root_events.insert_one(event)
        
        # Link article
        await self.articles.update_one(
            {"_id": article["_id"]},
            {"$set": {"root_event_id": event_id}}
        )
        
        return event
    
    async def _find_similar_event(
        self,
        title: str,
        entities: List[str],
        hours_window: int = 48
    ) -> Optional[Dict]:
        """Find existing similar event"""
        if not entities:
            return None
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_window)
        
        # Find events with overlapping entities
        cursor = self.root_events.find({
            "entities": {"$in": entities},
            "first_seen": {"$gte": cutoff},
            "lifecycle_stage": {"$ne": "resolved"}
        }).limit(50)
        
        title_words = set(title.lower().split())
        
        async for event in cursor:
            event_title_words = set(event.get("title", "").lower().split())
            
            # Check word overlap
            overlap = len(title_words & event_title_words)
            if overlap >= 3:  # At least 3 common words
                return event
        
        return None
    
    @staticmethod
    def _generate_event_id() -> str:
        """Generate unique event ID"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        hash_part = hashlib.md5(timestamp.encode()).hexdigest()[:8]
        return f"re_{hash_part}"
    
    @staticmethod
    def _slugify(text: str) -> str:
        """Convert to URL-safe slug"""
        import re
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[\s_-]+', '-', text)
        return text.strip('-')[:100]
