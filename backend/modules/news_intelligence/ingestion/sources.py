"""
News Sources Registry
=====================

Configuration for all news sources with RSS/API/HTML endpoints.
V2: 20 sources - EN (14) + RU (6)
"""

from typing import List, Dict
from ..models import NewsSource, SourceType, SourceTier


# ═══════════════════════════════════════════════════════════════
# V2 SOURCES (20 sources)
# ═══════════════════════════════════════════════════════════════

NEWS_SOURCES: List[Dict] = [
    # ─────────────────────────────────────────────────────────────
    # TIER A - English Primary Sources (fast, reliable)
    # ─────────────────────────────────────────────────────────────
    {
        "id": "coindesk",
        "name": "CoinDesk",
        "domain": "coindesk.com",
        "source_type": "rss",
        "tier": "A",
        "language": "en",
        "region": "US",
        "rss_url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "refresh_interval_sec": 300,
        "source_weight": 1.0,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "cointelegraph",
        "name": "Cointelegraph",
        "domain": "cointelegraph.com",
        "source_type": "rss",
        "tier": "A",
        "language": "en",
        "region": "Global",
        "rss_url": "https://cointelegraph.com/rss",
        "refresh_interval_sec": 300,
        "source_weight": 1.0,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "theblock",
        "name": "The Block",
        "domain": "theblock.co",
        "source_type": "rss",
        "tier": "A",
        "language": "en",
        "region": "US",
        "rss_url": "https://www.theblock.co/rss.xml",
        "refresh_interval_sec": 300,
        "source_weight": 1.0,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "decrypt",
        "name": "Decrypt",
        "domain": "decrypt.co",
        "source_type": "rss",
        "tier": "A",
        "language": "en",
        "region": "US",
        "rss_url": "https://decrypt.co/feed",
        "refresh_interval_sec": 300,
        "source_weight": 0.95,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "blockworks",
        "name": "Blockworks",
        "domain": "blockworks.co",
        "source_type": "rss",
        "tier": "A",
        "language": "en",
        "region": "US",
        "rss_url": "https://blockworks.co/feed/",
        "refresh_interval_sec": 300,
        "source_weight": 0.95,
        "is_official": False,
        "is_active": True
    },
    
    # ─────────────────────────────────────────────────────────────
    # TIER B - English Secondary Sources
    # ─────────────────────────────────────────────────────────────
    {
        "id": "bitcoinmagazine",
        "name": "Bitcoin Magazine",
        "domain": "bitcoinmagazine.com",
        "source_type": "rss",
        "tier": "B",
        "language": "en",
        "region": "US",
        "rss_url": "https://bitcoinmagazine.com/.rss/full/",
        "refresh_interval_sec": 600,
        "source_weight": 0.85,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "cryptoslate",
        "name": "CryptoSlate",
        "domain": "cryptoslate.com",
        "source_type": "rss",
        "tier": "B",
        "language": "en",
        "region": "US",
        "rss_url": "https://cryptoslate.com/feed/",
        "refresh_interval_sec": 600,
        "source_weight": 0.8,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "beincrypto",
        "name": "BeInCrypto",
        "domain": "beincrypto.com",
        "source_type": "rss",
        "tier": "B",
        "language": "en",
        "region": "Global",
        "rss_url": "https://beincrypto.com/feed/",
        "refresh_interval_sec": 600,
        "source_weight": 0.8,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "newsbtc",
        "name": "NewsBTC",
        "domain": "newsbtc.com",
        "source_type": "rss",
        "tier": "B",
        "language": "en",
        "region": "Global",
        "rss_url": "https://www.newsbtc.com/feed/",
        "refresh_interval_sec": 600,
        "source_weight": 0.75,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "cryptopotato",
        "name": "CryptoPotato",
        "domain": "cryptopotato.com",
        "source_type": "rss",
        "tier": "B",
        "language": "en",
        "region": "Global",
        "rss_url": "https://cryptopotato.com/feed/",
        "refresh_interval_sec": 600,
        "source_weight": 0.75,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "utoday",
        "name": "U.Today",
        "domain": "u.today",
        "source_type": "rss",
        "tier": "B",
        "language": "en",
        "region": "Global",
        "rss_url": "https://u.today/rss",
        "refresh_interval_sec": 600,
        "source_weight": 0.75,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "coinjournal",
        "name": "CoinJournal",
        "domain": "coinjournal.net",
        "source_type": "rss",
        "tier": "B",
        "language": "en",
        "region": "EU",
        "rss_url": "https://coinjournal.net/feed/",
        "refresh_interval_sec": 600,
        "source_weight": 0.7,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "coingape",
        "name": "CoinGape",
        "domain": "coingape.com",
        "source_type": "rss",
        "tier": "B",
        "language": "en",
        "region": "Global",
        "rss_url": "https://coingape.com/feed/",
        "refresh_interval_sec": 600,
        "source_weight": 0.7,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "coinpedia",
        "name": "Coinpedia",
        "domain": "coinpedia.org",
        "source_type": "rss",
        "tier": "B",
        "language": "en",
        "region": "Global",
        "rss_url": "https://coinpedia.org/feed/",
        "refresh_interval_sec": 600,
        "source_weight": 0.7,
        "is_official": False,
        "is_active": True
    },
    
    # ─────────────────────────────────────────────────────────────
    # TIER A - Russian/Ukrainian Sources
    # ─────────────────────────────────────────────────────────────
    {
        "id": "incrypted",
        "name": "Incrypted",
        "domain": "incrypted.com",
        "source_type": "rss",
        "tier": "A",
        "language": "ru",
        "region": "UA",
        "rss_url": "https://incrypted.com/feed/",
        "refresh_interval_sec": 300,
        "source_weight": 1.0,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "forklog",
        "name": "Forklog",
        "domain": "forklog.com",
        "source_type": "rss",
        "tier": "A",
        "language": "ru",
        "region": "RU",
        "rss_url": "https://forklog.com/feed/",
        "refresh_interval_sec": 300,
        "source_weight": 0.95,
        "is_official": False,
        "is_active": True
    },
    
    # ─────────────────────────────────────────────────────────────
    # TIER B - Russian Sources
    # ─────────────────────────────────────────────────────────────
    {
        "id": "bits_media",
        "name": "Bits.media",
        "domain": "bits.media",
        "source_type": "rss",
        "tier": "B",
        "language": "ru",
        "region": "RU",
        "rss_url": "https://bits.media/rss/",
        "refresh_interval_sec": 600,
        "source_weight": 0.8,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "cryptonews_ru",
        "name": "CryptoNews RU",
        "domain": "cryptonews.net",
        "source_type": "rss",
        "tier": "B",
        "language": "ru",
        "region": "RU",
        "rss_url": "https://ru.cryptonews.com/news/feed/",
        "refresh_interval_sec": 600,
        "source_weight": 0.75,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "coinspot",
        "name": "CoinSpot",
        "domain": "coinspot.io",
        "source_type": "rss",
        "tier": "B",
        "language": "ru",
        "region": "RU",
        "rss_url": "https://coinspot.io/feed/",
        "refresh_interval_sec": 600,
        "source_weight": 0.7,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "2bitcoins",
        "name": "2Bitcoins",
        "domain": "2bitcoins.ru",
        "source_type": "rss",
        "tier": "B",
        "language": "ru",
        "region": "RU",
        "rss_url": "https://2bitcoins.ru/feed/",
        "refresh_interval_sec": 600,
        "source_weight": 0.7,
        "is_official": False,
        "is_active": True
    },
    
    # ═══════════════════════════════════════════════════════════════
    # V3 EXPANSION - 30+ NEW SOURCES
    # ═══════════════════════════════════════════════════════════════
    
    # ─────────────────────────────────────────────────────────────
    # TIER A - Additional Fast Sources
    # ─────────────────────────────────────────────────────────────
    {
        "id": "dlnews",
        "name": "DL News",
        "domain": "dlnews.com",
        "source_type": "rss",
        "tier": "A",
        "language": "en",
        "region": "Global",
        "rss_url": "https://www.dlnews.com/rss/",
        "refresh_interval_sec": 300,
        "source_weight": 0.95,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "defiant",
        "name": "The Defiant",
        "domain": "thedefiant.io",
        "source_type": "rss",
        "tier": "A",
        "language": "en",
        "region": "US",
        "rss_url": "https://thedefiant.io/feed/",
        "refresh_interval_sec": 300,
        "source_weight": 0.9,
        "is_official": False,
        "is_active": True
    },
    
    # ─────────────────────────────────────────────────────────────
    # TIER B - More Secondary Sources
    # ─────────────────────────────────────────────────────────────
    {
        "id": "cryptobriefing",
        "name": "CryptoBriefing",
        "domain": "cryptobriefing.com",
        "source_type": "rss",
        "tier": "B",
        "language": "en",
        "region": "US",
        "rss_url": "https://cryptobriefing.com/feed/",
        "refresh_interval_sec": 600,
        "source_weight": 0.8,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "dailycoin",
        "name": "DailyCoin",
        "domain": "dailycoin.com",
        "source_type": "rss",
        "tier": "B",
        "language": "en",
        "region": "Global",
        "rss_url": "https://dailycoin.com/feed/",
        "refresh_interval_sec": 600,
        "source_weight": 0.75,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "cryptoglobe",
        "name": "CryptoGlobe",
        "domain": "cryptoglobe.com",
        "source_type": "rss",
        "tier": "B",
        "language": "en",
        "region": "Global",
        "rss_url": "https://www.cryptoglobe.com/latest/feed/",
        "refresh_interval_sec": 600,
        "source_weight": 0.7,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "insidebitcoins",
        "name": "InsideBitcoins",
        "domain": "insidebitcoins.com",
        "source_type": "rss",
        "tier": "B",
        "language": "en",
        "region": "US",
        "rss_url": "https://insidebitcoins.com/feed/",
        "refresh_interval_sec": 600,
        "source_weight": 0.7,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "ambcrypto",
        "name": "AMBCrypto",
        "domain": "ambcrypto.com",
        "source_type": "rss",
        "tier": "B",
        "language": "en",
        "region": "Global",
        "rss_url": "https://ambcrypto.com/feed/",
        "refresh_interval_sec": 600,
        "source_weight": 0.7,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "zycrypto",
        "name": "ZyCrypto",
        "domain": "zycrypto.com",
        "source_type": "rss",
        "tier": "B",
        "language": "en",
        "region": "Global",
        "rss_url": "https://zycrypto.com/feed/",
        "refresh_interval_sec": 600,
        "source_weight": 0.65,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "bitcoinist",
        "name": "Bitcoinist",
        "domain": "bitcoinist.com",
        "source_type": "rss",
        "tier": "B",
        "language": "en",
        "region": "Global",
        "rss_url": "https://bitcoinist.com/feed/",
        "refresh_interval_sec": 600,
        "source_weight": 0.7,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "cryptopotato_2",
        "name": "CryptoPotato News",
        "domain": "cryptopotato.com",
        "source_type": "rss",
        "tier": "B",
        "language": "en",
        "region": "Global",
        "rss_url": "https://cryptopotato.com/crypto-news/feed/",
        "refresh_interval_sec": 600,
        "source_weight": 0.7,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "finbold",
        "name": "Finbold",
        "domain": "finbold.com",
        "source_type": "rss",
        "tier": "B",
        "language": "en",
        "region": "Global",
        "rss_url": "https://finbold.com/feed/",
        "refresh_interval_sec": 600,
        "source_weight": 0.65,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "cryptonews_en",
        "name": "CryptoNews EN",
        "domain": "cryptonews.com",
        "source_type": "rss",
        "tier": "B",
        "language": "en",
        "region": "Global",
        "rss_url": "https://cryptonews.com/news/feed/",
        "refresh_interval_sec": 600,
        "source_weight": 0.75,
        "is_official": False,
        "is_active": True
    },
    
    # ─────────────────────────────────────────────────────────────
    # TIER C - Niche / Blog / Research Sources (slower refresh)
    # ─────────────────────────────────────────────────────────────
    {
        "id": "bankless",
        "name": "Bankless",
        "domain": "bankless.com",
        "source_type": "rss",
        "tier": "C",
        "language": "en",
        "region": "US",
        "rss_url": "https://www.bankless.com/rss/",
        "refresh_interval_sec": 1800,
        "source_weight": 0.85,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "messari_blog",
        "name": "Messari Research",
        "domain": "messari.io",
        "source_type": "rss",
        "tier": "C",
        "language": "en",
        "region": "US",
        "rss_url": "https://messari.io/rss",
        "refresh_interval_sec": 1800,
        "source_weight": 0.9,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "rekt_news",
        "name": "Rekt News",
        "domain": "rekt.news",
        "source_type": "rss",
        "tier": "C",
        "language": "en",
        "region": "Global",
        "rss_url": "https://rekt.news/rss/feed.xml",
        "refresh_interval_sec": 1800,
        "source_weight": 0.75,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "cryptotimes",
        "name": "CryptoTimes",
        "domain": "cryptotimes.io",
        "source_type": "rss",
        "tier": "C",
        "language": "en",
        "region": "Asia",
        "rss_url": "https://www.cryptotimes.io/feed/",
        "refresh_interval_sec": 1800,
        "source_weight": 0.6,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "coininsider",
        "name": "CoinInsider",
        "domain": "coininsider.com",
        "source_type": "rss",
        "tier": "C",
        "language": "en",
        "region": "Global",
        "rss_url": "https://www.coininsider.com/feed/",
        "refresh_interval_sec": 1800,
        "source_weight": 0.55,
        "is_official": False,
        "is_active": True
    },
    
    # ─────────────────────────────────────────────────────────────
    # TIER C - Asian Sources
    # ─────────────────────────────────────────────────────────────
    {
        "id": "blocktempo",
        "name": "BlockTempo",
        "domain": "blocktempo.com",
        "source_type": "rss",
        "tier": "C",
        "language": "zh",
        "region": "Taiwan",
        "rss_url": "https://www.blocktempo.com/feed/",
        "refresh_interval_sec": 1800,
        "source_weight": 0.7,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "panewslab",
        "name": "PANews",
        "domain": "panewslab.com",
        "source_type": "rss",
        "tier": "C",
        "language": "zh",
        "region": "China",
        "rss_url": "https://www.panewslab.com/en/rss/index.html",
        "refresh_interval_sec": 1800,
        "source_weight": 0.7,
        "is_official": False,
        "is_active": True
    },
    
    # ─────────────────────────────────────────────────────────────
    # TIER C - European Sources
    # ─────────────────────────────────────────────────────────────
    {
        "id": "btcecho",
        "name": "BTC-Echo",
        "domain": "btc-echo.de",
        "source_type": "rss",
        "tier": "C",
        "language": "de",
        "region": "Germany",
        "rss_url": "https://www.btc-echo.de/feed/",
        "refresh_interval_sec": 1800,
        "source_weight": 0.7,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "cryptonomist",
        "name": "The Cryptonomist",
        "domain": "cryptonomist.ch",
        "source_type": "rss",
        "tier": "C",
        "language": "en",
        "region": "Europe",
        "rss_url": "https://cryptonomist.ch/en/feed/",
        "refresh_interval_sec": 1800,
        "source_weight": 0.65,
        "is_official": False,
        "is_active": True
    },
    
    # ─────────────────────────────────────────────────────────────
    # TIER C - Exchange/Official Blogs
    # ─────────────────────────────────────────────────────────────
    {
        "id": "binance_blog",
        "name": "Binance Blog",
        "domain": "binance.com",
        "source_type": "rss",
        "tier": "C",
        "language": "en",
        "region": "Global",
        "rss_url": "https://www.binance.com/en/blog/rss",
        "refresh_interval_sec": 1800,
        "source_weight": 0.9,
        "is_official": True,
        "is_active": True
    },
    {
        "id": "coinbase_blog",
        "name": "Coinbase Blog",
        "domain": "coinbase.com",
        "source_type": "rss",
        "tier": "C",
        "language": "en",
        "region": "US",
        "rss_url": "https://blog.coinbase.com/feed",
        "refresh_interval_sec": 1800,
        "source_weight": 0.9,
        "is_official": True,
        "is_active": True
    },
    {
        "id": "kraken_blog",
        "name": "Kraken Blog",
        "domain": "kraken.com",
        "source_type": "rss",
        "tier": "C",
        "language": "en",
        "region": "US",
        "rss_url": "https://blog.kraken.com/feed/",
        "refresh_interval_sec": 1800,
        "source_weight": 0.85,
        "is_official": True,
        "is_active": True
    },
    
    # ─────────────────────────────────────────────────────────────
    # TIER C - Additional Russian Sources
    # ─────────────────────────────────────────────────────────────
    {
        "id": "crypto_ru",
        "name": "Crypto.ru",
        "domain": "crypto.ru",
        "source_type": "rss",
        "tier": "C",
        "language": "ru",
        "region": "RU",
        "rss_url": "https://crypto.ru/feed/",
        "refresh_interval_sec": 1800,
        "source_weight": 0.6,
        "is_official": False,
        "is_active": True
    },
    {
        "id": "mining_cryptocurrency",
        "name": "Mining Cryptocurrency",
        "domain": "mining-cryptocurrency.ru",
        "source_type": "rss",
        "tier": "C",
        "language": "ru",
        "region": "RU",
        "rss_url": "https://mining-cryptocurrency.ru/feed/",
        "refresh_interval_sec": 1800,
        "source_weight": 0.55,
        "is_official": False,
        "is_active": True
    },
]


