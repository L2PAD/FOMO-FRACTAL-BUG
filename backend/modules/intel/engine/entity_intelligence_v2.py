"""
Entity Intelligence Engine

Core system for entity resolution, identity merging, and unified API.
Uses entity_id as primary key, symbol/slug/address as access indexes.

Architecture:
- entity_id = internal UUID (ent_xxx)
- symbol/slug/address → entity_index → entity_id → entity
- One entity can have multiple aliases, keys, contracts
"""

import re
import hashlib
import uuid
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class EntityType(Enum):
    TOKEN = "token"
    PROJECT = "project"
    FUND = "fund"
    EXCHANGE = "exchange"
    LAUNCHPAD = "launchpad"
    INVESTOR = "investor"


@dataclass
class IntelEntity:
    """Canonical entity representation"""
    entity_id: str
    type: EntityType
    
    # Canonical identity
    name: str
    symbol: Optional[str] = None
    chain: Optional[str] = None
    
    # All known aliases
    aliases: List[str] = field(default_factory=list)
    
    # External keys for cross-referencing
    keys: Dict[str, str] = field(default_factory=dict)
    # keys = {coingecko: "arbitrum", cryptorank: "arb-arbitrum", dropstab: "arbitrum"}
    
    # Contract addresses
    contracts: List[Dict[str, str]] = field(default_factory=list)
    # contracts = [{chain: "ethereum", address: "0x..."}]
    
    # Links
    website: Optional[str] = None
    twitter: Optional[str] = None
    github: Optional[str] = None
    telegram: Optional[str] = None
    
    # Categories/tags
    categories: List[str] = field(default_factory=list)
    
    # Confidence and provenance
    confidence: float = 0.8
    provenance: Dict[str, List[str]] = field(default_factory=dict)
    # provenance = {name: ["cryptorank", "coingecko"], symbol: ["cryptorank"]}
    
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


def generate_entity_id(name: str, symbol: str = None) -> str:
    """Generate unique entity_id"""
    base = f"{name}_{symbol or ''}"
    slug = re.sub(r'[^a-z0-9]', '', base.lower())[:20]
    short_hash = hashlib.md5(base.encode()).hexdigest()[:6]
    return f"ent_{slug}_{short_hash}"


def normalize_key(s: str) -> str:
    """Normalize string for index lookup"""
    if not s:
        return ""
    # Lowercase, remove extra spaces, strip
    s = re.sub(r'\s+', ' ', s.strip().lower())
    return s


def extract_domain(url: str) -> str:
    """Extract domain from URL"""
    if not url:
        return ""
    url = url.lower().replace("https://", "").replace("http://", "")
    url = url.replace("www.", "")
    return url.split("/")[0].split("?")[0]


