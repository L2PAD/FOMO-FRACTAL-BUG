"""
Data Consistency Engine

Self-monitoring system for data quality control.
Automatically detects:
- Schema drift (API changes)
- Source conflicts (data mismatches)
- Missing data (scraper failures)
- Duplicate explosions (dedup failures)
- Data freshness issues

Integrates into pipeline:
Scraper → Raw → Parser → Normalized → Dedup → Consistency Engine → Curated
"""

import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum


class CheckStatus(str, Enum):
    OK = "ok"
    WARNING = "warning"
    FAIL = "fail"
    UNKNOWN = "unknown"


class CheckType(str, Enum):
    SCHEMA_DRIFT = "schema_drift"
    SOURCE_CONFLICT = "source_conflict"
    MISSING_DATA = "missing_data"
    DUPLICATE_EXPLOSION = "duplicate_explosion"
    DATA_FRESHNESS = "data_freshness"
    COUNT_ANOMALY = "count_anomaly"


@dataclass
class ConsistencyCheck:
    """Single consistency check result"""
    check_type: CheckType
    source: str
    endpoint: str
    status: CheckStatus
    message: str
    detected_at: str
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["check_type"] = self.check_type.value
        d["status"] = self.status.value
        return d


@dataclass
class SourceReliability:
    """Source reliability score"""
    source: str
    score: float  # 0.0 - 1.0
    total_checks: int
    passed_checks: int
    last_failure: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EventConfidence:
    """Confidence level for an event"""
    event_id: str
    confidence: str  # "high", "medium", "low"
    sources_count: int
    sources: List[str]
    has_conflict: bool = False
    conflict_details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DataConsistencyEngine:
    """
    Main engine for data quality monitoring.
    
    Usage:
        engine = DataConsistencyEngine(db)
        
        # Run all checks
        results = await engine.run_all_checks()
        
        # Get health status
        health = engine.get_health_status()
        
        # Get source reliability
        reliability = engine.get_source_reliability()
    """
    
    # Expected schemas for each entity type
    EXPECTED_SCHEMAS = {
        "unlock": {
            "required": ["id", "source", "symbol", "unlock_date"],
            "optional": ["amount_usd", "percent_supply", "unlock_type", "project"]
        },
        "funding": {
            "required": ["id", "source", "round_date"],
            "optional": ["symbol", "project", "raised_usd", "round_type", "investors"]
        },
        "investor": {
            "required": ["id", "source", "name"],
            "optional": ["slug", "tier", "portfolio", "aum_usd"]
        },
        "sale": {
            "required": ["id", "source", "start_date", "end_date"],
            "optional": ["symbol", "project", "sale_type", "platform"]
        }
    }
    
    # Thresholds
    COUNT_DROP_THRESHOLD = 0.3  # Alert if count drops by 70%
    DUPLICATE_GROWTH_THRESHOLD = 3.0  # Alert if count grows 3x
    FRESHNESS_THRESHOLD_HOURS = 24  # Alert if no updates in 24h
    CONFLICT_TOLERANCE_PERCENT = 0.20  # 20% tolerance for numeric conflicts
    
    def __init__(self, db):
        self.db = db
        self.checks: List[ConsistencyCheck] = []
        self.source_stats: Dict[str, Dict[str, int]] = {}
    
    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
    
    def _hash_schema(self, keys: List[str]) -> str:
        """Generate hash for schema keys"""
        return hashlib.md5(json.dumps(sorted(keys)).encode()).hexdigest()[:12]
    
    # ═══════════════════════════════════════════════════════════════
    # CHECK: Schema Drift
    # ═══════════════════════════════════════════════════════════════
    
    async def check_schema_drift(self, entity_type: str, sample_records: List[Dict]) -> ConsistencyCheck:
        """
        Check if API response schema has changed.
        
        Example:
            Was: {"unlockUsd": 1000}
            Now: {"unlock_value_usd": 1000}
        """
        expected = self.EXPECTED_SCHEMAS.get(entity_type, {})
        required_fields = expected.get("required", [])
        
        if not sample_records:
            return ConsistencyCheck(
                check_type=CheckType.SCHEMA_DRIFT,
                source=entity_type,
                endpoint=f"normalized_{entity_type}",
                status=CheckStatus.UNKNOWN,
                message="No records to check",
                detected_at=self._now_iso()
            )
        
        missing_fields = []
        for record in sample_records[:10]:
            for field in required_fields:
                if field not in record or record[field] is None:
                    missing_fields.append(field)
        
        if missing_fields:
            unique_missing = list(set(missing_fields))
            return ConsistencyCheck(
                check_type=CheckType.SCHEMA_DRIFT,
                source=entity_type,
                endpoint=f"normalized_{entity_type}",
                status=CheckStatus.FAIL,
                message=f"Schema drift detected: missing fields {unique_missing}",
                detected_at=self._now_iso(),
                details={
                    "missing_fields": unique_missing,
                    "expected_fields": required_fields,
                    "sample_keys": list(sample_records[0].keys()) if sample_records else []
                }
            )
        
        return ConsistencyCheck(
            check_type=CheckType.SCHEMA_DRIFT,
            source=entity_type,
            endpoint=f"normalized_{entity_type}",
            status=CheckStatus.OK,
            message="Schema OK",
            detected_at=self._now_iso(),
            details={
                "schema_hash": self._hash_schema(list(sample_records[0].keys()))
            }
        )
    
    # ═══════════════════════════════════════════════════════════════
    # CHECK: Source Conflict
    # ═══════════════════════════════════════════════════════════════
    
    async def check_source_conflict(
        self, 
        entity_type: str, 
        records_by_source: Dict[str, List[Dict]]
    ) -> ConsistencyCheck:
        """
        Check for data conflicts between sources.
        
        Example:
            Dropstab:   LayerZero funding = $120M
            CryptoRank: LayerZero funding = $100M
        """
        conflicts = []
        
        # Group records by identifier (symbol/project)
        records_by_key: Dict[str, Dict[str, List[Dict]]] = {}
        
        for source, records in records_by_source.items():
            for record in records:
                # Get identifier
                key = record.get("symbol") or record.get("project") or record.get("name")
                if not key:
                    continue
                
                if key not in records_by_key:
                    records_by_key[key] = {}
                if source not in records_by_key[key]:
                    records_by_key[key][source] = []
                records_by_key[key][source].append(record)
        
        # Check for conflicts
        for key, sources in records_by_key.items():
            if len(sources) < 2:
                continue  # Only one source, no conflict possible
            
            # Compare numeric values
            amounts: Dict[str, float] = {}
            for source, recs in sources.items():
                for r in recs:
                    amt = r.get("raised_usd") or r.get("amount_usd") or r.get("aum_usd")
                    if amt is not None and isinstance(amt, (int, float)):
                        amounts[source] = float(amt)
            
            if len(amounts) >= 2:
                values = list(amounts.values())
                max_val = max(values)
                min_val = min(values)
                
                if max_val > 0:
                    diff_pct = (max_val - min_val) / max_val
                    if diff_pct > self.CONFLICT_TOLERANCE_PERCENT:
                        conflicts.append({
                            "key": key,
                            "amounts": amounts,
                            "diff_percent": round(diff_pct * 100, 1)
                        })
        
        if conflicts:
            return ConsistencyCheck(
                check_type=CheckType.SOURCE_CONFLICT,
                source=entity_type,
                endpoint="multi_source",
                status=CheckStatus.WARNING,
                message=f"Found {len(conflicts)} source conflicts",
                detected_at=self._now_iso(),
                details={
                    "conflicts": conflicts[:10],  # Limit to 10
                    "total_conflicts": len(conflicts)
                }
            )
        
        return ConsistencyCheck(
            check_type=CheckType.SOURCE_CONFLICT,
            source=entity_type,
            endpoint="multi_source",
            status=CheckStatus.OK,
            message="No source conflicts detected",
            detected_at=self._now_iso()
        )
    
    # ═══════════════════════════════════════════════════════════════
    # CHECK: Missing Data (Count Drop)
    # ═══════════════════════════════════════════════════════════════
    
    async def check_count_anomaly(
        self, 
        entity_type: str,
        current_count: int,
        previous_count: int
    ) -> ConsistencyCheck:
        """
        Check for abnormal count changes.
        
        Example:
            Yesterday: 200 unlock events
            Today:     40 unlock events  -> ALERT
        """
        if previous_count == 0:
            return ConsistencyCheck(
                check_type=CheckType.COUNT_ANOMALY,
                source=entity_type,
                endpoint="count_check",
                status=CheckStatus.OK,
                message="First count recorded",
                detected_at=self._now_iso(),
                details={"current": current_count, "previous": previous_count}
            )
        
        # Check for drop
        if current_count < previous_count * self.COUNT_DROP_THRESHOLD:
            return ConsistencyCheck(
                check_type=CheckType.MISSING_DATA,
                source=entity_type,
                endpoint="count_check",
                status=CheckStatus.FAIL,
                message=f"Severe count drop: {previous_count} → {current_count}",
                detected_at=self._now_iso(),
                details={
                    "current": current_count,
                    "previous": previous_count,
                    "drop_percent": round((1 - current_count / previous_count) * 100, 1)
                }
            )
        
        # Check for explosion (duplicate issue)
        if current_count > previous_count * self.DUPLICATE_GROWTH_THRESHOLD:
            return ConsistencyCheck(
                check_type=CheckType.DUPLICATE_EXPLOSION,
                source=entity_type,
                endpoint="count_check",
                status=CheckStatus.FAIL,
                message=f"Count explosion: {previous_count} → {current_count}",
                detected_at=self._now_iso(),
                details={
                    "current": current_count,
                    "previous": previous_count,
                    "growth_factor": round(current_count / previous_count, 2)
                }
            )
        
        return ConsistencyCheck(
            check_type=CheckType.COUNT_ANOMALY,
            source=entity_type,
            endpoint="count_check",
            status=CheckStatus.OK,
            message="Count within normal range",
            detected_at=self._now_iso(),
            details={"current": current_count, "previous": previous_count}
        )
    
    # ═══════════════════════════════════════════════════════════════
    # CHECK: Data Freshness
    # ═══════════════════════════════════════════════════════════════
    
    async def check_data_freshness(
        self, 
        entity_type: str,
        last_update_ts: Optional[int]
    ) -> ConsistencyCheck:
        """
        Check if data is stale.
        
        Example:
            Last unlock update: 2h ago  -> OK
            Last unlock update: 48h ago -> ALERT
        """
        if last_update_ts is None:
            return ConsistencyCheck(
                check_type=CheckType.DATA_FRESHNESS,
                source=entity_type,
                endpoint="freshness_check",
                status=CheckStatus.WARNING,
                message="No update timestamp found",
                detected_at=self._now_iso()
            )
        
        now = datetime.now(timezone.utc)
        last_update = datetime.fromtimestamp(last_update_ts / 1000, tz=timezone.utc)
        hours_ago = (now - last_update).total_seconds() / 3600
        
        if hours_ago > self.FRESHNESS_THRESHOLD_HOURS:
            return ConsistencyCheck(
                check_type=CheckType.DATA_FRESHNESS,
                source=entity_type,
                endpoint="freshness_check",
                status=CheckStatus.WARNING,
                message=f"Data stale: last update {hours_ago:.1f}h ago",
                detected_at=self._now_iso(),
                details={
                    "last_update": last_update.isoformat(),
                    "hours_ago": round(hours_ago, 1),
                    "threshold_hours": self.FRESHNESS_THRESHOLD_HOURS
                }
            )
        
        return ConsistencyCheck(
            check_type=CheckType.DATA_FRESHNESS,
            source=entity_type,
            endpoint="freshness_check",
            status=CheckStatus.OK,
            message=f"Data fresh: {hours_ago:.1f}h ago",
            detected_at=self._now_iso(),
            details={
                "last_update": last_update.isoformat(),
                "hours_ago": round(hours_ago, 1)
            }
        )
    
    # ═══════════════════════════════════════════════════════════════
    # Source Reliability Score
    # ═══════════════════════════════════════════════════════════════
    
    def calculate_source_reliability(self, source: str) -> SourceReliability:
        """
        Calculate reliability score for a source.
        
        Score based on:
        - Schema consistency
        - Data freshness
        - Count stability
        """
        source_checks = [c for c in self.checks if c.source == source]
        
        if not source_checks:
            return SourceReliability(
                source=source,
                score=0.0,
                total_checks=0,
                passed_checks=0
            )
        
        passed = sum(1 for c in source_checks if c.status == CheckStatus.OK)
        total = len(source_checks)
        
        # Find last failure
        failures = [c for c in source_checks if c.status == CheckStatus.FAIL]
        last_failure = failures[-1].detected_at if failures else None
        
        return SourceReliability(
            source=source,
            score=round(passed / total, 2) if total > 0 else 0.0,
            total_checks=total,
            passed_checks=passed,
            last_failure=last_failure
        )
    
    # ═══════════════════════════════════════════════════════════════
    # Event Confidence
    # ═══════════════════════════════════════════════════════════════
    
    def calculate_event_confidence(
        self, 
        event_id: str,
        sources: List[str],
        has_conflict: bool = False,
        conflict_details: Optional[Dict] = None
    ) -> EventConfidence:
        """
        Calculate confidence level for an event.
        
        High:   2+ sources, no conflict
        Medium: 1 source, or 2+ with conflict
        Low:    1 source with known issues
        """
        sources_count = len(sources)
        
        if sources_count >= 2 and not has_conflict:
            confidence = "high"
        elif sources_count >= 2 and has_conflict:
            confidence = "medium"
        elif sources_count == 1:
            confidence = "medium"
        else:
            confidence = "low"
        
        return EventConfidence(
            event_id=event_id,
            confidence=confidence,
            sources_count=sources_count,
            sources=sources,
            has_conflict=has_conflict,
            conflict_details=conflict_details
        )
    
    # ═══════════════════════════════════════════════════════════════
    # Main Entry Points
    # ═══════════════════════════════════════════════════════════════
    
    async def run_all_checks(self) -> List[ConsistencyCheck]:
        """Run all consistency checks"""
        self.checks = []
        
        # Get collections
        entity_types = ["unlock", "funding", "investor", "sale"]
        
        for entity_type in entity_types:
            # Get sample records
            try:
                collection = self.db.get_collection(f"normalized_{entity_type}s")
                sample = await collection.find({}, {"_id": 0}).limit(20).to_list(20)
                
                # Schema check
                check = await self.check_schema_drift(entity_type, sample)
                self.checks.append(check)
                
                # Count check (comparing to stored previous)
                current_count = await collection.count_documents({})
                prev_count = await self._get_previous_count(entity_type)
                check = await self.check_count_anomaly(entity_type, current_count, prev_count)
                self.checks.append(check)
                await self._store_count(entity_type, current_count)
                
                # Freshness check
                latest = await collection.find_one(sort=[("_scraped_at", -1)])
                last_ts = latest.get("_scraped_at") if latest else None
                check = await self.check_data_freshness(entity_type, last_ts)
                self.checks.append(check)
                
            except Exception as e:
                self.checks.append(ConsistencyCheck(
                    check_type=CheckType.SCHEMA_DRIFT,
                    source=entity_type,
                    endpoint="error",
                    status=CheckStatus.UNKNOWN,
                    message=f"Check failed: {str(e)}",
                    detected_at=self._now_iso()
                ))
        
        return self.checks
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status"""
        if not self.checks:
            return {
                "status": "unknown",
                "message": "No checks run yet",
                "ts": self._now_iso()
            }
        
        fails = [c for c in self.checks if c.status == CheckStatus.FAIL]
        warnings = [c for c in self.checks if c.status == CheckStatus.WARNING]
        
        if fails:
            status = "critical"
        elif warnings:
            status = "warning"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "total_checks": len(self.checks),
            "passed": sum(1 for c in self.checks if c.status == CheckStatus.OK),
            "warnings": len(warnings),
            "failures": len(fails),
            "checks": [c.to_dict() for c in self.checks],
            "ts": self._now_iso()
        }
    
    def get_source_reliability(self) -> Dict[str, SourceReliability]:
        """Get reliability scores for all sources"""
        sources = set(c.source for c in self.checks)
        return {
            source: self.calculate_source_reliability(source)
            for source in sources
        }
    
    async def _get_previous_count(self, entity_type: str) -> int:
        """Get previous count from stats collection"""
        try:
            stats = self.db.get_collection("intel_consistency_stats")
            doc = await stats.find_one({"entity": entity_type})
            return doc.get("count", 0) if doc else 0
        except:
            return 0
    
    async def _store_count(self, entity_type: str, count: int):
        """Store count for future comparison"""
        try:
            stats = self.db.get_collection("intel_consistency_stats")
            await stats.update_one(
                {"entity": entity_type},
                {"$set": {"count": count, "updated_at": self._now_iso()}},
                upsert=True
            )
        except:
            pass


# ═══════════════════════════════════════════════════════════════
# API Routes Integration
# ═══════════════════════════════════════════════════════════════

def create_consistency_routes(app, db):
    """
    Add consistency check routes to FastAPI app.
    
    Routes:
        GET  /api/intel/consistency/health
        GET  /api/intel/consistency/checks
        POST /api/intel/consistency/run
        GET  /api/intel/consistency/reliability
    """
    from fastapi import APIRouter
    
    router = APIRouter(prefix="/api/intel/consistency", tags=["consistency"])
    engine = DataConsistencyEngine(db)
    
    @router.get("/health")
    async def get_health():
        """Get overall data health status"""
        return engine.get_health_status()
    
    @router.get("/checks")
    async def get_checks():
        """Get all consistency checks"""
        return {
            "ts": engine._now_iso(),
            "checks": [c.to_dict() for c in engine.checks]
        }
    
    @router.post("/run")
    async def run_checks():
        """Run all consistency checks"""
        checks = await engine.run_all_checks()
        return engine.get_health_status()
    
    @router.get("/reliability")
    async def get_reliability():
        """Get source reliability scores"""
        reliability = engine.get_source_reliability()
        return {
            "ts": engine._now_iso(),
            "sources": {k: v.to_dict() for k, v in reliability.items()}
        }
    
    app.include_router(router)
    return router
