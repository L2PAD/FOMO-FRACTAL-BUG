"""
Confidence Scoring System

Когда данные приходят из нескольких источников (CryptoRank + Dropstab + ...) -
система автоматически определяет какому полю верить.

Факторы оценки:
- Source reliability (вес источника)
- Freshness (давность данных)
- Cross-source agreement (совпадение с другими источниками)
- Endpoint health (стабильность endpoint)
- Auth level (публичное/браузер/с авторизацией)
"""

import math
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


# Default source reliability weights
DEFAULT_SOURCE_WEIGHT = {
    "cryptorank": 0.90,
    "dropstab": 0.88,
    "coingecko": 0.85,
    "defillama": 0.87,
    "messari": 0.92,
    "rootdata": 0.85,
    "icodrops": 0.80,
    "manual": 0.95,
    "unknown": 0.50
}


@dataclass
class ScoreResult:
    """Confidence score result"""
    score: float  # 0.0 - 1.0
    reasons: Dict[str, float]
    source: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass 
class CuratedFact:
    """Best fact selected from multiple sources"""
    entity_id: str
    fact_key: str
    fact_type: str
    payload: Dict[str, Any]
    confidence: float
    provenance: List[Dict[str, Any]]  # List of sources with their scores
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ConfidenceEngine:
    """
    Calculates confidence scores for facts from multiple sources.
    
    Usage:
        engine = ConfidenceEngine(db)
        
        # Score single fact
        score = engine.score_fact(fact_record)
        
        # Pick best from multiple
        best = engine.pick_best_fact(list_of_facts)
    """
    
    def __init__(self, db=None):
        self.db = db
        self.source_weights = DEFAULT_SOURCE_WEIGHT.copy()
    
    def _freshness_score(self, observed_at: datetime, half_life_hours: float = 72.0) -> float:
        """
        Calculate freshness score.
        Score = 1.0 for now, 0.5 after half_life_hours, exponential decay.
        """
        if not observed_at:
            return 0.5
        
        now = datetime.now(timezone.utc)
        
        if isinstance(observed_at, str):
            try:
                observed_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
            except:
                return 0.5
        
        age_hours = (now - observed_at).total_seconds() / 3600.0
        
        # Exponential decay: 1.0 now -> 0.5 after half_life
        return math.exp(-math.log(2) * (age_hours / half_life_hours))
    
    def _endpoint_health_score(self, endpoint_stats: Dict[str, Any]) -> float:
        """
        Calculate endpoint health score.
        Based on success_rate and schema_change_rate.
        """
        if not endpoint_stats:
            return 0.7  # Default
        
        success_rate = float(endpoint_stats.get("success_rate", 0.7))
        schema_change_rate = float(endpoint_stats.get("schema_change_rate", 0.2))
        
        # Penalize schema churn harder
        return max(0.0, min(1.0, 0.7 * success_rate + 0.3 * (1.0 - schema_change_rate)))
    
    def _agreement_score(self, agreement_ratio: float) -> float:
        """
        Score based on cross-source agreement.
        0.0 = no agreement, 1.0 = all sources agree.
        """
        # Base 0.4 + up to 0.6 based on agreement
        return max(0.0, min(1.0, 0.4 + 0.6 * agreement_ratio))
    
    def score_fact(
        self,
        source: str,
        observed_at: Optional[datetime] = None,
        endpoint_stats: Optional[Dict[str, Any]] = None,
        agreement_ratio: float = 0.5,
        auth_level: str = "public"
    ) -> ScoreResult:
        """
        Calculate confidence score for a single fact.
        
        Args:
            source: Data source name
            observed_at: When the data was observed
            endpoint_stats: Endpoint health metrics
            agreement_ratio: How many other sources agree (0-1)
            auth_level: "public" | "browser" | "auth"
        
        Returns:
            ScoreResult with score and breakdown
        """
        # Component scores
        w_source = self.source_weights.get(source.lower(), 0.6)
        w_fresh = self._freshness_score(observed_at)
        w_ep = self._endpoint_health_score(endpoint_stats)
        w_agree = self._agreement_score(agreement_ratio)
        
        # Auth bonus
        auth_bonus = 0.0
        if auth_level == "browser":
            auth_bonus = 0.03
        elif auth_level == "auth":
            auth_bonus = 0.05
        
        # Weighted combination
        score = (
            0.40 * w_source +
            0.20 * w_fresh +
            0.20 * w_ep +
            0.20 * w_agree +
            auth_bonus
        )
        
        score = max(0.0, min(1.0, score))
        
        return ScoreResult(
            score=score,
            reasons={
                "source_weight": round(w_source, 3),
                "freshness": round(w_fresh, 3),
                "endpoint_health": round(w_ep, 3),
                "agreement": round(w_agree, 3),
                "auth_bonus": round(auth_bonus, 3)
            },
            source=source
        )
    
    def calculate_agreement(self, facts: List[Dict[str, Any]], key_fields: List[str]) -> Dict[str, float]:
        """
        Calculate agreement ratio between facts.
        Returns agreement ratio for each fact.
        """
        if len(facts) <= 1:
            return {i: 1.0 for i in range(len(facts))}
        
        agreements = {}
        
        for i, fact in enumerate(facts):
            matching = 0
            total = 0
            
            for j, other in enumerate(facts):
                if i == j:
                    continue
                
                total += 1
                matches = 0
                checked = 0
                
                for field in key_fields:
                    v1 = fact.get("payload", fact).get(field)
                    v2 = other.get("payload", other).get(field)
                    
                    if v1 is not None and v2 is not None:
                        checked += 1
                        # For numbers, allow 10% tolerance
                        if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                            if v1 == 0 and v2 == 0:
                                matches += 1
                            elif abs(v1 - v2) / max(abs(v1), abs(v2), 1) <= 0.1:
                                matches += 1
                        elif str(v1).lower() == str(v2).lower():
                            matches += 1
                
                if checked > 0:
                    matching += matches / checked
            
            agreements[i] = matching / total if total > 0 else 1.0
        
        return agreements
    
    def pick_best_fact(
        self,
        facts: List[Dict[str, Any]],
        key_fields: Optional[List[str]] = None
    ) -> CuratedFact:
        """
        Pick the best fact from multiple sources.
        
        Args:
            facts: List of facts from different sources
            key_fields: Fields to check for agreement
        
        Returns:
            CuratedFact with best data and provenance
        """
        if not facts:
            raise ValueError("No facts to curate")
        
        if len(facts) == 1:
            f = facts[0]
            score = self.score_fact(
                source=f.get("source", "unknown"),
                observed_at=f.get("observed_at") or f.get("_scraped_at")
            )
            return CuratedFact(
                entity_id=f.get("entity_id", "unknown"),
                fact_key=f.get("fact_key", f.get("id", "unknown")),
                fact_type=f.get("fact_type", f.get("type", "unknown")),
                payload=f.get("payload", f),
                confidence=score.score,
                provenance=[{"source": f.get("source"), "score": score.score, "reasons": score.reasons}]
            )
        
        # Default key fields
        if key_fields is None:
            key_fields = ["amount_usd", "raised_usd", "stage", "date", "percent"]
        
        # Calculate agreement
        agreements = self.calculate_agreement(facts, key_fields)
        
        # Score each fact
        scored = []
        for i, f in enumerate(facts):
            score = self.score_fact(
                source=f.get("source", "unknown"),
                observed_at=f.get("observed_at") or f.get("_scraped_at"),
                endpoint_stats=f.get("endpoint_stats"),
                agreement_ratio=agreements.get(i, 0.5),
                auth_level=f.get("auth_level", "public")
            )
            scored.append((score.score, f, score))
        
        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)
        
        best_score, best_fact, best_result = scored[0]
        
        # Build provenance
        provenance = []
        for sc, f, res in scored[:5]:
            provenance.append({
                "source": f.get("source"),
                "score": round(sc, 3),
                "reasons": res.reasons
            })
        
        return CuratedFact(
            entity_id=best_fact.get("entity_id", "unknown"),
            fact_key=best_fact.get("fact_key", best_fact.get("id", "unknown")),
            fact_type=best_fact.get("fact_type", best_fact.get("type", "unknown")),
            payload=best_fact.get("payload", best_fact),
            confidence=best_score,
            provenance=provenance
        )
    
    def update_source_weight(self, source: str, weight: float):
        """Update source reliability weight"""
        self.source_weights[source.lower()] = max(0.0, min(1.0, weight))
    
    def get_source_weights(self) -> Dict[str, float]:
        """Get all source weights"""
        return self.source_weights.copy()


# Singleton
confidence_engine: Optional[ConfidenceEngine] = None


def init_confidence_engine(db=None) -> ConfidenceEngine:
    """Initialize confidence engine"""
    global confidence_engine
    confidence_engine = ConfidenceEngine(db)
    return confidence_engine
