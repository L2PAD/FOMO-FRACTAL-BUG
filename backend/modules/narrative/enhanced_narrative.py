"""
Enhanced Narrative Layer with Lifecycle Dynamics

Additions per architecture audit:
1. lifecycle_state: emerging → growing → peak → declining → dead
2. momentum_velocity: Rate of momentum change
3. momentum_acceleration: Acceleration of momentum change
4. narrative_entities: Direct links to entities

This allows the system to understand:
- "Narrative is just starting" vs "Narrative is popular"
- Early detection of emerging themes
- Prediction of narrative lifecycle
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class DetailedLifecycleState(str, Enum):
    """
    5-stage lifecycle model (more granular than original)
    
    emerging  → Just appearing, few signals
    growing   → Gaining momentum, increasing coverage
    peak      → Maximum attention, saturation
    declining → Losing momentum, less coverage
    dead      → No longer active, historical only
    """
    EMERGING = "emerging"
    GROWING = "growing"
    PEAK = "peak"
    DECLINING = "declining"
    DEAD = "dead"


class EnhancedNarrative(BaseModel):
    """
    Enhanced Narrative model with lifecycle dynamics
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
    
    # ═══════════════════════════════════════════════════════════════
    # NEW: Enhanced Lifecycle Model
    # ═══════════════════════════════════════════════════════════════
    
    lifecycle_state: DetailedLifecycleState = Field(
        DetailedLifecycleState.EMERGING,
        description="Current lifecycle stage"
    )
    
    momentum_velocity: float = Field(
        0.0, 
        description="Rate of momentum change (points per day)"
    )
    
    momentum_acceleration: float = Field(
        0.0,
        description="Acceleration of momentum change (velocity change per day)"
    )
    
    # Lifecycle timestamps
    emerged_at: Optional[datetime] = Field(None, description="When first detected")
    growth_started_at: Optional[datetime] = Field(None, description="When growth phase began")
    peak_reached_at: Optional[datetime] = Field(None, description="When peak was reached")
    decline_started_at: Optional[datetime] = Field(None, description="When decline began")
    declared_dead_at: Optional[datetime] = Field(None, description="When declared inactive")
    
    # Lifecycle predictions
    predicted_peak_date: Optional[datetime] = Field(None, description="AI-predicted peak")
    days_until_peak: Optional[int] = Field(None, description="Estimated days to peak")
    lifecycle_confidence: float = Field(0.5, ge=0, le=1, description="Confidence in lifecycle prediction")
    
    # ═══════════════════════════════════════════════════════════════
    
    # Stats
    event_count: int = Field(0)
    entity_count: int = Field(0)
    update_count_24h: int = Field(0)
    sentiment_avg: float = Field(0.0, ge=-1, le=1)
    
    # Volume correlation
    volume_correlation: Optional[float] = Field(None, ge=-1, le=1)
    price_impact_avg: Optional[float] = None
    
    # Timeline
    first_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    peak_date: Optional[datetime] = None
    
    class Config:
        use_enum_values = True


class NarrativeEntityLink(BaseModel):
    """
    Direct link between narrative and entity
    
    Example:
    Narrative: "AI x Crypto"
    entities:
      - TAO (relevance: 0.95, is_key_player: true)
      - FET (relevance: 0.90, is_key_player: true)
      - RNDR (relevance: 0.85)
      - NVIDIA (relevance: 0.80, entity_type: external)
    """
    narrative_id: str
    entity_id: str
    entity_type: str = Field(..., description="project/fund/person/exchange/external")
    entity_symbol: Optional[str] = None  # For quick lookups
    
    # Relevance
    relevance_score: float = Field(0.5, ge=0, le=1)
    is_key_player: bool = Field(False, description="Core entity for this narrative")
    contribution_type: str = Field("related", description="core/related/peripheral")
    
    # Metrics
    mention_count: int = Field(0, description="How often mentioned in narrative context")
    sentiment_in_narrative: float = Field(0.0, ge=-1, le=1)
    
    # Timeline
    first_linked: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_mentioned: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NarrativeMomentumSnapshot(BaseModel):
    """
    Time-series momentum data for tracking narrative dynamics
    """
    narrative_id: str
    timestamp: datetime
    
    # Current values
    momentum_score: float
    velocity: float
    acceleration: float
    
    # Activity metrics
    event_count_24h: int
    entity_mentions_24h: int
    source_count_24h: int
    
    # Sentiment
    sentiment_avg: float
    sentiment_std: float = 0.0  # Standard deviation
    
    # Market correlation
    volume_correlation: Optional[float] = None
    price_impact: Optional[float] = None


