"""
Entity Merge System
====================

Handles merging duplicate entities to prevent graph fragmentation.

Example duplicates:
- Pantera Capital / Pantera / Pantera VC
- a16z / Andreessen Horowitz / A16Z

Merge process:
1. Detect merge candidates (via similarity/alias overlap)
2. Select canonical entity
3. Move edges to canonical
4. Move aliases to canonical
5. Delete duplicate
6. Record in merge history

Collections:
- entity_merge_candidates: Pending merge suggestions
- entity_merge_history: Completed merges for audit
"""

import logging
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# Similarity threshold for auto-suggesting merge
SIMILARITY_THRESHOLD = 0.85


class EntityMergeService:
    """
    Manages entity merging to prevent graph fragmentation.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.graph_nodes = db.graph_nodes
        self.graph_edges = db.graph_edges
        self.entity_aliases = db.entity_aliases
        self.entity_confidence = db.entity_confidence
        self.merge_candidates = db.entity_merge_candidates
        self.merge_history = db.entity_merge_history
    
    async def ensure_indexes(self):
        """Create indexes"""
        await self.merge_candidates.create_index("status")
        await self.merge_candidates.create_index([("entity_a", 1), ("entity_b", 1)], unique=True)
        await self.merge_history.create_index("merged_at")
        await self.merge_history.create_index("canonical_entity")
        
        logger.info("[EntityMerge] Indexes created")
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize name for comparison"""
        if not name:
            return ""
        normalized = name.lower().strip()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized
    
    def similarity(self, s1: str, s2: str) -> float:
        """Calculate string similarity"""
        return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()
    
    async def detect_merge_candidates(self, limit: int = 50) -> Dict[str, Any]:
        """
        Detect potential merge candidates based on:
        1. Name similarity
        2. Alias overlap
        3. Same type + similar name
        """
        # Get all entities grouped by type
        cursor = self.graph_nodes.find({}, {"id": 1, "entity_type": 1, "entity_id": 1, "label": 1})
        nodes = await cursor.to_list(length=1000)
        
        # Group by type
        by_type = {}
        for node in nodes:
            entity_type = node.get("entity_type") or node.get("id", "").split(":")[0]
            if entity_type not in by_type:
                by_type[entity_type] = []
            by_type[entity_type].append(node)
        
        candidates_found = 0
        
        # Check within each type
        for entity_type, type_nodes in by_type.items():
            for i, node1 in enumerate(type_nodes):
                for node2 in type_nodes[i+1:]:
                    label1 = node1.get("label", "")
                    label2 = node2.get("label", "")
                    
                    if not label1 or not label2:
                        continue
                    
                    sim = self.similarity(label1, label2)
                    
                    if sim >= SIMILARITY_THRESHOLD and sim < 1.0:
                        # Check if already exists
                        existing = await self.merge_candidates.find_one({
                            "$or": [
                                {"entity_a": node1.get("id"), "entity_b": node2.get("id")},
                                {"entity_a": node2.get("id"), "entity_b": node1.get("id")}
                            ]
                        })
                        
                        if not existing:
                            candidate = {
                                "entity_a": node1.get("id"),
                                "entity_a_label": label1,
                                "entity_b": node2.get("id"),
                                "entity_b_label": label2,
                                "entity_type": entity_type,
                                "similarity": round(sim, 3),
                                "reason": "name_similarity",
                                "status": "pending",
                                "created_at": datetime.now(timezone.utc)
                            }
                            
                            try:
                                await self.merge_candidates.insert_one(candidate)
                                candidates_found += 1
                            except Exception as e:
                                logger.debug(f"[EntityMerge] Candidate insert error: {e}")
                    
                    if candidates_found >= limit:
                        break
                if candidates_found >= limit:
                    break
            if candidates_found >= limit:
                break
        
        # Also check alias overlap
        alias_candidates = await self._detect_alias_overlaps(limit - candidates_found)
        candidates_found += alias_candidates
        
        logger.info(f"[EntityMerge] Detected {candidates_found} merge candidates")
        
        return {
            "candidates_found": candidates_found,
            "detection_method": ["name_similarity", "alias_overlap"]
        }
    
    async def _detect_alias_overlaps(self, limit: int) -> int:
        """Detect merge candidates via alias overlap"""
        if limit <= 0:
            return 0
        
        # Find aliases that point to different entities
        pipeline = [
            {"$group": {
                "_id": "$normalized_alias",
                "entities": {"$addToSet": {"type": "$entity_type", "id": "$entity_id"}},
                "count": {"$sum": 1}
            }},
            {"$match": {"count": {"$gt": 1}}},
            {"$limit": limit}
        ]
        
        overlaps = await self.entity_aliases.aggregate(pipeline).to_list(limit)
        
        candidates_created = 0
        
        for overlap in overlaps:
            entities = overlap.get("entities", [])
            if len(entities) >= 2:
                entity_a = f"{entities[0]['type']}:{entities[0]['id']}"
                entity_b = f"{entities[1]['type']}:{entities[1]['id']}"
                
                # Check if already exists
                existing = await self.merge_candidates.find_one({
                    "$or": [
                        {"entity_a": entity_a, "entity_b": entity_b},
                        {"entity_a": entity_b, "entity_b": entity_a}
                    ]
                })
                
                if not existing:
                    candidate = {
                        "entity_a": entity_a,
                        "entity_a_label": entities[0]['id'],
                        "entity_b": entity_b,
                        "entity_b_label": entities[1]['id'],
                        "entity_type": entities[0]['type'],
                        "similarity": 1.0,
                        "reason": "alias_overlap",
                        "shared_alias": overlap["_id"],
                        "status": "pending",
                        "created_at": datetime.now(timezone.utc)
                    }
                    
                    try:
                        await self.merge_candidates.insert_one(candidate)
                        candidates_created += 1
                    except Exception:
                        pass
        
        return candidates_created
    
    async def get_merge_candidates(
        self, 
        status: str = "pending",
        limit: int = 50
    ) -> List[Dict]:
        """Get merge candidates by status"""
        cursor = self.merge_candidates.find(
            {"status": status},
            {"_id": 0}
        ).sort("similarity", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def merge_entities(
        self,
        source_entity_id: str,
        target_entity_id: str,
        reason: str = "manual"
    ) -> Dict[str, Any]:
        """
        Merge source entity into target (canonical) entity.
        
        Steps:
        1. Move all edges from source to target
        2. Move all aliases from source to target
        3. Update confidence record
        4. Delete source entity
        5. Record in merge history
        """
        now = datetime.now(timezone.utc)
        
        # Validate entities exist
        source_node = await self.graph_nodes.find_one({"id": source_entity_id})
        target_node = await self.graph_nodes.find_one({"id": target_entity_id})
        
        if not source_node:
            return {"error": f"Source entity not found: {source_entity_id}"}
        if not target_node:
            return {"error": f"Target entity not found: {target_entity_id}"}
        
        edges_moved = 0
        aliases_moved = 0
        
        # 1. Move outgoing edges
        result = await self.graph_edges.update_many(
            {"source": source_entity_id},
            {"$set": {"source": target_entity_id}}
        )
        edges_moved += result.modified_count
        
        # 2. Move incoming edges
        result = await self.graph_edges.update_many(
            {"target": source_entity_id},
            {"$set": {"target": target_entity_id}}
        )
        edges_moved += result.modified_count
        
        # 3. Remove self-loops created by merge
        await self.graph_edges.delete_many({
            "source": target_entity_id,
            "target": target_entity_id
        })
        
        # 4. Move aliases
        source_parts = source_entity_id.split(":")
        target_parts = target_entity_id.split(":")
        
        if len(source_parts) == 2 and len(target_parts) == 2:
            source_type, source_slug = source_parts
            target_type, target_slug = target_parts
            
            result = await self.entity_aliases.update_many(
                {"entity_type": source_type, "entity_id": source_slug},
                {"$set": {
                    "entity_type": target_type,
                    "entity_id": target_slug,
                    "merged_from": source_entity_id,
                    "merged_at": now
                }}
            )
            aliases_moved = result.modified_count
            
            # Add source label as alias
            source_label = source_node.get("label")
            if source_label:
                await self.entity_aliases.update_one(
                    {
                        "entity_type": target_type,
                        "normalized_alias": self.normalize_name(source_label)
                    },
                    {
                        "$setOnInsert": {
                            "entity_type": target_type,
                            "entity_id": target_slug,
                            "alias": source_label,
                            "normalized_alias": self.normalize_name(source_label),
                            "source": "merge",
                            "created_at": now
                        }
                    },
                    upsert=True
                )
        
        # 5. Delete source entity from graph_nodes
        await self.graph_nodes.delete_one({"id": source_entity_id})
        
        # 6. Delete source confidence record
        await self.entity_confidence.delete_one({"entity_id": source_entity_id})
        
        # 7. Record merge in history
        merge_record = {
            "source_entity": source_entity_id,
            "source_label": source_node.get("label"),
            "canonical_entity": target_entity_id,
            "canonical_label": target_node.get("label"),
            "reason": reason,
            "edges_moved": edges_moved,
            "aliases_moved": aliases_moved,
            "merged_at": now
        }
        await self.merge_history.insert_one(merge_record)
        
        # 8. Update merge candidate status if exists
        await self.merge_candidates.update_many(
            {
                "$or": [
                    {"entity_a": source_entity_id, "entity_b": target_entity_id},
                    {"entity_a": target_entity_id, "entity_b": source_entity_id}
                ]
            },
            {"$set": {"status": "merged", "merged_at": now}}
        )
        
        logger.info(f"[EntityMerge] Merged {source_entity_id} → {target_entity_id}: "
                   f"{edges_moved} edges, {aliases_moved} aliases")
        
        return {
            "success": True,
            "source_entity": source_entity_id,
            "canonical_entity": target_entity_id,
            "edges_moved": edges_moved,
            "aliases_moved": aliases_moved,
            "merged_at": now.isoformat()
        }
    
    async def reject_candidate(self, entity_a: str, entity_b: str) -> bool:
        """Mark merge candidate as rejected"""
        result = await self.merge_candidates.update_one(
            {
                "$or": [
                    {"entity_a": entity_a, "entity_b": entity_b},
                    {"entity_a": entity_b, "entity_b": entity_a}
                ]
            },
            {"$set": {"status": "rejected", "rejected_at": datetime.now(timezone.utc)}}
        )
        return result.modified_count > 0
    
    async def get_merge_history(self, limit: int = 50) -> List[Dict]:
        """Get merge history"""
        cursor = self.merge_history.find(
            {},
            {"_id": 0}
        ).sort("merged_at", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get merge statistics"""
        pending = await self.merge_candidates.count_documents({"status": "pending"})
        merged = await self.merge_candidates.count_documents({"status": "merged"})
        rejected = await self.merge_candidates.count_documents({"status": "rejected"})
        total_merges = await self.merge_history.count_documents({})
        
        return {
            "candidates": {
                "pending": pending,
                "merged": merged,
                "rejected": rejected
            },
            "total_merges_completed": total_merges
        }
    
    async def auto_merge_high_confidence(self, similarity_threshold: float = 0.95) -> Dict[str, Any]:
        """
        Auto-merge candidates with very high similarity.
        Use with caution - only for obvious duplicates.
        """
        cursor = self.merge_candidates.find({
            "status": "pending",
            "similarity": {"$gte": similarity_threshold}
        }).limit(20)
        
        merged_count = 0
        errors = []
        
        async for candidate in cursor:
            # Always merge into the entity with more edges (more established)
            entity_a = candidate["entity_a"]
            entity_b = candidate["entity_b"]
            
            edges_a = await self.graph_edges.count_documents({
                "$or": [{"source": entity_a}, {"target": entity_a}]
            })
            edges_b = await self.graph_edges.count_documents({
                "$or": [{"source": entity_b}, {"target": entity_b}]
            })
            
            # Merge smaller into larger
            if edges_a >= edges_b:
                source, target = entity_b, entity_a
            else:
                source, target = entity_a, entity_b
            
            result = await self.merge_entities(source, target, reason="auto_high_similarity")
            
            if result.get("success"):
                merged_count += 1
            else:
                errors.append(result.get("error"))
        
        return {
            "auto_merged": merged_count,
            "errors": errors[:5] if errors else []
        }


# Singleton
_merge_service: Optional[EntityMergeService] = None


def get_entity_merge_service(db: AsyncIOMotorDatabase = None) -> EntityMergeService:
    """Get or create entity merge service"""
    global _merge_service
    if db is not None:
        _merge_service = EntityMergeService(db)
    return _merge_service
