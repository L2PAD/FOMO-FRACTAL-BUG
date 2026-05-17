"""
Engine Integration — Phase 13: Unified Decision Engine
========================================================
Aggregates ALL intelligence modules into a single market decision:
  - Entities Intelligence (behaviour, flows, holdings, clusters, discovery)
  - Smart Money Radar (signals, conviction, capital)
  - Token Intelligence (regime, patterns, positioning)
  - CEX Flow Intelligence (pressure, liquidity, stablecoin)

Composite Score = 0.35 * smart_money + 0.30 * cex + 0.20 * entities + 0.15 * token

Output: Decision (BUY/SELL/NEUTRAL), Confidence, Setup, Window, Drivers, Risks, Signals
"""

import time
import os
from pymongo import MongoClient

_client = None
_db = None


def _get_db():
    global _client, _db
    if _db is None:
        _client = MongoClient(os.environ.get("MONGO_URL"))
        _db = _client[os.environ.get("DB_NAME", "test_database")]
    return _db


_cache: dict = {}
_CACHE_TTL = 120


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and time.time() - entry["ts"] < _CACHE_TTL:
        return entry["data"]
    return None


def _cache_set(key: str, data):
    _cache[key] = {"data": data, "ts": time.time()}


def _clamp(v: float, lo: float = 0, hi: float = 100) -> int:
    return int(max(lo, min(hi, round(v))))


def _fmt_usd(v: float) -> str:
    a = abs(v)
    if a >= 1e9:
        return f"${a / 1e9:.1f}B"
    if a >= 1e6:
        return f"${a / 1e6:.1f}M"
    if a >= 1e3:
        return f"${a / 1e3:.1f}K"
    return f"${a:.0f}"


# ══════════════════════════════════════════════════════════
#  WEIGHTS
# ══════════════════════════════════════════════════════════

WEIGHTS = {
    "smart_money": 0.35,
    "cex": 0.30,
    "entities": 0.20,
    "token": 0.15,
}


# ══════════════════════════════════════════════════════════
#  ENTITIES SCORE ENGINE
# ══════════════════════════════════════════════════════════

def _fetch_entities_context() -> dict:
    """Fetch and aggregate entities intelligence from MongoDB, including Actor Intelligence Layer."""
    db = _get_db()

    # Base data
    behaviours = list(db["entity_behaviour_v2"].find({}, {"_id": 0}).limit(50))
    flows = list(db["entity_flows_v2"].find({}, {"_id": 0}).limit(50))
    clusters = list(db["entity_clusters_v2"].find({}, {"_id": 0}).limit(100))
    candidates = list(db["entity_discovery_v2"].find({}, {"_id": 0}).sort("discovery_score", -1).limit(20))
    similarities = list(db["entity_similarity_v2"].find({}, {"_id": 0}).limit(50))
    holdings = list(db["entity_holdings_v2"].find({}, {"_id": 0}).limit(50))
    chains = list(db["entity_chains_v2"].find({}, {"_id": 0}).limit(50))

    # Actor Intelligence Layer — pressure map + actor flows
    actor_intelligence = {}
    try:
        from entities_v2.actor_intelligence_service import get_pressure_map, get_actor_flows
        actor_intelligence["pressure_map"] = get_pressure_map()
        actor_intelligence["actor_flows"] = get_actor_flows()
    except Exception:
        actor_intelligence["pressure_map"] = {"bullish_entities": [], "bearish_entities": [], "neutral_entities": []}
        actor_intelligence["actor_flows"] = {"interactions": []}

    return {
        "behaviours": behaviours,
        "flows": flows,
        "clusters": clusters,
        "candidates": candidates,
        "similarities": similarities,
        "holdings": holdings,
        "chains": chains,
        "actor_intelligence": actor_intelligence,
    }


def _compute_entities_score(ent_ctx: dict) -> tuple:
    """
    Entities Score (0-100) from:
      - behaviour_coherence: avg confidence of classified behaviours
      - capital_activity: flow volume and direction signals
      - cluster_coverage: how much market is covered by clusters
      - discovery_quality: quality score of discovered entities
      - actor_pressure: bullish/bearish actor balance (V4)
      - actor_impact: systemic/high impact actor count (V4)
    """
    drivers = []
    components = {}

    behaviours = ent_ctx.get("behaviours", [])
    flows = ent_ctx.get("flows", [])
    clusters = ent_ctx.get("clusters", [])
    candidates = ent_ctx.get("candidates", [])
    holdings = ent_ctx.get("holdings", [])
    ai = ent_ctx.get("actor_intelligence", {})
    pm = ai.get("pressure_map", {})

    # 1) Behaviour Coherence
    if behaviours:
        confidences = [b.get("confidence", 0) for b in behaviours if b.get("confidence", 0) > 0]
        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            behaviour_score = _clamp(avg_conf * 100)
            types_seen = set(b.get("behaviour_type", "unknown") for b in behaviours)
            if len(types_seen) >= 3:
                behaviour_score = _clamp(behaviour_score + 10)
                drivers.append(f"{len(types_seen)} distinct behaviour types detected")
        else:
            behaviour_score = 40
    else:
        behaviour_score = 30
    components["behaviour_coherence"] = behaviour_score

    # 2) Capital Activity
    if flows:
        total_volume = sum(f.get("all_time", {}).get("volume_usd", 0) for f in flows)
        import math
        if total_volume > 0:
            log_vol = math.log10(max(total_volume, 1))
            activity_score = _clamp(log_vol * 12)
        else:
            activity_score = 30
        if total_volume > 100_000:
            drivers.append(f"Entity capital volume {_fmt_usd(total_volume)}")
    else:
        activity_score = 30
    components["capital_activity"] = activity_score

    # 3) Cluster Coverage
    if clusters:
        total_wallets = sum(c.get("cluster_size", 0) for c in clusters)
        avg_confidence = sum(c.get("confidence", 0) for c in clusters) / len(clusters)
        coverage_score = _clamp(min(total_wallets / 5, 100) * 0.5 + avg_confidence * 100 * 0.5)
        if total_wallets > 50:
            drivers.append(f"{total_wallets} wallets in entity clusters")
    else:
        coverage_score = 30
    components["cluster_coverage"] = coverage_score

    # 4) Discovery Quality
    if candidates:
        avg_disc_score = sum(c.get("discovery_score", 0) for c in candidates) / len(candidates)
        discovery_score = _clamp(avg_disc_score * 100)
        high_quality = sum(1 for c in candidates if c.get("discovery_score", 0) >= 0.7)
        if high_quality >= 2:
            drivers.append(f"{high_quality} high-quality entity candidates")
    else:
        discovery_score = 40
    components["discovery_quality"] = discovery_score

    # 5) Holdings depth
    if holdings:
        with_value = [h for h in holdings if h.get("total_value_usd", 0) > 0]
        holdings_score = _clamp(min(len(with_value) / 3, 1) * 70 + 30)
    else:
        holdings_score = 30
    components["holdings_depth"] = holdings_score

    # 6) V4: Actor Pressure Intelligence
    bullish = pm.get("bullish_entities", [])
    bearish = pm.get("bearish_entities", [])
    b_count = len(bullish)
    r_count = len(bearish)
    total_pressure_entities = b_count + r_count + len(pm.get("neutral_entities", []))

    if total_pressure_entities > 0:
        # Systemic/High impact actors amplify pressure signal
        b_systemic = sum(1 for e in bullish if e.get("impact") in ("SYSTEMIC", "HIGH"))
        r_systemic = sum(1 for e in bearish if e.get("impact") in ("SYSTEMIC", "HIGH"))

        if b_count > r_count:
            pressure_score = _clamp(60 + b_systemic * 10)
            drivers.append(f"{b_count} bullish actors ({b_systemic} high-impact)")
        elif r_count > b_count:
            pressure_score = _clamp(40 - r_systemic * 10)
            drivers.append(f"{r_count} bearish actors ({r_systemic} high-impact)")
        else:
            pressure_score = 50
    else:
        pressure_score = 50
    components["actor_pressure"] = pressure_score

    # Aggregate: V4 weights include actor pressure
    score = _clamp(
        behaviour_score * 0.22 +
        activity_score * 0.20 +
        coverage_score * 0.15 +
        discovery_score * 0.10 +
        holdings_score * 0.08 +
        pressure_score * 0.25  # V4: actor pressure is significant
    )

    return score, drivers, components


