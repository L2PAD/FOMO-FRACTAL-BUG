"""
Graph Layer Separation
======================

Separates graph into three distinct layers to prevent future architecture issues:

1. Core Graph (factual):
   - Only direct facts from data sources
   - invested_in, founded, works_at, has_token, traded_on
   - Collections: graph_nodes, graph_edges
   
2. Derived Graph:
   - Computed relationships from facts
   - coinvested_with, worked_together, shares_investor_with
   - Collection: graph_derived_edges
   
3. Intelligence Graph:
   - Analytical/narrative relationships
   - event -> topic, topic -> narrative, influence links
   - Collection: graph_intelligence_edges

Why separation matters:
- Factual graph can be rebuilt from normalized data
- Derived graph can be recalculated without affecting core
- Intelligence graph can be modified by algorithms without breaking core
- Different refresh rates for each layer
- Clear debugging boundaries

Usage:
    layers = GraphLayerService(db)
    
    # Query factual only (default for most UI)
    graph = await layers.get_entity_graph(entity_key, layers=['factual'])
    
    # Query with derived
    graph = await layers.get_entity_graph(entity_key, layers=['factual', 'derived'])
    
    # Research mode - all layers
    graph = await layers.get_entity_graph(entity_key, layers=['all'])
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Set
from enum import Enum
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class GraphLayer(str, Enum):
    FACTUAL = "factual"         # Core facts
    DERIVED = "derived"         # Computed relationships
    INTELLIGENCE = "intelligence"  # Analytical links


# Define which relation types belong to which layer
FACTUAL_RELATIONS = {
    # Investment relations
    "invested_in",
    "led_round",
    "participated_in",
    
    # Organizational relations
    "works_at",
    "founded",
    "advisor_of",
    "partner_at",
    
    # Token/Asset relations
    "has_token",
    "mapped_to_asset",
    "traded_on",
    "listed_on",
    
    # Project relations
    "built_on",
    "uses_tech",
    "forked_from",
    
    # Unlock relations
    "has_unlock",
    "has_vesting",
    
    # Activity relations
    "has_activity",
    "github_commits",
}

DERIVED_RELATIONS = {
    # Co-investment patterns
    "coinvested_with",
    "shares_investor_with",
    "shared_portfolio",
    
    # Team patterns
    "worked_together",
    "co_founded",
    "shared_advisor",
    
    # Market patterns
    "correlated_with",
    "competes_with",
    "similar_to",
    
    # Graph-derived
    "graph_cluster_link",
    "strong_connection",
}

INTELLIGENCE_RELATIONS = {
    # Event/Narrative
    "event_linked",
    "topic_linked",
    "narrative_linked",
    "narrative_exposure",
    
    # Influence
    "influences",
    "influenced_by",
    "momentum_correlated",
    
    # Temporal
    "temporal_link",
    "causal_link",
    
    # Signals
    "signal_correlated",
    "alpha_source",
}


class GraphLayerService:
    """
    Service for managing separated graph layers.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        
        # Core collections
        self.graph_nodes = db.graph_nodes
        self.graph_edges = db.graph_edges  # Factual layer
        
        # Separated layers
        self.derived_edges = db.graph_derived_edges
        self.intelligence_edges = db.graph_intelligence_edges
    
    async def ensure_indexes(self):
        """Create indexes for all layer collections"""
        # Derived edges indexes
        await self.derived_edges.create_index([("from_node_id", 1), ("to_node_id", 1)])
        await self.derived_edges.create_index("relation_type")
        await self.derived_edges.create_index("from_node_id")
        await self.derived_edges.create_index("to_node_id")
        await self.derived_edges.create_index("created_at")
        
        # Intelligence edges indexes
        await self.intelligence_edges.create_index([("from_node_id", 1), ("to_node_id", 1)])
        await self.intelligence_edges.create_index("relation_type")
        await self.intelligence_edges.create_index("from_node_id")
        await self.intelligence_edges.create_index("to_node_id")
        await self.intelligence_edges.create_index("created_at")
        await self.intelligence_edges.create_index("event_id")
        await self.intelligence_edges.create_index("narrative_id")
        
        logger.info("[GraphLayers] Indexes created")
    
    def classify_edge(self, relation_type: str) -> GraphLayer:
        """Classify an edge by its relation type"""
        if relation_type in FACTUAL_RELATIONS:
            return GraphLayer.FACTUAL
        elif relation_type in DERIVED_RELATIONS:
            return GraphLayer.DERIVED
        elif relation_type in INTELLIGENCE_RELATIONS:
            return GraphLayer.INTELLIGENCE
        else:
            # Default to factual for unknown relations
            return GraphLayer.FACTUAL
    
    async def add_edge(
        self,
        from_node_id: str,
        to_node_id: str,
        relation_type: str,
        metadata: Dict[str, Any] = None,
        source: str = None,
        confidence: float = None
    ) -> Dict[str, Any]:
        """
        Add an edge to the appropriate layer based on relation type.
        """
        layer = self.classify_edge(relation_type)
        now = datetime.now(timezone.utc)
        
        edge = {
            "from_node_id": from_node_id,
            "to_node_id": to_node_id,
            "relation_type": relation_type,
            "layer": layer.value,
            "source": source,
            "confidence": confidence,
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now
        }
        
        # Select target collection based on layer
        if layer == GraphLayer.FACTUAL:
            collection = self.graph_edges
        elif layer == GraphLayer.DERIVED:
            collection = self.derived_edges
        else:
            collection = self.intelligence_edges
        
        # Upsert edge
        await collection.update_one(
            {
                "from_node_id": from_node_id,
                "to_node_id": to_node_id,
                "relation_type": relation_type
            },
            {"$set": edge},
            upsert=True
        )
        
        logger.debug(f"[GraphLayers] Added {layer.value} edge: {from_node_id} -> {to_node_id} ({relation_type})")
        
        return edge
    
    async def get_entity_graph(
        self,
        entity_key: str,
        layers: List[str] = None,
        max_nodes: int = 50,
        max_edges: int = 80,
        depth: int = 1
    ) -> Dict[str, Any]:
        """
        Get graph for entity with specified layers.
        
        Args:
            entity_key: Entity key (e.g., "project:ethereum")
            layers: List of layers to include ['factual', 'derived', 'intelligence', 'all']
            max_nodes: Maximum nodes to return
            max_edges: Maximum edges to return
            depth: Traversal depth
        """
        if not layers:
            layers = ['factual']  # Default to factual only
        
        if 'all' in layers:
            layers = ['factual', 'derived', 'intelligence']
        
        # Parse entity key
        parts = entity_key.split(':')
        entity_type = parts[0] if len(parts) > 0 else "unknown"
        entity_id = parts[1] if len(parts) > 1 else entity_key
        
        # Find center node
        center_node = await self.graph_nodes.find_one({
            "entity_type": entity_type,
            "entity_id": entity_id
        })
        
        if not center_node:
            return {
                "entity_key": entity_key,
                "layers": layers,
                "nodes": [],
                "edges": [],
                "error": "Entity not found"
            }
        
        center_id = center_node["id"]
        
        # Collect edges from requested layers
        all_edges = []
        node_ids: Set[str] = {center_id}
        
        # Query each layer
        for layer in layers:
            if layer == 'factual':
                collection = self.graph_edges
            elif layer == 'derived':
                collection = self.derived_edges
            elif layer == 'intelligence':
                collection = self.intelligence_edges
            else:
                continue
            
            # Get edges for center node
            cursor = collection.find({
                "$or": [
                    {"from_node_id": center_id},
                    {"to_node_id": center_id}
                ]
            }).limit(max_edges // len(layers))
            
            async for edge in cursor:
                edge["_layer"] = layer
                all_edges.append(edge)
                node_ids.add(edge["from_node_id"])
                node_ids.add(edge["to_node_id"])
                
                if len(node_ids) >= max_nodes:
                    break
        
        # Fetch all nodes
        nodes = []
        for node_id in list(node_ids)[:max_nodes]:
            node = await self.graph_nodes.find_one({"id": node_id})
            if node:
                nodes.append({
                    "id": f"{node.get('entity_type')}:{node.get('entity_id')}",
                    "node_id": node.get("id"),
                    "label": node.get("label", node.get("entity_id")),
                    "type": node.get("entity_type"),
                    "is_center": node.get("id") == center_id
                })
        
        # Format edges
        edges = [
            {
                "source": e.get("from_node_id"),
                "target": e.get("to_node_id"),
                "relation": e.get("relation_type"),
                "layer": e.get("_layer"),
                "confidence": e.get("confidence"),
                "weight": e.get("weight", 1.0)
            }
            for e in all_edges[:max_edges]
        ]
        
        return {
            "entity_key": entity_key,
            "layers": layers,
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "edges_by_layer": {
                layer: len([e for e in edges if e.get("layer") == layer])
                for layer in layers
            }
        }
    
    async def migrate_existing_edges(self, batch_size: int = 1000) -> Dict[str, Any]:
        """
        Migrate existing edges from graph_edges to appropriate layer collections.
        Run once for existing data.
        """
        results = {
            "factual_kept": 0,
            "moved_to_derived": 0,
            "moved_to_intelligence": 0,
            "errors": 0
        }
        
        cursor = self.graph_edges.find({})
        
        async for edge in cursor:
            relation_type = edge.get("relation_type", "")
            layer = self.classify_edge(relation_type)
            
            try:
                if layer == GraphLayer.DERIVED:
                    # Move to derived collection
                    edge["layer"] = layer.value
                    await self.derived_edges.update_one(
                        {
                            "from_node_id": edge["from_node_id"],
                            "to_node_id": edge["to_node_id"],
                            "relation_type": relation_type
                        },
                        {"$set": edge},
                        upsert=True
                    )
                    results["moved_to_derived"] += 1
                    
                elif layer == GraphLayer.INTELLIGENCE:
                    # Move to intelligence collection
                    edge["layer"] = layer.value
                    await self.intelligence_edges.update_one(
                        {
                            "from_node_id": edge["from_node_id"],
                            "to_node_id": edge["to_node_id"],
                            "relation_type": relation_type
                        },
                        {"$set": edge},
                        upsert=True
                    )
                    results["moved_to_intelligence"] += 1
                    
                else:
                    results["factual_kept"] += 1
                    
            except Exception as e:
                logger.error(f"Migration error: {e}")
                results["errors"] += 1
        
        logger.info(f"[GraphLayers] Migration complete: {results}")
        
        return results
    
    async def compute_derived_edges(
        self,
        relation_type: str = "coinvested_with"
    ) -> int:
        """
        Compute derived edges from factual data.
        Supported types:
        - coinvested_with: Funds that invested in the same project
        - shares_investor_with: Projects that share the same investor
        """
        now = datetime.now(timezone.utc)
        computed = 0
        
        if relation_type == "coinvested_with":
            # Find all investments - group by project to find co-investors
            pipeline = [
                {"$match": {"relation_type": "invested_in"}},
                {"$group": {
                    "_id": "$to_node_id",  # Project
                    "investors": {"$addToSet": "$from_node_id"}
                }},
                {"$match": {"investors.1": {"$exists": True}}}  # At least 2 investors
            ]
            
            async for project in self.graph_edges.aggregate(pipeline):
                investors = project["investors"]
                
                # Create coinvested_with edges between all pairs
                for i, inv1 in enumerate(investors):
                    for inv2 in investors[i+1:]:
                        edge = {
                            "from_node_id": inv1,
                            "to_node_id": inv2,
                            "relation_type": "coinvested_with",
                            "layer": "derived",
                            "source": "computed",
                            "confidence": 1.0,
                            "metadata": {"shared_investment": project["_id"]},
                            "created_at": now,
                            "updated_at": now
                        }
                        
                        await self.derived_edges.update_one(
                            {
                                "from_node_id": inv1,
                                "to_node_id": inv2,
                                "relation_type": "coinvested_with"
                            },
                            {"$set": edge},
                            upsert=True
                        )
                        computed += 1
        
        elif relation_type == "shares_investor_with":
            # Find all investments - group by investor to find projects with shared investors
            pipeline = [
                {"$match": {"relation_type": "invested_in"}},
                {"$group": {
                    "_id": "$from_node_id",  # Investor
                    "projects": {"$addToSet": "$to_node_id"}
                }},
                {"$match": {"projects.1": {"$exists": True}}}  # At least 2 projects
            ]
            
            async for investor in self.graph_edges.aggregate(pipeline):
                projects = investor["projects"]
                investor_id = investor["_id"]
                
                # Create shares_investor_with edges between all project pairs
                for i, proj1 in enumerate(projects):
                    for proj2 in projects[i+1:]:
                        edge = {
                            "from_node_id": proj1,
                            "to_node_id": proj2,
                            "relation_type": "shares_investor_with",
                            "layer": "derived",
                            "source": "computed",
                            "confidence": 1.0,
                            "metadata": {"shared_investor": investor_id},
                            "created_at": now,
                            "updated_at": now
                        }
                        
                        await self.derived_edges.update_one(
                            {
                                "from_node_id": proj1,
                                "to_node_id": proj2,
                                "relation_type": "shares_investor_with"
                            },
                            {"$set": edge},
                            upsert=True
                        )
                        computed += 1
        
        logger.info(f"[GraphLayers] Computed {computed} {relation_type} edges")
        return computed
    
    async def link_events_to_entities(self, limit: int = 500) -> int:
        """
        Create intelligence edges linking events to entities.
        Links events from news_events to graph entities.
        """
        now = datetime.now(timezone.utc)
        linked = 0
        
        # Get recent events with entities
        cursor = self.db.news_events.find({
            "primary_entities": {"$exists": True, "$ne": []}
        }).sort("created_at", -1).limit(limit)
        
        async for event in cursor:
            event_id = event.get("id")
            if not event_id:
                continue
            
            # Get entities from event
            primary_entities = event.get("primary_entities", [])
            primary_assets = event.get("primary_assets", [])
            
            # Combine all entity mentions
            all_entities = []
            for entity in primary_entities:
                if isinstance(entity, str):
                    all_entities.append(("unknown", entity.lower()))
                elif isinstance(entity, dict):
                    all_entities.append((entity.get("type", "unknown"), entity.get("id", "").lower()))
            
            for asset in primary_assets:
                if isinstance(asset, str):
                    all_entities.append(("project", asset.lower()))
            
            # Create intelligence edges between co-mentioned entities
            for i, (type1, id1) in enumerate(all_entities):
                for type2, id2 in all_entities[i+1:]:
                    # Find node IDs
                    node1 = await self.graph_nodes.find_one({
                        "entity_type": type1 if type1 != "unknown" else {"$exists": True},
                        "entity_id": id1
                    })
                    node2 = await self.graph_nodes.find_one({
                        "entity_type": type2 if type2 != "unknown" else {"$exists": True},
                        "entity_id": id2
                    })
                    
                    if node1 and node2:
                        edge = {
                            "from_node_id": node1["id"],
                            "to_node_id": node2["id"],
                            "relation_type": "event_linked",
                            "layer": "intelligence",
                            "event_id": event_id,
                            "source": "event_extraction",
                            "confidence": 0.8,
                            "metadata": {
                                "event_title": event.get("title", "")[:100],
                                "event_type": event.get("type")
                            },
                            "created_at": now,
                            "updated_at": now
                        }
                        
                        await self.intelligence_edges.update_one(
                            {
                                "from_node_id": node1["id"],
                                "to_node_id": node2["id"],
                                "event_id": event_id
                            },
                            {"$set": edge},
                            upsert=True
                        )
                        linked += 1
        
        logger.info(f"[GraphLayers] Created {linked} intelligence edges from events")
        return linked
    
    async def add_intelligence_edge(
        self,
        from_entity_key: str,
        to_entity_key: str,
        relation_type: str,
        event_id: str = None,
        narrative_id: str = None,
        topic_id: str = None,
        confidence: float = 0.5,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Add an intelligence layer edge (event/narrative links).
        """
        now = datetime.now(timezone.utc)
        
        # Parse entity keys to get node IDs
        from_node = await self._find_node_by_key(from_entity_key)
        to_node = await self._find_node_by_key(to_entity_key)
        
        if not from_node or not to_node:
            return {"error": "Entity not found"}
        
        edge = {
            "from_node_id": from_node["id"],
            "to_node_id": to_node["id"],
            "from_entity_key": from_entity_key,
            "to_entity_key": to_entity_key,
            "relation_type": relation_type,
            "layer": "intelligence",
            "event_id": event_id,
            "narrative_id": narrative_id,
            "topic_id": topic_id,
            "confidence": confidence,
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now
        }
        
        await self.intelligence_edges.update_one(
            {
                "from_node_id": from_node["id"],
                "to_node_id": to_node["id"],
                "relation_type": relation_type
            },
            {"$set": edge},
            upsert=True
        )
        
        return edge
    
    async def _find_node_by_key(self, entity_key: str) -> Optional[Dict]:
        """Find node by entity key (e.g., project:ethereum)"""
        parts = entity_key.split(':')
        if len(parts) != 2:
            return None
        
        return await self.graph_nodes.find_one({
            "entity_type": parts[0],
            "entity_id": parts[1]
        })
    
    async def get_layer_stats(self) -> Dict[str, Any]:
        """Get statistics for each layer"""
        factual_count = await self.graph_edges.count_documents({})
        derived_count = await self.derived_edges.count_documents({})
        intelligence_count = await self.intelligence_edges.count_documents({})
        
        # Get relation type distribution
        factual_types = await self.graph_edges.distinct("relation_type")
        derived_types = await self.derived_edges.distinct("relation_type")
        intelligence_types = await self.intelligence_edges.distinct("relation_type")
        
        return {
            "factual": {
                "edge_count": factual_count,
                "relation_types": factual_types
            },
            "derived": {
                "edge_count": derived_count,
                "relation_types": derived_types
            },
            "intelligence": {
                "edge_count": intelligence_count,
                "relation_types": intelligence_types
            },
            "total_edges": factual_count + derived_count + intelligence_count
        }


# Singleton
_layer_service: Optional[GraphLayerService] = None


def get_graph_layer_service(db: AsyncIOMotorDatabase = None) -> GraphLayerService:
    """Get or create layer service instance"""
    global _layer_service
    if db is not None:
        _layer_service = GraphLayerService(db)
    return _layer_service
