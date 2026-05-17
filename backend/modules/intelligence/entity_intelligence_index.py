"""
Entity Intelligence Index
=========================

Единый интеллектуальный индекс каждой сущности.
Агрегирует все сигналы в один Intelligence Score.

Компоненты индекса:
1. influence_score - Graph influence (pagerank, degree, betweenness)
2. momentum_score - Momentum engine score
3. narrative_alignment - Связь с активными нарративами
4. activity_level - Активность (events, news, funding)
5. investor_strength - Сила инвесторской базы

Формула:
intelligence_score = 
    0.25 * influence
  + 0.20 * momentum
  + 0.20 * narrative_alignment
  + 0.20 * activity_level
  + 0.15 * investor_strength

Collections:
    entity_intelligence_index - Текущий индекс
    
APIs:
    /api/intelligence/top - Top entities by score
    /api/intelligence/entity/{id} - Entity intelligence profile
    /api/intelligence/narrative/{topic} - Narrative leaders
    /api/intelligence/emerging - Fastest growing entities
"""

import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Intelligence score weights
INTELLIGENCE_WEIGHTS = {
    "influence": 0.25,
    "momentum": 0.20,
    "narrative_alignment": 0.20,
    "activity_level": 0.20,
    "investor_strength": 0.15
}

# Known narratives for alignment scoring
ACTIVE_NARRATIVES = [
    "AI", "RWA", "Restaking", "DePIN", "L2", "ZK",
    "DeFi", "NFT", "Gaming", "Modular", "Bitcoin L2",
    "Liquid Staking", "Intent", "Account Abstraction"
]