def _compress_entities_context(ent_ctx: dict) -> dict:
    """Compress entities data for context matrix (V4: includes actor intelligence)."""
    behaviours = ent_ctx.get("behaviours", [])
    flows = ent_ctx.get("flows", [])
    clusters = ent_ctx.get("clusters", [])
    candidates = ent_ctx.get("candidates", [])
    ai = ent_ctx.get("actor_intelligence", {})
    pm = ai.get("pressure_map", {})
    af = ai.get("actor_flows", {})

    # Dominant behaviour
    type_counts = {}
    for b in behaviours:
        t = b.get("behaviour_type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    dominant = max(type_counts, key=type_counts.get) if type_counts else "unknown"

    total_volume = sum(f.get("all_time", {}).get("volume_usd", 0) for f in flows)
    total_wallets = sum(c.get("cluster_size", 0) for c in clusters)

    # V4: Actor pressure summary
    bullish = pm.get("bullish_entities", [])
    bearish = pm.get("bearish_entities", [])
    pressure_balance = "bullish" if len(bullish) > len(bearish) else "bearish" if len(bearish) > len(bullish) else "neutral"

    top_bullish = [{"name": e.get("name"), "impact": e.get("impact")} for e in bullish[:3]]
    top_bearish = [{"name": e.get("name"), "impact": e.get("impact")} for e in bearish[:3]]

    return {
        "entity_count": len(behaviours),
        "dominant_behaviour": dominant,
        "total_volume": round(total_volume, 2),
        "total_volume_fmt": _fmt_usd(total_volume),
        "cluster_wallets": total_wallets,
        "discovery_candidates": len(candidates),
        "behaviour_types": dict(type_counts),
        "pressure_balance": pressure_balance,
        "bullish_actors": len(bullish),
        "bearish_actors": len(bearish),
        "top_bullish": top_bullish,
        "top_bearish": top_bearish,
        "actor_interactions": af.get("total_interactions", 0),
    }


# ══════════════════════════════════════════════════════════
#  SIGNAL LIFECYCLE ENGINE
# ══════════════════════════════════════════════════════════

def _classify_signal_phase(signal_age_h: float, confirmation_count: int) -> str:
    """
    Determine signal lifecycle phase:
      Detected → Confirmed → Expansion → Exhaustion
    """
    if confirmation_count >= 3 and signal_age_h >= 24:
        return "exhaustion"
    if confirmation_count >= 2 and signal_age_h >= 8:
        return "expansion"
    if confirmation_count >= 1 and signal_age_h >= 2:
        return "confirmed"
    return "detected"


def _build_signal_feed(market_ctx: dict, ent_ctx: dict) -> list:
    """Build temporal signal feed from all modules (V4: includes actor intelligence)."""
    signals = []
    ts = time.time()

    # V4: Actor Intelligence signals (highest priority)
    ai = ent_ctx.get("actor_intelligence", {})
    pm = ai.get("pressure_map", {})
    for e in pm.get("bullish_entities", [])[:3]:
        if e.get("impact") in ("SYSTEMIC", "HIGH"):
            signals.append({
                "type": "actor_bullish",
                "source": "entities",
                "description": f"{e['name']}: Bullish pressure ({e['impact']} impact, {e.get('strategy', 'mixed')})",
                "confidence": 0.85 if e["impact"] == "SYSTEMIC" else 0.75,
                "phase": "confirmed",
                "age_h": 1.0,
            })
    for e in pm.get("bearish_entities", [])[:3]:
        if e.get("impact") in ("SYSTEMIC", "HIGH"):
            signals.append({
                "type": "actor_bearish",
                "source": "entities",
                "description": f"{e['name']}: Bearish pressure ({e['impact']} impact, {e.get('strategy', 'mixed')})",
                "confidence": 0.85 if e["impact"] == "SYSTEMIC" else 0.75,
                "phase": "confirmed",
                "age_h": 1.0,
            })

    # Entity-derived signals
    behaviours = ent_ctx.get("behaviours", [])
    for b in behaviours:
        if b.get("confidence", 0) >= 0.6:
            btype = b.get("behaviour_type", "unknown")
            entity = b.get("entity_slug", "unknown")
            age_h = (ts - b.get("computed_at_ts", ts - 3600)) / 3600 if b.get("computed_at_ts") else 6
            conf_count = 2 if b.get("confidence", 0) >= 0.8 else 1
            signals.append({
                "type": f"entity_{btype}",
                "source": "entities",
                "description": f"{entity}: {btype} (conf {b.get('confidence', 0):.0%})",
                "confidence": round(b.get("confidence", 0), 2),
                "phase": _classify_signal_phase(age_h, conf_count),
                "age_h": round(age_h, 1),
            })

    candidates = ent_ctx.get("candidates", [])
    for c in candidates[:3]:
        if c.get("discovery_score", 0) >= 0.7:
            signals.append({
                "type": "new_actor_discovered",
                "source": "entities",
                "description": f"New {c.get('candidate_type', 'unknown')}: {c.get('cluster_id', '?')} (score {c.get('discovery_score', 0):.0%})",
                "confidence": round(c.get("discovery_score", 0), 2),
                "phase": "detected",
                "age_h": 1.0,
            })

    # Smart Money signals
    sm_signals = market_ctx.get("signals", {}).get("smart_money", [])
    for i, s in enumerate(sm_signals[:5]):
        signals.append({
            "type": "smart_money_signal",
            "source": "smart_money",
            "description": s if isinstance(s, str) else str(s),
            "confidence": 0.7 - i * 0.05,
            "phase": _classify_signal_phase(4 + i * 2, 2 - min(i, 1)),
            "age_h": 4 + i * 2,
        })

    # CEX signals
    cex_signals = market_ctx.get("signals", {}).get("cex", [])
    for i, s in enumerate(cex_signals[:5]):
        signals.append({
            "type": "cex_signal",
            "source": "cex",
            "description": s if isinstance(s, str) else str(s),
            "confidence": 0.75 - i * 0.05,
            "phase": _classify_signal_phase(3 + i * 3, 2),
            "age_h": 3 + i * 3,
        })

    # Token signals
    token_signals = market_ctx.get("signals", {}).get("token", [])
    for i, s in enumerate(token_signals[:3]):
        signals.append({
            "type": "token_signal",
            "source": "token",
            "description": s if isinstance(s, str) else str(s),
            "confidence": 0.65 - i * 0.05,
            "phase": _classify_signal_phase(6 + i * 4, 1),
            "age_h": 6 + i * 4,
        })

    # Sort by confidence desc
    signals.sort(key=lambda x: x["confidence"], reverse=True)
    return signals[:20]


# ══════════════════════════════════════════════════════════
#  DECISION GATES
# ══════════════════════════════════════════════════════════

def _evidence_gate(scores: dict) -> dict:
    """Gate 1: Do enough modules agree on the direction?"""
    composite = scores.get("composite", 50)
    is_bullish = composite >= 55

    modules_agreeing = 0
    verdicts = {}

    for name in ["smart_money", "cex", "entities", "token"]:
        s = scores.get(f"{name}_score", 50)
        if is_bullish and s >= 55:
            modules_agreeing += 1
            verdicts[name] = "supports"
        elif not is_bullish and s <= 45:
            modules_agreeing += 1
            verdicts[name] = "supports"
        elif 45 < s < 55:
            verdicts[name] = "neutral"
        else:
            verdicts[name] = "contradicts"

    if modules_agreeing >= 3:
        status = "PASS"
    elif modules_agreeing >= 2:
        status = "PASS"
    elif modules_agreeing == 1:
        status = "WEAK"
    else:
        status = "FAIL"

    return {
        "status": status,
        "modules_agreeing": modules_agreeing,
        "total_modules": 4,
        "verdicts": verdicts,
    }


def _risk_gate(scores: dict, market_ctx: dict, ent_ctx: dict) -> dict:
    """Gate 2: Are there factors that break the signal?"""
    risk_factors = []

    ctx = market_ctx.get("context", {})
    cex_ctx = ctx.get("cex", {})
    wallet_ctx = ctx.get("wallet", {})

    # CEX contradictions
    if cex_ctx.get("pressure_bias") == "bearish" and scores.get("cex_score", 50) >= 55:
        risk_factors.append("Exchange deposit pressure contradicts bullish signal")
    if cex_ctx.get("inventory_state") == "growing":
        risk_factors.append("Exchange inventory growing — supply increasing")

    # Wallet weakness
    if wallet_ctx.get("active_actors", 0) < 3:
        risk_factors.append("Wallet participation narrow — few active smart actors")

    # Entity-specific risks
    behaviours = ent_ctx.get("behaviours", [])
    dist_count = sum(1 for b in behaviours if b.get("behaviour_type") == "distribution")
    accum_count = sum(1 for b in behaviours if b.get("behaviour_type") == "accumulation")
    if dist_count > accum_count and scores.get("composite", 50) >= 55:
        risk_factors.append("Entity distribution > accumulation — contradicts bullish bias")

    # V4: Actor pressure contradictions
    ai = ent_ctx.get("actor_intelligence", {})
    pm = ai.get("pressure_map", {})
    bullish_count = len(pm.get("bullish_entities", []))
    bearish_count = len(pm.get("bearish_entities", []))
    composite = scores.get("composite", 50)
    if composite >= 55 and bearish_count > bullish_count:
        systemic_bearish = sum(1 for e in pm.get("bearish_entities", []) if e.get("impact") in ("SYSTEMIC", "HIGH"))
        if systemic_bearish > 0:
            risk_factors.append(f"Systemic actors bearish ({systemic_bearish} high-impact) — contradicts bullish composite")
    if composite <= 45 and bullish_count > bearish_count:
        systemic_bullish = sum(1 for e in pm.get("bullish_entities", []) if e.get("impact") in ("SYSTEMIC", "HIGH"))
        if systemic_bullish > 0:
            risk_factors.append(f"Systemic actors bullish ({systemic_bullish} high-impact) — contradicts bearish composite")

    # Module divergence
    score_values = [
        scores.get("smart_money_score", 50), scores.get("cex_score", 50),
        scores.get("entities_score", 50), scores.get("token_score", 50),
    ]
    if max(score_values) - min(score_values) > 40:
        risk_factors.append("High module divergence — conflicting signals across layers")

    # Signal density
    all_signals = market_ctx.get("signals", {})
    total_sigs = sum(len(v) if isinstance(v, list) else 0 for v in all_signals.values())
    if total_sigs < 3:
        risk_factors.append("Low signal density — insufficient market activity")

    if len(risk_factors) >= 3:
        level = "HIGH"
    elif len(risk_factors) >= 1:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "status": level,
        "factors": risk_factors[:5],
        "count": len(risk_factors),
    }


