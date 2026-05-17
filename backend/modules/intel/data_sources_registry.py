"""
Data Sources Registry
=====================
Master registry of all data sources for FOMO Platform.
Tracks what sources are available, their capabilities, sync status, and priority.

Categories:
- funding: Investment rounds, VC data
- ico: Token sales, launchpads
- unlocks: Token unlock schedules
- activities: Airdrops, campaigns, testnets
- market: Price, volume, market data
- projects: Project info, profiles
- funds: Fund/VC profiles
- persons: Key people in crypto
- news: Crypto news feeds
- defi: DeFi protocols, TVL
"""

from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from pydantic import BaseModel
from enum import Enum


class SourceCategory(str, Enum):
    FUNDING = "funding"
    ICO = "ico"
    UNLOCKS = "unlocks"
    ACTIVITIES = "activities"
    MARKET = "market"
    PROJECTS = "projects"
    FUNDS = "funds"
    PERSONS = "persons"
    NEWS = "news"
    DEFI = "defi"
    ANALYTICS = "analytics"


class SourcePriority(str, Enum):
    """
    Priority determines sync frequency:
    - TIER1: every 5-10 min (core data)
    - TIER2: every 15 min (token/market)
    - TIER3: every 30 min (activities)
    - TIER4: every few hours (research)
    """
    TIER1 = "tier1"  # Core Data: CryptoRank, RootData, DefiLlama, Dropstab
    TIER2 = "tier2"  # Token/Market: CoinGecko, CoinMarketCap, TokenUnlocks
    TIER3 = "tier3"  # Activities: Dropsearn, ICO Drops, DappRadar, AirdropAlert
    TIER4 = "tier4"  # Research: Messari (optional, skip if no API)


class SourceStatus(str, Enum):
    ACTIVE = "active"      # Parser implemented and working
    PARTIAL = "partial"    # Some endpoints work
    PLANNED = "planned"    # Not implemented yet
    DISABLED = "disabled"  # Temporarily disabled


class DataSourceModel(BaseModel):
    """Schema for data source"""
    id: str
    name: str
    website: str
    categories: List[str]
    data_types: List[str]
    priority: str
    status: str
    has_api: bool
    api_key_required: bool
    rate_limit: Optional[str] = None
    parser_module: Optional[str] = None
    last_sync: Optional[str] = None
    sync_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    description: Optional[str] = None
    is_new: bool = False
    discovered_at: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# MASTER DATA SOURCES REGISTRY
# ═══════════════════════════════════════════════════════════════
# Pipeline: Parser → Public API → Admin API
# If source fails → skip → next source
# System NEVER depends on single source

