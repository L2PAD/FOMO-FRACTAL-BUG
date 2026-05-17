"""
Discovery Engine Data Models
============================
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class EndpointStatus(str, Enum):
    """Endpoint operational status"""
    DISCOVERED = "discovered"
    VALIDATING = "validating"
    ACTIVE = "active"
    DEGRADED = "degraded"
    DEAD = "dead"
    BLOCKED = "blocked"


class CapabilityType(str, Enum):
    """Auto-detected capability types"""
    MARKET_DATA = "market_data"
    DEFI_DATA = "defi_data"
    DEX_DATA = "dex_data"
    FUNDING = "funding"
    NEWS = "news"
    DERIVATIVES = "derivatives"
    ONCHAIN = "onchain"
    ACTIVITIES = "activities"
    PROTOCOL = "protocol"
    UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════════════
# DISCOVERED ENDPOINT
# ═══════════════════════════════════════════════════════════════

class DiscoveredEndpoint(BaseModel):
    """
    API endpoint discovered through network capture.
    """
    id: str = Field(..., description="Unique endpoint ID")
    
    # Discovery info
    domain: str = Field(..., description="Source domain")
    url: str = Field(..., description="Full endpoint URL")
    path: str = Field(..., description="API path")
    method: str = Field(default="GET")
    
    # Detection
    discovery_method: str = Field(default="network_capture", description="How it was found")
    detected_patterns: List[str] = Field(default=[], description="Patterns found: /api/, /v1/, etc.")
    
    # Schema
    response_schema: Optional[Dict] = Field(None, description="Detected response schema")
    capabilities: List[CapabilityType] = Field(default=[])
    
    # Health
    status: EndpointStatus = Field(default=EndpointStatus.DISCOVERED)
    latency_ms: Optional[float] = None
    success_rate: float = Field(default=0.0)
    
    # Scoring
    stability_score: float = Field(default=0.0, description="0-1 stability score")
    data_quality_score: float = Field(default=0.0, description="0-1 data quality")
    overall_score: float = Field(default=0.0, description="Combined score")
    
    # Auth detection
    requires_auth: bool = Field(default=False)
    auth_type: Optional[str] = None
    auth_header: Optional[str] = None
    
    # Provider link
    provider_id: Optional[str] = Field(None, description="Linked provider if registered")
    
    # Timestamps
    discovered_at: datetime = Field(default_factory=lambda: datetime.now())
    last_checked: Optional[datetime] = None
    last_success: Optional[datetime] = None


class EndpointCreate(BaseModel):
    """Schema for manual endpoint creation"""
    domain: str
    url: str
    path: str
    method: str = "GET"
    requires_auth: bool = False


# ═══════════════════════════════════════════════════════════════
# ENDPOINT SCHEMA
# ═══════════════════════════════════════════════════════════════

class EndpointSchema(BaseModel):
    """
    Detected schema for an endpoint response.
    """
    endpoint_id: str
    
    # Schema info
    content_type: str = Field(default="application/json")
    is_array: bool = Field(default=False)
    fields: Dict[str, str] = Field(default={}, description="field_name: field_type")
    sample_data: Optional[Dict] = None
    
    # Capability indicators
    has_price: bool = False
    has_volume: bool = False
    has_tvl: bool = False
    has_timestamp: bool = False
    has_symbol: bool = False
    
    # Auto-detected capability
    detected_capability: CapabilityType = CapabilityType.UNKNOWN
    confidence: float = Field(default=0.0, description="Detection confidence 0-1")


# ═══════════════════════════════════════════════════════════════
# DISCOVERY JOB
# ═══════════════════════════════════════════════════════════════

class DiscoveryJob(BaseModel):
    """
    Discovery job for a domain.
    """
    id: str = Field(..., description="Job ID")
    domain: str = Field(..., description="Target domain")
    
    # Job config
    scan_depth: int = Field(default=3, description="How deep to crawl")
    network_capture: bool = Field(default=True, description="Enable network interception")
    check_subdomains: List[str] = Field(default=["api", "docs", "developer"])
    
    # Status
    status: str = Field(default="pending")
    progress: float = Field(default=0.0)
    
    # Results
    endpoints_found: int = Field(default=0)
    apis_detected: int = Field(default=0)
    errors: List[str] = Field(default=[])
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class DiscoveryJobCreate(BaseModel):
    """Schema for creating discovery job"""
    domain: str
    scan_depth: int = 3
    network_capture: bool = True
    check_subdomains: List[str] = ["api", "docs", "developer"]


# ═══════════════════════════════════════════════════════════════
# SEED DOMAINS
# ═══════════════════════════════════════════════════════════════

SEED_DOMAINS = {
    "market_data": [
        "coingecko.com",
        "coinmarketcap.com",
        "messari.io",
    ],
    "defi": [
        "defillama.com",
        "tokenterminal.com",
    ],
    "dex": [
        "dexscreener.com",
        "geckoterminal.com",
        "dextools.io",
    ],
    "derivatives": [
        "coinglass.com",
    ],
    "intel": [
        "cryptorank.io",
        "dropstab.com",
        "rootdata.com",
    ],
    "news": [
        "incrypted.com",
        "cointelegraph.com",
        "decrypt.co",
        "theblock.co",
        "blockworks.co",
        "coindesk.com",
    ],
    "onchain": [
        "artemis.xyz",
        "dune.com",
    ]
}
