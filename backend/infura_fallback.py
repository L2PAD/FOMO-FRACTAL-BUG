"""
Infura RPC Fallback — Graph Data Provider
==========================================
Fetches on-chain transfer data for addresses not present in graph_relations.
Uses eth_getLogs with ERC20 Transfer events.

Flow:
  1. Fetch outgoing Transfer events (address as sender)
  2. Fetch incoming Transfer events (address as receiver)
  3. Aggregate by counterparty
  4. Save to graph_nodes + graph_relations
  5. Return (nodes, edges) in unified format

Config:
  INFURA_KEY env var
  Ethereum mainnet only
"""

import os
import asyncio
from datetime import datetime, timezone
from collections import defaultdict

import httpx

from graph_normalizer import normalize_node_id

INFURA_URL = "https://mainnet.infura.io/v3/{key}"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# Fetch last ~1 hour of blocks (~300 blocks at 12s/block)
# Infura limits large ranges, so keep it small and aggregate
BLOCK_RANGE = 2000
MAX_LOGS_PER_QUERY = 2000
MAX_COUNTERPARTIES = 50

_db = None


def init_infura_fallback(database):
    global _db
    _db = database


def _get_infura_url():
    key = os.environ.get("INFURA_KEY", "")
    if not key:
        return None
    return INFURA_URL.format(key=key)


def _pad_address(addr: str) -> str:
    """Pad an Ethereum address to 32 bytes for log topic filtering"""
    clean = addr.lower().replace("0x", "")
    return "0x" + clean.zfill(64)


def _unpad_address(topic: str) -> str:
    """Extract Ethereum address from 32-byte topic"""
    return "0x" + topic[-40:].lower()


async def _rpc_call(url: str, method: str, params: list) -> dict:
    """Make a JSON-RPC call to Infura"""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=payload)
        return resp.json()


async def fetch_transfers_for_address(address: str) -> dict:
    """
    Fetch ERC20 Transfer events for an address from Infura.
    Returns aggregated counterparty data:
    {
        counterparty_address: {
            "in_count": int,
            "out_count": int,
            "tokens": set of token contract addresses,
        }
    }
    """
    url = _get_infura_url()
    if not url:
        return {}

    addr_lower = address.lower()
    padded = _pad_address(addr_lower)

    # Get latest block number
    result = await _rpc_call(url, "eth_blockNumber", [])
    if "error" in result or "result" not in result:
        print(f"[Infura] Failed to get block number: {result.get('error', {})}")
        return {}

    latest_block = int(result["result"], 16)
    from_block = hex(max(0, latest_block - BLOCK_RANGE))
    to_block = "latest"

    counterparties = defaultdict(lambda: {"in_count": 0, "out_count": 0, "tokens": set()})

    # Fetch OUTGOING transfers (address is sender = topic[1])
    try:
        out_result = await _rpc_call(url, "eth_getLogs", [{
            "fromBlock": from_block,
            "toBlock": to_block,
            "topics": [TRANSFER_TOPIC, padded, None],
        }])

        logs = out_result.get("result", [])
        if isinstance(logs, list):
            for log in logs[:MAX_LOGS_PER_QUERY]:
                topics = log.get("topics", [])
                if len(topics) >= 3:
                    to_addr = _unpad_address(topics[2])
                    token = log.get("address", "").lower()
                    counterparties[to_addr]["out_count"] += 1
                    counterparties[to_addr]["tokens"].add(token)
            print(f"[Infura] {addr_lower[:10]}... outgoing: {len(logs)} logs")
    except Exception as e:
        print(f"[Infura] Outgoing fetch error: {e}")

    # Small delay to respect rate limits
    await asyncio.sleep(0.2)

    # Fetch INCOMING transfers (address is receiver = topic[2])
    try:
        in_result = await _rpc_call(url, "eth_getLogs", [{
            "fromBlock": from_block,
            "toBlock": to_block,
            "topics": [TRANSFER_TOPIC, None, padded],
        }])

        logs = in_result.get("result", [])
        if isinstance(logs, list):
            for log in logs[:MAX_LOGS_PER_QUERY]:
                topics = log.get("topics", [])
                if len(topics) >= 3:
                    from_addr = _unpad_address(topics[1])
                    token = log.get("address", "").lower()
                    counterparties[from_addr]["in_count"] += 1
                    counterparties[from_addr]["tokens"].add(token)
            print(f"[Infura] {addr_lower[:10]}... incoming: {len(logs)} logs")
    except Exception as e:
        print(f"[Infura] Incoming fetch error: {e}")

    return counterparties