DATA_SOURCES = [
    # ─────────────────────────────────────────────────────────────
    # TIER 1: CORE DATA (sync every 5-10 min)
    # Primary sources for: projects, funding, investors, protocols, ecosystem
    # ─────────────────────────────────────────────────────────────
    {
        "id": "cryptorank",
        "name": "CryptoRank",
        "website": "https://cryptorank.io",
        "categories": ["funding", "ico", "unlocks", "activities", "analytics", "persons"],
        "data_types": ["funding_rounds", "investors", "ico_calendar", "unlocks", "activities", "team_members"],
        "tier": 1,
        "priority": "tier1",
        "priority_score": 100,
        "status": "active",
        "has_api": True,
        "api_key_required": False,
        "rate_limit": "30 req/min",
        "parser_module": "parser_cryptorank",
        "sync_interval_min": 10,
        "description": "Core source: funding rounds, investors, ICO, unlocks"
    },
    {
        "id": "rootdata",
        "name": "RootData",
        "website": "https://rootdata.com",
        "categories": ["funding", "funds", "persons"],
        "data_types": ["funding_rounds", "investor_profiles", "team_members"],
        "tier": 1,
        "priority": "tier1",
        "priority_score": 95,
        "status": "active",
        "has_api": True,
        "api_key_required": False,
        "rate_limit": "20 req/min",
        "parser_module": "parser_rootdata",
        "sync_interval_min": 10,
        "description": "Core source: funding, funds, teams (person graph)"
    },
    {
        "id": "defillama",
        "name": "DefiLlama",
        "website": "https://defillama.com",
        "categories": ["defi", "projects", "analytics"],
        "data_types": ["tvl", "protocol_data", "yields", "bridges"],
        "tier": 1,
        "priority": "tier1",
        "priority_score": 90,
        "status": "active",
        "has_api": True,
        "api_key_required": False,
        "rate_limit": "100 req/min",
        "parser_module": "parser_defillama",
        "sync_interval_min": 5,
        "description": "Core source: DeFi TVL, protocols, ecosystem"
    },
    {
        "id": "dropstab",
        "name": "Dropstab",
        "website": "https://dropstab.com",
        "categories": ["activities"],
        "data_types": ["airdrops", "campaigns", "testnets", "points_programs"],
        "tier": 1,
        "priority": "tier1",
        "priority_score": 85,
        "status": "active",
        "has_api": False,
        "api_key_required": False,
        "rate_limit": "10 req/min",
        "parser_module": "parser_activities",
        "sync_interval_min": 10,
        "description": "Core source: activities, airdrops, testnets"
    },
    
    # ─────────────────────────────────────────────────────────────
    # TIER 2: TOKEN / MARKET DATA (sync every 15 min)
    # prices, marketcap, tokenomics, unlock schedules
    # CoinGecko/CMC: API if available, Parser if no API
    # ─────────────────────────────────────────────────────────────
    {
        "id": "coingecko",
        "name": "CoinGecko",
        "website": "https://coingecko.com",
        "categories": ["market", "projects", "analytics"],
        "data_types": ["prices", "market_cap", "volume", "project_info", "categories", "exchanges"],
        "tier": 2,
        "priority": "tier2",
        "priority_score": 80,
        "status": "active",
        "has_api": True,
        "api_key_required": False,
        "rate_limit": "50 req/min",
        "parser_module": "parser_coingecko",
        "sync_interval_min": 15,
        "description": "Market data: prices, volume, marketcap (API or Parser)"
    },
    {
        "id": "coinmarketcap",
        "name": "CoinMarketCap",
        "website": "https://coinmarketcap.com",
        "categories": ["market", "projects", "ico", "activities"],
        "data_types": ["prices", "market_cap", "volume", "ico_calendar", "airdrops"],
        "tier": 2,
        "priority": "tier2",
        "priority_score": 75,
        "status": "active",
        "has_api": True,
        "api_key_required": True,
        "rate_limit": "30 req/min",
        "parser_module": "parser_coinmarketcap",
        "sync_interval_min": 15,
        "description": "Market data: alternative source (API or Parser)"
    },
    {
        "id": "tokenunlocks",
        "name": "TokenUnlocks",
        "website": "https://token.unlocks.app",
        "categories": ["unlocks"],
        "data_types": ["unlock_schedules", "vesting_data", "cliff_dates"],
        "tier": 2,
        "priority": "tier2",
        "priority_score": 70,
        "status": "active",
        "has_api": True,
        "api_key_required": False,
        "rate_limit": "10 req/min",
        "parser_module": "parser_tokenunlocks",
        "sync_interval_min": 15,
        "description": "Token unlock schedules, vesting"
    },
    
    # ─────────────────────────────────────────────────────────────
    # TIER 3: ACTIVITIES / AIRDROPS (sync every 30 min)
    # airdrop campaigns, project activities, launches, events
    # ─────────────────────────────────────────────────────────────
    {
        "id": "dropsearn",
        "name": "DropsEarn",
        "website": "https://dropsearn.com",
        "categories": ["activities"],
        "data_types": ["airdrops", "campaigns", "testnets"],
        "tier": 3,
        "priority": "tier3",
        "priority_score": 60,
        "status": "active",
        "has_api": False,
        "api_key_required": False,
        "rate_limit": "10 req/min",
        "parser_module": "parser_activities",
        "sync_interval_min": 30,
        "description": "Activities: airdrop campaigns"
    },
    {
        "id": "icodrops",
        "name": "ICO Drops",
        "website": "https://icodrops.com",
        "categories": ["ico"],
        "data_types": ["ico_calendar", "token_sales", "launchpads"],
        "tier": 3,
        "priority": "tier3",
        "priority_score": 55,
        "status": "active",
        "has_api": False,
        "api_key_required": False,
        "rate_limit": "10 req/min",
        "parser_module": "parser_icodrops",
        "sync_interval_min": 30,
        "description": "Activities: ICO calendar, token sales"
    },
    {
        "id": "dappradar",
        "name": "DappRadar",
        "website": "https://dappradar.com",
        "categories": ["defi", "projects"],
        "data_types": ["dapps", "usage_stats", "rankings"],
        "tier": 3,
        "priority": "tier3",
        "priority_score": 50,
        "status": "active",
        "has_api": True,
        "api_key_required": False,
        "rate_limit": "50 req/min",
        "parser_module": "parser_dappradar",
        "sync_interval_min": 30,
        "description": "Activities: DApp rankings, usage stats"
    },
    {
        "id": "airdropalert",
        "name": "AirdropAlert",
        "website": "https://airdropalert.com",
        "categories": ["activities"],
        "data_types": ["airdrops"],
        "tier": 3,
        "priority": "tier3",
        "priority_score": 45,
        "status": "active",
        "has_api": False,
        "api_key_required": False,
        "rate_limit": "N/A",
        "parser_module": "parser_airdropalert",
        "sync_interval_min": 30,
        "description": "Activities: airdrop alerts"
    },
    
    # ─────────────────────────────────────────────────────────────
    # TIER 4: RESEARCH DATA (sync every few hours)
    # project descriptions, research, tokenomics
    # Skip if no API key - NOT required for system to work
    # ─────────────────────────────────────────────────────────────
    {
        "id": "messari",
        "name": "Messari",
        "website": "https://messari.io",
        "categories": ["projects", "funding", "analytics", "news"],
        "data_types": ["project_profiles", "funding_rounds", "research", "metrics"],
        "tier": 4,
        "priority": "tier4",
        "priority_score": 30,
        "status": "active",
        "has_api": True,
        "api_key_required": True,
        "rate_limit": "20 req/min",
        "parser_module": "parser_messari",
        "sync_interval_min": 180,
        "description": "Research: project profiles (skip if no API key)"
    },
    
    # ─────────────────────────────────────────────────────────────
    # NEWS SOURCES (separate category, handled by news_parser)
    # NOT part of core tiers - separate news pipeline
    # ─────────────────────────────────────────────────────────────
    {
        "id": "incrypted",
        "name": "Incrypted",
        "website": "https://incrypted.com",
        "categories": ["news", "analytics"],
        "data_types": ["news_articles", "market_updates", "research", "guides", "airdrops", "tokensales"],
        "tier": 3,
        "tree": "news",
        "priority": "tier3",
        "priority_score": 65,
        "status": "active",
        "has_api": False,
        "api_key_required": False,
        "rate_limit": "N/A",
        "parser_module": "parser_incrypted",
        "sync_interval_min": 15,
        "description": "News: primary crypto news source (RSS)"
    },
    {
        "id": "cointelegraph",
        "name": "Cointelegraph",
        "website": "https://cointelegraph.com",
        "categories": ["news"],
        "data_types": ["news_articles", "market_updates"],
        "tier": 3,
        "priority": "tier3",
        "priority_score": 40,
        "status": "active",
        "has_api": False,
        "api_key_required": False,
        "rate_limit": "N/A",
        "parser_module": "parser_news",
        "sync_interval_min": 30,
        "description": "News: crypto news (RSS)"
    },
    {
        "id": "theblock",
        "name": "The Block",
        "website": "https://theblock.co",
        "categories": ["news", "analytics"],
        "data_types": ["news_articles", "research", "data"],
        "tier": 3,
        "priority": "tier3",
        "priority_score": 38,
        "status": "active",
        "has_api": False,
        "api_key_required": False,
        "rate_limit": "N/A",
        "parser_module": "parser_news",
        "sync_interval_min": 30,
        "description": "News: crypto news and research (RSS)"
    },
    {
        "id": "coindesk",
        "name": "CoinDesk",
        "website": "https://coindesk.com",
        "categories": ["news"],
        "data_types": ["news_articles", "market_updates"],
        "tier": 3,
        "priority": "tier3",
        "priority_score": 35,
        "status": "active",
        "has_api": False,
        "api_key_required": False,
        "rate_limit": "N/A",
        "parser_module": "parser_news",
        "sync_interval_min": 30,
        "description": "News: crypto news (RSS)"
    },
    
    # ─────────────────────────────────────────────────────────────
    # PERSON / TEAM DATA (for graph: person ↔ fund ↔ project)
    # ─────────────────────────────────────────────────────────────
    {
        "id": "github",
        "name": "GitHub",
        "website": "https://github.com",
        "categories": ["persons", "projects"],
        "data_types": ["developer_activity", "repos", "contributors"],
        "tier": 3,
        "priority": "tier3",
        "priority_score": 42,
        "status": "active",
        "has_api": True,
        "api_key_required": False,
        "rate_limit": "60 req/min",
        "parser_module": "parser_github",
        "sync_interval_min": 60,
        "description": "Person data: developer activity, contributors"
    },
    {
        "id": "twitter",
        "name": "Twitter/X",
        "website": "https://twitter.com",
        "categories": ["persons", "projects"],
        "data_types": ["social_profiles", "followers", "engagement"],
        "tier": 3,
        "priority": "tier3",
        "priority_score": 40,
        "status": "planned",
        "has_api": True,
        "api_key_required": True,
        "rate_limit": "varies",
        "parser_module": None,
        "sync_interval_min": 60,
        "description": "Person data: social presence"
    },
    {
        "id": "linkedin",
        "name": "LinkedIn",
        "website": "https://linkedin.com",
        "categories": ["persons"],
        "data_types": ["professional_profiles", "work_history"],
        "tier": 4,
        "priority": "tier4",
        "priority_score": 25,
        "status": "planned",
        "has_api": True,
        "api_key_required": True,
        "rate_limit": "varies",
        "parser_module": None,
        "sync_interval_min": 180,
        "description": "Person data: professional profiles"
    },
]


