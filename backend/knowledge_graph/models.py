"""
Knowledge Graph Layer - Data Models

Collections:
- graph_nodes: Entity nodes in the graph
- graph_edges: Relationships between nodes
- graph_edge_types: Dictionary of valid edge types
- graph_snapshots: Graph rebuild history
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import uuid


def generate_id() -> str:
    return str(uuid.uuid4())[:12]


# =============================================================================
# Node Types
# =============================================================================

NODE_TYPES = [
    "project",
    "token",
    "asset",
    "fund",
    "person",
    "exchange",
    "activity",
    "funding_round",
    "unlock_event",
    "ico_sale",
]


# =============================================================================
# Edge Types Dictionary
# =============================================================================

# G3: Graph Context Layer - Relation Scopes
# Maps relation_type to scope for context filtering
RELATION_SCOPE = {
    # Investment scope
    "invested_in": "investment",
    "investor": "investment",
    "led_round": "investment",
    "has_funding_round": "investment",
    
    # Founder scope
    "founded": "founder",
    "founder": "founder",
    "co_founded_by": "founder",
    
    # Ecosystem scope
    "built_on": "ecosystem",
    "built_by": "ecosystem",
    "ecosystem": "ecosystem",
    "has_token": "ecosystem",
    "belongs_to_project": "ecosystem",
    
    # Partnership scope
    "partner": "partnership",
    "partnership": "partnership",
    "coinvested_with": "partnership",
    "coinvested": "partnership",
    
    # Market scope
    "listed_on": "market",
    "listing": "market",
    "traded_on": "market",
    "has_pair": "market",
    
    # Event scope
    "event_linked": "event",
    "event": "event",
    "has_activity": "event",
    "has_unlock": "event",
    
    # Mention scope (lowest priority)
    "mention": "mention",
    "mentioned": "mention",
    "related_to": "mention",
    "related": "mention",
}

EDGE_TYPES = {
    # Direct - Funds / Persons / Projects
    "invested_in": {"from": "fund", "to": "project", "directed": True, "derived": False},
    "led_round": {"from": "fund", "to": "funding_round", "directed": True, "derived": False},
    "works_at": {"from": "person", "to": "fund", "directed": True, "derived": False},
    "worked_at": {"from": "person", "to": "fund", "directed": True, "derived": False},
    "founded": {"from": "person", "to": "project", "directed": True, "derived": False},
    "advisor_of": {"from": "person", "to": "project", "directed": True, "derived": False},
    "partner_at": {"from": "person", "to": "fund", "directed": True, "derived": False},
    
    # Direct - Projects / Tokens / Assets
    "has_token": {"from": "project", "to": "token", "directed": True, "derived": False},
    "mapped_to_asset": {"from": "token", "to": "asset", "directed": True, "derived": False},
    "belongs_to_project": {"from": "asset", "to": "project", "directed": True, "derived": False},
    
    # Direct - Market / Exchanges
    "traded_on": {"from": "asset", "to": "exchange", "directed": True, "derived": False},
    "listed_on": {"from": "project", "to": "exchange", "directed": True, "derived": False},
    "has_pair": {"from": "exchange", "to": "asset", "directed": True, "derived": False},
    
    # Direct - Intel / Events
    "has_activity": {"from": "project", "to": "activity", "directed": True, "derived": False},
    "has_unlock": {"from": "project", "to": "unlock_event", "directed": True, "derived": False},
    "has_funding_round": {"from": "project", "to": "funding_round", "directed": True, "derived": False},
    "has_ico": {"from": "project", "to": "ico_sale", "directed": True, "derived": False},
    
    # Derived - Network relations
    "coinvested_with": {"from": "fund", "to": "fund", "directed": False, "derived": True},
    "worked_together": {"from": "person", "to": "person", "directed": False, "derived": True},
    "shares_investor_with": {"from": "project", "to": "project", "directed": False, "derived": True},
    "shares_founder_with": {"from": "project", "to": "project", "directed": False, "derived": True},
    "shares_ecosystem_with": {"from": "project", "to": "project", "directed": False, "derived": True},
    "related_to": {"from": "*", "to": "*", "directed": False, "derived": True},
}


# =============================================================================
# Pydantic Models
# =============================================================================

class GraphNode(BaseModel):
    """Graph node representing an entity"""
    id: str = Field(default_factory=generate_id)
    entity_type: str  # project, token, asset, fund, person, exchange, etc.
    entity_id: str    # Reference to source entity
    label: str        # Display name
    slug: Optional[str] = None
    status: Optional[str] = "active"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def node_key(self) -> str:
        """Canonical node key: entity_type:entity_id"""
        return f"{self.entity_type}:{self.entity_id}"


class GraphEdge(BaseModel):
    """Graph edge representing a relationship"""
    id: str = Field(default_factory=generate_id)
    from_node_id: str
    to_node_id: str
    relation_type: str      # invested_in, works_at, traded_on, etc.
    weight: float = 1.0
    directionality: str = "directed"  # directed / undirected
    source_type: str = "direct"       # direct / derived / inferred
    source_ref: Optional[str] = None  # Reference to source record
    confidence: Optional[float] = None
    # G3: Graph Context Layer fields
    scope: Optional[str] = None       # investment, ecosystem, partnership, listing, mention
    context: Optional[str] = None     # Additional context (e.g., "Series A", "Strategic Partner")
    event_timestamp: Optional[datetime] = None  # When the relationship was established
    data_source: Optional[str] = None  # crunchbase, coingecko, manual, parser, etc.
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def edge_key(self) -> str:
        """Canonical edge key for deduplication"""
        return f"{self.from_node_id}|{self.to_node_id}|{self.relation_type}"


class GraphEdgeType(BaseModel):
    """Dictionary entry for valid edge types"""
    id: str = Field(default_factory=generate_id)
    relation_type: str
    from_entity_type: str
    to_entity_type: str
    directed: bool = True
    symmetric: bool = False
    derived: bool = False
    description: Optional[str] = None
    metadata_schema: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GraphSnapshot(BaseModel):
    """Graph rebuild snapshot for versioning"""
    id: str = Field(default_factory=generate_id)
    snapshot_type: str  # full_rebuild, incremental, derived_only
    node_count: int = 0
    edge_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# API Response Models
# =============================================================================

class GraphNodeResponse(BaseModel):
    """API response for a single node"""
    id: str
    entity_type: str
    entity_id: str
    label: str
    slug: Optional[str] = None
    status: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    neighbor_count: int = 0
    edge_count: int = 0


class GraphEdgeResponse(BaseModel):
    """API response for a single edge"""
    id: str
    source: str  # node_key format for frontend
    target: str  # node_key format for frontend
    relation: str
    weight: float = 1.0
    source_type: str = "direct"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GraphNetworkResponse(BaseModel):
    """API response for graph network (for frontend)"""
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    stats: Dict[str, Any] = Field(default_factory=dict)


class GraphStatsResponse(BaseModel):
    """API response for graph statistics"""
    total_nodes: int = 0
    total_edges: int = 0
    nodes_by_type: Dict[str, int] = Field(default_factory=dict)
    edges_by_type: Dict[str, int] = Field(default_factory=dict)
    last_rebuild: Optional[datetime] = None
