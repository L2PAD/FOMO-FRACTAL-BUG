"""
R1.3 — Research V3 Engine
Three modes: global, asset, universe.
"""

import time
from typing import Optional
from .snapshot import build_global_snapshot, build_asset_snapshot, build_universe_snapshot
from .scoring import (
    compute_market_state,
    compute_risk_pressure,
    compute_horizon_bias,
    compute_dominant_forces,
    compute_execution_implications,
)

# Per-key cache with 45s TTL
_cache: dict = {}
_CACHE_TTL = 45


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < _CACHE_TTL:
        return entry["data"]
    return None


def _cache_set(key: str, data: dict):
    _cache[key] = {"data": data, "ts": time.time()}


# ═══════════════════════════════════════════════════════════════
# GLOBAL REPORT
# ═══════════════════════════════════════════════════════════════

async def build_global_report(timeframe: str = "15m", force: bool = False) -> dict:
    ck = f"global_{timeframe}"
    if not force:
        cached = _cache_get(ck)
        if cached:
            return {**cached, "fromCache": True}

    t0 = time.time()
    snapshot = await build_global_snapshot(timeframe)

    report = _build_core_report(snapshot)
    report["mode"] = "global"
    report["symbol"] = None
    report["latencyMs"] = round((time.time() - t0) * 1000)

    _cache_set(ck, report)
    return report


# ═══════════════════════════════════════════════════════════════
# ASSET REPORT
# ═══════════════════════════════════════════════════════════════

async def build_asset_report(symbol: str, timeframe: str = "15m", force: bool = False) -> dict:
    ck = f"asset_{symbol}_{timeframe}"
    if not force:
        cached = _cache_get(ck)
        if cached:
            return {**cached, "fromCache": True}

    t0 = time.time()
    snapshot = await build_asset_snapshot(symbol, timeframe)

    report = _build_core_report(snapshot)
    report["mode"] = "asset"
    report["symbol"] = symbol
    report["latencyMs"] = round((time.time() - t0) * 1000)

    # Asset overlay from radar row
    asset_row = snapshot.get("assetRow")
    if asset_row:
        report["assetOverlay"] = {
            "radarOneLiner": asset_row.get("explain", {}).get("oneLiner", ""),
            "verdict": asset_row.get("verdict", "neutral"),
            "conviction": asset_row.get("conviction", 0),
            "convictionTier": asset_row.get("convictionTier"),
            "setupScore": asset_row.get("integrity", {}).get("setupScore", 0),
            "horizon": asset_row.get("horizons", {}).get("primary", "auto"),
            "risk": asset_row.get("risk", "unknown"),
            "direction": asset_row.get("direction", "neutral"),
            "structure": asset_row.get("structure", "unknown"),
            "divergence": {
                "score": asset_row.get("divergenceScore", 0),
                "label": asset_row.get("divergenceLabel", "NONE"),
            },
            "venues": {
                "venueCount": asset_row.get("venueCount", 1),
                "venues": asset_row.get("venues", ["binance"]),
            },
            "horizons": asset_row.get("horizons"),
            "reasons": asset_row.get("reasons", []),
        }
    else:
        report["assetOverlay"] = None

    _cache_set(ck, report)
    return report


# ═══════════════════════════════════════════════════════════════
# UNIVERSE REPORT
# ═══════════════════════════════════════════════════════════════

async def build_universe_report(timeframe: str = "15m", force: bool = False) -> dict:
    ck = f"universe_{timeframe}"
    if not force:
        cached = _cache_get(ck)
        if cached:
            return {**cached, "fromCache": True}

    t0 = time.time()
    snapshot = await build_universe_snapshot(timeframe)

    report = _build_core_report(snapshot)
    report["mode"] = "universe"
    report["symbol"] = None
    report["latencyMs"] = round((time.time() - t0) * 1000)

    # Universe insight from all radar rows
    all_rows = snapshot.get("allRows", [])
    report["universeInsight"] = _compute_universe_insight(all_rows)

    _cache_set(ck, report)
    return report


# ═══════════════════════════════════════════════════════════════
# CORE REPORT BUILDER
# ═══════════════════════════════════════════════════════════════

def _build_core_report(snapshot: dict) -> dict:
    market_state = compute_market_state(snapshot)
    risk_pressure = compute_risk_pressure(snapshot)
    dominant_forces = compute_dominant_forces(snapshot)

    # Get Labs V2 state for horizon bias enrichment
    labs_v2_state = _get_labs_v2_state()
    horizon_bias = compute_horizon_bias(snapshot, labs_v2_state=labs_v2_state)
    execution = compute_execution_implications(snapshot, risk_pressure, horizon_bias)

    integrity = _compute_integrity(snapshot)

    report = {
        "ok": True,
        "ts": int(time.time()),
        "freshnessSec": int(time.time()) - snapshot.get("ts", int(time.time())),
        "timeframe": snapshot.get("timeframe", "15m"),

        "marketState": market_state,
        "riskPressure": risk_pressure,
        "horizonBias": horizon_bias,
        "dominantForces": dominant_forces,
        "executionImplications": execution,
        "integrity": integrity,

        "meta": {
            "radarCoverage": snapshot.get("radar", {}).get("coverage", {}),
            "radarSpot": snapshot.get("radar", {}).get("spot", {}),
            "radarDivergence": snapshot.get("radar", {}).get("divergence", {}),
            "marketPulse": snapshot.get("pulse", {}),
            "healthStatus": snapshot.get("health", {}).get("status", "UNKNOWN"),
            "labsSummary": snapshot.get("labsSummary", {}),
        },

        "fromCache": False,
    }

    # Add Total Risk from Labs V2
    if labs_v2_state:
        report["totalRisk"] = labs_v2_state.get("totalRisk")

    return report


