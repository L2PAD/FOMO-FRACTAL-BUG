"""
Entity Alias System

Provides alias resolution for entities to prevent duplicates.
Example: "a16z", "A16Z", "Andreessen Horowitz" -> fund:a16z

Collections:
- entity_aliases: Maps aliases to canonical entities
"""

import logging
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field
import uuid

logger = logging.getLogger(__name__)


def generate_id() -> str:
    return str(uuid.uuid4())[:12]


class EntityAlias(BaseModel):
    """Entity alias record"""
    id: str = Field(default_factory=generate_id)
    entity_type: str  # project, fund, person
    entity_id: str    # Canonical entity ID (e.g., fund_a16z)
    alias: str        # Original alias text
    normalized_alias: str  # Lowercase, cleaned alias for matching
    source: str = "manual"  # manual, cryptorank, messari, etc.
    confidence: float = 1.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EntityAliasResolver:
    """
    Resolves entity aliases to canonical entities.
    Prevents duplicate nodes in the graph.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.aliases_collection = db.entity_aliases
        self._cache: Dict[str, Tuple[str, str]] = {}  # normalized_alias -> (entity_type, entity_id)
    
    async def ensure_indexes(self):
        """Create required indexes"""
        await self.aliases_collection.create_index(
            "normalized_alias",
            name="idx_normalized_alias"
        )
        await self.aliases_collection.create_index(
            [("entity_type", 1), ("entity_id", 1)],
            name="idx_entity"
        )
        await self.aliases_collection.create_index(
            [("entity_type", 1), ("normalized_alias", 1)],
            unique=True,
            name="unique_type_alias"
        )
        logger.info("[AliasResolver] Indexes created")
    
    @staticmethod
    def normalize_alias(alias: str) -> str:
        """
        Normalize alias for matching.
        - Lowercase
        - Remove punctuation
        - Trim whitespace
        - Collapse multiple spaces
        """
        if not alias:
            return ""
        # Lowercase
        normalized = alias.lower()
        # Remove punctuation except spaces
        normalized = re.sub(r'[^\w\s]', '', normalized)
        # Collapse multiple spaces
        normalized = re.sub(r'\s+', ' ', normalized)
        # Trim
        return normalized.strip()
    
    async def add_alias(
        self,
        entity_type: str,
        entity_id: str,
        alias: str,
        source: str = "manual",
        confidence: float = 1.0
    ) -> bool:
        """Add a new alias for an entity"""
        normalized = self.normalize_alias(alias)
        if not normalized:
            return False
        
        try:
            record = EntityAlias(
                entity_type=entity_type,
                entity_id=entity_id,
                alias=alias,
                normalized_alias=normalized,
                source=source,
                confidence=confidence
            )
            
            await self.aliases_collection.update_one(
                {"entity_type": entity_type, "normalized_alias": normalized},
                {"$set": record.model_dump()},
                upsert=True
            )
            
            # Update cache
            self._cache[f"{entity_type}:{normalized}"] = (entity_type, entity_id)
            
            logger.debug(f"[AliasResolver] Added alias: {alias} -> {entity_type}:{entity_id}")
            return True
            
        except Exception as e:
            logger.warning(f"[AliasResolver] Failed to add alias: {e}")
            return False
    
    async def add_aliases_batch(
        self,
        entity_type: str,
        entity_id: str,
        aliases: List[str],
        source: str = "manual"
    ) -> int:
        """Add multiple aliases for an entity"""
        count = 0
        for alias in aliases:
            if await self.add_alias(entity_type, entity_id, alias, source):
                count += 1
        return count
    
    async def resolve(
        self,
        query: str,
        entity_type: Optional[str] = None
    ) -> Optional[Tuple[str, str]]:
        """
        Resolve a query to canonical entity.
        Returns (entity_type, entity_id) or None if not found.
        """
        normalized = self.normalize_alias(query)
        if not normalized:
            return None
        
        # Check cache first
        if entity_type:
            cache_key = f"{entity_type}:{normalized}"
            if cache_key in self._cache:
                return self._cache[cache_key]
        else:
            # Check all types in cache
            for etype in ["project", "fund", "person"]:
                cache_key = f"{etype}:{normalized}"
                if cache_key in self._cache:
                    return self._cache[cache_key]
        
        # Query database
        filter_dict = {"normalized_alias": normalized}
        if entity_type:
            filter_dict["entity_type"] = entity_type
        
        # Sort by confidence desc
        record = await self.aliases_collection.find_one(
            filter_dict,
            sort=[("confidence", -1)]
        )
        
        if record:
            result = (record["entity_type"], record["entity_id"])
            # Update cache
            self._cache[f"{record['entity_type']}:{normalized}"] = result
            return result
        
        return None
    
    async def resolve_or_create(
        self,
        query: str,
        entity_type: str,
        default_id: Optional[str] = None
    ) -> Tuple[str, str, bool]:
        """
        Resolve alias or create new entity.
        Returns (entity_type, entity_id, was_created).
        """
        # Try to resolve existing
        result = await self.resolve(query, entity_type)
        if result:
            return (result[0], result[1], False)
        
        # Create new entity ID
        normalized = self.normalize_alias(query)
        entity_id = default_id or normalized.replace(' ', '_')
        
        # Add alias
        await self.add_alias(entity_type, entity_id, query, source="auto")
        
        return (entity_type, entity_id, True)
    
    async def get_all_aliases(
        self,
        entity_type: str,
        entity_id: str
    ) -> List[str]:
        """Get all aliases for an entity"""
        cursor = self.aliases_collection.find({
            "entity_type": entity_type,
            "entity_id": entity_id
        })
        
        aliases = []
        async for record in cursor:
            aliases.append(record["alias"])
        
        return aliases
    
    async def search_aliases(
        self,
        query: str,
        entity_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search aliases by partial match"""
        normalized = self.normalize_alias(query)
        if not normalized:
            return []
        
        filter_dict = {
            "normalized_alias": {"$regex": f".*{re.escape(normalized)}.*"}
        }
        if entity_type:
            filter_dict["entity_type"] = entity_type
        
        cursor = self.aliases_collection.find(filter_dict).sort(
            "confidence", -1
        ).limit(limit)
        
        results = []
        async for record in cursor:
            results.append({
                "entity_type": record["entity_type"],
                "entity_id": record["entity_id"],
                "alias": record["alias"],
                "confidence": record["confidence"]
            })
        
        return results
    
    def clear_cache(self):
        """Clear alias cache"""
        self._cache.clear()


