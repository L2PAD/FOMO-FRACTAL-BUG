"""
Sentiment API (canonical, single-source-of-truth)
==================================================
Public endpoints required by the web frontend, the Expo mobile app, the
Telegram mini-app and the admin panel.

All endpoints serve REAL data from MongoDB / sentiment_runtime — no stubs.

Routes:
  GET  /api/v1/sentiment/symbol/{symbol}         — full per-symbol verdict
  GET  /api/v1/sentiment/symbols                 — batch verdicts
  GET  /api/sentiment/status                     — overall runtime/coverage status
  GET  /api/sentiment/sources/breakdown          — sentiment_events grouped by source
  GET  /api/sentiment/timeseries/{symbol}        — 24h time-series for charts
  GET  /api/sentiment/feed                       — latest events feed
  GET  /api/admin/sentiment/sources              — admin: known sentiment data sources
  GET  /api/admin/sentiment/pipeline-status      — admin: per-pipeline health
  POST /api/admin/sentiment/run-now              — admin: force a substrate tick
  GET  /api/twitter/cookies/status               — admin/diag: Twitter session state
  POST /api/twitter/cookies/load                 — admin: load cookies from on-disk file
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Body, Query

from ml_ops import get_db
from services.sentiment_runtime import runtime, runtime_many, service_health

router = APIRouter(tags=["sentiment-public"])


# ───────────────────────── Helpers ─────────────────────────


def _db():
    return get_db()


def _utc_now():
    return datetime.now(timezone.utc)


def _safe(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


# ───────────────────────── Per-symbol verdict ─────────────────────────


@router.get("/api/v1/sentiment/symbol/{symbol}")
async def v1_sentiment_symbol(symbol: str):
    """Canonical per-symbol sentiment verdict (live from runtime)."""
    sym = (symbol or "").strip().upper()
    if not sym:
        return {"ok": False, "error": "symbol_required"}
    payload = runtime(sym)
    return {
        "ok": bool(payload.get("ok")),
        "symbol": sym,
        "verdict": payload,
        "asOf": _utc_now().isoformat(),
    }


@router.get("/api/v1/sentiment/symbols")
async def v1_sentiment_symbols(
    symbols: Optional[str] = Query(default="BTC,ETH,SOL,BNB,XRP,DOGE"),
):
    """Batch verdicts for any number of symbols."""
    syms = [s.strip().upper() for s in (symbols or "").split(",") if s.strip()]
    data = runtime_many(syms)
    return {
        "ok": True,
        "symbolsRequested": len(syms),
        "results": data,
        "asOf": _utc_now().isoformat(),
    }


# ───────────────────────── Overall status ─────────────────────────


@router.get("/api/sentiment/status")
async def sentiment_status():
    """
    Overall sentiment substrate status:
      - service_health from runtime
      - event counters by window
      - distinct sources and symbols
      - last ingestion timestamps
    """
    db = _db()
    cutoff_24h = _utc_now().replace(tzinfo=None) - timedelta(hours=24)
    cutoff_1h = _utc_now().replace(tzinfo=None) - timedelta(hours=1)

    total = await db.sentiment_events.count_documents({})
    n_24h = await db.sentiment_events.count_documents(
        {"createdAt": {"$gte": cutoff_24h}}
    )
    n_1h = await db.sentiment_events.count_documents(
        {"createdAt": {"$gte": cutoff_1h}}
    )
    sources = sorted(await db.sentiment_events.distinct("source"))
    symbols = sorted(await db.sentiment_events.distinct("symbol"))

    last_event = await db.sentiment_events.find_one(
        {}, sort=[("createdAt", -1)], projection={"_id": 0, "createdAt": 1, "source": 1}
    )

    return {
        "ok": True,
        "asOf": _utc_now().isoformat(),
        "runtime": service_health(),
        "events": {
            "total": total,
            "last_24h": n_24h,
            "last_1h": n_1h,
        },
        "sources": sources,
        "symbols": symbols,
        "lastEvent": {
            "createdAt": _safe(last_event.get("createdAt")) if last_event else None,
            "source": last_event.get("source") if last_event else None,
        },
    }


@router.get("/api/sentiment/sources/breakdown")
async def sentiment_sources_breakdown(hours: int = 24):
    """Aggregate events per source for the last N hours."""
    db = _db()
    cutoff = _utc_now().replace(tzinfo=None) - timedelta(hours=max(1, hours))
    pipeline = [
        {"$match": {"createdAt": {"$gte": cutoff}}},
        {
            "$group": {
                "_id": "$source",
                "count": {"$sum": 1},
                "avgScore": {"$avg": "$weightedScore"},
                "lastAt": {"$max": "$createdAt"},
            }
        },
        {"$sort": {"count": -1}},
    ]
    rows = []
    async for r in db.sentiment_events.aggregate(pipeline):
        rows.append(
            {
                "source": r.get("_id"),
                "count": r.get("count", 0),
                "avgScore": round(r.get("avgScore") or 0.0, 4),
                "lastAt": _safe(r.get("lastAt")),
            }
        )
    return {
        "ok": True,
        "windowHours": hours,
        "rows": rows,
        "asOf": _utc_now().isoformat(),
    }


# ───────────────────────── Time-series for charts ─────────────────────────


@router.get("/api/sentiment/timeseries/{symbol}")
async def sentiment_timeseries(
    symbol: str, hours: int = Query(default=24, ge=1, le=168)
):
    """Hourly time-series of weightedScore + sample count for a given symbol."""
    db = _db()
    sym = symbol.strip().upper()
    cutoff = _utc_now().replace(tzinfo=None) - timedelta(hours=hours)
    pipeline = [
        {"$match": {"symbol": sym, "createdAt": {"$gte": cutoff}}},
        {
            "$group": {
                "_id": {
                    "y": {"$year": "$createdAt"},
                    "m": {"$month": "$createdAt"},
                    "d": {"$dayOfMonth": "$createdAt"},
                    "h": {"$hour": "$createdAt"},
                },
                "avg": {"$avg": "$weightedScore"},
                "count": {"$sum": 1},
                "ts": {"$min": "$createdAt"},
            }
        },
        {"$sort": {"_id.y": 1, "_id.m": 1, "_id.d": 1, "_id.h": 1}},
    ]
    points = []
    async for r in db.sentiment_events.aggregate(pipeline):
        points.append(
            {
                "ts": _safe(r.get("ts")),
                "avgScore": round(r.get("avg") or 0.5, 4),
                "count": r.get("count", 0),
            }
        )
    return {
        "ok": True,
        "symbol": sym,
        "windowHours": hours,
        "points": points,
        "asOf": _utc_now().isoformat(),
    }


# ───────────────────────── Latest events feed ─────────────────────────


@router.get("/api/miniapp/sentiment")
async def miniapp_sentiment(
    symbols: Optional[str] = Query(default="BTC,ETH,SOL,BNB,XRP,DOGE"),
):
    """Compact sentiment widget data for Telegram miniapp — one row per symbol."""
    syms = [s.strip().upper() for s in (symbols or "").split(",") if s.strip()]
    data = runtime_many(syms)

    def _label_for(score):
        if score is None:
            return "n/a"
        if score >= 0.65:
            return "BULLISH"
        if score >= 0.55:
            return "LONG_BIAS"
        if score >= 0.45:
            return "NEUTRAL"
        if score >= 0.35:
            return "SHORT_BIAS"
        return "BEARISH"

    items = []
    for sym in syms:
        r = data.get(sym, {})
        score = r.get("score")
        items.append(
            {
                "symbol": sym,
                "ok": bool(r.get("ok")),
                "direction": r.get("direction"),
                "score": score,
                "confidence": r.get("confidence"),
                "sample": r.get("sample"),
                "label": _label_for(score),
            }
        )

    fg_event = await _db().sentiment_events.find_one(
        {"source": "fear_greed_index"}, sort=[("createdAt", -1)]
    )
    return {
        "ok": True,
        "items": items,
        "fearGreed": (
            {
                "value": fg_event.get("weightedScore"),
                "createdAt": _safe(fg_event.get("createdAt")),
            }
            if fg_event
            else None
        ),
        "asOf": _utc_now().isoformat(),
    }



@router.get("/api/sentiment/feed")
async def sentiment_feed(
    symbol: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    """Recent sentiment events feed (for the Sentiment tab list)."""
    db = _db()
    q: dict = {}
    if symbol:
        q["symbol"] = symbol.strip().upper()
    if source:
        q["source"] = source.strip().lower()
    cursor = db.sentiment_events.find(q, {"_id": 0}).sort("createdAt", -1).limit(limit)
    items = []
    async for ev in cursor:
        items.append(
            {
                "symbol": ev.get("symbol"),
                "source": ev.get("source"),
                "title": ev.get("title"),
                "url": ev.get("url"),
                "score": ev.get("weightedScore"),
                "polarity": ev.get("polarity"),
                "type": ev.get("type"),
                "createdAt": _safe(ev.get("createdAt")),
            }
        )
    return {
        "ok": True,
        "filter": {"symbol": symbol, "source": source},
        "count": len(items),
        "items": items,
        "asOf": _utc_now().isoformat(),
    }


# ───────────────────────── Admin: Sources ─────────────────────────


_SOURCE_DESCRIPTORS = [
    {
        "id": "news_rss_vader",
        "label": "News RSS (VADER scored)",
        "kind": "news",
        "engine": "vader_v1",
        "primary": True,
        "description": "119 RSS feeds → VADER → sentiment_events",
    },
    {
        "id": "cryptocompare_news",
        "label": "CryptoCompare News API",
        "kind": "news",
        "engine": "vader_v1",
        "primary": True,
        "description": "Periodic news ingestion from CryptoCompare",
    },
    {
        "id": "coingecko",
        "label": "CoinGecko community pressure",
        "kind": "community",
        "engine": "internal",
        "primary": False,
        "description": "Up/Down votes + trending signal",
    },
    {
        "id": "fear_greed_index",
        "label": "Fear & Greed Index (Alternative.me)",
        "kind": "macro",
        "engine": "passthrough",
        "primary": False,
        "description": "Daily market-wide F&G index",
    },
    {
        "id": "twitter_native",
        "label": "Twitter / X Native (cookie-session)",
        "kind": "social",
        "engine": "vader_v1",
        "primary": True,
        "description": "Cookie-based authenticated scraper",
    },
    {
        "id": "chainbroker",
        "label": "ChainBroker news (Next.js)",
        "kind": "news",
        "engine": "vader_v1",
        "primary": False,
        "description": "ChainBroker article index scraper",
    },
]


@router.get("/api/admin/sentiment/sources")
async def admin_sentiment_sources():
    """List all known Sentiment data sources with live counts and freshness."""
    db = _db()
    cutoff_24h = _utc_now().replace(tzinfo=None) - timedelta(hours=24)

    out = []
    for s in _SOURCE_DESCRIPTORS:
        sid = s["id"]
        total = await db.sentiment_events.count_documents({"source": sid})
        recent = await db.sentiment_events.count_documents(
            {"source": sid, "createdAt": {"$gte": cutoff_24h}}
        )
        last = await db.sentiment_events.find_one(
            {"source": sid},
            sort=[("createdAt", -1)],
            projection={"_id": 0, "createdAt": 1},
        )
        out.append(
            {
                **s,
                "events_total": total,
                "events_24h": recent,
                "lastEventAt": _safe(last.get("createdAt")) if last else None,
                "status": "ACTIVE" if recent > 0 else ("STALE" if total > 0 else "INACTIVE"),
            }
        )

    return {
        "ok": True,
        "count": len(out),
        "sources": out,
        "asOf": _utc_now().isoformat(),
    }


# ───────────────────────── Admin: Pipeline status ─────────────────────────


@router.get("/api/admin/sentiment/pipeline-status")
async def admin_sentiment_pipeline_status():
    """Show health of each ingestion pipeline feeding sentiment_events."""
    db = _db()
    cutoff = _utc_now().replace(tzinfo=None) - timedelta(hours=24)
    pipes: list = []

    # 1) RSS pipeline → news_articles
    rss_total = await db.news_articles.count_documents({})
    rss_24h = await db.news_articles.count_documents({"ingested_at": {"$gte": cutoff}})
    pipes.append(
        {
            "id": "rss_pipeline",
            "label": "RSS News Pipeline (119 sources)",
            "writes_to": "news_articles",
            "total": rss_total,
            "last_24h": rss_24h,
            "status": "ACTIVE" if rss_24h > 0 else ("STALE" if rss_total > 0 else "INACTIVE"),
        }
    )

    # 2) VADER scorer → sentiment_events (news_rss_vader)
    v_total = await db.sentiment_events.count_documents({"source": "news_rss_vader"})
    v_24h = await db.sentiment_events.count_documents(
        {"source": "news_rss_vader", "createdAt": {"$gte": cutoff}}
    )
    pipes.append(
        {
            "id": "vader_scorer",
            "label": "VADER scorer (news → sentiment)",
            "writes_to": "sentiment_events[source=news_rss_vader]",
            "total": v_total,
            "last_24h": v_24h,
            "status": "ACTIVE" if v_24h > 0 else ("STALE" if v_total > 0 else "INACTIVE"),
        }
    )

    # 3) sentiment_periodic
    sp_total = await db.sentiment_events.count_documents(
        {"source": {"$in": ["cryptocompare_news", "coingecko", "fear_greed_index"]}}
    )
    sp_24h = await db.sentiment_events.count_documents(
        {
            "source": {"$in": ["cryptocompare_news", "coingecko", "fear_greed_index"]},
            "createdAt": {"$gte": cutoff},
        }
    )
    pipes.append(
        {
            "id": "sentiment_periodic",
            "label": "Sentiment Periodic Loop (CC+CG+F&G)",
            "writes_to": "sentiment_events",
            "total": sp_total,
            "last_24h": sp_24h,
            "status": "ACTIVE" if sp_24h > 0 else ("STALE" if sp_total > 0 else "INACTIVE"),
        }
    )

    # 4) twitter_native
    tw_total = await db.sentiment_events.count_documents({"source": "twitter_native"})
    tw_24h = await db.sentiment_events.count_documents(
        {"source": "twitter_native", "createdAt": {"$gte": cutoff}}
    )
    pipes.append(
        {
            "id": "twitter_native",
            "label": "Twitter Native (cookie session)",
            "writes_to": "sentiment_events[source=twitter_native]",
            "total": tw_total,
            "last_24h": tw_24h,
            "status": "ACTIVE" if tw_24h > 0 else ("STALE" if tw_total > 0 else "INACTIVE"),
        }
    )

    return {
        "ok": True,
        "asOf": _utc_now().isoformat(),
        "pipelines": pipes,
    }


@router.post("/api/admin/sentiment/run-now")
async def admin_sentiment_run_now():
    """Force a substrate tick (RSS + VADER + orchestrator + graph_pipeline)."""
    import asyncio

    async def _bg():
        try:
            from scripts import run_news_substrate as substrate
            await substrate.main()
        except Exception as e:  # pragma: no cover
            print(f"[admin/sentiment/run-now] tick error: {e!r}")

    asyncio.create_task(_bg())
    return {
        "ok": True,
        "started": True,
        "note": "Substrate tick scheduled in background",
        "asOf": _utc_now().isoformat(),
    }


# ───────────────────────── Twitter cookies ─────────────────────────


_COOKIE_FILES = [
    "/app/backend/cookies_decrypted.json",
    "/app/backend/cookies.json",
    "/app/backend/twitter_playwright_state.json",
]


@router.get("/api/twitter/cookies/status")
async def twitter_cookies_status():
    """
    Reports presence/freshness of Twitter session cookies and whether the
    cookie-based scraper is unlocked.
    """
    files: list = []
    auth_token_valid_to: Optional[float] = None
    ct0_present = False

    for path in _COOKIE_FILES:
        info = {"path": path, "exists": os.path.exists(path)}
        if not info["exists"]:
            files.append(info)
            continue
        try:
            info["size_bytes"] = os.path.getsize(path)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cookies = data.get("cookies", data) if isinstance(data, dict) else data
            info["cookie_count"] = len(cookies) if isinstance(cookies, list) else 0
            if isinstance(cookies, list):
                for c in cookies:
                    if c.get("name") == "auth_token" and c.get("value") and c.get("value") != "...":
                        info["auth_token_present"] = True
                        exp = c.get("expirationDate") or c.get("expires") or 0
                        if exp and (auth_token_valid_to is None or exp > auth_token_valid_to):
                            auth_token_valid_to = exp
                    if c.get("name") == "ct0" and c.get("value") and c.get("value") != "...":
                        ct0_present = True
        except Exception as e:  # pragma: no cover
            info["error"] = repr(e)[:160]
        files.append(info)

    db = _db()
    sess_doc = await db.twitter_session.find_one({"id": "main"}, {"_id": 0}) if "twitter_session" in await db.list_collection_names() else None

    return {
        "ok": True,
        "files": files,
        "session_in_db": bool(sess_doc),
        "auth_token_present": auth_token_valid_to is not None,
        "auth_token_valid_to": (
            datetime.fromtimestamp(auth_token_valid_to, tz=timezone.utc).isoformat()
            if auth_token_valid_to
            else None
        ),
        "ct0_present": ct0_present,
        "asOf": _utc_now().isoformat(),
    }


@router.post("/api/twitter/cookies/load")
async def twitter_cookies_load(payload: dict = Body(default={})):
    """
    Load cookies from the on-disk file into MongoDB (twitter_session).
    """
    path = payload.get("path", "/app/backend/cookies_decrypted.json")
    if not os.path.exists(path):
        return {"ok": False, "error": f"file_not_found: {path}"}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cookies = data.get("cookies", data) if isinstance(data, dict) else data
        if not isinstance(cookies, list) or not cookies:
            return {"ok": False, "error": "no_cookies_in_file"}

        db = _db()
        await db.twitter_session.update_one(
            {"id": "main"},
            {
                "$set": {
                    "id": "main",
                    "cookies": cookies,
                    "loaded_from": path,
                    "loaded_at": _utc_now(),
                    "cookie_count": len(cookies),
                }
            },
            upsert=True,
        )
        return {
            "ok": True,
            "loaded": len(cookies),
            "path": path,
            "asOf": _utc_now().isoformat(),
        }
    except Exception as e:  # pragma: no cover
        return {"ok": False, "error": repr(e)[:300]}
