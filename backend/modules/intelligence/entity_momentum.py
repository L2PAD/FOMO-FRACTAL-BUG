"""
Entity Momentum Engine
======================

Tracks which entities are gaining structural influence in the system.
Not price. Not just news. STRUCTURAL presence across multiple layers.

Question this answers:
"Which entities are becoming centers of activity?"

Signals used:
1. Event frequency (events_7d, events_30d, growth_ratio)
2. Graph expansion (new_edges_7d, new_neighbors_7d)
3. Narrative exposure (narratives_count, narrative_momentum)
4. Investor activity (new_funds, new_rounds, new_investors)
5. Intelligence edges (event_linked, topic_connections)

Formula:
momentum_score = 
    0.30 * event_growth
  + 0.25 * graph_growth
  + 0.20 * narrative_exposure
  + 0.15 * investor_activity
  + 0.10 * intelligence_links

Collections:
    entity_momentum - Current momentum scores
    entity_momentum_history - Time series for tracking

Use cases:
- Top momentum entities ranking
- Narrative → top entities
- Fund → high momentum portfolio
- Ecosystem hubs detection
"""

import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Momentum calculation weights
WEIGHTS = {
    "event_growth": 0.30,
    "graph_growth": 0.25,
    "narrative_exposure": 0.20,
    "investor_activity": 0.15,
    "intelligence_links": 0.10
}

# Time decay factor (lambda for exponential decay)
DECAY_LAMBDA = 0.05  # ~14 days half-life


