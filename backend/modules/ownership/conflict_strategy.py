"""
Field Conflict Strategy

Extends ownership layer with conflict resolution rules.

When multiple providers supply the same field, how do we resolve?

Strategies:
- exchange_only: Only accept from exchange tree
- highest_confidence: Take from provider with best reliability
- majority_vote: Consensus from multiple sources
- merge_sources: Combine data from all sources
- freshest: Most recently updated wins
- weighted_average: For numeric fields
"""

from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime


class ConflictStrategy(str, Enum):
    """Strategy for resolving field conflicts"""
    EXCHANGE_ONLY = "exchange_only"        # Only accept from exchange tree
    HIGHEST_CONFIDENCE = "highest_confidence"  # Best reliability score
    MAJORITY_VOTE = "majority_vote"         # Consensus wins
    MERGE_SOURCES = "merge_sources"         # Combine all
    FRESHEST = "freshest"                   # Most recent
    WEIGHTED_AVERAGE = "weighted_average"   # For numerics
    CUSTOM = "custom"                       # Custom resolver function


class FieldConflictRule(BaseModel):
    """Rule for resolving conflicts on a specific field"""
    field: str
    strategy: ConflictStrategy
    min_sources_for_vote: int = Field(3, description="Min sources for majority vote")
    confidence_threshold: float = Field(0.7, description="Min confidence to accept")
    merge_method: Optional[str] = Field(None, description="For merge: union/intersect/append")
    custom_resolver: Optional[str] = Field(None, description="Name of custom function")
    
    # Validation rules
    require_tree_match: bool = Field(True, description="Must come from correct tree")
    allow_partial: bool = Field(False, description="Accept partial data")


# =============================================================================
# FIELD CONFLICT STRATEGY MAP
# =============================================================================

FIELD_CONFLICT_STRATEGY: Dict[str, FieldConflictRule] = {
    # =========================================================================
    # PRICE DATA - Exchange Only
    # =========================================================================
    "spot_price": FieldConflictRule(
        field="spot_price",
        strategy=ConflictStrategy.EXCHANGE_ONLY,
        require_tree_match=True,
        allow_partial=False
    ),
    "candles": FieldConflictRule(
        field="candles",
        strategy=ConflictStrategy.EXCHANGE_ONLY,
        require_tree_match=True
    ),
    "open_interest": FieldConflictRule(
        field="open_interest",
        strategy=ConflictStrategy.EXCHANGE_ONLY,
        require_tree_match=True
    ),
    "funding_rate": FieldConflictRule(
        field="funding_rate",
        strategy=ConflictStrategy.EXCHANGE_ONLY,
        require_tree_match=True
    ),
    
    # =========================================================================
    # TVL - Highest Confidence (DefiLlama primary)
    # =========================================================================
    "tvl": FieldConflictRule(
        field="tvl",
        strategy=ConflictStrategy.HIGHEST_CONFIDENCE,
        confidence_threshold=0.9,
        require_tree_match=True
    ),
    "protocol_tvl": FieldConflictRule(
        field="protocol_tvl",
        strategy=ConflictStrategy.HIGHEST_CONFIDENCE,
        confidence_threshold=0.9
    ),
    
    # =========================================================================
    # FUNDING DATA - Majority Vote
    # =========================================================================
    "funding_round_amount": FieldConflictRule(
        field="funding_round_amount",
        strategy=ConflictStrategy.MAJORITY_VOTE,
        min_sources_for_vote=2,
        confidence_threshold=0.7
    ),
    "funding_rounds": FieldConflictRule(
        field="funding_rounds",
        strategy=ConflictStrategy.MERGE_SOURCES,
        merge_method="union",
        allow_partial=True
    ),
    "investors": FieldConflictRule(
        field="investors",
        strategy=ConflictStrategy.MERGE_SOURCES,
        merge_method="union"
    ),
    "lead_investor": FieldConflictRule(
        field="lead_investor",
        strategy=ConflictStrategy.MAJORITY_VOTE,
        min_sources_for_vote=2
    ),
    
    # =========================================================================
    # TEAM DATA - Merge Sources
    # =========================================================================
    "team_members": FieldConflictRule(
        field="team_members",
        strategy=ConflictStrategy.MERGE_SOURCES,
        merge_method="union",
        allow_partial=True
    ),
    "advisors": FieldConflictRule(
        field="advisors",
        strategy=ConflictStrategy.MERGE_SOURCES,
        merge_method="union"
    ),
    "team_positions": FieldConflictRule(
        field="team_positions",
        strategy=ConflictStrategy.MERGE_SOURCES,
        merge_method="append"  # Keep all position histories
    ),
    
    # =========================================================================
    # TOKENOMICS - Freshest
    # =========================================================================
    "circulating_supply": FieldConflictRule(
        field="circulating_supply",
        strategy=ConflictStrategy.FRESHEST
    ),
    "total_supply": FieldConflictRule(
        field="total_supply",
        strategy=ConflictStrategy.FRESHEST
    ),
    "max_supply": FieldConflictRule(
        field="max_supply",
        strategy=ConflictStrategy.MAJORITY_VOTE,
        min_sources_for_vote=2
    ),
    
    # =========================================================================
    # MARKET DATA - Weighted Average
    # =========================================================================
    "volume_24h": FieldConflictRule(
        field="volume_24h",
        strategy=ConflictStrategy.WEIGHTED_AVERAGE,
        confidence_threshold=0.8
    ),
    "market_cap": FieldConflictRule(
        field="market_cap",
        strategy=ConflictStrategy.FRESHEST
    ),
    
    # =========================================================================
    # DESCRIPTIVE DATA - Highest Confidence
    # =========================================================================
    "project_description": FieldConflictRule(
        field="project_description",
        strategy=ConflictStrategy.HIGHEST_CONFIDENCE,
        confidence_threshold=0.8
    ),
    "project_profile": FieldConflictRule(
        field="project_profile",
        strategy=ConflictStrategy.HIGHEST_CONFIDENCE
    ),
    
    # =========================================================================
    # UNLOCK DATA - Merge + Freshest
    # =========================================================================
    "unlock_schedule": FieldConflictRule(
        field="unlock_schedule",
        strategy=ConflictStrategy.FRESHEST,
        confidence_threshold=0.85
    ),
    "upcoming_unlocks": FieldConflictRule(
        field="upcoming_unlocks",
        strategy=ConflictStrategy.FRESHEST
    ),
    
    # =========================================================================
    # DEV ACTIVITY - Highest Confidence (GitHub primary)
    # =========================================================================
    "github_activity": FieldConflictRule(
        field="github_activity",
        strategy=ConflictStrategy.HIGHEST_CONFIDENCE
    ),
    "developer_count": FieldConflictRule(
        field="developer_count",
        strategy=ConflictStrategy.HIGHEST_CONFIDENCE
    ),
}


