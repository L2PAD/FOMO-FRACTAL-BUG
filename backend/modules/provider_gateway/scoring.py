"""
Provider Scoring System
=======================

Система скоринга провайдеров данных.
Отслеживает latency, error_rate, success_rate для каждого провайдера.

Пример использования:
    coingecko score = 0.98
    defillama score = 0.95
    cryptorank score = 0.81

Gateway выбирает лучший источник на основе score.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProviderScore:
    """Provider score data"""
    provider_id: str
    score: float  # 0-1
    latency_ms: float
    error_rate: float
    success_rate: float
    calls_last_hour: int
    last_check: datetime
    status: str  # healthy, degraded, down


class ProviderScoringSystem:
    """
    Provider Scoring System - отслеживает качество провайдеров.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.metrics = db.provider_metrics
        self.scores = db.provider_scores
        self.history = db.provider_history
    
    async def init_indexes(self):
        """Create indexes"""
        try:
            await self.metrics.create_index("provider_id")
            await self.metrics.create_index([("timestamp", -1)])
            await self.scores.create_index("provider_id", unique=True)
            await self.history.create_index([("provider_id", 1), ("timestamp", -1)])
        except Exception as e:
            logger.debug(f"Index creation skipped: {e}")
    
    async def record_request(
        self,
        provider_id: str,
        success: bool,
        latency_ms: float,
        error: Optional[str] = None,
        endpoint: Optional[str] = None
    ):
        """Record a request to provider"""
        now = datetime.now(timezone.utc)
        
        metric = {
            "provider_id": provider_id,
            "success": success,
            "latency_ms": latency_ms,
            "error": error,
            "endpoint": endpoint,
            "timestamp": now.isoformat()
        }
        
        await self.metrics.insert_one(metric)
        
        # Update rolling score
        await self._update_score(provider_id)
    
    async def _update_score(self, provider_id: str):
        """Update provider score based on recent metrics"""
        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)
        one_day_ago = now - timedelta(days=1)
        
        # Get metrics from last hour for recent stats
        hour_cursor = self.metrics.find({
            "provider_id": provider_id,
            "timestamp": {"$gte": one_hour_ago.isoformat()}
        })
        
        hour_metrics = await hour_cursor.to_list(1000)
        
        # Get metrics from last day for overall stats
        day_cursor = self.metrics.find({
            "provider_id": provider_id,
            "timestamp": {"$gte": one_day_ago.isoformat()}
        })
        
        day_metrics = await day_cursor.to_list(5000)
        
        if not day_metrics:
            return
        
        # Calculate stats
        total_calls = len(day_metrics)
        successful_calls = sum(1 for m in day_metrics if m.get("success"))
        failed_calls = total_calls - successful_calls
        
        latencies = [m.get("latency_ms", 0) for m in day_metrics if m.get("success") and m.get("latency_ms")]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        
        success_rate = successful_calls / total_calls if total_calls > 0 else 0
        error_rate = failed_calls / total_calls if total_calls > 0 else 0
        
        # Calculate score (weighted)
        # Success rate: 50%, Latency: 30%, Recent performance: 20%
        latency_score = max(0, 1 - (avg_latency / 5000))  # 5s = 0 score
        
        # Recent performance (last hour)
        recent_success = sum(1 for m in hour_metrics if m.get("success"))
        recent_total = len(hour_metrics) if hour_metrics else 1
        recent_rate = recent_success / recent_total
        
        score = (
            success_rate * 0.50 +
            latency_score * 0.30 +
            recent_rate * 0.20
        )
        
        # Determine status
        if score >= 0.9 and error_rate < 0.05:
            status = "healthy"
        elif score >= 0.7 and error_rate < 0.20:
            status = "degraded"
        else:
            status = "down"
        
        # Update score
        score_doc = {
            "provider_id": provider_id,
            "score": round(score, 3),
            "latency_ms": round(avg_latency, 1),
            "error_rate": round(error_rate, 3),
            "success_rate": round(success_rate, 3),
            "calls_last_hour": len(hour_metrics),
            "calls_last_day": total_calls,
            "status": status,
            "last_updated": now.isoformat()
        }
        
        await self.scores.update_one(
            {"provider_id": provider_id},
            {"$set": score_doc},
            upsert=True
        )
        
        # Store history point
        history_point = {
            "provider_id": provider_id,
            "score": round(score, 3),
            "latency_ms": round(avg_latency, 1),
            "error_rate": round(error_rate, 3),
            "timestamp": now.isoformat()
        }
        await self.history.insert_one(history_point)
    
    async def get_score(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """Get current score for provider"""
        doc = await self.scores.find_one(
            {"provider_id": provider_id},
            {"_id": 0}
        )
        return doc
    
    async def get_all_scores(self) -> List[Dict[str, Any]]:
        """Get scores for all providers"""
        cursor = self.scores.find({}, {"_id": 0}).sort("score", -1)
        return await cursor.to_list(100)
    
    async def get_best_provider(
        self,
        providers: List[str],
        min_score: float = 0.5
    ) -> Optional[str]:
        """Get best provider from list based on score"""
        scores = []
        
        for provider_id in providers:
            score_doc = await self.get_score(provider_id)
            if score_doc and score_doc.get("score", 0) >= min_score:
                scores.append((provider_id, score_doc["score"]))
        
        if not scores:
            return providers[0] if providers else None
        
        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[0][0]
    
    async def get_provider_history(
        self,
        provider_id: str,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get score history for provider"""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        cursor = self.history.find(
            {
                "provider_id": provider_id,
                "timestamp": {"$gte": since.isoformat()}
            },
            {"_id": 0}
        ).sort("timestamp", 1)
        
        return await cursor.to_list(500)
    
    async def get_metrics(
        self,
        provider_id: Optional[str] = None,
        include_latency: bool = True,
        include_errors: bool = True
    ) -> Dict[str, Any]:
        """Get detailed metrics endpoint"""
        query = {}
        if provider_id:
            query["provider_id"] = provider_id
        
        scores = await self.get_all_scores()
        
        result = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "providers": []
        }
        
        for score in scores:
            provider_data = {
                "provider_id": score["provider_id"],
                "score": score.get("score", 0),
                "status": score.get("status", "unknown"),
                "calls_last_hour": score.get("calls_last_hour", 0),
                "success_rate": score.get("success_rate", 0)
            }
            
            if include_latency:
                provider_data["latency_ms"] = score.get("latency_ms", 0)
            
            if include_errors:
                provider_data["error_rate"] = score.get("error_rate", 0)
            
            result["providers"].append(provider_data)
        
        return result
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get scoring system stats"""
        total_providers = await self.scores.count_documents({})
        healthy = await self.scores.count_documents({"status": "healthy"})
        degraded = await self.scores.count_documents({"status": "degraded"})
        down = await self.scores.count_documents({"status": "down"})
        
        # Get overall averages
        pipeline = [
            {"$group": {
                "_id": None,
                "avg_score": {"$avg": "$score"},
                "avg_latency": {"$avg": "$latency_ms"},
                "avg_error_rate": {"$avg": "$error_rate"}
            }}
        ]
        
        agg_result = await self.scores.aggregate(pipeline).to_list(1)
        averages = agg_result[0] if agg_result else {}
        
        return {
            "total_providers": total_providers,
            "healthy": healthy,
            "degraded": degraded,
            "down": down,
            "avg_score": round(averages.get("avg_score", 0), 3),
            "avg_latency_ms": round(averages.get("avg_latency", 0), 1),
            "avg_error_rate": round(averages.get("avg_error_rate", 0), 3)
        }


# Singleton
_scoring_system: Optional[ProviderScoringSystem] = None


def get_scoring_system(db: AsyncIOMotorDatabase = None) -> ProviderScoringSystem:
    """Get or create scoring system instance"""
    global _scoring_system
    if db:
        _scoring_system = ProviderScoringSystem(db)
    return _scoring_system
