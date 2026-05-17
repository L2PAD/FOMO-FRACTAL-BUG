"""
Drift Detection Engine
======================

Detects when API endpoints change or break.
Automatically triggers re-discovery when drift is detected.

Drift Types:
- Schema drift: Response structure changed
- Status drift: Endpoint returns errors
- Performance drift: Latency significantly increased
- Data drift: Response data quality degraded

Pipeline:
    Scheduled Validation
    ↓
    Compare with baseline
    ↓
    Detect drift
    ↓
    Calculate severity
    ↓
    Trigger re-discovery (if needed)
"""

import logging
import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
import httpx

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


@dataclass
class DriftReport:
    """Report of detected drift"""
    endpoint_id: str
    domain: str
    drift_type: str  # schema, status, performance, data
    severity: str    # low, medium, high, critical
    details: Dict = field(default_factory=dict)
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    action_taken: Optional[str] = None


class DriftDetector:
    """
    Detects API drift and triggers re-discovery.
    
    Features:
    - Schema comparison (field changes)
    - Status monitoring (error rates)
    - Performance tracking (latency)
    - Data quality checks (null rates, record counts)
    """
    
    # Thresholds
    LATENCY_THRESHOLD_MS = 5000  # 5 seconds
    ERROR_RATE_THRESHOLD = 0.3   # 30% errors
    SCHEMA_CHANGE_THRESHOLD = 0.2  # 20% field changes
    DATA_QUALITY_THRESHOLD = 0.5   # 50% null rate
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.endpoints = db.endpoint_registry
        self.drift_logs = db.drift_logs
        self.baselines = db.endpoint_baselines
        
    async def check_drift(self, endpoint_id: str) -> Optional[DriftReport]:
        """
        Check single endpoint for drift.
        
        Returns DriftReport if drift detected, None otherwise.
        """
        endpoint = await self.endpoints.find_one({"id": endpoint_id}, {"_id": 0})
        if not endpoint:
            return None
        
        baseline = await self.baselines.find_one({"endpoint_id": endpoint_id}, {"_id": 0})
        
        # Fetch current state
        current = await self._fetch_endpoint_state(endpoint)
        if not current:
            return DriftReport(
                endpoint_id=endpoint_id,
                domain=endpoint.get("domain", ""),
                drift_type="status",
                severity="high",
                details={"error": "Failed to fetch endpoint"}
            )
        
        # Check different drift types
        drift = None
        
        # 1. Status drift (errors)
        if current.get("status_code", 200) >= 400:
            drift = DriftReport(
                endpoint_id=endpoint_id,
                domain=endpoint.get("domain", ""),
                drift_type="status",
                severity="critical" if current.get("status_code", 500) >= 500 else "high",
                details={
                    "status_code": current.get("status_code"),
                    "expected": 200
                }
            )
        
        # 2. Performance drift (latency)
        elif current.get("latency_ms", 0) > self.LATENCY_THRESHOLD_MS:
            drift = DriftReport(
                endpoint_id=endpoint_id,
                domain=endpoint.get("domain", ""),
                drift_type="performance",
                severity="medium",
                details={
                    "latency_ms": current.get("latency_ms"),
                    "threshold": self.LATENCY_THRESHOLD_MS
                }
            )
        
        # 3. Schema drift (if we have baseline)
        elif baseline and current.get("schema"):
            schema_drift = self._detect_schema_drift(
                baseline.get("schema", {}),
                current.get("schema", {})
            )
            if schema_drift:
                drift = DriftReport(
                    endpoint_id=endpoint_id,
                    domain=endpoint.get("domain", ""),
                    drift_type="schema",
                    severity=schema_drift["severity"],
                    details=schema_drift
                )
        
        # 4. Data drift (quality)
        elif baseline and current.get("data"):
            data_drift = self._detect_data_drift(
                baseline.get("data_stats", {}),
                current.get("data")
            )
            if data_drift:
                drift = DriftReport(
                    endpoint_id=endpoint_id,
                    domain=endpoint.get("domain", ""),
                    drift_type="data",
                    severity=data_drift["severity"],
                    details=data_drift
                )
        
        # Log drift if detected
        if drift:
            await self._log_drift(drift)
            
            # Update endpoint status
            await self.endpoints.update_one(
                {"id": endpoint_id},
                {"$set": {
                    "drift_detected": True,
                    "drift_type": drift.drift_type,
                    "drift_severity": drift.severity,
                    "last_drift_check": datetime.now(timezone.utc).isoformat()
                }}
            )
        else:
            # Update last check time
            await self.endpoints.update_one(
                {"id": endpoint_id},
                {"$set": {
                    "drift_detected": False,
                    "last_drift_check": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            # Update baseline if no drift
            if current:
                await self._update_baseline(endpoint_id, current)
        
        return drift
    
    async def check_domain_drift(self, domain: str) -> List[DriftReport]:
        """Check all endpoints for a domain"""
        drifts = []
        
        cursor = self.endpoints.find({"domain": domain}, {"_id": 0, "id": 1})
        async for ep in cursor:
            drift = await self.check_drift(ep["id"])
            if drift:
                drifts.append(drift)
        
        return drifts
    
    async def check_all_drift(self, limit: int = 50) -> List[DriftReport]:
        """Check all active endpoints for drift"""
        drifts = []
        
        # Get endpoints needing check
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        
        cursor = self.endpoints.find({
            "status": "active",
            "$or": [
                {"last_drift_check": {"$exists": False}},
                {"last_drift_check": {"$lt": cutoff.isoformat()}}
            ]
        }, {"_id": 0, "id": 1}).limit(limit)
        
        async for ep in cursor:
            drift = await self.check_drift(ep["id"])
            if drift:
                drifts.append(drift)
        
        return drifts
    
    async def _fetch_endpoint_state(self, endpoint: Dict) -> Optional[Dict]:
        """Fetch current endpoint state"""
        try:
            headers = endpoint.get("headers", {})
            cookies = endpoint.get("cookies", {})
            
            if cookies:
                headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
            
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                if endpoint.get("method", "GET") == "GET":
                    response = await client.get(endpoint["url"], headers=headers)
                else:
                    response = await client.post(
                        endpoint["url"],
                        headers=headers,
                        content=endpoint.get("body")
                    )
                
                latency = response.elapsed.total_seconds() * 1000 if response.elapsed else 0
                
                state = {
                    "status_code": response.status_code,
                    "latency_ms": latency,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                # Parse JSON response
                if response.status_code == 200 and "json" in response.headers.get("content-type", ""):
                    data = response.json()
                    state["data"] = data
                    state["schema"] = self._extract_schema(data)
                    state["data_stats"] = self._calculate_data_stats(data)
                
                return state
                
        except Exception as e:
            logger.error(f"[DriftDetector] Fetch error: {e}")
            return None
    
    def _extract_schema(self, data) -> Dict:
        """Extract schema from data"""
        schema = {"type": type(data).__name__}
        
        if isinstance(data, list) and data:
            schema["array_length"] = len(data)
            if isinstance(data[0], dict):
                schema["fields"] = sorted(data[0].keys())
                schema["field_types"] = {k: type(v).__name__ for k, v in data[0].items()}
        elif isinstance(data, dict):
            schema["fields"] = sorted(data.keys())
            schema["field_types"] = {k: type(v).__name__ for k, v in data.items()}
            
            # Check for data wrappers
            for key in ['data', 'result', 'results', 'items']:
                if key in data and isinstance(data[key], list):
                    schema["data_key"] = key
                    schema["array_length"] = len(data[key])
                    if data[key] and isinstance(data[key][0], dict):
                        schema["item_fields"] = sorted(data[key][0].keys())
                    break
        
        return schema
    
    def _calculate_data_stats(self, data) -> Dict:
        """Calculate data statistics for quality checks"""
        stats = {
            "record_count": 0,
            "null_rate": 0,
            "schema_hash": ""
        }
        
        # Get items
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            for key in ['data', 'result', 'results', 'items']:
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    break
        
        if not items:
            return stats
        
        stats["record_count"] = len(items)
        
        # Calculate null rate
        if items and isinstance(items[0], dict):
            null_counts = 0
            total_fields = 0
            for item in items[:100]:  # Sample first 100
                for v in item.values():
                    total_fields += 1
                    if v is None:
                        null_counts += 1
            
            stats["null_rate"] = null_counts / total_fields if total_fields > 0 else 0
        
        # Schema hash
        if items and isinstance(items[0], dict):
            fields = sorted(items[0].keys())
            stats["schema_hash"] = hashlib.md5(str(fields).encode()).hexdigest()[:8]
        
        return stats
    
    def _detect_schema_drift(self, baseline: Dict, current: Dict) -> Optional[Dict]:
        """Detect schema changes"""
        baseline_fields = set(baseline.get("fields", []))
        current_fields = set(current.get("fields", []))
        
        if not baseline_fields:
            return None
        
        added = current_fields - baseline_fields
        removed = baseline_fields - current_fields
        
        if not added and not removed:
            return None
        
        change_rate = len(added | removed) / len(baseline_fields)
        
        severity = "low"
        if change_rate > 0.5:
            severity = "critical"
        elif change_rate > 0.3:
            severity = "high"
        elif change_rate > 0.1:
            severity = "medium"
        
        return {
            "added_fields": list(added),
            "removed_fields": list(removed),
            "change_rate": change_rate,
            "severity": severity
        }
    
    def _detect_data_drift(self, baseline: Dict, current_data) -> Optional[Dict]:
        """Detect data quality changes"""
        current_stats = self._calculate_data_stats(current_data)
        
        # Record count change
        baseline_count = baseline.get("record_count", 0)
        current_count = current_stats.get("record_count", 0)
        
        if baseline_count > 0:
            count_change = abs(current_count - baseline_count) / baseline_count
        else:
            count_change = 0
        
        # Null rate change
        baseline_null = baseline.get("null_rate", 0)
        current_null = current_stats.get("null_rate", 0)
        null_increase = current_null - baseline_null
        
        # Schema hash change
        schema_changed = baseline.get("schema_hash") != current_stats.get("schema_hash")
        
        # Determine if drift
        issues = []
        severity = "low"
        
        if count_change > 0.5:
            issues.append(f"Record count changed by {count_change*100:.0f}%")
            severity = "medium"
        
        if null_increase > 0.2:
            issues.append(f"Null rate increased by {null_increase*100:.0f}%")
            severity = "high"
        
        if schema_changed:
            issues.append("Schema hash changed")
            if severity == "low":
                severity = "medium"
        
        if not issues:
            return None
        
        return {
            "issues": issues,
            "record_count_change": count_change,
            "null_rate_change": null_increase,
            "schema_changed": schema_changed,
            "severity": severity
        }
    
    async def _log_drift(self, drift: DriftReport):
        """Log drift report"""
        await self.drift_logs.insert_one(asdict(drift))
    
    async def _update_baseline(self, endpoint_id: str, state: Dict):
        """Update endpoint baseline"""
        baseline = {
            "endpoint_id": endpoint_id,
            "schema": state.get("schema", {}),
            "data_stats": state.get("data_stats", {}),
            "latency_ms": state.get("latency_ms", 0),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        await self.baselines.update_one(
            {"endpoint_id": endpoint_id},
            {"$set": baseline},
            upsert=True
        )
    
    async def get_drift_stats(self) -> Dict:
        """Get drift statistics"""
        total = await self.drift_logs.count_documents({})
        
        # By type
        type_pipeline = [
            {"$group": {"_id": "$drift_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        by_type = {}
        async for doc in self.drift_logs.aggregate(type_pipeline):
            by_type[doc["_id"]] = doc["count"]
        
        # By severity
        severity_pipeline = [
            {"$group": {"_id": "$severity", "count": {"$sum": 1}}}
        ]
        by_severity = {}
        async for doc in self.drift_logs.aggregate(severity_pipeline):
            by_severity[doc["_id"]] = doc["count"]
        
        # Recent drifts
        recent = []
        cursor = self.drift_logs.find({}, {"_id": 0}).sort("detected_at", -1).limit(10)
        async for doc in cursor:
            recent.append(doc)
        
        return {
            "total_drifts": total,
            "by_type": by_type,
            "by_severity": by_severity,
            "recent": recent
        }
