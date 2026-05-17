"""
Temporal Graph Layer

Adds time dimension to the graph:
- valid_from / valid_to on edges
- Graph state queries at specific time
- Network evolution analysis
- Graph snapshots

This transforms static graph into temporal network intelligence.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field
from enum import Enum
import hashlib


class TemporalEdge(BaseModel):
    """
    Edge with temporal validity
    
    Example:
    Person X works at Fund Y
    valid_from: 2021-01
    valid_to: 2024-06 (or None if still active)
    """
    id: str
    from_node_id: str
    to_node_id: str
    relation_type: str
    
    # Temporal validity
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None  # None = still active
    
    # Metadata
    weight: float = Field(1.0, ge=0, le=1)
    confidence: float = Field(0.5, ge=0, le=1)
    source_type: str = Field("direct")  # direct / derived
    source_ref: Optional[str] = None
    
    # Event that created this edge
    created_by_event: Optional[str] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def is_active_at(self, time: datetime) -> bool:
        """Check if edge is active at given time"""
        if self.valid_from and time < self.valid_from:
            return False
        if self.valid_to and time > self.valid_to:
            return False
        return True


class GraphSnapshot(BaseModel):
    """
    Snapshot of graph state at a point in time
    
    Used for:
    - Historical analysis
    - Trend comparison
    - Network evolution tracking
    """
    id: str
    snapshot_time: datetime
    snapshot_label: str  # e.g., "2024_Q1"
    
    # Counts
    node_count: int
    edge_count: int
    active_edge_count: int
    
    # Type distribution
    nodes_by_type: Dict[str, int] = Field(default_factory=dict)
    edges_by_type: Dict[str, int] = Field(default_factory=dict)
    
    # Metrics
    graph_density: float = 0.0
    avg_degree: float = 0.0
    
    # Top entities
    top_nodes_by_degree: List[Dict] = Field(default_factory=list)
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TemporalGraphService:
    """
    Service for temporal graph operations
    """
    
    def __init__(self, db):
        self.db = db
        self.graph_nodes = db.graph_nodes
        self.graph_edges = db.graph_edges
        self.graph_snapshots = db.graph_snapshots
    
    async def ensure_indexes(self):
        """Create indexes for temporal queries"""
        # Temporal edge indexes
        await self.graph_edges.create_index("valid_from")
        await self.graph_edges.create_index("valid_to")
        await self.graph_edges.create_index([("valid_from", 1), ("valid_to", 1)])
        await self.graph_edges.create_index("created_by_event")
        
        # Snapshot indexes
        await self.graph_snapshots.create_index("id", unique=True)
        await self.graph_snapshots.create_index("snapshot_time")
        await self.graph_snapshots.create_index("snapshot_label")
    
    async def get_graph_at_time(
        self,
        center_type: str,
        center_id: str,
        at_time: datetime,
        depth: int = 1
    ) -> Dict:
        """
        Get ego graph state at specific time
        
        Example: /api/graph/ego/project/arbitrum?time=2023-01-01
        """
        # Find center node
        center = await self.graph_nodes.find_one({
            "entity_type": center_type,
            "entity_id": center_id
        })
        
        if not center:
            return {"error": "Node not found", "nodes": [], "edges": []}
        
        nodes = {center["id"]: center}
        edges = []
        
        # Get edges active at given time
        current_level = [center["id"]]
        
        for d in range(depth):
            next_level = []
            
            for node_id in current_level:
                # Query edges for this node
                cursor = self.graph_edges.find({
                    "$or": [
                        {"from_node_id": node_id},
                        {"to_node_id": node_id}
                    ]
                }).limit(50)
                
                async for edge in cursor:
                    # Check if edge is active at given time
                    valid_from = edge.get("valid_from")
                    valid_to = edge.get("valid_to")
                    
                    # Skip if edge started after our time
                    if valid_from and valid_from > at_time:
                        continue
                    # Skip if edge ended before our time
                    if valid_to and valid_to < at_time:
                        continue
                    
                    # Get neighbor
                    neighbor_id = edge["to_node_id"] if edge["from_node_id"] == node_id else edge["from_node_id"]
                    
                    if neighbor_id not in nodes:
                        neighbor = await self.graph_nodes.find_one({"id": neighbor_id})
                        if neighbor:
                            nodes[neighbor_id] = neighbor
                            next_level.append(neighbor_id)
                    
                    edges.append(edge)
            
            current_level = next_level
        
        # Clean _id from results
        for node in nodes.values():
            node.pop("_id", None)
        for edge in edges:
            edge.pop("_id", None)
        
        return {
            "center": center,
            "nodes": list(nodes.values()),
            "edges": edges,
            "at_time": at_time.isoformat(),
            "meta": {
                "node_count": len(nodes),
                "edge_count": len(edges)
            }
        }
    
    async def create_edge_from_event(
        self,
        from_entity_type: str,
        from_entity_id: str,
        to_entity_type: str,
        to_entity_id: str,
        relation_type: str,
        event_id: str,
        event_time: datetime,
        weight: float = 1.0,
        confidence: float = 0.8
    ):
        """
        Create or update edge from an event
        
        Called when events indicate new relationships
        """
        # Get node IDs
        from_node = await self.graph_nodes.find_one({
            "entity_type": from_entity_type,
            "entity_id": from_entity_id
        })
        to_node = await self.graph_nodes.find_one({
            "entity_type": to_entity_type,
            "entity_id": to_entity_id
        })
        
        if not from_node or not to_node:
            return None
        
        from_id = from_node["id"]
        to_id = to_node["id"]
        edge_id = f"e_{hashlib.md5(f'{from_id}_{to_id}_{relation_type}'.encode()).hexdigest()[:12]}"
        
        edge = {
            "id": edge_id,
            "from_node_id": from_id,
            "to_node_id": to_id,
            "relation_type": relation_type,
            "valid_from": event_time,
            "valid_to": None,
            "weight": weight,
            "confidence": confidence,
            "source_type": "direct",
            "created_by_event": event_id,
            "updated_at": datetime.now(timezone.utc)
        }
        
        await self.graph_edges.update_one(
            {"id": edge_id},
            {"$set": edge, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
            upsert=True
        )
        
        return edge
    
    async def end_edge_from_event(
        self,
        from_entity_type: str,
        from_entity_id: str,
        to_entity_type: str,
        to_entity_id: str,
        relation_type: str,
        end_time: datetime
    ):
        """
        Mark edge as ended (set valid_to)
        
        Called when events indicate relationship ended
        (e.g., person left company)
        """
        from_node = await self.graph_nodes.find_one({
            "entity_type": from_entity_type,
            "entity_id": from_entity_id
        })
        to_node = await self.graph_nodes.find_one({
            "entity_type": to_entity_type,
            "entity_id": to_entity_id
        })
        
        if not from_node or not to_node:
            return
        
        await self.graph_edges.update_one(
            {
                "from_node_id": from_node["id"],
                "to_node_id": to_node["id"],
                "relation_type": relation_type,
                "valid_to": None
            },
            {"$set": {"valid_to": end_time, "updated_at": datetime.now(timezone.utc)}}
        )
    
    async def create_snapshot(
        self,
        label: str = None
    ) -> GraphSnapshot:
        """
        Create snapshot of current graph state
        
        Should run periodically (weekly/monthly)
        """
        now = datetime.now(timezone.utc)
        label = label or now.strftime("%Y_Q%q" if now.month % 3 == 0 else "%Y_%m")
        
        # Count nodes by type
        node_pipeline = [
            {"$group": {"_id": "$entity_type", "count": {"$sum": 1}}}
        ]
        nodes_by_type = {}
        async for doc in self.graph_nodes.aggregate(node_pipeline):
            nodes_by_type[doc["_id"]] = doc["count"]
        
        total_nodes = sum(nodes_by_type.values())
        
        # Count edges
        total_edges = await self.graph_edges.count_documents({})
        active_edges = await self.graph_edges.count_documents({
            "$or": [
                {"valid_to": None},
                {"valid_to": {"$gte": now}}
            ]
        })
        
        # Edge types
        edge_pipeline = [
            {"$group": {"_id": "$relation_type", "count": {"$sum": 1}}}
        ]
        edges_by_type = {}
        async for doc in self.graph_edges.aggregate(edge_pipeline):
            edges_by_type[doc["_id"]] = doc["count"]
        
        # Calculate density
        density = 0.0
        if total_nodes > 1:
            max_edges = total_nodes * (total_nodes - 1) / 2
            density = total_edges / max_edges if max_edges > 0 else 0
        
        # Average degree
        avg_degree = (2 * total_edges / total_nodes) if total_nodes > 0 else 0
        
        # Top nodes by degree
        degree_pipeline = [
            {"$group": {"_id": "$from_node_id", "degree": {"$sum": 1}}},
            {"$sort": {"degree": -1}},
            {"$limit": 10}
        ]
        top_nodes = []
        async for doc in self.graph_edges.aggregate(degree_pipeline):
            node = await self.graph_nodes.find_one({"id": doc["_id"]})
            if node:
                top_nodes.append({
                    "id": doc["_id"],
                    "label": node.get("label"),
                    "type": node.get("entity_type"),
                    "degree": doc["degree"]
                })
        
        snapshot = GraphSnapshot(
            id=f"snapshot_{now.strftime('%Y%m%d%H%M%S')}",
            snapshot_time=now,
            snapshot_label=label,
            node_count=total_nodes,
            edge_count=total_edges,
            active_edge_count=active_edges,
            nodes_by_type=nodes_by_type,
            edges_by_type=edges_by_type,
            graph_density=density,
            avg_degree=avg_degree,
            top_nodes_by_degree=top_nodes
        )
        
        await self.graph_snapshots.insert_one(snapshot.dict())
        
        return snapshot
    
    async def get_network_evolution(
        self,
        entity_type: str,
        entity_id: str,
        from_date: datetime,
        to_date: datetime
    ) -> List[Dict]:
        """
        Get how an entity's network evolved over time
        
        Returns timeline of edge creations
        """
        node = await self.graph_nodes.find_one({
            "entity_type": entity_type,
            "entity_id": entity_id
        })
        
        if not node:
            return []
        
        node_id = node["id"]
        
        # Get edges created in time range
        cursor = self.graph_edges.find({
            "$or": [
                {"from_node_id": node_id},
                {"to_node_id": node_id}
            ],
            "valid_from": {"$gte": from_date, "$lte": to_date}
        }).sort("valid_from", 1)
        
        evolution = []
        async for edge in cursor:
            neighbor_id = edge["to_node_id"] if edge["from_node_id"] == node_id else edge["from_node_id"]
            neighbor = await self.graph_nodes.find_one({"id": neighbor_id})
            
            evolution.append({
                "time": edge.get("valid_from"),
                "relation": edge.get("relation_type"),
                "neighbor": {
                    "id": neighbor_id,
                    "label": neighbor.get("label") if neighbor else None,
                    "type": neighbor.get("entity_type") if neighbor else None
                },
                "event": edge.get("created_by_event")
            })
        
        return evolution


# =============================================================================
# GRAPH METRICS
# =============================================================================

class NodeMetrics(BaseModel):
    """Metrics for a single node"""
    node_id: str
    entity_type: str
    entity_id: str
    
    # Degree metrics
    degree: int = 0
    in_degree: int = 0
    out_degree: int = 0
    
    # Centrality
    betweenness: float = 0.0
    closeness: float = 0.0
    pagerank: float = 0.0
    
    # Cluster
    cluster_coefficient: float = 0.0
    
    # Influence score
    influence_score: float = 0.0
    
    # Temporal
    earliest_edge: Optional[datetime] = None
    latest_edge: Optional[datetime] = None
    edge_growth_rate: float = 0.0
    
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GraphMetricsService:
    """
    Service for calculating graph metrics
    """
    
    def __init__(self, db):
        self.db = db
        self.graph_nodes = db.graph_nodes
        self.graph_edges = db.graph_edges
        self.node_metrics = db.node_metrics
    
    async def calculate_node_metrics(self, node_id: str) -> NodeMetrics:
        """Calculate metrics for a single node"""
        node = await self.graph_nodes.find_one({"id": node_id})
        if not node:
            return None
        
        # Count edges
        out_degree = await self.graph_edges.count_documents({"from_node_id": node_id})
        in_degree = await self.graph_edges.count_documents({"to_node_id": node_id})
        degree = out_degree + in_degree
        
        # Get edge timestamps
        edge_cursor = self.graph_edges.find({
            "$or": [{"from_node_id": node_id}, {"to_node_id": node_id}]
        }).sort("valid_from", 1)
        
        edges = await edge_cursor.to_list(length=1000)
        
        earliest = None
        latest = None
        for edge in edges:
            vf = edge.get("valid_from")
            if vf:
                if not earliest or vf < earliest:
                    earliest = vf
                if not latest or vf > latest:
                    latest = vf
        
        # Growth rate (edges per month)
        growth_rate = 0.0
        if earliest and latest and earliest != latest:
            months = (latest - earliest).days / 30
            if months > 0:
                growth_rate = degree / months
        
        # Simple influence score
        influence = self._calculate_influence(degree, in_degree, growth_rate)
        
        metrics = NodeMetrics(
            node_id=node_id,
            entity_type=node.get("entity_type"),
            entity_id=node.get("entity_id"),
            degree=degree,
            in_degree=in_degree,
            out_degree=out_degree,
            influence_score=influence,
            earliest_edge=earliest,
            latest_edge=latest,
            edge_growth_rate=growth_rate
        )
        
        # Store
        await self.node_metrics.update_one(
            {"node_id": node_id},
            {"$set": metrics.dict()},
            upsert=True
        )
        
        return metrics
    
    def _calculate_influence(
        self,
        degree: int,
        in_degree: int,
        growth_rate: float
    ) -> float:
        """
        Calculate influence score
        
        Formula:
        influence = degree_weight + in_degree_weight + growth_weight
        """
        # Normalize
        degree_norm = min(degree / 100, 1.0)
        in_norm = min(in_degree / 50, 1.0)
        growth_norm = min(growth_rate / 5, 1.0)
        
        return (degree_norm * 0.4 + in_norm * 0.3 + growth_norm * 0.3) * 100
    
    async def calculate_all_metrics(self) -> Dict:
        """Calculate metrics for all nodes"""
        stats = {"processed": 0, "errors": 0}
        
        cursor = self.graph_nodes.find()
        async for node in cursor:
            try:
                await self.calculate_node_metrics(node["id"])
                stats["processed"] += 1
            except Exception as e:
                stats["errors"] += 1
        
        return stats
    
    async def get_top_by_influence(self, limit: int = 20) -> List[Dict]:
        """Get nodes with highest influence"""
        cursor = self.node_metrics.find().sort("influence_score", -1).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def get_graph_summary_metrics(self) -> Dict:
        """Get overall graph metrics"""
        node_count = await self.graph_nodes.count_documents({})
        edge_count = await self.graph_edges.count_documents({})
        
        # Average degree
        avg_degree = (2 * edge_count / node_count) if node_count > 0 else 0
        
        # Density
        density = 0.0
        if node_count > 1:
            max_edges = node_count * (node_count - 1) / 2
            density = edge_count / max_edges if max_edges > 0 else 0
        
        return {
            "node_count": node_count,
            "edge_count": edge_count,
            "avg_degree": round(avg_degree, 2),
            "density": round(density, 6)
        }
