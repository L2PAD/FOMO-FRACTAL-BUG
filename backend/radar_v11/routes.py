"""
ALT RADAR V11 — FastAPI Routes (v4 — R4.2 Cache + R4.3 Guardrails)
===================================================================
All endpoints support: page, limit, search, verdict, minConv, sort.
Response includes meta: {universe, total, page, pages, limit}.
R4.2: LRU Cache (45s TTL) on list endpoints.
R4.3: Rate limiting, max pageSize=100.
"""

import time
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from typing import List, Dict
from collections import Counter

from .types import (
    SpotRadarResponse, FuturesRadarResponse, UniverseResponse,
    PaginationMeta, Verdict,
)
from .universe import (
    get_spot_main_symbols, get_spot_alpha_symbols,
    get_futures_symbols, get_universe_counts,
)
from .spot_engine import scan_spot
from .futures_engine import scan_futures
from .market_board import build_market_board
from .alpha_builder import (
    build_alpha_universe, get_last_build_result,
    get_dynamic_alpha_meta, get_alpha_candidates, get_alpha_stats,
)

# R4.2: Cache layer
import radar_cache as cache

# R4.3: Load guardrails
from rate_limiter import MAX_PAGE_SIZE
from exchange_health import record_pipeline_hit

router = APIRouter(prefix="/api/v11/exchange/radar", tags=["radar-v11"])
market_router = APIRouter(prefix="/api/v11/exchange/market", tags=["market-v2"])


# -- Helpers --

def _apply_filters(rows, search=None, verdict=None, min_conv=None):
    if search:
        s = search.lower().strip()
        rows = [r for r in rows if s in r.symbol.lower()]
    if verdict and verdict != "all":
        rows = [r for r in rows if r.verdict.value == verdict.lower()]
    if min_conv is not None and min_conv > 0:
        rows = [r for r in rows if r.conviction >= min_conv]
    return rows


def _apply_sort(rows, sort="conviction"):
    if sort == "risk":
        order = {"high": 0, "medium": 1, "low": 2, "unknown": 3}
        return sorted(rows, key=lambda r: order.get(r.risk.value, 3))
    if sort == "symbol":
        return sorted(rows, key=lambda r: r.symbol)
    # conviction desc, DATA_GAP last
    return sorted(rows, key=lambda r: (0 if r.verdict == Verdict.DATA_GAP else 1, r.conviction), reverse=True)


