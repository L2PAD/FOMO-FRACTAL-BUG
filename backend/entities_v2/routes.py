"""
Entities V2 Routes
===================
Phase 1: Entity Registry
Phase 2: Address Attribution Engine
"""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/entities/v2", tags=["entities-v2"])


# ══════════════════════════════════════════════════════════
#  PHASE 1 — Registry
# ══════════════════════════════════════════════════════════

@router.post("/seed")
def seed():
    """Seed entity registry with real addresses. Idempotent."""
    from .service import seed_entities
    result = seed_entities()
    return JSONResponse(content={"ok": True, **result})


@router.get("/list")
def entity_list(
    type: str = Query(None),
    category: str = Query(None),
    search: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
):
    """List entities with filtering."""
    from .service import list_entities
    result = list_entities(entity_type=type, category=category, search=search, page=page, limit=limit)
    return JSONResponse(content={"ok": True, **result})


@router.get("/summary")
def entity_summary():
    """Entity counts by type/category."""
    from .service import get_entity_types_summary
    result = get_entity_types_summary()
    return JSONResponse(content={"ok": True, **result})


@router.get("/search")
def entity_search(q: str = Query(""), limit: int = Query(10, ge=1, le=50)):
    """Quick entity search."""
    from .service import search_entities
    results = search_entities(query=q, limit=limit)
    return JSONResponse(content={"ok": True, "results": results})


@router.get("/resolve")
def resolve_address(address: str = Query(""), chain: str = Query("ethereum")):
    """Resolve an address to its entity."""
    from .service import resolve_address
    result = resolve_address(address=address, chain=chain)
    if not result:
        return JSONResponse(content={"ok": True, "found": False, "entity": None})
    return JSONResponse(content={"ok": True, "found": True, "entity": result})


# ══════════════════════════════════════════════════════════
#  PHASE 2 — Address Attribution Engine
# ══════════════════════════════════════════════════════════

@router.post("/address-index/build")
def build_index():
    """Build/rebuild address activity index from all on-chain sources."""
    from .address_activity_service import build_address_activity_index
    result = build_address_activity_index()
    return JSONResponse(content={"ok": True, **result})


@router.get("/address-index/status")
def index_status():
    """Address activity index health & coverage."""
    from .address_activity_service import get_address_index_status
    result = get_address_index_status()
    return JSONResponse(content={"ok": True, **result})


@router.get("/{slug}/addresses")
def entity_addresses(slug: str):
    """All addresses for an entity with activity metrics."""
    from .address_activity_service import get_entity_addresses_with_activity
    result = get_entity_addresses_with_activity(slug)
    if not result:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Entity not found"})
    return JSONResponse(content={"ok": True, **result})


@router.get("/{slug}/address-activity")
def entity_address_activity(slug: str):
    """Detailed activity breakdown — token exposure, counterparty graph, DEX activity."""
    from .address_activity_service import get_entity_address_activity_detail
    result = get_entity_address_activity_detail(slug)
    if not result:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Entity not found"})
    return JSONResponse(content={"ok": True, **result})


# ══════════════════════════════════════════════════════════
#  PHASE 3 — Holdings Engine
# ══════════════════════════════════════════════════════════

@router.post("/holdings/build-all")
def build_all_holdings():
    """Build holdings for all entities. Returns summary stats."""
    from .holdings_service import build_all_entity_holdings
    result = build_all_entity_holdings()
    return JSONResponse(content={"ok": True, **result})


@router.get("/holdings/overview")
def holdings_overview():
    """Overview of all entity holdings — leaderboard."""
    from .holdings_service import get_holdings_overview
    result = get_holdings_overview()
    return JSONResponse(content={"ok": True, **result})


# ══════════════════════════════════════════════════════════
#  PHASE 4 — Flow Engine
# ══════════════════════════════════════════════════════════

@router.post("/flows/build-all")
def build_all_flows():
    """Build flows for all entities. Returns summary stats."""
    from .flow_service import build_all_entity_flows
    result = build_all_entity_flows()
    return JSONResponse(content={"ok": True, **result})


