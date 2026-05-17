"""
Entity Intelligence Engine

Решает главную проблему данных:
LayerZero / Layer Zero / ZRO / LayerZero Labs → entity_id = "layerzero"

Компоненты:
- Entity Resolver (поиск существующей сущности)
- Entity Creator (создание новой)
- Alias Learning (обучение новым названиям)
- Entity Merge (объединение дубликатов)
"""

import hashlib
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Попробуем импортировать rapidfuzz, если нет - используем простой алгоритм
try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False
    logger.warning("rapidfuzz not installed, using simple fuzzy matching")


FUZZ_THRESHOLD = 85


def simple_ratio(s1: str, s2: str) -> float:
    """Simple Levenshtein-like ratio without external deps"""
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 100.0
    
    # Simple character overlap ratio
    set1, set2 = set(s1), set(s2)
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    if union == 0:
        return 0.0
    
    jaccard = intersection / union * 100
    
    # Length similarity bonus
    len_ratio = min(len(s1), len(s2)) / max(len(s1), len(s2)) * 100
    
    return (jaccard + len_ratio) / 2


def fuzzy_ratio(s1: str, s2: str) -> float:
    """Get fuzzy match ratio"""
    if HAS_RAPIDFUZZ:
        return fuzz.ratio(s1, s2)
    return simple_ratio(s1, s2)


def normalize_name(name: str) -> str:
    """Normalize entity name for matching"""
    if not name:
        return ""
    
    # Lowercase
    name = name.lower()
    
    # Remove common suffixes
    suffixes = [" protocol", " labs", " network", " finance", " dao", " token"]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    
    # Remove special chars, keep only alphanumeric and spaces
    name = re.sub(r'[^a-z0-9\s]', '', name)
    
    # Collapse whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name


def generate_entity_id(name: str) -> str:
    """Generate canonical entity_id from name"""
    normalized = normalize_name(name)
    # Remove all spaces for ID
    return normalized.replace(' ', '')


@dataclass
class EntityMatch:
    """Result of entity matching"""
    entity_id: str
    name: str
    confidence: float
    match_type: str  # exact, alias, fuzzy, symbol, new


