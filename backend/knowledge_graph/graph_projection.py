"""
Graph Projection Layer
======================

Pre-computes and caches subgraphs for hot entities.
Solves the problem of expensive graph traversal on every UI request.

Architecture:
    graph_nodes + graph_edges → (projection job) → graph_projection
    
    UI request → read from graph_projection (fast)
    
Collections:
    graph_projection:
        entity_key: "project:arbitrum"
        nodes: [...]
        edges: [...]
        generated_at: datetime
        ttl_minutes: 30
        
Scheduled Job:
    rebuild_hot_graphs - runs every 15 minutes
    rebuilds projections for HOT_ENTITIES list
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


# Hot entities that get pre-computed projections
HOT_ENTITIES = [
    # Top projects
    ("project", "bitcoin"),
    ("project", "ethereum"),
    ("project", "solana"),
    ("project", "arbitrum"),
    ("project", "optimism"),
    ("project", "base"),
    ("project", "celestia"),
    ("project", "eigenlayer"),
    ("project", "sui"),
    ("project", "aptos"),
    # Top funds
    ("fund", "a16z"),
    ("fund", "paradigm"),
    ("fund", "polychain"),
    ("fund", "pantera"),
    ("fund", "dragonfly"),
    ("fund", "multicoin"),
    ("fund", "binance-labs"),
    ("fund", "coinbase-ventures"),
    # Top exchanges
    ("exchange", "binance"),
    ("exchange", "coinbase"),
    ("exchange", "bybit"),
    ("exchange", "okx"),
    # Key persons
    ("person", "vitalik-buterin"),
    ("person", "cz-binance"),
    ("person", "brian-armstrong"),
]

# Default projection config
DEFAULT_DEPTH = 1
DEFAULT_MAX_NODES = 50
DEFAULT_MAX_EDGES = 80
PROJECTION_TTL_MINUTES = 30


class GraphProjectionService:
    """
    Service for managing pre-computed graph projections.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.projections = db.graph_projection
        self.graph_nodes = db.graph_nodes
        self.graph_edges = db.graph_edges
    
    async def ensure_indexes(self):
        """Create indexes for projection collection"""
        await self.projections.create_index("entity_key", unique=True)
        await self.projections.create_index("generated_at")
        await self.projections.create_index([("entity_type", 1), ("entity_id", 1)])
        logger.info("[GraphProjection] Indexes created")
    
    async def get_projection(
        self,
        entity_type: str,
        entity_id: str,
        max_age_minutes: int = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get pre-computed projection for entity.
        Returns None if not found or expired.
        """
        entity_key = f"{entity_type}:{entity_id}"
        max_age = max_age_minutes or PROJECTION_TTL_MINUTES
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age)
        
        projection = await self.projections.find_one({
            "entity_key": entity_key,
            "generated_at": {"$gte": cutoff}
        }, {"_id": 0})
        
        if projection:
            logger.debug(f"[GraphProjection] Cache hit: {entity_key}")
            return projection
        
        logger.debug(f"[GraphProjection] Cache miss: {entity_key}")
        return None
    
    async def build_projection(
        self,
        entity_type: str,
        entity_id: str,
        depth: int = DEFAULT_DEPTH,
        max_nodes: int = DEFAULT_MAX_NODES,
        max_edges: int = DEFAULT_MAX_EDGES
    ) -> Dict[str, Any]:
        """
        Build and store projection for entity.
        """
        entity_key = f"{entity_type}:{entity_id}"
        now = datetime.now(timezone.utc)
        
        # Find center node
        center_node = await self.graph_nodes.find_one({
            "entity_type": entity_type,
            "entity_id": entity_id
        })
        
        if not center_node:
            logger.warning(f"[GraphProjection] Node not found: {entity_key}")
            return {
                "entity_key": entity_key,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "nodes": [],
                "edges": [],
                "node_count": 0,
                "edge_count": 0,
                "generated_at": now,
                "error": "Node not found"
            }
        
        # Build subgraph using BFS
        nodes = {center_node["id"]: self._format_node(center_node)}
        edges = []
        visited_edges = set()
        
        current_level = [center_node["id"]]
        
        for d in range(depth):
            next_level = []
            
            for node_id in current_level:
                # Get edges for this node
                edge_cursor = self.graph_edges.find({
                    "$or": [
                        {"from_node_id": node_id},
                        {"to_node_id": node_id}
                    ],
                    "source_type": {"$ne": "derived"}  # Exclude derived by default
                }).limit(30)  # Hub suppression
                
                node_edges = await edge_cursor.to_list(30)
                
                for edge in node_edges:
                    edge_id = edge.get("id", f"{edge['from_node_id']}_{edge['to_node_id']}")
                    
                    if edge_id in visited_edges:
                        continue
                    visited_edges.add(edge_id)
                    
                    # Get neighbor
                    neighbor_id = edge["to_node_id"] if edge["from_node_id"] == node_id else edge["from_node_id"]
                    
                    if neighbor_id not in nodes:
                        neighbor = await self.graph_nodes.find_one({"id": neighbor_id})
                        if neighbor:
                            nodes[neighbor_id] = self._format_node(neighbor)
                            next_level.append(neighbor_id)
                    
                    edges.append(self._format_edge(edge))
                    
                    # Check limits
                    if len(nodes) >= max_nodes or len(edges) >= max_edges:
                        break
                
                if len(nodes) >= max_nodes or len(edges) >= max_edges:
                    break
            
            current_level = next_level
            
            if not current_level or len(nodes) >= max_nodes:
                break
        
        # Build projection document
        projection = {
            "entity_key": entity_key,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "center_node_id": center_node["id"],
            "nodes": list(nodes.values()),
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "depth": depth,
            "generated_at": now,
            "ttl_minutes": PROJECTION_TTL_MINUTES
        }
        
        # Store projection
        await self.projections.update_one(
            {"entity_key": entity_key},
            {"$set": projection},
            upsert=True
        )
        
        logger.info(f"[GraphProjection] Built: {entity_key} ({len(nodes)} nodes, {len(edges)} edges)")
        
        return projection
    
    async def rebuild_hot_graphs(self) -> Dict[str, Any]:
        """
        Rebuild projections for all hot entities.
        Called by scheduler job.
        """
        start = datetime.now(timezone.utc)
        results = {
            "success": 0,
            "failed": 0,
            "entities": []
        }
        
        for entity_type, entity_id in HOT_ENTITIES:
            try:
                projection = await self.build_projection(entity_type, entity_id)
                results["success"] += 1
                results["entities"].append({
                    "key": f"{entity_type}:{entity_id}",
                    "nodes": projection.get("node_count", 0),
                    "edges": projection.get("edge_count", 0)
                })
            except Exception as e:
                logger.error(f"[GraphProjection] Failed to build {entity_type}:{entity_id}: {e}")
                results["failed"] += 1
        
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        results["elapsed_seconds"] = round(elapsed, 2)
        results["timestamp"] = start.isoformat()
        
        logger.info(f"[GraphProjection] Rebuilt {results['success']} projections in {elapsed:.1f}s")
        
        return results
    
    async def invalidate_projection(self, entity_type: str, entity_id: str):
        """
        Invalidate (delete) projection for entity.
        Called when graph data changes.
        """
        entity_key = f"{entity_type}:{entity_id}"
        await self.projections.delete_one({"entity_key": entity_key})
        logger.info(f"[GraphProjection] Invalidated: {entity_key}")
    
    async def invalidate_all(self):
        """Invalidate all projections"""
        result = await self.projections.delete_many({})
        logger.info(f"[GraphProjection] Invalidated all: {result.deleted_count} projections")
        return result.deleted_count
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get projection cache statistics"""
        total = await self.projections.count_documents({})
        
        # Count fresh vs stale
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=PROJECTION_TTL_MINUTES)
        fresh = await self.projections.count_documents({"generated_at": {"$gte": cutoff}})
        stale = total - fresh
        
        # Get average sizes
        pipeline = [
            {"$group": {
                "_id": None,
                "avg_nodes": {"$avg": "$node_count"},
                "avg_edges": {"$avg": "$edge_count"},
                "total_nodes": {"$sum": "$node_count"},
                "total_edges": {"$sum": "$edge_count"}
            }}
        ]
        
        agg_result = await self.projections.aggregate(pipeline).to_list(1)
        averages = agg_result[0] if agg_result else {}
        
        return {
            "total_projections": total,
            "fresh": fresh,
            "stale": stale,
            "avg_nodes": round(averages.get("avg_nodes", 0), 1),
            "avg_edges": round(averages.get("avg_edges", 0), 1),
            "total_nodes_cached": averages.get("total_nodes", 0),
            "total_edges_cached": averages.get("total_edges", 0),
            "ttl_minutes": PROJECTION_TTL_MINUTES,
            "hot_entities_count": len(HOT_ENTITIES)
        }
    
    def _format_node(self, node: Dict) -> Dict:
        """Format node for projection"""
        return {
            "id": f"{node.get('entity_type')}:{node.get('entity_id')}",
            "node_id": node.get("id"),
            "label": node.get("label", node.get("entity_id")),
            "type": node.get("entity_type"),
            "slug": node.get("slug"),
            "importance": node.get("metadata", {}).get("importance", 0.5)
        }
    
    def _format_edge(self, edge: Dict) -> Dict:
        """Format edge for projection"""
        return {
            "id": edge.get("id"),
            "source": edge.get("from_node_id"),
            "target": edge.get("to_node_id"),
            "relation": edge.get("relation_type"),
            "weight": edge.get("weight", 1.0),
            "confidence": edge.get("confidence", 0.5),
            "is_derived": edge.get("source_type") == "derived"
        }


# Singleton
_projection_service: Optional[GraphProjectionService] = None


def get_projection_service(db: AsyncIOMotorDatabase = None) -> GraphProjectionService:
    """Get or create projection service instance"""
    global _projection_service
    if db is not None:
        _projection_service = GraphProjectionService(db)
    return _projection_service
