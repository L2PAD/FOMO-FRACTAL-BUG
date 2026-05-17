"""
Graph Growth Monitor
====================

Tracks graph evolution and growth patterns:
- nodes_added_7d / 30d
- edges_added_7d / 30d
- new_clusters
- avg_degree
- density
- growth velocity

Collections:
    graph_growth_metrics - Daily snapshots of graph metrics
    graph_growth_alerts - Growth anomaly alerts
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class GraphGrowthMonitor:
    """
    Monitors graph growth and evolution patterns.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.metrics = db.graph_growth_metrics
        self.alerts = db.graph_growth_alerts
        
        # Graph collections
        self.graph_nodes = db.graph_nodes
        self.graph_edges = db.graph_edges
        self.derived_edges = db.graph_derived_edges
        self.intelligence_edges = db.graph_intelligence_edges
    
    async def ensure_indexes(self):
        """Create indexes for growth monitoring"""
        await self.metrics.create_index("date", unique=True)
        await self.metrics.create_index("created_at")
        
        await self.alerts.create_index("alert_id", unique=True)
        await self.alerts.create_index("alert_type")
        await self.alerts.create_index("created_at")
        await self.alerts.create_index("status")
        
        logger.info("[GraphGrowth] Indexes created")
    
    async def capture_snapshot(self) -> Dict[str, Any]:
        """
        Capture current graph metrics snapshot.
        Called daily by scheduler.
        """
        now = datetime.now(timezone.utc)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Count nodes by type
        nodes_total = await self.graph_nodes.count_documents({})
        
        nodes_by_type = {}
        for node_type in ["project", "fund", "person", "exchange", "token"]:
            count = await self.graph_nodes.count_documents({"entity_type": node_type})
            nodes_by_type[node_type] = count
        
        # Count edges by layer
        factual_edges = await self.graph_edges.count_documents({})
        derived_edges = await self.derived_edges.count_documents({})
        intelligence_edges = await self.intelligence_edges.count_documents({})
        edges_total = factual_edges + derived_edges + intelligence_edges
        
        # Calculate avg degree
        avg_degree = (edges_total * 2) / max(nodes_total, 1)
        
        # Calculate density (for small graphs)
        max_edges = nodes_total * (nodes_total - 1) / 2
        density = edges_total / max(max_edges, 1) if max_edges > 0 else 0
        
        # Get yesterday's snapshot for growth calculation
        yesterday = today - timedelta(days=1)
        prev_snapshot = await self.metrics.find_one({"date": yesterday})
        
        # Calculate growth
        if prev_snapshot:
            nodes_growth_1d = nodes_total - prev_snapshot.get("nodes_total", 0)
            edges_growth_1d = edges_total - prev_snapshot.get("edges_total", 0)
        else:
            nodes_growth_1d = 0
            edges_growth_1d = 0
        
        # Get 7d ago snapshot
        week_ago = today - timedelta(days=7)
        week_snapshot = await self.metrics.find_one({"date": week_ago})
        
        if week_snapshot:
            nodes_growth_7d = nodes_total - week_snapshot.get("nodes_total", 0)
            edges_growth_7d = edges_total - week_snapshot.get("edges_total", 0)
        else:
            nodes_growth_7d = 0
            edges_growth_7d = 0
        
        # Get 30d ago snapshot
        month_ago = today - timedelta(days=30)
        month_snapshot = await self.metrics.find_one({"date": month_ago})
        
        if month_snapshot:
            nodes_growth_30d = nodes_total - month_snapshot.get("nodes_total", 0)
            edges_growth_30d = edges_total - month_snapshot.get("edges_total", 0)
        else:
            nodes_growth_30d = 0
            edges_growth_30d = 0
        
        # Build snapshot
        snapshot = {
            "date": today,
            "created_at": now,
            
            # Totals
            "nodes_total": nodes_total,
            "edges_total": edges_total,
            
            # By type
            "nodes_by_type": nodes_by_type,
            "edges_by_layer": {
                "factual": factual_edges,
                "derived": derived_edges,
                "intelligence": intelligence_edges
            },
            
            # Metrics
            "avg_degree": round(avg_degree, 2),
            "density": round(density, 6),
            
            # Growth
            "growth": {
                "nodes_1d": nodes_growth_1d,
                "nodes_7d": nodes_growth_7d,
                "nodes_30d": nodes_growth_30d,
                "edges_1d": edges_growth_1d,
                "edges_7d": edges_growth_7d,
                "edges_30d": edges_growth_30d
            },
            
            # Velocity (daily average)
            "velocity": {
                "nodes_daily_avg_7d": round(nodes_growth_7d / 7, 1) if nodes_growth_7d else 0,
                "edges_daily_avg_7d": round(edges_growth_7d / 7, 1) if edges_growth_7d else 0
            }
        }
        
        # Upsert today's snapshot
        await self.metrics.update_one(
            {"date": today},
            {"$set": snapshot},
            upsert=True
        )
        
        # Check for growth anomalies
        await self._check_growth_anomalies(snapshot, prev_snapshot)
        
        logger.info(f"[GraphGrowth] Snapshot: {nodes_total} nodes, {edges_total} edges")
        
        return snapshot
    
    async def _check_growth_anomalies(
        self,
        current: Dict,
        previous: Optional[Dict]
    ):
        """Check for unusual growth patterns"""
        if not previous:
            return
        
        now = datetime.now(timezone.utc)
        
        # Check for sudden node growth (>50% in 1 day)
        prev_nodes = previous.get("nodes_total", 0)
        if prev_nodes > 0:
            node_growth_pct = (current["nodes_total"] - prev_nodes) / prev_nodes
            if node_growth_pct > 0.5:
                await self._create_alert(
                    alert_type="node_spike",
                    message=f"Node count increased by {node_growth_pct*100:.0f}%",
                    severity="warning",
                    data={"growth_pct": node_growth_pct}
                )
        
        # Check for sudden edge growth (>100% in 1 day)
        prev_edges = previous.get("edges_total", 0)
        if prev_edges > 0:
            edge_growth_pct = (current["edges_total"] - prev_edges) / prev_edges
            if edge_growth_pct > 1.0:
                await self._create_alert(
                    alert_type="edge_spike",
                    message=f"Edge count increased by {edge_growth_pct*100:.0f}%",
                    severity="warning",
                    data={"growth_pct": edge_growth_pct}
                )
    
    async def _create_alert(
        self,
        alert_type: str,
        message: str,
        severity: str = "info",
        data: Dict = None
    ):
        """Create a growth alert"""
        now = datetime.now(timezone.utc)
        alert_id = f"{alert_type}_{now.strftime('%Y%m%d%H%M%S')}"
        
        alert = {
            "alert_id": alert_id,
            "alert_type": alert_type,
            "message": message,
            "severity": severity,
            "data": data or {},
            "status": "active",
            "created_at": now
        }
        
        await self.alerts.insert_one(alert)
        logger.warning(f"[GraphGrowth] Alert: {message}")
    
    async def get_current_metrics(self) -> Dict[str, Any]:
        """Get current graph metrics (live calculation)"""
        now = datetime.now(timezone.utc)
        
        # Quick counts
        nodes = await self.graph_nodes.count_documents({})
        factual = await self.graph_edges.count_documents({})
        derived = await self.derived_edges.count_documents({})
        intelligence = await self.intelligence_edges.count_documents({})
        total_edges = factual + derived + intelligence
        
        # Get growth from snapshots
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        week_snapshot = await self.metrics.find_one({"date": week_ago})
        month_snapshot = await self.metrics.find_one({"date": month_ago})
        
        return {
            "ts": now.isoformat(),
            "current": {
                "nodes": nodes,
                "edges_total": total_edges,
                "edges_factual": factual,
                "edges_derived": derived,
                "edges_intelligence": intelligence,
                "avg_degree": round((total_edges * 2) / max(nodes, 1), 2)
            },
            "growth_7d": {
                "nodes": nodes - week_snapshot.get("nodes_total", 0) if week_snapshot else 0,
                "edges": total_edges - week_snapshot.get("edges_total", 0) if week_snapshot else 0
            },
            "growth_30d": {
                "nodes": nodes - month_snapshot.get("nodes_total", 0) if month_snapshot else 0,
                "edges": total_edges - month_snapshot.get("edges_total", 0) if month_snapshot else 0
            }
        }
    
    async def get_growth_history(
        self,
        days: int = 30
    ) -> List[Dict]:
        """Get historical growth data"""
        from_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        cursor = self.metrics.find(
            {"date": {"$gte": from_date}},
            {"_id": 0}
        ).sort("date", 1)
        
        return await cursor.to_list(length=days)
    
    async def get_growth_alerts(
        self,
        status: str = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get growth alerts"""
        query = {}
        if status:
            query["status"] = status
        
        cursor = self.alerts.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        
        return await cursor.to_list(length=limit)


# Singleton
_monitor: Optional[GraphGrowthMonitor] = None


def get_graph_growth_monitor(db: AsyncIOMotorDatabase = None) -> GraphGrowthMonitor:
    """Get or create growth monitor instance"""
    global _monitor
    if db is not None:
        _monitor = GraphGrowthMonitor(db)
    return _monitor
