"""
Kalshi Source — fetches real markets from Kalshi public REST API.

Only pulls crypto-related series: KXBTC, KXETH (and future crypto series).
No auth required for market data.
"""
import logging
import requests
from typing import Optional

logger = logging.getLogger("cross_market.kalshi.source")

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"

# Only fetch crypto-related series
CRYPTO_SERIES = ["KXBTC", "KXETH"]

# Timeout for requests
REQUEST_TIMEOUT = 15


def fetch_kalshi_markets(
    series_list: Optional[list[str]] = None,
    status: str = "open",
    limit: int = 200,
) -> list[dict]:
    """Fetch open markets from Kalshi for crypto series.

    Returns raw Kalshi market dicts.
    """
    series_list = series_list or CRYPTO_SERIES
    all_markets = []

    for series_ticker in series_list:
        try:
            url = f"{KALSHI_BASE}/markets"
            params = {
                "series_ticker": series_ticker,
                "status": status,
                "limit": min(limit, 1000),
            }
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            markets = data.get("markets", [])
            all_markets.extend(markets)
            logger.info(f"[KalshiSource] {series_ticker}: {len(markets)} markets")
        except requests.RequestException as e:
            logger.error(f"[KalshiSource] Failed to fetch {series_ticker}: {e}")

    logger.info(f"[KalshiSource] Total: {len(all_markets)} markets from {len(series_list)} series")
    return all_markets


def fetch_kalshi_events(
    series_list: Optional[list[str]] = None,
    status: str = "open",
    with_markets: bool = True,
) -> list[dict]:
    """Fetch events with nested markets from Kalshi.

    Returns raw Kalshi event dicts.
    """
    series_list = series_list or CRYPTO_SERIES
    all_events = []

    for series_ticker in series_list:
        try:
            url = f"{KALSHI_BASE}/events"
            params = {
                "series_ticker": series_ticker,
                "status": status,
                "with_nested_markets": str(with_markets).lower(),
                "limit": 100,
            }
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            events = data.get("events", [])
            all_events.extend(events)
            logger.info(f"[KalshiSource] Events {series_ticker}: {len(events)} events")
        except requests.RequestException as e:
            logger.error(f"[KalshiSource] Failed to fetch events {series_ticker}: {e}")

    return all_events