def get_active_sources() -> List[NewsSource]:
    """Get all active news sources."""
    sources = []
    for src in NEWS_SOURCES:
        if src.get("is_active", True):
            sources.append(NewsSource(**src))
    return sources


def get_source_by_id(source_id: str) -> NewsSource | None:
    """Get source by ID."""
    for src in NEWS_SOURCES:
        if src["id"] == source_id:
            return NewsSource(**src)
    return None


def get_source_weight(source_id: str) -> float:
    """Get source weight for scoring."""
    source = get_source_by_id(source_id)
    if source:
        weight = source.source_weight
        if source.is_official:
            weight *= 1.5
        if source.tier == SourceTier.A:
            weight *= 1.2
        return weight
    return 0.5


def get_tier_a_sources() -> List[NewsSource]:
    """Get only Tier A sources for fast pipeline."""
    return [s for s in get_active_sources() if s.tier == SourceTier.A]


def get_tier_b_sources() -> List[NewsSource]:
    """Get Tier B sources for secondary pipeline."""
    return [s for s in get_active_sources() if s.tier == SourceTier.B]


def get_tier_c_sources() -> List[NewsSource]:
    """Get Tier C sources for slow pipeline."""
    return [s for s in get_active_sources() if s.tier == SourceTier.C]


def get_sources_by_tier() -> Dict[str, List[NewsSource]]:
    """Get all sources grouped by tier."""
    sources = get_active_sources()
    return {
        "A": [s for s in sources if s.tier == SourceTier.A],
        "B": [s for s in sources if s.tier == SourceTier.B],
        "C": [s for s in sources if s.tier == SourceTier.C]
    }


def get_source_count() -> Dict[str, int]:
    """Get count of sources by tier."""
    tiers = get_sources_by_tier()
    return {
        "A": len(tiers["A"]),
        "B": len(tiers["B"]),
        "C": len(tiers["C"]),
        "total": sum(len(v) for v in tiers.values())
    }