class EntityMomentumEngine:
    """
    Engine for calculating and tracking entity momentum.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.momentum = db.entity_momentum
        self.momentum_history = db.entity_momentum_history
        
        # Graph collections
        self.graph_nodes = db.graph_nodes
        self.graph_edges = db.graph_edges
        self.derived_edges = db.graph_derived_edges
        self.intelligence_edges = db.graph_intelligence_edges
        
        # Event collections
        self.events = db.news_events
        self.event_entities = db.event_entities
        
        # Narrative collections
        self.narratives = db.narratives
        self.narrative_entities = db.narrative_entities
    
    async def ensure_indexes(self):
        """Create indexes for momentum collections"""
        await self.momentum.create_index("entity_key", unique=True)
        await self.momentum.create_index("entity_type")
        await self.momentum.create_index("momentum_score")
        await self.momentum.create_index("updated_at")
        
        await self.momentum_history.create_index([("entity_key", 1), ("date", -1)])
        await self.momentum_history.create_index("date")
        
        logger.info("[MomentumEngine] Indexes created")
    
    async def calculate_momentum(
        self,
        entity_type: str,
        entity_id: str
    ) -> Dict[str, Any]:
        """
        Calculate momentum score for a single entity.
        Returns detailed breakdown of all signals.
        """
        entity_key = f"{entity_type}:{entity_id}"
        now = datetime.now(timezone.utc)
        
        # Find graph node
        node = await self.graph_nodes.find_one({
            "entity_type": entity_type,
            "entity_id": entity_id
        })
        
        if not node:
            return {
                "entity_key": entity_key,
                "momentum_score": 0,
                "error": "Entity not found in graph"
            }
        
        node_id = node["id"]
        
        # Calculate each signal
        event_growth = await self._calculate_event_growth(entity_type, entity_id)
        graph_growth = await self._calculate_graph_growth(node_id)
        narrative_exposure = await self._calculate_narrative_exposure(entity_type, entity_id)
        investor_activity = await self._calculate_investor_activity(node_id)
        intelligence_links = await self._calculate_intelligence_links(node_id)
        
        # Weighted sum
        momentum_score = (
            WEIGHTS["event_growth"] * event_growth +
            WEIGHTS["graph_growth"] * graph_growth +
            WEIGHTS["narrative_exposure"] * narrative_exposure +
            WEIGHTS["investor_activity"] * investor_activity +
            WEIGHTS["intelligence_links"] * intelligence_links
        )
        
        # Normalize to 0-100
        momentum_score = min(100, max(0, momentum_score * 100))
        
        # Calculate velocity (change from 7 days ago)
        previous = await self.momentum_history.find_one(
            {"entity_key": entity_key},
            sort=[("date", -1)]
        )
        
        momentum_velocity = 0
        if previous and previous.get("momentum_score"):
            momentum_velocity = momentum_score - previous["momentum_score"]
        
        # Build result
        result = {
            "entity_key": entity_key,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "momentum_score": round(momentum_score, 2),
            "momentum_velocity": round(momentum_velocity, 2),
            "signals": {
                "event_growth": round(event_growth, 3),
                "graph_growth": round(graph_growth, 3),
                "narrative_exposure": round(narrative_exposure, 3),
                "investor_activity": round(investor_activity, 3),
                "intelligence_links": round(intelligence_links, 3)
            },
            "weights": WEIGHTS,
            "updated_at": now
        }
        
        # Store current momentum
        await self.momentum.update_one(
            {"entity_key": entity_key},
            {"$set": result},
            upsert=True
        )
        
        # Store in history
        history_record = {
            "entity_key": entity_key,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "momentum_score": round(momentum_score, 2),
            "date": now.replace(hour=0, minute=0, second=0, microsecond=0)
        }
        
        await self.momentum_history.update_one(
            {"entity_key": entity_key, "date": history_record["date"]},
            {"$set": history_record},
            upsert=True
        )
        
        logger.debug(f"[MomentumEngine] {entity_key}: {momentum_score:.1f}")
        
        return result
    
    async def _calculate_event_growth(
        self,
        entity_type: str,
        entity_id: str
    ) -> float:
        """
        Calculate event frequency signal.
        Compares 7d vs 30d event counts.
        """
        now = datetime.now(timezone.utc)
        day_7_ago = now - timedelta(days=7)
        day_30_ago = now - timedelta(days=30)
        
        # Check event_entities collection first
        entity_key = f"{entity_type}:{entity_id}"
        
        events_7d = await self.event_entities.count_documents({
            "entity_key": entity_key,
            "event_date": {"$gte": day_7_ago}
        })
        
        events_30d = await self.event_entities.count_documents({
            "entity_key": entity_key,
            "event_date": {"$gte": day_30_ago}
        })
        
        # Also check news_events primary_assets
        events_7d += await self.events.count_documents({
            "primary_assets": {"$regex": entity_id, "$options": "i"},
            "created_at": {"$gte": day_7_ago}
        })
        
        events_30d += await self.events.count_documents({
            "primary_assets": {"$regex": entity_id, "$options": "i"},
            "created_at": {"$gte": day_30_ago}
        })
        
        if events_30d == 0:
            return 0
        
        # Growth ratio (7d vs expected from 30d average)
        expected_7d = (events_30d - events_7d) / 23 * 7  # 23 days before last 7
        
        if expected_7d <= 0:
            return min(1.0, events_7d / 10)  # Cap at 10 events
        
        growth_ratio = events_7d / expected_7d
        
        # Normalize: ratio of 2 = 1.0, ratio of 1 = 0.5
        return min(1.0, growth_ratio / 2)
    
    async def _calculate_graph_growth(self, node_id: str) -> float:
        """
        Calculate graph expansion signal.
        Measures new edges and neighbors in last 7 days.
        """
        now = datetime.now(timezone.utc)
        day_7_ago = now - timedelta(days=7)
        
        # Count new edges in all layers
        new_factual = await self.graph_edges.count_documents({
            "$or": [
                {"from_node_id": node_id},
                {"to_node_id": node_id}
            ],
            "created_at": {"$gte": day_7_ago}
        })
        
        new_derived = await self.derived_edges.count_documents({
            "$or": [
                {"from_node_id": node_id},
                {"to_node_id": node_id}
            ],
            "created_at": {"$gte": day_7_ago}
        })
        
        new_intelligence = await self.intelligence_edges.count_documents({
            "$or": [
                {"from_node_id": node_id},
                {"to_node_id": node_id}
            ],
            "created_at": {"$gte": day_7_ago}
        })
        
        total_new = new_factual + new_derived + new_intelligence
        
        # Normalize: 20 new edges = 1.0
        return min(1.0, total_new / 20)
    
    async def _calculate_narrative_exposure(
        self,
        entity_type: str,
        entity_id: str
    ) -> float:
        """
        Calculate narrative exposure signal.
        How many narratives is this entity part of.
        """
        entity_key = f"{entity_type}:{entity_id}"
        
        # Count narrative links
        narrative_count = await self.narrative_entities.count_documents({
            "$or": [
                {"entity_id": entity_id},
                {"entity_key": entity_key}
            ]
        })
        
        # Also check by entity name in narrative keywords
        if narrative_count == 0:
            # Fallback: check if entity_id appears in any narrative
            narratives_mentioning = await self.narratives.count_documents({
                "$or": [
                    {"keywords": {"$regex": entity_id, "$options": "i"}},
                    {"topics": {"$regex": entity_id, "$options": "i"}}
                ]
            })
            narrative_count = narratives_mentioning
        
        # Normalize: 5 narratives = 1.0
        return min(1.0, narrative_count / 5)
    
    async def _calculate_investor_activity(self, node_id: str) -> float:
        """
        Calculate investor activity signal.
        New investment relationships in last 30 days.
        """
        now = datetime.now(timezone.utc)
        day_30_ago = now - timedelta(days=30)
        
        # Count new investment edges (project receiving investment OR fund making investment)
        new_investments = await self.graph_edges.count_documents({
            "$or": [
                {"to_node_id": node_id, "relation_type": "invested_in"},
                {"from_node_id": node_id, "relation_type": "invested_in"}
            ],
            "created_at": {"$gte": day_30_ago}
        })
        
        # Normalize: 3 new investments = 1.0
        return min(1.0, new_investments / 3)
    
    async def _calculate_intelligence_links(self, node_id: str) -> float:
        """
        Calculate intelligence links signal.
        Event and topic connections.
        """
        # Count intelligence edges
        intelligence_count = await self.intelligence_edges.count_documents({
            "$or": [
                {"from_node_id": node_id},
                {"to_node_id": node_id}
            ]
        })
        
        # Normalize: 30 intelligence links = 1.0
        return min(1.0, intelligence_count / 30)
    
    async def apply_decay(self, days_old: float) -> float:
        """
        Apply time decay to momentum score.
        Uses exponential decay: e^(-lambda * days)
        """
        return math.exp(-DECAY_LAMBDA * days_old)
    
    async def update_all_entities(
        self,
        entity_types: List[str] = None,
        limit: int = 500
    ) -> Dict[str, Any]:
        """
        Batch update momentum for all entities.
        Called by scheduler job.
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
            
            # Get entities of this type from graph
            cursor = self.graph_nodes.find({
                "entity_type": entity_type
            }).limit(limit // len(entity_types))
            
            async for node in cursor:
                try:
                    await self.calculate_momentum(
                        entity_type,
                        node.get("entity_id")
                    )
                    type_count += 1
                    results["processed"] += 1
                except Exception as e:
                    logger.error(f"[MomentumEngine] Error for {node.get('entity_id')}: {e}")
                    results["errors"] += 1
            
            results["by_type"][entity_type] = type_count
        
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        results["elapsed_seconds"] = round(elapsed, 2)
        
        logger.info(f"[MomentumEngine] Updated {results['processed']} entities in {elapsed:.1f}s")
        
        return results
    
    async def get_top_momentum(
        self,
        entity_type: str = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get top entities by momentum score.
        """
        query = {}
        if entity_type:
            query["entity_type"] = entity_type
        
        cursor = self.momentum.find(
            query,
            {"_id": 0}
        ).sort("momentum_score", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_fastest_growing(
        self,
        entity_type: str = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get entities with highest momentum velocity (fastest growing).
        """
        query = {"momentum_velocity": {"$gt": 0}}
        if entity_type:
            query["entity_type"] = entity_type
        
        cursor = self.momentum.find(
            query,
            {"_id": 0}
        ).sort("momentum_velocity", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_narrative_top_entities(
        self,
        narrative_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get top momentum entities for a specific narrative.
        """
        # Get entities linked to this narrative
        cursor = self.narrative_entities.find({
            "narrative_id": narrative_id
        })
        
        entity_keys = []
        async for link in cursor:
            entity_key = link.get("entity_key") or f"{link.get('entity_type')}:{link.get('entity_id')}"
            entity_keys.append(entity_key)
        
        if not entity_keys:
            return []
        
        # Get momentum for these entities
        cursor = self.momentum.find(
            {"entity_key": {"$in": entity_keys}},
            {"_id": 0}
        ).sort("momentum_score", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_entity_momentum_history(
        self,
        entity_type: str,
        entity_id: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get momentum history for an entity.
        """
        entity_key = f"{entity_type}:{entity_id}"
        from_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        cursor = self.momentum_history.find(
            {
                "entity_key": entity_key,
                "date": {"$gte": from_date}
            },
            {"_id": 0}
        ).sort("date", 1)
        
        return await cursor.to_list(length=days)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get momentum engine statistics"""
        total = await self.momentum.count_documents({})
        
        # Average momentum by type
        pipeline = [
            {"$group": {
                "_id": "$entity_type",
                "count": {"$sum": 1},
                "avg_momentum": {"$avg": "$momentum_score"},
                "max_momentum": {"$max": "$momentum_score"}
            }}
        ]
        
        type_stats = await self.momentum.aggregate(pipeline).to_list(10)
        
        # Count high momentum entities (>50)
        high_momentum = await self.momentum.count_documents({
            "momentum_score": {"$gte": 50}
        })
        
        # Count growing entities (positive velocity)
        growing = await self.momentum.count_documents({
            "momentum_velocity": {"$gt": 0}
        })
        
        return {
            "total_tracked": total,
            "high_momentum": high_momentum,
            "growing": growing,
            "by_type": {
                stat["_id"]: {
                    "count": stat["count"],
                    "avg_momentum": round(stat["avg_momentum"], 1),
                    "max_momentum": round(stat["max_momentum"], 1)
                }
                for stat in type_stats
            },
            "weights": WEIGHTS
        }


# Singleton
_momentum_engine: Optional[EntityMomentumEngine] = None


def get_momentum_engine(db: AsyncIOMotorDatabase = None) -> EntityMomentumEngine:
    """Get or create momentum engine instance"""
    global _momentum_engine
    if db is not None:
        _momentum_engine = EntityMomentumEngine(db)
    return _momentum_engine
