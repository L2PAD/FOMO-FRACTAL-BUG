"""
Discovery Data Pipeline — T1 + T2 + ICO Drops
===============================================

Runs ALL parsers by tier priority:

T1 (Primary - funding, ico, unlocks, activities, defi):
  1. CryptoRank — funding, ico, unlocks
  2. RootData — funding, funds, persons
  3. DefiLlama — defi, projects, analytics
  4. Dropstab — activities

T2 (Secondary - market, projects, ico, unlocks):
  5. CoinGecko — market, projects, analytics
  6. CoinMarketCap — market, projects, ico
  7. TokenUnlocks — unlocks

Essential (user-specified):
  8. ICO Drops — ico calendar, token sales

After parsing: rebuilds graph from new funding data.
"""

import asyncio
import os
import sys
import time
import logging
from datetime import datetime, timezone

# CRITICAL: Set up paths FIRST before any other imports
FOMO_PATH = '/app/backend'
sys.path.insert(0, FOMO_PATH)
os.chdir(FOMO_PATH)

from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("DiscoveryPipeline")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "fomo_mobile")


async def run_parser(name, sync_fn, db, **kwargs):
    """Run a single parser with error handling"""
    start = time.time()
    try:
        result = await sync_fn(db, **kwargs)
        elapsed = time.time() - start
        logger.info(f"  [{name}] OK ({elapsed:.1f}s) → {result}")
        return {"name": name, "ok": True, "result": result, "time": elapsed}
    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"  [{name}] FAIL ({elapsed:.1f}s): {e}")
        return {"name": name, "ok": False, "error": str(e), "time": elapsed}


async def run_discovery_pipeline():
    """Run the complete T1+T2 discovery pipeline"""
    start = time.time()
    logger.info("=" * 70)
    logger.info("DISCOVERY PIPELINE — T1 + T2 + ICO DROPS")
    logger.info("=" * 70)

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    results = []

    # ═══════════════════════════════════════════════════
    # T1 — PRIMARY SOURCES
    # ═══════════════════════════════════════════════════
    logger.info("\n▶ T1 — PRIMARY SOURCES")

    # 1. CryptoRank (funding, ico, unlocks)
    from modules.parsers.parser_cryptorank import sync_cryptorank_data
    results.append(await run_parser("CryptoRank", sync_cryptorank_data, db))

    # 2. RootData (funding, funds, persons)
    from modules.parsers.parser_rootdata import sync_rootdata_data
    results.append(await run_parser("RootData", sync_rootdata_data, db))

    # 3. DefiLlama (defi, projects, analytics)
    from modules.parsers.parser_defillama import sync_defillama_data
    results.append(await run_parser("DefiLlama", sync_defillama_data, db))

    # 4. Dropstab (activities)
    from modules.parsers.parser_activities import sync_activities_data
    results.append(await run_parser("Dropstab", sync_activities_data, db))

    # ═══════════════════════════════════════════════════
    # T2 — SECONDARY SOURCES
    # ═══════════════════════════════════════════════════
    logger.info("\n▶ T2 — SECONDARY SOURCES")

    # 5. CoinGecko (market, projects, analytics)
    from modules.parsers.parser_coingecko import sync_coingecko_data
    results.append(await run_parser("CoinGecko", sync_coingecko_data, db))

    # 6. CoinMarketCap (market, projects, ico)
    from modules.parsers.parser_coinmarketcap import sync_coinmarketcap_data
    results.append(await run_parser("CoinMarketCap", sync_coinmarketcap_data, db))

    # 7. TokenUnlocks (unlocks)
    from modules.parsers.parser_tokenunlocks import sync_tokenunlocks_data
    results.append(await run_parser("TokenUnlocks", sync_tokenunlocks_data, db))

    # ═══════════════════════════════════════════════════
    # ESSENTIAL — ICO DROPS
    # ═══════════════════════════════════════════════════
    logger.info("\n▶ ESSENTIAL — ICO DROPS")

    # 8. ICO Drops (ico calendar, token sales)
    from modules.parsers.parser_icodrops import sync_icodrops_data
    results.append(await run_parser("ICODrops", sync_icodrops_data, db))

    # ═══════════════════════════════════════════════════
    # POST-PARSE: Rebuild graph from new funding data
    # ═══════════════════════════════════════════════════
    logger.info("\n▶ POST-PARSE — Graph rebuild")

    try:
        # Temporarily add backend to path for graph builder
        sys.path.insert(0, '/app/backend')
        from scripts.run_data_pipeline import build_graph_from_funding, enrich_graph_from_protocols, ensure_indexes
        sys.path.pop(0)
        graph = await build_graph_from_funding(db)
        enrichment = await enrich_graph_from_protocols(db)
        await ensure_indexes(db)
        results.append({"name": "GraphRebuild", "ok": True, "result": graph})
    except Exception as e:
        logger.error(f"  [GraphRebuild] FAIL: {e}")
        results.append({"name": "GraphRebuild", "ok": False, "error": str(e)})

    # ═══════════════════════════════════════════════════
    # REPORT
    # ═══════════════════════════════════════════════════
    elapsed = time.time() - start
    ok_count = sum(1 for r in results if r.get("ok"))
    fail_count = sum(1 for r in results if not r.get("ok"))

    logger.info("\n" + "=" * 70)
    logger.info("DISCOVERY PIPELINE — REPORT")
    logger.info("=" * 70)
    logger.info(f"  Parsers OK: {ok_count}/{len(results)}")
    logger.info(f"  Parsers FAIL: {fail_count}")

    for r in results:
        status = "✓" if r.get("ok") else "✗"
        name = r["name"].ljust(20)
        if r.get("ok"):
            logger.info(f"  {status} {name} {r.get('result', '')}")
        else:
            logger.info(f"  {status} {name} ERROR: {r.get('error', 'unknown')}")

    # Collection counts
    logger.info("\n  COLLECTION COUNTS:")
    collections = [
        "cryptorank_projects", "cryptorank_funds", "intel_funding", "intel_investors",
        "intel_projects", "intel_events", "coingecko_coins", "market_data",
        "defi_protocols", "chain_tvl", "rootdata_projects", "rootdata_organizations",
        "crypto_activities", "token_unlocks", "funding_rounds",
        "graph_nodes", "graph_relations", "data_sources"
    ]
    for col in collections:
        cnt = await db[col].count_documents({})
        if cnt > 0:
            logger.info(f"    {col}: {cnt}")

    logger.info(f"\n  Total time: {elapsed:.1f}s")
    logger.info("=" * 70)

    client.close()
    return results


if __name__ == "__main__":
    asyncio.run(run_discovery_pipeline())
