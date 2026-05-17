"""
Labs service — orchestrator for computing labs in all 3 modes.
No dependency on Radar. No HTTP self-calls.
"""

import time
from typing import Optional, List
from .config import LABS_CONFIG, GROUP_ORDER
from .providers import get_feature_map, get_all_symbols
from .scoring import compute_lab_score, compute_confidence, classify_state
from .state import classify_overall_state
from .explain import generate_explain
from .aggregate import aggregate_universe, compute_total_risk

# Simple TTL cache
_cache: dict = {}
_CACHE_TTL = 45


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < _CACHE_TTL:
        return entry["data"]
    return None


def _cache_set(key: str, data: dict):
    _cache[key] = {"data": data, "ts": time.time()}


def compute_single_asset(symbol: str) -> dict:
    """Compute all labs for a single asset."""
    feature_map, freshness_sec, source_type = get_feature_map(symbol)

    if not feature_map:
        return {
            "symbol": symbol,
            "labs": [],
            "overallState": {"stateKey": "DATA_WEAK", "stateLabel": "No data", "confidence": 0, "tags": ["NO_DATA"]},
            "explain": {"oneLiner": "No data available", "bullets": [], "risks": [], "invalidation": ""},
            "totalRisk": 0.0,
            "activeRisks": [],
            "integrity": {"status": "CRITICAL", "coveragePct": 0, "freshnessSec": 9999, "reasons": ["No data"]},
        }

    labs = []
    active_risks = []

    for lab_key, lab_cfg in LABS_CONFIG.items():
        score = compute_lab_score(lab_key, lab_cfg, feature_map)
        confidence = compute_confidence(score["present"], score["expected"], freshness_sec, source_type, score["abnormality"])
        state_label = classify_state(lab_key, lab_cfg, feature_map, score["abnormality"])

        lab_result = {
            "lab": lab_key,
            "group": lab_cfg["group"],
            "displayName": lab_cfg["displayName"],
            "description": lab_cfg["description"],
            "state": state_label,
            "abnormality": score["abnormality"],
            "riskContribution": score["riskContribution"],
            "convictionContribution": score["convictionContribution"],
            "confidence": round(confidence, 4),
            "horizonW": lab_cfg["horizonW"],
            "present": score["present"],
            "expected": score["expected"],
            "metrics": score["metrics"],
        }
        labs.append(lab_result)

        # Collect risk flags
        if score["riskContribution"] >= 0.60:
            active_risks.append(f"{lab_cfg['displayName']}: {state_label}")

    overall_state = classify_overall_state(labs)
    explain = generate_explain(overall_state, labs)
    total_risk = compute_total_risk(labs)

    # Integrity
    total_present = sum(l["present"] for l in labs)
    total_expected = sum(l["expected"] for l in labs)
    coverage_pct = round(total_present / max(1, total_expected) * 100, 1)
    reasons = []
    if coverage_pct < 60:
        reasons.append(f"Low coverage: {coverage_pct}%")
    if freshness_sec > 600:
        reasons.append(f"Stale data: {freshness_sec}s")
    if source_type == "snapshot":
        reasons.append("Fallback to snapshot data")

    status = "HEALTHY"
    if coverage_pct < 50 or freshness_sec > 900:
        status = "CRITICAL"
    elif coverage_pct < 70 or freshness_sec > 600 or source_type == "snapshot":
        status = "DEGRADED"

    return {
        "symbol": symbol,
        "labs": labs,
        "overallState": overall_state,
        "explain": explain,
        "totalRisk": total_risk,
        "activeRisks": active_risks,
        "integrity": {
            "status": status,
            "coveragePct": coverage_pct,
            "freshnessSec": freshness_sec,
            "sourceType": source_type,
            "reasons": reasons,
        },
    }