def _coverage_gate(market_ctx: dict, ent_ctx: dict) -> dict:
    """Gate 3: Is data coverage sufficient?"""
    issues = []
    ctx = market_ctx.get("context", {})

    # Smart Money coverage
    sm = ctx.get("smart_money", {})
    if sm.get("signal_count", 0) == 0:
        issues.append("No smart money signals detected")

    # CEX coverage
    cex = ctx.get("cex", {})
    if cex.get("liquidity_shock") == "neutral" and cex.get("pressure_bias") == "neutral":
        issues.append("CEX data shows no directional signals")

    # Token coverage
    token = ctx.get("token", {})
    if token.get("token_count", 0) == 0:
        issues.append("No token intelligence data available")

    # Entities coverage
    behaviours = ent_ctx.get("behaviours", [])
    if len(behaviours) == 0:
        issues.append("No entity behaviour data available")
    clusters = ent_ctx.get("clusters", [])
    if len(clusters) == 0:
        issues.append("No entity clusters available")

    if len(issues) >= 3:
        level = "LOW"
    elif len(issues) >= 1:
        level = "PARTIAL"
    else:
        level = "FULL"

    return {
        "status": level,
        "issues": issues[:5],
        "missing_count": len(issues),
    }


# ══════════════════════════════════════════════════════════
#  DECISION ENGINE
# ══════════════════════════════════════════════════════════

