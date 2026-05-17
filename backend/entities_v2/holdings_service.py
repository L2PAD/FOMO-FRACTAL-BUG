"""
Entities V2 — Phase 3: Holdings Engine
=========================================
Computes real token holdings for each entity by analyzing
ERC20 transfer logs across all attributed addresses.

Data flow:
  entity_addresses_v2 → onchain_v2_erc20_logs → net balance per token
  token_registry → symbol, name, decimals
  onchain_v2_token_prices → USD pricing

Output collection:
  entity_holdings_v2 — Materialized holdings per entity
"""

import os
import time
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING, DESCENDING

_client = None
_db = None


def _get_db():
    global _client, _db
    if _db is None:
        _client = MongoClient(os.environ.get("MONGO_URL"))
        _db = _client[os.environ.get("DB_NAME", "test_database")]
    return _db


# ── Cache ──
_cache: dict = {}
_CACHE_TTL = 300


def _cache_get(k: str):
    e = _cache.get(k)
    return e["data"] if e and time.time() - e["ts"] < _CACHE_TTL else None


def _cache_set(k: str, data):
    _cache[k] = {"data": data, "ts": time.time()}


# ── Known stablecoin addresses (Ethereum mainnet) ──
STABLECOIN_ADDRESSES = {
    "0xdac17f958d2ee523a2206206994597c13d831ec7",  # USDT
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",  # USDC
    "0x6b175474e89094c44da98b954eedeac495271d0f",  # DAI
    "0x4fabb145d64652a948d72533023f6e7a623c7c53",  # BUSD
    "0x8e870d67f660d95d5be530380d0ec0bd388289e1",  # USDP
    "0x4c9edd5852cd905f086c759e8383e09bff1e68b3",  # USDe
}

MAJOR_ADDRESSES = {
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",  # WETH
    "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599",  # WBTC
    "0xae7ab96520de3a18e5e111b5eaab095312d7fe84",  # stETH
    "0xbe9895146f7af43049ca1c1ae358b0541ea49704",  # cbETH
}


def _load_token_meta() -> dict:
    """Load token metadata: {address: {symbol, name, decimals}}"""
    db = _get_db()
    meta = {}
    for doc in db["token_registry"].find({"chain": "ethereum"}, {"_id": 0}):
        addr = doc["address"].lower()
        # Prefer first seen (don't overwrite)
        if addr not in meta:
            meta[addr] = {
                "symbol": doc.get("symbol", "???"),
                "name": doc.get("name", "Unknown"),
                "decimals": doc.get("decimals", 18),
            }
    return meta


def _load_token_prices() -> dict:
    """Load token prices: {address: {priceUsd, source, confidence}}"""
    db = _get_db()
    prices = {}
    for doc in db["onchain_v2_token_prices"].find({"chainId": 1}, {"_id": 0}):
        addr = doc["token"].lower()
        prices[addr] = {
            "price_usd": doc.get("priceUsd", 0),
            "source": doc.get("source", "unknown"),
            "confidence": doc.get("confidence", 0),
        }
    # Stablecoins: fallback $1 if not in oracle
    for stable in STABLECOIN_ADDRESSES:
        if stable not in prices:
            prices[stable] = {"price_usd": 1.0, "source": "assumed_stable", "confidence": 0.9}
    return prices


def _compute_address_balances(address: str) -> dict:
    """
    Compute net token balances for a single address.
    Returns: {token_address: raw_balance (int)}
    Uses Python arbitrary-precision ints for wei values.
    """
    db = _get_db()
    erc20 = db["onchain_v2_erc20_logs"]

    balances: dict[str, int] = {}

    # Incoming transfers (address is receiver)
    for doc in erc20.find({"to": address}, {"_id": 0, "tokenAddress": 1, "value": 1}):
        token = doc.get("tokenAddress", "").lower()
        val_str = doc.get("value", "0")
        try:
            val = int(val_str)
        except (ValueError, TypeError):
            continue
        balances[token] = balances.get(token, 0) + val

    # Outgoing transfers (address is sender)
    for doc in erc20.find({"from": address}, {"_id": 0, "tokenAddress": 1, "value": 1}):
        token = doc.get("tokenAddress", "").lower()
        val_str = doc.get("value", "0")
        try:
            val = int(val_str)
        except (ValueError, TypeError):
            continue
        balances[token] = balances.get(token, 0) - val

    return balances


