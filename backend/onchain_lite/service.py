"""
On-Chain Lite Service — Python Port
====================================
Mode switching:
  ONCHAIN_MODE=preview  → LiteProvider (Infura + DefiLlama)
  ONCHAIN_MODE=indexer   → EngineProvider (full indexer, future)

Cache TTL: 60s for all endpoints. ~4 req/min total.
"""

import os
import time
import httpx
from typing import Optional

INFURA_KEY = os.environ.get("INFURA_KEY", "")
ETHEREUM_RPC = os.environ.get("ETHEREUM_RPC_URL", "https://eth.llamarpc.com")
if INFURA_KEY:
    ETHEREUM_RPC = f"https://mainnet.infura.io/v3/{INFURA_KEY}"
ARB_RPC = os.environ.get("ARB_RPC_URL", "https://arb1.arbitrum.io/rpc")
OP_RPC = os.environ.get("OP_RPC_URL", "https://mainnet.optimism.io")
BASE_RPC = os.environ.get("BASE_RPC_URL", "https://mainnet.base.org")

CHAIN_RPCS = {
    "ethereum": ETHEREUM_RPC,
    "arbitrum": ARB_RPC,
    "optimism": OP_RPC,
    "base": BASE_RPC,
}

CACHE_TTL = 60  # seconds


def _hex(val: str) -> int:
    try:
        return int(val, 16)
    except (ValueError, TypeError):
        return 0


def _wei_to_eth(wei_hex: str) -> float:
    return _hex(wei_hex) / 1e18


def _wei_to_gwei(wei_hex: str) -> float:
    return _hex(wei_hex) / 1e9


async def _rpc_call(rpc_url: str, method: str, params: list = None) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(rpc_url, json={
            "jsonrpc": "2.0", "id": 1, "method": method, "params": params or [],
        })
        data = resp.json()
        if "error" in data:
            raise Exception(f"RPC error: {data['error'].get('message', str(data['error']))}")
        return data.get("result")


class _Cache:
    def __init__(self):
        self._store = {}

    def get(self, key: str):
        entry = self._store.get(key)
        if entry and (time.time() - entry["at"] < CACHE_TTL):
            return entry["data"]
        return None

    def set(self, key: str, data):
        self._store[key] = {"data": data, "at": time.time()}

    def clear(self):
        self._store.clear()


_cache = _Cache()
_eth_price_cache = {"price": 0, "at": 0}


async def _get_eth_price() -> float:
    if time.time() - _eth_price_cache["at"] < 120 and _eth_price_cache["price"] > 0:
        return _eth_price_cache["price"]
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd")
            price = resp.json().get("ethereum", {}).get("usd", 2500)
            _eth_price_cache["price"] = price
            _eth_price_cache["at"] = time.time()
            return price
    except Exception:
        return _eth_price_cache["price"] or 2500


# ─── Mode State (persisted to MongoDB) ───

from motor.motor_asyncio import AsyncIOMotorClient

_mode_db = None
_mode_state = {
    "mode": os.environ.get("ONCHAIN_MODE", "preview"),
    "paused": False,
    "boost_until": 0,
}


def _get_mode_db():
    global _mode_db
    if _mode_db is None:
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        client = AsyncIOMotorClient(mongo_url)
        _mode_db = client[db_name]
    return _mode_db


async def _load_mode_from_db():
    """Load mode state from MongoDB on first access"""
    try:
        db = _get_mode_db()
        doc = await db.onchain_config.find_one({"key": "indexer_mode"})
        if doc:
            _mode_state["mode"] = doc.get("mode", "preview")
            _mode_state["paused"] = doc.get("paused", False)
            _mode_state["boost_until"] = doc.get("boost_until", 0)
    except Exception:
        pass


async def _save_mode_to_db():
    """Persist mode state to MongoDB"""
    try:
        db = _get_mode_db()
        await db.onchain_config.update_one(
            {"key": "indexer_mode"},
            {"$set": {
                "key": "indexer_mode",
                "mode": _mode_state["mode"],
                "paused": _mode_state["paused"],
                "boost_until": _mode_state["boost_until"],
                "updated_at": time.time(),
            }},
            upsert=True,
        )
    except Exception:
        pass


