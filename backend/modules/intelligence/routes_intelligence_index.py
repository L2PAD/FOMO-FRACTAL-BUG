"""
Entity Intelligence Index API Routes
=====================================

API endpoints for the Entity Intelligence Index.

Endpoints:
- GET /api/intelligence/top - Top entities by intelligence score
- GET /api/intelligence/entity/{type}/{id} - Entity intelligence profile
- GET /api/intelligence/narrative/{topic} - Narrative leaders
- GET /api/intelligence/emerging - Emerging entities
- GET /api/intelligence/tier/{tier} - Entities by tier (S/A/B/C/D)
- GET /api/intelligence/stats - Index statistics
- POST /api/intelligence/update - Trigger index update
"""

from fastapi import APIRouter, Query, Path
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/intelligence", tags=["Intelligence Index"])


# ═══════════════════════════════════════════════════════════════
# TOP ENTITIES
# ═══════════════════════════════════════════════════════════════

@router.get("/top")
async def get_top_entities(
    entity_type: Optional[str] = Query(None, description="Filter by type: project, fund, person, exchange"),
    limit: int = Query(20, ge=1, le=100)
) -> Dict[str, Any]:
    """
    Get top entities by intelligence score.
    
    Returns ranked list of entities with their intelligence profiles.
    """
    try:
        from server import db
        from modules.intelligence.entity_intelligence_index import get_intelligence_index
        
        index = get_intelligence_index(db)
        entities = await index.get_top_entities(entity_type, limit)
        
        return {
            "ok": True,
            "count": len(entities),
            "filter": {"entity_type": entity_type} if entity_type else None,
            "entities": entities
        }
    except Exception as e:
        logger.error(f"[IntelAPI] get_top_entities error: {e}")
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# ENTITY PROFILE
# ═══════════════════════════════════════════════════════════════

@router.get("/entity/{entity_type}/{entity_id}")
async def get_entity_profile(
    entity_type: str = Path(..., description="Entity type: project, fund, person, exchange"),
    entity_id: str = Path(..., description="Entity ID (slug)")
) -> Dict[str, Any]:
    """
    Get full intelligence profile for an entity.
    
    Returns:
    - score: Overall intelligence score (0-100)
    - influence: Graph influence score
    - momentum: Current momentum
    - narrative_alignment: Alignment with active narratives
    - activity_level: Recent activity level
    - investor_strength: Investor quality score
    - narratives: Associated narratives
    - tier: S/A/B/C/D tier classification
    """
    try:
        from server import db
        from modules.intelligence.entity_intelligence_index import get_intelligence_index
        
        index = get_intelligence_index(db)
        profile = await index.get_entity_profile(entity_type, entity_id)
        
        if profile and not profile.get("error"):
            return {"ok": True, **profile}
        else:
            return {
                "ok": False,
                "error": profile.get("error", "Entity not found")
            }
    except Exception as e:
        logger.error(f"[IntelAPI] get_entity_profile error: {e}")
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# NARRATIVE LEADERS
# ═══════════════════════════════════════════════════════════════

@router.get("/narrative/{narrative}")
async def get_narrative_leaders(
    narrative: str = Path(..., description="Narrative name: AI, RWA, L2, DeFi, etc."),
    limit: int = Query(10, ge=1, le=50)
) -> Dict[str, Any]:
    """
    Get top entities leading a specific narrative.
    
    Example narratives: AI, RWA, Restaking, DePIN, L2, ZK, DeFi
    """
    try:
        from server import db
        from modules.intelligence.entity_intelligence_index import get_intelligence_index
        
        index = get_intelligence_index(db)
        leaders = await index.get_narrative_leaders(narrative, limit)
        
        return {
            "ok": True,
            "narrative": narrative,
            "count": len(leaders),
            "leaders": leaders
        }
    except Exception as e:
        logger.error(f"[IntelAPI] get_narrative_leaders error: {e}")
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# EMERGING ENTITIES
# ═══════════════════════════════════════════════════════════════

@router.get("/emerging")
async def get_emerging_entities(
    entity_type: Optional[str] = Query(None, description="Filter by type"),
    limit: int = Query(20, ge=1, le=100)
) -> Dict[str, Any]:
    """
    Get emerging entities (high momentum + growing activity).
    
    These are entities that are rapidly gaining importance in the ecosystem.
    """
    try:
        from server import db
        from modules.intelligence.entity_intelligence_index import get_intelligence_index
        
        index = get_intelligence_index(db)
        emerging = await index.get_emerging_entities(entity_type, limit)
        
        return {
            "ok": True,
            "count": len(emerging),
            "filter": {"entity_type": entity_type} if entity_type else None,
            "entities": emerging
        }
    except Exception as e:
        logger.error(f"[IntelAPI] get_emerging_entities error: {e}")
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# TIER CLASSIFICATION
# ═══════════════════════════════════════════════════════════════

