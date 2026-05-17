"""
Intelligence Console — Data Engine
====================================
Computes all 6 sections of the Intelligence Console from exchange_forecasts.
Supports time range filtering and baseline comparison.

Sections:
  1. System Health (overview)
  2. Phase Performance (phases)
  3. Regime Performance (regimes)
  4. Scenario Engine (scenarios)
  5. Drift Intelligence (drift) — delegates to existing drift_analysis
  6. Tactical + Execution Impact (tactical)
"""

import os
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from pymongo import MongoClient

_client = None


def _db():
    global _client
    if _client is None:
        _client = MongoClient(os.environ["MONGO_URL"])
    return _client[os.environ["DB_NAME"]]


RANGE_DAYS = {"7d": 7, "30d": 30, "90d": 90, "all": 9999}


def _range_filter(range_key: str):
    """Return (current_ms_start, previous_ms_start, previous_ms_end) for range."""
    days = RANGE_DAYS.get(range_key, 30)
    now = datetime.now(timezone.utc)
    if days >= 9999:
        return 0, 0, 0
    current_start = int((now - timedelta(days=days)).timestamp() * 1000)
    prev_end = current_start
    prev_start = int((now - timedelta(days=days * 2)).timestamp() * 1000)
    return current_start, prev_start, prev_end


def _get_evaluated(range_key: str = "all", asset: str = "BTC"):
    """Fetch evaluated forecasts for given range."""
    col = _db()["exchange_forecasts"]
    current_start, prev_start, prev_end = _range_filter(range_key)

    base_filter = {
        "evaluated": True,
        "outcome": {"$exists": True},
        "asset": asset,
    }

    if current_start > 0:
        current_filter = {**base_filter, "createdAt": {"$gte": current_start}}
        prev_filter = {**base_filter, "createdAt": {"$gte": prev_start, "$lt": prev_end}}
    else:
        current_filter = base_filter
        prev_filter = None

    proj = {
        "_id": 0, "direction": 1, "confidence": 1, "horizonDays": 1,
        "createdAt": 1, "modelVersion": 1, "expectedMovePct": 1,
        "outcome.hit": 1, "outcome.errorPct": 1, "outcome.realMovePct": 1,
        "outcome.pnlPct": 1, "outcome.label": 1,
        "audit.regimeV2": 1, "audit.regimeAdjustments": 1,
        "audit.regime": 1, "audit.scenarioResult": 1,
    }

    current_docs = list(col.find(current_filter, proj).sort("createdAt", -1))
    prev_docs = list(col.find(prev_filter, proj).sort("createdAt", -1)) if prev_filter else []

    return current_docs, prev_docs


def _compute_stats(docs):
    """Compute basic stats from a set of forecast documents."""
    if not docs:
        return {"n": 0, "accuracy": 0, "pnl": 0, "catastrophic_rate": 0, "avg_error": 0}

    n = len(docs)
    hits = sum(1 for d in docs if d.get("outcome", {}).get("hit"))
    catastrophic = sum(1 for d in docs if abs(d.get("outcome", {}).get("errorPct", 0) or 0) > 10)
    pnl = sum(d.get("outcome", {}).get("realMovePct", 0) or 0 for d in docs)
    errors = [abs(d.get("outcome", {}).get("errorPct", 0) or 0) for d in docs]

    return {
        "n": n,
        "accuracy": round(hits / n, 3) if n else 0,
        "pnl": round(pnl, 2),
        "catastrophic_rate": round(catastrophic / n, 3) if n else 0,
        "avg_error": round(sum(errors) / len(errors), 2) if errors else 0,
    }


def _with_delta(current, previous, keys=None):
    """Add delta comparison to stats."""
    keys = keys or ["accuracy", "pnl", "catastrophic_rate"]
    result = {}
    for k, v in current.items():
        if k in keys and isinstance(v, (int, float)):
            prev_v = previous.get(k, 0)
            result[k] = {"current": v, "previous": prev_v, "delta": round(v - prev_v, 3)}
        else:
            result[k] = v
    return result