class EntityIntelligenceEngine:
    """
    Main entity resolution engine.
    
    Usage:
        engine = EntityIntelligenceEngine(db)
        entity_id = await engine.resolve("LayerZero Labs", symbol="ZRO")
    """
    
    def __init__(self, db):
        self.db = db
        self._cache: Dict[str, str] = {}  # alias -> entity_id cache
    
    async def _init_collections(self):
        """Ensure collections exist"""
        # Create indexes
        try:
            await self.db.intel_entities.create_index("entity_id", unique=True)
            await self.db.intel_entities.create_index("symbol")
            await self.db.intel_entity_aliases.create_index("alias")
            await self.db.intel_entity_aliases.create_index("entity_id")
        except Exception as e:
            logger.debug(f"Index creation skipped: {e}")
    
    async def resolve(self, name: str, symbol: Optional[str] = None, source: Optional[str] = None) -> EntityMatch:
        """
        Resolve name to canonical entity.
        
        1. Check exact alias match
        2. Check symbol match
        3. Check fuzzy match
        4. Create new entity if not found
        """
        if not name:
            return EntityMatch("unknown", "Unknown", 0.0, "empty")
        
        normalized = normalize_name(name)
        
        # 1. Check cache first
        if normalized in self._cache:
            entity_id = self._cache[normalized]
            entity = await self.db.intel_entities.find_one({"entity_id": entity_id})
            if entity:
                return EntityMatch(entity_id, entity.get("name", name), 1.0, "cache")
        
        # 2. Check exact alias
        alias_doc = await self.db.intel_entity_aliases.find_one({"alias": normalized})
        if alias_doc:
            entity_id = alias_doc["entity_id"]
            self._cache[normalized] = entity_id
            entity = await self.db.intel_entities.find_one({"entity_id": entity_id})
            return EntityMatch(
                entity_id, 
                entity.get("name", name) if entity else name,
                alias_doc.get("confidence", 1.0),
                "alias"
            )
        
        # 3. Check symbol match
        if symbol:
            symbol_upper = symbol.upper()
            entity = await self.db.intel_entities.find_one({"symbol": symbol_upper})
            if entity:
                entity_id = entity["entity_id"]
                # Learn this alias
                await self._learn_alias(entity_id, normalized, 0.85)
                return EntityMatch(entity_id, entity["name"], 0.9, "symbol")
        
        # 4. Fuzzy match against existing entities
        best_match = await self._fuzzy_search(normalized)
        if best_match and best_match[1] >= FUZZ_THRESHOLD:
            entity_id, score, entity = best_match
            # Learn this alias if score is high enough
            if score >= 90:
                await self._learn_alias(entity_id, normalized, score / 100)
            return EntityMatch(entity_id, entity["name"], score / 100, "fuzzy")
        
        # 5. Create new entity
        entity_id = await self._create_entity(name, symbol, source)
        return EntityMatch(entity_id, name, 1.0, "new")
    
    async def _fuzzy_search(self, normalized: str) -> Optional[Tuple[str, float, Dict]]:
        """Search for fuzzy match in existing entities"""
        cursor = self.db.intel_entities.find({})
        
        best_score = 0.0
        best_entity = None
        
        async for entity in cursor:
            entity_name = normalize_name(entity.get("name", ""))
            score = fuzzy_ratio(normalized, entity_name)
            
            if score > best_score:
                best_score = score
                best_entity = entity
            
            # Also check aliases
            for alias in entity.get("aliases", []):
                alias_norm = normalize_name(alias)
                alias_score = fuzzy_ratio(normalized, alias_norm)
                if alias_score > best_score:
                    best_score = alias_score
                    best_entity = entity
        
        if best_entity and best_score >= FUZZ_THRESHOLD:
            return (best_entity["entity_id"], best_score, best_entity)
        
        return None
    
    async def _create_entity(self, name: str, symbol: Optional[str], source: Optional[str]) -> str:
        """Create new entity"""
        entity_id = generate_entity_id(name)
        normalized = normalize_name(name)
        
        entity = {
            "entity_id": entity_id,
            "name": name,
            "symbol": symbol.upper() if symbol else None,
            "type": "project",
            "aliases": [normalized] if normalized != entity_id else [],
            "sources": [source] if source else [],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            await self.db.intel_entities.insert_one(entity)
        except Exception as e:
            # Might already exist
            logger.debug(f"Entity creation skipped: {e}")
        
        # Add alias
        await self._learn_alias(entity_id, normalized, 1.0)
        
        self._cache[normalized] = entity_id
        
        logger.info(f"[EntityEngine] Created new entity: {entity_id} ({name})")
        return entity_id
    
    async def _learn_alias(self, entity_id: str, alias: str, confidence: float):
        """Learn new alias for entity"""
        if not alias:
            return
        
        try:
            await self.db.intel_entity_aliases.update_one(
                {"alias": alias},
                {"$set": {
                    "alias": alias,
                    "entity_id": entity_id,
                    "confidence": confidence,
                    "learned_at": datetime.now(timezone.utc).isoformat()
                }},
                upsert=True
            )
            self._cache[alias] = entity_id
        except Exception as e:
            logger.debug(f"Alias learning failed: {e}")
    
    async def merge_entities(self, source_id: str, target_id: str) -> Dict[str, Any]:
        """
        Merge source entity into target.
        All aliases and references point to target.
        """
        # Update all aliases
        result = await self.db.intel_entity_aliases.update_many(
            {"entity_id": source_id},
            {"$set": {"entity_id": target_id}}
        )
        
        # Get source entity for its aliases
        source = await self.db.intel_entities.find_one({"entity_id": source_id})
        if source:
            # Add source aliases to target
            await self.db.intel_entities.update_one(
                {"entity_id": target_id},
                {"$addToSet": {"aliases": {"$each": source.get("aliases", [])}}}
            )
        
        # Delete source entity
        await self.db.intel_entities.delete_one({"entity_id": source_id})
        
        # Clear cache
        self._cache = {k: v for k, v in self._cache.items() if v != source_id}
        
        logger.info(f"[EntityEngine] Merged {source_id} into {target_id}")
        
        return {
            "merged": True,
            "source": source_id,
            "target": target_id,
            "aliases_updated": result.modified_count
        }
    
    async def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get entity by ID"""
        return await self.db.intel_entities.find_one({"entity_id": entity_id})
    
    async def search_entities(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search entities by name"""
        normalized = normalize_name(query)
        
        # First try exact prefix
        cursor = self.db.intel_entities.find({
            "entity_id": {"$regex": f"^{normalized[:5]}", "$options": "i"}
        }).limit(limit)
        
        results = await cursor.to_list(limit)
        
        # If not enough, do fuzzy search
        if len(results) < limit:
            cursor = self.db.intel_entities.find({}).limit(200)
            all_entities = await cursor.to_list(200)
            
            scored = []
            for e in all_entities:
                if e["entity_id"] in [r["entity_id"] for r in results]:
                    continue
                score = fuzzy_ratio(normalized, normalize_name(e.get("name", "")))
                if score >= 50:
                    scored.append((score, e))
            
            scored.sort(key=lambda x: x[0], reverse=True)
            results.extend([e for _, e in scored[:limit - len(results)]])
        
        return results
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get entity engine statistics"""
        entities_count = await self.db.intel_entities.count_documents({})
        aliases_count = await self.db.intel_entity_aliases.count_documents({})
        
        return {
            "entities": entities_count,
            "aliases": aliases_count,
            "cache_size": len(self._cache)
        }


# Singleton instance
entity_engine: Optional[EntityIntelligenceEngine] = None


def init_entity_engine(db) -> EntityIntelligenceEngine:
    """Initialize entity engine"""
    global entity_engine
    entity_engine = EntityIntelligenceEngine(db)
    return entity_engine