def _get_labs_v2_state() -> dict:
    """Get Labs V2 overall state + totalRisk (direct function call, no HTTP)."""
    try:
        from labs.service import compute_single_asset
        result = compute_single_asset("BTCUSDT")
        return {
            "overallState": result.get("overallState", {}),
            "totalRisk": result.get("totalRisk", {}),
            "explain": result.get("explain", {}),
        }
    except Exception:
        return {}


def _compute_integrity(snapshot: dict) -> dict:
    health = snapshot.get("health", {})
    radar = snapshot.get("radar", {})
    labs = snapshot.get("labs", {})
    coverage = radar.get("coverage", {})

    h_status = health.get("status", "UNKNOWN")
    rich_pct = coverage.get("richCoveragePct", 0)
    data_quality = labs.get("dataQuality", {})
    dq_conf = data_quality.get("confidence", 0)
    dq_state = data_quality.get("state", "UNKNOWN")

    reasons = []
    if h_status not in ("HEALTHY", "healthy"):
        reasons.append("System health degraded")
    if rich_pct < 80:
        reasons.append(f"Rich data coverage only {rich_pct}%")
    if dq_state in ("DEGRADED", "UNTRUSTED"):
        reasons.append(f"Data quality: {dq_state}")

    if reasons:
        status = "CRITICAL" if len(reasons) >= 2 else "DEGRADED"
    else:
        status = "HEALTHY"

    return {
        "status": status,
        "dataFreshnessSec": 0,
        "coveragePct": rich_pct,
        "dataQualityConfidence": dq_conf,
        "reasons": reasons,
    }


def _compute_universe_insight(rows: list) -> dict:
    """Cross-universe analysis from all radar rows."""
    if not rows:
        return {"dominance": [], "distributions": {"verdicts": {}, "tiers": {}, "horizons": {}}, "totalSymbols": 0}

    from collections import Counter

    total = len(rows)
    verdicts = Counter()
    tiers = Counter()
    horizons = Counter()
    risk_levels = Counter()
    structures = Counter()
    compression_count = 0
    high_conviction = 0
    divergent_count = 0

    for r in rows:
        v = r.get("verdict", "neutral")
        if v == "data_gap":
            continue
        verdicts[v] += 1
        tiers[r.get("convictionTier", "C")] += 1
        h = r.get("horizons", {})
        if isinstance(h, dict):
            horizons[h.get("primary", "auto")] += 1
        risk = r.get("risk", "unknown")
        risk_levels[risk if isinstance(risk, str) else "unknown"] += 1
        structures[r.get("structure", "unknown")] += 1

        feat = r.get("features", {})
        if isinstance(feat, dict) and feat.get("compression", 0) > 0.5:
            compression_count += 1
        if r.get("conviction", 0) >= 70:
            high_conviction += 1
        if r.get("divergenceScore", 0) >= 0.25:
            divergent_count += 1

    active = sum(verdicts.values())

    # Dominance = top patterns across universe
    dominance = []
    buy_pct = round(verdicts.get("buy", 0) / max(1, active) * 100, 1)
    sell_pct = round(verdicts.get("sell", 0) / max(1, active) * 100, 1)
    watch_pct = round(verdicts.get("watch", 0) / max(1, active) * 100, 1)
    compression_pct = round(compression_count / max(1, active) * 100, 1)
    high_conv_pct = round(high_conviction / max(1, active) * 100, 1)
    div_pct = round(divergent_count / max(1, active) * 100, 1)

    if buy_pct > 15:
        dominance.append({"key": "buy_bias", "pct": buy_pct, "label": f"Buy signals active ({buy_pct}% of universe)"})
    if sell_pct > 10:
        dominance.append({"key": "sell_bias", "pct": sell_pct, "label": f"Sell signals active ({sell_pct}% of universe)"})
    if compression_pct > 20:
        dominance.append({"key": "compression", "pct": compression_pct, "label": f"Compression building ({compression_pct}% of symbols)"})
    if high_conv_pct > 5:
        dominance.append({"key": "high_conviction", "pct": high_conv_pct, "label": f"High conviction setups ({high_conv_pct}%)"})
    if div_pct > 5:
        dominance.append({"key": "divergence", "pct": div_pct, "label": f"Venue divergence detected ({div_pct}%)"})
    if watch_pct > 40:
        dominance.append({"key": "caution", "pct": watch_pct, "label": f"Most symbols on WATCH ({watch_pct}%)"})

    dominance.sort(key=lambda d: d["pct"], reverse=True)

    return {
        "totalSymbols": active,
        "dominance": dominance[:5],
        "distributions": {
            "verdicts": dict(verdicts.most_common()),
            "tiers": dict(tiers.most_common()),
            "horizons": dict(horizons.most_common()),
            "risks": dict(risk_levels.most_common()),
        },
        "stats": {
            "buyPct": buy_pct,
            "sellPct": sell_pct,
            "watchPct": watch_pct,
            "compressionPct": compression_pct,
            "highConvictionPct": high_conv_pct,
            "divergencePct": div_pct,
        },
    }
