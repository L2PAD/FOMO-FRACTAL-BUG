"""
CryptoRank Source Adapter
=========================
Bridges to existing CryptoRank parser in modules/parsers/.
Fetches funding rounds, investors, projects.
"""
import sys
import httpx
from datetime import datetime, timezone
from intelligence_os.ingestion.base_parser import BaseParser
from intelligence_os.core.logging_config import get_logger

log = get_logger("source.cryptorank")

CRYPTORANK_API = "https://api.cryptorank.io/v0"


class CryptoRankFundingParser(BaseParser):
    name = "cryptorank"
    raw_collection = "raw_funding"

    async def fetch(self, query: dict | None = None) -> list[dict]:
        rows = []
        now = datetime.now(timezone.utc).isoformat()

        try:
            sys.path.insert(0, "/app/backend")
            from modules.parsers.proxy_helper import get_proxy_url
            proxy_url = get_proxy_url()
        except Exception:
            proxy_url = None

        async with httpx.AsyncClient(
            timeout=30,
            proxy=proxy_url,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        ) as client:
            resp = await client.get(f"{CRYPTORANK_API}/coins", params={"limit": 200})
            resp.raise_for_status()
            data = resp.json()
            coins = data.get("data", [])

            for coin in coins:
                rows.append({
                    "source": "cryptorank",
                    "domain": "FUNDING",
                    "name": coin.get("name"),
                    "symbol": coin.get("symbol"),
                    "slug": coin.get("slug"),
                    "price_usd": coin.get("price", {}).get("USD") if isinstance(coin.get("price"), dict) else coin.get("price"),
                    "market_cap": coin.get("marketCap"),
                    "volume_24h": coin.get("volume24h"),
                    "category": coin.get("category"),
                    "fetched_at": now,
                })

        log.info(f"Fetched {len(rows)} coins from CryptoRank")
        return rows

    def validate(self, rows: list[dict]) -> list[dict]:
        return [r for r in rows if r.get("name") and r.get("symbol")]


class CryptoRankUnlocksParser(BaseParser):
    name = "cryptorank_unlocks"
    raw_collection = "raw_unlocks"

    async def fetch(self, query: dict | None = None) -> list[dict]:
        rows = []
        now = datetime.now(timezone.utc).isoformat()

        try:
            sys.path.insert(0, "/app/backend")
            from modules.parsers.proxy_helper import get_proxy_url
            proxy_url = get_proxy_url()
        except Exception:
            proxy_url = None

        async with httpx.AsyncClient(
            timeout=30,
            proxy=proxy_url,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        ) as client:
            resp = await client.get(
                f"{CRYPTORANK_API}/token-unlocks",
                params={"limit": 50},
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("data", []):
                    rows.append({
                        "source": "cryptorank",
                        "domain": "UNLOCKS",
                        "project_name": item.get("name"),
                        "symbol": item.get("symbol"),
                        "unlock_date": item.get("nextUnlockDate"),
                        "unlock_amount_usd": item.get("nextUnlockUsd"),
                        "unlock_pct": item.get("nextUnlockPercent"),
                        "fetched_at": now,
                    })

        log.info(f"Fetched {len(rows)} unlocks from CryptoRank")
        return rows

    def validate(self, rows: list[dict]) -> list[dict]:
        return [r for r in rows if r.get("project_name")]
