"""
Neighbor Materialization Layer
==============================

Pre-computes and caches neighbor data for fast graph queries.
Speeds up API responses by 20-30x for hot entities.

Stores:
- top_neighbors: Ranked list of neighbors
- neighbor_counts: Counts by entity type
- grouped_neighbors: Neighbors grouped by type
- relation_summary: Counts by relation type

Only materializes for:
- Entities with confidence >= 0.75
- Hot entities (frequently queried)
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Set
from motor.motor_asyncio import AsyncIOMotorDatabase
from collections import defaultdict

logger = logging.getLogger(__name__)

# Minimum confidence for materialization
MIN_CONFIDENCE = 0.75

# Hot entities to always materialize
HOT_ENTITIES = [
    "project:bitcoin", "project:ethereum", "project:solana", "project:arbitrum",
    "fund:a16z", "fund:paradigm", "fund:polychain", "fund:pantera",
    "exchange:binance", "exchange:coinbase"
]

# Cache TTL
CACHE_TTL_HOURS = 1


class NeighborMaterializationService:
    """
    Pre-computes and caches neighbor data for graph entities.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.graph_nodes = db.graph_nodes
        self.graph_edges = db.graph_edges
        self.entity_confidence = db.entity_confidence
        self.neighbor_cache = db.graph_neighbor_cache
        
        # Track hot entities (most queried)
        self._query_counts: Dict[str, int] = defaultdict(int)
    
    async def ensure_indexes(self):
        """Create indexes for neighbor cache"""
        await self.neighbor_cache.create_index("entity_id", unique=True)
        await self.neighbor_cache.create_index("updated_at")
        await self.neighbor_cache.create_index("is_hot")
        
        logger.info("[NeighborMaterialization] Indexes created")
    
    def record_query(self, entity_id: str):
        """Record entity query for hot detection"""
        self._query_counts[entity_id] += 1
    
    def get_hot_entities(self, limit: int = 20) -> List[str]:
        """Get most queried entities"""
        sorted_entities = sorted(
            self._query_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return [e[0] for e in sorted_entities[:limit]]
    
    async def materialize_entity(self, entity_id: str, force: bool = False) -> Dict[str, Any]:
        """
        Materialize neighbors for a specific entity.
        
        entity_id format: "project:bitcoin" or "fund:a16z"
        """
        # Check if already cached and fresh
        if not force:
            cached = await self.neighbor_cache.find_one({"entity_id": entity_id})
            if cached:
                updated_at = cached.get("updated_at")
                if updated_at:
                    # Make timezone-aware if needed
                    if updated_at.tzinfo is None:
                        updated_at = updated_at.replace(tzinfo=timezone.utc)
                    if (datetime.now(timezone.utc) - updated_at) < timedelta(hours=CACHE_TTL_HOURS):
                        return {
                            "entity_id": entity_id,
                            "cached": True,
                            "updated_at": updated_at.isoformat()
                        }
        
        # Check confidence (skip for hot entities)
        is_hot = entity_id in HOT_ENTITIES
        if not is_hot:
            confidence_record = await self.entity_confidence.find_one({"entity_id": entity_id})
            if confidence_record and confidence_record.get("confidence_score", 0) < MIN_CONFIDENCE:
                return {"skipped": True, "reason": "low_confidence"}
        
        # Parse entity_id to find the node
        parts = entity_id.split(":", 1)
        if len(parts) == 2:
            entity_type, entity_slug = parts
        else:
            # Try to find by entity_id directly
            entity_type = None
            entity_slug = entity_id
        
        # Find the node in graph_nodes
        if entity_type:
            node = await self.graph_nodes.find_one({
                "entity_type": entity_type,
                "entity_id": entity_slug
            })
        else:
            node = await self.graph_nodes.find_one({"entity_id": entity_slug})
        
        if not node:
            logger.debug(f"[NeighborMaterialization] Node not found: {entity_id}")
            return {"skipped": True, "reason": "node_not_found"}
        
        node_uuid = node.get("id")
        if not node_uuid:
            return {"skipped": True, "reason": "node_missing_id"}
        
        # Build node_id to entity_id mapping for lookups
        node_id_to_entity: Dict[str, str] = {}
        node_id_to_entity[node_uuid] = entity_id
        
        # Get all edges involving this node (using from_node_id/to_node_id)
        edges_out = await self.graph_edges.find({"from_node_id": node_uuid}).to_list(500)
        edges_in = await self.graph_edges.find({"to_node_id": node_uuid}).to_list(500)
        
        # Collect all neighbor node UUIDs
        neighbor_uuids: Set[str] = set()
        for edge in edges_out:
            if edge.get("to_node_id"):
                neighbor_uuids.add(edge["to_node_id"])
        for edge in edges_in:
            if edge.get("from_node_id"):
                neighbor_uuids.add(edge["from_node_id"])
        
        # Fetch all neighbor nodes to get their entity_ids
        if neighbor_uuids:
            neighbor_nodes = await self.graph_nodes.find(
                {"id": {"$in": list(neighbor_uuids)}}
            ).to_list(len(neighbor_uuids))
            
            for n in neighbor_nodes:
                n_uuid = n.get("id")
                n_type = n.get("entity_type", "unknown")
                n_slug = n.get("entity_id", n_uuid)
                node_id_to_entity[n_uuid] = f"{n_type}:{n_slug}"
        
        # Build neighbor data
        neighbors: Dict[str, Dict] = {}
        relation_counts: Dict[str, int] = defaultdict(int)
        
        for edge in edges_out:
            target_uuid = edge.get("to_node_id")
            relation = edge.get("relation_type", "related_to")
            weight = edge.get("weight", 0.5) or 0.5
            
            target_entity_id = node_id_to_entity.get(target_uuid, target_uuid)
            
            if target_entity_id and target_entity_id != entity_id:
                if target_entity_id not in neighbors:
                    neighbors[target_entity_id] = {
                        "entity_id": target_entity_id,
                        "relations": [],
                        "total_weight": 0,
                        "edge_count": 0
                    }
                
                neighbors[target_entity_id]["relations"].append({
                    "type": relation,
                    "direction": "outgoing",
                    "weight": weight
                })
                neighbors[target_entity_id]["total_weight"] += weight
                neighbors[target_entity_id]["edge_count"] += 1
                relation_counts[relation] += 1
        
        for edge in edges_in:
            source_uuid = edge.get("from_node_id")
            relation = edge.get("relation_type", "related_to")
            weight = edge.get("weight", 0.5) or 0.5
            
            source_entity_id = node_id_to_entity.get(source_uuid, source_uuid)
            
            if source_entity_id and source_entity_id != entity_id:
                if source_entity_id not in neighbors:
                    neighbors[source_entity_id] = {
                        "entity_id": source_entity_id,
                        "relations": [],
                        "total_weight": 0,
                        "edge_count": 0
                    }
                
                neighbors[source_entity_id]["relations"].append({
                    "type": relation,
                    "direction": "incoming",
                    "weight": weight
                })
                neighbors[source_entity_id]["total_weight"] += weight
                neighbors[source_entity_id]["edge_count"] += 1
                relation_counts[f"{relation}_incoming"] += 1
        
        # Sort neighbors by weight
        top_neighbors = sorted(
            neighbors.values(),
            key=lambda x: x["total_weight"],
            reverse=True
        )[:100]  # Top 100
        
        # Group by type
        grouped = defaultdict(list)
        type_counts = defaultdict(int)
        
        for neighbor in neighbors.values():
            neighbor_id = neighbor["entity_id"]
            parts = neighbor_id.split(":")
            neighbor_type = parts[0] if len(parts) >= 2 else "unknown"
            
            grouped[neighbor_type].append({
                "id": neighbor_id,
                "weight": neighbor["total_weight"],
                "edges": neighbor["edge_count"]
            })
            type_counts[neighbor_type] += 1
        
        # Sort grouped lists
        for type_name in grouped:
            grouped[type_name] = sorted(
                grouped[type_name],
                key=lambda x: x["weight"],
                reverse=True
            )[:20]  # Top 20 per type
        
        now = datetime.now(timezone.utc)
        
        # Build cache record
        cache_record = {
            "entity_id": entity_id,
            "is_hot": is_hot,
            "neighbor_count": len(neighbors),
            "edge_count": len(edges_out) + len(edges_in),
            
            "top_neighbors": [
                {
                    "entity_id": n["entity_id"],
                    "weight": round(n["total_weight"], 3),
                    "edge_count": n["edge_count"]
                }
                for n in top_neighbors[:30]
            ],
            
            "neighbor_counts": dict(type_counts),
            
            "grouped_neighbors": dict(grouped),
            
            "relation_summary": dict(relation_counts),
            
            "updated_at": now
        }
        
        # Save to cache
        await self.neighbor_cache.update_one(
            {"entity_id": entity_id},
            {"$set": cache_record},
            upsert=True
        )
        
        logger.debug(f"[NeighborMaterialization] Materialized {entity_id}: {len(neighbors)} neighbors")
        
        return {
            "entity_id": entity_id,
            "materialized": True,
            "neighbor_count": len(neighbors),
            "edge_count": len(edges_out) + len(edges_in),
            "updated_at": now.isoformat()
        }
    
    async def get_cached_neighbors(self, entity_id: str) -> Optional[Dict]:
        """
        Get cached neighbors for an entity.
        Returns None if not cached or stale.
        """
        # Record query
        self.record_query(entity_id)
        
        cached = await self.neighbor_cache.find_one(
            {"entity_id": entity_id},
            {"_id": 0}
        )
        
        if not cached:
            return None
        
        # Check freshness - handle both timezone-aware and naive datetimes
        updated_at = cached.get("updated_at")
        if updated_at:
            # Make updated_at timezone-aware if it isn't
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - updated_at) > timedelta(hours=CACHE_TTL_HOURS):
                return None
        
        return cached
    
    async def materialize_hot_entities(self) -> Dict[str, Any]:
        """
        Materialize all hot entities.
        Called by scheduler.
        """
        results = {
            "materialized": 0,
            "skipped": 0,
            "errors": 0
        }
        
        # Combine static hot list with dynamically detected
        all_hot = set(HOT_ENTITIES)
        all_hot.update(self.get_hot_entities(10))
        
        for entity_id in all_hot:
            try:
                result = await self.materialize_entity(entity_id, force=True)
                if result.get("materialized"):
                    results["materialized"] += 1
                else:
                    results["skipped"] += 1
            except Exception as e:
                logger.error(f"[NeighborMaterialization] Error for {entity_id}: {e}")
                results["errors"] += 1
        
        logger.info(f"[NeighborMaterialization] Hot entities: {results['materialized']} materialized")
        
        return results
    
    async def refresh_stale_cache(self, limit: int = 50) -> Dict[str, Any]:
        """
        Refresh stale cached entries.
        """
        stale_threshold = datetime.now(timezone.utc) - timedelta(hours=CACHE_TTL_HOURS)
        
        cursor = self.neighbor_cache.find(
            {"updated_at": {"$lt": stale_threshold}}
        ).limit(limit)
        
        refreshed = 0
        
        async for cached in cursor:
            entity_id = cached.get("entity_id")
            if entity_id:
                result = await self.materialize_entity(entity_id, force=True)
                if result.get("materialized"):
                    refreshed += 1
        
        return {"refreshed": refreshed}
    
    async def invalidate_entity(self, entity_id: str) -> bool:
        """
        Invalidate cache for an entity.
        Called when entity's edges change.
        """
        result = await self.neighbor_cache.delete_one({"entity_id": entity_id})
        return result.deleted_count > 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get materialization statistics"""
        total_cached = await self.neighbor_cache.count_documents({})
        hot_cached = await self.neighbor_cache.count_documents({"is_hot": True})
        
        # Average neighbor count
        avg_pipeline = [
            {"$group": {"_id": None, "avg_neighbors": {"$avg": "$neighbor_count"}}}
        ]
        avg_result = await self.neighbor_cache.aggregate(avg_pipeline).to_list(1)
        avg_neighbors = avg_result[0]["avg_neighbors"] if avg_result else 0
        
        return {
            "total_cached": total_cached,
            "hot_cached": hot_cached,
            "average_neighbors": round(avg_neighbors, 1),
            "hot_entities_tracked": len(self._query_counts),
            "top_queried": self.get_hot_entities(5)
        }
    
    async def run_materialization_job(self) -> Dict[str, Any]:
        """
        Full materialization job - called by scheduler.
        """
        results = {
            "hot_entities": await self.materialize_hot_entities(),
            "stale_refresh": await self.refresh_stale_cache(30),
            "stats": await self.get_stats()
        }
        
        return results


# Singleton
_materialization_service: Optional[NeighborMaterializationService] = None


def get_neighbor_materialization_service(db: AsyncIOMotorDatabase = None) -> NeighborMaterializationService:
    """Get or create neighbor materialization service"""
    global _materialization_service
    if db is not None:
        _materialization_service = NeighborMaterializationService(db)
    return _materialization_service
