"""
Alias Learning Service - Auto-learning and promotion of entity aliases

Architecture:
1. alias_candidates - stores potential aliases with confidence scores
2. Validation - accumulates seen_count and confidence over time
3. Auto-promotion - when threshold met, moves to entity_aliases

Thresholds:
- seen_count >= 10
- confidence >= 0.9
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Promotion thresholds
MIN_SEEN_COUNT = 10
MIN_CONFIDENCE = 0.9


class AliasLearningService:
    """
    Service for learning and promoting entity aliases.
    
    Flow:
    1. record_alias_observation() - called when system sees alias → entity mapping
    2. Candidate accumulates confidence and seen_count
    3. promote_ready_candidates() - auto-promotes when thresholds met
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        # Use fomo_intel database for aliases
        self._alias_db = None
    
    async def _get_collections(self):
        """Get alias collections from fomo_intel database"""
        if self._alias_db is None:
            client = self.db.client
            self._alias_db = client['fomo_intel']
        
        return (
            self._alias_db.alias_candidates,
            self._alias_db.entity_aliases
        )
    
    async def record_alias_observation(
        self,
        alias: str,
        canonical_id: str,
        source: str = "system",
        confidence: float = 0.8,
        entity_type: str = "asset"
    ) -> Dict[str, Any]:
        """
        Record an observation of alias → canonical mapping.
        
        If alias already in entity_aliases, skip.
        If alias in candidates, increment seen_count and update confidence.
        Otherwise, create new candidate.
        
        Returns status dict with action taken.
        """
        candidates_col, aliases_col = await self._get_collections()
        
        alias_normalized = alias.lower().strip()
        canonical_normalized = canonical_id.lower().strip()
        
        if not alias_normalized or not canonical_normalized:
            return {"status": "skipped", "reason": "empty_input"}
        
        # Skip if alias already in entity_aliases
        existing_alias = await aliases_col.find_one({"aliases": alias_normalized})
        if existing_alias:
            return {
                "status": "already_exists",
                "entity_id": existing_alias.get("entity_id"),
                "canonical_id": existing_alias.get("canonical_id")
            }
        
        # Check if candidate exists
        existing_candidate = await candidates_col.find_one({
            "alias": alias_normalized,
            "canonical_candidate": canonical_normalized
        })
        
        now = datetime.now(timezone.utc)
        
        if existing_candidate:
            # Update existing candidate
            new_seen_count = existing_candidate.get("seen_count", 0) + 1
            
            # Rolling average confidence
            old_confidence = existing_candidate.get("confidence", 0.5)
            new_confidence = (old_confidence * 0.7) + (confidence * 0.3)
            
            await candidates_col.update_one(
                {"_id": existing_candidate["_id"]},
                {
                    "$set": {
                        "seen_count": new_seen_count,
                        "confidence": new_confidence,
                        "last_seen_at": now,
                        "last_source": source
                    },
                    "$addToSet": {"sources": source}
                }
            )
            
            # Check for auto-promotion
            if new_seen_count >= MIN_SEEN_COUNT and new_confidence >= MIN_CONFIDENCE:
                promoted = await self._promote_candidate(existing_candidate["_id"])
                if promoted:
                    return {
                        "status": "promoted",
                        "alias": alias_normalized,
                        "canonical_id": canonical_normalized,
                        "seen_count": new_seen_count,
                        "confidence": new_confidence
                    }
            
            return {
                "status": "updated",
                "alias": alias_normalized,
                "canonical_id": canonical_normalized,
                "seen_count": new_seen_count,
                "confidence": new_confidence
            }
        else:
            # Create new candidate
            candidate_doc = {
                "alias": alias_normalized,
                "canonical_candidate": canonical_normalized,
                "entity_type": entity_type,
                "confidence": confidence,
                "seen_count": 1,
                "sources": [source],
                "last_source": source,
                "approved": False,
                "created_at": now,
                "last_seen_at": now
            }
            
            await candidates_col.insert_one(candidate_doc)
            
            return {
                "status": "created",
                "alias": alias_normalized,
                "canonical_id": canonical_normalized,
                "confidence": confidence
            }
    
    async def _promote_candidate(self, candidate_id) -> bool:
        """
        Promote a candidate to entity_aliases.
        
        Returns True if promotion successful.
        """
        candidates_col, aliases_col = await self._get_collections()
        
        candidate = await candidates_col.find_one({"_id": candidate_id})
        if not candidate:
            return False
        
        alias = candidate["alias"]
        canonical = candidate["canonical_candidate"]
        entity_type = candidate.get("entity_type", "asset")
        
        # Check if canonical already exists in aliases
        entity_id = f"{entity_type}:{canonical}"
        existing = await aliases_col.find_one({"entity_id": entity_id})
        
        now = datetime.now(timezone.utc)
        
        if existing:
            # Add alias to existing entity
            await aliases_col.update_one(
                {"entity_id": entity_id},
                {
                    "$addToSet": {"aliases": alias},
                    "$set": {"updated_at": now}
                }
            )
        else:
            # Create new alias entry
            await aliases_col.insert_one({
                "entity_id": entity_id,
                "canonical_id": canonical,
                "aliases": [alias, canonical],
                "source": "auto_learning",
                "learned_from": candidate.get("sources", []),
                "created_at": now
            })
        
        # Mark candidate as approved
        await candidates_col.update_one(
            {"_id": candidate_id},
            {
                "$set": {
                    "approved": True,
                    "promoted_at": now
                }
            }
        )
        
        logger.info(f"Alias promoted: {alias} → {canonical}")
        return True
    
    async def promote_ready_candidates(self) -> List[Dict[str, Any]]:
        """
        Batch promote all candidates that meet thresholds.
        
        Returns list of promoted aliases.
        """
        candidates_col, _ = await self._get_collections()
        
        # Find candidates ready for promotion
        cursor = candidates_col.find({
            "approved": False,
            "seen_count": {"$gte": MIN_SEEN_COUNT},
            "confidence": {"$gte": MIN_CONFIDENCE}
        })
        
        promoted = []
        async for candidate in cursor:
            success = await self._promote_candidate(candidate["_id"])
            if success:
                promoted.append({
                    "alias": candidate["alias"],
                    "canonical_id": candidate["canonical_candidate"],
                    "confidence": candidate["confidence"],
                    "seen_count": candidate["seen_count"]
                })
        
        return promoted
    
    async def get_candidates(
        self,
        limit: int = 50,
        min_confidence: float = 0.0,
        include_approved: bool = False
    ) -> List[Dict[str, Any]]:
        """Get alias candidates for review."""
        candidates_col, _ = await self._get_collections()
        
        filter_dict = {"confidence": {"$gte": min_confidence}}
        if not include_approved:
            filter_dict["approved"] = False
        
        cursor = candidates_col.find(filter_dict).sort([
            ("confidence", -1),
            ("seen_count", -1)
        ]).limit(limit)
        
        results = []
        async for doc in cursor:
            results.append({
                "alias": doc["alias"],
                "canonical_candidate": doc["canonical_candidate"],
                "confidence": doc["confidence"],
                "seen_count": doc["seen_count"],
                "sources": doc.get("sources", []),
                "approved": doc.get("approved", False),
                "created_at": doc.get("created_at"),
                "last_seen_at": doc.get("last_seen_at")
            })
        
        return results
    
    async def manually_approve(self, alias: str, canonical_id: str) -> bool:
        """Manually approve and promote an alias."""
        candidates_col, _ = await self._get_collections()
        
        candidate = await candidates_col.find_one({
            "alias": alias.lower(),
            "canonical_candidate": canonical_id.lower()
        })
        
        if candidate:
            return await self._promote_candidate(candidate["_id"])
        
        # Create and promote immediately
        result = await self.record_alias_observation(
            alias=alias,
            canonical_id=canonical_id,
            source="manual_approval",
            confidence=1.0
        )
        
        # Force promotion
        candidate = await candidates_col.find_one({
            "alias": alias.lower(),
            "canonical_candidate": canonical_id.lower()
        })
        
        if candidate:
            await candidates_col.update_one(
                {"_id": candidate["_id"]},
                {"$set": {"seen_count": MIN_SEEN_COUNT, "confidence": 1.0}}
            )
            return await self._promote_candidate(candidate["_id"])
        
        return False
    
    async def reject_candidate(self, alias: str, canonical_id: str) -> bool:
        """Reject a candidate (mark as not to promote)."""
        candidates_col, _ = await self._get_collections()
        
        result = await candidates_col.update_one(
            {
                "alias": alias.lower(),
                "canonical_candidate": canonical_id.lower()
            },
            {
                "$set": {
                    "rejected": True,
                    "rejected_at": datetime.now(timezone.utc)
                }
            }
        )
        
        return result.modified_count > 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get alias learning statistics."""
        candidates_col, aliases_col = await self._get_collections()
        
        total_candidates = await candidates_col.count_documents({})
        pending_candidates = await candidates_col.count_documents({"approved": False, "rejected": {"$ne": True}})
        promoted_candidates = await candidates_col.count_documents({"approved": True})
        rejected_candidates = await candidates_col.count_documents({"rejected": True})
        
        ready_for_promotion = await candidates_col.count_documents({
            "approved": False,
            "rejected": {"$ne": True},
            "seen_count": {"$gte": MIN_SEEN_COUNT},
            "confidence": {"$gte": MIN_CONFIDENCE}
        })
        
        total_aliases = await aliases_col.count_documents({})
        auto_learned = await aliases_col.count_documents({"source": "auto_learning"})
        
        return {
            "candidates": {
                "total": total_candidates,
                "pending": pending_candidates,
                "promoted": promoted_candidates,
                "rejected": rejected_candidates,
                "ready_for_promotion": ready_for_promotion
            },
            "aliases": {
                "total": total_aliases,
                "auto_learned": auto_learned
            },
            "thresholds": {
                "min_seen_count": MIN_SEEN_COUNT,
                "min_confidence": MIN_CONFIDENCE
            }
        }


# Singleton instance
_learning_service: Optional[AliasLearningService] = None


def get_alias_learning_service(db: AsyncIOMotorDatabase) -> AliasLearningService:
    """Get or create alias learning service singleton."""
    global _learning_service
    if _learning_service is None:
        _learning_service = AliasLearningService(db)
    return _learning_service
