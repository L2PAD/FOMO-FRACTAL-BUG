"""
News runtime endpoints — reads directly from raw_news + sentiment_events.
Mounted BEFORE legacy_compat so /api/news/* surfaces real data
instead of the catch-all stub.

Endpoints:
  GET /api/news/feed?limit=&hours=         — recent news with sentiment
  GET /api/news/digest                     — counters + bullish/bearish/neutral split
  GET /api/news/velocity                   — events per hour rolling 48h
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from pymongo import MongoClient, DESCENDING

router = APIRouter(prefix="/api/news", tags=["news-runtime"])

_client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
_db = _client[os.environ.get("DB_NAME", "fomo_mobile")]


# ─── helpers ────────────────────────────────────────────────────────────────
_NEG_WORDS = re.compile(r"\b(crash|dump|hack|exploit|scam|loss|bear|ban|lawsuit|sec\s+sues|liquidat|sell-?off|fud|rug)\b", re.I)
_POS_WORDS = re.compile(r"\b(rally|surge|pump|all-?time\s+high|breakout|bull|approval|partnership|integrat|launch|adoption|etf|win|listing)\b", re.I)

_CATEGORY_MAP = [
    ("regulation", re.compile(r"\b(sec|cftc|regul|law|congress|legal|approve|approval|ban|sue|lawsuit|cfpb|treasury)\b", re.I)),
    ("etf",        re.compile(r"\betf\b", re.I)),
    ("macro",      re.compile(r"\b(fed|fomc|inflation|cpi|jobs|gdp|rate|powell|yellen|macro)\b", re.I)),
    ("funding",    re.compile(r"\b(raised?|round|series\s+[a-c]|funding|seed|venture|valuation)\b", re.I)),
    ("listing",    re.compile(r"\b(list|listed|listing|binance|coinbase|kraken|bybit|okx)\b", re.I)),
    ("hack",       re.compile(r"\b(hack|exploit|drain|stolen|compromise|breach)\b", re.I)),
    ("price",      re.compile(r"\b(all-?time\s+high|crash|surge|rally|dump|breakout|pump)\b", re.I)),
    ("whale",      re.compile(r"\b(whale|large\s+transfer|moved\s+\$|deposit|withdrawal)\b", re.I)),
]


def _classify_sentiment(text: str) -> str:
    pos = len(_POS_WORDS.findall(text or ""))
    neg = len(_NEG_WORDS.findall(text or ""))
    if pos > neg and pos > 0:
        return "positive"
    if neg > pos and neg > 0:
        return "negative"
    return "neutral"


def _classify_category(text: str) -> List[str]:
    out = []
    text = text or ""
    for label, rx in _CATEGORY_MAP:
        if rx.search(text):
            out.append(label)
    return out or ["general"]


def _normalize_doc(doc: dict) -> dict:
    title = doc.get("title") or doc.get("headline") or doc.get("name") or ""
    desc  = doc.get("description") or doc.get("summary") or doc.get("content") or ""
    url   = doc.get("link") or doc.get("url") or doc.get("source_url") or ""
    src   = doc.get("source") or doc.get("publisher") or doc.get("domain") or "news"
    ts    = doc.get("published_at") or doc.get("publishedAt") or doc.get("fetched_at") or doc.get("createdAt")
    if isinstance(ts, datetime):
        ts = ts.isoformat()
    body = f"{title} · {desc}"
    return {
        "id":          str(doc.get("_id") or doc.get("hash") or doc.get("id") or ""),
        "title":       title,
        "description": desc[:300],
        "url":         url,
        "source":      src,
        "publishedAt": ts,
        "sentiment":   _classify_sentiment(body),
        "categories":  _classify_category(body),
    }


# ─── /api/news/feed ─────────────────────────────────────────────────────────
_TICKER_RX = re.compile(r"\b(BTC|ETH|SOL|DOGE|XRP|ADA|BNB|LINK|AVAX|ARB|OP|MATIC|DOT|TON|NEAR|APT|SUI|PEPE|SHIB|WIF|TRUMP|FET|RNDR|UNI|AAVE|MKR|TIA|SEI|TAO|ATOM|RUNE|FTM|INJ|STX)\b")

_EVENT_TYPE_PATTERNS = [
    ("regulation", re.compile(r"\b(sec|cftc|regul|approve|lawsuit|sue|congress|treasury|cfpb|ban|legal)\b", re.I)),
    ("etf",        re.compile(r"\betf\b", re.I)),
    ("hack",       re.compile(r"\b(hack|exploit|drain|stolen|breach|compromise)\b", re.I)),
    ("listing",    re.compile(r"\b(list|listed|listing|binance|coinbase|kraken|bybit|okx)\b", re.I)),
    ("funding",    re.compile(r"\b(raised?|round|series\s+[a-c]|funding|seed|venture)\b", re.I)),
    ("partnership",re.compile(r"\b(partner|integration|collab|joins|deal)\b", re.I)),
    ("price",      re.compile(r"\b(all-?time\s+high|crash|surge|rally|dump|breakout|pump)\b", re.I)),
    ("whale",      re.compile(r"\b(whale|large\s+transfer|moved\s+\$)\b", re.I)),
    ("macro",      re.compile(r"\b(fed|fomc|inflation|cpi|jobs|gdp|rate|powell|yellen)\b", re.I)),
]


def _detect_event_type(text: str) -> str:
    for et, rx in _EVENT_TYPE_PATTERNS:
        if rx.search(text or ""):
            return et
    return "market"


def _detect_primary_ticker(text: str) -> Optional[str]:
    m = _TICKER_RX.search(text or "")
    return m.group(0) if m else None


def _importance_score(item: dict) -> int:
    """0-100 heuristic: regulation/hack/etf weight higher; positive/negative weighted."""
    base = 35
    body = f"{item.get('title','')} · {item.get('description','')}"
    et = _detect_event_type(body)
    if et == "regulation": base += 25
    if et == "etf":        base += 30
    if et == "hack":       base += 35
    if et == "listing":    base += 20
    if et == "partnership":base += 15
    if et == "macro":      base += 10
    s = _classify_sentiment(body)
    if s == "negative": base += 10
    elif s == "positive": base += 5
    # source credibility (rough)
    src = (item.get("source") or "").lower()
    if any(k in src for k in ("coindesk", "bloomberg", "reuters", "cointelegraph", "decrypt")):
        base += 8
    return min(100, base)


@router.get("/feed")
async def news_feed(
    limit: int = Query(50, ge=1, le=200),
    hours: int = Query(48, ge=1, le=168),
):
    """Real news clustered for the UI: returns `data.clusters` with importance + breaking flags."""
    # Read from news_articles (RSS pipeline destination); fall back to raw_news (ChainBroker)
    primary = list(_db.news_articles.find({}, {}).sort([("published_at", DESCENDING), ("_id", DESCENDING)]).limit(limit * 4))
    if not primary:
        primary = list(_db.raw_news.find({}, {}).sort([("fetched_at", DESCENDING), ("_id", DESCENDING)]).limit(limit * 4))
    cursor = primary

    # Build clusters keyed by (primary_ticker, event_type) — falls back to title-prefix.
    clusters_idx: Dict[str, Dict[str, Any]] = {}
    now_utc = datetime.now(timezone.utc)

    for d in cursor:
        title = d.get("title") or d.get("headline") or d.get("name") or ""
        desc  = d.get("description") or d.get("summary") or d.get("content") or ""
        if not title.strip():
            continue
        body = f"{title} · {desc}"
        ticker = _detect_primary_ticker(body)
        et = _detect_event_type(body)
        # Cluster key: token+event_type, OR title-prefix (first 40 chars normalized) when no ticker
        if ticker:
            key = f"{ticker}::{et}"
        else:
            key = f"GEN::{et}::{title[:40].lower().strip()}"

        url = d.get("link") or d.get("url") or d.get("source_url") or ""
        src = d.get("source") or d.get("publisher") or d.get("domain") or "news"
        ts  = d.get("fetched_at") or d.get("published_at") or d.get("publishedAt")
        if isinstance(ts, datetime):
            ts_iso = ts.isoformat()
        else:
            ts_iso = str(ts) if ts else now_utc.isoformat()

        member_event = {
            "id":           str(d.get("_id") or ""),
            "title":        title,
            "description":  desc[:280],
            "url":          url,
            "source":       src,
            "publishedAt":  ts_iso,
            "sentiment":    _classify_sentiment(body),
            "importance":   _importance_score(d),
            "importanceBand": "high" if _importance_score(d) >= 70 else "medium" if _importance_score(d) >= 50 else "low",
            "eventType":    et,
            "isBreaking":   _importance_score(d) >= 70,
            "primaryAsset": ticker,
        }

        c = clusters_idx.setdefault(key, {
            "clusterId":      key,
            "title":          title,
            "primaryAsset":   ticker,
            "eventType":      et,
            "importance":     0,
            "importanceBand": "low",
            "isBreaking":     False,
            "sentimentHint":  member_event["sentiment"],
            "sourcesCount":   0,
            "firstSeenAt":    ts_iso,
            "lastSeenAt":     ts_iso,
            "events":         [],
            "sources":        set(),
        })
        c["events"].append(member_event)
        c["sources"].add(src)
        c["sourcesCount"] = len(c["sources"])
        # latest importance wins as cluster importance
        if member_event["importance"] > c["importance"]:
            c["importance"] = member_event["importance"]
            c["importanceBand"] = member_event["importanceBand"]
            c["isBreaking"] = member_event["isBreaking"]
            c["title"] = member_event["title"]
            c["sentimentHint"] = member_event["sentiment"]
        if ts_iso < c["firstSeenAt"]: c["firstSeenAt"] = ts_iso
        if ts_iso > c["lastSeenAt"]:  c["lastSeenAt"]  = ts_iso

    clusters_list = []
    for c in clusters_idx.values():
        c["sources"] = sorted(list(c["sources"]))[:8]
        c["events"]  = c["events"][:8]
        clusters_list.append(c)

    clusters_list.sort(key=lambda x: x["importance"], reverse=True)
    clusters_list = clusters_list[:limit]

    return {
        "ok":     True,
        "data":   {
            "clusters":     clusters_list,
            "totalEvents":  sum(c["sourcesCount"] for c in clusters_list),
        },
        "events": [e for c in clusters_list for e in c["events"]][:limit],
        "count":  len(clusters_list),
        "asOf":   datetime.now(timezone.utc).isoformat(),
        "source": "raw_news+clusterer",
    }


# ─── /api/news/digest ───────────────────────────────────────────────────────
@router.get("/digest")
async def news_digest(hours: int = Query(48, ge=1, le=168)):
    """Counters: total / bullish / bearish / neutral over the window."""
    docs = list(_db.news_articles.find({}, {}).sort([("published_at", DESCENDING), ("_id", DESCENDING)]).limit(500))
    if not docs:
        docs = list(_db.raw_news.find({}, {}).sort([("fetched_at", DESCENDING), ("_id", DESCENDING)]).limit(500))
    cursor = docs
    bull = bear = neut = total = 0
    for d in cursor:
        body = f"{d.get('title') or ''} · {d.get('description') or d.get('summary') or ''}"
        s = _classify_sentiment(body)
        total += 1
        if s == "positive": bull += 1
        elif s == "negative": bear += 1
        else: neut += 1
    return {
        "ok":       True,
        "total":    total,
        "bullish":  bull,
        "bearish":  bear,
        "neutral":  neut,
        "bullishPct": round(bull * 100 / max(total, 1), 1),
        "bearishPct": round(bear * 100 / max(total, 1), 1),
        "neutralPct": round(neut * 100 / max(total, 1), 1),
        "windowHours": hours,
        "asOf":     datetime.now(timezone.utc).isoformat(),
        "source":   "raw_news+sentiment_heuristic",
    }


# ─── /api/news/velocity ─────────────────────────────────────────────────────
@router.get("/velocity")
async def news_velocity(hours: int = Query(48, ge=1, le=168)):
    """Events-per-hour buckets over the window (rolling)."""
    now = datetime.now(timezone.utc)
    buckets: Dict[str, int] = {}
    for i in range(hours):
        bucket_dt = now - timedelta(hours=i)
        key = bucket_dt.strftime("%Y-%m-%dT%H")
        buckets[key] = 0

    docs = list(_db.news_articles.find({}, {"published_at": 1, "fetched_at": 1, "_id": 0}).limit(2000))
    if not docs:
        docs = list(_db.raw_news.find({}, {"fetched_at": 1, "_id": 0}).limit(2000))
    cursor = docs
    for d in cursor:
        ts = d.get("published_at") or d.get("fetched_at") or d.get("publishedAt")
        if not ts:
            continue
        if isinstance(ts, str):
            try:
                ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                continue
        elif isinstance(ts, datetime):
            ts_dt = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        else:
            continue
        key = ts_dt.strftime("%Y-%m-%dT%H")
        if key in buckets:
            buckets[key] += 1

    series = sorted(({"hour": k, "count": v} for k, v in buckets.items()), key=lambda x: x["hour"])
    total = sum(b["count"] for b in series)
    return {
        "ok":     True,
        "total":  total,
        "perHour": round(total / max(hours, 1), 2),
        "series": series,
        "windowHours": hours,
        "asOf":   now.isoformat(),
        "source": "raw_news",
    }
