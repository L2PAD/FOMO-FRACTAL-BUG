"""
Graph API Routes

Headless Graph Engine endpoints for:
- Internal Dashboard
- UA Project
- Any external consumer

Endpoints:
- GET /api/graph/search
- GET /api/graph/ego/{type}/{id}
- GET /api/graph/expand/{node_id}
- GET /api/graph/path
- GET /api/graph/related/{type}/{id}
- GET /api/graph/ui/{type}/{id} - Ready-to-render payload
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/api/graph", tags=["Graph API"])


# =============================================================================
# SEARCH
# =============================================================================

# Stabilization Sprint C2 — shadowed by knowledge_graph.api.routes::search_nodes.
async def search_entities(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(20, ge=1, le=50)
):
    """
    Search for entities in the graph
    
    Returns: [{type, id, label}]
    """
    from server import db
    from modules.knowledge_graph.graph_api_service import GraphQueryService
    
    service = GraphQueryService(db)
    results = await service.search(q, limit=limit)
    
    return {"results": results, "query": q}


@router.get("/search/advanced")
async def search_entities_advanced(
    q: str = Query(..., min_length=2, description="Search query"),
    entity_type: Optional[str] = Query(None, description="Filter by type: fund, project, person"),
    auto_create: bool = Query(True, description="Auto-create entity if found in sources")
):
    """
    Advanced multi-stage entity search.
    
    Pipeline:
    1. Exact match in graph
    2. Alias match
    3. Fuzzy match
    4. Candidate search
    5. Mention discovery
    
    If entity is found in any source, it will be returned (or created).
    This ensures search NEVER fails if entity exists in data.
    """
    from server import db
    from modules.knowledge_graph.entity_search_service import get_entity_search_service
    
    search_service = get_entity_search_service(db)
    result = await search_service.search(q, entity_type=entity_type, auto_create=auto_create)
    
    return result


@router.get("/candidates")
async def get_entity_candidates(
    status: Optional[str] = Query(None, description="Filter by status"),
    entity_type: Optional[str] = Query(None, description="Filter by type"),
    limit: int = Query(50, ge=1, le=200)
):
    """Get discovered entity candidates"""
    from server import db
    
    filter_dict = {}
    if status:
        filter_dict["status"] = status
    if entity_type:
        filter_dict["entity_type_guess"] = entity_type
    
    cursor = db.entity_candidates.find(
        filter_dict, 
        {"_id": 0}
    ).sort("confidence", -1).limit(limit)
    
    candidates = await cursor.to_list(length=limit)
    
    return {
        "candidates": candidates,
        "count": len(candidates)
    }


@router.post("/candidates/seed")
async def seed_entity_candidates():
    """Seed known entities as candidates"""
    from server import db
    from modules.knowledge_graph.entity_candidate_discovery import get_entity_candidate_discovery
    
    discovery = get_entity_candidate_discovery(db)
    await discovery.ensure_indexes()
    result = await discovery.seed_known_entities()
    
    return result


@router.post("/candidates/discover")
async def run_entity_discovery():
    """Run entity discovery job manually"""
    from server import db
    from modules.knowledge_graph.entity_candidate_discovery import get_entity_candidate_discovery
    
    discovery = get_entity_candidate_discovery(db)
    result = await discovery.run_discovery_job()
    
    return result


@router.get("/candidates/stats")
async def get_candidate_stats():
    """Get entity candidate statistics"""
    from server import db
    from modules.knowledge_graph.entity_candidate_discovery import get_entity_candidate_discovery
    
    discovery = get_entity_candidate_discovery(db)
    stats = await discovery.get_stats()
    
    return stats


@router.get("/entities/{entity_id}/confidence")
async def get_entity_confidence(entity_id: str):
    """Get confidence record for an entity"""
    from server import db
    from modules.knowledge_graph.entity_confidence_service import get_entity_confidence_service
    
    service = get_entity_confidence_service(db)
    confidence = await service.get_confidence(entity_id)
    
    if not confidence:
        raise HTTPException(status_code=404, detail="Confidence record not found")
    
    return confidence


@router.get("/entities/low-confidence")
async def get_low_confidence_entities(limit: int = Query(50, ge=1, le=200)):
    """Get entities with low confidence scores"""
    from server import db
    from modules.knowledge_graph.entity_confidence_service import get_entity_confidence_service
    
    service = get_entity_confidence_service(db)
    entities = await service.get_low_confidence_entities(limit)
    
    return {"entities": entities, "count": len(entities)}


@router.get("/quality/metrics")
async def get_quality_metrics():
    """Get entity quality metrics and health status"""
    from server import db
    from modules.knowledge_graph.entity_confidence_service import get_entity_confidence_service
    
    service = get_entity_confidence_service(db)
    metrics = await service.get_quality_metrics()
    
    return metrics


@router.get("/validation/stats")
async def get_validation_stats():
    """Get provider validation statistics"""
    from server import db
    from modules.knowledge_graph.provider_validation_service import get_provider_validation_service
    
    service = get_provider_validation_service(db)
    stats = await service.get_validation_stats()
    
    return stats


@router.post("/entities/{name}/validate")
async def validate_entity_manually(name: str, entity_type: Optional[str] = Query(None)):
    """Manually validate an entity against providers"""
    from server import db
    from modules.knowledge_graph.provider_validation_service import get_provider_validation_service
    from modules.knowledge_graph.entity_confidence_service import get_entity_confidence_service
    
    provider_service = get_provider_validation_service(db)
    confidence_service = get_entity_confidence_service(db)
    
    # Validate with providers
    validation = await provider_service.validate_entity(name, entity_type)
    
    # Calculate confidence
    candidate = {
        "name": name,
        "entity_type_guess": entity_type or "project",
        "source_type": "manual",
        "mention_count": 1,
        "provider_matches": validation.get("provider_matches", [])
    }
    
    confidence = await confidence_service.calculate_confidence(candidate, validation)
    
    return {
        "name": name,
        "validation": validation,
        "confidence": confidence
    }


@router.get("/search/analytics")
async def get_search_analytics(days: int = Query(7, ge=1, le=30)):
    """Get search analytics to identify missing entities"""
    from server import db
    from modules.knowledge_graph.entity_search_service import get_entity_search_service
    
    search_service = get_entity_search_service(db)
    analytics = await search_service.get_search_analytics(days)
    
    return analytics


# =============================================================================
# GRAPH EXPANSION
# =============================================================================

@router.post("/expand/{entity_id:path}")
async def expand_entity_graph(entity_id: str):
    """
    Expand graph for a specific entity.
    Creates edges based on funding, co-investments, mentions.
    """
    from server import db
    from modules.knowledge_graph.graph_expansion_service import get_graph_expansion_service
    
    service = get_graph_expansion_service(db)
    result = await service.expand_for_entity(entity_id)
    
    return result


@router.post("/expand/batch")
async def expand_new_entities():
    """Run graph expansion for newly approved entities"""
    from server import db
    from modules.knowledge_graph.graph_expansion_service import get_graph_expansion_service
    
    service = get_graph_expansion_service(db)
    result = await service.expand_new_entities()
    
    return result


@router.get("/expansion/stats")
async def get_expansion_stats():
    """Get graph expansion statistics"""
    from server import db
    from modules.knowledge_graph.graph_expansion_service import get_graph_expansion_service
    
    service = get_graph_expansion_service(db)
    stats = await service.get_stats()
    
    return stats


# =============================================================================
# ALIAS STABILITY
# =============================================================================

@router.get("/alias/stability")
async def get_alias_stability_report():
    """Get full alias stability report"""
    from server import db
    from modules.knowledge_graph.alias_stability_service import get_alias_stability_service
    
    service = get_alias_stability_service(db)
    report = await service.get_stability_report()
    
    return report


@router.get("/alias/conflicts")
async def get_alias_conflicts():
    """Detect alias conflicts"""
    from server import db
    from modules.knowledge_graph.alias_stability_service import get_alias_stability_service
    
    service = get_alias_stability_service(db)
    result = await service.detect_conflicts()
    
    return result


@router.get("/alias/duplicates")
async def get_potential_duplicates(limit: int = Query(20, ge=1, le=100)):
    """Detect potential duplicate entities"""
    from server import db
    from modules.knowledge_graph.alias_stability_service import get_alias_stability_service
    
    service = get_alias_stability_service(db)
    result = await service.detect_potential_duplicates(limit)
    
    return result


@router.get("/alias/health/{entity_id:path}")
async def get_entity_alias_health(entity_id: str):
    """Check alias health for a specific entity"""
    from server import db
    from modules.knowledge_graph.alias_stability_service import get_alias_stability_service
    
    service = get_alias_stability_service(db)
    result = await service.check_alias_health(entity_id)
    
    return result


@router.get("/alias/merge-suggestions")
async def get_merge_suggestions(limit: int = Query(20, ge=1, le=50)):
    """Get suggested entity merges"""
    from server import db
    from modules.knowledge_graph.alias_stability_service import get_alias_stability_service
    
    service = get_alias_stability_service(db)
    suggestions = await service.suggest_merges(limit)
    
    return {"suggestions": suggestions, "count": len(suggestions)}


# =============================================================================
# NEIGHBOR MATERIALIZATION (Cache Layer)
# Routes: /api/graph/cache/neighbors/* to avoid conflict with /api/graph/neighbors/{type}/{id}
# IMPORTANT: Static routes MUST come before dynamic path routes
# =============================================================================

@router.get("/cache/neighbors/stats")
async def get_materialization_stats():
    """Get neighbor materialization statistics"""
    from server import db
    from modules.knowledge_graph.neighbor_materialization_service import get_neighbor_materialization_service
    
    service = get_neighbor_materialization_service(db)
    stats = await service.get_stats()
    
    return stats


@router.post("/cache/neighbors/materialize-hot")
async def materialize_hot_entities():
    """Materialize all hot entities"""
    from server import db
    from modules.knowledge_graph.neighbor_materialization_service import get_neighbor_materialization_service
    
    service = get_neighbor_materialization_service(db)
    result = await service.materialize_hot_entities()
    
    return result


@router.post("/cache/neighbors/materialize/{entity_id:path}")
async def materialize_entity_neighbors(entity_id: str, force: bool = Query(False)):
    """Materialize neighbors for an entity"""
    from server import db
    from modules.knowledge_graph.neighbor_materialization_service import get_neighbor_materialization_service
    
    service = get_neighbor_materialization_service(db)
    result = await service.materialize_entity(entity_id, force=force)
    
    return result


@router.get("/cache/neighbors/{entity_id:path}")
async def get_cached_neighbors(entity_id: str):
    """
    Get cached neighbors for an entity (fast).
    
    entity_id format: "project:bitcoin", "fund:a16z"
    
    Returns pre-computed neighbor data if cached, otherwise materializes on-demand.
    """
    from server import db
    from modules.knowledge_graph.neighbor_materialization_service import get_neighbor_materialization_service
    
    service = get_neighbor_materialization_service(db)
    cached = await service.get_cached_neighbors(entity_id)
    
    if cached:
        return cached
    
    # Materialize on demand
    result = await service.materialize_entity(entity_id)
    if result.get("materialized"):
        return await service.get_cached_neighbors(entity_id)
    
    return {"error": "Could not materialize neighbors", "details": result}


# =============================================================================
# ENTITY MERGE
# =============================================================================

@router.get("/merge/candidates")
async def get_merge_candidates(
    status: str = Query("pending", description="Filter by status: pending, merged, rejected"),
    limit: int = Query(50, ge=1, le=200)
):
    """Get merge candidates"""
    from server import db
    from modules.knowledge_graph.entity_merge_service import get_entity_merge_service
    
    service = get_entity_merge_service(db)
    candidates = await service.get_merge_candidates(status, limit)
    
    return {"candidates": candidates, "count": len(candidates)}


@router.post("/merge/detect")
async def detect_merge_candidates(limit: int = Query(50, ge=1, le=100)):
    """Detect new merge candidates"""
    from server import db
    from modules.knowledge_graph.entity_merge_service import get_entity_merge_service
    
    service = get_entity_merge_service(db)
    await service.ensure_indexes()
    result = await service.detect_merge_candidates(limit)
    
    return result


@router.post("/merge/execute")
async def merge_entities(
    source_entity: str = Query(..., description="Entity to merge FROM (will be deleted)"),
    target_entity: str = Query(..., description="Entity to merge INTO (canonical)"),
    reason: str = Query("manual", description="Reason for merge")
):
    """
    Merge source entity into target (canonical) entity.
    
    WARNING: This permanently merges entities. Source entity will be deleted.
    """
    from server import db
    from modules.knowledge_graph.entity_merge_service import get_entity_merge_service
    
    service = get_entity_merge_service(db)
    result = await service.merge_entities(source_entity, target_entity, reason)
    
    return result


@router.post("/merge/reject")
async def reject_merge_candidate(
    entity_a: str = Query(...),
    entity_b: str = Query(...)
):
    """Reject a merge candidate"""
    from server import db
    from modules.knowledge_graph.entity_merge_service import get_entity_merge_service
    
    service = get_entity_merge_service(db)
    rejected = await service.reject_candidate(entity_a, entity_b)
    
    return {"rejected": rejected}


@router.post("/merge/auto")
async def auto_merge_high_confidence(similarity: float = Query(0.95, ge=0.9, le=1.0)):
    """
    Auto-merge candidates with very high similarity.
    Use with caution.
    """
    from server import db
    from modules.knowledge_graph.entity_merge_service import get_entity_merge_service
    
    service = get_entity_merge_service(db)
    result = await service.auto_merge_high_confidence(similarity)
    
    return result


@router.get("/merge/history")
async def get_merge_history(limit: int = Query(50, ge=1, le=200)):
    """Get merge history"""
    from server import db
    from modules.knowledge_graph.entity_merge_service import get_entity_merge_service
    
    service = get_entity_merge_service(db)
    history = await service.get_merge_history(limit)
    
    return {"history": history, "count": len(history)}


@router.get("/merge/stats")
async def get_merge_stats():
    """Get merge statistics"""
    from server import db
    from modules.knowledge_graph.entity_merge_service import get_entity_merge_service
    
    service = get_entity_merge_service(db)
    stats = await service.get_stats()
    
    return stats


# =============================================================================
# ENTITY SCOPE
# =============================================================================

@router.get("/scope/stats")
async def get_scope_stats():
    """Get scope statistics"""
    from server import db
    from modules.knowledge_graph.entity_scope_service import get_entity_scope_service
    
    service = get_entity_scope_service(db)
    stats = await service.get_stats()
    
    return stats


@router.get("/scope/drift-detection")
async def detect_identity_drift():
    """Detect potential identity drift"""
    from server import db
    from modules.knowledge_graph.entity_scope_service import get_entity_scope_service
    
    service = get_entity_scope_service(db)
    result = await service.detect_identity_drift()
    
    return result


@router.post("/scope/assign")
async def assign_entity_scope(
    entity_id: str = Query(...),
    scope: str = Query(..., description="Scope: protocol, token, organization, ecosystem, person, narrative, technology, product")
):
    """Manually assign scope to entity"""
    from server import db
    from modules.knowledge_graph.entity_scope_service import get_entity_scope_service
    
    service = get_entity_scope_service(db)
    success = await service.assign_scope(entity_id, scope, confidence=1.0, source="manual")
    
    return {"success": success, "entity_id": entity_id, "scope": scope}


@router.post("/scope/batch")
async def batch_assign_scopes(limit: int = Query(100, ge=1, le=500)):
    """Batch assign scopes to entities without scope"""
    from server import db
    from modules.knowledge_graph.entity_scope_service import get_entity_scope_service
    
    service = get_entity_scope_service(db)
    await service.ensure_indexes()
    result = await service.batch_assign_scopes(limit)
    
    return result


@router.get("/scope/by-scope/{scope}")
async def get_entities_by_scope(scope: str, limit: int = Query(50, ge=1, le=200)):
    """Get entities by scope"""
    from server import db
    from modules.knowledge_graph.entity_scope_service import get_entity_scope_service
    
    service = get_entity_scope_service(db)
    entities = await service.get_entities_by_scope(scope, limit)
    
    return {"entities": entities, "count": len(entities), "scope": scope}


@router.get("/scope/{entity_id:path}")
async def get_entity_scope(entity_id: str):
    """Get scope for an entity"""
    from server import db
    from modules.knowledge_graph.entity_scope_service import get_entity_scope_service
    
    service = get_entity_scope_service(db)
    scope = await service.get_scope(entity_id)
    
    if not scope:
        # Try to resolve
        node = await db.graph_nodes.find_one({"id": entity_id})
        if node:
            parts = entity_id.split(":")
            entity_type = parts[0] if len(parts) >= 2 else "unknown"
            resolution = await service.resolve_scope(
                entity_id, node.get("label", ""), entity_type
            )
            return {"resolved": True, **resolution}
        return {"error": "Entity not found"}
    
    return scope


# =============================================================================
# EGO GRAPH
# =============================================================================

@router.get("/ego/{entity_type}/{entity_id}")
async def get_ego_graph(
    entity_type: str,
    entity_id: str,
    depth: int = Query(1, ge=1, le=3),
    max_nodes: int = Query(30, ge=10, le=80),
    max_edges: int = Query(40, ge=10, le=120),
    include_derived: bool = Query(False, description="Include derived relations"),
    no_cache: bool = Query(False, description="Skip cache")
):
    """
    Get ego graph (subgraph around an entity)
    
    This is the main endpoint for graph visualization.
    Returns nodes and edges ready for frontend rendering.
    
    Graph Explosion Protection:
    - Max depth: 3
    - Max nodes: 80
    - Max edges: 120
    - Hub suppression: 25 edges per hub
    """
    import logging
    log = logging.getLogger(__name__)
    log.info(f"[GraphRoute] GET ego/{entity_type}/{entity_id} no_cache={no_cache}")
    
    from server import db
    from modules.knowledge_graph.graph_api_service import GraphQueryService
    
    service = GraphQueryService(db)
    
    result = await service.get_ego_graph(
        entity_type=entity_type,
        entity_id=entity_id,
        depth=depth,
        max_nodes=max_nodes,
        max_edges=max_edges,
        include_derived=include_derived,
        use_cache=not no_cache
    )
    
    return result.dict()


@router.get("/ui/{entity_type}/{entity_id}")
async def get_ui_ready_graph(
    entity_type: str,
    entity_id: str,
    mode: str = Query("default", description="default or research")
):
    """
    Get UI-ready graph payload
    
    Simplified endpoint that returns optimal graph for visualization.
    
    Modes:
    - default: depth=1, max_nodes=30, no derived edges
    - research: depth=2, max_nodes=60, includes derived edges
    """
    from server import db
    from modules.knowledge_graph.graph_api_service import GraphQueryService
    
    service = GraphQueryService(db)
    
    if mode == "research":
        result = await service.get_ego_graph(
            entity_type=entity_type,
            entity_id=entity_id,
            depth=2,
            max_nodes=60,
            max_edges=80,
            include_derived=True
        )
    else:
        result = await service.get_ego_graph(
            entity_type=entity_type,
            entity_id=entity_id,
            depth=1,
            max_nodes=30,
            max_edges=40,
            include_derived=False
        )
    
    return result.dict()


# =============================================================================
# EXPAND NODE
# =============================================================================

@router.get("/expand/{node_id}")
async def expand_node(
    node_id: str,
    relation_type: Optional[str] = None,
    limit: int = Query(20, ge=5, le=30)
):
    """
    Expand a node - get its neighbors
    
    Called when user clicks on a node in the graph.
    Returns new nodes and edges to add to the visualization.
    """
    from server import db
    from modules.knowledge_graph.graph_api_service import GraphQueryService
    
    service = GraphQueryService(db)
    
    result = await service.expand_node(
        node_id=node_id,
        relation_type=relation_type,
        limit=limit
    )
    
    return result


# =============================================================================
# PATH SEARCH
# =============================================================================

@router.get("/path")
async def find_path(
    from_type: str = Query(..., description="Source entity type"),
    from_id: str = Query(..., description="Source entity ID"),
    to_type: str = Query(..., description="Target entity type"),
    to_id: str = Query(..., description="Target entity ID"),
    max_depth: int = Query(4, ge=2, le=6)
):
    """
    Find path between two entities
    
    Uses BFS to find shortest connection path.
    
    Example:
    /api/graph/path?from_type=person&from_id=vitalik_buterin&to_type=fund&to_id=a16z
    """
    from server import db
    from modules.knowledge_graph.graph_api_service import GraphQueryService
    
    service = GraphQueryService(db)
    
    result = await service.find_path(
        from_type=from_type,
        from_id=from_id,
        to_type=to_type,
        to_id=to_id,
        max_depth=max_depth
    )
    
    return result


# =============================================================================
# RELATED ENTITIES
# =============================================================================

# Stabilization Sprint C2 — shadowed by knowledge_graph.api.routes::get_related.
async def get_related_entities(
    entity_type: str,
    entity_id: str,
    limit: int = Query(30, ge=5, le=50)
):
    """
    Get related entities (flat list)
    
    For sidebars, cards, and non-graph UIs.
    Returns list of related entities with relation type.
    """
    from server import db
    from modules.knowledge_graph.graph_api_service import GraphQueryService
    
    service = GraphQueryService(db)
    
    related = await service.get_related(
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit
    )
    
    return {
        "entity": f"{entity_type}:{entity_id}",
        "related": related,
        "count": len(related)
    }


# =============================================================================
# GRAPH STATS
# =============================================================================

# Stabilization Sprint C2 — shadowed by knowledge_graph.api.routes::get_stats.
async def get_graph_stats():
    """Get graph statistics"""
    from server import db
    
    node_count = await db.graph_nodes.count_documents({})
    edge_count = await db.graph_relations.count_documents({})
    
    # Count by type - support both 'entity_type' and 'type' fields
    node_types = await db.graph_nodes.aggregate([
        {"$group": {"_id": {"$ifNull": ["$entity_type", {"$ifNull": ["$type", "unknown"]}]}, "count": {"$sum": 1}}}
    ]).to_list(length=20)
    
    edge_types = await db.graph_relations.aggregate([
        {"$group": {"_id": {"$ifNull": ["$relation_type", "unknown"]}, "count": {"$sum": 1}}}
    ]).to_list(length=50)
    
    return {
        "total_nodes": node_count,
        "total_edges": edge_count,
        "nodes_by_type": {str(t["_id"] or "unknown"): t["count"] for t in node_types},
        "edges_by_type": {str(t["_id"] or "unknown"): t["count"] for t in edge_types}
    }


# =============================================================================
# NARRATIVE EARLY DETECTION API
# =============================================================================

@router.get("/narratives/all")
async def get_all_narratives(limit: int = Query(30, ge=5, le=100)):
    """Get all active narratives with emergence scores"""
    from server import db
    from modules.narrative.early_detection import NarrativeEarlyDetector
    
    detector = NarrativeEarlyDetector(db)
    narratives = await detector.get_all_active_narratives(limit=limit)
    
    return {"narratives": narratives, "count": len(narratives)}


@router.get("/narratives/emerging")
async def get_emerging_narratives_v2(limit: int = Query(10, ge=1, le=50)):
    """
    Get emerging narratives (early detection)
    
    These are narratives just starting to form
    """
    from server import db
    from modules.narrative.early_detection import NarrativeEarlyDetector
    
    detector = NarrativeEarlyDetector(db)
    narratives = await detector.get_emerging_narratives(limit=limit)
    
    return {"narratives": narratives, "lifecycle": "emerging"}


@router.get("/narratives/growing")
async def get_growing_narratives(limit: int = Query(10, ge=1, le=50)):
    """Get growing narratives"""
    from server import db
    from modules.narrative.early_detection import NarrativeEarlyDetector
    
    detector = NarrativeEarlyDetector(db)
    narratives = await detector.get_growing_narratives(limit=limit)
    
    return {"narratives": narratives, "lifecycle": "growing"}


@router.get("/narratives/dominant")
async def get_dominant_narratives(limit: int = Query(10, ge=1, le=50)):
    """Get dominant narratives (peak attention)"""
    from server import db
    from modules.narrative.early_detection import NarrativeEarlyDetector
    
    detector = NarrativeEarlyDetector(db)
    narratives = await detector.get_dominant_narratives(limit=limit)
    
    return {"narratives": narratives, "lifecycle": "dominant"}


@router.post("/narratives/detect")
async def trigger_narrative_detection():
    """Manually trigger narrative early detection"""
    from server import db
    from modules.narrative.early_detection import NarrativeEarlyDetector
    
    detector = NarrativeEarlyDetector(db)
    emerging = await detector.detect_emerging_narratives()
    
    return {
        "status": "completed",
        "detected": len(emerging),
        "narratives": [{"id": n.id, "name": n.name, "lifecycle": n.lifecycle, "score": n.emergence_score} for n in emerging]
    }


# =============================================================================
# TEMPORAL GRAPH API
# =============================================================================

@router.get("/temporal/at")
async def get_graph_at_time(
    entity_type: str = Query(...),
    entity_id: str = Query(...),
    time: str = Query(..., description="ISO datetime or YYYY-MM-DD"),
    depth: int = Query(1, ge=1, le=2)
):
    """
    Get graph state at specific point in time
    
    Example: /api/graph/temporal/at?entity_type=project&entity_id=arbitrum&time=2023-01-01
    """
    from server import db
    from modules.knowledge_graph.temporal_graph import TemporalGraphService
    from datetime import datetime
    
    # Parse time
    try:
        if "T" in time:
            at_time = datetime.fromisoformat(time.replace("Z", "+00:00"))
        else:
            at_time = datetime.strptime(time, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except:
        raise HTTPException(status_code=400, detail="Invalid time format. Use YYYY-MM-DD or ISO datetime")
    
    service = TemporalGraphService(db)
    result = await service.get_graph_at_time(entity_type, entity_id, at_time, depth)
    
    return result


@router.get("/temporal/evolution/{entity_type}/{entity_id}")
async def get_network_evolution(
    entity_type: str,
    entity_id: str,
    days: int = Query(365, ge=30, le=1095)
):
    """
    Get how entity's network evolved over time
    
    Returns timeline of edge creations
    """
    from server import db
    from modules.knowledge_graph.temporal_graph import TemporalGraphService
    
    service = TemporalGraphService(db)
    
    to_date = datetime.now(timezone.utc)
    from_date = to_date - timedelta(days=days)
    
    evolution = await service.get_network_evolution(
        entity_type, entity_id, from_date, to_date
    )
    
    return {
        "entity": f"{entity_type}:{entity_id}",
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "events": evolution,
        "count": len(evolution)
    }


@router.post("/temporal/snapshot")
async def create_graph_snapshot(label: Optional[str] = None):
    """Create snapshot of current graph state"""
    from server import db
    from modules.knowledge_graph.temporal_graph import TemporalGraphService
    
    service = TemporalGraphService(db)
    snapshot = await service.create_snapshot(label)
    
    return snapshot.dict()


@router.get("/temporal/snapshots")
async def get_graph_snapshots(limit: int = Query(20, ge=1, le=50)):
    """Get list of graph snapshots"""
    from server import db
    
    cursor = db.graph_snapshots.find().sort("snapshot_time", -1).limit(limit)
    snapshots = await cursor.to_list(length=limit)
    
    return {"snapshots": snapshots}


# =============================================================================
# GRAPH METRICS API
# =============================================================================

@router.get("/metrics/summary")
async def get_graph_metrics_summary():
    """Get overall graph metrics"""
    from server import db
    from modules.knowledge_graph.temporal_graph import GraphMetricsService
    
    service = GraphMetricsService(db)
    return await service.get_graph_summary_metrics()


@router.get("/metrics/node/{entity_type}/{entity_id}")
async def get_node_metrics(entity_type: str, entity_id: str):
    """Get metrics for specific node"""
    from server import db
    from modules.knowledge_graph.temporal_graph import GraphMetricsService
    
    # Find node
    node = await db.graph_nodes.find_one({
        "entity_type": entity_type,
        "entity_id": entity_id
    })
    
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    service = GraphMetricsService(db)
    metrics = await service.calculate_node_metrics(node["id"])
    
    return metrics.dict() if metrics else {"error": "Failed to calculate"}


@router.get("/metrics/top-influence")
async def get_top_influence_nodes(limit: int = Query(20, ge=5, le=50)):
    """Get nodes with highest influence score"""
    from server import db
    from modules.knowledge_graph.temporal_graph import GraphMetricsService
    
    service = GraphMetricsService(db)
    top_nodes = await service.get_top_by_influence(limit)
    
    return {"nodes": top_nodes}


@router.post("/metrics/calculate-all")
async def calculate_all_node_metrics():
    """Trigger calculation of metrics for all nodes"""
    from server import db
    from modules.knowledge_graph.temporal_graph import GraphMetricsService
    
    service = GraphMetricsService(db)
    stats = await service.calculate_all_metrics()
    
    return {"status": "completed", "stats": stats}


# =============================================================================
# TOPIC API
# =============================================================================

@router.get("/topics/trending")
async def get_trending_topics(limit: int = Query(20, ge=5, le=50)):
    """Get trending topics"""
    from server import db
    from modules.intelligence.topic_layer import TopicService
    
    service = TopicService(db)
    topics = await service.get_trending_topics(limit=limit)
    
    return {"topics": topics}


@router.get("/topics/{topic_id}/events")
async def get_topic_events(topic_id: str, limit: int = Query(50, ge=10, le=100)):
    """Get events for a topic"""
    from server import db
    from modules.intelligence.topic_layer import TopicService
    
    service = TopicService(db)
    event_ids = await service.get_events_for_topic(topic_id, limit=limit)
    
    return {"topic_id": topic_id, "event_ids": event_ids, "count": len(event_ids)}
