"""
Data Pipeline — Feeds the system with real data from parsers
=============================================================

Runs parsers to populate MongoDB collections:
1. CryptoRank → cryptorank_projects, cryptorank_funds, funding_rounds
2. CoinGecko → coingecko_coins, market_data
3. DefiLlama → defi_protocols, chain_tvl
4. Entity Discovery → entity_candidates
5. Graph Builder → graph_nodes, graph_relations (from funding data)

No external API keys required — uses free public endpoints + seed data.
"""

import asyncio
import os
import sys
import time
import logging
import httpx
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from motor.motor_asyncio import AsyncIOMotorClient

# Setup path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("DataPipeline")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")


async def get_active_proxy(db) -> str:
    """Get highest-priority active proxy URL for parsers"""
    proxy = await db.proxy_pool.find_one(
        {"enabled": True, "healthy": {"$ne": False}},
        {"_id": 0},
        sort=[("priority", -1), ("error_count", 1)]
    )
    if not proxy:
        return None
    server = proxy.get("server", "")
    if not server.startswith("http"):
        server = f"http://{server}"
    if proxy.get("username"):
        proto, rest = server.split("://", 1)
        return f"{proto}://{proxy['username']}:{proxy.get('password', '')}@{rest}"
    return server


def make_client(proxy_url=None, timeout=30):
    """Create httpx client optionally with proxy"""
    kwargs = {"timeout": timeout, "headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }}
    if proxy_url:
        kwargs["proxy"] = proxy_url
        kwargs["verify"] = False
    return httpx.AsyncClient(**kwargs)

# =====================================================
# STEP 1: CryptoRank — coins + funding data
# =====================================================

async def fetch_cryptorank_coins(db, limit=300):
    """Fetch coins from CryptoRank free API → cryptorank_projects"""
    logger.info("[CryptoRank] Fetching coins...")
    proxy_url = await get_active_proxy(db)
    if proxy_url:
        logger.info(f"[CryptoRank] Using proxy: {proxy_url[:30]}...")
    try:
        async with make_client(proxy_url) as client:
            resp = await client.get(
                "https://api.cryptorank.io/v0/coins",
                params={"limit": limit}
            )
            if resp.status_code != 200:
                logger.warning(f"[CryptoRank] API returned {resp.status_code}")
                return 0

            data = resp.json()
            coins = data.get("data", [])
            now = datetime.now(timezone.utc)
            count = 0

            for c in coins:
                key = c.get("key", "")
                price_obj = c.get("price") or {}
                price_usd = price_obj.get("USD") if isinstance(price_obj, dict) else price_obj
                doc = {
                    "cryptorank_id": c.get("rank"),
                    "name": c.get("name"),
                    "symbol": (c.get("symbol") or "").upper(),
                    "slug": key,
                    "key": key,
                    "rank": c.get("rank"),
                    "price_usd": price_usd,
                    "market_cap": c.get("marketCap"),
                    "volume_24h": c.get("volume24h"),
                    "category": c.get("category"),
                    "has_funding_rounds": c.get("hasFundingRounds", False),
                    "source": "cryptorank",
                    "updated_at": now
                }
                if not key:
                    continue
                await db.cryptorank_projects.update_one(
                    {"slug": key},
                    {"$set": doc},
                    upsert=True
                )
                # Also populate coingecko_coins-like collection for validation
                await db.coingecko_coins.update_one(
                    {"id": key},
                    {"$set": {
                        "id": key,
                        "name": doc["name"],
                        "symbol": doc["symbol"],
                        "market_cap_rank": doc["rank"],
                        "source": "cryptorank_cross",
                        "updated_at": now
                    }},
                    upsert=True
                )
                count += 1

            logger.info(f"[CryptoRank] Synced {count} coins → cryptorank_projects")
            return count
    except Exception as e:
        logger.error(f"[CryptoRank] Error: {e}")
        return 0


async def seed_cryptorank_funds(db):
    """Seed known VC funds into cryptorank_funds from real_investments.py"""
    from knowledge_graph.real_investments import ALL_INVESTMENTS_EXTENDED
    now = datetime.now(timezone.utc)
    count = 0

    # Extract unique fund names
    fund_meta = {
        "a16z": {"name": "a16z Crypto", "type": "Venture Capital", "tier": 1},
        "paradigm": {"name": "Paradigm", "type": "Venture Capital", "tier": 1},
        "coinbase-ventures": {"name": "Coinbase Ventures", "type": "Corporate VC", "tier": 1},
        "binance-labs": {"name": "Binance Labs", "type": "Corporate VC", "tier": 1},
        "polychain": {"name": "Polychain Capital", "type": "Venture Capital", "tier": 1},
        "pantera": {"name": "Pantera Capital", "type": "Venture Capital", "tier": 1},
        "dragonfly": {"name": "Dragonfly", "type": "Venture Capital", "tier": 1},
        "multicoin": {"name": "Multicoin Capital", "type": "Venture Capital", "tier": 1},
        "sequoia": {"name": "Sequoia Capital", "type": "Venture Capital", "tier": 1},
        "galaxy": {"name": "Galaxy Digital", "type": "Asset Management", "tier": 1},
        "jump-crypto": {"name": "Jump Crypto", "type": "Trading/VC", "tier": 1},
        "framework": {"name": "Framework Ventures", "type": "Venture Capital", "tier": 2},
        "hack-vc": {"name": "Hack VC", "type": "Venture Capital", "tier": 2},
        "animoca": {"name": "Animoca Brands", "type": "Gaming/VC", "tier": 1},
        "spartan": {"name": "Spartan Group", "type": "Venture Capital", "tier": 2},
        "delphi": {"name": "Delphi Ventures", "type": "Research/VC", "tier": 2},
        "dcg": {"name": "Digital Currency Group", "type": "Conglomerate", "tier": 1},
        "placeholder": {"name": "Placeholder VC", "type": "Venture Capital", "tier": 2},
        "robot-ventures": {"name": "Robot Ventures", "type": "Venture Capital", "tier": 2},
    }

    for slug, meta in fund_meta.items():
        investments = ALL_INVESTMENTS_EXTENDED.get(slug, [])
        portfolio_count = len(investments)
        total_deployed = sum(inv.get("amount", 0) for inv in investments)

        doc = {
            "slug": slug,
            "key": slug,
            "name": meta["name"],
            "type": meta["type"],
            "tier": meta["tier"],
            "portfolio_count": portfolio_count,
            "total_deployed_usd": total_deployed,
            "source": "cryptorank_seed",
            "updated_at": now
        }
        await db.cryptorank_funds.update_one(
            {"slug": slug},
            {"$set": doc},
            upsert=True
        )
        count += 1

    logger.info(f"[CryptoRank] Seeded {count} funds → cryptorank_funds")
    return count


async def seed_funding_rounds(db):
    """Seed funding_rounds collection from real_investments.py + extended rounds"""
    from knowledge_graph.real_investments import ALL_INVESTMENTS_EXTENDED
    now = datetime.now(timezone.utc)
    count = 0

    # Build funding rounds from ALL_INVESTMENTS_EXTENDED
    project_rounds = defaultdict(list)
    for fund_slug, investments in ALL_INVESTMENTS_EXTENDED.items():
        for inv in investments:
            project_key = inv["project"]
            project_rounds[project_key].append({
                "fund_slug": fund_slug,
                "fund_name": inv.get("fund_name", fund_slug),
                "amount": inv.get("amount", 0),
                "round": inv.get("round", "Unknown"),
                "year": inv.get("year", 0),
            })

    for project_key, rounds in project_rounds.items():
        # Group by round type
        round_groups = defaultdict(list)
        for r in rounds:
            round_groups[r["round"]].append(r)

        for round_type, investors_data in round_groups.items():
            total_raised = sum(i["amount"] for i in investors_data)
            investor_names = list(set(i["fund_slug"] for i in investors_data))
            year = max(i["year"] for i in investors_data) if investors_data else 0

            round_id = f"seed:{project_key}:{round_type.lower().replace(' ', '_')}"
            doc = {
                "id": round_id,
                "project": investors_data[0].get("fund_name", project_key),
                "project_name": project_key,
                "project_key": project_key,
                "round_type": round_type,
                "raised_usd": total_raised,
                "investors": investor_names,
                "lead_investors": investor_names[:2],
                "year": year,
                "source": "seed_data",
                "created_at": now,
                "updated_at": now
            }
            await db.funding_rounds.update_one(
                {"id": round_id},
                {"$set": doc},
                upsert=True
            )
            count += 1

    # Add additional known recent rounds not in real_investments.py
    extra_rounds = [
        {"project_name": "Monad", "raised_usd": 225_000_000, "round_type": "Series A", "investors": ["paradigm", "dragonfly"], "year": 2024},
        {"project_name": "Story Protocol", "raised_usd": 140_000_000, "round_type": "Series B", "investors": ["a16z", "polychain"], "year": 2024},
        {"project_name": "Berachain", "raised_usd": 100_000_000, "round_type": "Series B", "investors": ["framework", "polychain"], "year": 2024},
        {"project_name": "Movement Labs", "raised_usd": 38_000_000, "round_type": "Series A", "investors": ["polychain"], "year": 2024},
        {"project_name": "Avail", "raised_usd": 75_000_000, "round_type": "Series A", "investors": ["dragonfly", "coinbase-ventures"], "year": 2024},
        {"project_name": "Humanity Protocol", "raised_usd": 30_000_000, "round_type": "Seed", "investors": ["pantera", "multicoin"], "year": 2024},
        {"project_name": "Succinct", "raised_usd": 55_000_000, "round_type": "Series A", "investors": ["paradigm", "robot-ventures"], "year": 2024},
        {"project_name": "Initia", "raised_usd": 7_500_000, "round_type": "Seed", "investors": ["binance-labs", "delphi"], "year": 2024},
        {"project_name": "Aligned Layer", "raised_usd": 20_000_000, "round_type": "Series A", "investors": ["hack-vc"], "year": 2024},
        {"project_name": "Hyperlane", "raised_usd": 18_500_000, "round_type": "Series A", "investors": ["galaxy"], "year": 2023},
        {"project_name": "Espresso Systems", "raised_usd": 28_000_000, "round_type": "Series B", "investors": ["sequoia", "polychain"], "year": 2023},
        {"project_name": "Eclipse", "raised_usd": 50_000_000, "round_type": "Series A", "investors": ["polychain", "hack-vc"], "year": 2024},
        {"project_name": "MegaETH", "raised_usd": 20_000_000, "round_type": "Seed", "investors": ["dragonfly"], "year": 2024},
        {"project_name": "Babylon", "raised_usd": 70_000_000, "round_type": "Series A", "investors": ["paradigm", "polychain"], "year": 2024},
        {"project_name": "Morph", "raised_usd": 20_000_000, "round_type": "Seed", "investors": ["dragonfly", "pantera"], "year": 2024},
        {"project_name": "Particle Network", "raised_usd": 25_000_000, "round_type": "Series A", "investors": ["spartan", "animoca"], "year": 2024},
        {"project_name": "io.net", "raised_usd": 30_000_000, "round_type": "Series A", "investors": ["hack-vc", "multicoin"], "year": 2024},
        {"project_name": "Aethir", "raised_usd": 9_000_000, "round_type": "Pre-Series A", "investors": ["framework", "animoca"], "year": 2024},
        {"project_name": "Symbiotic", "raised_usd": 5_800_000, "round_type": "Seed", "investors": ["paradigm", "coinbase-ventures"], "year": 2024},
    ]

    for r in extra_rounds:
        rid = f"extra:{r['project_name'].lower().replace(' ', '-')}:{r['round_type'].lower().replace(' ', '_')}"
        doc = {
            "id": rid,
            "project_name": r["project_name"],
            "project_key": r["project_name"].lower().replace(" ", "-"),
            "round_type": r["round_type"],
            "raised_usd": r["raised_usd"],
            "investors": r["investors"],
            "lead_investors": r["investors"][:1],
            "year": r["year"],
            "source": "verified_public",
            "created_at": now,
            "updated_at": now
        }
        await db.funding_rounds.update_one(
            {"id": rid},
            {"$set": doc},
            upsert=True
        )
        count += 1

    logger.info(f"[FundingRounds] Seeded {count} funding rounds → funding_rounds")
    return count


# =====================================================
# STEP 2: CoinGecko — market data
# =====================================================

async def fetch_coingecko_markets(db, limit=250):
    """Fetch top coins from CoinGecko free API → coingecko_coins + market_data"""
    logger.info("[CoinGecko] Fetching market data...")
    proxy_url = await get_active_proxy(db)
    try:
        async with make_client(proxy_url) as client:
            all_coins = []
            for page in [1, 2, 3]:
                resp = await client.get(
                    "https://api.coingecko.com/api/v3/coins/markets",
                    params={
                        "vs_currency": "usd",
                        "order": "market_cap_desc",
                        "per_page": min(limit, 100),
                        "page": page,
                        "sparkline": "false"
                    }
                )
                if resp.status_code == 200:
                    all_coins.extend(resp.json())
                elif resp.status_code == 429:
                    logger.warning("[CoinGecko] Rate limited, waiting 60s...")
                    await asyncio.sleep(60)
                    resp = await client.get(
                        "https://api.coingecko.com/api/v3/coins/markets",
                        params={
                            "vs_currency": "usd",
                            "order": "market_cap_desc",
                            "per_page": min(limit, 100),
                            "page": page,
                            "sparkline": "false"
                        }
                    )
                    if resp.status_code == 200:
                        all_coins.extend(resp.json())
                else:
                    logger.warning(f"[CoinGecko] API returned {resp.status_code}")
                    break
                await asyncio.sleep(2)  # Rate limit

            now = datetime.now(timezone.utc)
            count = 0
            for c in all_coins:
                doc = {
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "symbol": (c.get("symbol") or "").upper(),
                    "market_cap_rank": c.get("market_cap_rank"),
                    "current_price": c.get("current_price"),
                    "market_cap": c.get("market_cap"),
                    "total_volume": c.get("total_volume"),
                    "price_change_24h": c.get("price_change_percentage_24h"),
                    "circulating_supply": c.get("circulating_supply"),
                    "total_supply": c.get("total_supply"),
                    "ath": c.get("ath"),
                    "logo_url": c.get("image"),
                    "source": "coingecko",
                    "updated_at": now
                }
                await db.coingecko_coins.update_one(
                    {"id": doc["id"]},
                    {"$set": doc},
                    upsert=True
                )
                await db.market_data.update_one(
                    {"coingecko_id": doc["id"]},
                    {"$set": {**doc, "coingecko_id": doc["id"]}},
                    upsert=True
                )
                count += 1

            logger.info(f"[CoinGecko] Synced {count} coins → coingecko_coins + market_data")
            return count
    except Exception as e:
        logger.error(f"[CoinGecko] Error: {e}")
        return 0


# =====================================================
# STEP 3: DefiLlama — protocols + chains
# =====================================================

async def fetch_defillama_protocols(db, limit=200):
    """Fetch DeFi protocols from DefiLlama → defi_protocols"""
    logger.info("[DefiLlama] Fetching protocols...")
    proxy_url = await get_active_proxy(db)
    try:
        async with make_client(proxy_url) as client:
            resp = await client.get("https://api.llama.fi/protocols")
            if resp.status_code != 200:
                logger.warning(f"[DefiLlama] API returned {resp.status_code}")
                return 0

            protocols = resp.json()[:limit]
            now = datetime.now(timezone.utc)
            count = 0

            for p in protocols:
                doc = {
                    "id": f"defillama:{p.get('slug', '')}",
                    "name": p.get("name"),
                    "slug": p.get("slug"),
                    "symbol": p.get("symbol"),
                    "category": p.get("category"),
                    "chains": p.get("chains", []),
                    "tvl": p.get("tvl", 0),
                    "tvl_change_1d": p.get("change_1d"),
                    "tvl_change_7d": p.get("change_7d"),
                    "mcap": p.get("mcap"),
                    "logo": p.get("logo"),
                    "url": p.get("url"),
                    "twitter": p.get("twitter"),
                    "gecko_id": p.get("gecko_id"),
                    "source": "defillama",
                    "updated_at": now
                }
                await db.defi_protocols.update_one(
                    {"id": doc["id"]},
                    {"$set": doc},
                    upsert=True
                )

                # Cross-populate to rootdata_projects format for validation
                if doc["name"]:
                    await db.rootdata_projects.update_one(
                        {"name": {"$regex": f"^{doc['name']}$", "$options": "i"}},
                        {"$setOnInsert": {
                            "name": doc["name"],
                            "slug": doc["slug"],
                            "symbol": doc["symbol"],
                            "category": doc["category"],
                            "source": "defillama_cross",
                            "updated_at": now
                        }},
                        upsert=True
                    )
                count += 1

            logger.info(f"[DefiLlama] Synced {count} protocols → defi_protocols + rootdata_projects")
            return count
    except Exception as e:
        logger.error(f"[DefiLlama] Error: {e}")
        return 0


async def fetch_defillama_chains(db):
    """Fetch chain TVL data"""
    logger.info("[DefiLlama] Fetching chains...")
    proxy_url = await get_active_proxy(db)
    try:
        async with make_client(proxy_url) as client:
            resp = await client.get("https://api.llama.fi/v2/chains")
            if resp.status_code != 200:
                return 0
            chains = resp.json()
            now = datetime.now(timezone.utc)
            count = 0
            for c in chains:
                doc = {
                    "id": f"chain:{(c.get('name') or '').lower()}",
                    "name": c.get("name"),
                    "gecko_id": c.get("gecko_id"),
                    "token_symbol": c.get("tokenSymbol"),
                    "tvl": c.get("tvl", 0),
                    "source": "defillama",
                    "updated_at": now
                }
                await db.chain_tvl.update_one(
                    {"id": doc["id"]},
                    {"$set": doc},
                    upsert=True
                )
                count += 1
            logger.info(f"[DefiLlama] Synced {count} chains → chain_tvl")
            return count
    except Exception as e:
        logger.error(f"[DefiLlama] Error: {e}")
        return 0


# =====================================================
# STEP 4: Build graph from ALL funding data
# =====================================================

async def build_graph_from_funding(db):
    """Build/enrich graph_nodes and graph_relations from funding_rounds"""
    logger.info("[GraphBuilder] Building graph from funding data...")
    now = datetime.now(timezone.utc)
    nodes_created = 0
    edges_created = 0
    project_investors = defaultdict(list)

    cursor = db.funding_rounds.find({}, {"_id": 0})
    async for fr in cursor:
        project_key = fr.get("project_key") or fr.get("project_name", "").lower().replace(" ", "-")
        project_name = fr.get("project_name", project_key)
        investors = fr.get("investors", [])
        raised = fr.get("raised_usd", 0)
        round_type = fr.get("round_type", "Unknown")
        year = fr.get("year", 0)

        if not project_key:
            continue

        project_id = f"project:{project_key}"

        # Create/update project node
        await db.entity_graph_nodes.update_one(
            {"id": project_id},
            {"$set": {
                "id": project_id,
                "type": "project",
                "entity": project_key,
                "cluster_id": project_key,
                "label": project_name,
                "graph_version": "v2_entity",
                "source": "discovery_pipeline",
                "metadata": {"source": "discovery"},
                "created_at": now
            }},
            upsert=True
        )
        nodes_created += 1

        for inv_slug in investors:
            fund_id = f"fund:{inv_slug}"
            project_investors[project_key].append(inv_slug)

            # Ensure fund node exists
            existing_fund = await db.entity_graph_nodes.find_one({"id": fund_id})
            if not existing_fund:
                fund_doc = await db.cryptorank_funds.find_one({"slug": inv_slug})
                label = fund_doc["name"] if fund_doc else inv_slug.replace("-", " ").title()
                await db.entity_graph_nodes.update_one(
                    {"id": fund_id},
                    {"$set": {
                        "id": fund_id,
                        "type": "fund",
                        "entity": inv_slug,
                        "cluster_id": inv_slug,
                        "label": label,
                        "graph_version": "v2_entity",
                        "source": "cryptorank",
                        "metadata": {"source": "discovery", "category": "VC"},
                        "created_at": now
                    }},
                    upsert=True
                )
                nodes_created += 1

            # Create invested_in edge
            weight = min(10, 1 + (raised / 50_000_000)) if raised else 1
            await db.entity_graph_relations.update_one(
                {"source_id": fund_id, "target_id": project_id, "relation_type": "invested_in"},
                {"$set": {
                    "source_id": fund_id,
                    "target_id": project_id,
                    "relation_type": "invested_in",
                    "direction": "out",
                    "weight": weight,
                    "graph_version": "v2_entity",
                    "source": "cryptorank",
                    "metadata": {
                        "amount_usd": raised,
                        "round": round_type,
                        "year": year,
                        "source": "discovery"
                    },
                    "tags": ["investment", "discovery"],
                    "first_seen": int(now.timestamp()),
                    "last_seen": int(now.timestamp()),
                }},
                upsert=True
            )
            edges_created += 1

    # Build coinvested_with edges
    coinvest_pairs = set()
    for project_key, investors in project_investors.items():
        unique_investors = list(set(investors))
        if len(unique_investors) < 2:
            continue
        for i in range(len(unique_investors)):
            for j in range(i + 1, len(unique_investors)):
                a, b = sorted([unique_investors[i], unique_investors[j]])
                pair = (a, b)
                if pair in coinvest_pairs:
                    continue
                coinvest_pairs.add(pair)

                fund_a = f"fund:{a}"
                fund_b = f"fund:{b}"
                await db.entity_graph_relations.update_one(
                    {"source_id": fund_a, "target_id": fund_b, "relation_type": "coinvested_with"},
                    {"$set": {
                        "source_id": fund_a,
                        "target_id": fund_b,
                        "relation_type": "coinvested_with",
                        "direction": "bidirectional",
                        "weight": 2,
                        "graph_version": "v2_entity",
                        "source": "cryptorank",
                        "metadata": {"shared_project": project_key, "source": "discovery"},
                        "tags": ["coinvestment", "discovery"],
                        "first_seen": int(now.timestamp()),
                        "last_seen": int(now.timestamp()),
                    }},
                    upsert=True
                )
                edges_created += 1

    logger.info(f"[GraphBuilder] Nodes: {nodes_created}, Edges: {edges_created}, Coinvest pairs: {len(coinvest_pairs)}")
    return {"nodes": nodes_created, "edges": edges_created, "coinvest_pairs": len(coinvest_pairs)}


# =====================================================
# STEP 5: Enrich graph from DefiLlama/CoinGecko data
# =====================================================

async def enrich_graph_from_protocols(db):
    """Add DeFi protocols as project nodes if they match existing entities"""
    logger.info("[Enrichment] Enriching graph from DeFi protocols...")
    now = datetime.now(timezone.utc)
    enriched = 0

    cursor = db.defi_protocols.find({"tvl": {"$gte": 50_000_000}}, {"_id": 0}).limit(100)
    async for proto in cursor:
        slug = proto.get("slug", "")
        name = proto.get("name", "")
        if not slug:
            continue

        project_id = f"project:{slug}"
        existing = await db.entity_graph_nodes.find_one({"id": project_id})

        if existing:
            # Enrich with TVL data
            await db.entity_graph_nodes.update_one(
                {"id": project_id},
                {"$set": {
                    "metadata.tvl": proto.get("tvl"),
                    "metadata.category": proto.get("category"),
                    "metadata.chains": proto.get("chains", []),
                }}
            )
            enriched += 1
        else:
            # Create new project node from DeFi data
            await db.entity_graph_nodes.update_one(
                {"id": project_id},
                {"$set": {
                    "id": project_id,
                    "type": "project",
                    "entity": slug,
                    "cluster_id": slug,
                    "label": name,
                    "graph_version": "v2_entity",
                    "source": "defillama",
                    "metadata": {
                        "source": "defillama",
                        "tvl": proto.get("tvl"),
                        "category": proto.get("category"),
                        "chains": proto.get("chains", []),
                    },
                    "created_at": now
                }},
                upsert=True
            )
            enriched += 1

    logger.info(f"[Enrichment] Enriched {enriched} projects from DeFi protocols")
    return enriched


# =====================================================
# STEP 6: Create indexes
# =====================================================

async def ensure_indexes(db):
    """Create indexes for all populated collections"""
    logger.info("[Indexes] Creating indexes...")

    await db.cryptorank_projects.create_index("slug", unique=True)
    await db.cryptorank_projects.create_index("name")
    await db.cryptorank_projects.create_index("symbol")

    await db.cryptorank_funds.create_index("slug", unique=True)
    await db.cryptorank_funds.create_index("name")

    await db.coingecko_coins.create_index("id", unique=True)
    await db.coingecko_coins.create_index("name")
    await db.coingecko_coins.create_index("symbol")

    await db.funding_rounds.create_index("id", unique=True)
    await db.funding_rounds.create_index("project_key")
    await db.funding_rounds.create_index("investors")

    await db.defi_protocols.create_index("id", unique=True)
    await db.defi_protocols.create_index("slug")

    await db.rootdata_projects.create_index("name")

    await db.entity_graph_nodes.create_index("id", unique=True)
    await db.entity_graph_nodes.create_index("type")
    await db.entity_graph_nodes.create_index("entity")
    await db.entity_graph_nodes.create_index("graph_version")
    await db.entity_graph_relations.create_index("source_id")
    await db.entity_graph_relations.create_index("target_id")
    await db.entity_graph_relations.create_index("relation_type")
    await db.entity_graph_relations.create_index([("source_id", 1), ("target_id", 1), ("relation_type", 1)])

    logger.info("[Indexes] Done")


# =====================================================
# MAIN PIPELINE
# =====================================================

async def run_pipeline():
    """Run the complete data pipeline"""
    start = time.time()
    logger.info("=" * 60)
    logger.info("DATA PIPELINE — START")
    logger.info("=" * 60)

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    results = {}

    # Step 1: CryptoRank
    results["cryptorank_coins"] = await fetch_cryptorank_coins(db, 300)
    results["cryptorank_funds"] = await seed_cryptorank_funds(db)
    results["funding_rounds"] = await seed_funding_rounds(db)

    # Step 2: CoinGecko (may be rate-limited)
    results["coingecko_coins"] = await fetch_coingecko_markets(db, 250)

    # Step 3: DefiLlama
    results["defillama_protocols"] = await fetch_defillama_protocols(db, 200)
    results["defillama_chains"] = await fetch_defillama_chains(db)

    # Step 4: Build graph
    results["graph"] = await build_graph_from_funding(db)

    # Step 5: Enrich
    results["enrichment"] = await enrich_graph_from_protocols(db)

    # Step 6: Indexes
    await ensure_indexes(db)

    # Final counts
    logger.info("=" * 60)
    logger.info("DATA PIPELINE — RESULTS")
    logger.info("=" * 60)
    collections_to_count = [
        "cryptorank_projects", "cryptorank_funds", "coingecko_coins",
        "funding_rounds", "defi_protocols", "chain_tvl", "rootdata_projects",
        "market_data", "graph_nodes", "graph_relations", "entity_aliases"
    ]
    for col in collections_to_count:
        cnt = await db[col].count_documents({})
        logger.info(f"  {col}: {cnt}")

    elapsed = time.time() - start
    logger.info(f"\nTotal time: {elapsed:.1f}s")
    logger.info("=" * 60)

    client.close()
    return results


if __name__ == "__main__":
    asyncio.run(run_pipeline())