class EntityResolver:
    """
    Resolves various identifiers to canonical entity_id.
    
    Supports:
    - Symbol (BTC, ETH, ARB)
    - Name (Bitcoin, Ethereum, Arbitrum)
    - Slug (bitcoin, ethereum, arbitrum)
    - Contract address (0x...)
    - External keys (coingecko:bitcoin, cryptorank:btc)
    """
    
    def __init__(self, db=None):
        self.db = db
        self._cache: Dict[str, str] = {}
    
    async def resolve(self, query: str) -> Optional[str]:
        """
        Resolve any identifier to entity_id.
        
        Returns entity_id or None if not found.
        """
        if not query:
            return None
        
        key = normalize_key(query)
        
        # Check cache
        if key in self._cache:
            return self._cache[key]
        
        # Check entity_index
        if self.db is not None:
            index_doc = await self.db.entity_index.find_one({"key": key})
            if index_doc:
                entity_id = index_doc["entity_id"]
                self._cache[key] = entity_id
                return entity_id
            
            # Try prefix match for external keys (coingecko:xxx)
            if ":" in query:
                source, source_key = query.split(":", 1)
                entity = await self.db.cur_entities.find_one(
                    {f"keys.{source}": source_key.lower()},
                    {"entity_id": 1}
                )
                if entity:
                    self._cache[key] = entity["entity_id"]
                    return entity["entity_id"]
        
        return None
    
    async def resolve_or_create(
        self, 
        name: str,
        symbol: str = None,
        source: str = None,
        source_key: str = None,
        entity_type: EntityType = EntityType.TOKEN
    ) -> str:
        """
        Resolve to existing entity or create new one.
        
        Returns entity_id.
        """
        # Try to resolve first
        for query in [symbol, name, source_key]:
            if query:
                entity_id = await self.resolve(query)
                if entity_id:
                    return entity_id
        
        # Create new entity
        entity_id = generate_entity_id(name, symbol)
        
        if self.db is not None:
            entity = {
                "entity_id": entity_id,
                "type": entity_type.value,
                "canonical": {
                    "name": name,
                    "symbol": symbol
                },
                "aliases": [name],
                "keys": {},
                "contracts": [],
                "links": {},
                "categories": [],
                "confidence": 0.5,
                "provenance": {"name": [source] if source else []},
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            if symbol:
                entity["aliases"].append(symbol)
            if source and source_key:
                entity["keys"][source] = source_key
            
            await self.db.cur_entities.insert_one(entity)
            
            # Add to index
            await self._index_entity(entity_id, name, symbol, source_key)
        
        return entity_id
    
    async def _index_entity(
        self, 
        entity_id: str, 
        name: str, 
        symbol: str = None,
        source_key: str = None
    ):
        """Add entity to lookup index"""
        if self.db is None:
            return
        
        keys_to_index = []
        
        if name:
            keys_to_index.append(normalize_key(name))
        if symbol:
            keys_to_index.append(normalize_key(symbol))
        if source_key:
            keys_to_index.append(normalize_key(source_key))
        
        for key in set(keys_to_index):
            if key:
                await self.db.entity_index.update_one(
                    {"key": key},
                    {"$set": {"key": key, "entity_id": entity_id}},
                    upsert=True
                )
    
    def clear_cache(self):
        """Clear resolution cache"""
        self._cache.clear()


class EntityMerger:
    """
    Merges duplicate entities based on matching criteria.
    
    Match scoring:
    - Exact key match (coingecko, cryptorank): +1.0
    - Same website domain: +0.6
    - Same twitter handle: +0.7
    - Symbol match: +0.35
    - Name similarity: +0.45 * similarity
    
    Merge threshold: score >= 1.2
    """
    
    def __init__(self, db=None):
        self.db = db
    
    def calculate_match_score(
        self, 
        entity_a: Dict, 
        entity_b: Dict
    ) -> Tuple[float, List[str]]:
        """
        Calculate match score between two entities.
        
        Returns (score, reasons).
        """
        score = 0.0
        reasons = []
        
        # Strong key matches
        keys_a = entity_a.get("keys", {})
        keys_b = entity_b.get("keys", {})
        
        for source in ["coingecko", "cryptorank", "dropstab", "cmc"]:
            ka = keys_a.get(source)
            kb = keys_b.get(source)
            if ka and kb and ka == kb:
                score += 1.0
                reasons.append(f"key_match:{source}")
        
        # Website domain
        canon_a = entity_a.get("canonical", {})
        canon_b = entity_b.get("canonical", {})
        links_a = entity_a.get("links", {})
        links_b = entity_b.get("links", {})
        
        website_a = links_a.get("website") or canon_a.get("website")
        website_b = links_b.get("website") or canon_b.get("website")
        
        if website_a and website_b:
            domain_a = extract_domain(website_a)
            domain_b = extract_domain(website_b)
            if domain_a and domain_b and domain_a == domain_b:
                score += 0.6
                reasons.append("website_domain")
        
        # Twitter handle
        twitter_a = normalize_key(links_a.get("twitter", ""))
        twitter_b = normalize_key(links_b.get("twitter", ""))
        
        if twitter_a and twitter_b and twitter_a == twitter_b:
            score += 0.7
            reasons.append("twitter_match")
        
        # Symbol match
        symbol_a = normalize_key(canon_a.get("symbol", ""))
        symbol_b = normalize_key(canon_b.get("symbol", ""))
        
        if symbol_a and symbol_b and symbol_a == symbol_b:
            score += 0.35
            reasons.append("symbol_match")
        
        # Name similarity
        name_a = normalize_key(canon_a.get("name", ""))
        name_b = normalize_key(canon_b.get("name", ""))
        
        if name_a and name_b:
            # Simple similarity (can use rapidfuzz for better results)
            if name_a == name_b:
                similarity = 1.0
            elif name_a in name_b or name_b in name_a:
                similarity = 0.8
            else:
                # Jaccard-like similarity
                set_a = set(name_a.split())
                set_b = set(name_b.split())
                if set_a and set_b:
                    similarity = len(set_a & set_b) / len(set_a | set_b)
                else:
                    similarity = 0
            
            score += 0.45 * similarity
            reasons.append(f"name_similarity:{similarity:.2f}")
        
        return score, reasons
    
    async def find_merge_candidates(
        self, 
        entity: Dict,
        threshold: float = 0.85
    ) -> List[Dict]:
        """
        Find entities that might be duplicates of the given entity.
        """
        if self.db is None:
            return []
        
        candidates = []
        
        # Search by symbol
        symbol = (entity.get("canonical", {}).get("symbol") or "").upper()
        if symbol:
            cursor = self.db.cur_entities.find(
                {
                    "canonical.symbol": symbol,
                    "entity_id": {"$ne": entity.get("entity_id")}
                },
                {"_id": 0}
            ).limit(10)
            
            async for doc in cursor:
                score, reasons = self.calculate_match_score(entity, doc)
                if score >= threshold:
                    candidates.append({
                        "entity": doc,
                        "score": score,
                        "reasons": reasons
                    })
        
        # Search by name
        name = (entity.get("canonical", {}).get("name") or "")
        if name:
            cursor = self.db.cur_entities.find(
                {
                    "canonical.name": {"$regex": name[:10], "$options": "i"},
                    "entity_id": {"$ne": entity.get("entity_id")}
                },
                {"_id": 0}
            ).limit(20)
            
            async for doc in cursor:
                score, reasons = self.calculate_match_score(entity, doc)
                if score >= threshold:
                    # Avoid duplicates
                    if not any(c["entity"]["entity_id"] == doc["entity_id"] for c in candidates):
                        candidates.append({
                            "entity": doc,
                            "score": score,
                            "reasons": reasons
                        })
        
        return sorted(candidates, key=lambda x: -x["score"])
    
    async def merge_entities(
        self, 
        primary_id: str, 
        secondary_id: str
    ) -> Dict[str, Any]:
        """
        Merge secondary entity into primary entity.
        
        - Combines aliases
        - Merges keys
        - Updates all events to point to primary
        - Deletes secondary
        """
        if self.db is None:
            return {"error": "No database"}
        
        primary = await self.db.cur_entities.find_one({"entity_id": primary_id})
        secondary = await self.db.cur_entities.find_one({"entity_id": secondary_id})
        
        if not primary or not secondary:
            return {"error": "Entity not found"}
        
        # Merge aliases
        merged_aliases = list(set(
            primary.get("aliases", []) + 
            secondary.get("aliases", [])
        ))
        
        # Merge keys
        merged_keys = {**secondary.get("keys", {}), **primary.get("keys", {})}
        
        # Merge contracts
        merged_contracts = primary.get("contracts", []) + secondary.get("contracts", [])
        
        # Merge categories
        merged_categories = list(set(
            primary.get("categories", []) + 
            secondary.get("categories", [])
        ))
        
        # Update primary
        await self.db.cur_entities.update_one(
            {"entity_id": primary_id},
            {
                "$set": {
                    "aliases": merged_aliases,
                    "keys": merged_keys,
                    "contracts": merged_contracts,
                    "categories": merged_categories,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        # Update all events pointing to secondary
        event_result = await self.db.cur_events.update_many(
            {"entity_id": secondary_id},
            {"$set": {"entity_id": primary_id}}
        )
        
        # Update entity_index
        await self.db.entity_index.update_many(
            {"entity_id": secondary_id},
            {"$set": {"entity_id": primary_id}}
        )
        
        # Delete secondary
        await self.db.cur_entities.delete_one({"entity_id": secondary_id})
        
        return {
            "merged": True,
            "primary_id": primary_id,
            "secondary_id": secondary_id,
            "events_updated": event_result.modified_count
        }


class EntityIntelligenceEngine:
    """
    Main Entity Intelligence Engine.
    
    Provides:
    - Entity resolution (any identifier → entity_id)
    - Entity profiles (full entity data + events)
    - Entity timeline (chronological events)
    - Entity merging (duplicate detection + resolution)
    """
    
    def __init__(self, db=None):
        self.db = db
        self.resolver = EntityResolver(db)
        self.merger = EntityMerger(db)
    
    async def get_entity(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Get entity by any identifier.
        
        Query can be: symbol, name, slug, address, external key
        """
        entity_id = await self.resolver.resolve(query)
        
        if not entity_id:
            return None
        
        if self.db is None:
            return {"entity_id": entity_id}
        
        entity = await self.db.cur_entities.find_one(
            {"entity_id": entity_id},
            {"_id": 0}
        )
        
        return entity
    
    async def get_entity_profile(self, query: str) -> Dict[str, Any]:
        """
        Get full entity profile with event counts.
        """
        entity = await self.get_entity(query)
        
        if not entity:
            return {"error": "Entity not found", "query": query}
        
        entity_id = entity["entity_id"]
        
        # Get event counts
        event_counts = {}
        if self.db is not None:
            pipeline = [
                {"$match": {"entity_id": entity_id}},
                {"$group": {"_id": "$type", "count": {"$sum": 1}}}
            ]
            cursor = self.db.cur_events.aggregate(pipeline)
            event_counts = {doc["_id"]: doc["count"] async for doc in cursor}
        
        return {
            "entity": entity,
            "event_counts": event_counts,
            "total_events": sum(event_counts.values())
        }
    
    async def get_entity_timeline(
        self, 
        query: str,
        event_types: List[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get chronological event timeline for entity.
        """
        entity = await self.get_entity(query)
        
        if not entity:
            return {"error": "Entity not found", "query": query}
        
        entity_id = entity["entity_id"]
        
        if self.db is None:
            return {"entity": entity, "timeline": []}
        
        match_query = {"entity_id": entity_id}
        if event_types:
            match_query["type"] = {"$in": event_types}
        
        cursor = self.db.cur_events.find(
            match_query,
            {"_id": 0}
        ).sort("ts", 1).limit(limit)
        
        events = await cursor.to_list(limit)
        
        return {
            "entity": entity,
            "timeline": events,
            "count": len(events)
        }
    
    async def get_entity_events(
        self, 
        query: str,
        event_type: str = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Get events for entity, optionally filtered by type.
        """
        entity = await self.get_entity(query)
        
        if not entity:
            return {"error": "Entity not found", "query": query}
        
        entity_id = entity["entity_id"]
        
        if self.db is None:
            return {"entity": entity, "events": []}
        
        match_query = {"entity_id": entity_id}
        if event_type:
            match_query["type"] = event_type
        
        cursor = self.db.cur_events.find(
            match_query,
            {"_id": 0}
        ).sort("ts", -1).limit(limit)
        
        events = await cursor.to_list(limit)
        
        return {
            "entity": entity,
            "event_type": event_type,
            "events": events,
            "count": len(events)
        }
    
    async def search_entities(
        self, 
        query: str, 
        entity_type: str = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        Search entities by name/symbol.
        """
        if self.db is None:
            return []
        
        search_query = {
            "$or": [
                {"canonical.name": {"$regex": query, "$options": "i"}},
                {"canonical.symbol": {"$regex": query, "$options": "i"}},
                {"aliases": {"$regex": query, "$options": "i"}}
            ]
        }
        
        if entity_type:
            search_query["type"] = entity_type
        
        cursor = self.db.cur_entities.find(
            search_query,
            {"_id": 0}
        ).limit(limit)
        
        return await cursor.to_list(limit)
    
    async def run_entity_resolution(self, limit: int = 1000) -> Dict[str, Any]:
        """
        Run entity resolution job.
        
        1. Takes normalized entities
        2. Resolves/creates entities
        3. Builds entity index
        4. Finds merge candidates
        """
        if self.db is None:
            return {"error": "No database"}
        
        start_time = datetime.now(timezone.utc)
        stats = {
            "processed": 0,
            "created": 0,
            "resolved": 0,
            "merge_candidates": 0
        }
        
        # Process normalized entities
        cursor = self.db.norm_entities.find({}, {"_id": 0}).limit(limit)
        
        async for doc in cursor:
            name = doc.get("name") or doc.get("canonical", {}).get("name")
            symbol = doc.get("symbol") or doc.get("canonical", {}).get("symbol")
            source = doc.get("source", "unknown")
            source_key = doc.get("source_id") or doc.get("_source_id")
            
            if not name:
                continue
            
            # Check if already resolved
            existing = await self.resolver.resolve(name)
            if existing:
                stats["resolved"] += 1
            else:
                await self.resolver.resolve_or_create(
                    name=name,
                    symbol=symbol,
                    source=source,
                    source_key=source_key
                )
                stats["created"] += 1
            
            stats["processed"] += 1
        
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        stats["elapsed_sec"] = round(elapsed, 2)
        
        return stats
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get entity intelligence statistics"""
        if self.db is None:
            return {"error": "No database"}
        
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "entities": await self.db.cur_entities.count_documents({}),
            "index_entries": await self.db.entity_index.count_documents({}),
            "events": await self.db.cur_events.count_documents({}),
            "resolver_cache_size": len(self.resolver._cache)
        }


# Singleton
entity_intelligence: Optional[EntityIntelligenceEngine] = None


def init_entity_intelligence(db):
    """Initialize entity intelligence engine"""
    global entity_intelligence
    entity_intelligence = EntityIntelligenceEngine(db)
    return entity_intelligence


def get_entity_intelligence():
    """Get entity intelligence engine"""
    return entity_intelligence