# ═══════════════════════════════════════════════════════
# SECTION 1: System Health
# ═══════════════════════════════════════════════════════
def compute_overview(range_key: str = "30d", asset: str = "BTC"):
    current, prev = _get_evaluated(range_key, asset)
    stats_now = _compute_stats(current)
    stats_prev = _compute_stats(prev)

    # Uncertainty distribution
    uncertainty = {"low": 0, "mid": 0, "high": 0}
    for d in current:
        conf = d.get("confidence", 0.5)
        if conf >= 0.7:
            uncertainty["low"] += 1
        elif conf >= 0.4:
            uncertainty["mid"] += 1
        else:
            uncertainty["high"] += 1
    n = max(len(current), 1)
    uncertainty = {k: round(v / n, 3) for k, v in uncertainty.items()}

    # Execution mode distribution (inferred from confidence)
    exec_modes = {"normal": 0, "reduced": 0, "minimal": 0}
    for d in current:
        conf = d.get("confidence", 0.5)
        adj = (d.get("audit") or {}).get("regimeAdjustments", {})
        du = adj.get("decision_uncertainty", 0.5)
        if du >= 0.65:
            exec_modes["minimal"] += 1
        elif du >= 0.45:
            exec_modes["reduced"] += 1
        else:
            if conf < 0.3:
                exec_modes["minimal"] += 1
            elif conf < 0.5:
                exec_modes["reduced"] += 1
            else:
                exec_modes["normal"] += 1
    exec_modes = {k: round(v / n, 3) for k, v in exec_modes.items()}

    # System mode from drift
    from drift.drift_execution_hook import compute_drift_adjustments
    try:
        from drift.drift_metrics_engine import compute_drift_metrics
        from drift.drift_detector import detect_drift
        from drift.drift_analysis import compute_drift_score as compute_intelligence_score
        metrics = compute_drift_metrics(horizon_days=7, asset=asset, rolling_window_days=14)
        if metrics.get("ok"):
            drift_result = detect_drift(metrics)
            drift_score_data = compute_intelligence_score(metrics, drift_result)
            drift_score = drift_score_data.get("score", 0)
            cat_rate = metrics.get("global", {}).get("catastrophic_rate", 0)
            adj = compute_drift_adjustments(drift_score, cat_rate)
            system_mode = adj["mode"]
        else:
            system_mode = "normal"
    except Exception:
        system_mode = "normal"

    return {
        "stats": _with_delta(stats_now, stats_prev),
        "uncertainty": uncertainty,
        "execution_modes": exec_modes,
        "system_mode": system_mode,
    }


# ═══════════════════════════════════════════════════════
# SECTION 2: Phase Performance
# ═══════════════════════════════════════════════════════
def compute_phases(range_key: str = "30d", asset: str = "BTC"):
    current, prev = _get_evaluated(range_key, asset)

    def _group_by_phase(docs):
        groups = defaultdict(list)
        for d in docs:
            adj = (d.get("audit") or {}).get("regimeAdjustments", {})
            flags = adj.get("flags") or []
            # Determine phase from flags
            phase = "standard"
            if "transition_caution" in flags or "transition_hard_dampen" in flags:
                phase = "unstable_transition"
            elif "uncertainty_damping" in flags:
                phase = "high_uncertainty"
            elif "synergy_transition_weak" in flags:
                phase = "mixed_range"

            # Also check direction for recovery/pullback hints
            rv2 = (d.get("audit") or {}).get("regimeV2", {})
            dom = (rv2.get("dominant_regime") or "").lower()
            if dom == "pullback":
                phase = "pullback"
            elif dom == "transition":
                phase = "unstable_transition"
            elif dom == "breakdown":
                phase = "breakdown"

            groups[phase].append(d)
        return groups

    curr_groups = _group_by_phase(current)
    prev_groups = _group_by_phase(prev)

    phases = {}
    all_phases = set(list(curr_groups.keys()) + list(prev_groups.keys()))
    for p in sorted(all_phases):
        curr_stats = _compute_stats(curr_groups.get(p, []))
        prev_stats = _compute_stats(prev_groups.get(p, []))
        phases[p] = _with_delta(curr_stats, prev_stats)

    # Also add from drift intelligence if available
    try:
        from drift.drift_metrics_engine import compute_drift_metrics
        drift_metrics = compute_drift_metrics(
            horizon_days=7, asset=asset, rolling_window_days=RANGE_DAYS.get(range_key, 30)
        )
        if drift_metrics.get("ok"):
            by_regime = drift_metrics.get("by_regime", {})
            for regime_name, stats in by_regime.items():
                key = regime_name.lower()
                if key not in phases:
                    phases[key] = {
                        "n": stats.get("n", 0),
                        "accuracy": {"current": stats.get("accuracy", 0), "previous": 0, "delta": 0},
                        "pnl": {"current": stats.get("pnl", 0), "previous": 0, "delta": 0},
                        "catastrophic_rate": {"current": stats.get("catastrophic_rate", 0), "previous": 0, "delta": 0},
                    }
    except Exception:
        pass

    return {"phases": phases}