@router.get("/flows/overview")
def flows_overview():
    """Overview of all entity flows — volume leaderboard."""
    from .flow_service import get_flows_overview
    result = get_flows_overview()
    return JSONResponse(content={"ok": True, **result})


@router.get("/{slug}/net-flow")
def entity_net_flow(slug: str):
    """Net flow summary — inflow/outflow/net across all time windows."""
    from .flow_service import get_entity_net_flow
    result = get_entity_net_flow(slug)
    if not result:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Entity not found"})
    return JSONResponse(content={"ok": True, **result})


@router.get("/{slug}/flows")
def entity_flows(slug: str):
    """Full flow data — windows, token flows, exchange interactions."""
    from .flow_service import get_entity_flows_full
    result = get_entity_flows_full(slug)
    if not result:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Entity not found"})
    return JSONResponse(content={"ok": True, **result})


@router.get("/{slug}/token-flows")
def entity_token_flows(slug: str):
    """Token-level flow breakdown for an entity."""
    from .flow_service import get_entity_token_flows
    result = get_entity_token_flows(slug)
    if not result:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Entity not found"})
    return JSONResponse(content={"ok": True, **result})


# ══════════════════════════════════════════════════════════
#  PHASE 5 — Token Flow Matrix
# ══════════════════════════════════════════════════════════

@router.post("/token-matrix/build-all")
def build_all_matrices():
    """Build token flow matrices for all entities."""
    from .token_matrix_service import build_all_token_matrices
    result = build_all_token_matrices()
    return JSONResponse(content={"ok": True, **result})


@router.get("/token-matrix/overview")
def token_matrix_overview():
    """Cross-entity token analysis — most traded tokens across all entities."""
    from .token_matrix_service import get_token_matrix_overview
    result = get_token_matrix_overview()
    return JSONResponse(content={"ok": True, **result})


@router.get("/{slug}/token-matrix")
def entity_token_matrix(slug: str):
    """Token flow matrix — role classification, dominance, dependency analysis."""
    from .token_matrix_service import get_entity_token_matrix
    result = get_entity_token_matrix(slug)
    if not result:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Entity not found"})
    return JSONResponse(content={"ok": True, **result})


# ══════════════════════════════════════════════════════════
#  PHASE 6 — Behaviour Engine
# ══════════════════════════════════════════════════════════

@router.post("/behaviour/build-all")
def build_all_behaviours():
    """Build behaviour classifications for all entities."""
    from .behaviour_service import build_all_behaviours
    result = build_all_behaviours()
    return JSONResponse(content={"ok": True, **result})


@router.get("/behaviour/overview")
def behaviour_overview():
    """Overview of all entity behaviours — type distribution."""
    from .behaviour_service import get_behaviour_overview
    result = get_behaviour_overview()
    return JSONResponse(content={"ok": True, **result})


# ══════════════════════════════════════════════════════════
#  PHASE 7 — Similarity Engine
# ══════════════════════════════════════════════════════════

@router.post("/similarity/build-all")
def build_all_similarities():
    """Build similarity rankings for all entities."""
    from .similarity_service import build_all_similarities
    result = build_all_similarities()
    return JSONResponse(content={"ok": True, **result})


@router.get("/similarity-map")
def similarity_map():
    """Cross-entity similarity map — clusters and top pairs."""
    from .similarity_service import get_similarity_map
    result = get_similarity_map()
    return JSONResponse(content={"ok": True, **result})


# ══════════════════════════════════════════════════════════
#  PHASE 8 — Clustering Engine
# ══════════════════════════════════════════════════════════

@router.post("/clusters/build-all")
def build_all_clusters():
    """Build wallet clusters for all entities."""
    from .clustering_service import build_all_clusters
    result = build_all_clusters()
    return JSONResponse(content={"ok": True, **result})


@router.get("/clusters/overview")
def clusters_overview():
    """Overview of all entity clusters — coverage expansion."""
    from .clustering_service import get_clusters_overview
    result = get_clusters_overview()
    return JSONResponse(content={"ok": True, **result})