class ConflictResolver:
    """
    Resolves data conflicts between multiple providers
    """
    
    def __init__(self, provider_capabilities: Dict = None):
        self.strategies = FIELD_CONFLICT_STRATEGY
        self.provider_caps = provider_capabilities or {}
    
    def resolve(
        self,
        field: str,
        values: List[Dict[str, Any]]  # [{provider: str, value: any, confidence: float, timestamp: datetime}]
    ) -> Optional[Any]:
        """
        Resolve conflict for a field given multiple provider values
        
        Args:
            field: Field name
            values: List of {provider, value, confidence, timestamp}
        
        Returns:
            Resolved value
        """
        if not values:
            return None
        
        if len(values) == 1:
            return values[0]["value"]
        
        rule = self.strategies.get(field)
        if not rule:
            # Default: highest confidence
            return self._resolve_highest_confidence(values)
        
        strategy = rule.strategy
        
        if strategy == ConflictStrategy.EXCHANGE_ONLY:
            return self._resolve_exchange_only(values, rule)
        elif strategy == ConflictStrategy.HIGHEST_CONFIDENCE:
            return self._resolve_highest_confidence(values, rule)
        elif strategy == ConflictStrategy.MAJORITY_VOTE:
            return self._resolve_majority_vote(values, rule)
        elif strategy == ConflictStrategy.MERGE_SOURCES:
            return self._resolve_merge(values, rule)
        elif strategy == ConflictStrategy.FRESHEST:
            return self._resolve_freshest(values, rule)
        elif strategy == ConflictStrategy.WEIGHTED_AVERAGE:
            return self._resolve_weighted_average(values, rule)
        else:
            return self._resolve_highest_confidence(values)
    
    def _resolve_exchange_only(
        self,
        values: List[Dict],
        rule: FieldConflictRule
    ) -> Optional[Any]:
        """Only accept from exchange providers"""
        exchange_providers = {"binance", "bybit", "okx", "coinbase", "hyperliquid"}
        
        exchange_values = [
            v for v in values 
            if v.get("provider", "").lower() in exchange_providers
        ]
        
        if not exchange_values:
            return None
        
        # Return highest confidence among exchanges
        return self._resolve_highest_confidence(exchange_values)
    
    def _resolve_highest_confidence(
        self,
        values: List[Dict],
        rule: FieldConflictRule = None
    ) -> Optional[Any]:
        """Take value from highest confidence provider"""
        threshold = rule.confidence_threshold if rule else 0.0
        
        valid_values = [
            v for v in values 
            if v.get("confidence", 0) >= threshold
        ]
        
        if not valid_values:
            valid_values = values  # Fall back to all
        
        best = max(valid_values, key=lambda x: x.get("confidence", 0))
        return best.get("value")
    
    def _resolve_majority_vote(
        self,
        values: List[Dict],
        rule: FieldConflictRule
    ) -> Optional[Any]:
        """Consensus from multiple sources"""
        if len(values) < rule.min_sources_for_vote:
            return self._resolve_highest_confidence(values, rule)
        
        # Count occurrences of each value
        value_counts = {}
        for v in values:
            val = str(v.get("value"))  # Convert to string for comparison
            if val not in value_counts:
                value_counts[val] = {"count": 0, "original": v.get("value")}
            value_counts[val]["count"] += 1
        
        # Find majority
        majority_threshold = len(values) / 2
        for val, info in value_counts.items():
            if info["count"] > majority_threshold:
                return info["original"]
        
        # No majority - fall back to highest confidence
        return self._resolve_highest_confidence(values, rule)
    
    def _resolve_merge(
        self,
        values: List[Dict],
        rule: FieldConflictRule
    ) -> Any:
        """Merge data from all sources"""
        merge_method = rule.merge_method or "union"
        
        if merge_method == "union":
            # Union of all lists
            result = set()
            for v in values:
                val = v.get("value", [])
                if isinstance(val, list):
                    result.update(val)
                elif isinstance(val, dict):
                    result.update(val.keys())
                else:
                    result.add(val)
            return list(result)
        
        elif merge_method == "intersect":
            # Intersection of all lists
            sets = []
            for v in values:
                val = v.get("value", [])
                if isinstance(val, list):
                    sets.append(set(val))
            if not sets:
                return []
            result = sets[0]
            for s in sets[1:]:
                result &= s
            return list(result)
        
        elif merge_method == "append":
            # Append all values (for arrays)
            result = []
            seen = set()
            for v in values:
                val = v.get("value", [])
                if isinstance(val, list):
                    for item in val:
                        key = str(item)
                        if key not in seen:
                            result.append(item)
                            seen.add(key)
                else:
                    if str(val) not in seen:
                        result.append(val)
                        seen.add(str(val))
            return result
        
        return values[0].get("value") if values else None
    
    def _resolve_freshest(
        self,
        values: List[Dict],
        rule: FieldConflictRule = None
    ) -> Optional[Any]:
        """Most recently updated value wins"""
        sorted_values = sorted(
            values,
            key=lambda x: x.get("timestamp", datetime.min),
            reverse=True
        )
        return sorted_values[0].get("value") if sorted_values else None
    
    def _resolve_weighted_average(
        self,
        values: List[Dict],
        rule: FieldConflictRule
    ) -> Optional[float]:
        """Weighted average for numeric fields"""
        try:
            total_weight = 0
            weighted_sum = 0
            
            for v in values:
                confidence = v.get("confidence", 0.5)
                if confidence < rule.confidence_threshold:
                    continue
                
                val = float(v.get("value", 0))
                weighted_sum += val * confidence
                total_weight += confidence
            
            if total_weight == 0:
                return None
            
            return weighted_sum / total_weight
        except (ValueError, TypeError):
            return self._resolve_highest_confidence(values, rule)
    
    def get_strategy(self, field: str) -> Optional[FieldConflictRule]:
        """Get conflict strategy for a field"""
        return self.strategies.get(field)
    
    def list_strategies(self) -> Dict[str, str]:
        """List all field strategies"""
        return {
            field: rule.strategy.value 
            for field, rule in self.strategies.items()
        }


# Singleton instance
conflict_resolver = ConflictResolver()
