"""
Discovery Scoring Engine
========================

Scores and ranks discovered endpoints for optimal selection.
Helps scraper engine choose the best endpoint for data fetching.

Scoring Factors:
- Reliability (success rate)
- Performance (latency)
- Data quality (completeness, freshness)
- Coverage (data types, fields)

Pipeline:
    Endpoint Registry
    ↓
    Calculate scores
    ↓
    Rank endpoints
    ↓
    Select best for scraping
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


@dataclass
class EndpointScore:
    """Endpoint score breakdown"""
    endpoint_id: str
    domain: str
    
    # Component scores (0-100)
    reliability_score: float = 0
    performance_score: float = 0
    data_quality_score: float = 0
    coverage_score: float = 0
    freshness_score: float = 0
    
    # Final weighted score
    total_score: float = 0
    
    # Metadata
    calculated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "endpoint_id": self.endpoint_id,
            "domain": self.domain,
            "scores": {
                "reliability": round(self.reliability_score, 1),
                "performance": round(self.performance_score, 1),
                "data_quality": round(self.data_quality_score, 1),
                "coverage": round(self.coverage_score, 1),
                "freshness": round(self.freshness_score, 1)
            },
            "total_score": round(self.total_score, 1),
            "calculated_at": self.calculated_at
        }


class DiscoveryScoringEngine:
    """
    Scores and ranks discovered endpoints.
    
    Features:
    - Multi-factor scoring
    - Weighted aggregation
    - Automatic ranking
    - Best endpoint selection
    """
    
    # Score weights (must sum to 1.0)
    WEIGHTS = {
        "reliability": 0.30,
        "performance": 0.25,
        "data_quality": 0.20,
        "coverage": 0.15,
        "freshness": 0.10
    }
    
    # Performance thresholds (ms)
    LATENCY_EXCELLENT = 200
    LATENCY_GOOD = 500
    LATENCY_ACCEPTABLE = 1000
    LATENCY_POOR = 3000
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.endpoints = db.endpoint_registry
        self.scores = db.endpoint_scores
        self.scrape_logs = db.scrape_logs
    
    async def calculate_score(self, endpoint_id: str) -> Optional[EndpointScore]:
        """Calculate score for single endpoint"""
        endpoint = await self.endpoints.find_one({"id": endpoint_id}, {"_id": 0})
        if not endpoint:
            return None
        
        score = EndpointScore(
            endpoint_id=endpoint_id,
            domain=endpoint.get("domain", "")
        )
        
        # Calculate component scores
        score.reliability_score = await self._calc_reliability(endpoint_id, endpoint)
        score.performance_score = self._calc_performance(endpoint)
        score.data_quality_score = self._calc_data_quality(endpoint)
        score.coverage_score = self._calc_coverage(endpoint)
        score.freshness_score = self._calc_freshness(endpoint)
        
        # Calculate weighted total
        score.total_score = (
            score.reliability_score * self.WEIGHTS["reliability"] +
            score.performance_score * self.WEIGHTS["performance"] +
            score.data_quality_score * self.WEIGHTS["data_quality"] +
            score.coverage_score * self.WEIGHTS["coverage"] +
            score.freshness_score * self.WEIGHTS["freshness"]
        )
        
        # Save score
        await self._save_score(score)
        
        # Update endpoint with score
        await self.endpoints.update_one(
            {"id": endpoint_id},
            {"$set": {
                "score": score.total_score,
                "score_breakdown": score.to_dict()["scores"],
                "scored_at": score.calculated_at
            }}
        )
        
        return score
    
    async def calculate_domain_scores(self, domain: str) -> List[EndpointScore]:
        """Calculate scores for all endpoints in domain"""
        scores = []
        
        cursor = self.endpoints.find({"domain": domain}, {"_id": 0, "id": 1})
        async for ep in cursor:
            score = await self.calculate_score(ep["id"])
            if score:
                scores.append(score)
        
        # Sort by total score
        scores.sort(key=lambda s: s.total_score, reverse=True)
        
        return scores
    
    async def calculate_all_scores(self, limit: int = 100) -> List[EndpointScore]:
        """Calculate scores for all active endpoints"""
        scores = []
        
        cursor = self.endpoints.find(
            {"status": "active"},
            {"_id": 0, "id": 1}
        ).limit(limit)
        
        async for ep in cursor:
            score = await self.calculate_score(ep["id"])
            if score:
                scores.append(score)
        
        scores.sort(key=lambda s: s.total_score, reverse=True)
        
        return scores
    
    async def get_best_endpoint(
        self,
        domain: str = None,
        capability: str = None,
        min_score: float = 50
    ) -> Optional[Dict]:
        """
        Get best endpoint for given criteria.
        
        Args:
            domain: Filter by domain
            capability: Filter by capability (e.g., "market_data")
            min_score: Minimum score threshold
            
        Returns:
            Best endpoint document or None
        """
        query = {"status": "active"}
        
        if domain:
            query["domain"] = domain
        if capability:
            query["capabilities"] = capability
        if min_score > 0:
            query["score"] = {"$gte": min_score}
        
        # Get endpoint with highest score
        endpoint = await self.endpoints.find_one(
            query,
            {"_id": 0},
            sort=[("score", -1)]
        )
        
        return endpoint
    
    async def get_ranked_endpoints(
        self,
        domain: str = None,
        capability: str = None,
        limit: int = 10
    ) -> List[Dict]:
        """Get endpoints ranked by score"""
        query = {"status": "active", "score": {"$exists": True}}
        
        if domain:
            query["domain"] = domain
        if capability:
            query["capabilities"] = capability
        
        endpoints = []
        cursor = self.endpoints.find(
            query,
            {"_id": 0}
        ).sort("score", -1).limit(limit)
        
        async for ep in cursor:
            endpoints.append(ep)
        
        return endpoints
    
    async def _calc_reliability(self, endpoint_id: str, endpoint: Dict) -> float:
        """Calculate reliability score based on success rate"""
        # Check recent scrape history
        recent_scrapes = await self.scrape_logs.count_documents({
            "endpoint_id": endpoint_id,
            "timestamp": {"$gte": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()}
        })
        
        if recent_scrapes == 0:
            # Use endpoint status
            if endpoint.get("status") == "active" and endpoint.get("replay_success"):
                return 70  # Assumed reliable
            elif endpoint.get("status") == "active":
                return 50
            return 30
        
        successful = await self.scrape_logs.count_documents({
            "endpoint_id": endpoint_id,
            "success": True,
            "timestamp": {"$gte": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()}
        })
        
        success_rate = successful / recent_scrapes
        
        # Convert to score (0-100)
        if success_rate >= 0.99:
            return 100
        elif success_rate >= 0.95:
            return 90
        elif success_rate >= 0.90:
            return 80
        elif success_rate >= 0.80:
            return 70
        elif success_rate >= 0.70:
            return 60
        elif success_rate >= 0.50:
            return 40
        return 20
    
    def _calc_performance(self, endpoint: Dict) -> float:
        """Calculate performance score based on latency"""
        latency = endpoint.get("latency_ms", 0)
        
        if latency <= 0:
            return 50  # Unknown
        
        if latency <= self.LATENCY_EXCELLENT:
            return 100
        elif latency <= self.LATENCY_GOOD:
            return 85
        elif latency <= self.LATENCY_ACCEPTABLE:
            return 70
        elif latency <= self.LATENCY_POOR:
            return 50
        return 30
    
    def _calc_data_quality(self, endpoint: Dict) -> float:
        """Calculate data quality score"""
        score = 50  # Base score
        
        # Check response schema
        schema = endpoint.get("response_schema", {})
        if schema:
            score += 20
            
            # More fields = more data
            fields = schema.get("fields", {})
            if len(fields) > 10:
                score += 10
            elif len(fields) > 5:
                score += 5
            
            # Has array with items
            if schema.get("array_length", 0) > 0:
                score += 10
                if schema.get("array_length", 0) > 100:
                    score += 10
        
        # Check for sample data
        if endpoint.get("response_sample"):
            score += 10
        
        return min(score, 100)
    
    def _calc_coverage(self, endpoint: Dict) -> float:
        """Calculate coverage score based on capabilities"""
        capabilities = endpoint.get("capabilities", [])
        
        if not capabilities:
            return 30
        
        # Base score
        score = 40
        
        # More capabilities = better coverage
        score += len(capabilities) * 15
        
        # Valuable capabilities
        valuable = ["market_data", "defi_data", "funding", "dex_data"]
        for cap in capabilities:
            if cap in valuable:
                score += 10
        
        return min(score, 100)
    
    def _calc_freshness(self, endpoint: Dict) -> float:
        """Calculate freshness score based on last verification"""
        last_verified = endpoint.get("last_verified")
        discovered_at = endpoint.get("discovered_at")
        
        reference_time = last_verified or discovered_at
        if not reference_time:
            return 30
        
        try:
            ref_dt = datetime.fromisoformat(reference_time.replace('Z', '+00:00'))
            age = datetime.now(timezone.utc) - ref_dt
            
            if age < timedelta(hours=1):
                return 100
            elif age < timedelta(hours=6):
                return 90
            elif age < timedelta(days=1):
                return 75
            elif age < timedelta(days=3):
                return 60
            elif age < timedelta(days=7):
                return 45
            return 30
            
        except:
            return 30
    
    async def _save_score(self, score: EndpointScore):
        """Save score to database"""
        await self.scores.update_one(
            {"endpoint_id": score.endpoint_id},
            {"$set": score.to_dict()},
            upsert=True
        )
    
    async def get_scoring_stats(self) -> Dict:
        """Get scoring statistics"""
        total = await self.endpoints.count_documents({"score": {"$exists": True}})
        
        # Score distribution
        distribution_pipeline = [
            {"$match": {"score": {"$exists": True}}},
            {"$bucket": {
                "groupBy": "$score",
                "boundaries": [0, 30, 50, 70, 85, 101],
                "default": "other",
                "output": {"count": {"$sum": 1}}
            }}
        ]
        
        distribution = {}
        labels = {0: "Poor (0-30)", 30: "Fair (30-50)", 50: "Good (50-70)", 
                  70: "Excellent (70-85)", 85: "Outstanding (85-100)"}
        
        async for doc in self.endpoints.aggregate(distribution_pipeline):
            bucket = doc["_id"]
            if bucket in labels:
                distribution[labels[bucket]] = doc["count"]
        
        # Top endpoints
        top = []
        cursor = self.endpoints.find(
            {"score": {"$exists": True}},
            {"_id": 0, "id": 1, "domain": 1, "path": 1, "score": 1, "capabilities": 1}
        ).sort("score", -1).limit(10)
        
        async for ep in cursor:
            top.append(ep)
        
        # Average by domain
        domain_pipeline = [
            {"$match": {"score": {"$exists": True}}},
            {"$group": {"_id": "$domain", "avg_score": {"$avg": "$score"}, "count": {"$sum": 1}}},
            {"$sort": {"avg_score": -1}},
            {"$limit": 10}
        ]
        
        by_domain = []
        async for doc in self.endpoints.aggregate(domain_pipeline):
            by_domain.append({
                "domain": doc["_id"],
                "avg_score": round(doc["avg_score"], 1),
                "endpoints": doc["count"]
            })
        
        return {
            "total_scored": total,
            "distribution": distribution,
            "top_endpoints": top,
            "by_domain": by_domain
        }