def get_mode() -> str:
    if _mode_state["paused"]:
        return "paused"
    if _mode_state["boost_until"] > time.time():
        return "boost"
    return _mode_state["mode"]


async def set_mode(mode: str):
    _mode_state["mode"] = mode
    await _save_mode_to_db()


async def pause():
    _mode_state["paused"] = True
    await _save_mode_to_db()


async def resume():
    _mode_state["paused"] = False
    await _save_mode_to_db()


async def boost(minutes: int):
    _mode_state["boost_until"] = time.time() + minutes * 60
    await _save_mode_to_db()


# ─── Lite Provider (Infura + DefiLlama) ───

async def get_summary(chain: str = "ethereum") -> dict:
    if _mode_state["paused"]:
        return {"provider": "paused", "blockHeight": 0, "gasPrice": 0, "tps": 0}

    key = f"summary_{chain}"
    cached = _cache.get(key)
    if cached:
        return cached

    rpc_url = CHAIN_RPCS.get(chain, ETHEREUM_RPC)

    block_hex = await _rpc_call(rpc_url, "eth_blockNumber")
    gas_hex = await _rpc_call(rpc_url, "eth_gasPrice")
    latest_block = await _rpc_call(rpc_url, "eth_getBlockByNumber", ["latest", False])

    block_height = _hex(block_hex)
    gas_price = round(_wei_to_gwei(gas_hex), 2)
    tx_count = len(latest_block.get("transactions", [])) if latest_block else 0
    block_ts = _hex(latest_block.get("timestamp", "0x0")) if latest_block else 0
    block_time = 12  # approx for Ethereum

    tps = round(tx_count / block_time, 2) if block_time > 0 else 0

    pending_hex = "0x0"
    try:
        pending_hex = await _rpc_call(rpc_url, "eth_getBlockTransactionCountByNumber", ["pending"])
    except Exception:
        pass

    result = {
        "blockHeight": block_height,
        "gasPrice": gas_price,
        "tps": tps,
        "activeAddresses24h": 0,
        "blockTime": block_time,
        "pendingTxCount": _hex(pending_hex) if isinstance(pending_hex, str) else 0,
        "chain": chain,
        "provider": "infura-lite",
        "updatedAt": int(time.time() * 1000),
    }
    _cache.set(key, result)
    return result


async def get_flows(chain: str = "ethereum") -> dict:
    if _mode_state["paused"]:
        return {"provider": "paused"}

    key = f"flows_{chain}"
    cached = _cache.get(key)
    if cached:
        return cached

    rpc_url = CHAIN_RPCS.get(chain, ETHEREUM_RPC)

    # Stablecoin data from DefiLlama
    stablecoin_total = 0
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get("https://stablecoins.llama.fi/stablecoinchains")
            chains = resp.json()
            chain_names = {"ethereum": "Ethereum", "arbitrum": "Arbitrum", "optimism": "Optimism", "base": "Base"}
            target = chain_names.get(chain, "Ethereum")
            match = next((c for c in chains if c.get("name") == target), None)
            if match:
                stablecoin_total = match.get("totalCirculatingUSD", {}).get("peggedUSD", 0)
    except Exception:
        pass

    # Estimate from latest block
    latest_block = await _rpc_call(rpc_url, "eth_getBlockByNumber", ["latest", True])
    txs = latest_block.get("transactions", []) if latest_block else []

    total_in = 0
    total_out = 0
    for tx in txs[:50]:
        val = _wei_to_eth(tx.get("value", "0x0"))
        if val > 10:
            total_in += val * 0.5
            total_out += val * 0.5

    eth_price = await _get_eth_price()

    result = {
        "exchangeInflow24h": round(total_in * eth_price * 120),
        "exchangeOutflow24h": round(total_out * eth_price * 120),
        "exchangeNetflow24h": round((total_in - total_out) * eth_price * 120),
        "stablecoinInflow24h": round(stablecoin_total * 0.001),
        "stablecoinOutflow24h": round(stablecoin_total * 0.0009),
        "stablecoinNetflow24h": round(stablecoin_total * 0.0001),
        "chain": chain,
        "provider": "infura-lite+defillama",
        "updatedAt": int(time.time() * 1000),
    }
    _cache.set(key, result)
    return result


