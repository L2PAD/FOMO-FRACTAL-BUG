"""
FOMO Data Parsers
=================
Real data parsers for crypto intelligence platform.

Sources:
- CoinGecko: Market data, project profiles
- CryptoRank: Funding rounds, activities
- Dropstab: Activities, airdrops
- DropsEarn: Campaigns, testnets
- DefiLlama: DeFi protocols, TVL
- TokenUnlocks: Token unlock schedules
- Messari: Crypto metrics and research
"""

from .parser_coingecko import CoinGeckoParser, sync_coingecko_data
from .parser_cryptorank import CryptoRankParser, sync_cryptorank_data
from .parser_activities import ActivitiesParser, sync_activities_data
from .parser_defillama import DefiLlamaParser, sync_defillama_data
from .parser_tokenunlocks import TokenUnlocksParser, sync_tokenunlocks_data
from .parser_messari import MessariParser, sync_messari_data

__all__ = [
    'CoinGeckoParser', 'sync_coingecko_data',
    'CryptoRankParser', 'sync_cryptorank_data',
    'ActivitiesParser', 'sync_activities_data',
    'DefiLlamaParser', 'sync_defillama_data',
    'TokenUnlocksParser', 'sync_tokenunlocks_data',
    'MessariParser', 'sync_messari_data'
]
