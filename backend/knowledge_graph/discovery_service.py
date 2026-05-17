"""
Entity Discovery Service

When an entity is not found in the database, this service
attempts to discover it from external sources.

External sources:
- CryptoRank
- Messari
- RootData
- Web search (fallback)
"""

import logging
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from .alias_resolver import EntityAliasResolver

logger = logging.getLogger(__name__)


class EntityDiscoveryService:
    """
    Discovers entities from external sources when not found locally.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.alias_resolver = EntityAliasResolver(db)
    
    async def discover_entity(
        self,
        query: str,
        entity_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Attempt to discover an entity from external sources.
        
        Flow:
        1. Check alias resolver first
        2. Search local database
        3. If not found, search external sources
        4. Normalize and save discovered entity
        """
        
        # Step 1: Check alias resolver
        resolved = await self.alias_resolver.resolve(query, entity_type)
        if resolved:
            # Found via alias - load from local DB
            etype, eid = resolved
            entity = await self._load_local_entity(etype, eid)
            if entity:
                return entity
        
        # Step 2: Search local database directly
        entity = await self._search_local(query, entity_type)
        if entity:
            return entity
        
        # Step 3: Search external sources
        discovered = await self._search_external(query, entity_type)
        if discovered:
            # Step 4: Normalize and save
            saved = await self._save_discovered_entity(discovered)
            return saved
        
        return None
    
    async def _load_local_entity(
        self,
        entity_type: str,
        entity_id: str
    ) -> Optional[Dict[str, Any]]:
        """Load entity from local database"""
        collection_map = {
            "project": "intel_projects",
            "fund": "intel_funds",
            "person": "intel_persons"
        }
        
        collection_name = collection_map.get(entity_type)
        if not collection_name:
            return None
        
        # Try different ID fields
        for field in ["slug", "id", "key"]:
            entity = await self.db[collection_name].find_one({field: entity_id})
            if entity:
                entity["_entity_type"] = entity_type
                entity["_entity_id"] = entity_id
                return entity
        
        return None
    
    async def _search_local(
        self,
        query: str,
        entity_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Search local database for entity"""
        normalized = self.alias_resolver.normalize_alias(query)
        
        types_to_search = [entity_type] if entity_type else ["project", "fund", "person"]
        collection_map = {
            "project": "intel_projects",
            "fund": "intel_funds",
            "person": "intel_persons"
        }
        
        for etype in types_to_search:
            collection_name = collection_map.get(etype)
            if not collection_name:
                continue
            
            # Search by name, slug, symbol
            filter_dict = {
                "$or": [
                    {"name": {"$regex": f"^{re.escape(query)}$", "$options": "i"}},
                    {"slug": {"$regex": f"^{re.escape(normalized)}$", "$options": "i"}},
                    {"symbol": {"$regex": f"^{re.escape(query)}$", "$options": "i"}}
                ]
            }
            
            entity = await self.db[collection_name].find_one(filter_dict)
            if entity:
                entity["_entity_type"] = etype
                entity["_entity_id"] = entity.get("slug") or entity.get("id") or normalized
                return entity
        
        return None
    
    async def _search_external(
        self,
        query: str,
        entity_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Search external sources for entity.
        
        In production, this would call:
        - CryptoRank API
        - Messari API
        - RootData API
        - Crunchbase API
        
        For now, we return a normalized structure for known entities
        that might not be in the database yet.
        """
        normalized = self.alias_resolver.normalize_alias(query)
        
        # Known entities that might be searched
        KNOWN_EXTERNAL = {
            "layerzero": {
                "entity_type": "project",
                "entity_id": "layerzero",
                "name": "LayerZero",
                "slug": "layerzero",
                "symbol": "ZRO",
                "category": "Infrastructure",
                "description": "Omnichain interoperability protocol",
                "source": "external_discovery"
            },
            "eigenlayer": {
                "entity_type": "project",
                "entity_id": "eigenlayer",
                "name": "EigenLayer",
                "slug": "eigenlayer",
                "symbol": "EIGEN",
                "category": "Infrastructure",
                "description": "Restaking protocol",
                "source": "external_discovery"
            },
            "celestia": {
                "entity_type": "project",
                "entity_id": "celestia",
                "name": "Celestia",
                "slug": "celestia",
                "symbol": "TIA",
                "category": "Infrastructure",
                "description": "Modular data availability network",
                "source": "external_discovery"
            },
            "jump crypto": {
                "entity_type": "fund",
                "entity_id": "jump_crypto",
                "name": "Jump Crypto",
                "slug": "jump_crypto",
                "category": "Venture Capital",
                "source": "external_discovery"
            },
            "galaxy digital": {
                "entity_type": "fund",
                "entity_id": "galaxy_digital",
                "name": "Galaxy Digital",
                "slug": "galaxy_digital",
                "category": "Venture Capital",
                "source": "external_discovery"
            },
            "su zhu": {
                "entity_type": "person",
                "entity_id": "su_zhu",
                "name": "Su Zhu",
                "slug": "su_zhu",
                "title": "Co-founder",
                "company": "Three Arrows Capital",
                "source": "external_discovery"
            },
            "kyle davies": {
                "entity_type": "person",
                "entity_id": "kyle_davies",
                "name": "Kyle Davies",
                "slug": "kyle_davies",
                "title": "Co-founder",
                "company": "Three Arrows Capital",
                "source": "external_discovery"
            }
        }
        
        # Check known external entities
        result = KNOWN_EXTERNAL.get(normalized)
        if result:
            if entity_type and result["entity_type"] != entity_type:
                return None
            return result
        
        # In production: call external APIs here
        # For now, return None to indicate not found
        logger.debug(f"[Discovery] Entity not found in external sources: {query}")
        return None
    
    async def _save_discovered_entity(
        self,
        entity_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Save discovered entity to local database"""
        entity_type = entity_data.get("entity_type")
        entity_id = entity_data.get("entity_id")
        
        if not entity_type or not entity_id:
            return entity_data
        
        collection_map = {
            "project": "intel_projects",
            "fund": "intel_funds",
            "person": "intel_persons"
        }
        
        collection_name = collection_map.get(entity_type)
        if not collection_name:
            return entity_data
        
        # Prepare document
        doc = {
            "slug": entity_id,
            "name": entity_data.get("name"),
            "symbol": entity_data.get("symbol"),
            "category": entity_data.get("category"),
            "description": entity_data.get("description"),
            "source": entity_data.get("source", "external_discovery"),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        # Remove None values
        doc = {k: v for k, v in doc.items() if v is not None}
        
        try:
            # Upsert
            await self.db[collection_name].update_one(
                {"slug": entity_id},
                {"$set": doc},
                upsert=True
            )
            
            # Add alias
            await self.alias_resolver.add_alias(
                entity_type=entity_type,
                entity_id=entity_id,
                alias=entity_data.get("name", entity_id),
                source="discovery"
            )
            
            logger.info(f"[Discovery] Saved entity: {entity_type}:{entity_id}")
            
        except Exception as e:
            logger.warning(f"[Discovery] Failed to save entity: {e}")
        
        entity_data["_entity_type"] = entity_type
        entity_data["_entity_id"] = entity_id
        return entity_data
    
    async def search_suggestions(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get search suggestions combining local + alias search.
        """
        results = []
        seen = set()
        
        # Search aliases — resolve actual entity label from graph_nodes
        alias_results = await self.alias_resolver.search_aliases(query, limit=limit)
        for item in alias_results:
            key = f"{item['entity_type']}:{item['entity_id']}"
            if key not in seen:
                seen.add(key)
                # Look up real label from graph_nodes
                full_id = item.get("full_entity_id") or key
                node = await self.db.graph_nodes.find_one(
                    {"$or": [{"id": full_id}, {"id": key}]},
                    {"_id": 0, "label": 1}
                )
                display_label = (node or {}).get("label") or item.get("alias", item["entity_id"]).title()
                results.append({
                    "id": key,
                    "label": display_label,
                    "type": item["entity_type"],
                    "entity_id": item["entity_id"],
                    "source": "alias"
                })
        
        # Search local database if not enough results
        if len(results) < limit:
            remaining = limit - len(results)
            local_results = await self._search_local_suggestions(query, remaining)
            for item in local_results:
                key = f"{item['type']}:{item['entity_id']}"
                if key not in seen:
                    seen.add(key)
                    results.append(item)
        
        return results[:limit]
    
    async def _search_local_suggestions(
        self,
        query: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Search local database for suggestions"""
        results = []
        normalized = self.alias_resolver.normalize_alias(query)
        
        collections = [
            ("intel_projects", "project"),
            ("intel_funds", "fund"),
            ("intel_persons", "person")
        ]
        
        for collection_name, entity_type in collections:
            cursor = self.db[collection_name].find({
                "$or": [
                    {"name": {"$regex": re.escape(query), "$options": "i"}},
                    {"slug": {"$regex": re.escape(normalized), "$options": "i"}}
                ]
            }).limit(limit // 3 + 1)
            
            async for doc in cursor:
                entity_id = doc.get("slug") or doc.get("id") or doc.get("key", "").split(":")[-1]
                results.append({
                    "id": f"{entity_type}:{entity_id}",
                    "label": doc.get("name", entity_id),
                    "type": entity_type,
                    "entity_id": entity_id,
                    "source": "local"
                })
        
        return results
