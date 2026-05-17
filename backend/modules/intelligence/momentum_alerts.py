"""
Momentum Velocity Alerts
========================

Alerts when entities show significant momentum changes:
- spike_up: velocity > threshold (rising star)
- spike_down: velocity < -threshold (falling)
- breakout: momentum crosses 50/70 threshold
- dormant: previously active entity goes quiet

Collections:
    momentum_alerts - Active and historical alerts
    momentum_subscriptions - User/entity subscriptions
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Alert thresholds
VELOCITY_SPIKE_THRESHOLD = 10.0  # Momentum velocity change
MOMENTUM_HIGH_THRESHOLD = 70.0    # High momentum breakout
MOMENTUM_MID_THRESHOLD = 50.0     # Mid momentum breakout
VELOCITY_DROP_THRESHOLD = -10.0   # Significant drop


class MomentumAlertEngine:
    """
    Generates alerts based on momentum velocity changes.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.alerts = db.momentum_alerts
        self.subscriptions = db.momentum_subscriptions
        self.entity_momentum = db.entity_momentum
        self.momentum_history = db.entity_momentum_history
    
    async def ensure_indexes(self):
        """Create indexes for alert collections"""
        await self.alerts.create_index("alert_id", unique=True)
        await self.alerts.create_index("entity_key")
        await self.alerts.create_index("alert_type")
        await self.alerts.create_index("severity")
        await self.alerts.create_index("status")
        await self.alerts.create_index("created_at")
        
        await self.subscriptions.create_index(
            [("user_id", 1), ("entity_key", 1)],
            unique=True
        )
        
        logger.info("[MomentumAlerts] Indexes created")
    
    async def check_all_entities(self) -> Dict[str, Any]:
        """
        Check all entities for momentum alerts.
        Called by scheduler.
        """
        now = datetime.now(timezone.utc)
        alerts_created = 0
        entities_checked = 0
        
        cursor = self.entity_momentum.find({})
        
        async for entity in cursor:
            entities_checked += 1
            entity_key = entity.get("entity_key")
            momentum_score = entity.get("momentum_score", 0)
            velocity = entity.get("momentum_velocity", 0)
            
            # Check velocity spike up
            if velocity >= VELOCITY_SPIKE_THRESHOLD:
                await self._create_alert(
                    entity_key=entity_key,
                    alert_type="spike_up",
                    severity="info",
                    message=f"Momentum velocity spike: +{velocity:.1f}",
                    data={
                        "momentum_score": momentum_score,
                        "velocity": velocity,
                        "entity_type": entity.get("entity_type"),
                        "entity_id": entity.get("entity_id")
                    }
                )
                alerts_created += 1
            
            # Check velocity drop
            elif velocity <= VELOCITY_DROP_THRESHOLD:
                await self._create_alert(
                    entity_key=entity_key,
                    alert_type="spike_down",
                    severity="warning",
                    message=f"Momentum velocity drop: {velocity:.1f}",
                    data={
                        "momentum_score": momentum_score,
                        "velocity": velocity,
                        "entity_type": entity.get("entity_type"),
                        "entity_id": entity.get("entity_id")
                    }
                )
                alerts_created += 1
            
            # Check high momentum breakout
            if momentum_score >= MOMENTUM_HIGH_THRESHOLD:
                # Check if recently crossed threshold
                prev = await self._get_previous_momentum(entity_key)
                if prev and prev < MOMENTUM_HIGH_THRESHOLD:
                    await self._create_alert(
                        entity_key=entity_key,
                        alert_type="breakout_high",
                        severity="info",
                        message=f"Crossed {MOMENTUM_HIGH_THRESHOLD} momentum threshold",
                        data={
                            "momentum_score": momentum_score,
                            "previous_score": prev,
                            "entity_type": entity.get("entity_type"),
                            "entity_id": entity.get("entity_id")
                        }
                    )
                    alerts_created += 1
            
            # Check mid momentum breakout
            elif momentum_score >= MOMENTUM_MID_THRESHOLD:
                prev = await self._get_previous_momentum(entity_key)
                if prev and prev < MOMENTUM_MID_THRESHOLD:
                    await self._create_alert(
                        entity_key=entity_key,
                        alert_type="breakout_mid",
                        severity="info",
                        message=f"Crossed {MOMENTUM_MID_THRESHOLD} momentum threshold",
                        data={
                            "momentum_score": momentum_score,
                            "previous_score": prev,
                            "entity_type": entity.get("entity_type"),
                            "entity_id": entity.get("entity_id")
                        }
                    )
                    alerts_created += 1
        
        result = {
            "entities_checked": entities_checked,
            "alerts_created": alerts_created,
            "checked_at": now.isoformat()
        }
        
        logger.info(f"[MomentumAlerts] Checked {entities_checked} entities, {alerts_created} alerts")
        
        return result
    
    async def _get_previous_momentum(self, entity_key: str) -> Optional[float]:
        """Get previous day momentum score"""
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        yesterday = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        
        record = await self.momentum_history.find_one({
            "entity_key": entity_key,
            "date": yesterday
        })
        
        return record.get("momentum_score") if record else None
    
    async def _create_alert(
        self,
        entity_key: str,
        alert_type: str,
        severity: str,
        message: str,
        data: Dict = None
    ) -> str:
        """Create a momentum alert"""
        now = datetime.now(timezone.utc)
        alert_id = f"mom_{alert_type}_{entity_key}_{now.strftime('%Y%m%d%H%M')}"
        
        # Check for duplicate (same alert in last hour)
        recent = await self.alerts.find_one({
            "entity_key": entity_key,
            "alert_type": alert_type,
            "created_at": {"$gte": now - timedelta(hours=1)}
        })
        
        if recent:
            return recent.get("alert_id")  # Skip duplicate
        
        alert = {
            "alert_id": alert_id,
            "entity_key": entity_key,
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "data": data or {},
            "status": "active",
            "created_at": now
        }
        
        await self.alerts.insert_one(alert)
        
        # Notify subscribers (future: webhook/email)
        await self._notify_subscribers(entity_key, alert)
        
        logger.info(f"[MomentumAlerts] {alert_type}: {entity_key} - {message}")
        
        return alert_id
    
    async def _notify_subscribers(self, entity_key: str, alert: Dict):
        """Notify subscribers of an alert (placeholder for webhook/email)"""
        # Get subscriptions for this entity
        cursor = self.subscriptions.find({"entity_key": entity_key})
        
        async for sub in cursor:
            # Future: send webhook/email
            logger.debug(f"[MomentumAlerts] Would notify {sub.get('user_id')} about {entity_key}")
    
    async def get_alerts(
        self,
        entity_key: str = None,
        alert_type: str = None,
        status: str = None,
        severity: str = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get alerts with filters"""
        query = {}
        if entity_key:
            query["entity_key"] = entity_key
        if alert_type:
            query["alert_type"] = alert_type
        if status:
            query["status"] = status
        if severity:
            query["severity"] = severity
        
        cursor = self.alerts.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def acknowledge_alert(self, alert_id: str) -> bool:
        """Mark alert as acknowledged"""
        result = await self.alerts.update_one(
            {"alert_id": alert_id},
            {
                "$set": {
                    "status": "acknowledged",
                    "acknowledged_at": datetime.now(timezone.utc)
                }
            }
        )
        return result.modified_count > 0
    
    async def subscribe(
        self,
        user_id: str,
        entity_key: str
    ) -> Dict:
        """Subscribe to entity alerts"""
        now = datetime.now(timezone.utc)
        
        sub = {
            "user_id": user_id,
            "entity_key": entity_key,
            "created_at": now
        }
        
        await self.subscriptions.update_one(
            {"user_id": user_id, "entity_key": entity_key},
            {"$set": sub},
            upsert=True
        )
        
        return sub
    
    async def unsubscribe(
        self,
        user_id: str,
        entity_key: str
    ) -> bool:
        """Unsubscribe from entity alerts"""
        result = await self.subscriptions.delete_one({
            "user_id": user_id,
            "entity_key": entity_key
        })
        return result.deleted_count > 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get alert statistics"""
        total = await self.alerts.count_documents({})
        active = await self.alerts.count_documents({"status": "active"})
        
        # By type
        pipeline = [
            {"$group": {
                "_id": "$alert_type",
                "count": {"$sum": 1}
            }}
        ]
        type_stats = await self.alerts.aggregate(pipeline).to_list(20)
        
        # By severity
        pipeline = [
            {"$group": {
                "_id": "$severity",
                "count": {"$sum": 1}
            }}
        ]
        severity_stats = await self.alerts.aggregate(pipeline).to_list(10)
        
        # Recent alerts (24h)
        day_ago = datetime.now(timezone.utc) - timedelta(days=1)
        recent = await self.alerts.count_documents({
            "created_at": {"$gte": day_ago}
        })
        
        return {
            "total_alerts": total,
            "active_alerts": active,
            "alerts_24h": recent,
            "by_type": {s["_id"]: s["count"] for s in type_stats},
            "by_severity": {s["_id"]: s["count"] for s in severity_stats}
        }


# Singleton
_alert_engine: Optional[MomentumAlertEngine] = None


def get_momentum_alert_engine(db: AsyncIOMotorDatabase = None) -> MomentumAlertEngine:
    """Get or create alert engine instance"""
    global _alert_engine
    if db is not None:
        _alert_engine = MomentumAlertEngine(db)
    return _alert_engine