# Sync intervals by tier (in minutes)
TIER_SYNC_INTERVALS = {
    1: 10,   # Tier 1: every 10 min
    2: 15,   # Tier 2: every 15 min
    3: 30,   # Tier 3: every 30 min
    4: 180,  # Tier 4: every 3 hours
}


class DataSourcesRegistry:
    """
    Data Sources Registry Manager
    Handles CRUD operations for data sources and tracks sync status
    
    Pipeline: Parser → Public API → Admin API
    If source fails → skip → next source
    """
    
    def __init__(self, db):
        self.db = db
        self.collection = db.data_sources
    
    async def seed_sources(self) -> Dict[str, Any]:
        """Seed all predefined data sources to MongoDB"""
        now = datetime.now(timezone.utc).isoformat()
        seeded = 0
        
        for source in DATA_SOURCES:
            doc = {
                **source,
                "sync_count": 0,
                "error_count": 0,
                "last_sync": None,
                "last_error": None,
                "created_at": now,
                "updated_at": now
            }
            await self.collection.update_one(
                {"id": source["id"]},
                {"$set": doc},
                upsert=True
            )
            seeded += 1
        
        return {"seeded": seeded, "total": len(DATA_SOURCES)}
    
    async def get_sources_by_tier(self, tier: int) -> List[Dict]:
        """Get sources for specific tier, ordered by priority_score"""
        return await self.collection.find(
            {"tier": tier, "status": "active"},
            {"_id": 0}
        ).sort("priority_score", -1).to_list(50)
    
    async def get_sync_queue(self) -> List[Dict]:
        """Get sources ordered by tier and priority for sync queue"""
        return await self.collection.find(
            {"status": "active"},
            {"_id": 0}
        ).sort([("tier", 1), ("priority_score", -1)]).to_list(100)
    
    async def get_tier_sync_interval(self, tier: int) -> int:
        """Get sync interval in minutes for tier"""
        return TIER_SYNC_INTERVALS.get(tier, 60)
    
    async def get_all_sources(self, 
                               category: Optional[str] = None,
                               status: Optional[str] = None,
                               priority: Optional[str] = None) -> List[Dict]:
        """Get all data sources with optional filters"""
        query = {}
        if category:
            query["categories"] = category
        if status:
            query["status"] = status
        if priority:
            query["priority"] = priority
        
        sources = await self.collection.find(query, {"_id": 0}).to_list(100)
        return sources
    
    async def get_source(self, source_id: str) -> Optional[Dict]:
        """Get single data source by ID"""
        return await self.collection.find_one({"id": source_id}, {"_id": 0})
    
    async def update_sync_status(self, source_id: str, success: bool, 
                                  records: int = 0, error: Optional[str] = None):
        """Update sync status for a source"""
        now = datetime.now(timezone.utc).isoformat()
        update = {
            "updated_at": now,
            "last_sync": now if success else None
        }
        
        if success:
            update["$inc"] = {"sync_count": 1}
        else:
            update["last_error"] = error
            update["$inc"] = {"error_count": 1}
        
        await self.collection.update_one(
            {"id": source_id},
            {"$set": {k: v for k, v in update.items() if k != "$inc"}} | 
            ({"$inc": update["$inc"]} if "$inc" in update else {})
        )
    
    async def get_active_sources(self) -> List[Dict]:
        """Get sources that have active parsers"""
        return await self.collection.find(
            {"status": "active"},
            {"_id": 0}
        ).to_list(50)
    
    async def get_sources_by_data_type(self, data_type: str) -> List[Dict]:
        """Get sources that provide specific data type"""
        return await self.collection.find(
            {"data_types": data_type},
            {"_id": 0}
        ).sort("priority", 1).to_list(20)
    
    async def get_sync_summary(self) -> Dict[str, Any]:
        """Get summary of all sources sync status"""
        sources = await self.get_all_sources()
        
        summary = {
            "total": len(sources),
            "active": sum(1 for s in sources if s.get("status") == "active"),
            "planned": sum(1 for s in sources if s.get("status") == "planned"),
            "by_category": {},
            "by_priority": {},
            "recently_synced": []
        }
        
        for s in sources:
            for cat in s.get("categories", []):
                if cat not in summary["by_category"]:
                    summary["by_category"][cat] = 0
                summary["by_category"][cat] += 1
            
            p = s.get("priority", "unknown")
            if p not in summary["by_priority"]:
                summary["by_priority"][p] = 0
            summary["by_priority"][p] += 1
            
            if s.get("last_sync"):
                summary["recently_synced"].append({
                    "id": s["id"],
                    "name": s["name"],
                    "last_sync": s["last_sync"]
                })
        
        summary["recently_synced"] = sorted(
            summary["recently_synced"], 
            key=lambda x: x["last_sync"], 
            reverse=True
        )[:5]
        
        return summary
