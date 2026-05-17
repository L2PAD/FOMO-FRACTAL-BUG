"""
Proxy Service — Real proxy rotation with failover
===================================================

Used by:
1. Parsers (CryptoRank, DefiLlama, CoinGecko, etc.)
2. Exchange providers (Binance, Bybit)

Failover logic:
- Sort proxies by priority (highest first), then by error_count (lowest first)
- Try each proxy in order
- If proxy fails, mark as unhealthy, try next
- If all proxies fail, try direct (no proxy)
- Periodic health checks restore recovered proxies
"""

import httpx
import asyncio
import logging
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

import os

logger = logging.getLogger(__name__)

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")

_instance = None


class ProxyService:
    """Singleton proxy service with failover tree logic"""

    def __init__(self, db):
        self.db = db
        self._cache = []
        self._cache_ts = 0
        self._cache_ttl = 30  # Refresh proxy list every 30s

    async def _get_proxies(self) -> List[Dict]:
        """Get sorted proxy list from DB (cached)"""
        now = time.time()
        if now - self._cache_ts > self._cache_ttl:
            self._cache = await self.db.proxy_pool.find(
                {"enabled": True},
                {"_id": 0}
            ).sort([("priority", -1), ("error_count", 1)]).to_list(50)
            self._cache_ts = now
        return self._cache

    def _build_proxy_url(self, proxy: Dict) -> str:
        """Build proxy URL from proxy document"""
        server = proxy.get("server", "")
        if not server:
            return ""
        # Ensure protocol prefix
        if "://" not in server:
            server = f"http://{server}"
        if proxy.get("username"):
            # Insert auth into URL
            proto, rest = server.split("://", 1)
            return f"{proto}://{proxy['username']}:{proxy.get('password', '')}@{rest}"
        return server

    async def request(
        self,
        url: str,
        method: str = "GET",
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: int = 20,
        use_proxy: bool = True,
        target: str = "parser"
    ) -> Dict[str, Any]:
        """
        Make HTTP request with proxy failover.

        Args:
            url: Target URL
            method: HTTP method
            params: Query params
            data: JSON body
            headers: Headers dict
            timeout: Request timeout in seconds
            use_proxy: Whether to use proxies
            target: "parser" or "exchange" — for logging/stats

        Returns:
            {"ok": bool, "data": ..., "proxy_used": str|None, "latency_ms": float}
        """
        req_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            **(headers or {})
        }

        proxies = await self._get_proxies() if use_proxy else []

        # Try each proxy in priority order
        for proxy in proxies:
            proxy_url = self._build_proxy_url(proxy)
            if not proxy_url:
                continue

            try:
                start = time.time()
                async with httpx.AsyncClient(
                    proxy=proxy_url,
                    timeout=timeout,
                    verify=False
                ) as client:
                    resp = await client.request(
                        method=method,
                        url=url,
                        params=params,
                        json=data if method in ("POST", "PUT", "PATCH") else None,
                        headers=req_headers
                    )
                    latency = int((time.time() - start) * 1000)

                    if resp.status_code < 400:
                        # Success — update proxy stats
                        await self.db.proxy_pool.update_one(
                            {"id": proxy["id"]},
                            {
                                "$set": {"healthy": True, "latency_ms": latency, "last_used": datetime.now(timezone.utc).isoformat()},
                                "$inc": {"success_count": 1}
                            }
                        )
                        try:
                            resp_data = resp.json()
                        except Exception:
                            resp_data = resp.text

                        return {
                            "ok": True,
                            "data": resp_data,
                            "status": resp.status_code,
                            "proxy_used": proxy["id"],
                            "latency_ms": latency
                        }
                    else:
                        logger.warning(f"[Proxy:{proxy['id']}] HTTP {resp.status_code} for {url}")
                        await self.db.proxy_pool.update_one(
                            {"id": proxy["id"]},
                            {"$inc": {"error_count": 1}, "$set": {"last_error": f"HTTP {resp.status_code}"}}
                        )

            except Exception as e:
                logger.warning(f"[Proxy:{proxy['id']}] Failed for {url}: {e}")
                await self.db.proxy_pool.update_one(
                    {"id": proxy["id"]},
                    {
                        "$set": {"healthy": False, "last_error": str(e)[:200]},
                        "$inc": {"error_count": 1}
                    }
                )
                self._cache_ts = 0  # Invalidate cache

        # All proxies failed (or no proxies) — try direct
        try:
            start = time.time()
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=data if method in ("POST", "PUT", "PATCH") else None,
                    headers=req_headers
                )
                latency = int((time.time() - start) * 1000)
                try:
                    resp_data = resp.json()
                except Exception:
                    resp_data = resp.text

                return {
                    "ok": resp.status_code < 400,
                    "data": resp_data,
                    "status": resp.status_code,
                    "proxy_used": None,
                    "latency_ms": latency
                }
        except Exception as e:
            return {"ok": False, "error": str(e), "proxy_used": None}

    # === Convenience methods ===

    async def get(self, url: str, params=None, headers=None, timeout=20, use_proxy=True, target="parser"):
        return await self.request(url, "GET", params=params, headers=headers, timeout=timeout, use_proxy=use_proxy, target=target)

    async def post(self, url: str, data=None, headers=None, timeout=20, use_proxy=True, target="parser"):
        return await self.request(url, "POST", data=data, headers=headers, timeout=timeout, use_proxy=use_proxy, target=target)


def get_proxy_service() -> ProxyService:
    """Get singleton ProxyService instance"""
    global _instance
    if _instance is None:
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        _instance = ProxyService(db)
    return _instance