# ══════════════════════════════════════════════════════════
#  HOLDINGS BUILDER
# ══════════════════════════════════════════════════════════

def build_entity_holdings(slug: str) -> dict:
    """
    Compute real holdings for a specific entity.
    Aggregates across all attributed addresses.
    """
    db = _get_db()
    entity = db["entities_v2"].find_one({"slug": slug}, {"_id": 0})
    if not entity:
        return None

    # Get all addresses for this entity
    addresses = list(db["entity_addresses_v2"].find(
        {"entity_slug": slug},
        {"_id": 0, "address": 1, "role": 1, "confidence": 1},
    ))

    if not addresses:
        return _empty_holdings(entity)

    # Load reference data
    token_meta = _load_token_meta()
    token_prices = _load_token_prices()

    # Aggregate balances across all addresses
    entity_balances: dict[str, int] = {}
    address_coverage = {"total": len(addresses), "with_activity": 0}

    for addr_doc in addresses:
        address = addr_doc["address"]
        addr_balances = _compute_address_balances(address)
        if addr_balances:
            address_coverage["with_activity"] += 1
        for token, balance in addr_balances.items():
            entity_balances[token] = entity_balances.get(token, 0) + balance

    # Build holdings list
    holdings = []
    total_usd = 0.0
    priced_count = 0
    unpriced_count = 0

    for token_addr, raw_balance in entity_balances.items():
        if raw_balance <= 0:
            continue  # Skip tokens with zero or negative net balance

        meta = token_meta.get(token_addr, {})
        symbol = meta.get("symbol", token_addr[:8] + "...")
        name = meta.get("name", "Unknown Token")
        decimals = meta.get("decimals", 18)

        # Convert from wei to human-readable
        balance = raw_balance / (10 ** decimals)

        # Get price
        price_info = token_prices.get(token_addr)
        if price_info and price_info["price_usd"] > 0:
            usd_value = balance * price_info["price_usd"]
            priced_count += 1
            price_source = price_info["source"]
            price_confidence = price_info["confidence"]
        else:
            usd_value = 0.0
            unpriced_count += 1
            price_source = "none"
            price_confidence = 0.0

        # Classify token
        if token_addr in STABLECOIN_ADDRESSES:
            token_class = "stablecoin"
        elif token_addr in MAJOR_ADDRESSES:
            token_class = "major"
        else:
            token_class = "altcoin"

        holdings.append({
            "token_address": token_addr,
            "symbol": symbol,
            "name": name,
            "balance": round(balance, 8),
            "decimals": decimals,
            "usd_value": round(usd_value, 2),
            "price_usd": round(price_info["price_usd"], 6) if price_info else None,
            "price_source": price_source,
            "price_confidence": price_confidence,
            "token_class": token_class,
        })

        total_usd += usd_value

    # Sort by USD value descending
    holdings.sort(key=lambda h: h["usd_value"], reverse=True)

    # Compute shares
    for h in holdings:
        h["share"] = round(h["usd_value"] / total_usd, 4) if total_usd > 0 else 0.0

    # Concentration score (HHI - Herfindahl-Hirschman Index)
    shares = [h["share"] for h in holdings if h["share"] > 0]
    hhi = sum(s * s for s in shares) if shares else 0.0
    concentration_score = round(hhi, 4)

    # Portfolio structure
    stablecoin_usd = sum(h["usd_value"] for h in holdings if h["token_class"] == "stablecoin")
    major_usd = sum(h["usd_value"] for h in holdings if h["token_class"] == "major")
    altcoin_usd = sum(h["usd_value"] for h in holdings if h["token_class"] == "altcoin")

    # Confidence metrics
    all_tokens_count = priced_count + unpriced_count
    priced_coverage = round(priced_count / max(all_tokens_count, 1), 4)
    address_cov = round(address_coverage["with_activity"] / max(address_coverage["total"], 1), 4)

    now = datetime.now(timezone.utc)

    result = {
        "entity": {
            "slug": entity["slug"],
            "name": entity["name"],
            "type": entity["type"],
            "category": entity["category"],
        },
        "total_usd": round(total_usd, 2),
        "token_count": len(holdings),
        "concentration_score": concentration_score,
        "top_holdings": holdings[:20],
        "portfolio_structure": {
            "stablecoin_usd": round(stablecoin_usd, 2),
            "stablecoin_share": round(stablecoin_usd / total_usd, 4) if total_usd > 0 else 0.0,
            "major_usd": round(major_usd, 2),
            "major_share": round(major_usd / total_usd, 4) if total_usd > 0 else 0.0,
            "altcoin_usd": round(altcoin_usd, 2),
            "altcoin_share": round(altcoin_usd / total_usd, 4) if total_usd > 0 else 0.0,
        },
        "confidence": {
            "priced_coverage": priced_coverage,
            "priced_tokens": priced_count,
            "unpriced_tokens": unpriced_count,
            "address_coverage": address_cov,
            "active_addresses": address_coverage["with_activity"],
            "total_addresses": address_coverage["total"],
            "data_window": "partial",  # We only see transfers in our log window
            "note": "Balances derived from observed ERC20 transfers only. Actual holdings may differ.",
        },
        "computed_at": now.isoformat(),
    }

    # Persist to DB
    holdings_col = db["entity_holdings_v2"]
    holdings_col.create_index([("entity_slug", ASCENDING)], unique=True, background=True)
    holdings_col.update_one(
        {"entity_slug": slug},
        {"$set": {
            "entity_slug": slug,
            "entity_name": entity["name"],
            "total_usd": result["total_usd"],
            "token_count": result["token_count"],
            "concentration_score": result["concentration_score"],
            "holdings": holdings,
            "portfolio_structure": result["portfolio_structure"],
            "confidence": result["confidence"],
            "computed_at": now.isoformat(),
        }},
        upsert=True,
    )

    _cache.clear()
    return result