def compute_drilldown(lab_key: str, symbol: str) -> Optional[dict]:
    """Detailed drilldown for a single lab on a single asset."""
    if lab_key not in LABS_CONFIG:
        return None

    feature_map, freshness_sec, source_type = get_feature_map(symbol)
    if not feature_map:
        return None

    lab_cfg = LABS_CONFIG[lab_key]
    score = compute_lab_score(lab_key, lab_cfg, feature_map)
    confidence = compute_confidence(score["present"], score["expected"], freshness_sec, source_type)
    state_label = classify_state(lab_key, lab_cfg, feature_map, score["abnormality"])

    # Evidence bullets
    evidence = []
    for m in score["metrics"]:
        if m["abnormality"] > 0.4:
            direction = "elevated" if m["norm"] > 0.5 else "depressed"
            evidence.append(f"{m['key'].replace('_', ' ').title()}: {direction} (norm={m['norm']:.2f})")

    # Risk tags
    risk_tags = []
    if score["riskContribution"] >= 0.65:
        risk_tags.append("HIGH_RISK")
    if lab_key == "liquidity" and score["riskContribution"] >= 0.50:
        risk_tags.append("SLIPPAGE")
    if lab_key == "manipulation" and score["riskContribution"] >= 0.50:
        risk_tags.append("MANIPULATION_RISK")

    return {
        "lab": lab_key,
        "displayName": lab_cfg["displayName"],
        "group": lab_cfg["group"],
        "state": state_label,
        "confidence": round(confidence, 4),
        "abnormality": score["abnormality"],
        "riskContribution": score["riskContribution"],
        "convictionContribution": score["convictionContribution"],
        "horizonW": lab_cfg["horizonW"],
        "metrics": score["metrics"],
        "evidence": evidence,
        "risks": risk_tags,
        "sourceType": source_type,
        "freshnessSec": freshness_sec,
    }


def _get_labs_response(mode: str, asset: Optional[str] = None) -> dict:
    """Main entry point for labs API."""
    t0 = time.time()

    if mode == "asset" and asset:
        ck = f"labs_asset_{asset}"
        cached = _cache_get(ck)
        if cached:
            return {**cached, "fromCache": True}

        result = compute_single_asset(asset)
        # Group labs
        groups = _group_labs(result["labs"])
        response = {
            "ok": True,
            "mode": "asset",
            "asset": asset,
            "groups": groups,
            "overallState": result["overallState"],
            "explain": result["explain"],
            "totalRisk": result["totalRisk"],
            "activeRisks": result["activeRisks"],
            "integrity": result["integrity"],
            "latencyMs": round((time.time() - t0) * 1000),
        }
        _cache_set(ck, response)
        return response

    if mode == "universe":
        ck = "labs_universe"
        cached = _cache_get(ck)
        if cached:
            return {**cached, "fromCache": True}

        symbols = get_all_symbols()
        rows = []
        for sym in symbols[:200]:
            try:
                r = compute_single_asset(sym)
                rows.append(r)
            except Exception:
                continue

        agg = aggregate_universe(rows)
        response = {
            "ok": True,
            "mode": "universe",
            "universe": agg,
            "latencyMs": round((time.time() - t0) * 1000),
        }
        _cache_set(ck, response)
        return response

    # Global mode: BTC as proxy
    ck = "labs_global"
    cached = _cache_get(ck)
    if cached:
        return {**cached, "fromCache": True}

    result = compute_single_asset("BTCUSDT")
    groups = _group_labs(result["labs"])
    response = {
        "ok": True,
        "mode": "global",
        "asset": "BTCUSDT",
        "groups": groups,
        "overallState": result["overallState"],
        "explain": result["explain"],
        "totalRisk": result["totalRisk"],
        "activeRisks": result["activeRisks"],
        "integrity": result["integrity"],
        "latencyMs": round((time.time() - t0) * 1000),
    }
    _cache_set(ck, response)
    return response


def _group_labs(labs: list) -> list:
    """Group labs by GROUP_ORDER."""
    grouped = {}
    for lab in labs:
        g = lab["group"]
        if g not in grouped:
            grouped[g] = []
        grouped[g].append(lab)

    result = []
    for g in GROUP_ORDER:
        if g in grouped:
            result.append({"name": g, "labs": grouped[g]})
    return result