def _classify_decision(composite: int, gates: dict) -> str:
    """Composite → BUY / SELL / NEUTRAL with gate modifiers."""
    if composite >= 65:
        decision = "BUY"
    elif composite <= 40:
        decision = "SELL"
    else:
        decision = "NEUTRAL"

    evidence = gates.get("evidence", {}).get("status", "PASS")
    risk = gates.get("risk", {}).get("status", "LOW")
    coverage = gates.get("coverage", {}).get("status", "FULL")

    # Evidence gate: FAIL → force NEUTRAL
    if evidence == "FAIL":
        decision = "NEUTRAL"
    elif evidence == "WEAK" and decision == "BUY":
        decision = "NEUTRAL"

    # Risk gate: HIGH → downgrade
    if risk == "HIGH":
        downgrades = {"BUY": "NEUTRAL", "SELL": "NEUTRAL"}
        decision = downgrades.get(decision, decision)

    # Coverage LOW → NEUTRAL
    if coverage == "LOW":
        decision = "NEUTRAL"

    return decision


# ══════════════════════════════════════════════════════════
#  CONFIDENCE ENGINE
# ══════════════════════════════════════════════════════════

def _compute_confidence(scores: dict, gates: dict) -> dict:
    """confidence = evidence + coverage - risk"""
    evidence = gates.get("evidence", {})
    risk = gates.get("risk", {})
    coverage = gates.get("coverage", {})

    # Evidence contribution (0-50)
    agreement = (evidence.get("modules_agreeing", 0) / 4) * 50

    # Coverage contribution (0-30)
    coverage_bonus = {"FULL": 30, "PARTIAL": 15, "LOW": 0}.get(coverage.get("status", "FULL"), 0)

    # Risk penalty (0-30)
    risk_penalty = {"LOW": 0, "MEDIUM": 15, "HIGH": 30}.get(risk.get("status", "LOW"), 0)

    # Variance penalty
    score_values = [
        scores.get("smart_money_score", 50), scores.get("cex_score", 50),
        scores.get("entities_score", 50), scores.get("token_score", 50),
    ]
    variance = max(score_values) - min(score_values)
    variance_penalty = min(15, variance * 0.3)

    raw = agreement + coverage_bonus - risk_penalty - variance_penalty
    conf_score = _clamp(raw)

    if conf_score >= 70:
        level = "HIGH"
    elif conf_score >= 45:
        level = "MODERATE"
    elif conf_score >= 20:
        level = "LOW"
    else:
        level = "INSUFFICIENT"

    return {
        "level": level,
        "score": conf_score,
        "factors": {
            "evidence": round(agreement),
            "coverage": coverage_bonus,
            "risk_penalty": round(risk_penalty),
            "variance_penalty": round(variance_penalty),
        },
    }


# ══════════════════════════════════════════════════════════
#  SETUP CLASSIFIER
# ══════════════════════════════════════════════════════════

def _classify_setup(market_ctx: dict, ent_ctx: dict, composite: int) -> dict:
    """Classify market setup type."""
    ctx = market_ctx.get("context", {})
    cex = ctx.get("cex", {})
    token = ctx.get("token", {})
    sm = ctx.get("smart_money", {})

    shock = cex.get("liquidity_shock", "neutral")
    regime = token.get("regime", "neutral")
    conviction = sm.get("conviction", 0)

    # Entity behaviour context
    behaviours = ent_ctx.get("behaviours", [])
    accum_entities = sum(1 for b in behaviours if b.get("behaviour_type") == "accumulation")
    dist_entities = sum(1 for b in behaviours if b.get("behaviour_type") == "distribution")
    lp_entities = sum(1 for b in behaviours if b.get("behaviour_type") == "liquidity_provision")

    # Liquidity Shock (highest priority)
    if "bullish" in shock:
        return {"type": "Liquidity Shock", "bias": "bullish", "description": "Buy-side liquidity imbalance detected across exchanges"}
    if "bearish" in shock:
        return {"type": "Liquidity Shock", "bias": "bearish", "description": "Sell-side liquidity imbalance detected across exchanges"}

    # Accumulation (entity-enhanced)
    if accum_entities >= 2 and composite >= 55:
        return {"type": "Accumulation", "bias": "bullish", "description": f"{accum_entities} entities in accumulation mode — capital inflow confirmed"}

    if regime == "accumulation" and conviction >= 60:
        return {"type": "Accumulation", "bias": "bullish", "description": "Token regime accumulation with strong smart money conviction"}

    # Distribution
    if dist_entities >= 2 and composite <= 45:
        return {"type": "Distribution", "bias": "bearish", "description": f"{dist_entities} entities distributing — capital outflow confirmed"}

    if regime == "distribution" and composite <= 45:
        return {"type": "Distribution", "bias": "bearish", "description": "Token regime distribution phase, composite confirms bearish bias"}

    # Breakout Setup
    inventory = cex.get("inventory_state", "stable")
    if inventory == "shrinking" and conviction >= 50 and composite >= 60:
        return {"type": "Breakout Setup", "bias": "bullish", "description": "Exchange inventory shrinking + conviction = potential breakout"}

    # Rotation
    if lp_entities >= 2 and 45 <= composite <= 60:
        return {"type": "Rotation", "bias": "neutral", "description": "Liquidity provision entities active — capital rotating"}

    return {"type": "Neutral Market", "bias": "neutral", "description": "No clear setup detected — market in equilibrium"}


# ══════════════════════════════════════════════════════════
#  WINDOW ESTIMATOR
# ══════════════════════════════════════════════════════════

def _estimate_window(setup: dict, confidence: dict) -> str:
    setup_type = setup.get("type", "Neutral Market")
    conf_level = confidence.get("level", "LOW")
    windows = {
        "Liquidity Shock": {"HIGH": "2-8h", "MODERATE": "4-12h", "LOW": "6-24h"},
        "Accumulation": {"HIGH": "6-18h", "MODERATE": "12-36h", "LOW": "24-72h"},
        "Distribution": {"HIGH": "6-18h", "MODERATE": "12-36h", "LOW": "24-72h"},
        "Breakout Setup": {"HIGH": "4-12h", "MODERATE": "8-24h", "LOW": "12-48h"},
        "Rotation": {"HIGH": "12-36h", "MODERATE": "24-72h", "LOW": "48h+"},
        "Neutral Market": {"HIGH": "24h+", "MODERATE": "48h+", "LOW": "—"},
    }
    return windows.get(setup_type, {}).get(conf_level, "—")


