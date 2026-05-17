"""
Source Trust Engine

Evaluates reliability of data sources to influence:
- Confidence scores
- Dedup decisions  
- Event validation
- Source priority

Trust Score Formula:
trust = 0.35*success_rate + 0.25*schema_stability + 0.20*freshness + 0.20*cross_source_agreement
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SourceMetrics:
    """Metrics for evaluating source trust"""
    source_id: str
    success_rate: float      # requests_ok / total_requests
    schema_stability: float  # 1 - (schema_changes / total_runs)
    freshness: float         # How quickly source updates data
    cross_source_agreement: float  # matching_events / total_events
    
    def calculate_trust(self) -> float:
        """Calculate overall trust score."""
        return (
            0.35 * self.success_rate +
            0.25 * self.schema_stability +
            0.20 * self.freshness +
            0.20 * self.cross_source_agreement
        )


# Default trust scores for known sources
DEFAULT_TRUST_SCORES = {
    "cryptorank": 0.93,
    "dropstab": 0.89,
    "coingecko": 0.91,
    "rootdata": 0.86,
    "messari": 0.84,
    "defillama": 0.88,
    "icodrops": 0.71,
    "dune": 0.62,
}


class SourceTrustEngine:
    """
    Engine for computing and managing source trust scores.
    
    Trust affects:
    - Event confidence
    - Dedup priority
    - Data validation
    """
    
    def __init__(self, db=None):
        self.db = db
        self._cache: Dict[str, float] = {}
    
    async def get_trust_score(self, source_id: str) -> float:
        """
        Get trust score for a source.
        Returns cached value or computes fresh.
        """
        # Check cache
        if source_id in self._cache:
            return self._cache[source_id]
        
        # Check database
        if self.db is not None:
            source_doc = await self.db.intel_sources.find_one(
                {"source_id": source_id},
                {"_id": 0, "trust_score": 1}
            )
            if source_doc and "trust_score" in source_doc:
                self._cache[source_id] = source_doc["trust_score"]
                return source_doc["trust_score"]
        
        # Return default
        default = DEFAULT_TRUST_SCORES.get(source_id.lower(), 0.5)
        self._cache[source_id] = default
        return default
    
    async def compute_trust(self, source_id: str) -> Optional[float]:
        """
        Compute trust score for a source based on metrics.
        """
        if self.db is None:
            return None
        
        # Get metrics
        metrics_doc = await self.db.intel_source_metrics.find_one(
            {"source_id": source_id},
            {"_id": 0}
        )
        
        if not metrics_doc:
            # Use defaults if no metrics
            return DEFAULT_TRUST_SCORES.get(source_id.lower(), 0.5)
        
        metrics = SourceMetrics(
            source_id=source_id,
            success_rate=metrics_doc.get("success_rate", 0.8),
            schema_stability=metrics_doc.get("schema_stability", 0.9),
            freshness=metrics_doc.get("freshness", 0.7),
            cross_source_agreement=metrics_doc.get("cross_source_agreement", 0.8)
        )
        
        trust_score = metrics.calculate_trust()
        
        # Store computed trust
        await self.db.intel_sources.update_one(
            {"source_id": source_id},
            {
                "$set": {
                    "trust_score": trust_score,
                    "trust_updated_at": datetime.now(timezone.utc).isoformat()
                }
            },
            upsert=True
        )
        
        # Update cache
        self._cache[source_id] = trust_score
        
        logger.info(f"[SourceTrust] {source_id}: trust={trust_score:.3f}")
        
        return trust_score
    
    async def update_metrics(
        self, 
        source_id: str,
        success: bool = True,
        schema_changed: bool = False,
        records_matched: int = 0,
        records_total: int = 0
    ):
        """
        Update source metrics after a sync operation.
        """
        if self.db is None:
            return
        
        now = datetime.now(timezone.utc)
        
        # Get current metrics
        metrics_doc = await self.db.intel_source_metrics.find_one(
            {"source_id": source_id}
        )
        
        if not metrics_doc:
            metrics_doc = {
                "source_id": source_id,
                "total_requests": 0,
                "successful_requests": 0,
                "schema_changes": 0,
                "total_runs": 0,
                "matched_events": 0,
                "total_events": 0,
                "last_success": None
            }
        
        # Update counters
        metrics_doc["total_requests"] = metrics_doc.get("total_requests", 0) + 1
        metrics_doc["total_runs"] = metrics_doc.get("total_runs", 0) + 1
        
        if success:
            metrics_doc["successful_requests"] = metrics_doc.get("successful_requests", 0) + 1
            metrics_doc["last_success"] = now.isoformat()
        
        if schema_changed:
            metrics_doc["schema_changes"] = metrics_doc.get("schema_changes", 0) + 1
        
        if records_total > 0:
            metrics_doc["matched_events"] = metrics_doc.get("matched_events", 0) + records_matched
            metrics_doc["total_events"] = metrics_doc.get("total_events", 0) + records_total
        
        # Calculate derived metrics
        total_req = metrics_doc["total_requests"]
        success_req = metrics_doc["successful_requests"]
        metrics_doc["success_rate"] = success_req / total_req if total_req > 0 else 0.8
        
        total_runs = metrics_doc["total_runs"]
        schema_changes = metrics_doc["schema_changes"]
        metrics_doc["schema_stability"] = 1 - (schema_changes / total_runs) if total_runs > 0 else 0.9
        
        matched = metrics_doc["matched_events"]
        total_ev = metrics_doc["total_events"]
        metrics_doc["cross_source_agreement"] = matched / total_ev if total_ev > 0 else 0.8
        
        # Freshness based on last success
        if metrics_doc.get("last_success"):
            try:
                last = datetime.fromisoformat(metrics_doc["last_success"].replace("Z", "+00:00"))
                hours_ago = (now - last).total_seconds() / 3600
                metrics_doc["freshness"] = max(0, 1 - (hours_ago / 168))  # Decay over 1 week
            except:
                metrics_doc["freshness"] = 0.7
        else:
            metrics_doc["freshness"] = 0.5
        
        metrics_doc["updated_at"] = now.isoformat()
        
        # Store metrics
        await self.db.intel_source_metrics.update_one(
            {"source_id": source_id},
            {"$set": metrics_doc},
            upsert=True
        )
        
        # Recompute trust
        await self.compute_trust(source_id)
    
    async def recompute_all_trust(self) -> Dict[str, Any]:
        """
        Recompute trust scores for all sources.
        """
        if self.db is None:
            return {"error": "No database connection"}
        
        # Get all sources
        cursor = self.db.intel_sources.find({}, {"source_id": 1})
        sources = [doc["source_id"] async for doc in cursor]
        
        results = []
        for source_id in sources:
            trust = await self.compute_trust(source_id)
            results.append({
                "source": source_id,
                "trust": trust
            })
        
        # Sort by trust descending
        results.sort(key=lambda x: x["trust"] or 0, reverse=True)
        
        return {
            "sources_processed": len(results),
            "trust_scores": results
        }
    
    async def get_all_trust_scores(self) -> List[Dict]:
        """Get all source trust scores."""
        if self.db is None:
            # Return defaults
            return [
                {"source_id": k, "trust_score": v}
                for k, v in sorted(DEFAULT_TRUST_SCORES.items(), key=lambda x: -x[1])
            ]
        
        cursor = self.db.intel_sources.find(
            {},
            {"_id": 0, "source_id": 1, "trust_score": 1, "trust_updated_at": 1}
        ).sort("trust_score", -1)
        
        return await cursor.to_list(100)
    
    async def get_source_details(self, source_id: str) -> Dict[str, Any]:
        """Get detailed information about a source."""
        result = {
            "source_id": source_id,
            "trust_score": await self.get_trust_score(source_id),
            "default_trust": DEFAULT_TRUST_SCORES.get(source_id.lower()),
            "metrics": None,
            "source_info": None
        }
        
        if self.db is not None:
            metrics = await self.db.intel_source_metrics.find_one(
                {"source_id": source_id},
                {"_id": 0}
            )
            result["metrics"] = metrics
            
            source_info = await self.db.intel_sources.find_one(
                {"source_id": source_id},
                {"_id": 0}
            )
            result["source_info"] = source_info
        
        return result
    
    async def apply_trust_to_confidence(
        self, 
        base_confidence: float, 
        source_id: str
    ) -> float:
        """
        Apply source trust to event confidence.
        
        confidence = base_confidence * source_trust
        """
        trust = await self.get_trust_score(source_id)
        return base_confidence * trust
    
    async def resolve_conflict(
        self, 
        source_a: str, 
        source_b: str
    ) -> str:
        """
        Resolve conflict between two sources.
        Returns the more trusted source.
        """
        trust_a = await self.get_trust_score(source_a)
        trust_b = await self.get_trust_score(source_b)
        
        return source_a if trust_a >= trust_b else source_b
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get trust engine statistics."""
        if self.db is None:
            return {
                "default_sources": len(DEFAULT_TRUST_SCORES),
                "cached_scores": len(self._cache)
            }
        
        total_sources = await self.db.intel_sources.count_documents({})
        total_metrics = await self.db.intel_source_metrics.count_documents({})
        
        # Average trust
        pipeline = [
            {"$group": {"_id": None, "avg_trust": {"$avg": "$trust_score"}}}
        ]
        cursor = self.db.intel_sources.aggregate(pipeline)
        avg_result = await cursor.to_list(1)
        avg_trust = avg_result[0]["avg_trust"] if avg_result else None
        
        # Trust distribution
        pipeline = [
            {
                "$bucket": {
                    "groupBy": "$trust_score",
                    "boundaries": [0, 0.5, 0.7, 0.85, 1.0],
                    "default": "unknown",
                    "output": {"count": {"$sum": 1}}
                }
            }
        ]
        cursor = self.db.intel_sources.aggregate(pipeline)
        distribution = {str(doc["_id"]): doc["count"] async for doc in cursor}
        
        return {
            "total_sources": total_sources,
            "total_metrics": total_metrics,
            "average_trust": round(avg_trust, 3) if avg_trust else None,
            "trust_distribution": distribution,
            "cached_scores": len(self._cache)
        }


# Singleton instance
source_trust_engine: Optional[SourceTrustEngine] = None


def init_source_trust_engine(db):
    """Initialize source trust engine."""
    global source_trust_engine
    source_trust_engine = SourceTrustEngine(db)
    return source_trust_engine


def get_source_trust_engine():
    """Get source trust engine instance."""
    return source_trust_engine
