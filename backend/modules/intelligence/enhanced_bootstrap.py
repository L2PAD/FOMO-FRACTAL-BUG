"""
Enhanced Architecture Bootstrap

Initializes all new architectural components:
- Feed projection indexes
- Observability indexes
- Narrative lifecycle snapshots
- Entity alias seeding
"""

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def bootstrap_enhanced_architecture(db):
    """
    Bootstrap enhanced architecture components
    
    Called on server startup after base bootstrap
    """
    logger.info("=" * 60)
    logger.info("[ENHANCED BOOTSTRAP] Starting...")
    logger.info("=" * 60)
    
    try:
        # 1. Feed Projection Indexes
        logger.info("[ENHANCED BOOTSTRAP] Creating feed projection indexes...")
        await _setup_feed_indexes(db)
        
        # 2. Observability Indexes
        logger.info("[ENHANCED BOOTSTRAP] Creating observability indexes...")
        await _setup_observability_indexes(db)
        
        # 3. Enhanced Root Event Indexes
        logger.info("[ENHANCED BOOTSTRAP] Creating enhanced event indexes...")
        await _setup_event_indexes(db)
        
        # 4. Narrative Lifecycle Indexes
        logger.info("[ENHANCED BOOTSTRAP] Creating narrative lifecycle indexes...")
        await _setup_narrative_indexes(db)
        
        # 5. Conflict Strategy Collection
        logger.info("[ENHANCED BOOTSTRAP] Initializing conflict strategies...")
        await _init_conflict_strategies(db)
        
        logger.info("=" * 60)
        logger.info("[ENHANCED BOOTSTRAP] Complete!")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"[ENHANCED BOOTSTRAP] Error: {e}")
        return False


async def _setup_feed_indexes(db):
    """Create feed card indexes for fast queries"""
    try:
        feed_cards = db.feed_cards
        
        # Basic indexes
        await feed_cards.create_index("id", unique=True)
        await feed_cards.create_index("root_event_id")
        await feed_cards.create_index("narrative_id")
        await feed_cards.create_index("card_type")
        await feed_cards.create_index("priority")
        await feed_cards.create_index("fomo_score")
        await feed_cards.create_index("event_time")
        await feed_cards.create_index("is_archived")
        
        # Entity symbol lookup
        await feed_cards.create_index([("entities.symbol", 1)])
        await feed_cards.create_index([("tags", 1)])
        
        # Compound indexes for feed queries
        await feed_cards.create_index([
            ("is_archived", 1),
            ("priority", -1),
            ("event_time", -1)
        ])
        await feed_cards.create_index([
            ("is_archived", 1),
            ("card_type", 1),
            ("event_time", -1)
        ])
        
        logger.info("  → Feed projection indexes created")
        
    except Exception as e:
        logger.error(f"  → Feed index error: {e}")


async def _setup_observability_indexes(db):
    """Create observability collection indexes"""
    try:
        # Source health
        await db.source_health.create_index("source_id", unique=True)
        await db.source_health.create_index("status")
        
        # Parser health
        await db.parser_health.create_index("parser_id", unique=True)
        
        # Drift alerts
        await db.drift_alerts.create_index("id", unique=True)
        await db.drift_alerts.create_index([("is_resolved", 1), ("severity", -1)])
        await db.drift_alerts.create_index("source_id")
        
        # System metrics
        await db.system_metrics.create_index("timestamp")
        
        # Provider scores
        await db.provider_scores.create_index("provider_id", unique=True)
        
        logger.info("  → Observability indexes created")
        
    except Exception as e:
        logger.error(f"  → Observability index error: {e}")


async def _setup_event_indexes(db):
    """Create enhanced root event indexes"""
    try:
        root_events = db.root_events
        
        # Entity-based queries
        await root_events.create_index([("event_entities.entity_id", 1)])
        await root_events.create_index([("event_entities.entity_type", 1)])
        await root_events.create_index([("event_entities.role", 1)])
        
        # Score-based queries
        await root_events.create_index("impact_score")
        await root_events.create_index("fomo_score")
        
        # Compound for entity feed
        await root_events.create_index([
            ("event_entities.entity_id", 1),
            ("last_updated", -1)
        ])
        
        logger.info("  → Enhanced event indexes created")
        
    except Exception as e:
        logger.error(f"  → Event index error: {e}")