# ══════════════════════════════════════════════════════════
#  DRIVER AGGREGATION
# ══════════════════════════════════════════════════════════

def _build_drivers(market_drivers: list, entity_drivers: list) -> list:
    """Aggregate drivers from all modules."""
    all_d = []
    for d in entity_drivers:
        all_d.append({"source": "entities", "text": d})
    for d in market_drivers:
        all_d.append({"source": "market", "text": d})
    return all_d[:12]


def _build_module_drivers(market_ctx: dict, entity_drivers: list) -> dict:
    """Build per-module driver lists."""
    all_drivers = market_ctx.get("drivers", [])

    sm_drivers = [d for d in all_drivers if "smart" in d.lower() or "actor" in d.lower() or "conviction" in d.lower() or "inflow" in d.lower()]
    cex_drivers = [d for d in all_drivers if "exchange" in d.lower() or "stable" in d.lower() or "deposit" in d.lower() or "withdraw" in d.lower() or "liquidity" in d.lower() or "inventory" in d.lower() or "pressure" in d.lower()]
    token_drivers = [d for d in all_drivers if "token" in d.lower() or "regime" in d.lower() or "positioning" in d.lower() or "buy-side" in d.lower()]

    # Fallback: any unclassified drivers go to market
    classified = set(sm_drivers + cex_drivers + token_drivers)
    other = [d for d in all_drivers if d not in classified]
    if other:
        sm_drivers.extend(other[:1])

    return {
        "entities": entity_drivers[:4],
        "smart_money": sm_drivers[:4],
        "cex": cex_drivers[:4],
        "token": token_drivers[:4],
    }


# ══════════════════════════════════════════════════════════
#  RISK ENGINE
# ══════════════════════════════════════════════════════════

def _build_risks(gates: dict) -> list:
    return list(gates.get("risk", {}).get("factors", []))[:6]


def _compute_otc_mm_influence(otc_trades: list, mm_list: list, setup_engine: dict) -> dict:
    """E3: Compute how OTC and Market Maker activity influences the engine."""
    otc_bias = "neutral"
    mm_presence = len(mm_list) > 0
    conf_adj = 0
    risk_adj = 0
    drivers = []

    # OTC influence
    if otc_trades:
        # Determine if OTC is buy or sell biased
        buy_signals = sum(1 for t in otc_trades if t.get("direction") == "buy" or t.get("confidence", 0) > 0.5)
        sell_signals = sum(1 for t in otc_trades if t.get("direction") == "sell")
        if buy_signals > sell_signals:
            otc_bias = "bullish"
            conf_adj += min(len(otc_trades) * 2, 6)
            drivers.append(f"OTC buy activity detected ({len(otc_trades)} trades)")
        elif sell_signals > buy_signals:
            otc_bias = "bearish"
            conf_adj -= min(len(otc_trades) * 2, 6)
            drivers.append(f"OTC sell activity detected ({len(otc_trades)} trades)")
        else:
            # Default: OTC activity is bullish-neutral (large transfers = accumulation signal)
            otc_bias = "bullish"
            conf_adj += min(len(otc_trades), 3)
            drivers.append(f"OTC transfers detected — {len(otc_trades)} trades")

    # MM influence
    if mm_presence:
        avg_score = sum(m.get("score", 0) for m in mm_list) / len(mm_list)
        if avg_score >= 0.7:
            risk_adj += 8
            drivers.append(f"Confirmed market maker activity (score {avg_score:.0%}) — increases variance")
        elif avg_score >= 0.5:
            risk_adj += 4
            drivers.append(f"Probable market maker presence (score {avg_score:.0%}) — moderate variance")
        else:
            risk_adj += 2
            drivers.append("Market maker signals present — slight variance increase")

    # Check alignment with setup
    setup_type = setup_engine.get("primary", {}).get("type", "mixed")
    if otc_bias == "bullish" and setup_type in ("smart_money_accumulation", "liquidity_shock"):
        conf_adj += 3
        drivers.append("OTC aligns with bullish setup — reinforcing signal")
    elif otc_bias == "bearish" and setup_type == "distribution_risk":
        conf_adj += 3
        drivers.append("OTC aligns with distribution setup — reinforcing signal")

    return {
        "otc_bias": otc_bias,
        "mm_presence": mm_presence,
        "confidence_adjustment": conf_adj,
        "risk_adjustment": risk_adj,
        "drivers": drivers,
    }


# ══════════════════════════════════════════════════════════
#  DECISION EXPLANATION LAYER (E1)
# ══════════════════════════════════════════════════════════

