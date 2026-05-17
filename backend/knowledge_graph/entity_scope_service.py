"""
Entity Scope Layer
==================

Prevents identity drift by assigning scope to entities.

Problem solved:
- "EigenLayer" can mean: protocol, ecosystem, restaking technology
- "Arbitrum" can mean: chain, foundation, DAO, token
- Without scope, one entity absorbs multiple meanings → broken analytics

Scopes:
- protocol: The core project/protocol
- token: Asset/cryptocurrency
- organization: Company, foundation, DAO
- ecosystem: Broader ecosystem around a project
- person: Individual
- narrative: Market narrative (AI, RWA, etc.)
- technology: Specific technology/mechanism
- product: Specific product within ecosystem

Scope resolution:
1. Provider type mapping (CryptoRank → project, CoinGecko → token)
2. Keyword extraction (token, ecosystem, foundation, DAO)
3. Context analysis (funding/investment → organization)
"""

import logging
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


# Available scopes
SCOPES = [
    "protocol",      # Core project/protocol
    "token",         # Asset/cryptocurrency
    "organization",  # Company, foundation, DAO
    "ecosystem",     # Broader ecosystem
    "person",        # Individual
    "narrative",     # Market narrative
    "technology",    # Specific technology
    "product"        # Product within ecosystem
]

# Provider to scope mapping
PROVIDER_SCOPE_MAP = {
    "cryptorank_projects": "protocol",
    "cryptorank_funds": "organization",
    "coingecko_coins": "token",
    "rootdata_projects": "protocol",
    "rootdata_organizations": "organization"
}

# Keyword patterns for scope detection
SCOPE_KEYWORDS = {
    "token": [
        r"\btoken\b", r"\bcoin\b", r"\basset\b", r"\$[A-Z]+\b",
        r"\bstaking\b", r"\brewards\b"
    ],
    "ecosystem": [
        r"\becosystem\b", r"\bnetwork\b", r"\bchain\b"
    ],
    "organization": [
        r"\bfoundation\b", r"\bdao\b", r"\blabs\b", r"\binc\b",
        r"\bcorp\b", r"\bventures\b", r"\bcapital\b", r"\bfund\b"
    ],
    "technology": [
        r"\brestaking\b", r"\brollup\b", r"\bbridge\b", r"\boracle\b",
        r"\blayer\s*2\b", r"\bl2\b", r"\bzk\b", r"\bproof\b"
    ],
    "narrative": [
        r"\bai\b", r"\brwa\b", r"\bdepin\b", r"\bgaming\b",
        r"\bdefi\b", r"\bnft\b", r"\bmeme\b"
    ],
    "product": [
        r"\bapp\b", r"\bwallet\b", r"\bexchange\b", r"\bdex\b",
        r"\bmarketplace\b", r"\bplatform\b"
    ]
}

# Context patterns for scope detection
CONTEXT_SCOPE_MAP = {
    "invested": "organization",
    "funding": "organization",
    "raised": "organization",
    "round": "organization",
    "price": "token",
    "trading": "token",
    "market cap": "token",
    "launched": "protocol",
    "mainnet": "protocol",
    "testnet": "protocol"
}


