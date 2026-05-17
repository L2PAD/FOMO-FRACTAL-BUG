"""
Entity Narrative Score Engine
==============================

Правильный pipeline для расчёта narrative alignment:

Entity → Event → Topic → Narrative

НЕ напрямую Entity → Narrative!

Формула:
narrative_score = Σ (event_importance × topic_relevance × recency_decay)

Пример flow:
1. Article: "BlackRock files Ethereum ETF"
2. Event: ethereum_etf_filing
3. Topic: ETF
4. Narrative: Institutional Adoption
5. Entities: [BlackRock, Ethereum, SEC, Nasdaq]

Collections:
    entity_narrative_scores - Narrative scores per entity
    entity_narrative_history - Historical scores for trends
"""

import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Decay rate for recency (half-life in days)
RECENCY_DECAY_HALFLIFE = 7  # 7 days half-life

# Active narratives to track
NARRATIVE_DEFINITIONS = {
    # ═══════════════════════════════════════════════════════════════
    # INSTITUTIONAL & REGULATORY
    # ═══════════════════════════════════════════════════════════════
    "institutional_adoption": {
        "name": "Institutional Adoption",
        "icon": "🏦",
        "color": "#3B82F6",
        "keywords": ["etf", "blackrock", "fidelity", "institutional", "sec", "nasdaq", "custody", "grayscale", "wall street"],
        "topics": ["etf", "blackrock_etf", "grayscale_etf", "sec_action"],
        "entities": ["blackrock", "fidelity", "grayscale", "coinbase", "bitwise"]
    },
    "regulation": {
        "name": "Regulation",
        "icon": "⚖️",
        "color": "#EF4444",
        "keywords": ["regulation", "sec", "cftc", "lawsuit", "enforcement", "compliance", "license", "legal"],
        "topics": ["sec_action", "binance_regulation"],
        "entities": ["sec", "cftc"]
    },
    
    # ═══════════════════════════════════════════════════════════════
    # AI & COMPUTE
    # ═══════════════════════════════════════════════════════════════
    "ai_crypto": {
        "name": "AI x Crypto",
        "icon": "🤖",
        "color": "#8B5CF6",
        "keywords": ["ai", "artificial intelligence", "machine learning", "gpu", "compute", "llm", "inference", "training"],
        "topics": ["ai_crypto"],
        "entities": ["tao", "bittensor", "fetch-ai", "fet", "render", "rndr", "ocean", "near", "akash", "io-net", "grass", "worldcoin"]
    },
    
    # ═══════════════════════════════════════════════════════════════
    # TOKENIZATION & RWA
    # ═══════════════════════════════════════════════════════════════
    "rwa": {
        "name": "Real World Assets",
        "icon": "🏠",
        "color": "#10B981",
        "keywords": ["rwa", "real world", "tokenized", "treasury", "bonds", "real estate", "commodities", "securities"],
        "entities": ["ondo", "centrifuge", "maple", "goldfinch", "maker", "frax", "mountain-protocol"]
    },
    
    # ═══════════════════════════════════════════════════════════════
    # STAKING & LIQUID STAKING
    # ═══════════════════════════════════════════════════════════════
    "restaking": {
        "name": "Restaking",
        "icon": "🔄",
        "color": "#F59E0B",
        "keywords": ["restaking", "eigenlayer", "liquid restaking", "avs", "operator", "lrt"],
        "entities": ["eigenlayer", "ether-fi", "etherfi", "renzo", "puffer", "kelp", "swell", "pendle"]
    },
    "liquid_staking": {
        "name": "Liquid Staking",
        "icon": "💧",
        "color": "#06B6D4",
        "keywords": ["liquid staking", "steth", "lsd", "staking derivative", "lido", "rocket pool"],
        "entities": ["lido", "rocket-pool", "frax-ether", "coinbase-wrapped-staked-eth", "mantle-staked-ether"]
    },
    
    # ═══════════════════════════════════════════════════════════════
    # INFRASTRUCTURE
    # ═══════════════════════════════════════════════════════════════
    "depin": {
        "name": "DePIN",
        "icon": "📡",
        "color": "#EC4899",
        "keywords": ["depin", "physical infrastructure", "iot", "wireless", "storage", "bandwidth", "network"],
        "entities": ["helium", "hivemapper", "render", "filecoin", "arweave", "theta", "livepeer", "akash", "io-net"]
    },
    "data_availability": {
        "name": "Data Availability",
        "icon": "📊",
        "color": "#6366F1",
        "keywords": ["data availability", "da", "celestia", "eigenda", "avail", "modular"],
        "entities": ["celestia", "avail", "near"]
    },
    
    # ═══════════════════════════════════════════════════════════════
    # SCALING
    # ═══════════════════════════════════════════════════════════════
    "l2": {
        "name": "Layer 2",
        "icon": "⚡",
        "color": "#3B82F6",
        "keywords": ["l2", "layer 2", "rollup", "optimistic", "zk", "scaling", "sequencer"],
        "topics": ["l2_launch", "l2_airdrop"],
        "entities": ["arbitrum", "optimism", "base", "zksync", "starknet", "linea", "scroll", "blast", "manta", "mode", "taiko"]
    },
    "zk": {
        "name": "Zero Knowledge",
        "icon": "🔐",
        "color": "#7C3AED",
        "keywords": ["zk", "zero knowledge", "zkp", "snark", "stark", "zkvm", "zkevm", "privacy"],
        "entities": ["zksync", "starknet", "polygon-zkevm", "scroll", "risc-zero", "succinct"]
    },
    "bitcoin_l2": {
        "name": "Bitcoin L2",
        "icon": "₿",
        "color": "#F7931A",
        "keywords": ["bitcoin l2", "bitcoin layer 2", "ordinals", "brc20", "runes", "bitvm", "bitcoin defi"],
        "entities": ["stacks", "lightning", "rsk", "liquid-network", "merlin-chain", "bob"]
    },
    
    # ═══════════════════════════════════════════════════════════════
    # DEFI
    # ═══════════════════════════════════════════════════════════════
    "defi": {
        "name": "DeFi",
        "icon": "🏛️",
        "color": "#14B8A6",
        "keywords": ["defi", "lending", "borrowing", "dex", "amm", "yield", "liquidity", "tvl"],
        "topics": ["defi_exploit", "defi_tvl"],
        "entities": ["uniswap", "aave", "compound", "maker", "curve", "lido", "gmx", "dydx", "synthetix", "balancer"]
    },
    "perps_dex": {
        "name": "Perps & DEX",
        "icon": "📈",
        "color": "#22C55E",
        "keywords": ["perpetual", "perps", "futures", "derivatives", "dex", "decentralized exchange"],
        "entities": ["gmx", "dydx", "hyperliquid", "vertex", "drift", "jupiter", "raydium"]
    },
    "stablecoins": {
        "name": "Stablecoins",
        "icon": "💵",
        "color": "#059669",
        "keywords": ["stablecoin", "usdt", "usdc", "dai", "frax", "algorithmic", "fiat-backed"],
        "topics": ["stablecoin_depeg", "stablecoin_regulation"],
        "entities": ["tether", "circle", "maker", "frax", "ethena", "usual"]
    },
    
    # ═══════════════════════════════════════════════════════════════
    # SOCIAL & CONSUMER
    # ═══════════════════════════════════════════════════════════════
    "social": {
        "name": "SocialFi",
        "icon": "👥",
        "color": "#A855F7",
        "keywords": ["social", "socialfi", "friend.tech", "lens", "farcaster", "creator", "community"],
        "entities": ["lens-protocol", "farcaster", "friend-tech", "deso"]
    },
    "gaming": {
        "name": "Gaming",
        "icon": "🎮",
        "color": "#EF4444",
        "keywords": ["gaming", "p2e", "play to earn", "gamefi", "metaverse", "nft game"],
        "entities": ["axie-infinity", "illuvium", "gala", "immutable", "ronin", "beam", "pixels", "big-time"]
    },
    "memecoins": {
        "name": "Memecoins",
        "icon": "🐕",
        "color": "#FBBF24",
        "keywords": ["meme", "memecoin", "doge", "shib", "pepe", "pump", "pump.fun"],
        "entities": ["dogecoin", "shiba-inu", "pepe", "bonk", "wif", "floki", "brett"]
    },
    
    # ═══════════════════════════════════════════════════════════════
    # SOLANA ECOSYSTEM
    # ═══════════════════════════════════════════════════════════════
    "solana_ecosystem": {
        "name": "Solana Ecosystem",
        "icon": "☀️",
        "color": "#9945FF",
        "keywords": ["solana", "sol", "spl", "blink", "actions", "compressed nft"],
        "entities": ["solana", "jupiter", "raydium", "marinade", "jito", "tensor", "magic-eden", "phantom"]
    },
    
    # ═══════════════════════════════════════════════════════════════
    # CROSS-CHAIN & INTEROP
    # ═══════════════════════════════════════════════════════════════
    "interoperability": {
        "name": "Interoperability",
        "icon": "🌉",
        "color": "#64748B",
        "keywords": ["bridge", "cross-chain", "interop", "messaging", "ccip", "layerzero", "wormhole"],
        "entities": ["layerzero", "wormhole", "axelar", "chainlink", "stargate", "across"]
    },
    
    # ═══════════════════════════════════════════════════════════════
    # INTENT & ABSTRACTION
    # ═══════════════════════════════════════════════════════════════
    "intent": {
        "name": "Intent & Abstraction",
        "icon": "🎯",
        "color": "#0EA5E9",
        "keywords": ["intent", "account abstraction", "erc4337", "smart account", "gasless", "paymaster"],
        "entities": ["cowswap", "1inch", "uniswap-x", "across", "safe"]
    }
}