async def infura_fallback_for_node(node_id: str, node_type: str = "wallet", chain: str = "ethereum"):
    """
    Full fallback pipeline:
    1. Fetch transfers from Infura
    2. Create graph_nodes for counterparties
    3. Create graph_relations
    4. Return (nodes, edges) in unified format
    """
    if _db is None:
        return [], []

    from graph_normalizer import extract_address
    address = extract_address(node_id)

    if not address or len(address) < 10:
        return [], []

    print(f"[Infura Fallback] Fetching data for {node_id}")
    counterparties = await fetch_transfers_for_address(address)

    if not counterparties:
        print(f"[Infura Fallback] No data found for {address[:10]}...")
        return [], []

    # Sort by total activity, take top N
    sorted_cps = sorted(
        counterparties.items(),
        key=lambda x: x[1]["in_count"] + x[1]["out_count"],
        reverse=True,
    )[:MAX_COUNTERPARTIES]

    nodes = []
    edges = []
    now_iso = datetime.now(timezone.utc).isoformat()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    # Ensure center node exists
    center_node = await _db["graph_nodes"].find_one({"id": node_id}, {"_id": 0})
    if center_node:
        nodes.append(center_node)
    else:
        center_node = {
            "id": node_id,
            "type": node_type,
            "chain": chain,
            "address": address,
            "label": f"0x{address[2:6]}...{address[-4:]}",
            "degree": len(sorted_cps),
            "updated_at": now_iso,
        }
        await _db["graph_nodes"].update_one({"id": node_id}, {"$set": center_node}, upsert=True)
        nodes.append(center_node)

    # Process counterparties
    for cp_addr, stats in sorted_cps:
        total_tx = stats["in_count"] + stats["out_count"]
        if total_tx < 1:
            continue

        # Resolve counterparty type from existing data
        cp_node = await _db["graph_nodes"].find_one({"address": cp_addr}, {"_id": 0})
        if cp_node:
            cp_id = cp_node["id"]
            cp_type = cp_node.get("type", "wallet")
        else:
            cp_type = "wallet"
            cp_id = normalize_node_id(cp_type, cp_addr, chain)
            cp_node = {
                "id": cp_id,
                "type": cp_type,
                "chain": chain,
                "address": cp_addr,
                "label": f"0x{cp_addr[2:6]}...{cp_addr[-4:]}",
                "degree": 0,
                "updated_at": now_iso,
            }
            await _db["graph_nodes"].update_one({"id": cp_id}, {"$set": cp_node}, upsert=True)

        nodes.append(cp_node)

        # Determine direction and relation type
        if stats["out_count"] > stats["in_count"]:
            direction = "out"
        else:
            direction = "in"

        relation_type = "transfer"
        if cp_type == "cex":
            relation_type = "deposit" if direction == "out" else "withdraw"
        elif cp_type == "dex":
            relation_type = "swap"

        # Save relation to DB
        rel_data = {
            "source_id": node_id,
            "target_id": cp_id,
            "relation_type": relation_type,
            "direction": direction,
            "chain": chain,
            "tx_count": total_tx,
            "total_amount_usd": 0,
            "first_seen": now_ts,
            "last_seen": now_ts,
            "confidence": 0.7,
            "tags": ["infura_rpc"],
            "updated_at": now_iso,
        }
        await _db["graph_relations"].update_one(
            {"source_id": node_id, "target_id": cp_id, "relation_type": relation_type},
            {"$set": rel_data},
            upsert=True,
        )

        # Build edge for response
        edges.append({
            "id": f"{node_id}-{cp_id}-{relation_type}",
            "source": node_id,
            "target": cp_id,
            "direction": direction,
            "type": relation_type,
            "amountUsd": 0,
            "timestamp": now_ts,
            "chain": chain,
            "tags": ["infura_rpc"],
        })

    # Update center node degree
    await _db["graph_nodes"].update_one(
        {"id": node_id},
        {"$set": {"degree": len(edges)}},
    )

    print(f"[Infura Fallback] Built: {len(nodes)} nodes, {len(edges)} edges for {node_id}")
    return nodes, edges
