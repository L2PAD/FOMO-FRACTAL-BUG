"""
Entity Candidate Discovery Engine
==================================

Automatically discovers new entities from data sources:
- Articles / News
- Funding rounds
- Provider data

Pipeline:
1. Extract entity mentions from new data
2. Normalize and deduplicate
3. Classify entity type
4. Calculate confidence
5. Store as candidates for validation

Collections:
- entity_candidates: Discovered entity candidates
"""

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Set
from motor.motor_asyncio import AsyncIOMotorDatabase
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


# Entity type classification patterns
ENTITY_PATTERNS = {
    "fund": {
        "suffixes": [
            "capital", "ventures", "fund", "partners", "labs", "vc", 
            "investments", "crypto", "asset", "group", "holdings"
        ],
        "keywords": ["invest", "portfolio", "raise", "backed by", "led by"]
    },
    "project": {
        "suffixes": [
            "protocol", "network", "chain", "platform", "finance", 
            "swap", "dex", "dao", "fi", "bridge", "layer"
        ],
        "keywords": ["launch", "mainnet", "testnet", "airdrop", "token"]
    },
    "person": {
        "prefixes": ["ceo", "founder", "co-founder", "cto", "coo"],
        "patterns": [r"\b[A-Z][a-z]+ [A-Z][a-z]+\b"]  # Name pattern
    },
    "exchange": {
        "suffixes": ["exchange", "ex", "dex"],
        "keywords": ["listed on", "trading", "pair"]
    }
}

# Known high-confidence entities to seed
SEED_ENTITIES = {
    "fund": [
        "Pantera Capital", "Multicoin Capital", "Paradigm", "a16z", 
        "Polychain Capital", "Dragonfly", "Framework Ventures",
        "Jump Crypto", "Hack VC", "Galaxy Digital", "Spartan Group",
        "Delphi Ventures", "DCG", "Placeholder", "Robot Ventures",
        "Sequoia Capital", "Coinbase Ventures", "Binance Labs",
        "Electric Capital", "Variant Fund", "Blockchain Capital",
        "Three Arrows Capital", "Animoca Brands", "Solana Ventures"
    ],
    "project": [
        "Monad", "Berachain", "EigenLayer", "Celestia", "Movement",
        "Fuel", "Eclipse", "Sei", "Sui", "Aptos", "LayerZero",
        "Wormhole", "Hyperlane", "Pyth Network", "StarkNet",
        "zkSync", "Scroll", "Linea", "Mantle", "Base"
    ],
    "person": [
        "Anatoly Yakovenko", "Vitalik Buterin", "Changpeng Zhao",
        "Brian Armstrong", "Sam Altman", "Balaji Srinivasan"
    ]
}


