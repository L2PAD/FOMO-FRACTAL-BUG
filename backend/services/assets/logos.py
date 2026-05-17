"""
Asset Logos Service.

Single source of truth for "what does $BTC look like?".
Reads from `asset_logos` collection (populated by CoinGecko).
On cache miss, fetches on-demand from CoinGecko and persists.

Public API:
    await asset_logos.get_many(["BTC","ETH","SOL"])
    → {"BTC": {"url": "...", "name": "Bitcoin", "coingecko_id": "bitcoin"}, ...}

    await asset_logos.get_one("BTC")
    → {"url": "...", "name": "Bitcoin", ...} | None

    await asset_logos.backfill_from_coingecko(pages=2)
    → seeds DB with top 500 coins
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Iterable

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

COINGECKO_API = "https://api.coingecko.com/api/v3"
CACHE_TTL_DAYS = 7

# Hardcoded fallback: for common symbols, direct URLs (works even if DB is empty)
HARDCODED = {
    "BTC": ("bitcoin", "Bitcoin", "https://assets.coingecko.com/coins/images/1/large/bitcoin.png"),
    "ETH": ("ethereum", "Ethereum", "https://assets.coingecko.com/coins/images/279/large/ethereum.png"),
    "SOL": ("solana", "Solana", "https://assets.coingecko.com/coins/images/4128/large/solana.png"),
    "BNB": ("binancecoin", "BNB", "https://assets.coingecko.com/coins/images/825/large/bnb-icon2_2x.png"),
    "XRP": ("ripple", "XRP", "https://assets.coingecko.com/coins/images/44/large/xrp-symbol-white-128.png"),
    "USDT": ("tether", "Tether", "https://assets.coingecko.com/coins/images/325/large/Tether.png"),
    "USDC": ("usd-coin", "USDC", "https://assets.coingecko.com/coins/images/6319/large/usdc.png"),
    "DOGE": ("dogecoin", "Dogecoin", "https://assets.coingecko.com/coins/images/5/large/dogecoin.png"),
    "ADA": ("cardano", "Cardano", "https://assets.coingecko.com/coins/images/975/large/cardano.png"),
    "AVAX": ("avalanche-2", "Avalanche", "https://assets.coingecko.com/coins/images/12559/large/Avalanche_Circle_RedWhite_Trans.png"),
    "LINK": ("chainlink", "Chainlink", "https://assets.coingecko.com/coins/images/877/large/chainlink-new-logo.png"),
    "MATIC": ("matic-network", "Polygon", "https://assets.coingecko.com/coins/images/4713/large/polygon.png"),
    "DOT": ("polkadot", "Polkadot", "https://assets.coingecko.com/coins/images/12171/large/polkadot.png"),
    "LTC": ("litecoin", "Litecoin", "https://assets.coingecko.com/coins/images/2/large/litecoin.png"),
    "TON": ("the-open-network", "Toncoin", "https://assets.coingecko.com/coins/images/17980/large/ton_symbol.png"),
    "TRX": ("tron", "TRON", "https://assets.coingecko.com/coins/images/1094/large/tron-logo.png"),
    "SHIB": ("shiba-inu", "Shiba Inu", "https://assets.coingecko.com/coins/images/11939/large/shiba.png"),
    "UNI": ("uniswap", "Uniswap", "https://assets.coingecko.com/coins/images/12504/large/uniswap-logo.png"),
    "ATOM": ("cosmos", "Cosmos", "https://assets.coingecko.com/coins/images/1481/large/cosmos_hub.png"),
    "BCH": ("bitcoin-cash", "Bitcoin Cash", "https://assets.coingecko.com/coins/images/780/large/bitcoin-cash-circle.png"),
    "NEAR": ("near", "NEAR Protocol", "https://assets.coingecko.com/coins/images/10365/large/near.jpg"),
    "APT": ("aptos", "Aptos", "https://assets.coingecko.com/coins/images/26455/large/aptos_round.png"),
    "ARB": ("arbitrum", "Arbitrum", "https://assets.coingecko.com/coins/images/16547/large/arb.jpg"),
    "OP": ("optimism", "Optimism", "https://assets.coingecko.com/coins/images/25244/large/Optimism.png"),
    "SPX": (None, "S&P 500", ""),
    "DXY": (None, "Dollar Index", ""),
}


def _norm(symbol: str) -> str:
    return (symbol or "").strip().upper()


class AssetLogos:
    def __init__(self) -> None:
        self._proxy_url: str | None = None  # No proxy — CoinGecko works directly

    def _db(self):
        return AsyncIOMotorClient(
            os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        )[os.environ.get("DB_NAME", "test_database")]

    async def ensure_indexes(self) -> None:
        try:
            db = self._db()
            await db["asset_logos"].create_index("symbol", unique=True)
            await db["asset_logos"].create_index("coingecko_id")
        except Exception as e:
            logger.warning(f"asset_logos indexes: {e}")

    # ── Read ─────────────────────────────────────────────────────────
    async def get_many(self, symbols: Iterable[str]) -> dict[str, dict]:
        syms = list({_norm(s) for s in symbols if s})
        if not syms:
            return {}

        db = self._db()
        found: dict[str, dict] = {}
        try:
            async for doc in db["asset_logos"].find(
                {"symbol": {"$in": syms}}, {"_id": 0}
            ):
                found[doc["symbol"]] = doc
        except Exception as e:
            logger.warning(f"asset_logos read failed: {e}")

        # Backfill misses on-demand (hardcoded first, then CoinGecko)
        missing = [s for s in syms if s not in found]
        for s in missing:
            if s in HARDCODED:
                cg_id, name, url = HARDCODED[s]
                doc = await self._persist(s, cg_id, name, url, url, url)
                if doc:
                    found[s] = doc

        # Final output: trimmed public shape
        return {
            s: {
                "symbol": d["symbol"],
                "coingecko_id": d.get("coingecko_id", ""),
                "name": d.get("name", ""),
                "url": d.get("image_large") or d.get("image_small") or d.get("image_thumb") or "",
                "thumb": d.get("image_thumb") or "",
                "small": d.get("image_small") or "",
                "large": d.get("image_large") or "",
            }
            for s, d in found.items()
        }

    async def get_one(self, symbol: str) -> dict | None:
        res = await self.get_many([symbol])
        return res.get(_norm(symbol))

    # ── Write helpers ─────────────────────────────────────────────────
    async def _persist(
        self,
        symbol: str,
        coingecko_id: str | None,
        name: str,
        image_thumb: str,
        image_small: str,
        image_large: str,
    ) -> dict | None:
        try:
            db = self._db()
            payload = {
                "symbol": _norm(symbol),
                "coingecko_id": coingecko_id or "",
                "name": name or "",
                "image_thumb": image_thumb or image_small or image_large or "",
                "image_small": image_small or image_large or image_thumb or "",
                "image_large": image_large or image_small or image_thumb or "",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await db["asset_logos"].update_one(
                {"symbol": payload["symbol"]}, {"$set": payload}, upsert=True
            )
            return payload
        except Exception as e:
            logger.warning(f"asset_logos persist failed for {symbol}: {e}")
            return None

    # ── Backfill ──────────────────────────────────────────────────────
    async def backfill_from_coingecko(self, pages: int = 2, per_page: int = 250) -> dict:
        """
        Hit CoinGecko /coins/markets for top (pages × per_page) coins and
        seed `asset_logos`. Idempotent — existing records are updated.
        """
        await self.ensure_indexes()
        wrote = 0
        failed_pages = 0

        async with httpx.AsyncClient(timeout=30, proxy=self._proxy_url) as client:
            for page in range(1, pages + 1):
                try:
                    resp = await client.get(
                        f"{COINGECKO_API}/coins/markets",
                        params={
                            "vs_currency": "usd",
                            "order": "market_cap_desc",
                            "per_page": per_page,
                            "page": page,
                        },
                    )
                    if resp.status_code != 200:
                        failed_pages += 1
                        logger.warning(f"CoinGecko page {page}: {resp.status_code}")
                        continue
                    coins = resp.json()
                    db = self._db()
                    ops = []
                    now = datetime.now(timezone.utc).isoformat()
                    for c in coins:
                        sym = _norm(c.get("symbol", ""))
                        if not sym:
                            continue
                        img = c.get("image") or ""
                        # CoinGecko /coins/markets returns single image URL.
                        # Reconstruct sizes by substituting /large/, /small/, /thumb/
                        thumb = img.replace("/large/", "/thumb/") if img else ""
                        small = img.replace("/large/", "/small/") if img else ""
                        large = img
                        payload = {
                            "symbol": sym,
                            "coingecko_id": c.get("id", ""),
                            "name": c.get("name", ""),
                            "image_thumb": thumb,
                            "image_small": small,
                            "image_large": large,
                            "updated_at": now,
                        }
                        from pymongo import UpdateOne
                        ops.append(UpdateOne({"symbol": sym}, {"$set": payload}, upsert=True))
                    if ops:
                        result = await db["asset_logos"].bulk_write(ops, ordered=False)
                        wrote += result.upserted_count + result.modified_count
                except Exception as e:
                    failed_pages += 1
                    logger.warning(f"backfill page {page} failed: {e}")
                await asyncio.sleep(1.5)  # respect CoinGecko free tier

        # Ensure hardcoded fallbacks also present (for non-crypto symbols etc.)
        for sym, (cg_id, name, url) in HARDCODED.items():
            if not url:
                continue
            existing = await self._db()["asset_logos"].find_one({"symbol": sym})
            if not existing:
                await self._persist(sym, cg_id, name, url, url, url)
                wrote += 1

        return {"ok": True, "wrote": wrote, "pages": pages, "failed_pages": failed_pages}


asset_logos = AssetLogos()


# ─── Source / news-outlet logos ───────────────────────────────────────
# Canonical map of popular news / social sources → logo URLs.
# Looked up by lower-cased slug. Extend as new sources are added.
SOURCE_LOGOS: dict[str, dict] = {
    # Crypto publications
    "coindesk":       {"name": "CoinDesk", "url": "https://assets.coindesk.com/static/ui/coindesk-logo-512.png"},
    "cointelegraph":  {"name": "Cointelegraph", "url": "https://cointelegraph.com/apple-touch-icon.png"},
    "theblock":       {"name": "The Block", "url": "https://www.theblock.co/apple-icon.png"},
    "messari":        {"name": "Messari", "url": "https://messari.io/apple-icon.png"},
    "decrypt":        {"name": "Decrypt", "url": "https://decrypt.co/apple-touch-icon.png"},
    "cryptoslate":    {"name": "CryptoSlate", "url": "https://cryptoslate.com/apple-touch-icon.png"},
    "bloomberg":      {"name": "Bloomberg", "url": "https://www.bloomberg.com/apple-touch-icon.png"},
    "reuters":        {"name": "Reuters", "url": "https://www.reuters.com/pf/resources/images/reuters/apple-touch-icon.png"},
    "cnbc":           {"name": "CNBC", "url": "https://www.cnbc.com/apple-touch-icon.png"},
    "wsj":            {"name": "WSJ", "url": "https://s.wsj.net/img/meta/wsj-social-share.png"},
    "ft":             {"name": "Financial Times", "url": "https://www.ft.com/__assets/creatives/apple-touch-icon.png"},
    # Social platforms (source == platform)
    "twitter":        {"name": "X", "url": "https://abs.twimg.com/favicons/twitter.3.ico"},
    "x":              {"name": "X", "url": "https://abs.twimg.com/favicons/twitter.3.ico"},
    "telegram":       {"name": "Telegram", "url": "https://telegram.org/img/t_logo.png"},
    "discord":        {"name": "Discord", "url": "https://assets-global.website-files.com/6257adef93867e50d84d30e2/636e0a6ca814282eca7172c6_icon_clyde_white_RGB.svg"},
    "reddit":         {"name": "Reddit", "url": "https://www.redditstatic.com/icon.png"},
    "youtube":        {"name": "YouTube", "url": "https://www.youtube.com/s/desktop/12a35f2e/img/favicon_144x144.png"},
    # Data providers
    "coingecko":      {"name": "CoinGecko", "url": "https://static.coingecko.com/s/coingecko-logo-8903d34ce19ca4be1c81f0db30e924154750d208683fad7ae6f2ce06c76d0a56.png"},
    "coinmarketcap":  {"name": "CoinMarketCap", "url": "https://s2.coinmarketcap.com/static/cloud/img/coinmarketcap_1.png"},
    "santiment":      {"name": "Santiment", "url": "https://santiment.net/apple-touch-icon.png"},
    "glassnode":      {"name": "Glassnode", "url": "https://glassnode.com/apple-touch-icon.png"},
    "defillama":      {"name": "DefiLlama", "url": "https://icons.llamao.fi/icons/memes/llama?w=48&h=48"},
    "dextools":       {"name": "DEXTools", "url": "https://www.dextools.io/app/favicon/apple-touch-icon.png"},
    "dexscreener":    {"name": "DexScreener", "url": "https://dexscreener.com/favicon.png"},
    # Exchanges
    "binance":        {"name": "Binance", "url": "https://bin.bnbstatic.com/static/images/common/favicon.ico"},
    "coinbase":       {"name": "Coinbase", "url": "https://www.coinbase.com/apple-touch-icon.png"},
    "kraken":         {"name": "Kraken", "url": "https://assets.kraken.com/marketing/web/icons/apple-touch-icon.png"},
    "okx":            {"name": "OKX", "url": "https://www.okx.com/apple-touch-icon.png"},
    "bybit":          {"name": "Bybit", "url": "https://www.bybit.com/apple-touch-icon.png"},
    "bitfinex":       {"name": "Bitfinex", "url": "https://www.bitfinex.com/apple-touch-icon.png"},
    "kucoin":         {"name": "KuCoin", "url": "https://www.kucoin.com/apple-touch-icon.png"},
    "gate":           {"name": "Gate.io", "url": "https://www.gate.io/apple-touch-icon.png"},
    "mexc":           {"name": "MEXC", "url": "https://www.mexc.com/apple-touch-icon.png"},
    # On-chain
    "etherscan":      {"name": "Etherscan", "url": "https://etherscan.io/apple-touch-icon.png"},
    "arbiscan":       {"name": "Arbiscan", "url": "https://arbiscan.io/apple-touch-icon.png"},
    "basescan":       {"name": "BaseScan", "url": "https://basescan.org/apple-touch-icon.png"},
    # Markets beyond crypto
    "polymarket":     {"name": "Polymarket", "url": "https://polymarket.com/apple-touch-icon.png"},
    "kalshi":         {"name": "Kalshi", "url": "https://kalshi.com/apple-touch-icon.png"},
}


def resolve_source_logo(slug_or_url: str) -> dict:
    """
    Best-effort source logo lookup.
    Returns {"name", "url"} always — with a transparent-generic fallback if unknown.
    """
    key = (slug_or_url or "").strip().lower()
    # Exact slug hit
    if key in SOURCE_LOGOS:
        return SOURCE_LOGOS[key]
    # Domain-style ("https://www.coindesk.com/..." → "coindesk")
    for slug, meta in SOURCE_LOGOS.items():
        if slug in key:
            return meta
    return {
        "name": (slug_or_url or "Source").title(),
        "url": (
            "https://raw.githubusercontent.com/spothq/cryptocurrency-icons/"
            "master/svg/color/generic.svg"
        ),
    }
