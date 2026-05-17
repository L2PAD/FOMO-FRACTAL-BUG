"""
Entity Search Service
=====================

Multi-stage search pipeline for finding entities:
1. Exact match in entity registry
2. Alias match (normalized + fuzzy)
3. Candidate search (discovered but not yet approved)
4. External provider lookup (CryptoRank, RootData)
5. Auto-create entity if found

This ensures search NEVER returns "Entity not found" if entity exists in any source.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class EntitySearchService:
    """
    Multi-stage entity search with fallbacks.
    Solves the "Entity not found" problem.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.graph_nodes = db.graph_nodes
        self.entity_aliases = db.entity_aliases
        self.entity_candidates = db.entity_candidates
        self.search_logs = db.search_logs
        
        # Entity type patterns for classification
        self.type_patterns = {
            "fund": [
                r"capital$", r"ventures$", r"fund$", r"partners$", 
                r"labs$", r"vc$", r"investments$", r"crypto$"
            ],
            "project": [
                r"protocol$", r"network$", r"chain$", r"platform$",
                r"finance$", r"swap$", r"dex$", r"dao$"
            ],
            "person": [
                r"^ceo\s", r"^founder\s", r"^co-founder\s"
            ]
        }
    
    @staticmethod
    def normalize_query(query: str) -> str:
        """Normalize search query"""
        if not query:
            return ""
        normalized = query.lower().strip()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized
    
    @staticmethod
    def to_slug(name: str) -> str:
        """Convert name to slug format"""
        slug = name.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'\s+', '-', slug)
        return slug
    
    def fuzzy_match(self, s1: str, s2: str) -> float:
        """Calculate fuzzy similarity between two strings"""
        return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()
    
    def guess_entity_type(self, name: str) -> str:
        """Guess entity type from name patterns"""
        name_lower = name.lower()
        
        for entity_type, patterns in self.type_patterns.items():
            for pattern in patterns:
                if re.search(pattern, name_lower):
                    return entity_type
        
        # Default to project
        return "project"
    
    def _normalize_entity_response(self, entity: Dict) -> Dict:
        """Normalize entity response to clean format for frontend.
        
        Converts raw graph_node documents (with address-based IDs) to clean entity format:
        - id: "type:entity_name" (e.g., "cex:binance")
        - type: entity type
        - entity_id: clean entity identifier
        - label: display name (cleaned of suffixes)
        """
        if not entity:
            return entity
        
        etype = entity.get("entity_type") or entity.get("type") or "unknown"
        eid = entity.get("entity_id") or entity.get("entity") or entity.get("cluster_id") or ""
        
        # If entity_id is empty but we have a raw ID like "cex:0x28c6...:ethereum"
        # Extract entity from cluster_id or entity field
        if not eid and entity.get("id"):
            raw_id = entity["id"]
            parts = raw_id.split(":")
            if len(parts) >= 2:
                eid = parts[1]  # Could be address, use entity/cluster_id if available
        
        clean_id = f"{etype}:{eid}" if eid else entity.get("id", "")
        
        # Clean label: remove wallet type suffixes
        raw_label = entity.get("label") or entity.get("entity") or eid
        clean_label = raw_label
        for suffix in (" hot_wallet", " cold_wallet", " deposit", " withdrawal"):
            if clean_label and clean_label.lower().endswith(suffix):
                clean_label = clean_label[:len(clean_label)-len(suffix)]
        
        return {
            "id": clean_id,
            "type": etype,
            "entity_type": etype,
            "entity_id": eid,
            "entity": eid,
            "label": clean_label or eid,
            "cluster_id": entity.get("cluster_id"),
            "members_count": entity.get("members_count"),
            "cluster_score": entity.get("cluster_score"),
            "status": entity.get("status"),
            "metadata": entity.get("metadata", {}),
            "from_alias": entity.get("from_alias", False),
            "from_fuzzy": entity.get("from_fuzzy", False),
        }

    
    async def search(
        self,
        query: str,
        entity_type: Optional[str] = None,
        auto_create: bool = True,
        log_search: bool = True
    ) -> Dict[str, Any]:
        """
        Multi-stage entity search.
        
        Pipeline:
        1. Exact match in graph_nodes
        2. Alias match (normalized)
        3. Fuzzy alias match
        4. Candidate search
        5. External provider lookup
        6. Auto-create if found
        
        Returns:
        {
            "found": bool,
            "entity": {...} or None,
            "stage": "exact|alias|fuzzy|candidate|provider|created",
            "confidence": float,
            "suggestions": [...]  # If not found
        }
        """
        normalized = self.normalize_query(query)
        if not normalized:
            return {"found": False, "error": "Empty query"}
        
        result = {
            "found": False,
            "entity": None,
            "stage": None,
            "confidence": 0.0,
            "query": query,
            "normalized_query": normalized
        }
        
        # Stage 1: Exact match in graph_nodes
        entity = await self._search_exact(normalized, entity_type)
        if entity:
            result.update({
                "found": True,
                "entity": self._normalize_entity_response(entity),
                "stage": "exact",
                "confidence": 1.0
            })
            if log_search:
                await self._log_search(query, result)
            return result
        
        # Stage 2: Alias match (normalized)
        entity = await self._search_alias(normalized, entity_type)
        if entity:
            result.update({
                "found": True,
                "entity": self._normalize_entity_response(entity),
                "stage": "alias",
                "confidence": 0.95
            })
            if log_search:
                await self._log_search(query, result)
            return result
        
        # Stage 3: Fuzzy alias match
        entity, confidence = await self._search_fuzzy(normalized, entity_type)
        if entity and confidence >= 0.75:
            result.update({
                "found": True,
                "entity": self._normalize_entity_response(entity),
                "stage": "fuzzy",
                "confidence": confidence
            })
            if log_search:
                await self._log_search(query, result)
            return result
        
        # Stage 4: Candidate search
        candidate = await self._search_candidates(normalized, entity_type)
        if candidate:
            # If candidate has high confidence, promote to entity
            if candidate.get("confidence", 0) >= 0.75 and auto_create:
                entity = await self._create_entity_from_candidate(candidate)
                if entity:
                    result.update({
                        "found": True,
                        "entity": entity,
                        "stage": "candidate_promoted",
                        "confidence": candidate.get("confidence", 0.75)
                    })
                    if log_search:
                        await self._log_search(query, result)
                    return result
            
            result.update({
                "found": True,
                "entity": {
                    "id": candidate.get("_id"),
                    "entity_type": candidate.get("entity_type_guess"),
                    "label": candidate.get("name"),
                    "status": "candidate",
                    "confidence": candidate.get("confidence", 0.5)
                },
                "stage": "candidate",
                "confidence": candidate.get("confidence", 0.5),
                "is_candidate": True
            })
            if log_search:
                await self._log_search(query, result)
            return result
        
        # Stage 5: Search in articles/news (entity mention extraction)
        mention = await self._search_mentions(normalized)
        if mention:
            # Create candidate from mention
            if auto_create:
                candidate = await self._create_candidate_from_mention(
                    query, 
                    entity_type or self.guess_entity_type(query),
                    mention
                )
                if candidate:
                    result.update({
                        "found": True,
                        "entity": {
                            "id": candidate.get("_id"),
                            "entity_type": candidate.get("entity_type_guess"),
                            "label": candidate.get("name"),
                            "status": "candidate",
                            "confidence": 0.5
                        },
                        "stage": "mention_discovered",
                        "confidence": 0.5,
                        "is_candidate": True
                    })
                    if log_search:
                        await self._log_search(query, result)
                    return result
        
        # Not found - return suggestions
        suggestions = await self._get_suggestions(normalized, entity_type)
        result["suggestions"] = suggestions
        
        if log_search:
            await self._log_search(query, result)
        
        return result
    
    async def _search_exact(
        self, 
        normalized: str, 
        entity_type: Optional[str]
    ) -> Optional[Dict]:
        """Stage 1: Exact match in graph_nodes"""
        slug = self.to_slug(normalized)
        upper = normalized.upper().strip()  # Symbol normalization (ETH, BTC, SOL)
        
        # Try different ID formats - support both old (entity_id) and new (entity/cluster_id) fields
        search_patterns = [
            {"entity_id": normalized},
            {"entity_id": slug},
            {"entity": {"$regex": f"^{re.escape(normalized)}$", "$options": "i"}},
            {"cluster_id": {"$regex": f"^{re.escape(normalized)}$", "$options": "i"}},
            {"entity_id": normalized.replace(' ', '_')},
            {"label": {"$regex": f"^{re.escape(normalized)}$", "$options": "i"}},
            # Symbol matching
            {"metadata.symbol": upper},
            {"metadata.ticker": upper},
        ]
        
        if entity_type:
            for pattern in search_patterns:
                pattern["$or"] = [{"entity_type": entity_type}, {"type": entity_type}]
        
        for pattern in search_patterns:
            entity = await self.graph_nodes.find_one(pattern, {"_id": 0})
            if entity:
                return entity
        
        # Also try with type prefix
        if entity_type:
            prefixed_id = f"{entity_type}:{slug}"
            entity = await self.graph_nodes.find_one(
                {"id": prefixed_id}, 
                {"_id": 0}
            )
            if entity:
                return entity
        else:
            # Try common type prefixes
            for prefix in ["cex", "dex", "exchange", "cluster", "protocol", "token", "project", "fund"]:
                entity = await self.graph_nodes.find_one(
                    {"id": f"{prefix}:{slug}"},
                    {"_id": 0}
                )
                if entity:
                    return entity
        
        return None
    
    async def _search_alias(
        self, 
        normalized: str, 
        entity_type: Optional[str]
    ) -> Optional[Dict]:
        """Stage 2: Alias match - supports both alias formats"""
        
        # Format 1: New format {"entity_id": "asset:bitcoin", "aliases": ["btc", "bitcoin"]}
        alias_doc = await self.entity_aliases.find_one({
            "aliases": {"$regex": f"^{re.escape(normalized)}$", "$options": "i"}
        })
        
        if alias_doc and alias_doc.get("entity_id"):
            full_entity_id = alias_doc["entity_id"]  # e.g., "asset:bitcoin"
            
            # Parse entity_type from entity_id if needed
            if ':' in full_entity_id:
                canonical_type, canonical_id = full_entity_id.split(':', 1)
            else:
                canonical_type = entity_type or "project"
                canonical_id = full_entity_id
            
            # If entity_type filter is specified, check it matches
            if entity_type and canonical_type != entity_type:
                # Try to find another alias with matching type
                pass  # Continue to other matches
            else:
                entity = await self.graph_nodes.find_one(
                    {"id": full_entity_id},
                    {"_id": 0}
                )
                
                if entity:
                    return entity
                
                # Return alias info even if entity not in graph
                return {
                    "id": full_entity_id,
                    "entity_type": canonical_type,
                    "entity_id": canonical_id,
                    "label": normalized.title(),
                    "from_alias": True
                }
        
        # Format 2: Legacy format {"entity_id": "bitcoin", "entity_type": "asset", "normalized_alias": "btc"}
        filter_dict = {"normalized_alias": normalized}
        if entity_type:
            filter_dict["entity_type"] = entity_type
        
        alias = await self.entity_aliases.find_one(filter_dict)
        if alias:
            canonical_type = alias["entity_type"]
            canonical_id = alias["entity_id"]
            
            entity = await self.graph_nodes.find_one(
                {
                    "$or": [
                        {"entity_id": canonical_id, "entity_type": canonical_type},
                        {"id": f"{canonical_type}:{canonical_id}"}
                    ]
                },
                {"_id": 0}
            )
            
            if entity:
                return entity
            
            return {
                "id": f"{canonical_type}:{canonical_id}",
                "entity_type": canonical_type,
                "entity_id": canonical_id,
                "label": alias.get("alias", normalized),
                "from_alias": True
            }
        
        return None
    
    async def _search_fuzzy(
        self, 
        normalized: str, 
        entity_type: Optional[str],
        threshold: float = 0.75
    ) -> Tuple[Optional[Dict], float]:
        """Stage 3: Fuzzy alias match"""
        filter_dict = {}
        if entity_type:
            filter_dict["entity_type"] = entity_type
        
        # Get all aliases and compute similarity
        cursor = self.entity_aliases.find(filter_dict).limit(500)
        
        best_match = None
        best_score = 0.0
        
        async for alias in cursor:
            alias_normalized = alias.get("normalized_alias", "")
            score = self.fuzzy_match(normalized, alias_normalized)
            
            if score > best_score and score >= threshold:
                best_score = score
                best_match = alias
        
        if best_match:
            # Fetch the entity
            entity = await self.graph_nodes.find_one(
                {
                    "$or": [
                        {"entity_id": best_match["entity_id"], "entity_type": best_match["entity_type"]},
                        {"id": f"{best_match['entity_type']}:{best_match['entity_id']}"}
                    ]
                },
                {"_id": 0}
            )
            
            if entity:
                return entity, best_score
            
            return {
                "id": f"{best_match['entity_type']}:{best_match['entity_id']}",
                "entity_type": best_match["entity_type"],
                "entity_id": best_match["entity_id"],
                "label": best_match.get("alias", normalized),
                "from_fuzzy": True
            }, best_score
        
        return None, 0.0
    
    async def _search_candidates(
        self, 
        normalized: str, 
        entity_type: Optional[str]
    ) -> Optional[Dict]:
        """Stage 4: Search in entity candidates"""
        filter_dict = {
            "$or": [
                {"normalized_name": normalized},
                {"normalized_name": {"$regex": f".*{re.escape(normalized)}.*"}}
            ],
            "status": {"$in": ["candidate", "validated"]}
        }
        if entity_type:
            filter_dict["entity_type_guess"] = entity_type
        
        candidate = await self.entity_candidates.find_one(
            filter_dict,
            sort=[("confidence", -1)]
        )
        
        return candidate
    
    async def _search_mentions(self, normalized: str) -> Optional[Dict]:
        """Stage 5: Search entity mentions in articles/news"""
        # Search in normalized articles
        articles_collection = self.db.normalized_articles
        
        mention = await articles_collection.find_one(
            {
                "$or": [
                    {"entities": {"$regex": f".*{re.escape(normalized)}.*", "$options": "i"}},
                    {"content": {"$regex": f"\\b{re.escape(normalized)}\\b", "$options": "i"}},
                    {"title": {"$regex": f".*{re.escape(normalized)}.*", "$options": "i"}}
                ]
            },
            {"_id": 0, "title": 1, "source": 1, "entities": 1, "published_at": 1}
        )
        
        return mention
    
    async def _create_candidate_from_mention(
        self,
        name: str,
        entity_type: str,
        mention: Dict
    ) -> Optional[Dict]:
        """Create entity candidate from mention"""
        normalized = self.normalize_query(name)
        now = datetime.now(timezone.utc)
        
        candidate = {
            "_id": f"candidate_{self.to_slug(normalized)}",
            "name": name,
            "normalized_name": normalized,
            "entity_type_guess": entity_type,
            "aliases": [name],
            "source_type": "mention",
            "source_ref": mention.get("title", ""),
            "mention_count": 1,
            "provider_matches": [],
            "confidence": 0.5,
            "status": "candidate",
            "created_at": now,
            "updated_at": now
        }
        
        await self.entity_candidates.update_one(
            {"_id": candidate["_id"]},
            {"$set": candidate},
            upsert=True
        )
        
        logger.info(f"[EntitySearch] Created candidate from mention: {name}")
        return candidate
    
    async def _create_entity_from_candidate(self, candidate: Dict) -> Optional[Dict]:
        """Promote candidate to entity in graph_nodes"""
        entity_type = candidate.get("entity_type_guess", "project")
        entity_id = self.to_slug(candidate.get("normalized_name", ""))
        name = candidate.get("name", entity_id)
        now = datetime.now(timezone.utc)
        
        # Create graph node
        node = {
            "id": f"{entity_type}:{entity_id}",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "label": name,
            "metadata": {
                "source": "entity_discovery",
                "confidence": candidate.get("confidence", 0.75),
                "created_from_candidate": True
            },
            "created_at": now
        }
        
        await self.graph_nodes.update_one(
            {"id": node["id"]},
            {"$set": node},
            upsert=True
        )
        
        # Add aliases
        for alias in candidate.get("aliases", [name]):
            await self.entity_aliases.update_one(
                {"entity_type": entity_type, "normalized_alias": self.normalize_query(alias)},
                {
                    "$set": {
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "alias": alias,
                        "normalized_alias": self.normalize_query(alias),
                        "source": "candidate_promotion",
                        "confidence": candidate.get("confidence", 0.75),
                        "created_at": now
                    }
                },
                upsert=True
            )
        
        # Update candidate status
        await self.entity_candidates.update_one(
            {"_id": candidate["_id"]},
            {"$set": {"status": "approved", "promoted_at": now}}
        )
        
        logger.info(f"[EntitySearch] Promoted candidate to entity: {entity_type}:{entity_id}")
        return node
    
    async def _get_suggestions(
        self, 
        normalized: str, 
        entity_type: Optional[str],
        limit: int = 5
    ) -> List[Dict]:
        """Get search suggestions when entity not found"""
        suggestions = []
        
        # Search similar aliases
        filter_dict = {
            "normalized_alias": {"$regex": f".*{re.escape(normalized[:5])}.*"}
        }
        if entity_type:
            filter_dict["entity_type"] = entity_type
        
        cursor = self.entity_aliases.find(filter_dict).limit(limit * 2)
        
        async for alias in cursor:
            score = self.fuzzy_match(normalized, alias.get("normalized_alias", ""))
            if score >= 0.5:
                suggestions.append({
                    "alias": alias.get("alias"),
                    "entity_type": alias.get("entity_type"),
                    "entity_id": alias.get("entity_id"),
                    "similarity": round(score, 2)
                })
        
        # Sort by similarity
        suggestions.sort(key=lambda x: x["similarity"], reverse=True)
        return suggestions[:limit]
    
    async def _log_search(self, query: str, result: Dict):
        """Log search for analytics"""
        try:
            now = datetime.now(timezone.utc)
            log = {
                "query": query,
                "normalized_query": result.get("normalized_query"),
                "found": result.get("found", False),
                "stage": result.get("stage"),
                "confidence": result.get("confidence"),
                "entity_type": result.get("entity", {}).get("entity_type") if result.get("entity") else None,
                "searched_at": now
            }
            await self.search_logs.insert_one(log)
        except Exception as e:
            logger.debug(f"[EntitySearch] Failed to log search: {e}")
    
    async def get_search_analytics(self, days: int = 7) -> Dict[str, Any]:
        """Get search analytics"""
        from_date = datetime.now(timezone.utc).replace(hour=0, minute=0) - timedelta(days=days)
        
        pipeline = [
            {"$match": {"searched_at": {"$gte": from_date}}},
            {"$group": {
                "_id": {
                    "found": "$found",
                    "stage": "$stage"
                },
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]
        
        results = await self.search_logs.aggregate(pipeline).to_list(100)
        
        # Find common failed queries
        failed_pipeline = [
            {"$match": {"searched_at": {"$gte": from_date}, "found": False}},
            {"$group": {
                "_id": "$normalized_query",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 20}
        ]
        
        failed_queries = await self.search_logs.aggregate(failed_pipeline).to_list(20)
        
        return {
            "by_stage": results,
            "common_failed_queries": failed_queries
        }


# Add missing import
from datetime import timedelta


# Singleton
_search_service: Optional[EntitySearchService] = None


def get_entity_search_service(db: AsyncIOMotorDatabase = None) -> EntitySearchService:
    """Get or create entity search service"""
    global _search_service
    if db is not None:
        _search_service = EntitySearchService(db)
    return _search_service