@router.get("/tier/{tier}")
async def get_tier_entities(
    tier: str = Path(..., description="Tier: S, A, B, C, D"),
    entity_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200)
) -> Dict[str, Any]:
    """
    Get entities by tier classification.
    
    Tiers:
    - S: score >= 80 (Top tier, market leaders)
    - A: score >= 60 (High quality)
    - B: score >= 40 (Good quality)
    - C: score >= 20 (Average)
    - D: score < 20 (Low activity)
    """
    try:
        from server import db
        from modules.intelligence.entity_intelligence_index import get_intelligence_index
        
        index = get_intelligence_index(db)
        entities = await index.get_tier_entities(tier, entity_type, limit)
        
        return {
            "ok": True,
            "tier": tier.upper(),
            "count": len(entities),
            "filter": {"entity_type": entity_type} if entity_type else None,
            "entities": entities
        }
    except Exception as e:
        logger.error(f"[IntelAPI] get_tier_entities error: {e}")
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# STATISTICS
# ═══════════════════════════════════════════════════════════════

@router.get("/stats")
async def get_index_stats() -> Dict[str, Any]:
    """
    Get intelligence index statistics.
    
    Returns distribution by tier, type, and top narratives.
    """
    try:
        from server import db
        from modules.intelligence.entity_intelligence_index import get_intelligence_index
        
        index = get_intelligence_index(db)
        stats = await index.get_stats()
        
        return {"ok": True, **stats}
    except Exception as e:
        logger.error(f"[IntelAPI] get_index_stats error: {e}")
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# ADMIN: TRIGGER UPDATE
# ═══════════════════════════════════════════════════════════════

@router.post("/update")
async def trigger_index_update(
    entity_types: Optional[str] = Query(None, description="Comma-separated types"),
    limit: int = Query(500, ge=1, le=2000)
) -> Dict[str, Any]:
    """
    Trigger index update for all entities.
    
    This is normally run by scheduler, but can be triggered manually.
    """
    try:
        from server import db
        from modules.intelligence.entity_intelligence_index import get_intelligence_index
        
        index = get_intelligence_index(db)
        
        types = None
        if entity_types:
            types = [t.strip() for t in entity_types.split(",")]
        
        result = await index.update_all_entities(types, limit)
        
        return {"ok": True, **result}
    except Exception as e:
        logger.error(f"[IntelAPI] trigger_index_update error: {e}")
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# COMPARE ENTITIES
# ═══════════════════════════════════════════════════════════════

@router.get("/compare")
async def compare_entities(
    entities: str = Query(..., description="Comma-separated entity keys (type:id)")
) -> Dict[str, Any]:
    """
    Compare multiple entities side by side.
    
    Example: ?entities=project:arbitrum,project:optimism,project:base
    """
    try:
        from server import db
        from modules.intelligence.entity_intelligence_index import get_intelligence_index
        
        index = get_intelligence_index(db)
        
        entity_keys = [e.strip() for e in entities.split(",")]
        profiles = []
        
        for key in entity_keys[:10]:  # Limit to 10
            if ":" in key:
                entity_type, entity_id = key.split(":", 1)
                profile = await index.get_entity_profile(entity_type, entity_id)
                if profile and not profile.get("error"):
                    profiles.append(profile)
        
        return {
            "ok": True,
            "count": len(profiles),
            "entities": profiles
        }
    except Exception as e:
        logger.error(f"[IntelAPI] compare_entities error: {e}")
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# NARRATIVE DOMINANCE
# ═══════════════════════════════════════════════════════════════

@router.get("/narratives")
async def get_all_narratives() -> Dict[str, Any]:
    """
    Get list of all tracked narratives with metadata.
    
    Returns narrative definitions with icons, colors, and current dominance.
    """
    try:
        from server import db
        from modules.intelligence.entity_narrative_score import (
            get_narrative_score_engine,
            NARRATIVE_DEFINITIONS
        )
        
        engine = get_narrative_score_engine(db)
        dominance = await engine.get_narrative_dominance()
        
        narratives = []
        for narr_id, narr_def in NARRATIVE_DEFINITIONS.items():
            dom = dominance.get(narr_id, {})
            narratives.append({
                "id": narr_id,
                "name": narr_def.get("name"),
                "icon": narr_def.get("icon", "📊"),
                "color": narr_def.get("color", "#6B7280"),
                "keywords": narr_def.get("keywords", [])[:5],
                "leader": dom.get("leader"),
                "leader_type": dom.get("leader_type"),
                "leader_score": dom.get("score", 0)
            })
        
        # Sort by leader_score descending
        narratives.sort(key=lambda x: x.get("leader_score", 0), reverse=True)
        
        return {
            "ok": True,
            "count": len(narratives),
            "narratives": narratives
        }
    except Exception as e:
        logger.error(f"[IntelAPI] get_all_narratives error: {e}")
        return {"ok": False, "error": str(e)}


