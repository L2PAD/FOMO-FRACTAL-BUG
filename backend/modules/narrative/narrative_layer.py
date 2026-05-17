"""
Narrative Layer - Market Narrative Intelligence

A Narrative is NOT an event. It's a multi-month story/theme.

Examples:
- AI x Crypto
- Restaking
- Bitcoin ETF
- RWA (Real World Assets)
- Layer 2
- DePIN
- Gaming

Architecture:
root_events → narrative_clustering → narratives

Key insight: Traders think in narratives, not individual events.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
import hashlib


class NarrativeLifecycle(str, Enum):
    EMERGING = "emerging"    # New narrative forming
    GROWTH = "growth"        # Gaining momentum
    PEAK = "peak"           # Maximum attention
    DECLINE = "decline"     # Losing momentum
    DORMANT = "dormant"     # Quiet but may return


class TrendDirection(str, Enum):
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


class Narrative(BaseModel):
    """
    Narrative - A market theme/story that spans multiple events
    
    Example:
    - name: "AI x Crypto"
    - topics: ["ai", "ml", "gpu", "compute", "decentralized-ai"]
    - momentum_score: 82
    """
    id: str = Field(..., description="Unique identifier (n_xxx)")
    name: str = Field(..., description="Human-readable name")
    canonical_name: str = Field(..., description="URL-safe slug")
    description: Optional[str] = None
    
    # Classification
    topics: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    related_narratives: List[str] = Field(default_factory=list)
    
    # Scores
    momentum_score: float = Field(0.0, ge=0, le=100)
    market_relevance: float = Field(0.0, ge=0, le=1)
    confidence: float = Field(0.0, ge=0, le=1)
    
    # Lifecycle
    lifecycle: NarrativeLifecycle = Field(NarrativeLifecycle.EMERGING)
    trend_direction: TrendDirection = Field(TrendDirection.STABLE)
    
    # Stats
    event_count: int = Field(0)
    entity_count: int = Field(0)
    update_count_24h: int = Field(0)
    sentiment_avg: float = Field(0.0, ge=-1, le=1)
    
    # Volume correlation (optional)
    volume_correlation: Optional[float] = Field(None, ge=-1, le=1)
    price_impact_avg: Optional[float] = None
    
    # Timeline
    first_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    peak_date: Optional[datetime] = None
    
    class Config:
        use_enum_values = True


class NarrativeEvent(BaseModel):
    """Link between narrative and root event"""
    narrative_id: str
    root_event_id: str
    weight: float = Field(0.5, ge=0, le=1, description="Relevance to narrative")
    contribution_type: str = Field("related", description="core/related/peripheral")
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NarrativeEntity(BaseModel):
    """Link between narrative and entity"""
    narrative_id: str
    entity_id: str
    entity_type: str  # project, fund, person, token
    relevance_score: float = Field(0.5, ge=0, le=1)
    is_key_player: bool = False
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NarrativeMetrics(BaseModel):
    """Time-series metrics for narrative tracking"""
    narrative_id: str
    date: datetime
    momentum: float
    event_count_24h: int
    sentiment_avg: float
    entity_mentions: int
    source_count: int
    volume_correlation: Optional[float] = None


# =============================================================================
# SEED NARRATIVES
# =============================================================================

SEED_NARRATIVES = [
    {
        "name": "AI x Crypto",
        "canonical_name": "ai-crypto",
        "description": "Intersection of artificial intelligence and blockchain technology",
        "topics": ["ai", "ml", "machine-learning", "gpu", "compute", "decentralized-ai", "llm"],
        "keywords": ["artificial intelligence", "AI token", "decentralized compute", "GPU network"]
    },
    {
        "name": "Bitcoin ETF",
        "canonical_name": "bitcoin-etf",
        "description": "Bitcoin exchange-traded funds and institutional adoption",
        "topics": ["etf", "bitcoin", "institutional", "sec", "regulation"],
        "keywords": ["spot ETF", "ETF approval", "BlackRock", "Grayscale", "GBTC"]
    },
    {
        "name": "Restaking",
        "canonical_name": "restaking",
        "description": "Restaking protocols and liquid staking derivatives",
        "topics": ["restaking", "eigenlayer", "lrt", "lst", "staking"],
        "keywords": ["EigenLayer", "restaking", "liquid restaking", "AVS"]
    },
    {
        "name": "Real World Assets (RWA)",
        "canonical_name": "rwa",
        "description": "Tokenization of real-world assets on blockchain",
        "topics": ["rwa", "tokenization", "real-estate", "bonds", "treasuries"],
        "keywords": ["RWA", "tokenized", "real world assets", "treasury bonds", "real estate"]
    },
    {
        "name": "Layer 2 Scaling",
        "canonical_name": "layer2",
        "description": "Ethereum Layer 2 scaling solutions",
        "topics": ["layer2", "l2", "rollup", "zk", "optimistic", "scaling"],
        "keywords": ["Layer 2", "rollup", "Arbitrum", "Optimism", "Base", "zkSync", "Starknet"]
    },
    {
        "name": "DePIN",
        "canonical_name": "depin",
        "description": "Decentralized Physical Infrastructure Networks",
        "topics": ["depin", "infrastructure", "iot", "wireless", "storage"],
        "keywords": ["DePIN", "decentralized infrastructure", "physical network", "Helium", "Filecoin"]
    },
    {
        "name": "Gaming & Metaverse",
        "canonical_name": "gaming",
        "description": "Blockchain gaming and metaverse projects",
        "topics": ["gaming", "metaverse", "nft", "play-to-earn", "gamefi"],
        "keywords": ["gaming", "metaverse", "P2E", "GameFi", "NFT game"]
    },
    {
        "name": "Memecoins",
        "canonical_name": "memecoins",
        "description": "Meme-based cryptocurrencies and community tokens",
        "topics": ["meme", "memecoin", "doge", "shib", "community"],
        "keywords": ["memecoin", "meme token", "DOGE", "SHIB", "PEPE", "WIF"]
    },
    {
        "name": "DeFi Renaissance",
        "canonical_name": "defi-renaissance",
        "description": "DeFi protocol innovations and TVL growth",
        "topics": ["defi", "dex", "lending", "yield", "liquidity"],
        "keywords": ["DeFi", "DEX", "lending", "yield farming", "liquidity mining"]
    },
    {
        "name": "Solana Ecosystem",
        "canonical_name": "solana-ecosystem",
        "description": "Solana blockchain and its ecosystem growth",
        "topics": ["solana", "sol", "spl", "solana-defi"],
        "keywords": ["Solana", "SOL", "Jupiter", "Marinade", "Raydium"]
    },
    {
        "name": "Bitcoin Ordinals & BRC-20",
        "canonical_name": "bitcoin-ordinals",
        "description": "Bitcoin inscriptions and BRC-20 tokens",
        "topics": ["ordinals", "brc20", "inscriptions", "bitcoin-nft"],
        "keywords": ["Ordinals", "BRC-20", "inscriptions", "Bitcoin NFT", "Runes"]
    },
    {
        "name": "Modular Blockchains",
        "canonical_name": "modular",
        "description": "Modular blockchain architecture and data availability",
        "topics": ["modular", "data-availability", "celestia", "rollup"],
        "keywords": ["modular", "Celestia", "data availability", "DA layer", "sovereign rollup"]
    },
]


class NarrativeService:
    """
    Service for managing narratives and narrative clustering
    """
    
    def __init__(self, db):
        self.db = db
        self.narratives = db.narratives
        self.narrative_events = db.narrative_events
        self.narrative_entities = db.narrative_entities
        self.narrative_metrics = db.narrative_metrics
    
    async def initialize_seed_narratives(self):
        """Initialize database with seed narratives"""
        for seed in SEED_NARRATIVES:
            existing = await self.narratives.find_one(
                {"canonical_name": seed["canonical_name"]}
            )
            if not existing:
                narrative = Narrative(
                    id=self._generate_id("n"),
                    **seed
                )
                await self.narratives.insert_one(narrative.dict())
    
    async def classify_event(
        self,
        root_event_id: str,
        entities: List[str],
        topics: List[str],
        title: str
    ) -> List[str]:
        """
        Classify a root event into one or more narratives
        Returns list of narrative IDs
        """
        matched_narratives = []
        
        # Get all active narratives
        cursor = self.narratives.find({"lifecycle": {"$ne": "dormant"}})
        all_narratives = await cursor.to_list(length=100)
        
        for narrative in all_narratives:
            score = self._calculate_narrative_match(
                narrative, entities, topics, title
            )
            
            if score > 0.3:  # Threshold
                matched_narratives.append({
                    "narrative_id": narrative["id"],
                    "score": score
                })
                
                # Create link
                await self._link_event_to_narrative(
                    narrative["id"],
                    root_event_id,
                    score
                )
        
        # Update narrative stats
        for match in matched_narratives:
            await self._update_narrative_stats(match["narrative_id"])
        
        return [m["narrative_id"] for m in matched_narratives]
    
    async def get_top_narratives(
        self,
        limit: int = 10,
        min_momentum: float = 0
    ) -> List[Narrative]:
        """Get top narratives by momentum"""
        cursor = self.narratives.find({
            "momentum_score": {"$gte": min_momentum},
            "lifecycle": {"$ne": "dormant"}
        }).sort("momentum_score", -1).limit(limit)
        
        narratives = await cursor.to_list(length=limit)
        return [Narrative(**n) for n in narratives]
    
    async def get_narrative_timeline(
        self,
        narrative_id: str,
        days: int = 30
    ) -> List[NarrativeMetrics]:
        """Get momentum timeline for a narrative"""
        from_date = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        from_date = from_date - timedelta(days=days)
        
        cursor = self.narrative_metrics.find({
            "narrative_id": narrative_id,
            "date": {"$gte": from_date}
        }).sort("date", 1)
        
        metrics = await cursor.to_list(length=days)
        return [NarrativeMetrics(**m) for m in metrics]
    
    async def get_narrative_events(
        self,
        narrative_id: str,
        limit: int = 50
    ) -> List[Dict]:
        """Get root events for a narrative"""
        # Get event links
        cursor = self.narrative_events.find({
            "narrative_id": narrative_id
        }).sort("added_at", -1).limit(limit)
        
        links = await cursor.to_list(length=limit)
        event_ids = [l["root_event_id"] for l in links]
        
        # Get actual events
        events_cursor = self.db.root_events.find({
            "id": {"$in": event_ids}
        })
        
        return await events_cursor.to_list(length=limit)
    
    async def get_narrative_entities(
        self,
        narrative_id: str,
        entity_type: str = None
    ) -> List[NarrativeEntity]:
        """Get key entities for a narrative"""
        query = {"narrative_id": narrative_id}
        if entity_type:
            query["entity_type"] = entity_type
        
        cursor = self.narrative_entities.find(query).sort(
            "relevance_score", -1
        ).limit(50)
        
        entities = await cursor.to_list(length=50)
        return [NarrativeEntity(**e) for e in entities]
    
    async def calculate_momentum(self, narrative_id: str) -> float:
        """
        Calculate current momentum score for narrative
        
        Factors:
        - event_count (24h)
        - entity_coverage
        - sentiment_strength
        - source_diversity
        - growth_rate
        """
        # Get recent events
        from_date = datetime.now(timezone.utc) - timedelta(hours=24)
        
        event_count = await self.narrative_events.count_documents({
            "narrative_id": narrative_id,
            "added_at": {"$gte": from_date}
        })
        
        # Get entity count
        entity_count = await self.narrative_entities.count_documents({
            "narrative_id": narrative_id
        })
        
        # Base momentum calculation
        event_score = min(event_count * 5, 40)  # Max 40 from events
        entity_score = min(entity_count * 2, 30)  # Max 30 from entities
        
        # Get sentiment from recent events
        recent_events = await self.narrative_events.find({
            "narrative_id": narrative_id,
            "added_at": {"$gte": from_date}
        }).to_list(length=100)
        
        sentiment_boost = 10  # Default neutral
        
        # Growth rate (compare to previous 24h)
        prev_from = from_date - timedelta(hours=24)
        prev_count = await self.narrative_events.count_documents({
            "narrative_id": narrative_id,
            "added_at": {"$gte": prev_from, "$lt": from_date}
        })
        
        growth_rate = 0
        if prev_count > 0:
            growth_rate = (event_count - prev_count) / prev_count
        
        growth_score = min(max(growth_rate * 20, -10), 20)
        
        momentum = event_score + entity_score + sentiment_boost + growth_score
        momentum = max(0, min(100, momentum))
        
        # Update narrative
        await self.narratives.update_one(
            {"id": narrative_id},
            {
                "$set": {
                    "momentum_score": momentum,
                    "event_count": await self.narrative_events.count_documents(
                        {"narrative_id": narrative_id}
                    ),
                    "update_count_24h": event_count,
                    "last_updated": datetime.now(timezone.utc)
                }
            }
        )
        
        return momentum
    
    async def update_lifecycle(self, narrative_id: str):
        """Update narrative lifecycle based on momentum trend"""
        # Get last 7 days of metrics
        metrics = await self.get_narrative_timeline(narrative_id, days=7)
        
        if len(metrics) < 3:
            return
        
        # Calculate trend
        recent_momentum = sum(m.momentum for m in metrics[-3:]) / 3
        older_momentum = sum(m.momentum for m in metrics[:3]) / 3
        
        change = recent_momentum - older_momentum
        
        narrative = await self.narratives.find_one({"id": narrative_id})
        current_lifecycle = narrative.get("lifecycle", "emerging")
        
        new_lifecycle = current_lifecycle
        new_trend = "stable"
        
        if change > 10:
            new_trend = "up"
            if current_lifecycle in ["emerging", "dormant"]:
                new_lifecycle = "growth"
            elif current_lifecycle == "decline":
                new_lifecycle = "growth"
        elif change < -10:
            new_trend = "down"
            if current_lifecycle == "peak":
                new_lifecycle = "decline"
            elif current_lifecycle == "growth":
                new_lifecycle = "peak"  # May have peaked
        
        # Check for dormancy
        if recent_momentum < 10:
            new_lifecycle = "dormant"
        
        await self.narratives.update_one(
            {"id": narrative_id},
            {
                "$set": {
                    "lifecycle": new_lifecycle,
                    "trend_direction": new_trend
                }
            }
        )
    
    async def _link_event_to_narrative(
        self,
        narrative_id: str,
        root_event_id: str,
        score: float
    ):
        """Create or update event-narrative link"""
        contribution = "core" if score > 0.7 else "related" if score > 0.4 else "peripheral"
        
        await self.narrative_events.update_one(
            {"narrative_id": narrative_id, "root_event_id": root_event_id},
            {
                "$set": {
                    "weight": score,
                    "contribution_type": contribution,
                    "added_at": datetime.now(timezone.utc)
                }
            },
            upsert=True
        )
    
    async def _update_narrative_stats(self, narrative_id: str):
        """Update narrative statistics"""
        event_count = await self.narrative_events.count_documents({
            "narrative_id": narrative_id
        })
        entity_count = await self.narrative_entities.count_documents({
            "narrative_id": narrative_id
        })
        
        await self.narratives.update_one(
            {"id": narrative_id},
            {
                "$set": {
                    "event_count": event_count,
                    "entity_count": entity_count,
                    "last_updated": datetime.now(timezone.utc)
                }
            }
        )
    
    def _calculate_narrative_match(
        self,
        narrative: Dict,
        entities: List[str],
        topics: List[str],
        title: str
    ) -> float:
        """Calculate how well an event matches a narrative"""
        score = 0.0
        
        narrative_topics = set(narrative.get("topics", []))
        narrative_keywords = set(narrative.get("keywords", []))
        
        # Topic overlap
        if topics:
            topic_overlap = len(set(topics) & narrative_topics)
            score += topic_overlap * 0.15
        
        # Keyword match in title
        title_lower = title.lower()
        for keyword in narrative_keywords:
            if keyword.lower() in title_lower:
                score += 0.2
        
        # Entity relevance (would need entity classification)
        # For now, basic matching
        for entity in entities:
            if entity.lower() in str(narrative_keywords).lower():
                score += 0.1
        
        return min(score, 1.0)
    
    @staticmethod
    def _generate_id(prefix: str) -> str:
        """Generate unique ID with prefix"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        hash_part = hashlib.md5(timestamp.encode()).hexdigest()[:8]
        return f"{prefix}_{hash_part}"


# Import for timedelta
from datetime import timedelta
