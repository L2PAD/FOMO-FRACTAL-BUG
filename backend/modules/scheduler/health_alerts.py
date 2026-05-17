"""
Health Alerts System
====================
Monitors source health and generates alerts/notifications.
Stores alerts in MongoDB and exposes via API.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(str, Enum):
    SOURCE_DOWN = "source_down"
    SOURCE_DEGRADED = "source_degraded"
    SOURCE_RECOVERED = "source_recovered"
    HIGH_FAIL_RATE = "high_fail_rate"
    SYNC_DELAYED = "sync_delayed"
    EXCHANGE_ISSUE = "exchange_issue"
    TIER_DEGRADED = "tier_degraded"


@dataclass
class HealthAlert:
    """Health alert definition"""
    alert_id: str
    alert_type: AlertType
    severity: AlertSeverity
    source_id: str
    tree: str  # "intel" or "exchange"
    message: str
    details: Dict
    created_at: datetime
    acknowledged: bool = False
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat()
        d["resolved_at"] = self.resolved_at.isoformat() if self.resolved_at else None
        d["alert_type"] = self.alert_type.value
        d["severity"] = self.severity.value
        return d


class HealthAlertManager:
    """
    Manages health alerts for all data sources.
    Monitors both Intel Tree and Exchange Tree.
    """
    
    def __init__(self, db):
        self.db = db
        self._alert_counter = 0
        self._active_alerts: Dict[str, HealthAlert] = {}
    
    async def ensure_indexes(self):
        """Create indexes for alerts collection"""
        try:
            await self.db.health_alerts.create_index([("created_at", -1)])
            await self.db.health_alerts.create_index([("source_id", 1)])
            await self.db.health_alerts.create_index([("resolved", 1)])
            await self.db.health_alerts.create_index([("severity", 1)])
        except:
            pass
    
    def _generate_alert_id(self) -> str:
        self._alert_counter += 1
        return f"alert_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{self._alert_counter}"
    
    async def create_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        source_id: str,
        tree: str,
        message: str,
        details: Dict = None
    ) -> HealthAlert:
        """Create and store a new alert"""
        alert = HealthAlert(
            alert_id=self._generate_alert_id(),
            alert_type=alert_type,
            severity=severity,
            source_id=source_id,
            tree=tree,
            message=message,
            details=details or {},
            created_at=datetime.now(timezone.utc)
        )
        
        # Store in MongoDB
        await self.db.health_alerts.insert_one(alert.to_dict())
        
        # Track active alerts
        key = f"{source_id}:{alert_type.value}"
        self._active_alerts[key] = alert
        
        logger.warning(f"[HealthAlert] {severity.value.upper()}: {message}")
        
        return alert
    
    async def resolve_alert(self, source_id: str, alert_type: AlertType):
        """Resolve an active alert"""
        key = f"{source_id}:{alert_type.value}"
        
        if key in self._active_alerts:
            del self._active_alerts[key]
        
        # Mark as resolved in DB
        await self.db.health_alerts.update_many(
            {
                "source_id": source_id,
                "alert_type": alert_type.value,
                "resolved": False
            },
            {
                "$set": {
                    "resolved": True,
                    "resolved_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
    
    async def acknowledge_alert(self, alert_id: str):
        """Mark alert as acknowledged"""
        await self.db.health_alerts.update_one(
            {"alert_id": alert_id},
            {"$set": {"acknowledged": True}}
        )
    
    async def get_active_alerts(self, tree: str = None) -> List[Dict]:
        """Get all unresolved alerts"""
        query = {"resolved": False}
        if tree:
            query["tree"] = tree
        
        cursor = self.db.health_alerts.find(
            query, {"_id": 0}
        ).sort("created_at", -1).limit(100)
        
        return await cursor.to_list(100)
    
    async def get_recent_alerts(self, hours: int = 24, limit: int = 50) -> List[Dict]:
        """Get recent alerts"""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        cursor = self.db.health_alerts.find(
            {"created_at": {"$gte": since.isoformat()}},
            {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        
        return await cursor.to_list(limit)
    
    async def get_alert_stats(self) -> Dict:
        """Get alert statistics"""
        now = datetime.now(timezone.utc)
        last_24h = (now - timedelta(hours=24)).isoformat()
        
        total_active = await self.db.health_alerts.count_documents({"resolved": False})
        
        by_severity = {}
        for sev in AlertSeverity:
            count = await self.db.health_alerts.count_documents({
                "severity": sev.value,
                "resolved": False
            })
            by_severity[sev.value] = count
        
        recent_count = await self.db.health_alerts.count_documents({
            "created_at": {"$gte": last_24h}
        })
        
        return {
            "active_alerts": total_active,
            "by_severity": by_severity,
            "last_24h": recent_count
        }
    
    # ═══════════════════════════════════════════════════════════════
    # CHECK FUNCTIONS
    # ═══════════════════════════════════════════════════════════════
    
    async def check_intel_source(self, source_id: str, health: Dict):
        """Check Intel Tree source health and generate alerts"""
        health_score = health.get("health_score", 1)
        consecutive_fails = health.get("consecutive_fails", 0)
        is_paused = health.get("is_paused", False)
        
        # Source down (paused due to fails)
        if is_paused:
            existing = f"{source_id}:{AlertType.SOURCE_DOWN.value}"
            if existing not in self._active_alerts:
                await self.create_alert(
                    AlertType.SOURCE_DOWN,
                    AlertSeverity.ERROR,
                    source_id,
                    "intel",
                    f"Source {source_id} is DOWN (auto-paused after {consecutive_fails} failures)",
                    {"consecutive_fails": consecutive_fails, "health_score": health_score}
                )
        else:
            # Check if recovered
            await self.resolve_alert(source_id, AlertType.SOURCE_DOWN)
        
        # Degraded (low health score)
        if 0.3 <= health_score < 0.7 and not is_paused:
            existing = f"{source_id}:{AlertType.SOURCE_DEGRADED.value}"
            if existing not in self._active_alerts:
                await self.create_alert(
                    AlertType.SOURCE_DEGRADED,
                    AlertSeverity.WARNING,
                    source_id,
                    "intel",
                    f"Source {source_id} is DEGRADED (health: {health_score:.0%})",
                    {"health_score": health_score, "consecutive_fails": consecutive_fails}
                )
        elif health_score >= 0.7:
            await self.resolve_alert(source_id, AlertType.SOURCE_DEGRADED)
        
        # High fail rate
        success_rate = health.get("success_rate", 1)
        if success_rate < 0.5 and not is_paused:
            existing = f"{source_id}:{AlertType.HIGH_FAIL_RATE.value}"
            if existing not in self._active_alerts:
                await self.create_alert(
                    AlertType.HIGH_FAIL_RATE,
                    AlertSeverity.WARNING,
                    source_id,
                    "intel",
                    f"Source {source_id} has HIGH FAIL RATE ({success_rate:.0%})",
                    {"success_rate": success_rate}
                )
        elif success_rate >= 0.7:
            await self.resolve_alert(source_id, AlertType.HIGH_FAIL_RATE)
    
    async def check_exchange(self, exchange_id: str, health: Dict):
        """Check Exchange Tree health and generate alerts"""
        health_score = health.get("health_score", 1)
        is_paused = health.get("is_paused", False)
        latency_ms = health.get("latency_ms", 0)
        
        # Exchange down
        if is_paused:
            existing = f"{exchange_id}:{AlertType.EXCHANGE_ISSUE.value}"
            if existing not in self._active_alerts:
                await self.create_alert(
                    AlertType.EXCHANGE_ISSUE,
                    AlertSeverity.ERROR,
                    exchange_id,
                    "exchange",
                    f"Exchange {exchange_id} connection FAILED",
                    {"health_score": health_score}
                )
        else:
            await self.resolve_alert(exchange_id, AlertType.EXCHANGE_ISSUE)
        
        # High latency warning
        if latency_ms > 5000:  # 5 seconds
            await self.create_alert(
                AlertType.SOURCE_DEGRADED,
                AlertSeverity.WARNING,
                exchange_id,
                "exchange",
                f"Exchange {exchange_id} HIGH LATENCY ({latency_ms:.0f}ms)",
                {"latency_ms": latency_ms}
            )
    
    async def check_tier_health(self, tier: int, sources_health: List[Dict]):
        """Check overall tier health"""
        if not sources_health:
            return
        
        healthy_count = sum(1 for s in sources_health if s.get("health_score", 1) >= 0.7)
        total_count = len(sources_health)
        tier_health = healthy_count / total_count if total_count > 0 else 1
        
        if tier_health < 0.5:
            await self.create_alert(
                AlertType.TIER_DEGRADED,
                AlertSeverity.CRITICAL if tier == 1 else AlertSeverity.WARNING,
                f"tier_{tier}",
                "intel",
                f"TIER {tier} DEGRADED: Only {healthy_count}/{total_count} sources healthy",
                {"tier": tier, "healthy": healthy_count, "total": total_count}
            )
        else:
            await self.resolve_alert(f"tier_{tier}", AlertType.TIER_DEGRADED)


# Global instance
_alert_manager: Optional[HealthAlertManager] = None


def get_alert_manager(db) -> HealthAlertManager:
    """Get or create alert manager"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = HealthAlertManager(db)
    return _alert_manager