def _build_decision_explanation(
    decision: str,
    scores: dict,
    gates: dict,
    setup: dict,
    confidence: dict,
    market_ctx: dict,
    ent_ctx: dict,
) -> dict:
    """
    Build structured explanation for the current decision:
      - bullish_drivers: what supports the trade
      - bearish_or_contradictions: what opposes the setup
      - decision_blockers: why decision isn't upgrading
      - upgrade_triggers: what must happen for upgrade
    """
    bullish = []
    bearish = []
    blockers = []
    triggers = []

    ctx = market_ctx.get("context", {})
    cex = ctx.get("cex", {})
    sm = ctx.get("smart_money", {})
    token = ctx.get("token", {})

    composite = scores.get("composite", 50)
    sm_score = scores.get("smart_money_score", 50)
    cex_score = scores.get("cex_score", 50)
    ent_score = scores.get("entities_score", 50)
    token_score = scores.get("token_score", 50)

    ai = ent_ctx.get("actor_intelligence", {})
    pm = ai.get("pressure_map", {})

    # ── BULLISH DRIVERS ──
    shock = cex.get("liquidity_shock", "neutral")
    if "bullish" in str(shock):
        bullish.append("Liquidity shock detected across exchanges")

    net_flow = sm.get("net_flow", 0)
    if net_flow > 50_000_000:
        bullish.append(f"Smart money inflow {_fmt_usd(net_flow)}")
    elif net_flow > 10_000_000:
        bullish.append(f"Smart money net positive {_fmt_usd(net_flow)}")

    inv = cex.get("inventory_state", "stable")
    if inv == "shrinking":
        inv_pct = cex.get("inventory_change_pct", 0)
        bullish.append(f"Exchange inventory shrinking ({inv_pct}%)" if inv_pct else "Exchange inventory shrinking")

    regime = token.get("regime", "neutral")
    if regime == "accumulation":
        bullish.append("Token regime: accumulation phase")

    stablecoin = cex.get("stablecoin_bias", "neutral")
    if stablecoin == "buying_power":
        bullish.append("Stablecoin buying power active")

    conviction = sm.get("conviction", 0)
    if conviction >= 60:
        bullish.append(f"Smart money conviction high ({conviction}%)")

    b_actors = pm.get("bullish_entities", [])
    b_high = sum(1 for e in b_actors if e.get("impact") in ("SYSTEMIC", "HIGH"))
    if b_high > 0:
        bullish.append(f"{b_high} high-impact bullish actor{'s' if b_high > 1 else ''}")

    pattern = token.get("pattern", "neutral")
    if "bullish" in str(pattern):
        bullish.append("Token pattern: strong bullish positioning")

    # ── BEARISH / CONTRADICTIONS ──
    if "bearish" in str(shock):
        bearish.append("Bearish liquidity shock detected")

    pressure = cex.get("pressure_bias", "neutral")
    if pressure == "bearish" and composite >= 50:
        bearish.append("Exchange deposit pressure contradicts bullish signal")

    if inv == "growing" and composite >= 50:
        bearish.append("Exchange inventory growing — supply increasing")

    r_actors = pm.get("bearish_entities", [])
    r_high = sum(1 for e in r_actors if e.get("impact") in ("SYSTEMIC", "HIGH"))
    if r_high > 0 and composite >= 50:
        bearish.append(f"{r_high} high-impact bearish actor{'s' if r_high > 1 else ''} opposing setup")

    if regime == "distribution" and composite >= 50:
        bearish.append("Token regime in distribution — contradicts bullish setup")

    behaviours = ent_ctx.get("behaviours", [])
    dist_count = sum(1 for b in behaviours if b.get("behaviour_type") == "distribution")
    accum_count = sum(1 for b in behaviours if b.get("behaviour_type") == "accumulation")
    if dist_count > accum_count and composite >= 50:
        bearish.append(f"Entity distribution ({dist_count}) > accumulation ({accum_count})")

    if net_flow < -50_000_000:
        bearish.append(f"Smart money outflow {_fmt_usd(abs(net_flow))}")

    # Module divergence
    score_vals = [sm_score, cex_score, ent_score, token_score]
    divergence = max(score_vals) - min(score_vals)
    if divergence > 35:
        bearish.append(f"High module divergence ({divergence} pts) — conflicting signals")

    # ── DECISION BLOCKERS ──
    conf_score = confidence.get("score", 0)
    if decision == "NEUTRAL" and composite >= 55:
        if conf_score < 55:
            blockers.append(f"Confidence too low ({conf_score}) to upgrade to BUY")

        evidence_status = gates.get("evidence", {}).get("status", "PASS")
        if evidence_status in ("WEAK", "FAIL"):
            blockers.append(f"Evidence gate {evidence_status} — insufficient module agreement")

        risk_status = gates.get("risk", {}).get("status", "LOW")
        if risk_status == "HIGH":
            blockers.append("Risk gate HIGH — too many contradictory factors")
        elif risk_status == "MEDIUM":
            blockers.append("Risk gate MEDIUM — contradictions present")

        if ent_score < 50:
            blockers.append(f"Entity participation insufficient (score {ent_score})")

        if composite < 65:
            blockers.append(f"Composite {composite} below BUY threshold (65)")

    elif decision == "NEUTRAL" and composite <= 45:
        if conf_score < 55:
            blockers.append(f"Confidence too low ({conf_score}) to downgrade to SELL")
        if composite > 40:
            blockers.append(f"Composite {composite} above SELL threshold (40)")

    elif decision == "NEUTRAL":
        blockers.append("Market in equilibrium — no clear directional signal")

    if not blockers and decision == "NEUTRAL":
        blockers.append("No single factor strong enough to trigger directional decision")

    # ── UPGRADE TRIGGERS ──
    if decision == "NEUTRAL" and composite >= 50:
        if ent_score < 60:
            triggers.append("Entity flows turn strongly bullish (score > 60)")
        if pressure == "bearish":
            triggers.append("Exchange deposit pressure reverses to neutral/bullish")
        if token_score < 70:
            triggers.append(f"Token regime strengthens above 70 (currently {token_score})")
        if conf_score < 55:
            triggers.append("Additional module confirmation raises confidence above 55")
        if conviction < 60:
            triggers.append(f"Smart money conviction rises above 60% (currently {conviction}%)")
        if composite < 65:
            triggers.append(f"Composite crosses 65 threshold (currently {composite})")
    elif decision == "NEUTRAL" and composite < 50:
        if ent_score > 40:
            triggers.append("Entity distribution accelerates (score < 40)")
        if sm_score > 45:
            triggers.append("Smart money turns net seller (score < 45)")
        if composite > 40:
            triggers.append(f"Composite drops below 40 (currently {composite})")
    elif decision == "BUY":
        triggers.append("Maintain: entity and token confirmation holds")
        if risk_status == "MEDIUM":
            triggers.append("Risk resolution would increase confidence")
    elif decision == "SELL":
        triggers.append("Maintain: bearish signals sustained across modules")

    return {
        "bullish_drivers": bullish[:6],
        "bearish_or_contradictions": bearish[:5],
        "decision_blockers": blockers[:4],
        "upgrade_triggers": triggers[:5],
    }


def _build_decision_integrity(gates: dict) -> dict:
    """Condensed integrity status for the hero block."""
    risk_factors = gates.get("risk", {}).get("factors", [])
    return {
        "evidence": gates.get("evidence", {}).get("status", "PASS"),
        "risk": gates.get("risk", {}).get("status", "LOW"),
        "coverage": gates.get("coverage", {}).get("status", "FULL"),
        "primary_blocker": risk_factors[0] if risk_factors else None,
    }


def _build_hero_summary(decision: str, setup: dict, explanation: dict, confidence: dict) -> dict:
    """Build concise hero summary text for the decision terminal."""
    setup_type = setup.get("type", "Neutral Market")
    conf_level = confidence.get("level", "LOW")

    # Build reason line
    if decision == "BUY":
        reason = f"{setup_type} confirmed with {conf_level.lower()} confidence"
    elif decision == "SELL":
        reason = f"{setup_type} bearish — distribution confirmed"
    else:
        bullish = explanation.get("bullish_drivers", [])
        contradictions = explanation.get("bearish_or_contradictions", [])
        if bullish and contradictions:
            reason = f"Constructive {setup_type.lower()} setup, but evidence incomplete"
        elif bullish:
            reason = f"{setup_type} detected, awaiting confirmation"
        else:
            reason = "No clear directional signal — market in equilibrium"

    # Primary blocker
    blockers = explanation.get("decision_blockers", [])
    primary_blocker = blockers[0] if blockers else None

    # Upgrade trigger
    triggers = explanation.get("upgrade_triggers", [])
    primary_trigger = triggers[0] if triggers else None

    return {
        "reason": reason,
        "primary_blocker": primary_blocker,
        "primary_trigger": primary_trigger,
    }


