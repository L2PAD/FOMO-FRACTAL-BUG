"""
Entity Confidence Layer
========================

Calculates confidence scores for entity candidates based on:
- source_quality (0.30)
- mention_count (0.20)
- multi_source_confirmation (0.25)
- structured_evidence (0.15)
- alias_stability (0.10)

Tiers:
- high: >= 0.85
- medium: 0.75-0.84
- low: 0.60-0.74
- reject: < 0.60

Entity creation threshold: confidence >= 0.75
"""

import logging
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


# Confidence factor weights
FACTOR_WEIGHTS = {
    "source_quality": 0.30,
    "mention_count": 0.20,
    "multi_source_confirmation": 0.25,
    "structured_evidence": 0.15,
    "alias_stability": 0.10
}

# Source quality scores
SOURCE_QUALITY_SCORES = {
    "provider": 0.95,        # CryptoRank, RootData, CoinGecko
    "funding": 0.90,         # Structured funding round data
    "structured": 0.85,      # Other structured data
    "research": 0.75,        # Research documents
    "article": 0.65,         # Article mention
    "mention": 0.55,         # Simple mention
    "seed": 0.80,            # Seed data
    "discovery": 0.60        # Auto-discovery
}

# Confidence tiers
CONFIDENCE_TIERS = {
    "high": 0.85,
    "medium": 0.75,
    "low": 0.60
}

# Entity creation threshold
CREATION_THRESHOLD = 0.75


