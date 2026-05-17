"""
Core Engine V2.1 — Service Layer.
Orchestrates providers + formulas. Supports tf, relative metrics, search.
"""

import time
from .config import CACHE_TTL, VALID_TIMEFRAMES, DEFAULT_TIMEFRAME, TF_PROFILES
from .providers import get_labs_features, get_macro_context, get_divergence_for_symbol, get_all_universe_symbols
from .formulas import (
    compute_integrity_penalty, compute_macro_multiplier,
    compute_regime_probabilities, compute_risk_surface,
    compute_factors, compute_pressure, compute_transition,
    compute_execution,
)
from .explain import build_explain

_cache = {}


def _cache_get(key):
    e = _cache.get(key)
    if e and (time.time() - e["ts"]) < CACHE_TTL:
        return e["data"]
    return None


def _cache_set(key, data):
    _cache[key] = {"data": data, "ts": time.time()}


def compute_snapshot(symbol: str, tf: str = "1h") -> dict:
    """Full Core Engine computation for a single asset with TF-specific parameters."""
    tf_profile = TF_PROFILES.get(tf, TF_PROFILES[DEFAULT_TIMEFRAME])

    f = get_labs_features(symbol)
    macro_raw = get_macro_context()
    divergence = get_divergence_for_symbol(symbol)

    integrity = compute_integrity_penalty(f, divergence)
    macro = compute_macro_multiplier(macro_raw)
    regime = compute_regime_probabilities(f, integrity["penalty"], tf_profile=tf_profile)
    risk = compute_risk_surface(f, macro["multiplier"], tf_profile=tf_profile)
    factors = compute_factors(f)
    pressure = compute_pressure(f, factors, tf_profile=tf_profile)
    transition = compute_transition(f, regime, risk, divergence, tf_profile=tf_profile)
    execution = compute_execution(risk, factors, integrity, macro, transition["shiftProbability"])
    explain = build_explain(regime, risk, pressure, transition, execution, integrity, macro)

    # Structural reference: for TFs < 4h, also compute key metrics using 4h profile
    # This gives "longer TF priority" for blocks/confidence
    structural_ref = None
    STRUCTURAL_TF = "4h"
    if tf in ("30m", "1h") and tf != STRUCTURAL_TF:
        ref_profile = TF_PROFILES[STRUCTURAL_TF]
        ref_regime = compute_regime_probabilities(f, integrity["penalty"], tf_profile=ref_profile)
        ref_risk = compute_risk_surface(f, macro["multiplier"], tf_profile=ref_profile)
        ref_transition = compute_transition(f, ref_regime, ref_risk, divergence, tf_profile=ref_profile)
        ref_execution = compute_execution(ref_risk, factors, integrity, macro, ref_transition["shiftProbability"])
        structural_ref = {
            "tf": STRUCTURAL_TF,
            "regime": ref_regime["dominant"],
            "regimeConf": ref_regime["confidence"],
            "risk": ref_risk["totalIndex"],
            "riskLevel": ref_risk["level"],
            "shiftProbability": ref_transition["shiftProbability"],
            "strongActionsBlocked": ref_execution["strongActionsBlocked"],
            "blockedGates": ref_execution["blockedGates"],
            "aggression": ref_execution["aggressionMultiplier"],
        }

    return {
        "symbol": symbol,
        "regime": regime,
        "risk": risk,
        "factors": factors,
        "pressure": pressure,
        "transition": transition,
        "execution": execution,
        "integrity": integrity,
        "macro": macro,
        "explain": explain,
        "structuralRef": structural_ref,
    }


def get_snapshot(scope: str = "global", symbol: str = "BTCUSDT", tf: str = "15m") -> dict:
    """Get Core Engine snapshot (cached)."""
    if tf not in VALID_TIMEFRAMES:
        tf = DEFAULT_TIMEFRAME

    ck = f"ce_snapshot_{scope}_{symbol}_{tf}"
    cached = _cache_get(ck)
    if cached:
        return {**cached, "fromCache": True}

    t0 = time.time()
    result = compute_snapshot(symbol, tf=tf)
    result["meta"] = {
        "scope": scope,
        "symbol": symbol,
        "tf": tf,
        "timestamp": int(time.time()),
        "latencyMs": round((time.time() - t0) * 1000),
    }
    result["ok"] = True
    _cache_set(ck, result)
    return result


