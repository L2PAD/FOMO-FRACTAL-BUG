"""
Schema Detector
===============

Automatically detects capabilities from API response schema.
"""

import re
import logging
from typing import Dict, List, Tuple, Any, Optional

from .models import CapabilityType, EndpointSchema

logger = logging.getLogger(__name__)


# Field patterns for capability detection
CAPABILITY_PATTERNS = {
    CapabilityType.MARKET_DATA: {
        "fields": ["price", "market_cap", "marketcap", "volume", "volume_24h", "circulating_supply", "ath", "atl"],
        "weight": 1.0
    },
    CapabilityType.DEFI_DATA: {
        "fields": ["tvl", "total_value_locked", "apy", "apr", "yield", "protocol", "chain"],
        "weight": 1.0
    },
    CapabilityType.DEX_DATA: {
        "fields": ["pair", "pairs", "liquidity", "dex", "pool", "swap", "amm", "base_token", "quote_token"],
        "weight": 1.0
    },
    CapabilityType.FUNDING: {
        "fields": ["funding", "round", "investor", "valuation", "raised", "series", "seed"],
        "weight": 1.0
    },
    CapabilityType.NEWS: {
        "fields": ["title", "content", "article", "news", "published", "author", "headline"],
        "weight": 1.0
    },
    CapabilityType.DERIVATIVES: {
        "fields": ["funding_rate", "open_interest", "liquidation", "futures", "perp", "perpetual"],
        "weight": 1.0
    },
    CapabilityType.ONCHAIN: {
        "fields": ["transaction", "block", "gas", "address", "wallet", "hash", "tx"],
        "weight": 1.0
    },
    CapabilityType.ACTIVITIES: {
        "fields": ["activity", "event", "airdrop", "campaign", "task", "reward"],
        "weight": 1.0
    },
    CapabilityType.PROTOCOL: {
        "fields": ["protocol", "dao", "governance", "vote", "proposal"],
        "weight": 0.8
    }
}


class SchemaDetector:
    """
    Detects API capabilities from response schema.
    """
    
    def __init__(self):
        self.patterns = CAPABILITY_PATTERNS
    
    def detect_from_response(self, response_data: Any) -> EndpointSchema:
        """
        Analyze API response and detect capabilities.
        
        Args:
            response_data: JSON response from API
            
        Returns:
            EndpointSchema with detected capabilities
        """
        schema = EndpointSchema(endpoint_id="temp")
        
        # Determine if array or object
        if isinstance(response_data, list):
            schema.is_array = True
            sample = response_data[0] if response_data else {}
        elif isinstance(response_data, dict):
            schema.is_array = False
            sample = response_data
            # Check if data is nested
            if "data" in sample and isinstance(sample["data"], (list, dict)):
                sample = sample["data"]
                if isinstance(sample, list) and sample:
                    schema.is_array = True
                    sample = sample[0]
        else:
            return schema
        
        # Extract fields
        fields = self._extract_fields(sample)
        schema.fields = fields
        schema.sample_data = self._truncate_sample(sample)
        
        # Check for common indicators
        field_names_lower = [f.lower() for f in fields.keys()]
        
        schema.has_price = any(p in field_names_lower for p in ["price", "current_price", "usd"])
        schema.has_volume = any(p in field_names_lower for p in ["volume", "volume_24h", "total_volume"])
        schema.has_tvl = any(p in field_names_lower for p in ["tvl", "total_value_locked"])
        schema.has_timestamp = any(p in field_names_lower for p in ["timestamp", "time", "date", "created_at", "updated_at"])
        schema.has_symbol = any(p in field_names_lower for p in ["symbol", "ticker", "coin"])
        
        # Detect capability
        capability, confidence = self._detect_capability(field_names_lower)
        schema.detected_capability = capability
        schema.confidence = confidence
        
        return schema
    
    def _extract_fields(self, obj: Dict, prefix: str = "") -> Dict[str, str]:
        """Extract field names and types from object"""
        fields = {}
        
        if not isinstance(obj, dict):
            return fields
        
        for key, value in obj.items():
            field_name = f"{prefix}.{key}" if prefix else key
            
            if value is None:
                fields[field_name] = "null"
            elif isinstance(value, bool):
                fields[field_name] = "boolean"
            elif isinstance(value, int):
                fields[field_name] = "integer"
            elif isinstance(value, float):
                fields[field_name] = "number"
            elif isinstance(value, str):
                fields[field_name] = "string"
            elif isinstance(value, list):
                fields[field_name] = "array"
            elif isinstance(value, dict):
                fields[field_name] = "object"
                # Recursively extract nested fields (1 level)
                if not prefix:
                    nested = self._extract_fields(value, field_name)
                    fields.update(nested)
        
        return fields
    
    def _detect_capability(self, field_names: List[str]) -> Tuple[CapabilityType, float]:
        """
        Detect capability type from field names.
        
        Returns:
            (capability_type, confidence_score)
        """
        scores = {}
        
        for capability, config in self.patterns.items():
            pattern_fields = config["fields"]
            weight = config["weight"]
            
            matches = 0
            for pattern in pattern_fields:
                if any(pattern in field for field in field_names):
                    matches += 1
            
            if matches > 0:
                score = (matches / len(pattern_fields)) * weight
                scores[capability] = score
        
        if not scores:
            return CapabilityType.UNKNOWN, 0.0
        
        # Get best match
        best_capability = max(scores, key=scores.get)
        best_score = scores[best_capability]
        
        # Normalize confidence (0-1)
        confidence = min(best_score * 2, 1.0)
        
        return best_capability, confidence
    
    def _truncate_sample(self, sample: Dict, max_depth: int = 2) -> Dict:
        """Truncate sample data for storage"""
        if not isinstance(sample, dict):
            return {}
        
        truncated = {}
        for key, value in list(sample.items())[:10]:  # Max 10 fields
            if isinstance(value, str) and len(value) > 100:
                truncated[key] = value[:100] + "..."
            elif isinstance(value, list):
                truncated[key] = f"[array:{len(value)} items]"
            elif isinstance(value, dict):
                truncated[key] = "{object}"
            else:
                truncated[key] = value
        
        return truncated
    
    def detect_auth_requirements(self, response_status: int, response_headers: Dict) -> Tuple[bool, Optional[str]]:
        """
        Detect if endpoint requires authentication.
        
        Returns:
            (requires_auth, auth_type)
        """
        if response_status == 401:
            return True, "unknown"
        
        if response_status == 403:
            # Check if it's auth or rate limit
            if "rate" in str(response_headers).lower():
                return False, None
            return True, "unknown"
        
        # Check for API key hints in headers
        for header in response_headers:
            header_lower = header.lower()
            if "api-key" in header_lower or "authorization" in header_lower:
                return True, "api_key"
        
        return False, None