class EntityScopeService:
    """
    Assigns and manages entity scopes to prevent identity drift.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.graph_nodes = db.graph_nodes
        self.entity_scopes = db.entity_scopes
    
    async def ensure_indexes(self):
        """Create indexes"""
        await self.entity_scopes.create_index("entity_id", unique=True)
        await self.entity_scopes.create_index("scope")
        await self.entity_scopes.create_index("entity_type")
        
        logger.info("[EntityScope] Indexes created")
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize name for matching"""
        if not name:
            return ""
        return name.lower().strip()
    
    def detect_scope_from_name(self, name: str) -> Optional[str]:
        """Detect scope from entity name using keywords"""
        name_lower = self.normalize_name(name)
        
        for scope, patterns in SCOPE_KEYWORDS.items():
            for pattern in patterns:
                if re.search(pattern, name_lower, re.IGNORECASE):
                    return scope
        
        return None
    
    def detect_scope_from_context(self, context: str) -> Optional[str]:
        """Detect scope from context text"""
        if not context:
            return None
        
        context_lower = context.lower()
        
        for keyword, scope in CONTEXT_SCOPE_MAP.items():
            if keyword in context_lower:
                return scope
        
        return None
    
    def detect_scope_from_provider(self, provider_source: str) -> Optional[str]:
        """Detect scope from provider source"""
        return PROVIDER_SCOPE_MAP.get(provider_source)
    
    async def resolve_scope(
        self,
        entity_id: str,
        entity_name: str,
        entity_type: str,
        provider_source: str = None,
        context: str = None
    ) -> Dict[str, Any]:
        """
        Resolve entity scope using multiple signals.
        
        Priority:
        1. Provider type (most reliable)
        2. Name keywords
        3. Context
        4. Default by entity type
        """
        scope = None
        confidence = 0.0
        source = None
        
        # 1. Try provider source
        if provider_source:
            scope = self.detect_scope_from_provider(provider_source)
            if scope:
                confidence = 0.95
                source = "provider"
        
        # 2. Try name keywords
        if not scope:
            scope = self.detect_scope_from_name(entity_name)
            if scope:
                confidence = 0.80
                source = "name_keyword"
        
        # 3. Try context
        if not scope and context:
            scope = self.detect_scope_from_context(context)
            if scope:
                confidence = 0.70
                source = "context"
        
        # 4. Default by entity type
        if not scope:
            type_defaults = {
                "project": "protocol",
                "fund": "organization",
                "person": "person",
                "token": "token",
                "exchange": "organization"
            }
            scope = type_defaults.get(entity_type, "protocol")
            confidence = 0.50
            source = "type_default"
        
        return {
            "entity_id": entity_id,
            "scope": scope,
            "confidence": confidence,
            "source": source
        }
    
    async def assign_scope(
        self,
        entity_id: str,
        scope: str,
        confidence: float = 1.0,
        source: str = "manual"
    ) -> bool:
        """Assign scope to entity"""
        if scope not in SCOPES:
            return False
        
        now = datetime.now(timezone.utc)
        
        # Parse entity_id
        parts = entity_id.split(":")
        entity_type = parts[0] if len(parts) >= 2 else "unknown"
        
        record = {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "scope": scope,
            "confidence": confidence,
            "source": source,
            "updated_at": now
        }
        
        try:
            await self.entity_scopes.update_one(
                {"entity_id": entity_id},
                {"$set": record},
                upsert=True
            )
            
            # Also update graph_nodes metadata
            await self.graph_nodes.update_one(
                {"id": entity_id},
                {"$set": {"metadata.scope": scope, "metadata.scope_confidence": confidence}}
            )
            
            logger.debug(f"[EntityScope] Assigned {scope} to {entity_id}")
            return True
        except Exception as e:
            logger.error(f"[EntityScope] Failed to assign scope: {e}")
            return False
    
    async def get_scope(self, entity_id: str) -> Optional[Dict]:
        """Get scope for entity"""
        record = await self.entity_scopes.find_one(
            {"entity_id": entity_id},
            {"_id": 0}
        )
        return record
    
    async def resolve_and_assign(
        self,
        entity_id: str,
        entity_name: str,
        entity_type: str,
        provider_source: str = None,
        context: str = None
    ) -> Dict[str, Any]:
        """Resolve scope and assign to entity"""
        resolution = await self.resolve_scope(
            entity_id, entity_name, entity_type, provider_source, context
        )
        
        assigned = await self.assign_scope(
            entity_id,
            resolution["scope"],
            resolution["confidence"],
            resolution["source"]
        )
        
        resolution["assigned"] = assigned
        return resolution
    
    async def batch_assign_scopes(self, limit: int = 100) -> Dict[str, Any]:
        """Assign scopes to entities without scope"""
        # Find entities without scope
        cursor = self.graph_nodes.find(
            {"metadata.scope": {"$exists": False}},
            {"id": 1, "entity_type": 1, "label": 1}
        ).limit(limit)
        
        assigned = 0
        
        async for node in cursor:
            entity_id = node.get("id")
            entity_type = node.get("entity_type") or entity_id.split(":")[0] if entity_id else "unknown"
            entity_name = node.get("label", "")
            
            result = await self.resolve_and_assign(
                entity_id, entity_name, entity_type
            )
            
            if result.get("assigned"):
                assigned += 1
        
        logger.info(f"[EntityScope] Batch assigned {assigned} scopes")
        return {"assigned": assigned}
    
    async def get_entities_by_scope(self, scope: str, limit: int = 50) -> List[Dict]:
        """Get entities by scope"""
        if scope not in SCOPES:
            return []
        
        cursor = self.entity_scopes.find(
            {"scope": scope},
            {"_id": 0}
        ).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_scope_distribution(self) -> Dict[str, int]:
        """Get distribution of scopes"""
        pipeline = [
            {"$group": {"_id": "$scope", "count": {"$sum": 1}}}
        ]
        
        results = await self.entity_scopes.aggregate(pipeline).to_list(20)
        return {r["_id"]: r["count"] for r in results if r["_id"]}
    
    async def detect_identity_drift(self) -> Dict[str, Any]:
        """
        Detect potential identity drift.
        
        Signs of drift:
        - Entity with multiple different scopes in aliases
        - Entity connected to both token and protocol edges
        - Entity name contains multiple scope keywords
        """
        drift_candidates = []
        
        # Find entities with name containing multiple scope keywords
        cursor = self.graph_nodes.find({}, {"id": 1, "label": 1}).limit(500)
        
        async for node in cursor:
            label = node.get("label", "")
            label_lower = label.lower()
            
            scopes_found = []
            for scope, patterns in SCOPE_KEYWORDS.items():
                for pattern in patterns:
                    if re.search(pattern, label_lower, re.IGNORECASE):
                        if scope not in scopes_found:
                            scopes_found.append(scope)
                        break
            
            if len(scopes_found) >= 2:
                drift_candidates.append({
                    "entity_id": node.get("id"),
                    "label": label,
                    "detected_scopes": scopes_found,
                    "risk": "multiple_scope_keywords"
                })
        
        return {
            "drift_candidates": drift_candidates[:20],
            "count": len(drift_candidates)
        }
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get scope statistics"""
        total_scoped = await self.entity_scopes.count_documents({})
        total_nodes = await self.graph_nodes.count_documents({})
        
        distribution = await self.get_scope_distribution()
        
        return {
            "total_entities_with_scope": total_scoped,
            "total_entities": total_nodes,
            "coverage": round(total_scoped / total_nodes, 3) if total_nodes > 0 else 0,
            "distribution": distribution
        }


# Singleton
_scope_service: Optional[EntityScopeService] = None


def get_entity_scope_service(db: AsyncIOMotorDatabase = None) -> EntityScopeService:
    """Get or create entity scope service"""
    global _scope_service
    if db is not None:
        _scope_service = EntityScopeService(db)
    return _scope_service