class EntityConfidenceService:
    """
    Calculates and manages entity confidence scores.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.confidence_collection = db.entity_confidence
        self.candidates = db.entity_candidates
        self.entity_aliases = db.entity_aliases
        self.graph_nodes = db.graph_nodes
        
        # Structured data collections for evidence check
        self.funding_rounds = db.funding_rounds
        self.token_symbols = db.token_unlocks
    
    async def ensure_indexes(self):
        """Create indexes for confidence collection"""
        await self.confidence_collection.create_index("entity_id", unique=True)
        await self.confidence_collection.create_index("confidence_score")
        await self.confidence_collection.create_index("confidence_tier")
        await self.confidence_collection.create_index("updated_at")
        
        logger.info("[EntityConfidence] Indexes created")
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize name for matching"""
        if not name:
            return ""
        normalized = name.lower().strip()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized
    
    def _get_tier(self, score: float) -> str:
        """Get confidence tier from score"""
        if score >= CONFIDENCE_TIERS["high"]:
            return "high"
        elif score >= CONFIDENCE_TIERS["medium"]:
            return "medium"
        elif score >= CONFIDENCE_TIERS["low"]:
            return "low"
        else:
            return "reject"
    
    async def calculate_source_quality(self, candidate: Dict) -> float:
        """Calculate source quality factor"""
        source_type = candidate.get("source_type", "discovery")
        base_score = SOURCE_QUALITY_SCORES.get(source_type, 0.5)
        
        # Boost if provider validated
        provider_matches = candidate.get("provider_matches", [])
        if provider_matches:
            provider_boost = min(0.15, len(provider_matches) * 0.05)
            base_score = min(1.0, base_score + provider_boost)
        
        return base_score
    
    async def calculate_mention_count(self, candidate: Dict) -> float:
        """Calculate mention count factor"""
        mentions = candidate.get("mention_count", 1)
        
        if mentions >= 10:
            return 1.0
        elif mentions >= 7:
            return 0.95
        elif mentions >= 5:
            return 0.85
        elif mentions >= 3:
            return 0.70
        elif mentions >= 2:
            return 0.55
        else:
            return 0.35
    
    async def calculate_multi_source(self, candidate: Dict) -> float:
        """Calculate multi-source confirmation factor"""
        sources = candidate.get("sources", [])
        provider_matches = candidate.get("provider_matches", [])
        
        total_sources = len(set(sources)) + len(provider_matches)
        
        if total_sources >= 4:
            return 1.0
        elif total_sources >= 3:
            return 0.85
        elif total_sources >= 2:
            return 0.70
        else:
            return 0.40
    
    async def calculate_structured_evidence(self, candidate: Dict) -> float:
        """Calculate structured evidence factor"""
        name = candidate.get("name", "")
        normalized = self.normalize_name(name)
        
        evidence_score = 0.0
        
        # Check funding rounds
        funding = await self.funding_rounds.find_one({
            "$or": [
                {"project_name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}},
                {"investors": {"$elemMatch": {"$regex": f".*{re.escape(name)}.*", "$options": "i"}}}
            ]
        })
        if funding:
            evidence_score += 0.4
        
        # Check if has provider validation with metadata
        provider_matches = candidate.get("provider_matches", [])
        if provider_matches:
            evidence_score += 0.3
        
        # Check aliases (more aliases = more confirmed)
        alias_count = await self.entity_aliases.count_documents({
            "normalized_alias": {"$regex": f".*{re.escape(normalized)}.*"}
        })
        if alias_count > 0:
            evidence_score += 0.2
        
        # Check graph nodes (already exists)
        node = await self.graph_nodes.find_one({
            "$or": [
                {"label": {"$regex": f"^{re.escape(name)}$", "$options": "i"}},
                {"entity_id": normalized.replace(' ', '-')}
            ]
        })
        if node:
            evidence_score += 0.3
        
        return min(1.0, evidence_score)
    
    async def calculate_alias_stability(self, candidate: Dict) -> float:
        """Calculate alias stability factor"""
        name = candidate.get("name", "")
        normalized = self.normalize_name(name)
        aliases = candidate.get("aliases", [name])
        
        # Check for alias conflicts
        conflicts = 0
        
        for alias in aliases:
            alias_norm = self.normalize_name(alias)
            
            # Check if alias maps to different entity
            existing_alias = await self.entity_aliases.find_one({
                "normalized_alias": alias_norm
            })
            
            if existing_alias:
                existing_entity_id = existing_alias.get("entity_id", "")
                candidate_slug = normalized.replace(' ', '-').replace(' ', '_')
                
                # If alias maps to different entity, it's a conflict
                if existing_entity_id and existing_entity_id != candidate_slug:
                    # Check similarity
                    similarity = SequenceMatcher(None, existing_entity_id, candidate_slug).ratio()
                    if similarity < 0.8:  # Significantly different
                        conflicts += 1
        
        # Calculate stability score
        if conflicts == 0:
            return 1.0
        elif conflicts == 1:
            return 0.7
        elif conflicts == 2:
            return 0.5
        else:
            return 0.3
    
    async def calculate_confidence(
        self, 
        candidate: Dict,
        provider_validation: Dict = None
    ) -> Dict[str, Any]:
        """
        Calculate full confidence score for a candidate.
        
        Returns:
        {
            "confidence_score": float,
            "confidence_tier": str,
            "factors": {...},
            "should_create": bool
        }
        """
        # Merge provider validation data if provided
        if provider_validation and provider_validation.get("validated"):
            candidate["provider_matches"] = provider_validation.get("provider_matches", [])
            if provider_validation.get("confirmed_type"):
                candidate["entity_type_guess"] = provider_validation["confirmed_type"]
        
        # Calculate all factors
        factors = {
            "source_quality": await self.calculate_source_quality(candidate),
            "mention_count": await self.calculate_mention_count(candidate),
            "multi_source_confirmation": await self.calculate_multi_source(candidate),
            "structured_evidence": await self.calculate_structured_evidence(candidate),
            "alias_stability": await self.calculate_alias_stability(candidate)
        }
        
        # Apply provider confidence boost
        if provider_validation and provider_validation.get("provider_confidence"):
            provider_conf = provider_validation["provider_confidence"]
            # Boost source_quality if provider validated
            factors["source_quality"] = min(1.0, factors["source_quality"] * 1.1)
            factors["multi_source_confirmation"] = max(
                factors["multi_source_confirmation"],
                provider_conf * 0.9
            )
        
        # Calculate weighted score
        confidence_score = sum(
            factors[factor] * weight 
            for factor, weight in FACTOR_WEIGHTS.items()
        )
        
        # Round to 2 decimal places
        confidence_score = round(confidence_score, 3)
        
        # Determine tier
        confidence_tier = self._get_tier(confidence_score)
        
        # Determine if entity should be created
        should_create = confidence_score >= CREATION_THRESHOLD
        
        return {
            "confidence_score": confidence_score,
            "confidence_tier": confidence_tier,
            "factors": factors,
            "should_create": should_create,
            "threshold": CREATION_THRESHOLD
        }
    
    async def save_confidence(
        self,
        entity_id: str,
        entity_type: str,
        confidence_result: Dict
    ) -> bool:
        """Save confidence record"""
        try:
            now = datetime.now(timezone.utc)
            
            record = {
                "entity_id": entity_id,
                "entity_type": entity_type,
                "confidence_score": confidence_result["confidence_score"],
                "confidence_tier": confidence_result["confidence_tier"],
                "factors": confidence_result["factors"],
                "updated_at": now
            }
            
            await self.confidence_collection.update_one(
                {"entity_id": entity_id},
                {"$set": record},
                upsert=True
            )
            
            return True
        except Exception as e:
            logger.error(f"[EntityConfidence] Failed to save: {e}")
            return False
    
    async def get_confidence(self, entity_id: str) -> Optional[Dict]:
        """Get confidence record for entity"""
        record = await self.confidence_collection.find_one(
            {"entity_id": entity_id},
            {"_id": 0}
        )
        return record
    
    async def get_low_confidence_entities(self, limit: int = 50) -> List[Dict]:
        """Get entities with low confidence"""
        cursor = self.confidence_collection.find(
            {"confidence_tier": {"$in": ["low", "reject"]}},
            {"_id": 0}
        ).sort("confidence_score", 1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_quality_metrics(self) -> Dict[str, Any]:
        """Get entity quality metrics"""
        # Total entities with confidence
        total = await self.confidence_collection.count_documents({})
        
        # By tier
        tier_pipeline = [
            {"$group": {"_id": "$confidence_tier", "count": {"$sum": 1}}}
        ]
        tier_counts = await self.confidence_collection.aggregate(tier_pipeline).to_list(10)
        
        # Average confidence
        avg_pipeline = [
            {"$group": {"_id": None, "avg": {"$avg": "$confidence_score"}}}
        ]
        avg_result = await self.confidence_collection.aggregate(avg_pipeline).to_list(1)
        avg_score = avg_result[0]["avg"] if avg_result else 0
        
        # Entity quality ratio (approved / total candidates)
        total_candidates = await self.candidates.count_documents({})
        approved_count = await self.candidates.count_documents({"status": "approved"})
        quality_ratio = approved_count / total_candidates if total_candidates > 0 else 0
        
        return {
            "total_with_confidence": total,
            "by_tier": {t["_id"]: t["count"] for t in tier_counts},
            "average_confidence": round(avg_score, 3),
            "entity_quality_ratio": round(quality_ratio, 3),
            "quality_threshold": 0.6,  # Alert if ratio drops below this
            "is_healthy": quality_ratio >= 0.6
        }


# Singleton
_confidence_service: Optional[EntityConfidenceService] = None


def get_entity_confidence_service(db: AsyncIOMotorDatabase = None) -> EntityConfidenceService:
    """Get or create entity confidence service"""
    global _confidence_service
    if db is not None:
        _confidence_service = EntityConfidenceService(db)
    return _confidence_service