# ══════════════════════════════════════════════════════════
#  PHASE 9 — Attribution Engine
# ══════════════════════════════════════════════════════════

@router.post("/attributions/build-all")
def build_all_attributions():
    """Build attribution hypotheses for all clusters."""
    from .attribution_service import build_all_attributions
    result = build_all_attributions()
    return JSONResponse(content={"ok": True, **result})


@router.get("/candidates")
def entity_candidates():
    """Entity candidates — clusters with attribution hypotheses."""
    from .attribution_service import get_entity_candidates
    result = get_entity_candidates()
    return JSONResponse(content={"ok": True, **result})


@router.get("/clusters/{cluster_id}/attribution")
def cluster_attribution(cluster_id: str):
    """Attribution hypothesis for a specific cluster."""
    from .attribution_service import get_cluster_attribution
    result = get_cluster_attribution(cluster_id)
    if not result:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Cluster not found"})
    return JSONResponse(content={"ok": True, **result})


# ══════════════════════════════════════════════════════════
#  PHASE 11 — Multichain Expansion
# ══════════════════════════════════════════════════════════

@router.post("/chains/build-all")
def build_all_chains():
    """Build multichain profiles for all entities."""
    from .multichain_service import build_all_chains
    result = build_all_chains()
    return JSONResponse(content={"ok": True, **result})


@router.get("/chains/overview")
def chains_overview():
    """Multichain overview — chain coverage across all entities."""
    from .multichain_service import get_chains_overview
    result = get_chains_overview()
    return JSONResponse(content={"ok": True, **result})


# ══════════════════════════════════════════════════════════
#  PHASE 12 — Entity Discovery Engine
# ══════════════════════════════════════════════════════════

@router.post("/discovery/build")
def build_discovery():
    """Run the discovery engine — find new entity candidates."""
    from .discovery_service import build_discovery
    result = build_discovery()
    return JSONResponse(content={"ok": True, **result})


@router.get("/discovery")
def discovery_candidates():
    """Entity discovery candidates — new market actors detected."""
    from .discovery_service import get_discovery_candidates
    result = get_discovery_candidates()
    return JSONResponse(content={"ok": True, **result})


@router.get("/discovery/{cluster_id}")
def discovery_detail(cluster_id: str):
    """Discovery details for a specific cluster candidate."""
    from .discovery_service import get_discovery_detail
    result = get_discovery_detail(cluster_id)
    if not result:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Discovery candidate not found"})
    return JSONResponse(content={"ok": True, **result})


@router.get("/{slug}/chains")
def entity_chains(slug: str):
    """Multichain profile — chain distribution, cross-chain flows, bridges."""
    from .multichain_service import get_entity_chains
    result = get_entity_chains(slug)
    if not result:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Entity not found"})
    return JSONResponse(content={"ok": True, **result})


@router.get("/{slug}/cluster-attributions")
def entity_cluster_attributions(slug: str):
    """All cluster attributions for a specific entity."""
    from .attribution_service import get_entity_cluster_attributions
    result = get_entity_cluster_attributions(slug)
    if not result:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Entity not found"})
    return JSONResponse(content={"ok": True, **result})


@router.get("/{slug}/clusters")
def entity_clusters(slug: str):
    """Wallet clusters — discovered addresses, tiers, confidence."""
    from .clustering_service import get_entity_clusters
    result = get_entity_clusters(slug)
    if not result:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Entity not found"})
    return JSONResponse(content={"ok": True, **result})


@router.get("/{slug}/similar")
def entity_similar(slug: str):
    """Similar entities — ranked by composite similarity score."""
    from .similarity_service import get_entity_similar
    result = get_entity_similar(slug)
    if not result:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Entity not found"})
    return JSONResponse(content={"ok": True, **result})


@router.get("/{slug}/behaviour")
def entity_behaviour(slug: str):
    """Behaviour classification — type, confidence, drivers, signals."""
    from .behaviour_service import get_entity_behaviour
    result = get_entity_behaviour(slug)
    if not result:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Entity not found"})
    return JSONResponse(content={"ok": True, **result})