class EntityNarrativeScoreEngine:
    """
    Engine for calculating entity narrative scores through events.
    
    Pipeline:
    events → topics → narratives → entity_scores
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        
        # Main collections
        self.entity_scores = db.entity_narrative_scores
        self.entity_history = db.entity_narrative_history
        
        # Source collections
        self.events = db.news_events
        self.root_events = db.root_events
        self.event_entities = db.event_entities
        self.topics = db.topics
        self.topic_events = db.topic_events
        self.graph_nodes = db.graph_nodes
        self.narratives = db.narratives
    
    async def ensure_indexes(self):
        """Create necessary indexes."""
        await self.entity_scores.create_index("entity_key", unique=True)
        await self.entity_scores.create_index("entity_type")
        await self.entity_scores.create_index("total_score")
        await self.entity_scores.create_index([("narratives.score", -1)])
        
        await self.entity_history.create_index([("entity_key", 1), ("date", -1)])
        await self.entity_history.create_index("date")
        
        logger.info("[NarrativeScoreEngine] Indexes created")
    
    # ═══════════════════════════════════════════════════════════════
    # CORE CALCULATION
    # ═══════════════════════════════════════════════════════════════
    
    async def calculate_entity_narrative_score(
        self,
        entity_type: str,
        entity_id: str
    ) -> Dict[str, Any]:
        """
        Calculate narrative scores for an entity through events.
        
        Pipeline:
        1. Get all events mentioning this entity
        2. For each event, get its topics
        3. Map topics to narratives
        4. Calculate weighted score with recency decay
        """
        entity_key = f"{entity_type}:{entity_id}"
        now = datetime.now(timezone.utc)
        
        # Step 1: Get events for this entity (last 30 days)
        cutoff = now - timedelta(days=30)
        entity_events = await self._get_entity_events(entity_type, entity_id, cutoff)
        
        # Step 2 & 3: Calculate narrative scores from events
        narrative_scores = {}
        event_narrative_links = []
        
        for event in entity_events:
            event_date = event.get("event_date") or event.get("created_at") or now
            if isinstance(event_date, str):
                try:
                    event_date = datetime.fromisoformat(event_date.replace("Z", "+00:00"))
                except:
                    event_date = now
            
            # Ensure timezone aware
            if event_date.tzinfo is None:
                event_date = event_date.replace(tzinfo=timezone.utc)
            
            event_importance = event.get("importance_score", 50) / 100
            
            # Get topics for this event
            topics = await self._get_event_topics(event.get("event_id") or event.get("id"))
            
            # Map topics to narratives
            for topic in topics:
                topic_relevance = topic.get("relevance_score", 0.5)
                
                # Find narrative for this topic
                narrative_id = await self._map_topic_to_narrative(topic)
                
                if narrative_id:
                    # Calculate recency decay
                    days_old = (now - event_date).total_seconds() / 86400
                    recency_decay = self._calculate_decay(days_old)
                    
                    # Final contribution
                    contribution = event_importance * topic_relevance * recency_decay
                    
                    if narrative_id not in narrative_scores:
                        narrative_scores[narrative_id] = {
                            "score": 0,
                            "event_count": 0,
                            "topics": set()
                        }
                    
                    narrative_scores[narrative_id]["score"] += contribution
                    narrative_scores[narrative_id]["event_count"] += 1
                    narrative_scores[narrative_id]["topics"].add(topic.get("name", "unknown"))
                    
                    event_narrative_links.append({
                        "event_id": event.get("event_id") or event.get("id"),
                        "narrative_id": narrative_id,
                        "contribution": contribution
                    })
        
        # Also check direct narrative definitions
        for narr_id, narr_def in NARRATIVE_DEFINITIONS.items():
            direct_score = self._check_direct_narrative_match(entity_id, narr_def)
            if direct_score > 0:
                if narr_id not in narrative_scores:
                    narrative_scores[narr_id] = {
                        "score": 0,
                        "event_count": 0,
                        "topics": set()
                    }
                narrative_scores[narr_id]["score"] += direct_score * 0.5  # Boost for direct match
        
        # Calculate total and normalize
        total_score = sum(n["score"] for n in narrative_scores.values())
        max_possible = len(NARRATIVE_DEFINITIONS)  # Theoretical max
        normalized_total = min(100, (total_score / max_possible) * 100) if max_possible > 0 else 0
        
        # Build final result
        narratives_list = []
        for narr_id, data in sorted(narrative_scores.items(), key=lambda x: x[1]["score"], reverse=True):
            narr_name = NARRATIVE_DEFINITIONS.get(narr_id, {}).get("name", narr_id)
            narratives_list.append({
                "id": narr_id,
                "name": narr_name,
                "score": round(data["score"] * 100, 2),  # Scale to 0-100
                "event_count": data["event_count"],
                "topics": list(data["topics"])[:5]
            })
        
        # Determine dominant narrative
        dominant_narrative = narratives_list[0]["id"] if narratives_list else None
        
        result = {
            "entity_key": entity_key,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "total_score": round(normalized_total, 2),
            "narrative_count": len(narratives_list),
            "dominant_narrative": dominant_narrative,
            "narratives": narratives_list[:10],  # Top 10
            "event_count": len(entity_events),
            "updated_at": now.isoformat()
        }
        
        # Store result
        await self.entity_scores.update_one(
            {"entity_key": entity_key},
            {"$set": result},
            upsert=True
        )
        
        # Store history
        await self._store_history(entity_key, normalized_total, dominant_narrative)
        
        logger.debug(f"[NarrativeScoreEngine] {entity_key}: score={normalized_total:.1f}, narratives={len(narratives_list)}")
        
        return result
    
    async def _get_entity_events(
        self,
        entity_type: str,
        entity_id: str,
        since: datetime
    ) -> List[Dict]:
        """Get all events mentioning this entity."""
        entity_key = f"{entity_type}:{entity_id}"
        events = []
        
        # Check event_entities collection
        cursor = self.event_entities.find({
            "entity_key": entity_key,
            "event_date": {"$gte": since}
        }).limit(100)
        
        async for link in cursor:
            event = await self.events.find_one({"id": link.get("event_id")})
            if event:
                event["event_date"] = link.get("event_date")
                events.append(event)
        
        # Also check news_events primary_assets
        cursor = self.events.find({
            "primary_assets": {"$regex": entity_id, "$options": "i"},
            "created_at": {"$gte": since}
        }).limit(100)
        
        async for event in cursor:
            events.append(event)
        
        # Check root_events
        cursor = self.root_events.find({
            "entities": {"$regex": entity_id, "$options": "i"},
            "first_seen": {"$gte": since}
        }).limit(50)
        
        async for event in cursor:
            event["event_date"] = event.get("first_seen")
            events.append(event)
        
        return events
    
    async def _get_event_topics(self, event_id: str) -> List[Dict]:
        """Get topics linked to an event."""
        if not event_id:
            return []
        
        # Check topic_events
        cursor = self.topic_events.find({"event_id": event_id})
        topic_links = await cursor.to_list(20)
        
        topics = []
        for link in topic_links:
            topic = await self.topics.find_one({"id": link.get("topic_id")})
            if topic:
                topic["relevance_score"] = link.get("relevance_score", 0.5)
                topics.append(topic)
        
        return topics
    
    async def _map_topic_to_narrative(self, topic: Dict) -> Optional[str]:
        """Map a topic to a narrative ID."""
        # First check if topic has narrative_id
        if topic.get("narrative_id"):
            return topic.get("narrative_id")
        
        # Otherwise, match by keywords
        topic_name = topic.get("name", "").lower()
        topic_keywords = [k.lower() for k in topic.get("keywords", [])]
        
        for narr_id, narr_def in NARRATIVE_DEFINITIONS.items():
            narr_keywords = [k.lower() for k in narr_def.get("keywords", [])]
            narr_topics = [t.lower() for t in narr_def.get("topics", [])]
            
            # Check direct topic match
            if topic.get("canonical_name") in narr_topics:
                return narr_id
            
            # Check keyword overlap
            overlap = set(topic_keywords) & set(narr_keywords)
            if overlap:
                return narr_id
            
            # Check name match
            for kw in narr_keywords:
                if kw in topic_name:
                    return narr_id
        
        return None
    
    def _check_direct_narrative_match(self, entity_id: str, narr_def: Dict) -> float:
        """Check if entity directly matches narrative definition."""
        narr_entities = [e.lower() for e in narr_def.get("entities", [])]
        
        if entity_id.lower() in narr_entities:
            return 1.0
        
        return 0
    
    def _calculate_decay(self, days_old: float) -> float:
        """Calculate recency decay using exponential decay."""
        # decay = 0.5 ^ (days / half_life)
        return math.pow(0.5, days_old / RECENCY_DECAY_HALFLIFE)
    
    async def _store_history(
        self,
        entity_key: str,
        score: float,
        dominant_narrative: str
    ):
        """Store score in history for trend tracking."""
        now = datetime.now(timezone.utc)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        history = {
            "entity_key": entity_key,
            "date": today,
            "score": score,
            "dominant_narrative": dominant_narrative
        }
        
        await self.entity_history.update_one(
            {"entity_key": entity_key, "date": today},
            {"$set": history},
            upsert=True
        )
    
    # ═══════════════════════════════════════════════════════════════
    # BATCH UPDATE
    # ═══════════════════════════════════════════════════════════════
    
    async def update_all_entities(
        self,
        entity_types: List[str] = None,
        limit: int = 300
    ) -> Dict[str, Any]:
        """Batch update narrative scores for all entities."""
        start = datetime.now(timezone.utc)
        
        if entity_types is None:
            entity_types = ["project", "fund", "exchange"]
        
        results = {
            "processed": 0,
            "with_narratives": 0,
            "errors": 0,
            "by_type": {}
        }
        
        for entity_type in entity_types:
            type_count = 0
            
            cursor = self.graph_nodes.find({
                "entity_type": entity_type
            }).limit(limit // len(entity_types))
            
            async for node in cursor:
                try:
                    score_result = await self.calculate_entity_narrative_score(
                        entity_type,
                        node.get("entity_id")
                    )
                    
                    results["processed"] += 1
                    type_count += 1
                    
                    if score_result.get("narrative_count", 0) > 0:
                        results["with_narratives"] += 1
                        
                except Exception as e:
                    logger.error(f"[NarrativeScoreEngine] Error for {node.get('entity_id')}: {e}")
                    results["errors"] += 1
            
            results["by_type"][entity_type] = type_count
        
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        results["elapsed_seconds"] = round(elapsed, 2)
        
        logger.info(
            f"[NarrativeScoreEngine] Updated {results['processed']} entities "
            f"({results['with_narratives']} with narratives) in {elapsed:.1f}s"
        )
        
        return results
    
    # ═══════════════════════════════════════════════════════════════
    # QUERY METHODS
    # ═══════════════════════════════════════════════════════════════
    
    async def get_entity_score(
        self,
        entity_type: str,
        entity_id: str
    ) -> Optional[Dict]:
        """Get narrative score for an entity."""
        entity_key = f"{entity_type}:{entity_id}"
        
        score = await self.entity_scores.find_one(
            {"entity_key": entity_key},
            {"_id": 0}
        )
        
        if not score:
            # Calculate on demand
            score = await self.calculate_entity_narrative_score(entity_type, entity_id)
        
        return score
    
    async def get_narrative_leaders(
        self,
        narrative_id: str,
        limit: int = 10
    ) -> List[Dict]:
        """
        Get top entities for a specific narrative.
        
        This answers: "Who dominates this narrative?"
        """
        cursor = self.entity_scores.find(
            {"dominant_narrative": narrative_id},
            {"_id": 0}
        ).sort("total_score", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_narrative_dominance(self) -> Dict[str, Dict]:
        """
        Get narrative dominance map.
        
        Returns: {narrative_id: {leader: entity, score: float}}
        """
        dominance = {}
        
        for narr_id, narr_def in NARRATIVE_DEFINITIONS.items():
            leaders = await self.get_narrative_leaders(narr_id, 1)
            
            if leaders:
                leader = leaders[0]
                dominance[narr_id] = {
                    "narrative_name": narr_def["name"],
                    "leader": leader.get("entity_id"),
                    "leader_type": leader.get("entity_type"),
                    "score": leader.get("total_score", 0)
                }
            else:
                # Check if any entity has this narrative in their list
                cursor = self.entity_scores.find({
                    "narratives.id": narr_id
                }).sort("narratives.score", -1).limit(1)
                
                alt_leaders = await cursor.to_list(1)
                if alt_leaders:
                    leader = alt_leaders[0]
                    dominance[narr_id] = {
                        "narrative_name": narr_def["name"],
                        "leader": leader.get("entity_id"),
                        "leader_type": leader.get("entity_type"),
                        "score": next(
                            (n["score"] for n in leader.get("narratives", []) if n["id"] == narr_id),
                            0
                        )
                    }
                else:
                    dominance[narr_id] = {
                        "narrative_name": narr_def["name"],
                        "leader": None,
                        "leader_type": None,
                        "score": 0
                    }
        
        return dominance
    
    async def get_entity_trend(
        self,
        entity_type: str,
        entity_id: str,
        days: int = 30
    ) -> List[Dict]:
        """Get narrative score history for trend analysis."""
        entity_key = f"{entity_type}:{entity_id}"
        since = datetime.now(timezone.utc) - timedelta(days=days)
        
        cursor = self.entity_history.find(
            {"entity_key": entity_key, "date": {"$gte": since}},
            {"_id": 0}
        ).sort("date", 1)
        
        return await cursor.to_list(length=days)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        total = await self.entity_scores.count_documents({})
        with_narratives = await self.entity_scores.count_documents({"narrative_count": {"$gt": 0}})
        
        # Dominant narratives distribution
        pipeline = [
            {"$match": {"dominant_narrative": {"$ne": None}}},
            {"$group": {
                "_id": "$dominant_narrative",
                "count": {"$sum": 1},
                "avg_score": {"$avg": "$total_score"}
            }},
            {"$sort": {"count": -1}}
        ]
        
        narr_stats = await self.entity_scores.aggregate(pipeline).to_list(20)
        
        return {
            "total_entities": total,
            "with_narratives": with_narratives,
            "narratives_tracked": len(NARRATIVE_DEFINITIONS),
            "narrative_distribution": [
                {
                    "narrative": stat["_id"],
                    "name": NARRATIVE_DEFINITIONS.get(stat["_id"], {}).get("name", stat["_id"]),
                    "entities": stat["count"],
                    "avg_score": round(stat["avg_score"], 1)
                }
                for stat in narr_stats
            ]
        }


# ═══════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════

_narrative_engine: Optional[EntityNarrativeScoreEngine] = None


def get_narrative_score_engine(db: AsyncIOMotorDatabase = None) -> EntityNarrativeScoreEngine:
    """Get or create narrative score engine."""
    global _narrative_engine
    if db is not None:
        _narrative_engine = EntityNarrativeScoreEngine(db)
    return _narrative_engine
