"""
Parser Factory — creates parser instances by name.
Maps registry names to actual parser classes.
"""
from intelligence_os.ingestion.base_parser import BaseParser


def create_parser_factory(db):
    """Returns a factory function that creates parsers by name."""

    _registry = {}

    def _lazy_load():
        if _registry:
            return
        from intelligence_os.ingestion.sources.cryptorank_parser import (
            CryptoRankFundingParser,
            CryptoRankUnlocksParser,
        )
        from intelligence_os.ingestion.sources.dropstab_parser import (
            DropstabActivitiesParser,
            DropstabProjectsParser,
        )
        from intelligence_os.ingestion.sources.icodrops_parser import ICODropsParser
        from intelligence_os.ingestion.sources.dropsearn_parser import DropsEarnParser
        from intelligence_os.ingestion.sources.tokenunlocks_parser import TokenUnlocksParser
        from intelligence_os.ingestion.sources.coingecko_parser import CoinGeckoParser
        from intelligence_os.ingestion.sources.news_rss_parser import NewsRSSParser
        from intelligence_os.ingestion.sources.chainbroker_parser import ChainBrokerParser

        _registry.update({
            "chainbroker": ChainBrokerParser,
            "cryptorank": CryptoRankFundingParser,
            "cryptorank_unlocks": CryptoRankUnlocksParser,
            "dropstab": DropstabActivitiesParser,
            "dropstab_projects": DropstabProjectsParser,
            "icodrops": ICODropsParser,
            "dropsearn": DropsEarnParser,
            "tokenunlocks": TokenUnlocksParser,
            "coingecko": CoinGeckoParser,
            "news_rss": NewsRSSParser,
        })

    def factory(name: str) -> BaseParser:
        _lazy_load()
        cls = _registry.get(name)
        if not cls:
            raise ValueError(f"Unknown parser: {name}. Available: {list(_registry.keys())}")
        return cls(db)

    return factory
