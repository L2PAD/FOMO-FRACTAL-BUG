"""
Parser Validation Layer
=======================
Integrates Field Ownership Map into parsers for data validation.

Ensures:
- Data only comes from authorized sources
- Forbidden sources are rejected
- Weighted merge for conflicting values
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from modules.intel.field_ownership import (
    field_registry,
    DataTree,
    SOURCE_WEIGHTS,
    PROVIDER_CAPABILITIES
)

logger = logging.getLogger(__name__)


class ParserValidator:
    """
    Validates parsed data against Field Ownership Map.
    Ensures data integrity and source authorization.
    """
    
    def __init__(self, source_id: str):
        self.source_id = source_id
        self.capabilities = PROVIDER_CAPABILITIES.get(source_id, {})
        self.owns = set(self.capabilities.get("owns", []))
        self.can_provide = set(self.capabilities.get("can_provide", []))
        self.forbidden_for = set(self.capabilities.get("forbidden_for", []))
        self.weight = SOURCE_WEIGHTS.get(source_id, 0.5)
        self.domain = self.capabilities.get("domain", "unknown")
        
        self._validation_stats = {
            "accepted": 0,
            "rejected": 0,
            "warnings": 0
        }
    
    def validate_field(self, field: str) -> bool:
        """
        Check if this source can provide this field.
        Returns False if forbidden.
        """
        # Check if explicitly forbidden
        if field in self.forbidden_for:
            logger.warning(f"[Validator] {self.source_id} forbidden for field: {field}")
            self._validation_stats["rejected"] += 1
            return False
        
        # Check via field registry
        if field_registry.is_forbidden(field, self.source_id):
            logger.warning(f"[Validator] {self.source_id} not authorized for field: {field}")
            self._validation_stats["rejected"] += 1
            return False
        
        # Check if can provide
        if field in self.owns or field in self.can_provide:
            self._validation_stats["accepted"] += 1
            return True
        
        # Check via registry
        if field_registry.validate_source_for_field(field, self.source_id):
            self._validation_stats["accepted"] += 1
            return True
        
        # Unknown field - warn but allow
        logger.debug(f"[Validator] Unknown field {field} from {self.source_id}")
        self._validation_stats["warnings"] += 1
        return True
    
    def filter_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter data dict, removing forbidden fields.
        Returns only authorized fields.
        """
        filtered = {}
        removed = []
        
        for key, value in data.items():
            if self.validate_field(key):
                filtered[key] = value
            else:
                removed.append(key)
        
        if removed:
            logger.info(f"[Validator] {self.source_id}: removed {len(removed)} forbidden fields: {removed[:5]}")
        
        return filtered
    
    def tag_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tag data with source metadata for later aggregation.
        """
        return {
            "_source": self.source_id,
            "_weight": self.weight,
            "_domain": self.domain,
            "_timestamp": datetime.now(timezone.utc).isoformat(),
            "_owns": list(self.owns & set(data.keys())),
            **data
        }
    
    def get_stats(self) -> Dict:
        return {
            "source_id": self.source_id,
            "domain": self.domain,
            "weight": self.weight,
            **self._validation_stats
        }


class DataAggregator:
    """
    Aggregates data from multiple sources using Field Ownership rules.
    Handles weighted merge for conflicting values.
    """
    
    def __init__(self):
        self._data_pool: Dict[str, Dict[str, Any]] = {}  # field -> {source: value}
    
    def add_data(self, source_id: str, data: Dict[str, Any]):
        """Add data from a source to the pool"""
        validator = ParserValidator(source_id)
        filtered = validator.filter_data(data)
        
        for field, value in filtered.items():
            if field not in self._data_pool:
                self._data_pool[field] = {}
            self._data_pool[field][source_id] = value
    
    def resolve(self) -> Dict[str, Any]:
        """
        Resolve all fields using ownership rules.
        Returns final merged data.
        """
        result = {}
        
        for field, sources in self._data_pool.items():
            if len(sources) == 1:
                # Single source - use directly
                result[field] = list(sources.values())[0]
            else:
                # Multiple sources - use weighted merge
                merged = field_registry.weighted_merge(field, sources)
                if merged is not None:
                    result[field] = merged
        
        return result
    
    def get_source_for_field(self, field: str) -> Optional[str]:
        """Get which source provided the value for a field"""
        if field not in self._data_pool:
            return None
        
        sources = self._data_pool[field]
        if len(sources) == 1:
            return list(sources.keys())[0]
        
        # Return owner if available
        owner = field_registry.get_owner(field)
        if owner and owner in sources:
            return owner
        
        # Return highest weight source
        best_source = max(sources.keys(), key=lambda s: SOURCE_WEIGHTS.get(s, 0))
        return best_source


def create_validator(source_id: str) -> ParserValidator:
    """Factory function to create validator for a source"""
    return ParserValidator(source_id)


def validate_exchange_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate that data is appropriate for Exchange Tree.
    Rejects Intel Tree fields.
    """
    exchange_fields = {
        "spot_price", "ohlcv", "candles", "spot_volume", "pair_volume",
        "open_interest", "funding_rate", "liquidations",
        "exchange_markets", "trading_pairs", "listed_on"
    }
    
    filtered = {}
    for key, value in data.items():
        tree = field_registry.get_tree(key)
        if tree == DataTree.EXCHANGE or key in exchange_fields:
            filtered[key] = value
        elif key.startswith("_"):  # Allow metadata
            filtered[key] = value
    
    return filtered


def validate_intel_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate that data is appropriate for Intel Tree.
    Rejects raw Exchange Tree fields.
    """
    exchange_only = {
        "spot_price", "ohlcv", "candles", "open_interest",
        "funding_rate", "liquidations"
    }
    
    filtered = {}
    for key, value in data.items():
        if key in exchange_only:
            logger.warning(f"[Validator] Rejecting exchange-only field from Intel source: {key}")
            continue
        filtered[key] = value
    
    return filtered


# ═══════════════════════════════════════════════════════════════
# Parser Mixins
# ═══════════════════════════════════════════════════════════════

class ValidatedParserMixin:
    """
    Mixin for parsers to add validation.
    Usage: class MyParser(ValidatedParserMixin): ...
    """
    source_id: str = "unknown"
    
    def __init__(self):
        self._validator = ParserValidator(self.source_id)
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and filter data"""
        return self._validator.filter_data(data)
    
    def tag(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Tag data with source metadata"""
        return self._validator.tag_data(data)
    
    def is_field_allowed(self, field: str) -> bool:
        """Check if field is allowed for this source"""
        return self._validator.validate_field(field)


# ═══════════════════════════════════════════════════════════════
# Convenience functions for parsers
# ═══════════════════════════════════════════════════════════════

def validate_parser_output(source_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    One-liner to validate parser output.
    Usage: validated_data = validate_parser_output("cryptorank", raw_data)
    """
    validator = ParserValidator(source_id)
    return validator.filter_data(data)


def get_allowed_fields(source_id: str) -> List[str]:
    """Get list of fields this source is allowed to provide"""
    caps = PROVIDER_CAPABILITIES.get(source_id, {})
    owns = set(caps.get("owns", []))
    can_provide = set(caps.get("can_provide", []))
    return list(owns | can_provide)


def get_forbidden_fields(source_id: str) -> List[str]:
    """Get list of fields this source must NOT provide"""
    caps = PROVIDER_CAPABILITIES.get(source_id, {})
    return caps.get("forbidden_for", [])