# ── Universe stats cache for relative metrics ──
_universe_stats_cache = {"data": None, "ts": 0}


def _get_universe_stats(tf: str = "1h") -> dict:
    """Compute and cache universe medians for relative comparison."""
    now = time.time()
    cache_key = f"universe_stats_{tf}"
    if _universe_stats_cache.get("key") == cache_key and _universe_stats_cache["data"] and (now - _universe_stats_cache["ts"]) < 120:
        return _universe_stats_cache["data"]

    symbols = get_all_universe_symbols()[:200]
    risks = []
    shifts = []
    instabilities = []
    biases = []
    regimes = {"breakout": 0, "range": 0, "distribution": 0, "trend": 0}

    for sym in symbols:
        try:
            snap = compute_snapshot(sym, tf=tf)
            shifts.append(snap["transition"]["shiftProbability"])
            instabilities.append(snap["transition"]["instability"])
            biases.append(snap["pressure"]["netBias"])
            dom = snap["regime"]["dominant"]
            if dom in regimes:
                regimes[dom] += 1
        except Exception:
            continue

    count = len(risks) or 1
    risks.sort()
    shifts.sort()
    instabilities.sort()

    stats = {
        "count": count,
        "riskMedian": risks[count // 2] if risks else 50,
        "riskMean": round(sum(risks) / count) if risks else 50,
        "shiftMedian": round(sorted(shifts)[count // 2], 4) if shifts else 0.5,
        "instabilityMedian": round(sorted(instabilities)[count // 2], 4) if instabilities else 0.5,
        "biasAvg": round(sum(biases) / count, 4) if biases else 0,
        "regimeDistribution": regimes,
        "risks": risks,
        "shifts": shifts,
        "instabilities": instabilities,
    }
    _universe_stats_cache["data"] = stats
    _universe_stats_cache["ts"] = now
    _universe_stats_cache["key"] = cache_key
    return stats


def _compute_relative(snap: dict, stats: dict) -> dict:
    """Compute asset-vs-universe relative metrics."""
    asset_risk = snap["risk"]["totalIndex"]
    asset_shift = snap["transition"]["shiftProbability"]
    asset_instab = snap["transition"]["instability"]
    asset_bias = snap["pressure"]["netBias"]
    asset_regime = snap["regime"]["dominant"]

    # Risk percentile
    risks = stats.get("risks", [])
    risk_pct = round(sum(1 for r in risks if r <= asset_risk) / max(len(risks), 1) * 100)

    # Shift rank
    shifts = stats.get("shifts", [])
    shift_rank = sum(1 for s in shifts if s >= asset_shift)

    # Instability rank
    instabs = stats.get("instabilities", [])
    instab_rank = sum(1 for i in instabs if i >= asset_instab)

    # Regime deviation
    global_dominant = max(stats["regimeDistribution"], key=stats["regimeDistribution"].get)
    regime_aligns = asset_regime == global_dominant

    # Bias vs universe avg
    bias_diff = round((asset_bias - stats["biasAvg"]) * 100, 1)

    return {
        "riskPercentile": risk_pct,
        "riskVsMedian": asset_risk - stats["riskMedian"],
        "shiftRank": shift_rank,
        "shiftTotal": len(shifts),
        "instabilityRank": instab_rank,
        "instabilityTotal": len(instabs),
        "regimeAlignsGlobal": regime_aligns,
        "globalDominant": global_dominant,
        "biasVsAvg": bias_diff,
        "universeCount": stats["count"],
    }


def get_snapshot_with_relative(scope: str = "global", symbol: str = "BTCUSDT", tf: str = "15m") -> dict:
    """Get snapshot. If asset mode, include relative metrics."""
    result = get_snapshot(scope=scope, symbol=symbol, tf=tf)

    if scope == "asset" and symbol != "BTCUSDT":
        try:
            stats = _get_universe_stats(tf=tf)
            result["relative"] = _compute_relative(result, stats)
        except Exception:
            result["relative"] = None
    else:
        result["relative"] = None

    return result


def get_universe(tf: str = "15m") -> dict:
    """Get Core Engine universe summary."""
    if tf not in VALID_TIMEFRAMES:
        tf = DEFAULT_TIMEFRAME

    ck = f"ce_universe_{tf}"
    cached = _cache_get(ck)
    if cached:
        return {**cached, "fromCache": True}

    t0 = time.time()
    symbols = get_all_universe_symbols()[:200]

    regime_dist = {"breakout": 0, "range": 0, "distribution": 0, "trend": 0}
    risk_dist = {"low": 0, "moderate": 0, "high": 0}
    bias_dist = {"bullish": 0, "bearish": 0, "neutral": 0}

    top_unstable = []
    top_risky = []
    top_opportunities = []

    for sym in symbols:
        try:
            snap = compute_snapshot(sym, tf=tf)
            dom = snap["regime"]["dominant"]
            if dom in regime_dist:
                regime_dist[dom] += 1
            lvl = snap["risk"]["level"]
            if lvl in risk_dist:
                risk_dist[lvl] += 1
            bl = snap["pressure"]["biasLabel"]
            if "bullish" in bl:
                bias_dist["bullish"] += 1
            elif "bearish" in bl:
                bias_dist["bearish"] += 1
            else:
                bias_dist["neutral"] += 1

            shift = snap["transition"]["shiftProbability"]
            risk_idx = snap["risk"]["totalIndex"]
            amp = snap["execution"]["signalAmplification"]

            sym_short = sym.replace("USDT", "")
            top_unstable.append({"symbol": sym_short, "shiftProb": shift, "regime": dom})
            top_risky.append({"symbol": sym_short, "risk": risk_idx, "level": lvl})
            top_opportunities.append({
                "symbol": sym_short,
                "amp": amp,
                "risk": risk_idx,
                "regime": dom,
                "bias": bl,
            })
        except Exception:
            continue

    top_unstable.sort(key=lambda x: x["shiftProb"], reverse=True)
    top_risky.sort(key=lambda x: x["risk"], reverse=True)
    top_opportunities.sort(key=lambda x: (x["amp"] * (1 - x["risk"] / 100)), reverse=True)

    result = {
        "ok": True,
        "meta": {
            "scope": "universe",
            "tf": tf,
            "count": len(symbols),
            "timestamp": int(time.time()),
            "latencyMs": round((time.time() - t0) * 1000),
        },
        "regimeDistribution": regime_dist,
        "riskDistribution": risk_dist,
        "biasDistribution": bias_dist,
        "topUnstable": top_unstable[:10],
        "topRisky": top_risky[:10],
        "topOpportunities": top_opportunities[:10],
    }
    _cache_set(ck, result)
    return result


def search_symbols(query: str, tf: str = "1h") -> dict:
    """Search symbols with Core Engine preview metrics."""
    symbols = get_all_universe_symbols()
    q = query.upper().replace("USDT", "")
    matched = [s for s in symbols if q in s.replace("USDT", "")][:15]

    results = []
    for sym in matched:
        try:
            snap = compute_snapshot(sym, tf=tf)
            results.append({
                "symbol": sym,
                "short": sym.replace("USDT", ""),
                "regime": snap["regime"]["dominant"],
                "regimeConf": snap["regime"]["confidence"],
                "risk": snap["risk"]["totalIndex"],
                "riskLevel": snap["risk"]["level"],
                "bias": snap["pressure"]["biasLabel"],
                "shift": snap["transition"]["shiftProbability"],
            })
        except Exception:
            results.append({
                "symbol": sym,
                "short": sym.replace("USDT", ""),
                "regime": "unknown",
                "regimeConf": 0,
                "risk": 0,
                "riskLevel": "unknown",
                "bias": "neutral",
                "shift": 0,
            })

    return {"ok": True, "query": query, "count": len(results), "results": results}


def get_explain(symbol: str, tf: str = "15m") -> dict:
    """Get Core Engine explain drilldown for a symbol."""
    snap = get_snapshot(scope="asset", symbol=symbol, tf=tf)
    return {
        "ok": True,
        "symbol": symbol,
        "tf": tf,
        "explain": snap.get("explain", {}),
        "integrity": snap.get("integrity", {}),
        "macro": snap.get("macro", {}),
        "factors": snap.get("factors", {}),
    }


# Legacy compatibility
def get_core_global():
    return get_snapshot(scope="global", symbol="BTCUSDT")


def get_core_asset(symbol: str):
    return get_snapshot(scope="asset", symbol=symbol)


def get_core_universe():
    return get_universe()
