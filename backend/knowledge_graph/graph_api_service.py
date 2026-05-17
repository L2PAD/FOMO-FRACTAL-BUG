"""
Graph API Service

Headless Graph Engine with:
- Ego graph (subgraph around entity)
- Expand node (click to expand)
- Path search (find connection)
- Related entities
- Search

Graph Explosion Protection:
- Edge budget (max 60 edges per query)
- Node budget (max 40 nodes per query)
- Relation whitelist
- Hub suppression
- Depth limits
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)
from pydantic import BaseModel, Field
from enum import Enum
import asyncio


# =============================================================================
# GRAPH API MODELS
# =============================================================================

class GraphUINode(BaseModel):
    """Node formatted for UI graph visualization"""
    id: str  # format: entity_type:entity_id
    label: str
    type: str  # project, fund, person, exchange, etc.
    size: int = Field(20, description="Visual size based on importance")
    importance: float = Field(0.5, ge=0, le=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GraphUIEdge(BaseModel):
    """Edge formatted for UI graph visualization"""
    id: str
    source: str  # node id
    target: str  # node id
    relation: str
    weight: float = Field(1.0, ge=0, le=1)
    is_derived: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EgoGraphResponse(BaseModel):
    """Response for ego graph query"""
    center: GraphUINode
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    meta: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# GRAPH EXPLOSION PROTECTION CONFIG
# =============================================================================

class GraphLimits:
    """Hard limits to prevent graph explosion"""
    DEFAULT_DEPTH = 1
    MAX_DEPTH = 3
    
    # Default mode limits
    DEFAULT_NODES = 40
    DEFAULT_EDGES = 60
    
    # Research mode limits
    MAX_NODES = 80
    MAX_EDGES = 120
    
    EXPAND_MAX_NODES = 20
    
    # Hub suppression: if degree > this, limit connections shown
    HUB_THRESHOLD = 100
    HUB_MAX_SHOWN = 25
    
    # Max relations per type in single query
    MAX_RELATIONS_PER_TYPE = {
        "invested_in": 10,
        "works_at": 8,
        "advisor_of": 6,
        "coinvested_with": 5,
        "traded_on": 8,
        "has_token": 10,
    }


# Relation priority for ranking (higher = more important)
RELATION_PRIORITY = {
    "founded": 10,
    "invested_in": 9,
    "led_round": 8,
    "works_at": 7,
    "worked_at": 6,
    "advisor_of": 6,
    "partner_at": 6,
    "has_token": 5,
    "mapped_to_asset": 5,
    "belongs_to_project": 4,
    "traded_on": 4,
    "listed_on": 4,
    "has_pair": 3,
    "has_activity": 3,
    "has_unlock": 3,
    "has_funding_round": 3,
    "has_ico": 2,
    # Derived - lower priority
    "coinvested_with": 2,
    "worked_together": 2,
    "shares_investor_with": 1,
    "shares_founder_with": 1,
    "shares_ecosystem_with": 1,
    "related_to": 0,
}

# Relations to show by default (whitelist)
DEFAULT_RELATION_WHITELIST = [
    "founded", "invested_in", "led_round", "works_at", "worked_at",
    "advisor_of", "partner_at", "has_token", "mapped_to_asset",
    "traded_on", "listed_on", "belongs_to_project"
]

# Derived relations - only shown in research mode
DERIVED_RELATIONS = [
    "coinvested_with", "worked_together", "shares_investor_with",
    "shares_founder_with", "shares_ecosystem_with", "related_to"
]


class GraphQueryService:
    """
    Service for graph queries with explosion protection
    """
    
    def __init__(self, db):
        self.db = db
        self.graph_nodes = db.graph_nodes
        self.graph_edges = db.graph_edges
        self.graph_payload_cache = db.graph_payload_cache
    
    async def ensure_indexes(self):
        """Create indexes for graph queries"""
        # Node indexes
        await self.graph_nodes.create_index("id", unique=True)
        await self.graph_nodes.create_index([("entity_type", 1), ("entity_id", 1)], unique=True)
        await self.graph_nodes.create_index("slug")
        await self.graph_nodes.create_index("label")
        
        # Edge indexes
        await self.graph_edges.create_index("id", unique=True)
        await self.graph_edges.create_index("from_node_id")
        await self.graph_edges.create_index("to_node_id")
        await self.graph_edges.create_index("relation_type")
        await self.graph_edges.create_index([("from_node_id", 1), ("relation_type", 1)])
        await self.graph_edges.create_index([("to_node_id", 1), ("relation_type", 1)])
        
        # Cache indexes
        await self.graph_payload_cache.create_index("cache_key", unique=True)
        await self.graph_payload_cache.create_index("generated_at")
    
    # =========================================================================
    # SEARCH
    # =========================================================================
    
    async def search(
        self,
        query: str,
        limit: int = 20
    ) -> List[Dict]:
        """
        Search for entities
        
        Returns: [{type, id, label}]
        """
        if not query or len(query) < 2:
            return []
        
        # Text search on label
        regex = {"$regex": query, "$options": "i"}
        
        cursor = self.graph_nodes.find({
            "$or": [
                {"label": regex},
                {"slug": regex},
                {"entity_id": regex}
            ]
        }).limit(limit)
        
        results = []
        async for node in cursor:
            results.append({
                "type": node.get("entity_type"),
                "id": node.get("entity_id"),
                "label": node.get("label"),
                "node_id": node.get("id")
            })
        
        return results
    
    # =========================================================================
    # EGO GRAPH
    # =========================================================================
    
    async def get_ego_graph(
        self,
        entity_type: str,
        entity_id: str,
        depth: int = 1,
        max_nodes: int = None,
        max_edges: int = None,
        include_derived: bool = False,
        use_cache: bool = True
    ) -> EgoGraphResponse:
        """
        Get ego graph (subgraph around an entity)
        
        This is the main UI graph endpoint.
        
        Cache priority (Layer 2 first):
        1. Redis hot cache (precomputed, fastest)
        2. Redis regular cache
        3. Mongo cache
        4. Compute fresh
        """
        logger.info(f"[GraphAPI] get_ego_graph called: {entity_type}/{entity_id}, use_cache={use_cache}")
        
        # Apply limits
        depth = min(depth, GraphLimits.MAX_DEPTH)
        max_nodes = min(max_nodes or GraphLimits.DEFAULT_NODES, GraphLimits.MAX_NODES)
        max_edges = min(max_edges or GraphLimits.DEFAULT_EDGES, GraphLimits.MAX_EDGES)
        
        # Check precomputed hot cache first (Layer 2 - fastest path)
        if use_cache:
            try:
                from modules.cache.graph_precompute import get_precompute_service
                precompute_service = get_precompute_service()
                if precompute_service:
                    precomputed = await precompute_service.get_precomputed(entity_type, entity_id)
                    if precomputed:
                        logger.info(f"[GraphAPI] Precomputed HIT: {entity_type}:{entity_id}")
                        return EgoGraphResponse(**precomputed)
            except Exception as e:
                logger.debug(f"[GraphAPI] Precompute check failed: {e}")
        
        # Check Redis cache (Layer 1)
        if use_cache:
            try:
                from modules.cache.graph_cache import GraphCache
                cached_redis = await GraphCache.get_ego(entity_type, entity_id)
                if cached_redis:
                    logger.info(f"[GraphAPI] Redis cache HIT: {entity_type}:{entity_id}")
                    return EgoGraphResponse(**cached_redis)
            except Exception:
                pass  # Redis unavailable, continue without it
        
        # Check Mongo cache
        cache_key = f"ego_{entity_type}_{entity_id}_d{depth}"
        if use_cache:
            cached = await self._get_cached_payload(cache_key)
            if cached:
                # Warm Redis cache for next request
                try:
                    from modules.cache.graph_cache import GraphCache
                    from modules.cache.redis_client import is_redis_available
                    if is_redis_available():
                        redis_set = await GraphCache.set_ego(entity_type, entity_id, cached)
                        logger.info(f"[GraphAPI] Redis warm from Mongo cache: {entity_type}:{entity_id} = {redis_set}")
                except Exception as e:
                    logger.error(f"[GraphAPI] Redis warm failed: {e}")
                return EgoGraphResponse(**cached)
        
        # Find center node
        center_node = await self._get_node(entity_type, entity_id)
        if not center_node:
            # Return empty response
            return EgoGraphResponse(
                center=GraphUINode(
                    id=f"{entity_type}:{entity_id}",
                    label=entity_id,
                    type=entity_type
                ),
                nodes=[],
                edges=[],
                meta={"error": "Node not found"}
            )
        
        # Build ego graph
        nodes = {center_node["id"]: center_node}
        edges = []
        
        # BFS to collect neighbors
        current_level = [center_node["id"]]
        
        for d in range(depth):
            next_level = []
            
            for node_id in current_level:
                # Get edges from this node
                neighbor_edges = await self._get_node_edges(
                    node_id,
                    include_derived=include_derived,
                    limit=GraphLimits.HUB_MAX_SHOWN  # Hub suppression
                )
                
                for edge in neighbor_edges:
                    # Get neighbor node
                    neighbor_id = edge["to_node_id"] if edge["from_node_id"] == node_id else edge["from_node_id"]
                    
                    if neighbor_id not in nodes:
                        neighbor = await self.graph_nodes.find_one({"id": neighbor_id})
                        if neighbor:
                            nodes[neighbor_id] = neighbor
                            next_level.append(neighbor_id)
                    
                    # Add edge
                    edge_key = f"{edge['from_node_id']}|{edge['to_node_id']}|{edge['relation_type']}"
                    if not any(e.get("_key") == edge_key for e in edges):
                        edge["_key"] = edge_key
                        edges.append(edge)
                    
                    # Check limits
                    if len(nodes) >= max_nodes or len(edges) >= max_edges:
                        break
                
                if len(nodes) >= max_nodes or len(edges) >= max_edges:
                    break
            
            current_level = next_level
            
            if len(nodes) >= max_nodes or len(edges) >= max_edges:
                break
        
        # Rank and trim
        ranked_edges = self._rank_edges(edges)[:max_edges]
        
        # Build response
        center_ui = self._node_to_ui(center_node)
        
        nodes_ui = [
            self._node_to_ui_dict(n) 
            for n in nodes.values()
        ]
        
        edges_ui = [
            self._edge_to_ui_dict(e, nodes)
            for e in ranked_edges
        ]
        
        response = EgoGraphResponse(
            center=center_ui,
            nodes=nodes_ui,
            edges=edges_ui,
            meta={
                "depth": depth,
                "node_count": len(nodes_ui),
                "edge_count": len(edges_ui),
                "center_id": f"{entity_type}:{entity_id}"
            }
        )
        
        # Cache result in Mongo
        if use_cache:
            await self._cache_payload(cache_key, response.dict())
            # Also warm Redis cache
            try:
                from modules.cache.graph_cache import GraphCache
                redis_result = await GraphCache.set_ego(entity_type, entity_id, response.dict())
                logger.debug(f"[GraphAPI] Redis cache set for {entity_type}:{entity_id}: {redis_result}")
            except Exception as e:
                logger.warning(f"[GraphAPI] Redis cache failed for {entity_type}:{entity_id}: {e}")
        
        return response
    
    # =========================================================================
    # EXPAND NODE
    # =========================================================================
    
    async def expand_node(
        self,
        node_id: str,
        relation_type: str = None,
        limit: int = None
    ) -> Dict:
        """
        Expand a node - get its neighbors for interactive graph
        
        Called when user clicks on a node
        """
        limit = min(limit or GraphLimits.EXPAND_MAX_NODES, GraphLimits.EXPAND_MAX_NODES)
        
        # Get edges
        query = {"$or": [
            {"from_node_id": node_id},
            {"to_node_id": node_id}
        ]}
        
        if relation_type:
            query["relation_type"] = relation_type
        
        cursor = self.graph_edges.find(query).limit(limit * 2)  # Get extra for ranking
        edges = await cursor.to_list(length=limit * 2)
        
        # Rank edges
        ranked_edges = self._rank_edges(edges)[:limit]
        
        # Get neighbor nodes
        neighbor_ids = set()
        for edge in ranked_edges:
            neighbor_ids.add(edge["from_node_id"])
            neighbor_ids.add(edge["to_node_id"])
        neighbor_ids.discard(node_id)
        
        nodes = {}
        for nid in neighbor_ids:
            node = await self.graph_nodes.find_one({"id": nid})
            if node:
                nodes[nid] = node
        
        return {
            "expanded_node": node_id,
            "nodes": [self._node_to_ui_dict(n) for n in nodes.values()],
            "edges": [self._edge_to_ui_dict(e, nodes) for e in ranked_edges],
            "new_node_count": len(nodes)
        }
    
    # =========================================================================
    # PATH SEARCH
    # =========================================================================
    
    async def find_path(
        self,
        from_type: str,
        from_id: str,
        to_type: str,
        to_id: str,
        max_depth: int = 4
    ) -> Dict:
        """
        Find path between two entities
        
        Uses BFS to find shortest path
        """
        max_depth = min(max_depth, GraphLimits.MAX_DEPTH + 1)
        
        # Get node IDs
        from_node = await self._get_node(from_type, from_id)
        to_node = await self._get_node(to_type, to_id)
        
        if not from_node or not to_node:
            return {"path": [], "found": False, "error": "Node not found"}
        
        from_node_id = from_node["id"]
        to_node_id = to_node["id"]
        
        # BFS
        visited = {from_node_id}
        queue = [(from_node_id, [from_node_id])]
        
        while queue:
            current_id, path = queue.pop(0)
            
            if len(path) > max_depth:
                break
            
            # Get neighbors
            edges = await self._get_node_edges(current_id, include_derived=True, limit=50)
            
            for edge in edges:
                neighbor_id = edge["to_node_id"] if edge["from_node_id"] == current_id else edge["from_node_id"]
                
                if neighbor_id == to_node_id:
                    # Found!
                    final_path = path + [neighbor_id]
                    return await self._build_path_response(final_path, edges)
                
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    queue.append((neighbor_id, path + [neighbor_id]))
        
        return {"path": [], "found": False, "depth_searched": max_depth}
    
    async def _build_path_response(
        self,
        path: List[str],
        all_edges: List[Dict]
    ) -> Dict:
        """Build response for found path"""
        nodes = []
        edges = []
        
        # Get all nodes in path
        for node_id in path:
            node = await self.graph_nodes.find_one({"id": node_id})
            if node:
                nodes.append(self._node_to_ui_dict(node))
        
        # Get edges between consecutive nodes
        for i in range(len(path) - 1):
            from_id = path[i]
            to_id = path[i + 1]
            
            # Find edge between these nodes
            edge = await self.graph_edges.find_one({
                "$or": [
                    {"from_node_id": from_id, "to_node_id": to_id},
                    {"from_node_id": to_id, "to_node_id": from_id}
                ]
            })
            
            if edge:
                edges.append(self._edge_to_ui_dict(edge, {}))
        
        return {
            "path": path,
            "found": True,
            "length": len(path) - 1,
            "nodes": nodes,
            "edges": edges
        }
    
    # =========================================================================
    # RELATED ENTITIES
    # =========================================================================
    
    async def get_related(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 30
    ) -> List[Dict]:
        """
        Get related entities (flat list, not graph)
        
        For sidebars and cards
        """
        node = await self._get_node(entity_type, entity_id)
        if not node:
            return []
        
        node_id = node["id"]
        
        # Get edges
        edges = await self._get_node_edges(node_id, include_derived=True, limit=limit * 2)
        ranked = self._rank_edges(edges)[:limit]
        
        # Get related nodes
        related = []
        seen = set()
        
        for edge in ranked:
            neighbor_id = edge["to_node_id"] if edge["from_node_id"] == node_id else edge["from_node_id"]
            
            if neighbor_id in seen:
                continue
            seen.add(neighbor_id)
            
            neighbor = await self.graph_nodes.find_one({"id": neighbor_id})
            if neighbor:
                related.append({
                    "type": neighbor.get("entity_type"),
                    "id": neighbor.get("entity_id"),
                    "label": neighbor.get("label"),
                    "relation": edge.get("relation_type"),
                    "weight": edge.get("weight", 1.0)
                })
        
        return related
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    async def _get_node(
        self,
        entity_type: str,
        entity_id: str
    ) -> Optional[Dict]:
        """Get node by entity type and id, with canonical resolution"""
        # First try direct match
        node = await self.graph_nodes.find_one({
            "entity_type": entity_type,
            "entity_id": entity_id
        })
        
        if node:
            return node
        
        # Try canonical resolution (handles aliases like ETH -> ethereum)
        try:
            from modules.knowledge_graph.canonical_resolver import get_canonical_resolver
            resolver = get_canonical_resolver(self.db)
            
            # Try to resolve by entity_id (might be symbol like ETH)
            canonical_id, entity = await resolver.resolve(entity_id, entity_type)
            if canonical_id:
                return await self.graph_nodes.find_one({"id": canonical_id})
        except Exception as e:
            logger.debug(f"[GraphAPI] Canonical resolution failed: {e}")
        
        return None
    
    async def _get_node_edges(
        self,
        node_id: str,
        include_derived: bool = False,
        limit: int = 50
    ) -> List[Dict]:
        """Get edges for a node with filtering"""
        query = {"$or": [
            {"from_node_id": node_id},
            {"to_node_id": node_id}
        ]}
        
        # Filter out derived if not requested
        if not include_derived:
            query["source_type"] = {"$ne": "derived"}
        
        cursor = self.graph_edges.find(query).limit(limit)
        return await cursor.to_list(length=limit)
    
    def _rank_edges(self, edges: List[Dict]) -> List[Dict]:
        """
        Rank edges by importance
        
        Formula: priority * 0.4 + weight * 0.3 + confidence * 0.2 + recency * 0.1
        """
        now = datetime.now(timezone.utc)
        
        def edge_score(edge):
            relation = edge.get("relation_type", "related_to")
            priority = RELATION_PRIORITY.get(relation, 0)
            weight = edge.get("weight", 1.0)
            confidence = edge.get("confidence", 0.5) or 0.5
            
            # Recency score (1.0 for edges < 30 days old, decreasing for older)
            created = edge.get("created_at") or edge.get("valid_from")
            recency = 0.5
            if created:
                if isinstance(created, str):
                    try:
                        created = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    except:
                        created = None
                # Ensure created has timezone
                if created and created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if created:
                    age_days = (now - created).days
                    if age_days < 30:
                        recency = 1.0
                    elif age_days < 90:
                        recency = 0.8
                    elif age_days < 365:
                        recency = 0.5
                    else:
                        recency = 0.3
            
            return priority * 0.4 + weight * 0.3 + confidence * 0.2 + recency * 0.1
        
        return sorted(edges, key=edge_score, reverse=True)
    
    def _node_to_ui(self, node: Dict) -> GraphUINode:
        """Convert DB node to UI node"""
        return GraphUINode(
            id=f"{node.get('entity_type')}:{node.get('entity_id')}",
            label=node.get("label", node.get("entity_id")),
            type=node.get("entity_type"),
            size=self._calculate_node_size(node),
            importance=node.get("metadata", {}).get("importance", 0.5),
            metadata=node.get("metadata", {})
        )
    
    def _node_to_ui_dict(self, node: Dict) -> Dict:
        """Convert DB node to UI dict"""
        return {
            "id": f"{node.get('entity_type')}:{node.get('entity_id')}",
            "label": node.get("label", node.get("entity_id")),
            "type": node.get("entity_type"),
            "size": self._calculate_node_size(node),
            "importance": node.get("metadata", {}).get("importance", 0.5)
        }
    
    def _edge_to_ui_dict(self, edge: Dict, nodes: Dict) -> Dict:
        """Convert DB edge to UI dict"""
        from_node = nodes.get(edge.get("from_node_id"), {})
        to_node = nodes.get(edge.get("to_node_id"), {})
        
        return {
            "id": edge.get("id"),
            "source": f"{from_node.get('entity_type', 'unknown')}:{from_node.get('entity_id', edge.get('from_node_id'))}",
            "target": f"{to_node.get('entity_type', 'unknown')}:{to_node.get('entity_id', edge.get('to_node_id'))}",
            "relation": edge.get("relation_type"),
            "weight": edge.get("weight", 1.0),
            "is_derived": edge.get("source_type") == "derived"
        }
    
    def _calculate_node_size(self, node: Dict) -> int:
        """Calculate visual size for node"""
        base_size = 20
        importance = node.get("metadata", {}).get("importance", 0.5)
        return int(base_size + importance * 20)
    
    async def _get_cached_payload(self, cache_key: str) -> Optional[Dict]:
        """Get cached graph payload"""
        doc = await self.graph_payload_cache.find_one({
            "cache_key": cache_key,
            "generated_at": {"$gte": datetime.now(timezone.utc) - timedelta(hours=1)}
        })
        
        if doc:
            return {
                "center": doc.get("center"),
                "nodes": doc.get("nodes", []),
                "edges": doc.get("edges", []),
                "meta": doc.get("meta", {})
            }
        
        return None
    
    async def _cache_payload(self, cache_key: str, payload: Dict):
        """Cache graph payload"""
        await self.graph_payload_cache.update_one(
            {"cache_key": cache_key},
            {
                "$set": {
                    "cache_key": cache_key,
                    **payload,
                    "generated_at": datetime.now(timezone.utc)
                }
            },
            upsert=True
        )


# =============================================================================
# HOT ENTITY PRECOMPUTATION
# =============================================================================

HOT_ENTITIES = [
    ("project", "bitcoin"),
    ("project", "ethereum"),
    ("project", "solana"),
    ("project", "arbitrum"),
    ("project", "optimism"),
    ("project", "base"),
    ("fund", "a16z"),
    ("fund", "paradigm"),
    ("fund", "polychain"),
    ("exchange", "binance"),
    ("exchange", "coinbase"),
]


async def precompute_hot_graphs(db):
    """
    Precompute ego graphs for hot entities
    
    Run as scheduled job
    """
    service = GraphQueryService(db)
    
    for entity_type, entity_id in HOT_ENTITIES:
        try:
            await service.get_ego_graph(
                entity_type=entity_type,
                entity_id=entity_id,
                depth=1,
                use_cache=True
            )
        except Exception as e:
            print(f"Error precomputing graph for {entity_type}:{entity_id}: {e}")