@router.get("/{slug}/holdings")
def entity_holdings(slug: str):
    """Real token holdings for an entity — balances, USD values, portfolio structure."""
    from .holdings_service import get_entity_holdings
    result = get_entity_holdings(slug)
    if not result:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Entity not found"})
    return JSONResponse(content={"ok": True, **result})


@router.get("/{slug}/portfolio")
def entity_portfolio(slug: str):
    """Portfolio analysis — class distribution, concentration, risk flags."""
    from .holdings_service import get_entity_portfolio
    result = get_entity_portfolio(slug)
    if not result:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Entity not found"})
    return JSONResponse(content={"ok": True, **result})


@router.get("/{slug}")
def entity_detail(slug: str):
    """Get single entity with all addresses."""
    from .service import get_entity
    entity = get_entity(slug)
    if not entity:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Entity not found"})
    return JSONResponse(content={"ok": True, "entity": entity})


# ══════════════════════════════════════════════════════════
#  PHASE E-UI — Actor Intelligence Extensions
# ══════════════════════════════════════════════════════════

@router.get("/{slug}/impact")
def entity_impact(slug: str):
    """Actor market impact — portfolio, flow, network, exchange influence."""
    from .actor_intelligence_service import get_entity_impact
    result = get_entity_impact(slug)
    if not result:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Entity not found"})
    return JSONResponse(content={"ok": True, **result})


@router.get("/{slug}/timeline")
def entity_timeline(slug: str):
    """Entity timeline — temporal activity stream (flows, shifts, events)."""
    from .actor_intelligence_service import get_entity_timeline
    result = get_entity_timeline(slug)
    if not result:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Entity not found"})
    return JSONResponse(content={"ok": True, **result})


@router.get("/{slug}/interactions")
def entity_interactions(slug: str):
    """Interaction network — entity relationships (exchanges, tokens, entities, clusters)."""
    from .actor_intelligence_service import get_entity_interactions
    result = get_entity_interactions(slug)
    if not result:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Entity not found"})
    return JSONResponse(content={"ok": True, **result})


# ══════════════════════════════════════════════════════════
#  ACTOR INTELLIGENCE LAYER
# ══════════════════════════════════════════════════════════

# Global routes MUST come before {slug} routes
@router.get("/global/actor-flows")
def actor_flows_map():
    """Cross-entity capital flow map — shows capital routing between actors."""
    from .actor_intelligence_service import get_actor_flows
    result = get_actor_flows()
    return JSONResponse(content={"ok": True, **result})


@router.get("/global/pressure-map")
def pressure_map():
    """Actor vs Actor pressure map — bullish/bearish/neutral actors with impact weight."""
    from .actor_intelligence_service import get_pressure_map
    result = get_pressure_map()
    return JSONResponse(content={"ok": True, **result})


@router.get("/{slug}/intelligence")
def entity_intelligence(slug: str):
    """Unified actor intelligence — pressure, strategy, conviction, regime, playbook, tags, highlights, summary."""
    from .actor_intelligence_service import get_entity_intelligence
    result = get_entity_intelligence(slug)
    if not result:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Entity not found"})
    return JSONResponse(content={"ok": True, **result})


@router.get("/{slug}/strategy-history")
def entity_strategy_history(slug: str, limit: int = 20):
    """Strategy drift timeline — adaptive snapshots of intelligence state changes."""
    from .actor_intelligence_service import get_strategy_history
    history = get_strategy_history(slug, limit)
    return JSONResponse(content={"ok": True, "entity": slug, "history": history, "count": len(history)})


@router.get("/{slug}/token-pressure")
def entity_token_pressure(slug: str):
    """Per-token pressure analysis — bullish/bearish/neutral per token."""
    from .actor_intelligence_service import _load_entity_data, compute_token_pressure
    data = _load_entity_data(slug)
    if not data:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Entity not found"})
    tokens = compute_token_pressure(data)
    return JSONResponse(content={"ok": True, "slug": slug, "tokens": tokens, "count": len(tokens)})