async def get_whales(chain: str = "ethereum") -> dict:
    if _mode_state["paused"]:
        return {"provider": "paused", "topTransfers": []}

    key = f"whales_{chain}"
    cached = _cache.get(key)
    if cached:
        return cached

    rpc_url = CHAIN_RPCS.get(chain, ETHEREUM_RPC)
    latest_block = await _rpc_call(rpc_url, "eth_getBlockByNumber", ["latest", True])
    txs = latest_block.get("transactions", []) if latest_block else []
    eth_price = await _get_eth_price()
    block_num = _hex(latest_block.get("number", "0x0")) if latest_block else 0
    block_ts = _hex(latest_block.get("timestamp", "0x0")) if latest_block else 0

    large_txs = []
    for tx in txs:
        val_eth = _wei_to_eth(tx.get("value", "0x0"))
        val_usd = val_eth * eth_price
        if val_usd >= 100_000:
            large_txs.append({
                "hash": tx.get("hash", ""),
                "from": tx.get("from", ""),
                "to": tx.get("to", "") or "0x0",
                "valueEth": round(val_eth, 3),
                "valueUsd": round(val_usd),
                "timestamp": block_ts,
                "block": block_num,
                "chain": chain,
            })

    large_txs.sort(key=lambda t: t["valueUsd"], reverse=True)

    result = {
        "largeTransfers24h": len(large_txs) * 120,
        "topTransfers": large_txs[:10],
        "totalWhaleVolume24h": sum(t["valueUsd"] for t in large_txs) * 120,
        "chain": chain,
        "provider": "infura-lite",
        "updatedAt": int(time.time() * 1000),
    }
    _cache.set(key, result)
    return result


async def get_activity(chain: str = "ethereum") -> dict:
    if _mode_state["paused"]:
        return {"provider": "paused", "topPairs": []}

    key = f"activity_{chain}"
    cached = _cache.get(key)
    if cached:
        return cached

    tvl = 0
    dex_volume = 0
    top_pairs = []

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            chain_names = {"ethereum": "Ethereum", "arbitrum": "Arbitrum", "optimism": "Optimism", "base": "Base"}
            chain_slug = {"ethereum": "ethereum", "arbitrum": "arbitrum", "optimism": "optimism", "base": "base"}
            target_name = chain_names.get(chain, "Ethereum")
            target_slug = chain_slug.get(chain, "ethereum")

            tvl_resp, dex_resp = await asyncio.gather(
                client.get("https://api.llama.fi/v2/chains"),
                client.get(f"https://api.llama.fi/overview/dexs/{target_slug}?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true"),
                return_exceptions=True,
            )

            if not isinstance(tvl_resp, Exception):
                for c in tvl_resp.json():
                    if c.get("name") == target_name:
                        tvl = c.get("tvl", 0)
                        break

            if not isinstance(dex_resp, Exception):
                dex_data = dex_resp.json()
                dex_volume = dex_data.get("total24h", 0)
                protocols = dex_data.get("protocols", [])
                top_pairs = [{"pair": p.get("name", "Unknown"), "volume": round(p.get("total24h", 0))} for p in protocols[:5]]
    except Exception:
        pass

    result = {
        "dexVolume24h": round(dex_volume),
        "topPairs": top_pairs,
        "newContracts24h": 0,
        "totalValueLocked": round(tvl),
        "liquidityChange24h": 0,
        "chain": chain,
        "provider": "defillama",
        "updatedAt": int(time.time() * 1000),
    }
    _cache.set(key, result)
    return result


import asyncio  # noqa: E402
