"""
Knowledge Graph API Routes

Endpoints:
- GET /api/graph/network - Full network or ego-network
- GET /api/graph/node/{type}/{id} - Get single node
- GET /api/graph/edges/{type}/{id} - Get edges for node
- GET /api/graph/neighbors/{type}/{id} - Get neighbor nodes
- GET /api/graph/search - Search nodes
- GET /api/graph/related/{type}/{id} - Get related entities
- GET /api/graph/stats - Graph statistics
- POST /api/graph/rebuild - Trigger graph rebuild
- GET /api/entities/search - Entity discovery search
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..models import GraphNetworkResponse, GraphStatsResponse, NODE_TYPES
from ..query_service import GraphQueryService
from ..builder import GraphBuilder
from ..alias_resolver import EntityAliasResolver, bootstrap_common_aliases
from ..discovery_service import EntityDiscoveryService
from ..alias_learning_service import AliasLearningService, get_alias_learning_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph", tags=["Knowledge Graph"])

# Global instances (initialized on startup)
_query_service: Optional[GraphQueryService] = None
_builder: Optional[GraphBuilder] = None
_alias_resolver: Optional[EntityAliasResolver] = None
_discovery_service: Optional[EntityDiscoveryService] = None
_alias_learning_service: Optional[AliasLearningService] = None
_db: Optional[AsyncIOMotorDatabase] = None


def init_graph_services(db: AsyncIOMotorDatabase):
    """Initialize graph services with database connection"""
    global _query_service, _builder, _alias_resolver, _discovery_service, _alias_learning_service, _db
    _db = db
    _query_service = GraphQueryService(db)
    _builder = GraphBuilder(db)
    _alias_resolver = EntityAliasResolver(db)
    _discovery_service = EntityDiscoveryService(db)
    _alias_learning_service = get_alias_learning_service(db)
    logger.info("[GraphAPI] Services initialized (including alias learning)")


def get_query_service() -> GraphQueryService:
    if not _query_service:
        raise HTTPException(status_code=503, detail="Graph service not initialized")
    return _query_service


def get_builder() -> GraphBuilder:
    if not _builder:
        raise HTTPException(status_code=503, detail="Graph builder not initialized")
    return _builder


def get_alias_resolver() -> EntityAliasResolver:
    if not _alias_resolver:
        raise HTTPException(status_code=503, detail="Alias resolver not initialized")
    return _alias_resolver


def get_discovery_service() -> EntityDiscoveryService:
    if not _discovery_service:
        raise HTTPException(status_code=503, detail="Discovery service not initialized")
    return _discovery_service


def get_alias_learning_service_instance() -> AliasLearningService:
    if not _alias_learning_service:
        raise HTTPException(status_code=503, detail="Alias learning service not initialized")
    return _alias_learning_service


# =============================================================================
# Graph Health Monitor (pre-freeze checkpoint)
# =============================================================================

@router.get("/health")
async def get_graph_health():
    """
    Graph Health Monitor — real metrics from entity_graph_nodes + entity_graph_relations.
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    try:
        nodes_col = _db.entity_graph_nodes
        edges_col = _db.entity_graph_relations
        
        # Basic counts
        nodes_count = await nodes_col.count_documents({})
        edges_count = await edges_col.count_documents({})
        
        # Alias stats (try fomo_intel DB, fallback to 0)
        aliases_total = 0
        alias_candidates = 0
        try:
            alias_db = _db.client['fomo_intel']
            aliases_total = await alias_db.entity_aliases.count_documents({})
            alias_candidates = await alias_db.alias_candidates.count_documents({"approved": False})
        except Exception:
            pass
        
        avg_degree = round(edges_count / max(nodes_count, 1) * 2, 2)
        
        # Duplicate check — entities with same label
        pipeline = [
            {"$group": {
                "_id": {"$toLower": "$label"},
                "count": {"$sum": 1},
                "ids": {"$push": {"$ifNull": ["$id", "$entity_id"]}}
            }},
            {"$match": {"count": {"$gt": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        duplicates_cursor = nodes_col.aggregate(pipeline)
        potential_duplicates = await duplicates_cursor.to_list(length=10)
        
        # Node type distribution (field = "type")
        type_pipeline = [
            {"$group": {"_id": "$type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        type_cursor = nodes_col.aggregate(type_pipeline)
        node_types = {}
        async for doc in type_cursor:
            key = doc["_id"] if doc["_id"] else "unknown"
            node_types[key] = doc["count"]
        
        # Edge type distribution (field = "relation_type")
        edge_pipeline = [
            {"$group": {"_id": "$relation_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        edge_cursor = edges_col.aggregate(edge_pipeline)
        edge_types = {}
        async for doc in edge_cursor:
            key = doc["_id"] if doc["_id"] else "unknown"
            edge_types[key] = doc["count"]
        
        # Status determination
        status = "healthy"
        if len(potential_duplicates) > 5:
            status = "warning"
        if nodes_count == 0:
            status = "error"
        
        return {
            "status": status,
            "metrics": {
                "nodes_count": nodes_count,
                "edges_count": edges_count,
                "aliases_total": aliases_total,
                "alias_candidates": alias_candidates,
                "avg_degree": avg_degree
            },
            "distribution": {
                "node_types": node_types,
                "edge_types": edge_types
            },
            "duplicate_check": {
                "potential_duplicates": len(potential_duplicates),
                "samples": [
                    {"label": d["_id"], "count": d["count"], "ids": d["ids"][:3]}
                    for d in potential_duplicates[:5]
                ]
            },
            "thresholds": {
                "alias_auto_promotion": {"min_seen_count": 10, "min_confidence": 0.9},
                "hub_suppression": {"max_edges_per_node": 25}
            }
        }
    except Exception as e:
        logger.error(f"Graph health check failed: {e}")
        return {"status": "error", "error": str(e)}


# =============================================================================
# Network endpoints (for visualization)
# =============================================================================

@router.get("/network", response_model=GraphNetworkResponse)
async def get_network(
    center_type: Optional[str] = Query(None, description="Center node entity type"),
    center_id: Optional[str] = Query(None, description="Center node entity id"),
    depth: int = Query(1, ge=1, le=3, description="Traversal depth from center"),
    limit_nodes: int = Query(200, ge=10, le=500, description="Max nodes to return"),
    limit_edges: int = Query(500, ge=10, le=1000, description="Max edges to return"),
    node_types: Optional[str] = Query(None, description="Comma-separated node types to include"),
    relation_types: Optional[str] = Query(None, description="Comma-separated relation types to include"),
    scopes: Optional[str] = Query(None, description="G3 Context: Comma-separated scopes (investment,founder,ecosystem,partnership,market,event,mention)")
):
    """
    Get graph network for visualization.
    
    If center_type and center_id provided, returns ego-network around that entity.
    Otherwise returns a sample of the full network.
    
    G3 Context Layer scopes:
    - investment: invested_in, investor, led_round
    - founder: founded, founder, co_founded_by
    - ecosystem: built_on, ecosystem, has_token
    - partnership: partner, coinvested_with
    - market: listed_on, traded_on
    - event: event_linked, has_activity
    - mention: mention, related_to
    
    Response format is compatible with react-force-graph-2d:
    - nodes: [{id, label, type, size, ...}]
    - edges: [{source, target, relation, weight, scope, confidence, ...}]
    """
    service = get_query_service()
    
    # Parse comma-separated filters
    node_types_list = node_types.split(",") if node_types else None
    relation_types_list = relation_types.split(",") if relation_types else None
    scopes_list = [s.strip() for s in scopes.split(",")] if scopes else None
    
    result = await service.get_network(
        center_type=center_type,
        center_id=center_id,
        depth=depth,
        limit_nodes=limit_nodes,
        limit_edges=limit_edges,
        node_types=node_types_list,
        relation_types=relation_types_list
    )
    
    # G3: Filter edges by scope if specified
    if scopes_list:
        result.edges = [e for e in result.edges if e.get("scope") in scopes_list]
        result.stats["filtered_by_scopes"] = scopes_list
        result.stats["edge_count"] = len(result.edges)
    
    return result


@router.get("/network/{entity_type}/{entity_id}", response_model=GraphNetworkResponse)
async def get_entity_network(
    entity_type: str,
    entity_id: str,
    depth: int = Query(1, ge=1, le=3),
    limit_nodes: int = Query(100, ge=10, le=300),
    limit_edges: int = Query(300, ge=10, le=500),
    scopes: Optional[str] = Query(None, description="G3 Context: Comma-separated scopes to filter")
):
    """
    Get ego-network around a specific entity.
    Shorthand for /network?center_type=X&center_id=Y
    
    G3 Context Layer scopes: investment, founder, ecosystem, partnership, market, event, mention
    """
    service = get_query_service()
    result = await service.get_network(
        center_type=entity_type,
        center_id=entity_id,
        depth=depth,
        limit_nodes=limit_nodes,
        limit_edges=limit_edges
    )
    
    # G3: Filter edges by scope if specified
    if scopes:
        scopes_list = [s.strip() for s in scopes.split(",")]
        result.edges = [e for e in result.edges if e.get("scope") in scopes_list]
        result.stats["filtered_by_scopes"] = scopes_list
        result.stats["edge_count"] = len(result.edges)
    
    return result


# =============================================================================
# Node endpoints
# =============================================================================

@router.get("/node/{entity_type}/{entity_id}")
async def get_node(entity_type: str, entity_id: str):
    """Get single node by entity type and id"""
    service = get_query_service()
    node = await service.get_node(entity_type, entity_id)
    
    if not node:
        raise HTTPException(status_code=404, detail=f"Node not found: {entity_type}:{entity_id}")
    
    # Convert to API format
    nt = node.get("entity_type") or node.get("type") or "unknown"
    nid = node.get("entity_id") or node.get("entity") or node.get("cluster_id") or node.get("id", "")
    return {
        "id": f"{nt}:{nid}",
        "entity_type": nt,
        "entity_id": nid,
        "label": node.get("label") or node.get("entity") or node.get("id", ""),
        "slug": node.get("slug"),
        "status": node.get("status"),
        "metadata": node.get("metadata", {}),
        "edge_count": node.get("edge_count", 0),
        "created_at": node.get("created_at"),
        "updated_at": node.get("updated_at")
    }


@router.get("/edges/{entity_type}/{entity_id}")
async def get_edges(
    entity_type: str,
    entity_id: str,
    relation_type: Optional[str] = Query(None),
    direction: str = Query("both", regex="^(both|outgoing|incoming)$"),
    limit: int = Query(100, ge=1, le=500)
):
    """Get edges for a node"""
    service = get_query_service()
    edges = await service.get_edges(
        entity_type=entity_type,
        entity_id=entity_id,
        relation_type=relation_type,
        direction=direction,
        limit=limit
    )
    
    # Fetch node labels for edges
    result = []
    for edge in edges:
        from_id = edge.get("source_id") or edge.get("from_node_id")
        to_id = edge.get("target_id") or edge.get("to_node_id")
        from_node = await service.get_node_by_id(from_id) if from_id else None
        to_node = await service.get_node_by_id(to_id) if to_id else None
        
        def node_label(n):
            if not n: return None
            return n.get("label") or n.get("entity") or n.get("id", "")
        
        def node_typed_id(n, fallback):
            if not n: return fallback
            nt = n.get("entity_type") or n.get("type") or "unknown"
            nid = n.get("entity_id") or n.get("entity") or n.get("cluster_id") or n.get("id", "")
            return f"{nt}:{nid}"
        
        result.append({
            "id": edge.get("id", f"{from_id}-{to_id}"),
            "source": node_typed_id(from_node, from_id),
            "source_label": node_label(from_node),
            "target": node_typed_id(to_node, to_id),
            "target_label": node_label(to_node),
            "relation": edge.get("relation_type", "related_to"),
            "weight": edge.get("weight", edge.get("confidence", 1.0)),
            "source_type": edge.get("source_type", "direct"),
            "metadata": edge.get("metadata", {})
        })
    
    return {"edges": result, "total": len(result)}


@router.get("/neighbors/{entity_type}/{entity_id}")
async def get_neighbors(
    entity_type: str,
    entity_id: str,
    neighbor_type: Optional[str] = Query(None),
    relation_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200)
):
    """Get neighbor nodes for a node"""
    service = get_query_service()
    neighbors = await service.get_neighbors(
        entity_type=entity_type,
        entity_id=entity_id,
        neighbor_type=neighbor_type,
        relation_type=relation_type,
        limit=limit
    )
    
    result = []
    for node in neighbors:
        nt = node.get("entity_type") or node.get("type") or "unknown"
        nid = node.get("entity_id") or node.get("entity") or node.get("cluster_id") or node.get("id", "")
        result.append({
            "id": f"{nt}:{nid}",
            "label": node.get("label") or node.get("entity") or node.get("id", ""),
            "type": nt,
            "entity_id": nid,
            "slug": node.get("slug"),
            "metadata": node.get("metadata", {})
        })
    
    return {"neighbors": result, "total": len(result)}


# =============================================================================
# Search & Discovery
# =============================================================================

@router.get("/search")
async def search_nodes(
    q: str = Query(..., min_length=1, description="Search query"),
    entity_type: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100)
):
    """Search nodes by label/slug"""
    service = get_query_service()
    results = await service.search(query=q, entity_type=entity_type, limit=limit)
    return {"results": results, "total": len(results), "query": q}


@router.get("/related/{entity_type}/{entity_id}")
async def get_related(
    entity_type: str,
    entity_id: str,
    limit: int = Query(10, ge=1, le=50)
):
    """Get related entities based on shared connections"""
    service = get_query_service()
    related = await service.get_related(
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit
    )
    return {"related": related, "total": len(related)}


# =============================================================================
# Stats & Admin
# =============================================================================

@router.get("/stats", response_model=GraphStatsResponse)
async def get_stats():
    """Get graph statistics"""
    service = get_query_service()
    return await service.get_stats()


@router.get("/node-types")
async def get_node_types():
    """Get available node types"""
    return {"node_types": NODE_TYPES}


@router.post("/rebuild")
async def rebuild_graph():
    """
    Trigger full graph rebuild.
    Warning: This may take time for large datasets.
    """
    builder = get_builder()
    
    try:
        snapshot = await builder.full_rebuild()
        return {
            "status": "success",
            "snapshot_id": snapshot.id,
            "node_count": snapshot.node_count,
            "edge_count": snapshot.edge_count,
            "created_at": snapshot.created_at.isoformat()
        }
    except Exception as e:
        logger.error(f"[GraphAPI] Rebuild failed: {e}")
        raise HTTPException(status_code=500, detail=f"Rebuild failed: {str(e)}")


# =============================================================================
# Entity Discovery & Resolution
# =============================================================================

@router.get("/entities/search")
async def search_entities(
    q: str = Query(..., min_length=1, description="Search query"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(10, ge=1, le=50)
):
    """
    Search entities with alias resolution and discovery.
    Falls back to graph_nodes search if discovery service returns empty.
    """
    try:
        discovery = get_discovery_service()
        results = await discovery.search_suggestions(q, limit=limit)
    except Exception:
        results = []
    
    # Fallback: search graph_nodes directly if discovery returned nothing
    if not results:
        service = get_query_service()
        results = await service.search(q, entity_type=entity_type, limit=limit)
    
    # Filter by type if specified
    if entity_type and results:
        results = [r for r in results if r.get("type") == entity_type]
    
    return {
        "results": results,
        "total": len(results),
        "query": q
    }


@router.get("/entities/resolve/{query}")
async def resolve_entity(
    query: str,
    entity_type: Optional[str] = Query(None)
):
    """
    Resolve an entity query to canonical entity.
    Uses alias resolution + discovery.
    
    Returns canonical entity or 404 if not found.
    """
    alias_resolver = get_alias_resolver()
    
    # Try alias resolution first
    resolved = await alias_resolver.resolve(query, entity_type)
    if resolved:
        etype, eid = resolved
        return {
            "resolved": True,
            "entity_type": etype,
            "entity_id": eid,
            "canonical_id": f"{etype}:{eid}",
            "source": "alias"
        }
    
    # Try discovery
    discovery = get_discovery_service()
    entity = await discovery.discover_entity(query, entity_type)
    
    if entity:
        etype = entity.get("_entity_type") or entity.get("entity_type")
        eid = entity.get("_entity_id") or entity.get("entity_id")
        return {
            "resolved": True,
            "entity_type": etype,
            "entity_id": eid,
            "canonical_id": f"{etype}:{eid}",
            "source": "discovery",
            "entity": entity
        }
    
    raise HTTPException(status_code=404, detail=f"Entity not found: {query}")


@router.post("/aliases/add")
async def add_alias(
    entity_type: str = Query(...),
    entity_id: str = Query(...),
    alias: str = Query(...),
    source: str = Query("manual")
):
    """Add a new alias for an entity"""
    resolver = get_alias_resolver()
    success = await resolver.add_alias(
        entity_type=entity_type,
        entity_id=entity_id,
        alias=alias,
        source=source
    )
    
    if success:
        return {"status": "success", "alias": alias, "entity": f"{entity_type}:{entity_id}"}
    raise HTTPException(status_code=400, detail="Failed to add alias")


# =============================================================================
# Alias Learning endpoints (G2 - Auto-learning)
# Must be BEFORE /{entity_type}/{entity_id} to avoid route conflicts
# =============================================================================

@router.get("/aliases/candidates")
async def get_alias_candidates(
    limit: int = Query(50, ge=1, le=200),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    include_approved: bool = Query(False)
):
    """
    Get alias candidates awaiting review/promotion.
    
    Candidates are potential aliases learned by the system.
    When they reach threshold (seen_count >= 10, confidence >= 0.9),
    they are auto-promoted to entity_aliases.
    """
    service = get_alias_learning_service_instance()
    candidates = await service.get_candidates(
        limit=limit,
        min_confidence=min_confidence,
        include_approved=include_approved
    )
    return {
        "candidates": candidates,
        "count": len(candidates)
    }


@router.get("/aliases/learning/stats")
async def get_alias_learning_stats():
    """Get alias learning statistics"""
    service = get_alias_learning_service_instance()
    return await service.get_stats()


@router.post("/aliases/learning/observe")
async def record_alias_observation(
    alias: str = Query(..., description="The alias observed"),
    canonical_id: str = Query(..., description="The canonical entity it maps to"),
    source: str = Query("api", description="Source of observation"),
    confidence: float = Query(0.8, ge=0.0, le=1.0),
    entity_type: str = Query("asset", description="Entity type")
):
    """
    Record an alias observation for learning.
    
    The system accumulates observations and auto-promotes
    aliases when they reach confidence threshold.
    """
    service = get_alias_learning_service_instance()
    result = await service.record_alias_observation(
        alias=alias,
        canonical_id=canonical_id,
        source=source,
        confidence=confidence,
        entity_type=entity_type
    )
    return result


@router.post("/aliases/learning/promote")
async def promote_ready_candidates():
    """
    Batch promote all candidates that meet thresholds.
    
    Thresholds: seen_count >= 10, confidence >= 0.9
    """
    service = get_alias_learning_service_instance()
    promoted = await service.promote_ready_candidates()
    return {
        "promoted": promoted,
        "count": len(promoted)
    }


@router.post("/aliases/learning/approve")
async def manually_approve_alias(
    alias: str = Query(...),
    canonical_id: str = Query(...)
):
    """Manually approve and promote an alias"""
    service = get_alias_learning_service_instance()
    success = await service.manually_approve(alias, canonical_id)
    if success:
        return {"status": "approved", "alias": alias, "canonical_id": canonical_id}
    raise HTTPException(status_code=400, detail="Failed to approve alias")


@router.post("/aliases/learning/reject")
async def reject_alias_candidate(
    alias: str = Query(...),
    canonical_id: str = Query(...)
):
    """Reject an alias candidate (prevent auto-promotion)"""
    service = get_alias_learning_service_instance()
    success = await service.reject_candidate(alias, canonical_id)
    if success:
        return {"status": "rejected", "alias": alias, "canonical_id": canonical_id}
    raise HTTPException(status_code=404, detail="Candidate not found")


# Dynamic route must come AFTER specific routes
@router.get("/aliases/{entity_type}/{entity_id}")
async def get_aliases(entity_type: str, entity_id: str):
    """Get all aliases for an entity"""
    resolver = get_alias_resolver()
    aliases = await resolver.get_all_aliases(entity_type, entity_id)
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "aliases": aliases,
        "count": len(aliases)
    }


@router.post("/aliases/bootstrap")
async def bootstrap_aliases():
    """Bootstrap common entity aliases"""
    try:
        count = await bootstrap_common_aliases(_db)
        return {"status": "success", "aliases_added": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
