"""
Alias Stability Monitoring
===========================

Monitors alias quality and detects:
1. Alias conflicts (same alias → multiple entities)
2. Alias drift (entity identity fragmentation)
3. Duplicate entities (multiple entities = same real-world entity)

Prevents identity drift that degrades graph quality.
"""

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase
from difflib import SequenceMatcher
from collections import defaultdict

logger = logging.getLogger(__name__)

# Similarity threshold for detecting potential duplicates
SIMILARITY_THRESHOLD = 0.85

# Maximum acceptable conflict ratio
MAX_CONFLICT_RATIO = 0.05


class AliasStabilityService:
    """
    Monitors and maintains alias stability.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.entity_aliases = db.entity_aliases
        self.graph_nodes = db.graph_nodes
        self.alias_conflicts = db.alias_conflicts
        self.entity_merges = db.entity_merge_history
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize name for matching"""
        if not name:
            return ""
        normalized = name.lower().strip()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized
    
    def similarity(self, s1: str, s2: str) -> float:
        """Calculate string similarity"""
        return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()
    
    async def detect_conflicts(self) -> Dict[str, Any]:
        """
        Detect alias conflicts where same alias maps to multiple entities.
        """
        # Group aliases by normalized form
        pipeline = [
            {"$group": {
                "_id": "$normalized_alias",
                "entities": {"$addToSet": {"entity_type": "$entity_type", "entity_id": "$entity_id"}},
                "count": {"$sum": 1}
            }},
            {"$match": {"count": {"$gt": 1}}},
            {"$sort": {"count": -1}}
        ]
        
        conflicts = await self.entity_aliases.aggregate(pipeline).to_list(100)
        
        conflict_records = []
        for conflict in conflicts:
            record = {
                "alias": conflict["_id"],
                "entity_count": conflict["count"],
                "entities": conflict["entities"],
                "detected_at": datetime.now(timezone.utc)
            }
            conflict_records.append(record)
            
            # Store conflict for tracking
            await self.alias_conflicts.update_one(
                {"alias": conflict["_id"]},
                {"$set": record},
                upsert=True
            )
        
        total_aliases = await self.entity_aliases.count_documents({})
        conflict_ratio = len(conflicts) / total_aliases if total_aliases > 0 else 0
        
        logger.info(f"[AliasStability] Detected {len(conflicts)} conflicts (ratio: {conflict_ratio:.2%})")
        
        return {
            "conflicts": conflict_records[:20],  # Top 20
            "total_conflicts": len(conflicts),
            "total_aliases": total_aliases,
            "conflict_ratio": round(conflict_ratio, 4),
            "is_healthy": conflict_ratio <= MAX_CONFLICT_RATIO
        }
    
    async def detect_potential_duplicates(self, limit: int = 100) -> Dict[str, Any]:
        """
        Detect potential duplicate entities based on name similarity.
        """
        # Get all entity nodes
        cursor = self.graph_nodes.find(
            {},
            {"id": 1, "entity_type": 1, "entity_id": 1, "label": 1}
        ).limit(500)
        
        nodes = await cursor.to_list(length=500)
        
        # Group by type
        by_type = defaultdict(list)
        for node in nodes:
            entity_type = node.get("entity_type") or node.get("id", "").split(":")[0]
            by_type[entity_type].append(node)
        
        potential_duplicates = []
        
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
                        potential_duplicates.append({
                            "entity1": {
                                "id": node1.get("id"),
                                "label": label1
                            },
                            "entity2": {
                                "id": node2.get("id"),
                                "label": label2
                            },
                            "similarity": round(sim, 3),
                            "entity_type": entity_type
                        })
                    
                    if len(potential_duplicates) >= limit:
                        break
                if len(potential_duplicates) >= limit:
                    break
            if len(potential_duplicates) >= limit:
                break
        
        # Sort by similarity
        potential_duplicates.sort(key=lambda x: x["similarity"], reverse=True)
        
        logger.info(f"[AliasStability] Found {len(potential_duplicates)} potential duplicates")
        
        return {
            "potential_duplicates": potential_duplicates[:limit],
            "count": len(potential_duplicates)
        }
    
    async def check_alias_health(self, entity_id: str) -> Dict[str, Any]:
        """
        Check alias health for a specific entity.
        """
        # Get all aliases for entity
        parts = entity_id.split(":")
        if len(parts) != 2:
            return {"error": "Invalid entity_id format"}
        
        entity_type, slug = parts
        
        aliases = await self.entity_aliases.find({
            "entity_type": entity_type,
            "entity_id": slug
        }).to_list(100)
        
        if not aliases:
            return {
                "entity_id": entity_id,
                "alias_count": 0,
                "health": "no_aliases"
            }
        
        # Check for conflicts
        conflicts = []
        for alias in aliases:
            norm_alias = alias.get("normalized_alias")
            
            # Check if this alias maps to other entities
            others = await self.entity_aliases.find({
                "normalized_alias": norm_alias,
                "$or": [
                    {"entity_type": {"$ne": entity_type}},
                    {"entity_id": {"$ne": slug}}
                ]
            }).to_list(10)
            
            if others:
                conflicts.append({
                    "alias": alias.get("alias"),
                    "conflicts_with": [
                        f"{o['entity_type']}:{o['entity_id']}" for o in others
                    ]
                })
        
        health = "healthy" if not conflicts else "has_conflicts"
        
        return {
            "entity_id": entity_id,
            "alias_count": len(aliases),
            "aliases": [a.get("alias") for a in aliases],
            "conflicts": conflicts,
            "health": health
        }
    
    async def suggest_merges(self, limit: int = 20) -> List[Dict]:
        """
        Suggest entity merges based on alias conflicts and similarity.
        """
        # Get conflicts
        conflicts = await self.alias_conflicts.find({}).sort("entity_count", -1).limit(limit).to_list(limit)
        
        suggestions = []
        
        for conflict in conflicts:
            entities = conflict.get("entities", [])
            if len(entities) < 2:
                continue
            
            # Suggest merging into the most common/oldest entity
            # For now, just suggest first two
            suggestions.append({
                "alias": conflict.get("alias"),
                "merge_from": f"{entities[1]['entity_type']}:{entities[1]['entity_id']}",
                "merge_into": f"{entities[0]['entity_type']}:{entities[0]['entity_id']}",
                "reason": "alias_conflict"
            })
        
        return suggestions
    
    async def record_merge(
        self,
        merged_entity_id: str,
        canonical_entity_id: str,
        reason: str
    ) -> bool:
        """Record entity merge for tracking"""
        try:
            record = {
                "merged_entity": merged_entity_id,
                "canonical_entity": canonical_entity_id,
                "reason": reason,
                "merged_at": datetime.now(timezone.utc)
            }
            
            await self.entity_merges.insert_one(record)
            logger.info(f"[AliasStability] Recorded merge: {merged_entity_id} → {canonical_entity_id}")
            return True
        except Exception as e:
            logger.error(f"[AliasStability] Failed to record merge: {e}")
            return False
    
    async def get_stability_report(self) -> Dict[str, Any]:
        """
        Generate full alias stability report.
        """
        # Detect conflicts
        conflicts = await self.detect_conflicts()
        
        # Check for duplicates
        duplicates = await self.detect_potential_duplicates(limit=20)
        
        # Get merge history
        recent_merges = await self.entity_merges.find({}).sort("merged_at", -1).limit(10).to_list(10)
        
        # Calculate health score
        conflict_penalty = min(0.5, conflicts["conflict_ratio"] * 10)
        duplicate_penalty = min(0.3, duplicates["count"] * 0.01)
        health_score = max(0, 1.0 - conflict_penalty - duplicate_penalty)
        
        return {
            "health_score": round(health_score, 2),
            "is_healthy": health_score >= 0.7,
            "conflicts": {
                "count": conflicts["total_conflicts"],
                "ratio": conflicts["conflict_ratio"],
                "top_conflicts": conflicts["conflicts"][:5]
            },
            "duplicates": {
                "potential_count": duplicates["count"],
                "top_duplicates": duplicates["potential_duplicates"][:5]
            },
            "merges": {
                "recent": [
                    {
                        "from": m.get("merged_entity"),
                        "to": m.get("canonical_entity"),
                        "reason": m.get("reason")
                    }
                    for m in recent_merges
                ]
            },
            "recommendations": await self._generate_recommendations(conflicts, duplicates),
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    
    async def _generate_recommendations(
        self, 
        conflicts: Dict, 
        duplicates: Dict
    ) -> List[str]:
        """Generate recommendations based on analysis"""
        recommendations = []
        
        if conflicts["conflict_ratio"] > MAX_CONFLICT_RATIO:
            recommendations.append(
                f"High alias conflict ratio ({conflicts['conflict_ratio']:.1%}). "
                "Consider reviewing and merging conflicting entities."
            )
        
        if duplicates["count"] > 10:
            recommendations.append(
                f"Found {duplicates['count']} potential duplicate entities. "
                "Review and merge similar entities to improve graph quality."
            )
        
        if not recommendations:
            recommendations.append("Alias stability is healthy. No immediate action required.")
        
        return recommendations
    
    async def run_monitoring_job(self) -> Dict[str, Any]:
        """
        Run full monitoring job - called by scheduler.
        """
        report = await self.get_stability_report()
        
        # Alert if unhealthy
        if not report["is_healthy"]:
            logger.warning(f"[AliasStability] Health score: {report['health_score']} - action recommended")
        
        return report


# Singleton
_stability_service: Optional[AliasStabilityService] = None


def get_alias_stability_service(db: AsyncIOMotorDatabase = None) -> AliasStabilityService:
    """Get or create alias stability service"""
    global _stability_service
    if db is not None:
        _stability_service = AliasStabilityService(db)
    return _stability_service