# ═══════════════════════════════════════════════════════
# SECTION 3: Regime Performance
# ═══════════════════════════════════════════════════════
def compute_regimes(range_key: str = "30d", asset: str = "BTC"):
    current, prev = _get_evaluated(range_key, asset)

    def _group_by_regime(docs):
        groups = defaultdict(list)
        for d in docs:
            rv2 = (d.get("audit") or {}).get("regimeV2", {})
            dom = (rv2.get("dominant_regime") or "unknown").lower()
            if dom == "unknown":
                regime_str = (d.get("audit") or {}).get("regime", "unknown")
                dom = regime_str.lower() if regime_str else "unknown"
            groups[dom].append(d)
        return groups

    curr_groups = _group_by_regime(current)
    prev_groups = _group_by_regime(prev)

    regimes = {}
    all_regimes = set(list(curr_groups.keys()) + list(prev_groups.keys()))
    for r in sorted(all_regimes):
        curr_stats = _compute_stats(curr_groups.get(r, []))
        prev_stats = _compute_stats(prev_groups.get(r, []))

        # Add entropy/confidence for current
        r_docs = curr_groups.get(r, [])
        avg_entropy = 0
        avg_conf = 0
        if r_docs:
            entropies = [(d.get("audit") or {}).get("regimeV2", {}).get("regime_entropy", 0.5) for d in r_docs]
            confs = [d.get("confidence", 0.5) for d in r_docs]
            avg_entropy = round(sum(entropies) / len(entropies), 3)
            avg_conf = round(sum(confs) / len(confs), 3)

        regimes[r] = {
            **_with_delta(curr_stats, prev_stats),
            "avg_entropy": avg_entropy,
            "avg_confidence": avg_conf,
        }

    # Enrich from drift analysis
    try:
        from drift.drift_metrics_engine import compute_drift_metrics
        drift_metrics = compute_drift_metrics(
            horizon_days=7, asset=asset, rolling_window_days=RANGE_DAYS.get(range_key, 30)
        )
        if drift_metrics.get("ok"):
            by_regime = drift_metrics.get("by_regime", {})
            for name, stats in by_regime.items():
                key = name.lower()
                if key not in regimes or regimes[key].get("n", 0) == 0:
                    regimes[key] = {
                        "n": stats.get("n", 0),
                        "accuracy": {"current": stats.get("accuracy", 0), "previous": 0, "delta": 0},
                        "pnl": {"current": stats.get("pnl", 0), "previous": 0, "delta": 0},
                        "catastrophic_rate": {"current": stats.get("catastrophic_rate", 0), "previous": 0, "delta": 0},
                        "avg_error": stats.get("avg_error", 0),
                        "avg_entropy": 0,
                        "avg_confidence": 0,
                    }
    except Exception:
        pass

    return {"regimes": regimes}


# ═══════════════════════════════════════════════════════
# SECTION 4: Scenario Engine
# ═══════════════════════════════════════════════════════
def compute_scenarios(range_key: str = "30d", asset: str = "BTC"):
    current, prev = _get_evaluated(range_key, asset)

    def _scenario_stats(docs):
        with_scenario = [d for d in docs if (d.get("audit") or {}).get("scenarioResult")]
        n = len(docs)
        coverage = round(len(with_scenario) / n, 3) if n else 0

        if not with_scenario:
            return {"coverage": coverage, "n": n, "direction_accuracy": 0, "pnl": 0, "catastrophic_rate": 0}

        dir_match = sum(1 for d in with_scenario if d.get("outcome", {}).get("hit"))
        cat = sum(1 for d in with_scenario if abs(d.get("outcome", {}).get("errorPct", 0) or 0) > 10)
        pnl = sum(d.get("outcome", {}).get("realMovePct", 0) or 0 for d in with_scenario)

        return {
            "coverage": coverage,
            "n": n,
            "scenario_cases": len(with_scenario),
            "direction_accuracy": round(dir_match / len(with_scenario), 3) if with_scenario else 0,
            "pnl": round(pnl, 2),
            "catastrophic_rate": round(cat / len(with_scenario), 3) if with_scenario else 0,
        }

    curr = _scenario_stats(current)
    prev_s = _scenario_stats(prev)

    return {
        "scenarios": _with_delta(curr, prev_s, keys=["coverage", "direction_accuracy", "pnl", "catastrophic_rate"]),
    }