class EntityCandidateDiscovery:
    """
    Discovers and validates entity candidates from data sources.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.candidates = db.entity_candidates
        self.entity_aliases = db.entity_aliases
        self.graph_nodes = db.graph_nodes
        
        # Data source collections
        self.articles = db.normalized_articles
        self.funding_rounds = db.funding_rounds
        self.news_articles = db.news_articles
    
    async def ensure_indexes(self):
        """Create indexes for entity_candidates"""
        await self.candidates.create_index("normalized_name", unique=True)
        await self.candidates.create_index("entity_type_guess")
        await self.candidates.create_index("status")
        await self.candidates.create_index("confidence")
        await self.candidates.create_index("mention_count")
        await self.candidates.create_index("created_at")
        await self.candidates.create_index("updated_at")
        
        logger.info("[EntityCandidateDiscovery] Indexes created")
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize entity name for matching"""
        if not name:
            return ""
        normalized = name.lower().strip()
        normalized = re.sub(r'[^\w\s-]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized
    
    @staticmethod
    def to_slug(name: str) -> str:
        """Convert name to slug"""
        slug = name.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'\s+', '-', slug)
        return slug
    
    def classify_entity_type(self, name: str, context: str = "") -> str:
        """Classify entity type based on name patterns and context"""
        name_lower = name.lower()
        context_lower = context.lower()
        
        # Check fund patterns
        for suffix in ENTITY_PATTERNS["fund"]["suffixes"]:
            if name_lower.endswith(suffix):
                return "fund"
        for keyword in ENTITY_PATTERNS["fund"]["keywords"]:
            if keyword in context_lower:
                return "fund"
        
        # Check project patterns
        for suffix in ENTITY_PATTERNS["project"]["suffixes"]:
            if name_lower.endswith(suffix):
                return "project"
        for keyword in ENTITY_PATTERNS["project"]["keywords"]:
            if keyword in context_lower:
                return "project"
        
        # Check exchange patterns
        for suffix in ENTITY_PATTERNS["exchange"]["suffixes"]:
            if name_lower.endswith(suffix):
                return "exchange"
        
        # Check person patterns
        for prefix in ENTITY_PATTERNS["person"]["prefixes"]:
            if prefix in context_lower:
                return "person"
        
        # Default to project
        return "project"
    
    def fuzzy_match(self, s1: str, s2: str) -> float:
        """Calculate fuzzy similarity"""
        return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()
    
    async def is_existing_entity(self, normalized_name: str) -> bool:
        """Check if entity already exists in graph or aliases"""
        # Check graph_nodes
        exists = await self.graph_nodes.find_one({
            "$or": [
                {"entity_id": normalized_name},
                {"entity_id": normalized_name.replace(' ', '-')},
                {"entity_id": normalized_name.replace(' ', '_')},
                {"label": {"$regex": f"^{re.escape(normalized_name)}$", "$options": "i"}}
            ]
        })
        if exists:
            return True
        
        # Check aliases
        alias_exists = await self.entity_aliases.find_one({
            "normalized_alias": normalized_name
        })
        if alias_exists:
            return True
        
        return False
    
    async def add_candidate(
        self,
        name: str,
        entity_type: str = None,
        source_type: str = "discovery",
        source_ref: str = None,
        confidence: float = 0.5,
        context: str = ""
    ) -> Optional[Dict]:
        """Add or update entity candidate"""
        normalized = self.normalize_name(name)
        if not normalized or len(normalized) < 2:
            return None
        
        # Skip if already exists as entity
        if await self.is_existing_entity(normalized):
            return None
        
        # Classify type if not provided
        if not entity_type:
            entity_type = self.classify_entity_type(name, context)
        
        now = datetime.now(timezone.utc)
        
        # Check for existing candidate
        existing = await self.candidates.find_one({"normalized_name": normalized})
        
        if existing:
            # Update existing candidate
            new_mention_count = existing.get("mention_count", 1) + 1
            
            # Increase confidence with more mentions
            new_confidence = min(0.95, existing.get("confidence", 0.5) + 0.05)
            
            # Add source if new
            sources = existing.get("sources", [])
            if source_ref and source_ref not in sources:
                sources.append(source_ref)
            
            await self.candidates.update_one(
                {"normalized_name": normalized},
                {
                    "$set": {
                        "mention_count": new_mention_count,
                        "confidence": new_confidence,
                        "sources": sources[:10],  # Keep last 10 sources
                        "updated_at": now
                    }
                }
            )
            
            logger.debug(f"[EntityCandidate] Updated: {name} (mentions: {new_mention_count})")
            return {"updated": True, "name": name, "mentions": new_mention_count}
        
        # Create new candidate
        candidate = {
            "name": name,
            "normalized_name": normalized,
            "slug": self.to_slug(name),
            "entity_type_guess": entity_type,
            "aliases": [name],
            "source_type": source_type,
            "sources": [source_ref] if source_ref else [],
            "mention_count": 1,
            "provider_matches": [],
            "confidence": confidence,
            "confidence_factors": {
                "source_quality": 0.5,
                "mention_count": 0.5,
                "multi_source": False,
                "structured_evidence": False
            },
            "status": "candidate",
            "created_at": now,
            "updated_at": now
        }
        
        try:
            await self.candidates.insert_one(candidate)
            logger.info(f"[EntityCandidate] Created: {name} ({entity_type})")
            return {"created": True, "name": name, "type": entity_type}
        except Exception as e:
            logger.debug(f"[EntityCandidate] Failed to create {name}: {e}")
            return None
    
    async def discover_from_articles(self, limit: int = 100) -> Dict[str, Any]:
        """Discover entities from recent articles"""
        now = datetime.now(timezone.utc)
        since = now - timedelta(hours=24)
        
        discovered = 0
        processed = 0
        
        # Get recent articles
        cursor = self.articles.find(
            {"created_at": {"$gte": since}},
            {"title": 1, "content": 1, "entities": 1, "source": 1}
        ).limit(limit)
        
        async for article in cursor:
            processed += 1
            
            # Extract from entities field if present
            entities = article.get("entities", [])
            if isinstance(entities, list):
                for entity_name in entities:
                    if isinstance(entity_name, str) and len(entity_name) >= 3:
                        result = await self.add_candidate(
                            name=entity_name,
                            source_type="article",
                            source_ref=article.get("title", ""),
                            context=article.get("content", "")[:500]
                        )
                        if result:
                            discovered += 1
            
            # Extract from title using NER patterns
            title = article.get("title", "")
            extracted = self._extract_entity_mentions(title)
            for name in extracted:
                result = await self.add_candidate(
                    name=name,
                    source_type="article_title",
                    source_ref=title,
                    context=title
                )
                if result:
                    discovered += 1
        
        logger.info(f"[EntityCandidate] Discovered {discovered} from {processed} articles")
        return {
            "discovered": discovered,
            "processed": processed,
            "source": "articles"
        }
    
    async def discover_from_funding(self, limit: int = 100) -> Dict[str, Any]:
        """Discover entities from funding rounds"""
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=7)
        
        discovered = 0
        processed = 0
        
        cursor = self.funding_rounds.find(
            {"created_at": {"$gte": since}}
        ).limit(limit)
        
        async for round_data in cursor:
            processed += 1
            
            # Extract project
            project_name = round_data.get("project_name") or round_data.get("project")
            if project_name:
                result = await self.add_candidate(
                    name=project_name,
                    entity_type="project",
                    source_type="funding",
                    source_ref=f"funding_{round_data.get('_id', '')}",
                    confidence=0.85  # High confidence from structured data
                )
                if result:
                    discovered += 1
            
            # Extract investors
            investors = round_data.get("investors", [])
            for investor in investors:
                investor_name = investor if isinstance(investor, str) else investor.get("name")
                if investor_name:
                    result = await self.add_candidate(
                        name=investor_name,
                        entity_type="fund",
                        source_type="funding",
                        source_ref=f"funding_{round_data.get('_id', '')}",
                        confidence=0.85
                    )
                    if result:
                        discovered += 1
        
        logger.info(f"[EntityCandidate] Discovered {discovered} from {processed} funding rounds")
        return {
            "discovered": discovered,
            "processed": processed,
            "source": "funding"
        }
    
    def _extract_entity_mentions(self, text: str) -> List[str]:
        """Extract potential entity mentions from text using patterns"""
        mentions = []
        
        # Pattern for capitalized multi-word names
        pattern = r'\b([A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)+)\b'
        matches = re.findall(pattern, text)
        
        for match in matches:
            # Filter out common non-entities
            if len(match) >= 5 and not self._is_common_phrase(match):
                mentions.append(match)
        
        return mentions[:10]  # Limit per text
    
    def _is_common_phrase(self, phrase: str) -> bool:
        """Check if phrase is a common non-entity phrase"""
        common = [
            "New York", "San Francisco", "Los Angeles", "United States",
            "Breaking News", "Read More", "Click Here", "Learn More",
            "Market Update", "Price Analysis", "Technical Analysis"
        ]
        return phrase in common
    
    async def seed_known_entities(self) -> Dict[str, Any]:
        """Seed high-confidence known entities as candidates"""
        seeded = 0
        
        for entity_type, names in SEED_ENTITIES.items():
            for name in names:
                result = await self.add_candidate(
                    name=name,
                    entity_type=entity_type,
                    source_type="seed",
                    confidence=0.9
                )
                if result and result.get("created"):
                    seeded += 1
        
        logger.info(f"[EntityCandidate] Seeded {seeded} known entities")
        return {"seeded": seeded}
    
    async def validate_candidates(self, limit: int = 50) -> Dict[str, Any]:
        """
        Validate candidates with full quality gate pipeline:
        1. Canonical entity check (prevent duplicates)
        2. Provider validation (CryptoRank, RootData, CoinGecko)
        3. Confidence scoring
        4. Approve/reject based on threshold
        """
        from modules.knowledge_graph.provider_validation_service import get_provider_validation_service
        from modules.knowledge_graph.entity_confidence_service import get_entity_confidence_service
        
        now = datetime.now(timezone.utc)
        processed = 0
        approved = 0
        rejected = 0
        skipped = 0
        
        # Initialize services
        provider_service = get_provider_validation_service(self.db)
        confidence_service = get_entity_confidence_service(self.db)
        
        # Get pending candidates with sufficient mentions or confidence
        cursor = self.candidates.find({
            "status": "candidate",
            "$or": [
                {"confidence": {"$gte": 0.5}},
                {"mention_count": {"$gte": 2}}
            ]
        }).sort([("mention_count", -1), ("confidence", -1)]).limit(limit)
        
        async for candidate in cursor:
            processed += 1
            name = candidate.get("name", "")
            entity_type = candidate.get("entity_type_guess", "project")
            
            try:
                # Step 1: Canonical entity check
                # Check if entity already exists in graph_nodes or aliases
                canonical_match = await self._check_canonical_entity(name, entity_type)
                if canonical_match:
                    # Entity already exists - merge alias and mark as duplicate
                    await self.candidates.update_one(
                        {"_id": candidate["_id"]},
                        {
                            "$set": {
                                "status": "merged",
                                "merged_into": canonical_match["entity_id"],
                                "merged_at": now
                            }
                        }
                    )
                    skipped += 1
                    logger.debug(f"[Validation] Skipped {name} - merged into {canonical_match['entity_id']}")
                    continue
                
                # Step 2: Provider validation
                validation_result = await provider_service.validate_entity(name, entity_type)
                
                # Update candidate with provider matches
                if validation_result.get("validated"):
                    await self.candidates.update_one(
                        {"_id": candidate["_id"]},
                        {
                            "$set": {
                                "provider_matches": validation_result.get("provider_matches", []),
                                "entity_type_guess": validation_result.get("confirmed_type", entity_type)
                            }
                        }
                    )
                    # Refresh candidate data
                    candidate["provider_matches"] = validation_result.get("provider_matches", [])
                    candidate["entity_type_guess"] = validation_result.get("confirmed_type", entity_type)
                
                # Step 3: Calculate confidence
                confidence_result = await confidence_service.calculate_confidence(
                    candidate, 
                    validation_result
                )
                
                # Step 4: Approve or reject
                if confidence_result["should_create"]:
                    # Create entity
                    entity_created = await self._create_approved_entity(
                        candidate, 
                        confidence_result,
                        validation_result
                    )
                    
                    if entity_created:
                        await self.candidates.update_one(
                            {"_id": candidate["_id"]},
                            {
                                "$set": {
                                    "status": "approved",
                                    "confidence": confidence_result["confidence_score"],
                                    "confidence_tier": confidence_result["confidence_tier"],
                                    "approved_at": now
                                }
                            }
                        )
                        approved += 1
                        logger.info(f"[Validation] Approved: {name} (conf: {confidence_result['confidence_score']:.2f})")
                else:
                    # Check if should reject or keep as candidate
                    if confidence_result["confidence_score"] < 0.60:
                        await self.candidates.update_one(
                            {"_id": candidate["_id"]},
                            {
                                "$set": {
                                    "status": "rejected",
                                    "confidence": confidence_result["confidence_score"],
                                    "rejection_reason": "low_confidence",
                                    "rejected_at": now
                                }
                            }
                        )
                        rejected += 1
                        logger.debug(f"[Validation] Rejected: {name} (conf: {confidence_result['confidence_score']:.2f})")
                    else:
                        # Update confidence but keep as candidate for more evidence
                        await self.candidates.update_one(
                            {"_id": candidate["_id"]},
                            {
                                "$set": {
                                    "confidence": confidence_result["confidence_score"],
                                    "confidence_tier": confidence_result["confidence_tier"],
                                    "last_validated_at": now
                                }
                            }
                        )
                
            except Exception as e:
                logger.error(f"[Validation] Error validating {name}: {e}")
                continue
        
        # Calculate quality ratio
        total_candidates = await self.candidates.count_documents({})
        total_approved = await self.candidates.count_documents({"status": "approved"})
        quality_ratio = total_approved / total_candidates if total_candidates > 0 else 0
        
        logger.info(f"[Validation] Processed {processed}: approved={approved}, rejected={rejected}, merged={skipped}")
        logger.info(f"[Validation] Quality ratio: {quality_ratio:.2%}")
        
        return {
            "processed": processed,
            "approved": approved,
            "rejected": rejected,
            "merged": skipped,
            "quality_ratio": round(quality_ratio, 3)
        }
    
    async def _check_canonical_entity(self, name: str, entity_type: str) -> Optional[Dict]:
        """Check if entity already exists (prevent duplicates)"""
        normalized = self.normalize_name(name)
        slug = self.to_slug(name)
        
        # Check graph_nodes
        node = await self.graph_nodes.find_one({
            "$or": [
                {"entity_id": slug},
                {"entity_id": normalized.replace(' ', '-')},
                {"entity_id": normalized.replace(' ', '_')},
                {"label": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}
            ]
        })
        if node:
            return {
                "entity_id": node.get("entity_id") or node.get("id"),
                "source": "graph_nodes"
            }
        
        # Check aliases
        alias = await self.entity_aliases.find_one({
            "normalized_alias": normalized
        })
        if alias:
            return {
                "entity_id": alias.get("entity_id"),
                "source": "aliases"
            }
        
        return None
    
    async def _create_approved_entity(
        self, 
        candidate: Dict, 
        confidence_result: Dict,
        validation_result: Dict
    ) -> bool:
        """Create entity in graph_nodes and related collections"""
        now = datetime.now(timezone.utc)
        name = candidate.get("name", "")
        entity_type = candidate.get("entity_type_guess", "project")
        normalized = self.normalize_name(name)
        slug = self.to_slug(name)
        
        try:
            # Create canonical entity ID
            entity_id = f"{entity_type}:{slug}"
            
            # Create graph node
            node = {
                "id": entity_id,
                "entity_type": entity_type,
                "entity_id": slug,
                "label": name,
                "metadata": {
                    "source": "entity_discovery",
                    "confidence": confidence_result["confidence_score"],
                    "confidence_tier": confidence_result["confidence_tier"],
                    "provider_matches": validation_result.get("provider_matches", []),
                    "created_from_candidate": True
                },
                "created_at": now
            }
            
            await self.graph_nodes.update_one(
                {"id": entity_id},
                {"$set": node},
                upsert=True
            )
            
            # Add primary alias
            await self.entity_aliases.update_one(
                {"entity_type": entity_type, "normalized_alias": normalized},
                {
                    "$set": {
                        "entity_type": entity_type,
                        "entity_id": slug,
                        "alias": name,
                        "normalized_alias": normalized,
                        "source": "entity_approval",
                        "confidence": confidence_result["confidence_score"],
                        "created_at": now
                    }
                },
                upsert=True
            )
            
            # Add additional aliases from candidate
            for alias in candidate.get("aliases", []):
                if alias != name:
                    alias_norm = self.normalize_name(alias)
                    await self.entity_aliases.update_one(
                        {"entity_type": entity_type, "normalized_alias": alias_norm},
                        {
                            "$set": {
                                "entity_type": entity_type,
                                "entity_id": slug,
                                "alias": alias,
                                "normalized_alias": alias_norm,
                                "source": "entity_approval",
                                "confidence": confidence_result["confidence_score"] * 0.9,
                                "created_at": now
                            }
                        },
                        upsert=True
                    )
            
            # Save confidence record
            from modules.knowledge_graph.entity_confidence_service import get_entity_confidence_service
            confidence_service = get_entity_confidence_service(self.db)
            await confidence_service.save_confidence(entity_id, entity_type, confidence_result)
            
            logger.info(f"[EntityApproval] Created entity: {entity_id}")
            return True
            
        except Exception as e:
            logger.error(f"[EntityApproval] Failed to create entity {name}: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get candidate statistics"""
        pipeline = [
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]
        
        status_counts = await self.candidates.aggregate(pipeline).to_list(10)
        
        type_pipeline = [
            {"$group": {
                "_id": "$entity_type_guess",
                "count": {"$sum": 1}
            }}
        ]
        
        type_counts = await self.candidates.aggregate(type_pipeline).to_list(10)
        
        return {
            "by_status": {s["_id"]: s["count"] for s in status_counts},
            "by_type": {t["_id"]: t["count"] for t in type_counts},
            "total": await self.candidates.count_documents({})
        }
    
    async def run_discovery_job(self) -> Dict[str, Any]:
        """Run full discovery job - called by scheduler"""
        results = {
            "articles": await self.discover_from_articles(),
            "funding": await self.discover_from_funding(),
            "validation": await self.validate_candidates()
        }
        
        return results


# Singleton
_candidate_discovery: Optional[EntityCandidateDiscovery] = None


def get_entity_candidate_discovery(db: AsyncIOMotorDatabase = None) -> EntityCandidateDiscovery:
    """Get or create candidate discovery engine"""
    global _candidate_discovery
    if db is not None:
        _candidate_discovery = EntityCandidateDiscovery(db)
    return _candidate_discovery
