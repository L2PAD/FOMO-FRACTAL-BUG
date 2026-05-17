"""
Canonical Entity Resolver
==========================

Ensures all queries return the canonical entity_id, even when:
- User searches "ETH" (should return asset:ethereum)
- User searches "Ethereum" (should return asset:ethereum)
- Graph loads "eth" (should map to asset:ethereum)

This prevents duplicate nodes in the graph (ETH vs Ethereum).

Resolution order:
1. Direct match in graph_nodes
2. Alias match in entity_aliases
3. Symbol match (normalized uppercase)
4. Fuzzy match (for typos)

Key principle: ONE entity_id per real-world entity.
"""

import logging
import re
from typing import Optional, Dict, Any, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class CanonicalEntityResolver:
    """
    Resolves any entity reference to its canonical entity_id.
    
    Example:
        "ETH" -> "asset:ethereum"
        "Ethereum" -> "asset:ethereum"
        "ethereum" -> "asset:ethereum"
        "eth token" -> "asset:ethereum"
    """
    
    # Well-known crypto symbols to names mapping
    SYMBOL_MAP = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "BNB": "binance-coin",
        "XRP": "ripple",
        "ADA": "cardano",
        "AVAX": "avalanche",
        "DOT": "polkadot",
        "MATIC": "polygon",
        "LINK": "chainlink",
        "UNI": "uniswap",
        "AAVE": "aave",
        "ATOM": "cosmos",
        "ARB": "arbitrum",
        "OP": "optimism",
        "APT": "aptos",
        "SUI": "sui",
        "NEAR": "near-protocol",
        "FTM": "fantom",
        "DOGE": "dogecoin",
        "SHIB": "shiba-inu",
        "LTC": "litecoin",
    }
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.graph_nodes = db.graph_nodes
        self.entity_aliases = db.entity_aliases
    
    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """Normalize symbol to uppercase"""
        if not symbol:
            return ""
        return symbol.upper().strip()
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize name for comparison"""
        if not name:
            return ""
        normalized = name.lower().strip()
        normalized = re.sub(r'[^\w\s-]', '', normalized)
        normalized = re.sub(r'\s+', '-', normalized)
        return normalized
    
    async def resolve(
        self, 
        query: str, 
        entity_type: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        Resolve query to canonical entity_id.
        
        Returns:
            (canonical_entity_id, entity_data) or (None, None) if not found
        
        Example:
            resolve("ETH") -> ("asset:ethereum", {...})
            resolve("Ethereum") -> ("asset:ethereum", {...})
        """
        if not query:
            return None, None
        
        query_normalized = self.normalize_name(query)
        query_upper = self.normalize_symbol(query)
        
        # 1. Check if it's already a canonical entity_id (e.g., "asset:ethereum")
        if ':' in query:
            entity = await self.graph_nodes.find_one({"id": query})
            if entity:
                return query, self._format_entity(entity)
        
        # 2. Check symbol map for well-known symbols
        if query_upper in self.SYMBOL_MAP:
            canonical_name = self.SYMBOL_MAP[query_upper]
            entity_id = f"asset:{canonical_name}"
            entity = await self.graph_nodes.find_one({"id": entity_id})
            if entity:
                return entity_id, self._format_entity(entity)
        
        # 3. Direct match in graph_nodes by label (case-insensitive)
        type_filter = {"entity_type": entity_type} if entity_type else {}
        entity = await self.graph_nodes.find_one({
            "$or": [
                {"label": {"$regex": f"^{re.escape(query)}$", "$options": "i"}},
                {"entity_id": {"$regex": f"^{re.escape(query)}$", "$options": "i"}},
            ],
            **type_filter
        })
        if entity:
            return entity.get("id"), self._format_entity(entity)
        
        # 4. Check entity_aliases collection
        alias_doc = await self.entity_aliases.find_one({
            "aliases": {"$regex": f"^{re.escape(query)}$", "$options": "i"}
        })
        if alias_doc and alias_doc.get("entity_id"):
            entity_id = alias_doc["entity_id"]
            entity = await self.graph_nodes.find_one({"id": entity_id})
            if entity:
                return entity_id, self._format_entity(entity)
        
        # 5. Try by symbol field
        entity = await self.graph_nodes.find_one({
            "metadata.symbol": {"$regex": f"^{re.escape(query)}$", "$options": "i"},
            **type_filter
        })
        if entity:
            return entity.get("id"), self._format_entity(entity)
        
        # 6. Try slug match (e.g., "ethereum" matches "asset:ethereum")
        entity = await self.graph_nodes.find_one({
            "entity_id": query_normalized,
            **type_filter
        })
        if entity:
            return entity.get("id"), self._format_entity(entity)
        
        # Not found
        return None, None
    
    async def resolve_or_create(
        self,
        name: str,
        entity_type: str,
        symbol: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, Dict[str, Any], bool]:
        """
        Resolve or create entity.
        
        Returns:
            (entity_id, entity_data, was_created)
        """
        # First try to resolve
        entity_id, entity = await self.resolve(name, entity_type)
        if entity_id:
            return entity_id, entity, False
        
        # Also try to resolve by symbol if provided
        if symbol:
            entity_id, entity = await self.resolve(symbol, entity_type)
            if entity_id:
                return entity_id, entity, True  # Found by symbol
        
        # Create new entity
        entity_id = f"{entity_type}:{self.normalize_name(name)}"
        
        new_entity = {
            "id": entity_id,
            "entity_type": entity_type,
            "entity_id": self.normalize_name(name),
            "label": name,
            "metadata": metadata or {},
            "canonical": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        if symbol:
            new_entity["metadata"]["symbol"] = self.normalize_symbol(symbol)
        
        await self.graph_nodes.insert_one(new_entity)
        
        # Add aliases
        aliases = [name.lower(), self.normalize_name(name)]
        if symbol:
            aliases.append(symbol.upper())
            aliases.append(symbol.lower())
        
        await self.entity_aliases.update_one(
            {"entity_id": entity_id},
            {"$addToSet": {"aliases": {"$each": aliases}}},
            upsert=True
        )
        
        logger.info(f"[CanonicalResolver] Created new entity: {entity_id}")
        return entity_id, self._format_entity(new_entity), True
    
    async def add_alias(self, entity_id: str, alias: str) -> bool:
        """Add alias to an entity"""
        normalized = alias.lower().strip()
        
        result = await self.entity_aliases.update_one(
            {"entity_id": entity_id},
            {"$addToSet": {"aliases": normalized}},
            upsert=True
        )
        
        return result.modified_count > 0 or result.upserted_id is not None
    
    def _format_entity(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        """Format entity for API response"""
        return {
            "id": entity.get("id"),
            "entity_type": entity.get("entity_type"),
            "entity_id": entity.get("entity_id"),
            "label": entity.get("label"),
            "metadata": entity.get("metadata", {})
        }


# Import datetime for created_at
from datetime import datetime, timezone


# Singleton instance
_resolver_instance = None


def get_canonical_resolver(db: AsyncIOMotorDatabase) -> CanonicalEntityResolver:
    """Get or create canonical resolver instance"""
    global _resolver_instance
    if _resolver_instance is None:
        _resolver_instance = CanonicalEntityResolver(db)
    return _resolver_instance