@router.get("/narrative-dominance")
async def get_narrative_dominance() -> Dict[str, Any]:
    """
    Get narrative dominance map.
    
    Shows which entity leads each narrative.
    
    Returns:
    {
        "ai_crypto": {"leader": "render", "score": 82},
        "restaking": {"leader": "eigenlayer", "score": 91},
        ...
    }
    """
    try:
        from server import db
        from modules.intelligence.entity_narrative_score import get_narrative_score_engine
        
        engine = get_narrative_score_engine(db)
        dominance = await engine.get_narrative_dominance()
        
        return {
            "ok": True,
            "narratives_count": len(dominance),
            "dominance": dominance
        }
    except Exception as e:
        logger.error(f"[IntelAPI] get_narrative_dominance error: {e}")
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# ENTITY TREND (Historical Scores)
# ═══════════════════════════════════════════════════════════════

@router.get("/entity/{entity_type}/{entity_id}/trend")
async def get_entity_trend(
    entity_type: str = Path(...),
    entity_id: str = Path(...),
    days: int = Query(30, ge=7, le=90)
) -> Dict[str, Any]:
    """
    Get historical score trend for an entity.
    
    Useful for:
    - Momentum detection
    - Trend detection
    - Bubble detection
    """
    try:
        from server import db
        from modules.intelligence.entity_narrative_score import get_narrative_score_engine
        
        engine = get_narrative_score_engine(db)
        trend = await engine.get_entity_trend(entity_type, entity_id, days)
        
        return {
            "ok": True,
            "entity_key": f"{entity_type}:{entity_id}",
            "days": days,
            "data_points": len(trend),
            "trend": trend
        }
    except Exception as e:
        logger.error(f"[IntelAPI] get_entity_trend error: {e}")
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# MOST ACTIVE ENTITIES
# ═══════════════════════════════════════════════════════════════

@router.get("/most-active")
async def get_most_active(
    entity_type: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100)
) -> Dict[str, Any]:
    """
    Get most active entities based on real events.
    
    Activity includes: funding, partnerships, launches, unlocks.
    """
    try:
        from server import db
        from modules.intelligence.entity_activity_engine import get_activity_engine
        
        engine = get_activity_engine(db)
        active = await engine.get_most_active(entity_type, limit)
        
        return {
            "ok": True,
            "count": len(active),
            "filter": {"entity_type": entity_type} if entity_type else None,
            "entities": active
        }
    except Exception as e:
        logger.error(f"[IntelAPI] get_most_active error: {e}")
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# ACCELERATING ENTITIES
# ═══════════════════════════════════════════════════════════════

@router.get("/accelerating")
async def get_accelerating(
    entity_type: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100)
) -> Dict[str, Any]:
    """
    Get entities with highest activity acceleration.
    
    These are entities where 7d activity > expected from 30d average.
    """
    try:
        from server import db
        from modules.intelligence.entity_activity_engine import get_activity_engine
        
        engine = get_activity_engine(db)
        accelerating = await engine.get_accelerating(entity_type, limit)
        
        return {
            "ok": True,
            "count": len(accelerating),
            "filter": {"entity_type": entity_type} if entity_type else None,
            "entities": accelerating
        }
    except Exception as e:
        logger.error(f"[IntelAPI] get_accelerating error: {e}")
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# BOOTSTRAP ENGINES
# ═══════════════════════════════════════════════════════════════

@router.post("/bootstrap")
async def bootstrap_all_engines(
    limit: int = Query(300, ge=1, le=1000)
) -> Dict[str, Any]:
    """
    Bootstrap all intelligence engines.
    
    Runs in sequence:
    1. Narrative Score Engine
    2. Activity Engine
    3. Intelligence Index
    """
    try:
        from server import db
        from modules.intelligence.entity_narrative_score import get_narrative_score_engine
        from modules.intelligence.entity_activity_engine import get_activity_engine
        from modules.intelligence.entity_intelligence_index import get_intelligence_index
        
        results = {}
        
        # 1. Narrative Scores
        logger.info("[Bootstrap] Starting Narrative Score Engine...")
        narrative_engine = get_narrative_score_engine(db)
        narrative_result = await narrative_engine.update_all_entities(limit=limit)
        results["narrative_scores"] = narrative_result
        
        # 2. Activity Scores
        logger.info("[Bootstrap] Starting Activity Engine...")
        activity_engine = get_activity_engine(db)
        activity_result = await activity_engine.update_all_entities(limit=limit)
        results["activity_scores"] = activity_result
        
        # 3. Intelligence Index (uses above scores)
        logger.info("[Bootstrap] Starting Intelligence Index...")
        index = get_intelligence_index(db)
        index_result = await index.update_all_entities(limit=limit)
        results["intelligence_index"] = index_result
        
        return {"ok": True, **results}
    except Exception as e:
        logger.error(f"[IntelAPI] bootstrap error: {e}")
        return {"ok": False, "error": str(e)}