class LifecycleCalculator:
    """
    Calculate lifecycle dynamics for narratives
    """
    
    @staticmethod
    def calculate_velocity(
        current_momentum: float,
        previous_momentum: float,
        hours_elapsed: float = 24
    ) -> float:
        """
        Calculate momentum velocity (rate of change)
        
        Returns points per day
        """
        if hours_elapsed <= 0:
            return 0.0
        
        daily_factor = 24 / hours_elapsed
        return (current_momentum - previous_momentum) * daily_factor
    
    @staticmethod
    def calculate_acceleration(
        current_velocity: float,
        previous_velocity: float,
        hours_elapsed: float = 24
    ) -> float:
        """
        Calculate momentum acceleration (rate of velocity change)
        
        Returns velocity change per day
        """
        if hours_elapsed <= 0:
            return 0.0
        
        daily_factor = 24 / hours_elapsed
        return (current_velocity - previous_velocity) * daily_factor
    
    @staticmethod
    def determine_lifecycle_state(
        momentum: float,
        velocity: float,
        acceleration: float,
        days_active: int
    ) -> DetailedLifecycleState:
        """
        Determine lifecycle state based on dynamics
        
        Logic:
        - emerging: low momentum, positive velocity, new
        - growing: increasing momentum and velocity
        - peak: high momentum, near-zero velocity, negative acceleration
        - declining: negative velocity, negative acceleration
        - dead: very low momentum, stable negative or zero velocity
        """
        # Dead check
        if momentum < 5 and days_active > 30:
            return DetailedLifecycleState.DEAD
        
        # Emerging check
        if days_active < 7 and momentum < 30:
            return DetailedLifecycleState.EMERGING
        
        # Peak detection
        if momentum > 60 and abs(velocity) < 3 and acceleration < -1:
            return DetailedLifecycleState.PEAK
        
        # Growing vs Declining
        if velocity > 2:
            return DetailedLifecycleState.GROWING
        elif velocity < -2:
            return DetailedLifecycleState.DECLINING
        
        # Default based on momentum level
        if momentum > 50:
            return DetailedLifecycleState.PEAK
        elif momentum > 20:
            return DetailedLifecycleState.GROWING
        else:
            return DetailedLifecycleState.EMERGING
    
    @staticmethod
    def predict_peak_date(
        current_momentum: float,
        velocity: float,
        acceleration: float
    ) -> Optional[datetime]:
        """
        Predict when narrative will reach peak
        
        Uses simple physics model:
        - Peak is when velocity = 0
        - Time to peak = -velocity / acceleration (if acceleration < 0)
        """
        if velocity <= 0:
            # Already at or past peak
            return None
        
        if acceleration >= 0:
            # Still accelerating, can't predict peak
            return None
        
        # Days until velocity = 0
        days_to_peak = -velocity / acceleration
        
        if days_to_peak > 90:
            # Too far in future, unreliable
            return None
        
        return datetime.now(timezone.utc) + timedelta(days=days_to_peak)


