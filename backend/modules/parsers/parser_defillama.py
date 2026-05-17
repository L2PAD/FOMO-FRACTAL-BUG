"""
DefiLlama Parser
================
Parser for DeFi protocol data from DefiLlama API.
Free API, no key required.

TIER 1 source - Core Data
Owner fields: tvl, protocols, chains, defi_categories

Endpoints:
- /protocols - All DeFi protocols with TVL
- /protocol/{slug} - Protocol details
- /chains - TVL by chain
- /tvl/{protocol} - Historical TVL
"""

import httpx
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from modules.intel.parser_validation import ParserValidator
from modules.parsers.base_reliable_parser import BaseReliableParser

logger = logging.getLogger(__name__)

BASE_URL = "https://api.llama.fi"


class DefiLlamaParser(BaseReliableParser):
    """Parser for DefiLlama DeFi data with validation and reliability tracking"""
    
    source_id = "defillama"
    
    def __init__(self, db):
        super().__init__(db)
        self.validator = ParserValidator(self.source_id)
        self.client = httpx.AsyncClient(timeout=30)
    
    async def close(self):
        await self.client.aclose()
    
    async def fetch_protocols(self, limit: int = 100) -> List[Dict]:
        """Fetch top DeFi protocols by TVL with reliability tracking"""
        start = time.time()
        try:
            resp = await self.client.get(f"{BASE_URL}/protocols")
            latency_ms = (time.time() - start) * 1000
            
            if resp.status_code == 200:
                protocols = resp.json()[:limit]
                
                await self.record_fetch_simple(
                    success=True,
                    latency_ms=latency_ms,
                    endpoint="protocols",
                    data_freshness_hours=0.5  # Updated every 30 min
                )
                
                logger.info(f"DefiLlama: Fetched {len(protocols)} protocols")
                return protocols
            else:
                await self.record_fetch_simple(
                    success=False,
                    latency_ms=latency_ms,
                    endpoint="protocols",
                    error=f"HTTP {resp.status_code}"
                )
                logger.warning(f"DefiLlama protocols failed: {resp.status_code}")
                return []
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            await self.record_fetch_simple(
                success=False,
                latency_ms=latency_ms,
                endpoint="protocols",
                error=str(e)
            )
            logger.error(f"DefiLlama protocols error: {e}")
            return []
    
    async def fetch_chains(self) -> List[Dict]:
        """Fetch TVL by chain with reliability tracking"""
        start = time.time()
        try:
            resp = await self.client.get(f"{BASE_URL}/v2/chains")
            latency_ms = (time.time() - start) * 1000
            
            if resp.status_code == 200:
                chains = resp.json()
                
                await self.record_fetch_simple(
                    success=True,
                    latency_ms=latency_ms,
                    endpoint="chains",
                    data_freshness_hours=0.5
                )
                
                logger.info(f"DefiLlama: Fetched {len(chains)} chains")
                return chains
            else:
                await self.record_fetch_simple(
                    success=False,
                    latency_ms=latency_ms,
                    endpoint="chains",
                    error=f"HTTP {resp.status_code}"
                )
                return []
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            await self.record_fetch_simple(
                success=False,
                latency_ms=latency_ms,
                endpoint="chains",
                error=str(e)
            )
            logger.error(f"DefiLlama chains error: {e}")
            return []
    
    async def fetch_protocol_tvl(self, slug: str) -> Optional[Dict]:
        """Fetch detailed protocol data including TVL history with reliability tracking"""
        start = time.time()
        try:
            resp = await self.client.get(f"{BASE_URL}/protocol/{slug}")
            latency_ms = (time.time() - start) * 1000
            
            if resp.status_code == 200:
                await self.record_fetch_simple(
                    success=True,
                    latency_ms=latency_ms,
                    endpoint=f"protocol/{slug}",
                    data_freshness_hours=1.0
                )
                return resp.json()
            
            await self.record_fetch_simple(
                success=False,
                latency_ms=latency_ms,
                endpoint=f"protocol/{slug}",
                error=f"HTTP {resp.status_code}"
            )
            return None
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            await self.record_fetch_simple(
                success=False,
                latency_ms=latency_ms,
                endpoint=f"protocol/{slug}",
                error=str(e)
            )
            logger.error(f"DefiLlama protocol {slug} error: {e}")
            return None
    
    async def sync_protocols(self, limit: int = 100) -> Dict[str, Any]:
        """Sync protocols to database"""
        protocols = await self.fetch_protocols(limit)
        now = datetime.now(timezone.utc).isoformat()
        
        synced = 0
        for p in protocols:
            doc = {
                "id": f"defillama:{p.get('slug', '')}",
                "source": "defillama",
                "name": p.get("name"),
                "slug": p.get("slug"),
                "symbol": p.get("symbol"),
                "category": p.get("category"),
                "chains": p.get("chains", []),
                "tvl": p.get("tvl", 0),
                "tvl_change_1d": p.get("change_1d"),
                "tvl_change_7d": p.get("change_7d"),
                "tvl_change_1m": p.get("change_1m"),
                "mcap": p.get("mcap"),
                "logo": p.get("logo"),
                "url": p.get("url"),
                "twitter": p.get("twitter"),
                "gecko_id": p.get("gecko_id"),
                "updated_at": now
            }
            
            await self.db.defi_protocols.update_one(
                {"id": doc["id"]},
                {"$set": doc},
                upsert=True
            )
            synced += 1
        
        # Update data source status
        await self._update_source_status("defillama", True, synced)
        
        return {"synced": synced, "source": "defillama"}
    
    async def sync_chains(self) -> Dict[str, Any]:
        """Sync chain TVL data"""
        chains = await self.fetch_chains()
        now = datetime.now(timezone.utc).isoformat()
        
        synced = 0
        for c in chains:
            doc = {
                "id": f"chain:{c.get('name', '').lower()}",
                "source": "defillama",
                "name": c.get("name"),
                "gecko_id": c.get("gecko_id"),
                "token_symbol": c.get("tokenSymbol"),
                "tvl": c.get("tvl", 0),
                "updated_at": now
            }
            
            await self.db.chain_tvl.update_one(
                {"id": doc["id"]},
                {"$set": doc},
                upsert=True
            )
            synced += 1
        
        return {"synced": synced, "type": "chains"}
    
    async def _update_source_status(self, source_id: str, success: bool, count: int):
        """Update data source sync status"""
        now = datetime.now(timezone.utc).isoformat()
        update = {
            "updated_at": now,
            "status": "active" if success else "error"
        }
        if success:
            update["last_sync"] = now
        
        await self.db.data_sources.update_one(
            {"id": source_id},
            {"$set": update, "$inc": {"sync_count": 1}}
        )


async def sync_defillama_data(db, limit: int = 100):
    """Main sync function for DefiLlama"""
    parser = DefiLlamaParser(db)
    try:
        result = await parser.sync_protocols(limit)
        chains = await parser.sync_chains()
        logger.info(f"DefiLlama sync complete: {result['synced']} protocols, {chains['synced']} chains")
        return {**result, "chains": chains["synced"]}
    finally:
        await parser.close()
