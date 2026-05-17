"""
Source Reliability Weights
===========================
Configurable source quality weights for importance scoring.
Each source has a reliability weight that affects the importance_score.

Usage:
    from .source_reliability import SourceReliabilityManager, get_source_weight
    
    manager = SourceReliabilityManager(db)
    weight = await manager.get_weight("coindesk")
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# DEFAULT SOURCE WEIGHTS
# ═══════════════════════════════════════════════════════════════

DEFAULT_SOURCE_WEIGHTS = {
    # Tier A - Premium (1.0) - Most reliable, breaking news first
    "coindesk": 1.0,
    "theblock": 1.0,
    "the_block": 1.0,
    "bloomberg": 1.0,
    "bloomberg_crypto": 1.0,
    "reuters": 1.0,
    "reuters_crypto": 1.0,
    "wsj": 1.0,
    "financial_times": 1.0,
    
    # Tier A - High Quality (0.95)
    "cointelegraph": 0.95,
    "blockworks": 0.95,
    "decrypt": 0.90,
    "bitcoinmagazine": 0.90,
    
    # Tier B - Quality (0.80-0.85)
    "defiant": 0.85,
    "unchained": 0.85,
    "bankless": 0.85,
    "dailyhodl": 0.80,
    "cryptoslate": 0.80,
    "cryptonews_en": 0.80,
    "bitcoinist": 0.80,
    
    # Tier B - Regional/Specialized (0.75-0.80)
    "incrypted": 0.80,  # Russian
    "forklog": 0.80,    # Russian
    "bits_media": 0.75,
    "coinspot": 0.75,
    "cryptach": 0.75,   # Ukrainian
    
    # Tier C - Research (0.70-0.80)
    "messari": 0.80,
    "messari_research": 0.80,
    "delphi_digital": 0.80,
    "delphidigital": 0.80,
    "galaxy_research": 0.75,
    "coinbase_research": 0.75,
    "binance_research": 0.75,
    "a16z_crypto": 0.80,
    "paradigm": 0.80,
    
    # Tier C - Analytics (0.70-0.75)
    "glassnode": 0.75,
    "glassnode_insights": 0.75,
    "nansen": 0.75,
    "nansen_research": 0.75,
    "chainalysis": 0.75,
    "santiment": 0.70,
    "santiment_insights": 0.70,
    "dune": 0.70,
    "dune_blog": 0.70,
    
    # Tier C - Protocol Blogs (0.70)
    "ethereum_blog": 0.70,
    "solana_blog": 0.70,
    "avalanche_blog": 0.70,
    "polygon_blog": 0.70,
    "arbitrum_blog": 0.70,
    "optimism_blog": 0.70,
    
    # Tier D - Aggregators (0.50-0.60)
    "cryptopanic": 0.50,
    "coingecko_news": 0.55,
    "coinmarketcap_news": 0.55,
    
    # Tier D - Secondary (0.40-0.50)
    "beincrypto": 0.50,
    "newsbtc": 0.45,
    "cryptopotato": 0.50,
    "utoday": 0.45,
    "coinjournal": 0.45,
    "coingape": 0.45,
    "coinpedia": 0.45,
    "cryptobriefing": 0.50,
    "ambcrypto": 0.45,
    "cryptoglobe": 0.45,
    "zycrypto": 0.40,
    "blockonomi": 0.45,
    "coinspeaker": 0.45,
    "cryptonewsz": 0.40,
    "nulltx": 0.40,
    
    # Tier D - Security (0.60-0.70)
    "rekt_news": 0.70,
    "slowmist": 0.65,
    "certik": 0.65,
    "immunefi": 0.65,
    
    # Social/Unverified (0.30-0.40)
    "twitter": 0.35,
    "medium": 0.40,
    "reddit": 0.30,
    "telegram": 0.30,
    
    # Default for unknown sources
    "default": 0.50
}


# ═══════════════════════════════════════════════════════════════
# SOURCE RELIABILITY MANAGER
# ═══════════════════════════════════════════════════════════════

class SourceReliabilityManager:
    """
    Manages source reliability weights with DB persistence.
    Weights can be customized per-source and stored in MongoDB.
    """
    
    def __init__(self, db):
        self.db = db
        self.cache: Dict[str, float] = {}
        self.cache_loaded = False
    
    async def load_weights(self) -> Dict[str, float]:
        """Load custom weights from database."""
        if self.cache_loaded:
            return self.cache
        
        # Start with defaults
        self.cache = DEFAULT_SOURCE_WEIGHTS.copy()
        
        # Load custom weights from DB
        try:
            cursor = self.db.source_weights.find({})
            async for doc in cursor:
                source_id = doc.get("source_id")
                weight = doc.get("weight")
                if source_id and weight is not None:
                    self.cache[source_id] = weight
            self.cache_loaded = True
        except Exception as e:
            logger.warning(f"[SourceReliability] Failed to load weights: {e}")
        
        return self.cache
    
    async def get_weight(self, source_id: str) -> float:
        """Get weight for a source."""
        if not self.cache_loaded:
            await self.load_weights()
        
        # Normalize source_id
        normalized = source_id.lower().replace(" ", "_").replace("-", "_")
        
        return self.cache.get(normalized, self.cache.get("default", 0.5))
    
    async def get_weights_for_sources(self, source_ids: List[str]) -> Dict[str, float]:
        """Get weights for multiple sources."""
        if not self.cache_loaded:
            await self.load_weights()
        
        result = {}
        for source_id in source_ids:
            normalized = source_id.lower().replace(" ", "_").replace("-", "_")
            result[source_id] = self.cache.get(normalized, self.cache.get("default", 0.5))
        
        return result
    
    async def set_weight(self, source_id: str, weight: float, reason: str = None) -> Dict[str, Any]:
        """Set custom weight for a source."""
        normalized = source_id.lower().replace(" ", "_").replace("-", "_")
        
        # Validate weight
        weight = max(0.0, min(1.0, weight))
        
        # Update cache
        self.cache[normalized] = weight
        
        # Persist to DB
        await self.db.source_weights.update_one(
            {"source_id": normalized},
            {"$set": {
                "source_id": normalized,
                "weight": weight,
                "reason": reason,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }},
            upsert=True
        )
        
        logger.info(f"[SourceReliability] Set weight for {normalized}: {weight}")
        
        return {
            "source_id": normalized,
            "weight": weight,
            "reason": reason
        }
    
    async def reset_to_default(self, source_id: str) -> Dict[str, Any]:
        """Reset source weight to default."""
        normalized = source_id.lower().replace(" ", "_").replace("-", "_")
        
        # Remove from DB
        await self.db.source_weights.delete_one({"source_id": normalized})
        
        # Reset cache to default
        default = DEFAULT_SOURCE_WEIGHTS.get(normalized, DEFAULT_SOURCE_WEIGHTS["default"])
        self.cache[normalized] = default
        
        return {
            "source_id": normalized,
            "weight": default,
            "is_default": True
        }
    
    async def get_all_weights(self) -> List[Dict[str, Any]]:
        """Get all source weights with their values."""
        if not self.cache_loaded:
            await self.load_weights()
        
        result = []
        for source_id, weight in sorted(self.cache.items(), key=lambda x: -x[1]):
            if source_id == "default":
                continue
            result.append({
                "source_id": source_id,
                "weight": weight,
                "tier": self._weight_to_tier(weight)
            })
        
        return result
    
    def _weight_to_tier(self, weight: float) -> str:
        """Convert weight to tier letter."""
        if weight >= 0.90:
            return "A"
        elif weight >= 0.75:
            return "B"
        elif weight >= 0.50:
            return "C"
        else:
            return "D"
    
    async def calculate_combined_weight(self, sources: List[str]) -> float:
        """Calculate combined weight for multiple sources."""
        if not sources:
            return 0.5
        
        weights = []
        for source in sources:
            w = await self.get_weight(source)
            weights.append(w)
        
        # Return max weight (best source defines reliability)
        return max(weights) if weights else 0.5
    
    async def seed_defaults(self) -> Dict[str, Any]:
        """Seed default weights to database."""
        count = 0
        for source_id, weight in DEFAULT_SOURCE_WEIGHTS.items():
            if source_id == "default":
                continue
            result = await self.db.source_weights.update_one(
                {"source_id": source_id},
                {"$setOnInsert": {
                    "source_id": source_id,
                    "weight": weight,
                    "is_default": True,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }},
                upsert=True
            )
            if result.upserted_id:
                count += 1
        
        return {"seeded": count, "total": len(DEFAULT_SOURCE_WEIGHTS) - 1}


# ═══════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ═══════════════════════════════════════════════════════════════

_manager: Optional[SourceReliabilityManager] = None


def get_source_reliability_manager(db) -> SourceReliabilityManager:
    """Get or create SourceReliabilityManager singleton."""
    global _manager
    if _manager is None:
        _manager = SourceReliabilityManager(db)
    return _manager


async def get_source_weight(db, source_id: str) -> float:
    """Quick helper to get source weight."""
    manager = get_source_reliability_manager(db)
    return await manager.get_weight(source_id)
