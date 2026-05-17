"""
Market Feed Service — Polymarket Feed + Intelligence Overlay.

Strategy:
1. Fetch ALL crypto markets from Polymarket (raw feed)
2. Run existing prediction pipeline to get analyzed cases
3. Merge: analyzed markets get full overlay, others get market-only data
4. Score universe: HOT / ACTIONABLE / ALL
"""
import logging
import time
import httpx
from datetime import datetime, timezone

from prediction import polymarket_client, event_classifier
from prediction.feed.clob_service import fetch_orderbooks, compute_execution_hints

logger = logging.getLogger("prediction.feed")

_feed_cache = {"data": None, "ts": 0}
CACHE_TTL = 90

GAMMA_API = "https://gamma-api.polymarket.com"


async def get_feed(analyzed_cases: list = None, force_refresh: bool = False) -> dict:
    """Main feed — merges raw polymarket feed with analyzed cases."""
    now = time.time()
    if not force_refresh and _feed_cache["data"] and (now - _feed_cache["ts"]) < CACHE_TTL:
        return _feed_cache["data"]

    raw_markets = await _fetch_all_crypto_markets()

    # Build lookup of analyzed cases by market_id
    case_map = {}
    if analyzed_cases:
        for c in analyzed_cases:
            mid = c.get("market_id")
            if mid:
                case_map[mid] = c

    # Fetch CLOB orderbook data for all markets with token IDs
    token_ids = []
    token_to_market = {}
    midpoints = {}
    for m in raw_markets:
        yes_tid = m.get("yes_token_id")
        if yes_tid:
            token_ids.append(yes_tid)
            token_to_market[yes_tid] = m["market_id"]
            midpoints[yes_tid] = m.get("yes_price", 0.5)

    clob_data = {}
    try:
        clob_results = await fetch_orderbooks(token_ids[:100], midpoints)
        for tid, metrics in clob_results.items():
            mid = token_to_market.get(tid)
            if mid:
                clob_data[mid] = metrics
    except Exception as e:
        logger.warning(f"CLOB fetch failed (non-blocking): {e}")

    # Merge (deduplicate by market_id)
    feed_items = []
    seen_ids = set()
    for m in raw_markets:
        mid = m["market_id"]
        if mid in seen_ids:
            continue
        seen_ids.add(mid)
        analyzed = case_map.get(mid)
        clob_depth = clob_data.get(mid)
        item = _build_feed_item(m, analyzed, clob_depth)
        feed_items.append(item)

    # Score
    scored = _score_universe(feed_items)

    result = {
        "ok": True,
        "total": len(scored),
        "hot": [i for i in scored if i["tier"] == "hot"],
        "actionable": [i for i in scored if i["tier"] == "actionable"],
        "all": scored,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    _feed_cache["data"] = result
    _feed_cache["ts"] = now
    return result


async def get_market_detail(market_id: str) -> dict | None:
    feed = await get_feed()
    for m in feed["all"]:
        if m["market_id"] == market_id:
            return m
    return None


async def _fetch_all_crypto_markets() -> list[dict]:
    """Fetch large pool of crypto markets from Polymarket Gamma API."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{GAMMA_API}/markets",
                params={"limit": 500, "closed": False, "order": "volume", "ascending": False},
            )
            if resp.status_code != 200:
                logger.warning(f"Gamma API {resp.status_code}")
                return []

            raw = resp.json()
            if not isinstance(raw, list):
                return []

            results = []
            for m in raw:
                if not m.get("question"):
                    continue
                norm = polymarket_client._normalize(m)
                if not polymarket_client._is_live(norm):
                    continue
                if polymarket_client._is_crypto_relevant(norm):
                    norm["volume_24h"] = float(m.get("volume24hr", 0) or 0)
                    norm["slug"] = m.get("slug", "")
                    norm["tags"] = m.get("tags", []) or []
                    norm["created_at"] = m.get("createdAt")
                    results.append(norm)

            return results
    except Exception as e:
        logger.error(f"Feed fetch error: {e}")
        return []


def _build_feed_item(market: dict, analyzed_case: dict | None, clob_depth: dict | None = None) -> dict:
    """Build a feed item — overlay from analyzed case if available."""
    classified = event_classifier.classify(market["question"])
    asset = classified.get("asset", "CRYPTO")
    etype = classified.get("event_type", "unknown")
    mtype = classified.get("market_type", "unknown")

    # Compute execution hints from Gamma bestBid/bestAsk + CLOB depth
    exec_hints = compute_execution_hints(market, clob_depth)

    item = {
        "market_id": market["market_id"],
        "question": market["question"],
        "yes_price": market["yes_price"],
        "no_price": market["no_price"],
        "volume": market["volume"],
        "volume_24h": market.get("volume_24h", 0),
        "liquidity": market["liquidity"],
        "spread": market["spread"],
        "end_date": market.get("end_date"),
        "asset": asset,
        "event_type": etype,
        "market_type": mtype,
        "entities": classified.get("entities", []),
        "slug": market.get("slug", ""),
        "tags": market.get("tags", []),
        "clob": exec_hints,
    }

    if analyzed_case:
        a = analyzed_case.get("analysis", {})
        rec = analyzed_case.get("recommendation", {})
        ex = analyzed_case.get("executionLayer", {})
        repr_data = analyzed_case.get("repricing", {})
        entry = analyzed_case.get("entry_timing", {})
        sizing = analyzed_case.get("sizing", {})
        intel = analyzed_case.get("intelligence", {})
        proj = analyzed_case.get("projectIntel", {})

        edge_val = a.get("net_edge", 0)
        conf = a.get("model_confidence", 0)

        # Edge drivers
        edge_drivers = []
        why_now = analyzed_case.get("why_now", [])
        if why_now:
            edge_drivers = why_now[:2]
        else:
            edge_drivers = _compute_edge_drivers(market, edge_val, conf, repr_data)

        urgency = _compute_urgency(edge_val, conf, repr_data)
        priority = _compute_action_priority(edge_val, conf, ex.get("entryQualityScore", 0.5))

        # Action mapping for feed
        action_map = {
            "YES_NOW": "BUY YES", "YES_SMALL": "BUY YES",
            "NO_NOW": "BUY NO", "NO_SMALL": "BUY NO",
            "GOOD_IDEA_BAD_PRICE": "WATCH", "AVOID": "AVOID",
            "WATCH": "WATCH", "WAIT": "WATCH",
        }
        raw_action = rec.get("action", "WATCH")
        feed_action = action_map.get(raw_action, "WATCH")

        item["has_overlay"] = True
        item["overlay"] = {
            "fair_prob": a.get("fair_prob", market["yes_price"]),
            "edge": edge_val,
            "edge_pct": round(abs(edge_val) * 100, 1),
            "confidence": conf,
            "action": feed_action,
            "raw_action": raw_action,
            "execution_style": ex.get("entryStyle", "WAIT"),
            "execution_quality": ex.get("entryQualityScore", 0.5),
            "slippage_risk": ex.get("slippageRisk", 0),
            "repricing_state": repr_data.get("repricing_state", "unknown"),
            "entry_action": entry.get("entry_action", "wait"),
            "sizing_allowed": sizing.get("allowed", False),
            "edge_drivers": edge_drivers,
            "urgency": urgency,
            "action_priority": priority,
            # Detail-level data
            "bull_case": (intel.get("thesis", {}).get("bullCase", {}).get("arguments") or
                         proj.get("bullCase", []))[:3],
            "bear_case": (intel.get("thesis", {}).get("bearCase", {}).get("arguments") or
                         proj.get("bearCase", []))[:3],
            "market_misses": (intel.get("memo", {}).get("whatMarketMisses", []))[:2],
            "why_now": analyzed_case.get("why_now", [])[:3],
            "why_not": analyzed_case.get("why_not", [])[:3],
            "project_verdict": proj.get("verdict"),
            "execution_grade": analyzed_case.get("executionScore", {}).get("grade"),
        }
    else:
        # Basic market data — no intelligence overlay
        item["has_overlay"] = False
        item["overlay"] = {
            "fair_prob": market["yes_price"],
            "edge": 0,
            "edge_pct": 0,
            "confidence": 0,
            "action": "NO DATA",
            "raw_action": "UNKNOWN",
            "execution_style": "WAIT",
            "execution_quality": 0,
            "slippage_risk": 0,
            "repricing_state": "unknown",
            "entry_action": "wait",
            "sizing_allowed": False,
            "edge_drivers": [],
            "urgency": "watch",
            "action_priority": 0,
            "bull_case": [],
            "bear_case": [],
            "market_misses": [],
            "why_now": [],
            "why_not": [],
            "project_verdict": None,
            "execution_grade": None,
        }

    return item


def _compute_edge_drivers(market, edge, conf, repricing) -> list[str]:
    drivers = []
    edge_pct = abs(edge) * 100
    if edge_pct > 10:
        drivers.append(f"Market underpricing by {edge_pct:.0f}%")
    elif edge_pct > 5:
        drivers.append(f"Moderate mispricing: {edge_pct:.0f}% edge")
    if repricing.get("repricing_state") == "fresh_mispricing":
        drivers.append("Fresh mispricing — market hasn't reacted")
    elif repricing.get("repricing_state") == "active_repricing":
        drivers.append("Active repricing — move in progress")
    if conf > 0.6:
        drivers.append("High confidence with multiple confirmations")
    elif conf < 0.35:
        drivers.append("Low confidence — limited signal strength")
    if market.get("liquidity", 0) < 5000:
        drivers.append("Caution: thin liquidity")
    return drivers[:3]


def _compute_urgency(edge, conf, repricing) -> str:
    edge_abs = abs(edge)
    repr_state = repricing.get("repricing_state", "")
    if edge_abs > 0.10 and conf > 0.5 and repr_state in ("fresh_mispricing", ""):
        return "now"
    if edge_abs > 0.06 and conf > 0.4:
        return "soon"
    if repr_state == "active_repricing" and edge_abs > 0.05:
        return "soon"
    return "watch"


def _compute_action_priority(edge, conf, quality) -> float:
    score = (abs(edge) * 3) + (conf * 0.3) + (quality * 0.2)
    return round(min(max(score, 0), 1), 3)


def _score_universe(items: list[dict]) -> list[dict]:
    for m in items:
        ov = m.get("overlay", {})
        edge = abs(ov.get("edge", 0))
        conf = ov.get("confidence", 0)
        vol24 = m.get("volume_24h", 0)
        has = m.get("has_overlay", False)
        action = ov.get("action", "")

        # HOT: big edge + has overlay + decent volume
        if has and edge > 0.08 and vol24 > 500:
            m["tier"] = "hot"
        elif has and edge > 0.05 and action in ("BUY YES", "BUY NO"):
            m["tier"] = "hot"
        # ACTIONABLE: moderate edge + overlay
        elif has and edge > 0.03:
            m["tier"] = "actionable"
        elif has and action in ("BUY YES", "BUY NO"):
            m["tier"] = "actionable"
        else:
            m["tier"] = "all"

    items.sort(key=lambda x: (
        0 if x["tier"] == "hot" else 1 if x["tier"] == "actionable" else 2,
        -abs(x.get("overlay", {}).get("edge", 0)),
        -x.get("volume_24h", 0),
    ))
    return items
