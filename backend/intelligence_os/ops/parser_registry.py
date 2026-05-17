"""
Parser Registry — Master Source Matrix
=======================================
Single source of truth for all data sources in the system.
Every parser must be registered here with its domain, tier, method, and fallback chain.

Rule: No parser runs outside this registry.
"""
from dataclasses import dataclass, field
from intelligence_os.core.enums import SourceTier, SourceDomain, SourceMethod


@dataclass
class ParserSpec:
    name: str
    domain: SourceDomain
    tier: SourceTier
    method: SourceMethod
    enabled: bool
    fallback_chain: list = field(default_factory=list)
    raw_collection: str = ""
    sync_interval_min: int = 60
    description: str = ""


# ═══════════════════════════════════════════════════════════════
# MASTER SOURCE MATRIX
# ═══════════════════════════════════════════════════════════════

SOURCE_MATRIX: list[ParserSpec] = [
    # ── TIER 1: CORE DATA (10 min sync) ──
    ParserSpec(
        name="cryptorank",
        domain=SourceDomain.FUNDING,
        tier=SourceTier.CORE,
        method=SourceMethod.XHR,
        enabled=True,
        fallback_chain=["dropstab"],
        raw_collection="raw_funding",
        sync_interval_min=10,
        description="Funding rounds, investors, ICO data",
    ),
    ParserSpec(
        name="cryptorank_unlocks",
        domain=SourceDomain.UNLOCKS,
        tier=SourceTier.CORE,
        method=SourceMethod.XHR,
        enabled=True,
        fallback_chain=["tokenunlocks"],
        raw_collection="raw_unlocks",
        sync_interval_min=10,
        description="Token unlock schedules",
    ),
    ParserSpec(
        name="dropstab",
        domain=SourceDomain.ACTIVITIES,
        tier=SourceTier.CORE,
        method=SourceMethod.BROWSER,
        enabled=True,
        fallback_chain=["dropsearn"],
        raw_collection="raw_activities",
        sync_interval_min=10,
        description="Activities, airdrops, unlocks",
    ),
    ParserSpec(
        name="dropstab_projects",
        domain=SourceDomain.PROJECTS,
        tier=SourceTier.CORE,
        method=SourceMethod.BROWSER,
        enabled=True,
        fallback_chain=[],
        raw_collection="raw_projects",
        sync_interval_min=30,
        description="Project metadata from Dropstab",
    ),

    # ── TIER 2: TOKEN / MARKET DATA (15 min sync) ──
    ParserSpec(
        name="coingecko",
        domain=SourceDomain.PROJECTS,
        tier=SourceTier.EXTENSION,
        method=SourceMethod.API,
        enabled=True,
        fallback_chain=["coinmarketcap"],
        raw_collection="raw_market_data",
        sync_interval_min=15,
        description="Market prices, tokenomics",
    ),
    ParserSpec(
        name="tokenunlocks",
        domain=SourceDomain.UNLOCKS,
        tier=SourceTier.EXTENSION,
        method=SourceMethod.API,
        enabled=True,
        fallback_chain=["cryptorank_unlocks"],
        raw_collection="raw_unlocks",
        sync_interval_min=15,
        description="Detailed unlock schedules",
    ),

    # ── TIER 3: ACTIVITIES (30 min sync) ──
    ParserSpec(
        name="dropsearn",
        domain=SourceDomain.ACTIVITIES,
        tier=SourceTier.EXTENSION,
        method=SourceMethod.HTML,
        enabled=True,
        fallback_chain=[],
        raw_collection="raw_activities",
        sync_interval_min=30,
        description="Airdrop campaigns, activities",
    ),
    ParserSpec(
        name="icodrops",
        domain=SourceDomain.ICO,
        tier=SourceTier.EXTENSION,
        method=SourceMethod.HTML,
        enabled=True,
        fallback_chain=[],
        raw_collection="raw_ico",
        sync_interval_min=30,
        description="ICO launches, token sales",
    ),

    # ── NEWS STREAM ──
    ParserSpec(
        name="news_rss",
        domain=SourceDomain.NEWS,
        tier=SourceTier.EXTENSION,
        method=SourceMethod.RSS,
        enabled=True,
        fallback_chain=[],
        raw_collection="raw_news",
        sync_interval_min=15,
        description="RSS news feeds (210+ sources)",
    ),
    ParserSpec(
        name="chainbroker",
        domain=SourceDomain.NEWS,
        tier=SourceTier.EXTENSION,
        method=SourceMethod.HTML,
        enabled=True,
        fallback_chain=[],
        raw_collection="raw_news",
        sync_interval_min=30,
        description="ChainBroker news / project announcements",
    ),
]


def get_source_matrix() -> list[ParserSpec]:
    return SOURCE_MATRIX


def get_enabled_sources() -> list[ParserSpec]:
    return [s for s in SOURCE_MATRIX if s.enabled]


def get_sources_by_domain(domain: SourceDomain) -> list[ParserSpec]:
    return [s for s in SOURCE_MATRIX if s.domain == domain and s.enabled]


def get_source_by_name(name: str) -> ParserSpec | None:
    for s in SOURCE_MATRIX:
        if s.name == name:
            return s
    return None