# ============================================================================
# Bootstrap common aliases
# ============================================================================

COMMON_ALIASES = {
    "fund": {
        "a16z": ["a16z", "A16Z", "Andreessen Horowitz", "A16Z Crypto", "a16z crypto", "Andreessen"],
        "paradigm": ["Paradigm", "paradigm", "Paradigm Capital"],
        "coinbase_ventures": ["Coinbase Ventures", "Coinbase", "CB Ventures"],
        "binance_labs": ["Binance Labs", "Binance", "BNB Labs"],
        "sequoia": ["Sequoia", "Sequoia Capital", "Sequoia Crypto"],
        "polychain": ["Polychain", "Polychain Capital"],
        "pantera": ["Pantera", "Pantera Capital"],
        "dragonfly": ["Dragonfly", "Dragonfly Capital"],
        "multicoin": ["Multicoin", "Multicoin Capital"],
        "framework": ["Framework", "Framework Ventures"],
        # Additional funds
        "sequoia": ["Sequoia", "Sequoia Capital", "Sequoia Crypto"],
        "galaxy": ["Galaxy", "Galaxy Digital", "Galaxy Investments"],
        "jump-crypto": ["Jump Crypto", "Jump", "Jump Trading Crypto", "Jump Capital"],
        "hack-vc": ["Hack VC", "Hack Ventures", "HackVC"],
        "animoca": ["Animoca", "Animoca Brands"],
        "spartan": ["Spartan", "Spartan Group", "Spartan Capital"],
        "delphi": ["Delphi", "Delphi Ventures", "Delphi Digital", "Delphi Labs"],
        "dcg": ["DCG", "Digital Currency Group", "Grayscale parent"],
        "placeholder": ["Placeholder", "Placeholder VC", "Placeholder Ventures"],
        "robot-ventures": ["Robot Ventures", "Robot", "Tarun Chitra Fund"],
    },
    "person": {
        "vitalik": ["Vitalik", "Vitalik Buterin", "Vitaly Buterin", "V. Buterin", "vitalik.eth"],
        "cz": ["CZ", "Changpeng Zhao", "CZ Binance"],
        "sbf": ["SBF", "Sam Bankman-Fried", "Sam Bankman Fried"],
        "balaji": ["Balaji", "Balaji Srinivasan", "Balaji S"],
        "marc": ["Marc Andreessen", "Marc", "a]pm"],
        "brian_armstrong": ["Brian Armstrong", "Brian", "Armstrong"],
    },
    "project": {
        "ethereum": ["Ethereum", "ETH", "Ether", "ethereum"],
        "bitcoin": ["Bitcoin", "BTC", "bitcoin"],
        "solana": ["Solana", "SOL", "solana"],
        "arbitrum": ["Arbitrum", "ARB", "Arbitrum One", "Arbitrum Network"],
        "optimism": ["Optimism", "OP", "Optimism Network"],
        "polygon": ["Polygon", "MATIC", "Polygon Network", "Matic Network"],
        "uniswap": ["Uniswap", "UNI", "Uniswap Protocol"],
        "aave": ["Aave", "AAVE", "Aave Protocol"],
        "compound": ["Compound", "COMP", "Compound Finance"],
        "layerzero": ["LayerZero", "Layer Zero", "L0", "layerzero"],
    }
}


async def bootstrap_common_aliases(db: AsyncIOMotorDatabase):
    """Bootstrap common entity aliases"""
    resolver = EntityAliasResolver(db)
    await resolver.ensure_indexes()
    
    total = 0
    for entity_type, entities in COMMON_ALIASES.items():
        for entity_id, aliases in entities.items():
            count = await resolver.add_aliases_batch(
                entity_type=entity_type,
                entity_id=entity_id,
                aliases=aliases,
                source="bootstrap"
            )
            total += count
    
    logger.info(f"[AliasResolver] Bootstrapped {total} common aliases")
    return total
