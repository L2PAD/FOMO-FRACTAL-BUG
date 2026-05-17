"""
News Intelligence Data Models
=============================

Core data structures for the News Intelligence Layer.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class SourceType(str, Enum):
    RSS = "rss"
    API = "api"
    HTML = "html"


class SourceTier(str, Enum):
    A = "A"  # Fastest, most reliable
    B = "B"  # Good quality
    C = "C"  # Supplementary


class EventStatus(str, Enum):
    CANDIDATE = "candidate"
    DEVELOPING = "developing"
    CONFIRMED = "confirmed"
    OFFICIAL = "official"
    RUMOR = "rumor"
    SUPERSEDED = "superseded"
    STALE = "stale"


class EventType(str, Enum):
    REGULATION = "regulation"
    LISTING = "listing"
    DELISTING = "delisting"
    FUNDING = "funding"
    PARTNERSHIP = "partnership"
    ACQUISITION = "acquisition"
    HACK = "hack"
    EXPLOIT = "exploit"
    LAUNCH = "launch"
    AIRDROP = "airdrop"
    UNLOCK = "unlock"
    GOVERNANCE = "governance"
    PRODUCT_UPDATE = "product_update"
    ADOPTION = "adoption"
    MARKET_MOVE = "market_move"
    LEGAL = "legal"
    SECURITY_INCIDENT = "security_incident"
    MACRO = "macro"
    NEWS = "news"


# ═══════════════════════════════════════════════════════════════
# NEWS SOURCE MODEL
# ═══════════════════════════════════════════════════════════════

class NewsSource(BaseModel):
    """Configuration for a news source."""
    id: str
    name: str
    domain: str
    source_type: SourceType
    tier: SourceTier
    language: str = "en"
    region: Optional[str] = None
    rss_url: Optional[str] = None
    api_url: Optional[str] = None
    html_url: Optional[str] = None
    parser_strategy: str = "default"
    refresh_interval_sec: int = 600
    source_weight: float = 1.0
    is_official: bool = False
    is_active: bool = True
    last_fetch: Optional[datetime] = None
    error_count: int = 0


# ═══════════════════════════════════════════════════════════════
# RAW ARTICLE MODEL
# ═══════════════════════════════════════════════════════════════

class RawArticle(BaseModel):
    """Raw article as fetched from source."""
    id: str
    source_id: str
    source_name: str
    url: str
    external_id: Optional[str] = None
    title_raw: str
    content_raw: Optional[str] = None
    html_raw: Optional[str] = None
    author_raw: Optional[str] = None
    published_at_raw: Optional[str] = None
    image_url_raw: Optional[str] = None
    language_detected: str = "en"
    tags_raw: List[str] = Field(default_factory=list)
    fetched_at: datetime
    content_hash: str
    status: str = "pending"


# ═══════════════════════════════════════════════════════════════
# NORMALIZED ARTICLE MODEL
# ═══════════════════════════════════════════════════════════════

class NormalizedArticle(BaseModel):
    """Cleaned and standardized article."""
    id: str
    raw_article_id: str
    source_id: str
    source_name: str
    canonical_url: str
    title: str
    clean_text: str
    summary: Optional[str] = None
    language: str = "en"
    published_at: Optional[datetime] = None
    author: Optional[str] = None
    image_url: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    
    # Extracted data
    entities: List[str] = Field(default_factory=list)
    assets: List[str] = Field(default_factory=list)
    organizations: List[str] = Field(default_factory=list)
    persons: List[str] = Field(default_factory=list)
    regions: List[str] = Field(default_factory=list)
    amounts: List[str] = Field(default_factory=list)
    event_hints: List[str] = Field(default_factory=list)
    
    # Vector
    embedding: Optional[List[float]] = None
    content_hash: str
    
    # Metadata
    created_at: datetime
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# NEWS EVENT MODEL
# ═══════════════════════════════════════════════════════════════

class NewsEvent(BaseModel):
    """Clustered news event from multiple sources."""
    id: str
    cluster_key: str
    status: EventStatus = EventStatus.CANDIDATE
    event_type: EventType = EventType.NEWS
    
    # Content
    title_seed: str
    title_en: Optional[str] = None
    title_ru: Optional[str] = None
    summary_en: Optional[str] = None
    summary_ru: Optional[str] = None
    story_en: Optional[str] = None
    story_ru: Optional[str] = None
    ai_view_en: Optional[str] = None
    ai_view_ru: Optional[str] = None
    
    # Entities
    primary_assets: List[str] = Field(default_factory=list)
    primary_entities: List[str] = Field(default_factory=list)
    organizations: List[str] = Field(default_factory=list)
    persons: List[str] = Field(default_factory=list)
    regions: List[str] = Field(default_factory=list)
    
    # Sources
    source_count: int = 1
    article_count: int = 1
    article_ids: List[str] = Field(default_factory=list)
    primary_source_id: Optional[str] = None
    
    # Scores
    confidence_score: float = 0.0
    importance_score: float = 0.0
    freshness_score: float = 0.0
    feed_score: float = 0.0
    fomo_score: Optional[float] = None
    
    # Facts
    extracted_facts: List[Dict[str, Any]] = Field(default_factory=list)
    fact_conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Cover
    cover_image_url: Optional[str] = None
    cover_image_prompt: Optional[str] = None
    
    # Timestamps
    first_seen_at: datetime
    last_seen_at: datetime
    published_at: Optional[datetime] = None
    
    # Centroid for clustering
    centroid_embedding: Optional[List[float]] = None


# ═══════════════════════════════════════════════════════════════
# EVENT ARTICLE LINK MODEL
# ═══════════════════════════════════════════════════════════════

class EventArticleLink(BaseModel):
    """Link between event and article with relevance score."""
    id: str
    event_id: str
    article_id: str
    relevance_score: float = 1.0
    is_primary_source: bool = False
    factual_weight: float = 1.0
    created_at: datetime


# ═══════════════════════════════════════════════════════════════
# FACT CLAIM MODEL
# ═══════════════════════════════════════════════════════════════

class FactClaim(BaseModel):
    """Individual fact claim from a source."""
    id: str
    event_id: str
    article_id: str
    field_name: str
    field_value: str
    source_id: str
    confidence: float = 0.8
    claim_type: str = "reported"  # confirmed, reported, rumored, inferred


# ═══════════════════════════════════════════════════════════════
# API RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════

class EventFeedItem(BaseModel):
    """Event item for feed API response."""
    id: str
    headline: str
    summary: str
    event_type: str
    status: str
    confidence: float
    source_count: int
    article_count: int
    assets: List[str]
    entities: List[str]
    regions: List[str]
    cover_image: Optional[str] = None
    published_at: Optional[str] = None
    first_seen_at: str
    feed_score: float
    fomo_score: Optional[float] = None


class EventDetail(BaseModel):
    """Detailed event for API response."""
    id: str
    headline: str
    summary: str
    story: Optional[str] = None
    ai_view: Optional[str] = None
    event_type: str
    status: str
    confidence: float
    importance: float
    source_count: int
    article_count: int
    assets: List[str]
    entities: List[str]
    organizations: List[str]
    persons: List[str]
    regions: List[str]
    facts: List[Dict[str, Any]]
    conflicts: List[Dict[str, Any]]
    sources: List[Dict[str, Any]]
    cover_image: Optional[str] = None
    published_at: Optional[str] = None
    first_seen_at: str
    last_seen_at: str