# ═══════════════════════════════════════════════════════
# SECTION 5: Drift Intelligence
# ═══════════════════════════════════════════════════════
def compute_drift(range_key: str = "30d", asset: str = "BTC"):
    try:
        from drift.drift_metrics_engine import compute_drift_metrics
        from drift.drift_detector import detect_drift
        from drift.drift_analysis import (
            analyze_root_causes,
            compute_drift_score as compute_intelligence_score,
            generate_recommendations,
        )

        window = RANGE_DAYS.get(range_key, 30)
        metrics = compute_drift_metrics(horizon_days=7, asset=asset, rolling_window_days=window)
        if not metrics.get("ok"):
            return {"drift_score": 0, "level": "unknown", "error": "No drift data"}

        drift_result = detect_drift(metrics)
        root_causes = analyze_root_causes(drift_result["drift_zones"], metrics)
        drift_score_data = compute_intelligence_score(metrics, drift_result)
        recommendations = generate_recommendations(
            drift_result["drift_zones"], root_causes, drift_score_data, metrics
        )

        # Extract top issues with impact
        top_issues = []
        by_regime = metrics.get("by_regime", {})
        for name, stats in by_regime.items():
            if stats.get("n", 0) >= 3:
                acc = stats.get("accuracy", 0)
                cat = stats.get("catastrophic_rate", 0)
                if acc < 0.3 or cat > 0.2:
                    top_issues.append({
                        "type": "regime_drift",
                        "zone": name,
                        "accuracy": round(acc, 3),
                        "catastrophic_rate": round(cat, 3),
                        "cases": stats.get("n", 0),
                        "pnl_impact": round(stats.get("pnl", 0), 2),
                    })

        top_issues.sort(key=lambda x: x.get("accuracy", 1))

        return {
            "drift_score": drift_score_data.get("score", 0),
            "level": drift_score_data.get("level", "unknown"),
            "has_drift": drift_result.get("has_drift", False),
            "top_issues": top_issues[:5],
            "recommendations": recommendations,
            "global_metrics": metrics.get("global", {}),
        }
    except Exception as e:
        return {"drift_score": 0, "level": "unknown", "error": str(e)}


# ═══════════════════════════════════════════════════════
# SECTION 6: Tactical + Execution Impact
# ═══════════════════════════════════════════════════════
def compute_tactical(range_key: str = "30d", asset: str = "BTC"):
    try:
        db_inst = _db()
        days = RANGE_DAYS.get(range_key, 30)
        cutoff_ms = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days)

        # Count observations
        obs_col = db_inst["exchange_observations"]
        # Block 7.2: use asset field with fallback to symbol
        obs_query = {"createdAt": {"$gte": cutoff_ms}}
        obs_query["$or"] = [{"asset": asset}, {"symbol": f"{asset}USDT"}]
        obs_count = obs_col.count_documents(obs_query)

        # Get tactical audits
        tactical_col = db_inst["tactical_audit"]
        audits = list(tactical_col.find(
            {"timestamp": {"$gte": cutoff_dt}},
            {"_id": 0, "advice": 1, "fusion": 1}
        ).limit(500))

        bias_dist = {"bullish": 0, "bearish": 0, "neutral": 0}
        advice_dist = {"normal": 0, "reduced": 0, "wait": 0, "avoid_aggressive": 0}
        strengths = []

        for a in audits:
            adv = a.get("advice", {})
            bias = adv.get("tactical_bias", "neutral")
            exec_adv = adv.get("execution_advice", "normal")
            bias_dist[bias] = bias_dist.get(bias, 0) + 1
            advice_dist[exec_adv] = advice_dist.get(exec_adv, 0) + 1
            strengths.append(a.get("fusion", {}).get("signal_strength", 0))

        n = max(len(audits), 1)
        bias_dist = {k: round(v / n, 3) for k, v in bias_dist.items()}
        advice_dist = {k: round(v / n, 3) for k, v in advice_dist.items()}

        caution_cases = advice_dist.get("reduced", 0) + advice_dist.get("wait", 0) + advice_dist.get("avoid_aggressive", 0)
        normal_cases = advice_dist.get("normal", 0)
        caution_ratio = round(caution_cases / normal_cases, 2) if normal_cases > 0 else 0

        avg_strength = round(sum(strengths) / len(strengths), 3) if strengths else 0

        return {
            "observations": obs_count,
            "audits": len(audits),
            "bias_distribution": bias_dist,
            "advice_distribution": advice_dist,
            "caution_ratio": caution_ratio,
            "avg_signal_strength": avg_strength,
            "impact": {
                "avg_size_reduction": round(1 - (bias_dist.get("neutral", 0) * 1.0 + bias_dist.get("bearish", 0) * 0.6 + bias_dist.get("bullish", 0) * 1.0), 3),
            },
        }
    except Exception as e:
        return {"error": str(e), "observations": 0, "audits": 0}


# ═══════════════════════════════════════════════════════
# AGGREGATOR: All sections in one call
# ═══════════════════════════════════════════════════════
def compute_full_console(range_key: str = "30d", asset: str = "BTC"):
    # ML dataset status (independent of range)
    ml_dataset = {}
    try:
        from ml_overlay.dataset_status import compute_dataset_status
        ml_dataset = compute_dataset_status(asset=asset)
    except Exception:
        pass

    return {
        "overview": compute_overview(range_key, asset),
        "phases": compute_phases(range_key, asset),
        "regimes": compute_regimes(range_key, asset),
        "scenarios": compute_scenarios(range_key, asset),
        "drift": compute_drift(range_key, asset),
        "tactical": compute_tactical(range_key, asset),
        "ml_dataset": ml_dataset,
        "range": range_key,
        "asset": asset,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