def _paginate(rows, page: int, limit: int):
    page = max(1, page)
    limit = max(1, min(MAX_PAGE_SIZE, limit))  # R4.3: enforce max page size
    total = len(rows)
    pages = max(1, (total + limit - 1) // limit)
    start = (page - 1) * limit
    end = start + limit
    return rows[start:end], PaginationMeta(
        total=total, page=page, pages=pages, limit=limit,
    )



# ═══════════════════════════════════════════════════════════════
# P2 — Market V2 Board
# ═══════════════════════════════════════════════════════════════

@market_router.get("/board")
def get_market_board(
    universe: str = Query("alpha", description="main or alpha"),
):
    """
    Market Execution Intelligence Board.
    Returns categorized radar rows: actionNow, earlyBuild, structuralShift, riskEvents + pulse.
    """
    t0 = time.time()

    # Fetch all radar rows for the universe (no pagination — board does its own filtering)
    all_rows = scan_spot(venue=universe, limit=500)

    board = build_market_board(all_rows)
    board["latencyMs"] = round((time.time() - t0) * 1000)
    return board


# -- Universe --

@router.get("/universe")
def get_universe(
    mode: str = Query("spot", description="spot or futures"),
):
    counts = get_universe_counts()
    if mode == "futures":
        return UniverseResponse(
            ok=True,
            mode="futures",
            futuresCount=counts["futuresCount"],
            futuresSymbols=get_futures_symbols(),
        )
    return UniverseResponse(
        ok=True,
        mode="spot",
        spotMainCount=counts["spotMainCount"],
        spotAlphaCount=counts["spotAlphaCount"],
        spotMainSymbols=get_spot_main_symbols(),
        spotAlphaSymbols=get_spot_alpha_symbols(),
    )


# -- Spot (main + alpha) --

@router.get("/spot")
def get_spot_radar(
    venue: str = Query("main", description="main or alpha"),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    search: str = Query(None),
    verdict: str = Query(None),
    minConv: int = Query(None, ge=0, le=100),
    sort: str = Query("conviction"),
):
    record_pipeline_hit("radar_spot")

    # R4.2: Check cache
    cache_key = cache.build_cache_key(
        universe=f"spot_{venue}", sort=sort, page=page,
        page_size=limit, search=search, verdict=verdict, min_conv=minConv,
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return JSONResponse(content=cached)

    t0 = time.time()
    all_rows = scan_spot(venue=venue)
    filtered = _apply_filters(all_rows, search=search, verdict=verdict, min_conv=minConv)
    sorted_rows = _apply_sort(filtered, sort=sort)
    page_rows, meta = _paginate(sorted_rows, page, limit)
    meta.universe = venue

    now = datetime.now(timezone.utc).isoformat()
    response = SpotRadarResponse(
        ok=True,
        mode="spot",
        venue=venue,
        count=len(page_rows),
        updatedAt=now,
        rows=page_rows,
        meta=meta,
    )

    # Serialize and cache
    result = response.model_dump(mode="json")
    result["_computeMs"] = round((time.time() - t0) * 1000, 1)
    cache.set(cache_key, result, cache.LIST_TTL)
    return result


# -- Futures --

@router.get("/futures")
def get_futures_radar(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    search: str = Query(None),
    verdict: str = Query(None),
    minConv: int = Query(None, ge=0, le=100),
    sort: str = Query("conviction"),
):
    record_pipeline_hit("radar_futures")

    # R4.2: Check cache
    cache_key = cache.build_cache_key(
        universe="futures", sort=sort, page=page,
        page_size=limit, search=search, verdict=verdict, min_conv=minConv,
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return JSONResponse(content=cached)

    t0 = time.time()
    all_rows = scan_futures()
    filtered = _apply_filters(all_rows, search=search, verdict=verdict, min_conv=minConv)
    sorted_rows = _apply_sort(filtered, sort=sort)
    page_rows, meta = _paginate(sorted_rows, page, limit)
    meta.universe = "futures"

    now = datetime.now(timezone.utc).isoformat()
    response = FuturesRadarResponse(
        ok=True,
        mode="futures",
        count=len(page_rows),
        updatedAt=now,
        rows=page_rows,
        meta=meta,
    )

    result = response.model_dump(mode="json")
    result["_computeMs"] = round((time.time() - t0) * 1000, 1)
    cache.set(cache_key, result, cache.LIST_TTL)
    return result


# -- Debug Stats --

@router.get("/debug/stats")
def get_debug_stats(
    universe: str = Query("main", description="main, alpha, or futures"),
):
    """Verdict distribution + data quality overview."""
    u = universe.lower()
    if u == "futures":
        rows = scan_futures()
    else:
        rows = scan_spot(venue=u)

    verdict_dist = Counter(r.verdict.value for r in rows)
    source_dist = Counter(r.source or "unknown" for r in rows)
    conviction_vals = [r.conviction for r in rows if r.verdict != Verdict.DATA_GAP]
    data_gap_count = verdict_dist.get("data_gap", 0)
    total = len(rows)

    return {
        "ok": True,
        "universe": u,
        "total": total,
        "verdictDistribution": dict(verdict_dist),
        "sourceDistribution": dict(source_dist),
        "convictionStats": {
            "min": min(conviction_vals) if conviction_vals else 0,
            "max": max(conviction_vals) if conviction_vals else 0,
            "avg": round(sum(conviction_vals) / len(conviction_vals), 1) if conviction_vals else 0,
        },
        "dataQuality": {
            "dataGapCount": data_gap_count,
            "dataGapPct": round(data_gap_count / total * 100, 1) if total > 0 else 0,
            "withDataCount": total - data_gap_count,
        },
    }


# -- Admin Rebuild --

@router.post("/admin/rebuild")
def admin_rebuild(
    universe: str = Query("futures", description="main, alpha, or futures"),
):
    """Force rebuild verdicts for all symbols in universe. Returns stats."""
    u = universe.lower()
    if u == "futures":
        rows = scan_futures()
    else:
        rows = scan_spot(venue=u)

    verdict_dist = Counter(r.verdict.value for r in rows)
    return {
        "ok": True,
        "universe": u,
        "totalScanned": len(rows),
        "verdictDistribution": dict(verdict_dist),
    }


# -- P3: Alpha Universe Builder --

@router.post("/admin/alpha-build")
def admin_alpha_build():
    """Trigger dynamic alpha universe rebuild. Returns full build summary."""
    result = build_alpha_universe()
    return result


@router.get("/admin/alpha/stats")
def admin_alpha_stats():
    """Admin: coverage, distribution, top movers."""
    return {"ok": True, **get_alpha_stats()}


@router.get("/debug/alpha-universe")
def debug_alpha_universe():
    """Current state of dynamic alpha universe + last build result."""
    meta = get_dynamic_alpha_meta()
    last_build = get_last_build_result()

    return {
        "ok": True,
        "meta": meta,
        "lastBuild": {
            "status": last_build["status"] if last_build else None,
            "candidatesTotal": last_build["candidates"]["total"] if last_build else 0,
            "selectedCount": last_build["selected"]["count"] if last_build else 0,
            "avgScore": last_build["selected"]["avgScore"] if last_build else 0,
            "top10": last_build["top10"] if last_build else [],
            "builtAt": last_build["builtAt"] if last_build else None,
        } if last_build else None,
    }


@router.get("/alpha/universe")
def alpha_universe():
    """Public: current alpha universe state."""
    meta = get_dynamic_alpha_meta()
    return {"ok": True, **meta}


@router.get("/alpha/candidates")
def alpha_candidates_list(
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    venue: str = Query(None),
):
    """Public: paginated alpha candidates from latest build."""
    result = get_alpha_candidates(page=page, page_size=pageSize, venue=venue)
    return {"ok": True, **result}



# -- R5: Self-check endpoint --

@router.get("/selfcheck")
def radar_selfcheck():
    """
    Global integrity self-check.
    Returns verdict/integrity distributions, coverage stats, worst/best symbols.
    """
    record_pipeline_hit("radar_selfcheck")

    # Scan all three universes
    spot_main = scan_spot(venue="main")
    spot_alpha = scan_spot(venue="alpha")
    futures_rows = scan_futures()

    all_rows = spot_main + spot_alpha

    # Verdict distribution
    verdict_dist = Counter()
    for r in all_rows:
        verdict_dist[r.verdict.value] += 1

    # Integrity distribution
    integrity_dist = Counter()
    coverage_by_universe = {"main": [], "alpha": [], "futures": []}

    for r in spot_main:
        if r.integrity:
            integrity_dist[r.integrity.status] += 1
            coverage_by_universe["main"].append(r.integrity.coveragePct)
    for r in spot_alpha:
        if r.integrity:
            integrity_dist[r.integrity.status] += 1
            coverage_by_universe["alpha"].append(r.integrity.coveragePct)

    # Futures don't have integrity yet — just count verdicts
    futures_verdict_dist = Counter()
    for r in futures_rows:
        futures_verdict_dist[r.verdict.value] += 1

    # Average coverage per universe
    avg_coverage = {}
    for k, vals in coverage_by_universe.items():
        avg_coverage[k] = round(sum(vals) / len(vals), 1) if vals else 0

    # Top 10 worst (by coverage)
    all_with_integrity = [(r.symbol, r.integrity) for r in all_rows if r.integrity]
    worst_10 = sorted(all_with_integrity, key=lambda x: x[1].coveragePct)[:10]
    worst_10_out = [
        {"symbol": sym, "coveragePct": ig.coveragePct, "status": ig.status,
         "setupScore": ig.setupScore, "reasons": ig.reasons}
        for sym, ig in worst_10
    ]

    # Top 10 best (by setupScore + conviction)
    all_with_score = [
        (r.symbol, r.conviction, r.integrity.setupScore if r.integrity else 0,
         r.verdict.value, r.integrity.status if r.integrity else "unknown")
        for r in all_rows if r.verdict.value not in ("data_gap",)
    ]
    best_10 = sorted(all_with_score, key=lambda x: (x[2], x[1]), reverse=True)[:10]
    best_10_out = [
        {"symbol": s, "conviction": c, "setupScore": ss, "verdict": v, "integrity": i}
        for s, c, ss, v, i in best_10
    ]

    # P0.2: Source coverage breakdown
    source_dist = Counter()
    for r in all_rows:
        source_dist[r.source or "unknown"] += 1

    rich_count = source_dist.get("observations", 0) + source_dist.get("verdict", 0)
    snapshot_count = source_dist.get("snapshot", 0) + source_dist.get("unknown", 0)
    total_count = len(all_rows)
    rich_pct = round(rich_count / total_count * 100, 1) if total_count > 0 else 0
    data_gap_count = sum(1 for r in all_rows if r.verdict.value == "data_gap")

    # P1.2: Divergence stats
    multi_venue_rows = [r for r in all_rows if (r.venueCount or 1) >= 2]
    multi_venue_pct = round(len(multi_venue_rows) / total_count * 100, 1) if total_count > 0 else 0
    div_scores = [r.divergenceScore for r in all_rows if r.divergenceScore > 0]
    avg_divergence = round(sum(div_scores) / len(div_scores), 4) if div_scores else 0
    high_div_count = sum(1 for r in all_rows if r.divergenceScore > 0.55)
    boosted_short_count = sum(1 for r in all_rows if r.divergenceScore >= 0.25 and r.divergenceScore <= 0.85)

    return {
        "ok": True,
        "coverage": {
            "totalSymbols": total_count,
            "richCoveragePct": rich_pct,
            "snapshotOnlyPct": round(snapshot_count / total_count * 100, 1) if total_count > 0 else 0,
            "dataGapPct": round(data_gap_count / total_count * 100, 1) if total_count > 0 else 0,
            "bySource": dict(source_dist),
        },
        "spot": {
            "totalSymbols": total_count,
            "verdictDistribution": dict(verdict_dist),
            "integrityDistribution": dict(integrity_dist),
            "avgCoverage": avg_coverage,
        },
        "futures": {
            "totalSymbols": len(futures_rows),
            "verdictDistribution": dict(futures_verdict_dist),
        },
        "divergence": {
            "multiVenuePct": multi_venue_pct,
            "avgDivergence": avg_divergence,
            "highDivergenceCount": high_div_count,
            "boostedShortCount": boosted_short_count,
        },
        "worst10": worst_10_out,
        "best10": best_10_out,
    }
