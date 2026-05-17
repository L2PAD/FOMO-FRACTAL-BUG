"""
Source Reliability Scoring System
=================================

Dynamic scoring of data sources based on:
- reliability_score: How often data is correct
- latency_score: Response time
- freshness_score: How up-to-date is the data
- error_rate: Failure rate
- final_score: Weighted combination

Architecture:
    source_metrics:
        source_id: "cryptorank"
        reliability_score: 0.92
        latency_score: 0.81
        freshness_score: 0.87
        error_rate: 0.03
        final_score: 0.88
        
Scheduler should use this to:
- Choose best provider for each data type
- Skip unreliable sources
- Prioritize fast, fresh sources

Usage:
    # Record data fetch
    await reliability.record_fetch(
        source_id="cryptorank",
        success=True,
        latency_ms=250,
        data_freshness_hours=0.5
    )
    
    # Get best source for funding data
    best = await reliability.get_best_source(
        data_type="funding",
        candidates=["cryptorank", "rootdata", "messari"]
    )
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# Weight configuration for final score
SCORE_WEIGHTS = {
    "reliability": 0.35,
    "latency": 0.20,
    "freshness": 0.25,
    "error_rate": 0.20  # Inverse - lower is better
}

# Source capabilities - what each source provides best
SOURCE_CAPABILITIES = {
    "cryptorank": ["funding", "ico", "unlocks", "activities", "persons"],
    "rootdata": ["funding", "funds", "persons", "portfolio"],
    "defillama": ["tvl", "defi", "chains", "protocols"],
    "coingecko": ["prices", "market_cap", "volume", "token_info"],
    "coinmarketcap": ["prices", "market_cap", "rankings"],
    "dropstab": ["tokenomics", "vesting", "allocations"],
    "tokenunlocks": ["unlocks", "vesting_schedule"],
    "messari": ["research", "profiles", "metrics"],
    "github": ["developer_activity", "commits", "contributors"],
}

# Default scores for new sources
DEFAULT_SCORES = {
    "reliability_score": 0.7,
    "latency_score": 0.7,
    "freshness_score": 0.7,
    "error_rate": 0.1,
    "final_score": 0.65
}


class SourceMetrics(BaseModel):
    """Metrics for a data source"""
    source_id: str
    reliability_score: float = Field(0.7, ge=0, le=1)
    latency_score: float = Field(0.7, ge=0, le=1)
    freshness_score: float = Field(0.7, ge=0, le=1)
    error_rate: float = Field(0.1, ge=0, le=1)
    final_score: float = Field(0.65, ge=0, le=1)
    
    # Stats
    total_fetches: int = 0
    successful_fetches: int = 0
    avg_latency_ms: float = 0
    avg_data_age_hours: float = 0
    
    # Status
    status: str = "unknown"  # healthy, degraded, down
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SourceReliabilitySystem:
    """
    System for tracking and scoring data source reliability.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.source_metrics = db.source_metrics
        self.source_history = db.source_reliability_history
        self.fetch_log = db.source_fetch_log
    
    async def ensure_indexes(self):
        """Create indexes"""
        await self.source_metrics.create_index("source_id", unique=True)
        await self.source_metrics.create_index("final_score")
        await self.source_metrics.create_index("status")
        
        await self.source_history.create_index([("source_id", 1), ("timestamp", -1)])
        await self.fetch_log.create_index([("source_id", 1), ("timestamp", -1)])
        await self.fetch_log.create_index("timestamp", expireAfterSeconds=86400 * 7)  # 7 day TTL
        
        logger.info("[SourceReliability] Indexes created")
    
    async def record_fetch(
        self,
        source_id: str,
        success: bool,
        latency_ms: float,
        data_freshness_hours: float = None,
        endpoint: str = None,
        error: str = None
    ):
        """
        Record a data fetch attempt.
        Updates rolling metrics.
        """
        now = datetime.now(timezone.utc)
        
        # Log the fetch
        log_entry = {
            "source_id": source_id,
            "success": success,
            "latency_ms": latency_ms,
            "data_freshness_hours": data_freshness_hours,
            "endpoint": endpoint,
            "error": error,
            "timestamp": now
        }
        await self.fetch_log.insert_one(log_entry)
        
        # Update metrics
        await self._update_metrics(source_id)
    
    async def _update_metrics(self, source_id: str):
        """Recalculate metrics for a source"""
        now = datetime.now(timezone.utc)
        
        # Get recent fetches (last 24 hours)
        cutoff_24h = now - timedelta(hours=24)
        cutoff_1h = now - timedelta(hours=1)
        
        fetches_24h = await self.fetch_log.find({
            "source_id": source_id,
            "timestamp": {"$gte": cutoff_24h}
        }).to_list(5000)
        
        # Handle timezone-naive timestamps
        def ensure_tz_aware(dt):
            if dt is None:
                return None
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        
        fetches_1h = [f for f in fetches_24h if ensure_tz_aware(f.get("timestamp")) and ensure_tz_aware(f["timestamp"]) >= cutoff_1h]
        
        if not fetches_24h:
            return
        
        # Calculate metrics
        total = len(fetches_24h)
        successful = sum(1 for f in fetches_24h if f.get("success"))
        failed = total - successful
        
        # Reliability score (success rate)
        reliability_score = successful / total if total > 0 else 0.5
        
        # Latency score
        latencies = [f["latency_ms"] for f in fetches_24h if f.get("success") and f.get("latency_ms")]
        avg_latency = sum(latencies) / len(latencies) if latencies else 1000
        # Score: 100ms = 1.0, 5000ms = 0.0
        latency_score = max(0, min(1, 1 - (avg_latency - 100) / 4900))
        
        # Freshness score
        freshness_values = [f["data_freshness_hours"] for f in fetches_24h if f.get("data_freshness_hours") is not None]
        avg_freshness = sum(freshness_values) / len(freshness_values) if freshness_values else 12
        # Score: 0h = 1.0, 24h = 0.0
        freshness_score = max(0, min(1, 1 - avg_freshness / 24))
        
        # Error rate
        error_rate = failed / total if total > 0 else 0.5
        
        # Final score (weighted)
        final_score = (
            reliability_score * SCORE_WEIGHTS["reliability"] +
            latency_score * SCORE_WEIGHTS["latency"] +
            freshness_score * SCORE_WEIGHTS["freshness"] +
            (1 - error_rate) * SCORE_WEIGHTS["error_rate"]
        )
        
        # Determine status
        if final_score >= 0.8 and error_rate < 0.1:
            status = "healthy"
        elif final_score >= 0.5 and error_rate < 0.3:
            status = "degraded"
        else:
            status = "down"
        
        # Recent performance (last hour)
        recent_success = sum(1 for f in fetches_1h if f.get("success"))
        recent_total = len(fetches_1h) or 1
        
        # Find last success/failure
        last_success = None
        last_failure = None
        for f in sorted(fetches_24h, key=lambda x: x["timestamp"], reverse=True):
            if f.get("success") and not last_success:
                last_success = f["timestamp"]
            if not f.get("success") and not last_failure:
                last_failure = f["timestamp"]
            if last_success and last_failure:
                break
        
        # Update metrics document
        metrics = {
            "source_id": source_id,
            "reliability_score": round(reliability_score, 3),
            "latency_score": round(latency_score, 3),
            "freshness_score": round(freshness_score, 3),
            "error_rate": round(error_rate, 3),
            "final_score": round(final_score, 3),
            "total_fetches": total,
            "successful_fetches": successful,
            "avg_latency_ms": round(avg_latency, 1),
            "avg_data_age_hours": round(avg_freshness, 1),
            "status": status,
            "last_success": last_success,
            "last_failure": last_failure,
            "last_updated": now,
            "recent_success_rate": round(recent_success / recent_total, 2)
        }
        
        await self.source_metrics.update_one(
            {"source_id": source_id},
            {"$set": metrics},
            upsert=True
        )
        
        # Store history point
        history = {
            "source_id": source_id,
            "final_score": round(final_score, 3),
            "reliability_score": round(reliability_score, 3),
            "latency_score": round(latency_score, 3),
            "error_rate": round(error_rate, 3),
            "timestamp": now
        }
        await self.source_history.insert_one(history)
    
    async def get_source_metrics(self, source_id: str) -> Optional[Dict[str, Any]]:
        """Get current metrics for a source"""
        doc = await self.source_metrics.find_one(
            {"source_id": source_id},
            {"_id": 0}
        )
        
        if not doc:
            # Return default metrics
            return {
                "source_id": source_id,
                **DEFAULT_SCORES,
                "status": "unknown",
                "total_fetches": 0
            }
        
        return doc
    
    async def get_all_metrics(self) -> List[Dict[str, Any]]:
        """Get metrics for all sources"""
        cursor = self.source_metrics.find({}, {"_id": 0}).sort("final_score", -1)
        return await cursor.to_list(100)
    
    async def get_best_source(
        self,
        data_type: str,
        candidates: List[str] = None,
        min_score: float = 0.3
    ) -> Optional[str]:
        """
        Get best source for a data type.
        
        Args:
            data_type: Type of data needed (funding, prices, etc.)
            candidates: Optional list of sources to consider
            min_score: Minimum acceptable score
            
        Returns:
            Best source ID or None
        """
        # Get candidates that support this data type
        if not candidates:
            candidates = [
                source_id 
                for source_id, capabilities in SOURCE_CAPABILITIES.items()
                if data_type in capabilities
            ]
        
        if not candidates:
            logger.warning(f"[SourceReliability] No candidates for data_type={data_type}")
            return None
        
        # Get scores for candidates
        scored = []
        
        for source_id in candidates:
            metrics = await self.get_source_metrics(source_id)
            score = metrics.get("final_score", DEFAULT_SCORES["final_score"])
            
            if score >= min_score:
                scored.append((source_id, score))
        
        if not scored:
            # Fallback to first candidate even if below threshold
            logger.warning(f"[SourceReliability] No sources above min_score={min_score}, using first candidate")
            return candidates[0]
        
        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        
        best = scored[0][0]
        logger.debug(f"[SourceReliability] Best source for {data_type}: {best} (score={scored[0][1]})")
        
        return best
    
    async def get_source_ranking(
        self,
        data_type: str = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get ranked list of sources.
        Optionally filtered by data type.
        """
        all_metrics = await self.get_all_metrics()
        
        if data_type:
            # Filter by capability
            capable_sources = [
                source_id 
                for source_id, caps in SOURCE_CAPABILITIES.items()
                if data_type in caps
            ]
            all_metrics = [m for m in all_metrics if m["source_id"] in capable_sources]
        
        return all_metrics[:limit]
    
    async def get_source_history(
        self,
        source_id: str,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get score history for a source"""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        cursor = self.source_history.find(
            {
                "source_id": source_id,
                "timestamp": {"$gte": cutoff}
            },
            {"_id": 0}
        ).sort("timestamp", 1)
        
        return await cursor.to_list(500)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get overall system statistics"""
        total_sources = await self.source_metrics.count_documents({})
        healthy = await self.source_metrics.count_documents({"status": "healthy"})
        degraded = await self.source_metrics.count_documents({"status": "degraded"})
        down = await self.source_metrics.count_documents({"status": "down"})
        
        # Average scores
        pipeline = [
            {"$group": {
                "_id": None,
                "avg_final": {"$avg": "$final_score"},
                "avg_reliability": {"$avg": "$reliability_score"},
                "avg_latency": {"$avg": "$avg_latency_ms"},
                "total_fetches": {"$sum": "$total_fetches"}
            }}
        ]
        
        agg_result = await self.source_metrics.aggregate(pipeline).to_list(1)
        averages = agg_result[0] if agg_result else {}
        
        # Handle None values safely
        avg_final = averages.get("avg_final")
        avg_reliability = averages.get("avg_reliability")
        avg_latency = averages.get("avg_latency")
        total_fetches = averages.get("total_fetches")
        
        return {
            "total_sources": total_sources,
            "healthy": healthy,
            "degraded": degraded,
            "down": down,
            "avg_final_score": round(avg_final, 3) if avg_final is not None else 0,
            "avg_reliability": round(avg_reliability, 3) if avg_reliability is not None else 0,
            "avg_latency_ms": round(avg_latency, 1) if avg_latency is not None else 0,
            "total_fetches_tracked": total_fetches or 0
        }
    
    async def seed_initial_sources(self):
        """Seed metrics for known sources with default values"""
        now = datetime.now(timezone.utc)
        seeded = 0
        
        for source_id in SOURCE_CAPABILITIES.keys():
            existing = await self.source_metrics.find_one({"source_id": source_id})
            if not existing:
                metrics = {
                    "source_id": source_id,
                    **DEFAULT_SCORES,
                    "status": "unknown",
                    "total_fetches": 0,
                    "successful_fetches": 0,
                    "capabilities": SOURCE_CAPABILITIES.get(source_id, []),
                    "last_updated": now
                }
                await self.source_metrics.insert_one(metrics)
                seeded += 1
        
        logger.info(f"[SourceReliability] Seeded {seeded} sources with default metrics")
        return seeded


# Singleton
_reliability_system: Optional[SourceReliabilitySystem] = None


def get_source_reliability(db: AsyncIOMotorDatabase = None) -> SourceReliabilitySystem:
    """Get or create reliability system instance"""
    global _reliability_system
    if db is not None:
        _reliability_system = SourceReliabilitySystem(db)
    return _reliability_system