async def _setup_narrative_indexes(db):
    """Create narrative lifecycle indexes"""
    try:
        narratives = db.narratives
        
        # Lifecycle queries
        await narratives.create_index("lifecycle_state")
        await narratives.create_index("momentum_velocity")
        await narratives.create_index("momentum_acceleration")
        
        # Compound for emerging detection
        await narratives.create_index([
            ("lifecycle_state", 1),
            ("momentum_velocity", -1)
        ])
        
        # Momentum snapshots
        await db.narrative_momentum_snapshots.create_index([
            ("narrative_id", 1),
            ("timestamp", -1)
        ])
        
        # Narrative entities
        await db.narrative_entities.create_index([
            ("narrative_id", 1),
            ("entity_id", 1)
        ], unique=True)
        await db.narrative_entities.create_index([
            ("narrative_id", 1),
            ("relevance_score", -1)
        ])
        
        logger.info("  → Narrative lifecycle indexes created")
        
    except Exception as e:
        logger.error(f"  → Narrative index error: {e}")


async def _init_conflict_strategies(db):
    """Initialize conflict strategy collection"""
    try:
        from modules.ownership.conflict_strategy import FIELD_CONFLICT_STRATEGY
        
        # Store strategies in DB for runtime access
        strategies_collection = db.field_conflict_strategies
        
        for field, rule in FIELD_CONFLICT_STRATEGY.items():
            await strategies_collection.update_one(
                {"field": field},
                {"$set": rule.dict()},
                upsert=True
            )
        
        logger.info(f"  → {len(FIELD_CONFLICT_STRATEGY)} conflict strategies initialized")
        
    except Exception as e:
        logger.error(f"  → Conflict strategy error: {e}")


# =============================================================================
# ENTITY ALIASES ENHANCEMENT
# =============================================================================

ADDITIONAL_ENTITY_ALIASES = {
    # Major exchanges
    "binance": ["binance", "bnb", "binance.com", "binance exchange"],
    "coinbase": ["coinbase", "cb", "coinbase exchange", "coinbase pro"],
    "kraken": ["kraken", "kraken exchange"],
    "bybit": ["bybit", "bybit exchange"],
    "okx": ["okx", "okex", "ok exchange"],
    
    # Major DeFi protocols
    "uniswap": ["uniswap", "uni", "uniswap v3", "uniswap v2"],
    "aave": ["aave", "aave protocol", "aave v3"],
    "compound": ["compound", "comp", "compound finance"],
    "makerdao": ["makerdao", "maker", "dai", "maker protocol"],
    "curve": ["curve", "crv", "curve finance"],
    "lido": ["lido", "lido finance", "steth", "lido staking"],
    
    # Layer 2s
    "arbitrum": ["arbitrum", "arb", "arbitrum one"],
    "optimism": ["optimism", "op", "optimism mainnet"],
    "base": ["base", "base chain", "coinbase base"],
    "polygon": ["polygon", "matic", "polygon pos"],
    "zksync": ["zksync", "zks", "zksync era"],
    
    # AI x Crypto
    "fetch.ai": ["fetch.ai", "fet", "fetch ai"],
    "bittensor": ["bittensor", "tao"],
    "render": ["render", "rndr", "render network"],
    "ocean": ["ocean", "ocean protocol"],
    
    # Stablecoins
    "tether": ["tether", "usdt", "tether usd"],
    "usdc": ["usdc", "usd coin", "circle usdc"],
    "dai": ["dai", "makerdao dai"],
    
    # Funds & VCs
    "a16z": ["a16z", "andreessen horowitz", "a16z crypto"],
    "paradigm": ["paradigm", "paradigm ventures"],
    "polychain": ["polychain", "polychain capital"],
    "multicoin": ["multicoin", "multicoin capital"],
    "pantera": ["pantera", "pantera capital"],
    "dragonfly": ["dragonfly", "dragonfly capital"],
    
    # Regulators
    "sec": ["sec", "securities and exchange commission", "us sec"],
    "cftc": ["cftc", "commodity futures trading commission"],
    "doj": ["doj", "department of justice"],
}


async def seed_additional_aliases(db):
    """Seed additional entity aliases"""
    try:
        aliases_collection = db.entity_aliases
        
        count = 0
        for entity_id, aliases in ADDITIONAL_ENTITY_ALIASES.items():
            for alias in aliases:
                await aliases_collection.update_one(
                    {"alias": alias.lower()},
                    {
                        "$set": {
                            "entity_id": entity_id,
                            "alias": alias.lower(),
                            "updated_at": datetime.now(timezone.utc)
                        }
                    },
                    upsert=True
                )
                count += 1
        
        logger.info(f"  → {count} additional aliases seeded")
        
    except Exception as e:
        logger.error(f"  → Alias seeding error: {e}")
