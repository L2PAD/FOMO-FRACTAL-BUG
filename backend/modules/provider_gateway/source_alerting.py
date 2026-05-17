"""
Source Alerting System
======================

Monitors source health and generates alerts when sources go down or degrade.

Alert Types:
- source_down: Source status changed to 'down'
- source_degraded: Source status changed to 'degraded'
- source_recovered: Source recovered from down/degraded

Collections:
    source_alerts:
        id: alert_123
        alert_type: source_down
        source_id: coingecko
        severity: critical | warning | info
        title: "CoinGecko is down"
        description: "..."
        created_at: datetime
        resolved_at: datetime | null
        acknowledged: bool
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
import uuid

logger = logging.getLogger(__name__)


class SourceAlertingSystem:
    """
    System for monitoring source health and generating alerts.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.alerts = db.source_alerts
        self.source_metrics = db.source_metrics
        self._previous_states: Dict[str, str] = {}
    
    async def ensure_indexes(self):
        """Create indexes for alerts collection"""
        await self.alerts.create_index("source_id")
        await self.alerts.create_index("alert_type")
        await self.alerts.create_index("severity")
        await self.alerts.create_index("created_at")
        await self.alerts.create_index([("resolved_at", 1), ("acknowledged", 1)])
        logger.info("[SourceAlerting] Indexes created")
    
    async def check_sources_and_alert(self) -> List[Dict[str, Any]]:
        """
        Check all sources and generate alerts for status changes.
        Returns list of new alerts generated.
        """
        new_alerts = []
        
        # Get all source metrics
        cursor = self.source_metrics.find({}, {"_id": 0})
        
        async for source in cursor:
            source_id = source.get("source_id")
            current_status = source.get("status", "unknown")
            previous_status = self._previous_states.get(source_id, "unknown")
            
            # Check for status change
            if current_status != previous_status:
                alert = await self._handle_status_change(
                    source_id, previous_status, current_status, source
                )
                if alert:
                    new_alerts.append(alert)
            
            # Update state
            self._previous_states[source_id] = current_status
        
        return new_alerts
    
    async def _handle_status_change(
        self,
        source_id: str,
        old_status: str,
        new_status: str,
        source_data: Dict
    ) -> Optional[Dict[str, Any]]:
        """Handle a source status change and create alert if needed"""
        now = datetime.now(timezone.utc)
        
        # Skip if transitioning from unknown
        if old_status == "unknown":
            return None
        
        alert = None
        
        if new_status == "down":
            # Source went down - CRITICAL
            alert = {
                "id": f"alert_{uuid.uuid4().hex[:12]}",
                "alert_type": "source_down",
                "source_id": source_id,
                "severity": "critical",
                "title": f"{source_id.upper()} is DOWN",
                "description": f"Source {source_id} has gone offline. Last reliability: {source_data.get('reliability_score', 0)*100:.0f}%. Error rate: {source_data.get('error_rate', 0)*100:.0f}%",
                "previous_status": old_status,
                "current_status": new_status,
                "metrics_snapshot": {
                    "reliability_score": source_data.get("reliability_score"),
                    "error_rate": source_data.get("error_rate"),
                    "final_score": source_data.get("final_score"),
                    "total_fetches": source_data.get("total_fetches")
                },
                "created_at": now,
                "resolved_at": None,
                "acknowledged": False
            }
            logger.warning(f"[SourceAlerting] CRITICAL: {source_id} is DOWN")
            
        elif new_status == "degraded":
            # Source degraded - WARNING
            alert = {
                "id": f"alert_{uuid.uuid4().hex[:12]}",
                "alert_type": "source_degraded",
                "source_id": source_id,
                "severity": "warning",
                "title": f"{source_id.upper()} is DEGRADED",
                "description": f"Source {source_id} performance has degraded. Reliability: {source_data.get('reliability_score', 0)*100:.0f}%. Consider using backup source.",
                "previous_status": old_status,
                "current_status": new_status,
                "metrics_snapshot": {
                    "reliability_score": source_data.get("reliability_score"),
                    "latency_score": source_data.get("latency_score"),
                    "final_score": source_data.get("final_score")
                },
                "created_at": now,
                "resolved_at": None,
                "acknowledged": False
            }
            logger.warning(f"[SourceAlerting] WARNING: {source_id} is DEGRADED")
            
        elif new_status == "healthy" and old_status in ["down", "degraded"]:
            # Source recovered - INFO
            alert = {
                "id": f"alert_{uuid.uuid4().hex[:12]}",
                "alert_type": "source_recovered",
                "source_id": source_id,
                "severity": "info",
                "title": f"{source_id.upper()} RECOVERED",
                "description": f"Source {source_id} has recovered and is now healthy. Current reliability: {source_data.get('reliability_score', 0)*100:.0f}%",
                "previous_status": old_status,
                "current_status": new_status,
                "metrics_snapshot": {
                    "reliability_score": source_data.get("reliability_score"),
                    "final_score": source_data.get("final_score")
                },
                "created_at": now,
                "resolved_at": now,  # Auto-resolved
                "acknowledged": True  # Auto-acknowledged
            }
            logger.info(f"[SourceAlerting] INFO: {source_id} RECOVERED")
            
            # Also resolve any existing alerts for this source
            await self.alerts.update_many(
                {
                    "source_id": source_id,
                    "resolved_at": None
                },
                {
                    "$set": {
                        "resolved_at": now,
                        "resolution_note": "Source recovered automatically"
                    }
                }
            )
        
        if alert:
            await self.alerts.insert_one(alert)
            return alert
        
        return None
    
    async def get_active_alerts(self, severity: str = None) -> List[Dict[str, Any]]:
        """Get all unresolved alerts"""
        query = {"resolved_at": None}
        if severity:
            query["severity"] = severity
        
        cursor = self.alerts.find(query, {"_id": 0}).sort("created_at", -1)
        return await cursor.to_list(100)
    
    async def get_alerts(
        self,
        source_id: str = None,
        severity: str = None,
        include_resolved: bool = False,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get alerts with optional filters"""
        query = {}
        
        if source_id:
            query["source_id"] = source_id
        if severity:
            query["severity"] = severity
        if not include_resolved:
            query["resolved_at"] = None
        
        cursor = self.alerts.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
        return await cursor.to_list(limit)
    
    async def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        result = await self.alerts.update_one(
            {"id": alert_id},
            {"$set": {"acknowledged": True, "acknowledged_at": datetime.now(timezone.utc)}}
        )
        return result.modified_count > 0
    
    async def resolve_alert(self, alert_id: str, note: str = None) -> bool:
        """Resolve an alert"""
        update = {
            "resolved_at": datetime.now(timezone.utc)
        }
        if note:
            update["resolution_note"] = note
        
        result = await self.alerts.update_one(
            {"id": alert_id},
            {"$set": update}
        )
        return result.modified_count > 0
    
    async def get_alert_stats(self) -> Dict[str, Any]:
        """Get alert statistics"""
        total = await self.alerts.count_documents({})
        active = await self.alerts.count_documents({"resolved_at": None})
        acknowledged = await self.alerts.count_documents({"acknowledged": True, "resolved_at": None})
        
        # By severity
        critical = await self.alerts.count_documents({"severity": "critical", "resolved_at": None})
        warning = await self.alerts.count_documents({"severity": "warning", "resolved_at": None})
        
        # By source
        pipeline = [
            {"$match": {"resolved_at": None}},
            {"$group": {"_id": "$source_id", "count": {"$sum": 1}}}
        ]
        by_source = await self.alerts.aggregate(pipeline).to_list(50)
        
        return {
            "total_alerts": total,
            "active_alerts": active,
            "acknowledged": acknowledged,
            "unacknowledged": active - acknowledged,
            "critical": critical,
            "warning": warning,
            "by_source": {r["_id"]: r["count"] for r in by_source}
        }
    
    async def load_previous_states(self):
        """Load previous states from database on startup"""
        cursor = self.source_metrics.find({}, {"source_id": 1, "status": 1})
        async for source in cursor:
            self._previous_states[source["source_id"]] = source.get("status", "unknown")
        logger.info(f"[SourceAlerting] Loaded {len(self._previous_states)} source states")


# Singleton
_alerting_system: Optional[SourceAlertingSystem] = None


def get_source_alerting(db: AsyncIOMotorDatabase = None) -> SourceAlertingSystem:
    """Get or create alerting system instance"""
    global _alerting_system
    if db is not None:
        _alerting_system = SourceAlertingSystem(db)
    return _alerting_system