class EntityIntelligenceIndex:
    """
    Builds and maintains the Entity Intelligence Index.
    Provides the most comprehensive view of entity importance.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        
        # Main index collection
        self.index = db.entity_intelligence_index
        
        # Source collections
        self.graph_nodes = db.graph_nodes
        self.graph_edges = db.graph_edges
        self.momentum = db.entity_momentum
        self.narratives = db.narratives
        self.narrative_entities = db.narrative_entities
        self.events = db.news_events
        self.event_entities = db.event_entities
        self.funding_rounds = db.cryptorank_funding
        self.projects = db.intel_projects
    
    async def ensure_indexes(self):
        """Create indexes for the intelligence index collection."""
        await self.index.create_index("entity_key", unique=True)
        await self.index.create_index("entity_type")
        await self.index.create_index("score", background=True)
        await self.index.create_index("influence", background=True)
        await self.index.create_index("momentum", background=True)
        await self.index.create_index([("narratives", 1)])
        await self.index.create_index("updated_at")
        
        logger.info("[IntelligenceIndex] Indexes created")
    
    # ═══════════════════════════════════════════════════════════════
    # SCORE CALCULATION
    # ═══════════════════════════════════════════════════════════════
    
    async def calculate_entity_intelligence(
        self,
        entity_type: str,
        entity_id: str
    ) -> Dict[str, Any]:
        """
        Calculate full intelligence index for a single entity.
        Returns comprehensive profile.
        """
        entity_key = f"{entity_type}:{entity_id}"
        now = datetime.now(timezone.utc)
        
        # Get graph node
        node = await self.graph_nodes.find_one({
            "entity_type": entity_type,
            "entity_id": entity_id
        })
        
        if not node:
            return {
                "entity_key": entity_key,
                "score": 0,
                "error": "Entity not found in graph"
            }
        
        node_id = node.get("id")
        label = node.get("label", entity_id)
        
        # Calculate all components
        influence = await self._calculate_influence(node_id, node)
        momentum = await self._get_momentum_score(entity_key)
        narrative_alignment = await self._calculate_narrative_alignment(entity_type, entity_id)
        activity_level = await self._calculate_activity_level(entity_type, entity_id)
        investor_strength = await self._calculate_investor_strength(node_id, entity_type)
        
        # Calculate weighted intelligence score
        score = (
            INTELLIGENCE_WEIGHTS["influence"] * influence +
            INTELLIGENCE_WEIGHTS["momentum"] * momentum +
            INTELLIGENCE_WEIGHTS["narrative_alignment"] * narrative_alignment +
            INTELLIGENCE_WEIGHTS["activity_level"] * activity_level +
            INTELLIGENCE_WEIGHTS["investor_strength"] * investor_strength
        )
        
        # Get associated narratives
        narratives = await self._get_entity_narratives(entity_type, entity_id)
        
        # Build profile
        profile = {
            "entity_key": entity_key,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "label": label,
            "score": round(score, 2),
            "influence": round(influence, 2),
            "momentum": round(momentum, 2),
            "narrative_alignment": round(narrative_alignment, 2),
            "activity_level": round(activity_level, 2),
            "investor_strength": round(investor_strength, 2),
            "narratives": narratives,
            "tier": self._calculate_tier(score),
            "updated_at": now.isoformat()
        }
        
        # Store in index
        await self.index.update_one(
            {"entity_key": entity_key},
            {"$set": profile},
            upsert=True
        )
        
        logger.debug(f"[IntelligenceIndex] {entity_key}: score={score:.2f}")
        
        return profile
    
    async def _calculate_influence(
        self,
        node_id: str,
        node: Dict
    ) -> float:
        """
        Calculate graph influence score.
        Uses: degree centrality, hub connections, tier investors.
        """
        # Degree centrality (number of connections)
        edge_count = await self.graph_edges.count_documents({
            "$or": [
                {"from_node_id": node_id},
                {"to_node_id": node_id}
            ]
        })
        
        # Normalize degree: 50 edges = 0.5, 100+ = 1.0
        degree_score = min(1.0, edge_count / 100)
        
        # Check connections to tier-1 entities
        tier1_entities = [
            "bitcoin", "ethereum", "solana", "arbitrum",
            "a16z", "paradigm", "polychain", "sequoia",
            "binance", "coinbase"
        ]
        
        tier1_connections = 0
        for entity in tier1_entities:
            connected = await self.graph_edges.count_documents({
                "$or": [
                    {"from_node_id": node_id, "to_node_id": {"$regex": entity, "$options": "i"}},
                    {"to_node_id": node_id, "from_node_id": {"$regex": entity, "$options": "i"}}
                ]
            })
            if connected > 0:
                tier1_connections += 1
        
        # Tier1 score: connected to 5+ tier1 = 1.0
        tier1_score = min(1.0, tier1_connections / 5)
        
        # Get importance from node metadata if available
        importance = node.get("metadata", {}).get("importance", 0.5)
        
        # Combined influence: 40% degree, 40% tier1 connections, 20% importance
        influence = 0.4 * degree_score + 0.4 * tier1_score + 0.2 * importance
        
        return influence * 100  # Scale to 0-100
    
    async def _get_momentum_score(self, entity_key: str) -> float:
        """Get momentum score from momentum engine."""
        momentum_doc = await self.momentum.find_one(
            {"entity_key": entity_key},
            {"momentum_score": 1}
        )
        
        if momentum_doc:
            return momentum_doc.get("momentum_score", 0)
        
        return 0
    
    async def _calculate_narrative_alignment(
        self,
        entity_type: str,
        entity_id: str
    ) -> float:
        """
        Calculate alignment with active narratives.
        
        Uses Entity Narrative Score Engine:
        Entity → Event → Topic → Narrative (правильный pipeline)
        """
        try:
            from modules.intelligence.entity_narrative_score import get_narrative_score_engine
            
            engine = get_narrative_score_engine(self.db)
            score_data = await engine.get_entity_score(entity_type, entity_id)
            
            if score_data and score_data.get("total_score", 0) > 0:
                return score_data.get("total_score", 0)
        except Exception as e:
            logger.debug(f"[IntelligenceIndex] Narrative score failed for {entity_id}: {e}")
        
        # Fallback to old method if new engine fails
        entity_key = f"{entity_type}:{entity_id}"
        
        # Get narratives this entity is linked to
        narrative_links = await self.narrative_entities.find({
            "$or": [
                {"entity_key": entity_key},
                {"entity_id": entity_id}
            ]
        }).to_list(50)
        
        if not narrative_links:
            # Fallback: check project tags/categories
            project = await self.projects.find_one({"slug": entity_id})
            if project:
                categories = project.get("categories", [])
                tags = project.get("tags", [])
                
                # Check if any match active narratives
                matches = 0
                for narrative in ACTIVE_NARRATIVES:
                    narrative_lower = narrative.lower()
                    if any(narrative_lower in str(c).lower() for c in categories):
                        matches += 1
                    if any(narrative_lower in str(t).lower() for t in tags):
                        matches += 1
                
                return min(100, matches * 20)  # 5 matches = 100
            
            return 0
        
        # Count alignment with active narratives
        aligned_count = 0
        for link in narrative_links:
            narrative_name = link.get("narrative_name", "")
            for active in ACTIVE_NARRATIVES:
                if active.lower() in narrative_name.lower():
                    aligned_count += 1
                    break
        
        # Normalize: 3 active narrative alignments = 100
        return min(100, aligned_count * 33)
    
    async def _calculate_activity_level(
        self,
        entity_type: str,
        entity_id: str
    ) -> float:
        """
        Calculate activity level based on real events.
        
        Uses Entity Activity Engine:
        - Funding rounds
        - Partnerships
        - Product launches
        - Token unlocks
        """
        try:
            from modules.intelligence.entity_activity_engine import get_activity_engine
            
            engine = get_activity_engine(self.db)
            activity_data = await engine.get_entity_activity(entity_type, entity_id)
            
            if activity_data and activity_data.get("total_score", 0) > 0:
                return activity_data.get("total_score", 0)
        except Exception as e:
            logger.debug(f"[IntelligenceIndex] Activity score failed for {entity_id}: {e}")
        
        # Fallback to old method
        now = datetime.now(timezone.utc)
        day_30_ago = now - timedelta(days=30)
        entity_key = f"{entity_type}:{entity_id}"
        
        # Count recent events
        event_count = await self.event_entities.count_documents({
            "entity_key": entity_key,
            "event_date": {"$gte": day_30_ago}
        })
        
        # Also check news_events
        news_count = await self.events.count_documents({
            "primary_assets": {"$regex": entity_id, "$options": "i"},
            "created_at": {"$gte": day_30_ago}
        })
        
        # Check funding activity
        funding_count = 0
        if entity_type == "project":
            funding_count = await self.funding_rounds.count_documents({
                "project_slug": entity_id,
                "date": {"$gte": day_30_ago.isoformat()}
            })
        elif entity_type == "fund":
            funding_count = await self.funding_rounds.count_documents({
                "lead_investors": {"$regex": entity_id, "$options": "i"},
                "date": {"$gte": day_30_ago.isoformat()}
            })
        
        total_activity = event_count + news_count + funding_count * 3  # Weight funding higher
        
        # Normalize: 30 activities in 30 days = 100
        return min(100, total_activity * 3.33)
    
    async def _calculate_investor_strength(
        self,
        node_id: str,
        entity_type: str
    ) -> float:
        """
        Calculate investor strength.
        For projects: quality of investors
        For funds: portfolio quality
        """
        if entity_type == "project":
            # Get investors
            investor_edges = await self.graph_edges.find({
                "to_node_id": node_id,
                "relation_type": "invested_in"
            }).to_list(50)
            
            if not investor_edges:
                return 0
            
            # Check for tier-1 investors
            tier1_investors = [
                "a16z", "paradigm", "polychain", "sequoia", "multicoin",
                "binance", "coinbase", "pantera", "framework", "dragonfly"
            ]
            
            tier1_count = 0
            total_investors = len(investor_edges)
            
            for edge in investor_edges:
                from_id = edge.get("from_node_id", "").lower()
                for tier1 in tier1_investors:
                    if tier1 in from_id:
                        tier1_count += 1
                        break
            
            # Score: tier1 percentage * 2 (capped at 100)
            if total_investors > 0:
                tier1_ratio = tier1_count / total_investors
                return min(100, tier1_ratio * 200 + total_investors * 2)
            
            return 0
            
        elif entity_type == "fund":
            # Get portfolio
            portfolio_edges = await self.graph_edges.find({
                "from_node_id": node_id,
                "relation_type": "invested_in"
            }).to_list(100)
            
            if not portfolio_edges:
                return 0
            
            # Portfolio size score
            portfolio_size = len(portfolio_edges)
            
            # Check for investments in top projects
            top_projects = [
                "bitcoin", "ethereum", "solana", "arbitrum", "optimism",
                "polygon", "uniswap", "aave", "compound", "chainlink"
            ]
            
            top_count = 0
            for edge in portfolio_edges:
                to_id = edge.get("to_node_id", "").lower()
                for top in top_projects:
                    if top in to_id:
                        top_count += 1
                        break
            
            # Score based on portfolio size and quality
            return min(100, portfolio_size + top_count * 10)
        
        return 50  # Default for other types
    
    async def _get_entity_narratives(
        self,
        entity_type: str,
        entity_id: str
    ) -> List[str]:
        """Get list of narratives this entity is associated with."""
        entity_key = f"{entity_type}:{entity_id}"
        
        narrative_links = await self.narrative_entities.find({
            "$or": [
                {"entity_key": entity_key},
                {"entity_id": entity_id}
            ]
        }, {"narrative_name": 1}).to_list(10)
        
        narratives = [link.get("narrative_name") for link in narrative_links if link.get("narrative_name")]
        
        if not narratives:
            # Try to infer from project categories
            project = await self.projects.find_one({"slug": entity_id})
            if project:
                categories = project.get("categories", [])
                for cat in categories[:5]:
                    narratives.append(str(cat))
        
        return narratives[:5]  # Limit to top 5
    
    def _calculate_tier(self, score: float) -> str:
        """Calculate tier based on score."""
        if score >= 80:
            return "S"
        elif score >= 60:
            return "A"
        elif score >= 40:
            return "B"
        elif score >= 20:
            return "C"
        else:
            return "D"
    
    # ═══════════════════════════════════════════════════════════════
    # BATCH UPDATE
    # ═══════════════════════════════════════════════════════════════
    
    async def update_all_entities(
        self,
        entity_types: List[str] = None,
        limit: int = 500
    ) -> Dict[str, Any]:
        """
        Batch update intelligence index for all entities.
        Called by scheduler.
        """
        start = datetime.now(timezone.utc)
        
        if entity_types is None:
            entity_types = ["project", "fund", "person", "exchange"]
        
        results = {
            "processed": 0,
            "errors": 0,
            "by_type": {}
        }
        
        for entity_type in entity_types:
            type_count = 0
            
            # Get entities from graph
            cursor = self.graph_nodes.find({
                "entity_type": entity_type
            }).limit(limit // len(entity_types))
            
            async for node in cursor:
                try:
                    await self.calculate_entity_intelligence(
                        entity_type,
                        node.get("entity_id")
                    )
                    type_count += 1
                    results["processed"] += 1
                except Exception as e:
                    logger.error(f"[IntelligenceIndex] Error for {node.get('entity_id')}: {e}")
                    results["errors"] += 1
            
            results["by_type"][entity_type] = type_count
        
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        results["elapsed_seconds"] = round(elapsed, 2)
        
        logger.info(f"[IntelligenceIndex] Updated {results['processed']} entities in {elapsed:.1f}s")
        
        return results
    
    # ═══════════════════════════════════════════════════════════════
    # QUERY METHODS
    # ═══════════════════════════════════════════════════════════════
    
    async def get_top_entities(
        self,
        entity_type: str = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get top entities by intelligence score."""
        query = {}
        if entity_type:
            query["entity_type"] = entity_type
        
        cursor = self.index.find(
            query,
            {"_id": 0}
        ).sort("score", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_entity_profile(
        self,
        entity_type: str,
        entity_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get intelligence profile for a specific entity."""
        entity_key = f"{entity_type}:{entity_id}"
        
        profile = await self.index.find_one(
            {"entity_key": entity_key},
            {"_id": 0}
        )
        
        if not profile:
            # Calculate on demand
            profile = await self.calculate_entity_intelligence(entity_type, entity_id)
        
        return profile
    
    async def get_narrative_leaders(
        self,
        narrative: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top entities for a specific narrative."""
        # Find entities with this narrative
        cursor = self.index.find(
            {"narratives": {"$regex": narrative, "$options": "i"}},
            {"_id": 0}
        ).sort("score", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_emerging_entities(
        self,
        entity_type: str = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get emerging entities (high momentum, growing activity).
        Cross-reference with momentum velocity.
        """
        # Get entities with high momentum velocity
        momentum_query = {"momentum_velocity": {"$gt": 5}}
        if entity_type:
            momentum_query["entity_type"] = entity_type
        
        growing = await self.momentum.find(
            momentum_query,
            {"entity_key": 1}
        ).sort("momentum_velocity", -1).limit(limit * 2).to_list(limit * 2)
        
        entity_keys = [m["entity_key"] for m in growing]
        
        if not entity_keys:
            return []
        
        # Get intelligence profiles for these
        cursor = self.index.find(
            {"entity_key": {"$in": entity_keys}},
            {"_id": 0}
        ).sort("score", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_tier_entities(
        self,
        tier: str,
        entity_type: str = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get entities by tier."""
        query = {"tier": tier.upper()}
        if entity_type:
            query["entity_type"] = entity_type
        
        cursor = self.index.find(
            query,
            {"_id": 0}
        ).sort("score", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get intelligence index statistics."""
        total = await self.index.count_documents({})
        
        # Distribution by tier
        tier_pipeline = [
            {"$group": {
                "_id": "$tier",
                "count": {"$sum": 1},
                "avg_score": {"$avg": "$score"}
            }}
        ]
        tier_stats = await self.index.aggregate(tier_pipeline).to_list(10)
        
        # Distribution by type
        type_pipeline = [
            {"$group": {
                "_id": "$entity_type",
                "count": {"$sum": 1},
                "avg_score": {"$avg": "$score"},
                "max_score": {"$max": "$score"}
            }}
        ]
        type_stats = await self.index.aggregate(type_pipeline).to_list(10)
        
        # Top narratives
        narrative_pipeline = [
            {"$unwind": "$narratives"},
            {"$group": {
                "_id": "$narratives",
                "count": {"$sum": 1},
                "avg_score": {"$avg": "$score"}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        narrative_stats = await self.index.aggregate(narrative_pipeline).to_list(10)
        
        return {
            "total_indexed": total,
            "by_tier": {
                stat["_id"]: {
                    "count": stat["count"],
                    "avg_score": round(stat["avg_score"], 1)
                }
                for stat in tier_stats if stat["_id"]
            },
            "by_type": {
                stat["_id"]: {
                    "count": stat["count"],
                    "avg_score": round(stat["avg_score"], 1),
                    "max_score": round(stat["max_score"], 1)
                }
                for stat in type_stats if stat["_id"]
            },
            "top_narratives": [
                {
                    "narrative": stat["_id"],
                    "entities": stat["count"],
                    "avg_score": round(stat["avg_score"], 1)
                }
                for stat in narrative_stats if stat["_id"]
            ],
            "weights": INTELLIGENCE_WEIGHTS
        }


# ═══════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════

_intelligence_index: Optional[EntityIntelligenceIndex] = None


def get_intelligence_index(db: AsyncIOMotorDatabase = None) -> EntityIntelligenceIndex:
    """Get or create intelligence index instance."""
    global _intelligence_index
    if db is not None:
        _intelligence_index = EntityIntelligenceIndex(db)
    return _intelligence_index


def set_intelligence_index_db(db: AsyncIOMotorDatabase):
    """Set database for intelligence index."""
    global _intelligence_index
    _intelligence_index = EntityIntelligenceIndex(db)
