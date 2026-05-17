"""
Data Fusion Models
==================

Модели для объединения данных:
- FusedEntity: объединенная сущность
- FusedEvent: объединенное событие
- FusedSignal: объединенный сигнал
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class EventType(str, Enum):
    """Типы событий"""
    FUNDING = "funding_event"
    UNLOCK = "unlock_event"
    LISTING = "listing_event"
    ICO = "ico_event"
    ACTIVITY = "activity_event"
    NEWS = "news_event"
    MARKET_SIGNAL = "market_signal"
    ONCHAIN_SIGNAL = "onchain_signal"


class SignalType(str, Enum):
    """Типы сигналов"""
    PUMP_SETUP = "pump_setup"
    DUMP_RISK = "dump_risk"
    UNLOCK_RISK = "unlock_risk"
    SMART_MONEY_ENTRY = "smart_money_entry"
    FUNDING_STRESS = "funding_stress"
    OI_SHOCK = "oi_shock"
    ROTATION_SIGNAL = "rotation_signal"
    NARRATIVE_BREAKOUT = "narrative_breakout"


class FusedEntity(BaseModel):
    """Объединенная сущность из разных источников"""
    id: str = Field(..., description="Canonical entity ID")
    entity_type: str = Field(..., description="project, investor, person, fund")
    canonical_id: str = Field(..., description="Normalized canonical ID")
    name: str = Field(..., description="Primary name")
    symbol: Optional[str] = None
    source_ids: List[str] = Field(default_factory=list, description="IDs from different sources")
    sources: List[str] = Field(default_factory=list, description="Source names")
    aliases: List[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0, le=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class FusedEvent(BaseModel):
    """Объединенное событие из разных источников"""
    id: str = Field(..., description="Fused event ID")
    event_type: EventType = Field(..., description="Type of event")
    canonical_entity_id: str = Field(..., description="Linked entity ID")
    title: str = Field(..., description="Event title")
    description: Optional[str] = None
    date: datetime = Field(..., description="Event date")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Source events")
    confidence: float = Field(default=1.0, ge=0, le=1)
    impact_score: int = Field(default=50, ge=0, le=100)
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event-specific data")
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class FusedSignal(BaseModel):
    """Объединенный market signal"""
    id: str = Field(..., description="Signal ID")
    signal_type: SignalType = Field(..., description="Type of signal")
    asset_id: str = Field(..., description="Asset/entity ID")
    symbol: str = Field(..., description="Asset symbol")
    score: int = Field(..., ge=0, le=100, description="Signal strength 0-100")
    components: Dict[str, float] = Field(default_factory=dict, description="Signal components")
    date: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FusionCandidate(BaseModel):
    """Кандидат на слияние"""
    source_a: Dict[str, Any]
    source_b: Dict[str, Any]
    similarity_score: float = Field(ge=0, le=1)
    match_reasons: List[str] = Field(default_factory=list)
    suggested_action: str = Field(default="review", description="merge, probable, separate")


class FusionRule(BaseModel):
    """Правило слияния"""
    id: str
    event_type: str
    conditions: Dict[str, Any] = Field(default_factory=dict)
    weights: Dict[str, float] = Field(default_factory=dict)
    threshold: float = Field(default=0.75)
    enabled: bool = True
