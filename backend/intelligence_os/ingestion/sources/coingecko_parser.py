"""
CoinGecko Source Adapter
========================
Fetches market data and project metadata.
"""
import sys
import httpx
from datetime import datetime, timezone
from intelligence_os.ingestion.base_parser import BaseParser
from intelligence_os.core.logging_config import get_logger

log = get_logger("source.coingecko")

COINGECKO_API = "https://api.coingecko.com/api/v3"


class CoinGeckoParser(BaseParser):
    name = "coingecko"
    raw_collection = "raw_market_data"

    async def fetch(self, query: dict | None = None) -> list[dict]:
        rows = []
        now = datetime.now(timezone.utc).isoformat()

        try:
            sys.path.insert(0, "/app/backend")
            from modules.parsers.proxy_helper import get_proxy_url
            proxy_url = get_proxy_url()
        except Exception:
            proxy_url = None

        async with httpx.AsyncClient(timeout=30, proxy=proxy_url) as client:
            resp = await client.get(
                f"{COINGECKO_API}/coins/markets",
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": 100,
                    "page": 1,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                for coin in data:
                    rows.append({
                        "source": "coingecko",
                        "domain": "PROJECTS",
                        "name": coin.get("name"),
                        "symbol": (coin.get("symbol") or "").upper(),
                        "coingecko_id": coin.get("id"),
                        "price_usd": coin.get("current_price"),
                        "market_cap": coin.get("market_cap"),
                        "volume_24h": coin.get("total_volume"),
                        "price_change_24h_pct": coin.get("price_change_percentage_24h"),
                        "circulating_supply": coin.get("circulating_supply"),
                        "total_supply": coin.get("total_supply"),
                        "ath": coin.get("ath"),
                        "fetched_at": now,
                    })
            else:
                log.warning(f"CoinGecko API returned {resp.status_code}")

        log.info(f"Fetched {len(rows)} coins from CoinGecko")
        return rows

    def validate(self, rows: list[dict]) -> list[dict]:
        return [r for r in rows if r.get("name") and r.get("symbol")]