# ══════════════════════════════════════════════════════════
#  MAIN ENTRY
# ══════════════════════════════════════════════════════════

def get_integrated_engine_context(chain_id: int = 1, window: str = "30d") -> dict:
    ck = f"engine_integrated:{chain_id}:{window}"
    cached = _cache_get(ck)
    if cached is not None:
        return cached

    # ── Fetch Market Context (SM + CEX + Token + Wallet) ──
    from market_context.service import get_market_context
    market_ctx = get_market_context(chain_id=chain_id, window=window)

    # ── Fetch Entities Context ──
    ent_ctx = _fetch_entities_context()

    # ── Compute Module Scores ──
    market_scores = market_ctx.get("scores", {})
    sm_score = market_scores.get("smart_money_score", 50)
    cex_score = market_scores.get("cex_score", 50)
    token_score = market_scores.get("token_score", 50)
    entities_score, entity_drivers, entity_components = _compute_entities_score(ent_ctx)

    # ── Composite with NEW weights ──
    composite = _clamp(
        sm_score * WEIGHTS["smart_money"] +
        cex_score * WEIGHTS["cex"] +
        entities_score * WEIGHTS["entities"] +
        token_score * WEIGHTS["token"]
    )

    scores = {
        "entities_score": entities_score,
        "smart_money_score": sm_score,
        "token_score": token_score,
        "cex_score": cex_score,
        "composite": composite,
        "weights": WEIGHTS,
        "components": {
            "entities": entity_components,
            "smart_money": market_scores.get("components", {}).get("smart_money", {}),
            "cex": market_scores.get("components", {}).get("cex", {}),
            "token": market_scores.get("components", {}).get("token", {}),
        },
    }

    # ── Gates ──
    evidence_gate = _evidence_gate(scores)
    risk_gate = _risk_gate(scores, market_ctx, ent_ctx)
    coverage_gate = _coverage_gate(market_ctx, ent_ctx)
    gates = {"evidence": evidence_gate, "risk": risk_gate, "coverage": coverage_gate}

    # ── Decision ──
    decision = _classify_decision(composite, gates)

    # ── Confidence ──
    confidence = _compute_confidence(scores, gates)

    # ── Setup ──
    setup = _classify_setup(market_ctx, ent_ctx, composite)

    # ── Window ──
    action_window = _estimate_window(setup, confidence)

    # ── Drivers ──
    market_drivers = market_ctx.get("drivers", [])
    drivers = _build_drivers(market_drivers, entity_drivers)
    module_drivers = _build_module_drivers(market_ctx, entity_drivers)

    # ── Risks ──
    risks = _build_risks(gates)

    # ── Context Matrix ──
    context_matrix = {
        "entities": _compress_entities_context(ent_ctx),
        "smart_money": market_ctx.get("context", {}).get("smart_money", {}),
        "cex": market_ctx.get("context", {}).get("cex", {}),
        "token": market_ctx.get("context", {}).get("token", {}),
    }

    # ── Entities summary for Setup/Regime engines ──
    _behaviours = ent_ctx.get("behaviours", [])
    _pm = ent_ctx.get("actor_intelligence", {}).get("pressure_map", {})
    _bull_ent = _pm.get("bullish_entities", [])
    _bear_ent = _pm.get("bearish_entities", [])
    entities_summary = {
        "bullish_actors": len(_bull_ent),
        "bearish_actors": len(_bear_ent),
        "bullish_high_impact": sum(1 for e in _bull_ent if e.get("impact") in ("SYSTEMIC", "HIGH")),
        "bearish_high_impact": sum(1 for e in _bear_ent if e.get("impact") in ("SYSTEMIC", "HIGH")),
        "accumulation_actors": sum(1 for b in _behaviours if b.get("behaviour_type") == "accumulation"),
        "distribution_actors": sum(1 for b in _behaviours if b.get("behaviour_type") == "distribution"),
        "lp_actors": sum(1 for b in _behaviours if b.get("behaviour_type") == "liquidity_provision"),
        "pressure_balance": "bullish" if len(_bull_ent) > len(_bear_ent) + 1 else "bearish" if len(_bear_ent) > len(_bull_ent) + 1 else "neutral",
    }

    # ── Regime Engine (E5.5) ──
    from engine_integration.engine_regime_service import detect_regime
    regime_ctx = {
        "cex": market_ctx.get("context", {}).get("cex", {}),
        "smart_money": market_ctx.get("context", {}).get("smart_money", {}),
        "entities_summary": entities_summary,
        "token": market_ctx.get("context", {}).get("token", {}),
        "scores": scores,
    }
    regime_engine = detect_regime(regime_ctx)

    # ── Setup Engine (E2/E5) ──
    from engine_integration.engine_setup_service import detect_all_setups
    setup_engine = detect_all_setups(regime_ctx)

    # ── E3: OTC/MM Scoring Integration ──
    from intelligence.otc_service import detect_otc_trades
    from intelligence.market_maker_service import detect_market_makers
    _otc = detect_otc_trades()
    _mm = detect_market_makers()
    otc_trades = _otc.get("trades", [])
    mm_list = _mm.get("market_makers", [])

    otc_mm_influence = _compute_otc_mm_influence(otc_trades, mm_list, setup_engine)

    # Apply OTC/MM adjustments to setup confidence
    _setup_primary = setup_engine.get("primary", {})
    adj = otc_mm_influence.get("confidence_adjustment", 0)
    if adj != 0 and "confidence" in _setup_primary:
        _setup_primary["confidence"] = round(max(0, min(1, _setup_primary["confidence"] + adj / 100)), 3)

    # ── Flow Acceleration Engine ──
    from engine_integration.engine_flow_service import detect_flow_acceleration
    flow_engine = detect_flow_acceleration(regime_ctx)

    # ── Liquidity Map Layer ──
    from engine_integration.engine_liquidity_service import build_liquidity_map
    liquidity_map = build_liquidity_map(regime_ctx, setup_engine, regime_engine)

    # ── Probability Layer (E5.7) ──
    from engine_integration.engine_probability_service import calculate_probabilities

    # ── Signals ──
    market_state = setup.get("bias", "neutral")
    if composite >= 60:
        market_state = "bullish_bias"
    elif composite <= 40:
        market_state = "bearish_bias"
    elif 45 <= composite <= 55:
        market_state = "neutral"
    else:
        market_state = setup.get("bias", "neutral") + "_bias" if setup.get("bias") != "neutral" else "neutral"

    # ── Signal Feed (temporal) with impact tags ──
    signal_feed = _build_signal_feed(market_ctx, ent_ctx)
    # Tag signals with impact classification for UI highlighting
    for sig in signal_feed:
        desc_lower = sig.get("description", "").lower()
        if sig.get("confidence", 0) >= 0.7 and setup.get("bias") == "bullish" and sig.get("source") != "entities":
            sig["impact"] = "bullish_driver"
        elif any(rf in desc_lower for rf in ["contradict", "pressure", "deposit", "distribution", "growing"]):
            sig["impact"] = "contradiction"
        elif sig.get("source") == "entities" and "new " in desc_lower:
            sig["impact"] = "discovery"
        else:
            sig["impact"] = "neutral"

    # ── Decision Explanation (E1) ──
    explanation = _build_decision_explanation(
        decision, scores, gates, setup, confidence, market_ctx, ent_ctx
    )
    decision_integrity = _build_decision_integrity(gates)

    # ── Probability Layer (E5.7) continued ──
    probability_layer = calculate_probabilities(
        decision=decision,
        composite=composite,
        confidence_score=confidence.get("score", 0),
        regime=regime_engine,
        setup=setup_engine,
        gates=gates,
        explanation=explanation,
    )

    # Apply flow acceleration and liquidity map adjustments to probability
    flow_state = flow_engine.get("state", "neutral")
    flow_strength = flow_engine.get("strength", 0)
    liq_targets = liquidity_map.get("target_zones", [])
    liq_dir = liquidity_map.get("primary_direction", "neutral")
    setup_bias = setup.get("bias", "neutral")

    # Flow acceleration boosts continuation
    if flow_state == "bullish_acceleration" and setup_bias == "bullish":
        probability_layer["continuation"] = round(min(1.0, probability_layer["continuation"] + flow_strength * 0.08), 3)
        probability_layer["failure"] = round(max(0.0, probability_layer["failure"] - flow_strength * 0.05), 3)
    elif flow_state == "bearish_acceleration" and setup_bias == "bearish":
        probability_layer["continuation"] = round(min(1.0, probability_layer["continuation"] + flow_strength * 0.06), 3)
    elif flow_state == "flow_exhaustion":
        probability_layer["failure"] = round(min(1.0, probability_layer["failure"] + 0.06), 3)
        probability_layer["continuation"] = round(max(0.0, probability_layer["continuation"] - 0.04), 3)

    # Liquidity target alignment boosts continuation
    if liq_targets and liq_dir == "above" and setup_bias == "bullish":
        probability_layer["continuation"] = round(min(1.0, probability_layer["continuation"] + 0.04), 3)
    elif liq_targets and liq_dir == "below" and setup_bias == "bearish":
        probability_layer["continuation"] = round(min(1.0, probability_layer["continuation"] + 0.04), 3)

    # OTC/MM influence on probability
    if otc_mm_influence.get("mm_presence"):
        probability_layer["failure"] = round(min(1.0, probability_layer["failure"] + 0.03), 3)

    # Re-normalize continuation+failure
    _total = probability_layer["continuation"] + probability_layer["failure"]
    if _total > 0:
        probability_layer["continuation"] = round(probability_layer["continuation"] / _total, 3)
        probability_layer["failure"] = round(probability_layer["failure"] / _total, 3)

    hero_summary = _build_hero_summary(decision, setup, explanation, confidence)
    # Enrich hero with regime
    hero_summary["regime"] = regime_engine.get("primary", {}).get("type", "neutral_chop")
    hero_summary["regime_status"] = regime_engine.get("primary", {}).get("status", "weak")

    # ── E4: Engine Narrative ──
    # Build after all layers so the narrative has access to everything
    _narrative_input = {
        "decision": decision,
        "confidence": confidence,
        "scores": scores,
        "regime_engine": regime_engine,
        "setup_engine": setup_engine,
        "flow_engine": flow_engine,
        "liquidity_map": liquidity_map,
        "probability_layer": probability_layer,
        "gates": gates,
        "decision_explanation": explanation,
        "otc_mm_influence": otc_mm_influence,
        "setup": setup,
        "hero_summary": hero_summary,
    }
    from engine_integration.engine_narrative_service import build_narrative
    narrative = build_narrative(_narrative_input)

    # ── Risk Engine ──
    from engine_integration.engine_risk_service import calculate_market_risk
    _risk_input = {
        "decision": decision,
        "confidence": confidence,
        "scores": scores,
        "context_matrix": context_matrix,
        "setup_engine": setup_engine,
        "flow_engine": flow_engine,
        "liquidity_map": liquidity_map,
        "probability_layer": probability_layer,
        "decision_explanation": explanation,
        "otc_mm_influence": otc_mm_influence,
    }
    risk_engine = calculate_market_risk(_risk_input)

    # ── Playbook Layer ──
    from engine_integration.engine_playbook_service import build_playbook
    _playbook_input = {
        "decision": decision,
        "confidence": confidence,
        "regime_engine": regime_engine,
        "setup_engine": setup_engine,
        "flow_engine": flow_engine,
        "liquidity_map": liquidity_map,
        "probability_layer": probability_layer,
        "risk_engine": risk_engine,
    }
    playbook = build_playbook(_playbook_input)

    # ── Market Memory Layer ──
    from engine_integration.engine_memory_service import get_memory_for_engine
    _memory_input = {
        "setup_engine": setup_engine,
    }
    market_memory = get_memory_for_engine(_memory_input)

    # ── E6: Alert Engine ──
    # Must run after all layers — compares current state with previous snapshot
    from engine_integration.engine_alert_service import generate_alerts
    _alert_input = {
        "decision": decision,
        "confidence": confidence,
        "scores": scores,
        "regime_engine": regime_engine,
        "setup_engine": setup_engine,
        "flow_engine": flow_engine,
        "liquidity_map": liquidity_map,
        "probability_layer": probability_layer,
        "gates": gates,
        "otc_mm_influence": otc_mm_influence,
    }
    alerts = generate_alerts(_alert_input)

    result = {
        "decision": decision,
        "confidence": confidence,
        "setup": setup,
        "window": action_window,

        "scores": scores,
        "market_state": market_state,

        "gates": gates,

        "regime_engine": regime_engine,
        "setup_engine": setup_engine,
        "otc_mm_influence": otc_mm_influence,
        "flow_engine": flow_engine,
        "liquidity_map": liquidity_map,
        "probability_layer": probability_layer,

        "decision_explanation": explanation,
        "decision_integrity": decision_integrity,
        "hero_summary": hero_summary,

        "drivers": drivers,
        "module_drivers": module_drivers,
        "risks": risks,

        "context_matrix": context_matrix,
        "signals": signal_feed,

        "narrative": narrative,

        "risk_engine": risk_engine,

        "playbook": playbook,

        "market_memory": market_memory,

        "alerts": alerts[:5],

        "meta": {
            "chain_id": chain_id,
            "window": window,
            "version": "4.5",
            "modules": ["entities", "smart_money", "token", "cex"],
        },
    }

    _cache_set(ck, result)
    return result
