"""
Master News + Sentiment Substrate Runner
========================================
Single entry-point that should be executed periodically (every 15 min
by supervisor) to keep the Sentiment / News substrate fresh.

Pipeline order:
  1. RSS news pipeline (119 sources → news_articles)
  2. ChainBroker scraper (→ raw_news + news_articles)
  3. Intelligence-OS orchestrator (cryptorank / dropstab / icodrops /
     coingecko / news_rss / chainbroker / …)
  4. VADER scorer on fresh news_articles → sentiment_events with
     primary llm_analysis confirmation (frees the trading runtime
     from the "inferred_only_no_primary_sentiment_confirmation"
     degradation).

Failures in any individual step are caught and logged; the script
always exits 0 so supervisor restarts it on the next interval.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
)
log = logging.getLogger("news_substrate")


async def _step_rss(db) -> dict:
    from news_pipeline import run_news_pipeline

    return await run_news_pipeline(db)


async def _step_chainbroker(db) -> dict:
    """Run the ChainBroker parser + project its rows into news_articles."""
    from intelligence_os.ingestion.parser_factory import create_parser_factory

    factory = create_parser_factory(db)
    parser = factory("chainbroker")
    rows = await parser.fetch()
    rows = parser.validate(rows)
    saved_raw = await parser.save_raw(rows)

    now = datetime.now(timezone.utc)
    upserted = 0
    for r in rows:
        url = r.get("url") or ""
        title = r.get("title") or ""
        if not url or not title:
            continue
        article_id = hashlib.md5(f"chainbroker:{url}".encode()).hexdigest()
        doc = {
            "id": article_id,
            "source_id": "chainbroker",
            "source_name": "ChainBroker",
            "source_tier": "B",
            "title": title[:300],
            "summary": (r.get("summary") or "")[:500],
            "url": url,
            "language": "en",
            "category": "news",
            "entities_mentioned": [],
            "entity_count": 0,
            "published_at": r.get("published_at") or now,
            "ingested_at": now,
        }
        res = await db.news_articles.update_one(
            {"id": article_id}, {"$set": doc}, upsert=True
        )
        if res.upserted_id or res.modified_count:
            upserted += 1

    return {"ok": True, "fetched": len(rows), "saved_raw": saved_raw, "news_articles_upserts": upserted}


async def _step_orchestrator(db) -> dict:
    from intelligence_os.ingestion.orchestrator import IngestionOrchestrator
    from intelligence_os.ingestion.parser_factory import create_parser_factory

    factory = create_parser_factory(db)
    orch = IngestionOrchestrator(db, factory)
    return await orch.run_all()


async def _step_graph_pipeline(db) -> dict:
    """
    Runs the primary subprocess-based GRAPH pipeline.
    Executes all 9 primary parsers (CryptoRank, Dropstab, RootData, GitHub,
    DefiLlama, ICODrops, DropsEarn, AirdropAlert, TokenUnlocks) plus the
    GraphRebuild + KnowledgeSync stages. HTML fallback engages automatically
    on consecutive failures.
    """
    from graph_bridge import run_graph_pipeline

    return await run_graph_pipeline(tiers=[0, 1, 2])


async def _step_html_fallback_parsers(db) -> dict:
    """
    Run the existing in-repo HTML fallback scrapers directly.
    These are the real scrapers that were already written for the
    Graph layer — we just invoke them on every tick so they keep
    publishing to the canonical collections.
    """
    from datetime import datetime, timezone
    from graph.html_fallback import (
        cryptorank_html_coins,
        cryptorank_html_funding,
        dropstab_html_activities,
        icodrops_html_upcoming,
    )

    out: dict = {}
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. CryptoRank coins → cryptorank_projects
    try:
        coins = await cryptorank_html_coins()
        wrote = 0
        for c in coins:
            sym = (c.get("symbol") or "").upper()
            if not sym:
                continue
            await db.cryptorank_projects.update_one(
                {"symbol": sym}, {"$set": c}, upsert=True
            )
            wrote += 1
        out["cryptorank_coins"] = {"fetched": len(coins), "upserted": wrote}
    except Exception as e:
        out["cryptorank_coins"] = {"error": repr(e)[:200]}

    # 2. CryptoRank funding rounds → funding_rounds + intel_funding
    try:
        rounds = await cryptorank_html_funding()
        wrote = 0
        for r in rounds:
            rid = r.get("id") or f"cr_html:funding:{r.get('project_key') or r.get('project')}"
            r["id"] = rid
            await db.funding_rounds.update_one({"id": rid}, {"$set": r}, upsert=True)
            await db.intel_funding.update_one(
                {"id": rid},
                {"$set": {**r, "source": "cryptorank_html", "updated_at": now_iso}},
                upsert=True,
            )
            wrote += 1
        out["cryptorank_funding"] = {"fetched": len(rounds), "upserted": wrote}
    except Exception as e:
        out["cryptorank_funding"] = {"error": repr(e)[:200]}

    # 3. Dropstab activities → crypto_activities
    try:
        acts = await dropstab_html_activities()
        wrote = 0
        for a in acts:
            aid = a.get("id")
            if not aid:
                continue
            await db.crypto_activities.update_one({"id": aid}, {"$set": a}, upsert=True)
            wrote += 1
        out["dropstab_activities"] = {"fetched": len(acts), "upserted": wrote}
    except Exception as e:
        out["dropstab_activities"] = {"error": repr(e)[:200]}

    # 4. ICODrops upcoming → intel_events (lightweight)
    try:
        icos = await icodrops_html_upcoming()
        wrote = 0
        for i in icos:
            name = (i.get("name") or "").strip()
            if not name:
                continue
            doc_id = f"icodrops_html_{name.lower().replace(' ', '_')[:40]}"
            await db.intel_events.update_one(
                {"id": doc_id},
                {"$set": {**i, "id": doc_id, "source": "icodrops_html", "updated_at": now_iso}},
                upsert=True,
            )
            wrote += 1
        out["icodrops_html"] = {"fetched": len(icos), "upserted": wrote}
    except Exception as e:
        out["icodrops_html"] = {"error": repr(e)[:200]}

    return {"ok": True, **out}


async def _step_icodrops_v2(db) -> dict:
    """Full ICODrops sync — upcoming, active and VC funding rounds."""
    from scripts.parser_icodrops_v2 import sync_icodrops_full

    return await sync_icodrops_full(db, limit=100)


async def _step_vader(db) -> dict:
    from scripts.news_sentiment_scorer import score_recent_news

    return await score_recent_news(db, lookback_hours=36, max_articles=4000)


async def _step_twitter_sentiment(db) -> dict:
    """Pull tweets for crypto actors + score them → sentiment_events (twitter_native)."""
    from scripts.twitter_sentiment_step import run_twitter_sentiment_tick

    return await run_twitter_sentiment_tick(db, max_actors=8)


async def main() -> int:
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ.get("DB_NAME", "fomo_mobile")
    log.info(f"=== NEWS SUBSTRATE TICK | db={db_name} ===")

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    t0 = time.time()
    summary: dict = {}

    for name, fn in (
        ("rss_pipeline", _step_rss),
        ("chainbroker", _step_chainbroker),
        ("orchestrator", _step_orchestrator),
        ("graph_pipeline", _step_graph_pipeline),
        ("html_fallback_parsers", _step_html_fallback_parsers),
        ("icodrops_v2", _step_icodrops_v2),
        ("vader_scorer", _step_vader),
        ("twitter_sentiment", _step_twitter_sentiment),
    ):
        try:
            tick = time.time()
            res = await fn(db)
            summary[name] = {"ok": True, "duration_sec": round(time.time() - tick, 2)}
            if isinstance(res, dict):
                # Keep concise stats
                for k in (
                    "total_articles",
                    "sources_checked",
                    "errors",
                    "sources_total",
                    "sources_ok",
                    "sources_fail",
                    "total_saved",
                    "events_written",
                    "articles_skipped_no_symbol",
                    "fetched",
                    "news_articles_upserts",
                    "upcoming",
                    "active",
                    "funding",
                    "cryptorank_coins",
                    "cryptorank_funding",
                    "dropstab_activities",
                    "icodrops_html",
                ):
                    if k in res:
                        summary[name][k] = res[k]
            log.info(f"[STEP] {name}: {summary[name]}")
        except Exception as exc:
            log.exception(f"[STEP] {name}: FAILED")
            summary[name] = {"ok": False, "error": repr(exc)[:300]}

    # Final substrate counters
    for col in ("news_sources", "news_articles", "sentiment_events", "raw_funding", "raw_news"):
        try:
            summary[f"db.{col}"] = await db[col].count_documents({})
        except Exception:
            summary[f"db.{col}"] = "n/a"

    log.info(f"=== TICK DONE in {round(time.time() - t0, 2)}s ===")
    log.info(f"SUMMARY: {summary}")

    client.close()
    return 0


if __name__ == "__main__":
    try:
        rc = asyncio.run(main())
    except Exception:
        log.exception("substrate tick crashed")
        rc = 0
    sys.exit(rc)