def _empty_holdings(entity: dict) -> dict:
    """Return empty holdings structure for entities with no addresses."""
    return {
        "entity": {
            "slug": entity["slug"],
            "name": entity["name"],
            "type": entity["type"],
            "category": entity["category"],
        },
        "total_usd": 0,
        "token_count": 0,
        "concentration_score": 0,
        "top_holdings": [],
        "portfolio_structure": {
            "stablecoin_usd": 0, "stablecoin_share": 0,
            "major_usd": 0, "major_share": 0,
            "altcoin_usd": 0, "altcoin_share": 0,
        },
        "confidence": {
            "priced_coverage": 0, "priced_tokens": 0, "unpriced_tokens": 0,
            "address_coverage": 0, "active_addresses": 0, "total_addresses": 0,
            "data_window": "none",
            "note": "No addresses attributed to this entity.",
        },
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════
#  QUERY FUNCTIONS
# ══════════════════════════════════════════════════════════

def get_entity_holdings(slug: str) -> dict | None:
    """Get cached holdings or compute fresh."""
    ck = f"holdings:{slug}"
    cached = _cache_get(ck)
    if cached:
        return cached

    db = _get_db()
    entity = db["entities_v2"].find_one({"slug": slug}, {"_id": 0})
    if not entity:
        return None

    # Check if we have pre-computed holdings
    stored = db["entity_holdings_v2"].find_one({"entity_slug": slug}, {"_id": 0})
    if stored:
        result = _format_stored_holdings(entity, stored)
        _cache_set(ck, result)
        return result

    # Compute on-the-fly
    result = build_entity_holdings(slug)
    if result:
        _cache_set(ck, result)
    return result


def _format_stored_holdings(entity: dict, stored: dict) -> dict:
    """Format stored holdings into API response shape."""
    return {
        "entity": {
            "slug": entity["slug"],
            "name": entity["name"],
            "type": entity["type"],
            "category": entity["category"],
        },
        "total_usd": stored.get("total_usd", 0),
        "token_count": stored.get("token_count", 0),
        "concentration_score": stored.get("concentration_score", 0),
        "top_holdings": stored.get("holdings", [])[:20],
        "portfolio_structure": stored.get("portfolio_structure", {}),
        "confidence": stored.get("confidence", {}),
        "computed_at": stored.get("computed_at"),
    }


def get_entity_portfolio(slug: str) -> dict | None:
    """
    Portfolio analysis — deeper breakdown of holdings.
    Adds: dominant asset analysis, class distribution, risk metrics.
    """
    holdings_data = get_entity_holdings(slug)
    if not holdings_data:
        return None

    all_holdings = holdings_data["top_holdings"]
    total_usd = holdings_data["total_usd"]
    structure = holdings_data["portfolio_structure"]

    # Dominant asset (top 1)
    dominant = all_holdings[0] if all_holdings else None

    # Top 3 concentration
    top3_share = sum(h["share"] for h in all_holdings[:3])

    # Token class counts
    class_counts = {"stablecoin": 0, "major": 0, "altcoin": 0}
    for h in all_holdings:
        cls = h.get("token_class", "altcoin")
        class_counts[cls] = class_counts.get(cls, 0) + 1

    # Risk indicators
    risk_flags = []
    if holdings_data["concentration_score"] > 0.5:
        risk_flags.append("HIGH_CONCENTRATION")
    if structure.get("stablecoin_share", 0) > 0.8:
        risk_flags.append("MOSTLY_STABLES")
    if holdings_data["confidence"].get("priced_coverage", 0) < 0.5:
        risk_flags.append("LOW_PRICE_COVERAGE")
    if holdings_data["confidence"].get("address_coverage", 0) < 0.5:
        risk_flags.append("LOW_ADDRESS_COVERAGE")

    return {
        "entity": holdings_data["entity"],
        "total_usd": total_usd,
        "token_count": holdings_data["token_count"],
        "dominant_asset": {
            "symbol": dominant["symbol"] if dominant else None,
            "usd_value": dominant["usd_value"] if dominant else 0,
            "share": dominant["share"] if dominant else 0,
        },
        "top3_concentration": round(top3_share, 4),
        "concentration_score": holdings_data["concentration_score"],
        "class_distribution": {
            "stablecoin": {
                "count": class_counts["stablecoin"],
                "usd": structure.get("stablecoin_usd", 0),
                "share": structure.get("stablecoin_share", 0),
            },
            "major": {
                "count": class_counts["major"],
                "usd": structure.get("major_usd", 0),
                "share": structure.get("major_share", 0),
            },
            "altcoin": {
                "count": class_counts["altcoin"],
                "usd": structure.get("altcoin_usd", 0),
                "share": structure.get("altcoin_share", 0),
            },
        },
        "risk_flags": risk_flags,
        "confidence": holdings_data["confidence"],
        "top_holdings": all_holdings[:10],
        "computed_at": holdings_data["computed_at"],
    }


def build_all_entity_holdings() -> dict:
    """Build holdings for all entities. Returns summary stats."""
    db = _get_db()
    entities = list(db["entities_v2"].find({"status": "active"}, {"_id": 0, "slug": 1}))

    stats = {
        "total_entities": len(entities),
        "computed": 0,
        "with_holdings": 0,
        "total_portfolio_usd": 0.0,
        "errors": 0,
    }

    for ent in entities:
        slug = ent["slug"]
        try:
            result = build_entity_holdings(slug)
            if result:
                stats["computed"] += 1
                if result["total_usd"] > 0:
                    stats["with_holdings"] += 1
                    stats["total_portfolio_usd"] += result["total_usd"]
        except Exception as e:
            stats["errors"] += 1
            print(f"[Holdings] Error building for {slug}: {e}")

    stats["total_portfolio_usd"] = round(stats["total_portfolio_usd"], 2)
    stats["built_at"] = datetime.now(timezone.utc).isoformat()
    _cache.clear()
    return stats


def get_holdings_overview() -> dict:
    """Overview of all entity holdings — leaderboard style."""
    db = _get_db()
    holdings_col = db["entity_holdings_v2"]

    all_holdings = list(holdings_col.find(
        {}, {"_id": 0, "entity_slug": 1, "entity_name": 1, "total_usd": 1,
             "token_count": 1, "concentration_score": 1, "computed_at": 1},
    ).sort("total_usd", -1))

    total_tracked = sum(h.get("total_usd", 0) for h in all_holdings)
    with_value = sum(1 for h in all_holdings if h.get("total_usd", 0) > 0)

    return {
        "total_entities_tracked": len(all_holdings),
        "entities_with_holdings": with_value,
        "total_tracked_usd": round(total_tracked, 2),
        "leaderboard": all_holdings[:20],
    }