class EnhancedNarrativeService:
    """
    Enhanced narrative service with lifecycle tracking
    """
    
    def __init__(self, db):
        self.db = db
        self.narratives = db.narratives
        self.narrative_entities = db.narrative_entities
        self.momentum_snapshots = db.narrative_momentum_snapshots
    
    async def update_lifecycle_metrics(self, narrative_id: str):
        """
        Update lifecycle metrics for a narrative
        """
        # Get current narrative
        narrative = await self.narratives.find_one({"id": narrative_id})
        if not narrative:
            return
        
        current_momentum = narrative.get("momentum_score", 0)
        
        # Get previous snapshot (24h ago)
        prev_snapshot = await self.momentum_snapshots.find_one(
            {
                "narrative_id": narrative_id,
                "timestamp": {"$lte": datetime.now(timezone.utc) - timedelta(hours=24)}
            },
            sort=[("timestamp", -1)]
        )
        
        previous_momentum = prev_snapshot.get("momentum_score", current_momentum) if prev_snapshot else current_momentum
        previous_velocity = prev_snapshot.get("velocity", 0) if prev_snapshot else 0
        
        # Calculate new metrics
        velocity = LifecycleCalculator.calculate_velocity(
            current_momentum, previous_momentum
        )
        acceleration = LifecycleCalculator.calculate_acceleration(
            velocity, previous_velocity
        )
        
        # Determine lifecycle state
        first_seen = narrative.get("first_seen", datetime.now(timezone.utc))
        days_active = (datetime.now(timezone.utc) - first_seen).days
        
        lifecycle_state = LifecycleCalculator.determine_lifecycle_state(
            current_momentum, velocity, acceleration, days_active
        )
        
        # Predict peak
        predicted_peak = LifecycleCalculator.predict_peak_date(
            current_momentum, velocity, acceleration
        )
        
        days_until_peak = None
        if predicted_peak:
            days_until_peak = (predicted_peak - datetime.now(timezone.utc)).days
        
        # Update narrative
        update_fields = {
            "momentum_velocity": round(velocity, 2),
            "momentum_acceleration": round(acceleration, 2),
            "lifecycle_state": lifecycle_state.value,
            "predicted_peak_date": predicted_peak,
            "days_until_peak": days_until_peak,
            "last_updated": datetime.now(timezone.utc)
        }
        
        # Track lifecycle transitions
        current_state = narrative.get("lifecycle_state", "emerging")
        if current_state != lifecycle_state.value:
            if lifecycle_state == DetailedLifecycleState.GROWING:
                update_fields["growth_started_at"] = datetime.now(timezone.utc)
            elif lifecycle_state == DetailedLifecycleState.PEAK:
                update_fields["peak_reached_at"] = datetime.now(timezone.utc)
            elif lifecycle_state == DetailedLifecycleState.DECLINING:
                update_fields["decline_started_at"] = datetime.now(timezone.utc)
            elif lifecycle_state == DetailedLifecycleState.DEAD:
                update_fields["declared_dead_at"] = datetime.now(timezone.utc)
        
        await self.narratives.update_one(
            {"id": narrative_id},
            {"$set": update_fields}
        )
        
        # Save snapshot
        snapshot = NarrativeMomentumSnapshot(
            narrative_id=narrative_id,
            timestamp=datetime.now(timezone.utc),
            momentum_score=current_momentum,
            velocity=velocity,
            acceleration=acceleration,
            event_count_24h=narrative.get("update_count_24h", 0),
            entity_mentions_24h=narrative.get("entity_count", 0),
            source_count_24h=0,  # Would need to calculate
            sentiment_avg=narrative.get("sentiment_avg", 0)
        )
        
        await self.momentum_snapshots.insert_one(snapshot.dict())
    
    async def link_entity_to_narrative(
        self,
        narrative_id: str,
        entity_id: str,
        entity_type: str,
        entity_symbol: str = None,
        relevance_score: float = 0.5,
        is_key_player: bool = False
    ):
        """
        Create or update entity-narrative link
        """
        contribution = "core" if is_key_player else "related" if relevance_score > 0.5 else "peripheral"
        
        link = NarrativeEntityLink(
            narrative_id=narrative_id,
            entity_id=entity_id,
            entity_type=entity_type,
            entity_symbol=entity_symbol,
            relevance_score=relevance_score,
            is_key_player=is_key_player,
            contribution_type=contribution
        )
        
        await self.narrative_entities.update_one(
            {"narrative_id": narrative_id, "entity_id": entity_id},
            {
                "$set": link.dict(),
                "$inc": {"mention_count": 1}
            },
            upsert=True
        )
    
    async def get_narrative_cluster(
        self,
        narrative_id: str
    ) -> Dict[str, List[Dict]]:
        """
        Get entity cluster for a narrative
        
        Returns:
        {
            "projects": [...],
            "funds": [...],
            "persons": [...],
            "external": [...]
        }
        """
        cursor = self.narrative_entities.find(
            {"narrative_id": narrative_id}
        ).sort("relevance_score", -1)
        
        links = await cursor.to_list(length=100)
        
        cluster = {
            "projects": [],
            "funds": [],
            "persons": [],
            "exchanges": [],
            "external": []
        }
        
        for link in links:
            entity_type = link.get("entity_type", "external")
            bucket = cluster.get(entity_type + "s", cluster["external"])
            bucket.append({
                "entity_id": link["entity_id"],
                "symbol": link.get("entity_symbol"),
                "relevance": link.get("relevance_score", 0),
                "is_key_player": link.get("is_key_player", False),
                "mentions": link.get("mention_count", 0)
            })
        
        return cluster
    
    async def get_emerging_narratives(self, limit: int = 10) -> List[Dict]:
        """
        Get narratives in emerging state with positive velocity
        
        These are the "next big things" - early detection
        """
        cursor = self.narratives.find({
            "lifecycle_state": "emerging",
            "momentum_velocity": {"$gt": 0}
        }).sort("momentum_velocity", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_peaking_narratives(self, limit: int = 10) -> List[Dict]:
        """
        Get narratives currently at peak
        """
        cursor = self.narratives.find({
            "lifecycle_state": "peak"
        }).sort("momentum_score", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
