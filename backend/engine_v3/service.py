"""
Engine V3 — Decision Intelligence Layer
=========================================
Context → Score → Gates → Decision → Drivers → Risks → Evidence

Architecture:
  Market Context (scores, context, signals, drivers)
  → Decision Gates (evidence, risk, coverage)
  → Decision Classifier (STRONG_BUY / BUY / WATCH / REDUCE / AVOID)
  → Confidence Engine
  → Setup Classifier
  → Output
"""

import time

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


# ══════════════════════════════════════════════════════════
#  DECISION GATES
# ══════════════════════════════════════════════════════════

def _evidence_gate(market_ctx: dict) -> dict:
    """
    Gate 1: Do enough modules agree on the direction?
    PASS if >= 2 modules align, WEAK if 1, FAIL if 0.
    """
    scores = market_ctx.get("scores", {})
    composite = scores.get("composite", 50)
    is_bullish = composite >= 55

    modules_agreeing = 0
    module_verdicts = {}

    sm = scores.get("smart_money_score", 50)
    cex = scores.get("cex_score", 50)
    token = scores.get("token_score", 50)
    wallet = scores.get("wallet_score", 50)

    for name, score in [("smart_money", sm), ("cex", cex), ("token", token), ("wallet", wallet)]:
        if is_bullish and score >= 55:
            modules_agreeing += 1
            module_verdicts[name] = "supports"
        elif not is_bullish and score <= 45:
            modules_agreeing += 1
            module_verdicts[name] = "supports"
        elif 45 < score < 55:
            module_verdicts[name] = "neutral"
        else:
            module_verdicts[name] = "contradicts"

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
        "verdicts": module_verdicts,
    }


def _risk_gate(market_ctx: dict) -> dict:
    """
    Gate 2: Are there factors that break the signal?
    Checks for contradictions, concentration, thin liquidity.
    """
    ctx = market_ctx.get("context", {})
    signals = market_ctx.get("signals", {})
    scores = market_ctx.get("scores", {})

    risk_factors = []

    # CEX contradictions
    cex_ctx = ctx.get("cex", {})
    if cex_ctx.get("pressure_bias") == "bearish" and scores.get("cex_score", 50) >= 55:
        risk_factors.append("Exchange deposit pressure contradicts bullish signal")
    if cex_ctx.get("inventory_state") == "growing":
        risk_factors.append("Exchange inventory growing — supply increasing")

    # Wallet weakness
    wallet_ctx = ctx.get("wallet", {})
    if wallet_ctx.get("active_actors", 0) < 3:
        risk_factors.append("Wallet participation narrow — few active smart actors")
    if wallet_ctx.get("direction") == "sell" and scores.get("composite", 50) >= 55:
        risk_factors.append("Smart wallets selling — contradicts bullish composite")

    # Signal density check
    sm_signals = signals.get("smart_money", [])
    cex_signals = signals.get("cex", [])
    total_signals = len(sm_signals) + len(cex_signals) + len(signals.get("token", [])) + len(signals.get("wallet", []))
    if total_signals < 3:
        risk_factors.append("Low signal density — insufficient market activity")

    # Module disagreement
    components = scores.get("components", {})
    score_values = [scores.get("smart_money_score", 50), scores.get("cex_score", 50),
                    scores.get("token_score", 50), scores.get("wallet_score", 50)]
    if max(score_values) - min(score_values) > 40:
        risk_factors.append("High module divergence — conflicting signals across layers")

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


def _coverage_gate(market_ctx: dict) -> dict:
    """
    Gate 3: Is data coverage sufficient?
    Checks for stale data, missing sources, incomplete modules.
    """
    ctx = market_ctx.get("context", {})
    issues = []

    # Smart Money coverage
    sm = ctx.get("smart_money", {})
    if sm.get("signal_count", 0) == 0:
        issues.append("No smart money signals detected")
    if sm.get("clusters", 0) == 0:
        issues.append("No token clusters in smart money data")

    # CEX coverage
    cex = ctx.get("cex", {})
    if cex.get("liquidity_shock") == "neutral" and cex.get("pressure_bias") == "neutral" and cex.get("stablecoin_bias") == "neutral":
        issues.append("CEX data shows no directional signals")

    # Token coverage
    token = ctx.get("token", {})
    if token.get("token_count", 0) == 0:
        issues.append("No token intelligence data available")
    if token.get("regime") == "neutral" and token.get("confidence", 0) < 40:
        issues.append("Token regime unclear — low confidence")

    # Wallet coverage
    wallet = ctx.get("wallet", {})
    if wallet.get("active_actors", 0) == 0:
        issues.append("No active wallet actors detected")

    if len(issues) >= 3:
        level = "LOW"
    elif len(issues) >= 1:
        level = "PARTIAL"
    else:
        level = "FULL"

    return {
        "status": level,
        "issues": issues[:4],
        "missing_count": len(issues),
    }


# ══════════════════════════════════════════════════════════
#  DECISION ENGINE
# ══════════════════════════════════════════════════════════

def _classify_decision(composite: int, gates: dict) -> str:
    """
    Composite → Decision, with gate modifiers.
    0-35=AVOID, 35-50=REDUCE, 50-60=WATCH, 60-75=BUY, 75-100=STRONG_BUY
    Gates can downgrade decision.
    """
    # Base decision from composite
    if composite >= 75:
        decision = "STRONG_BUY"
    elif composite >= 60:
        decision = "BUY"
    elif composite >= 50:
        decision = "WATCH"
    elif composite >= 35:
        decision = "REDUCE"
    else:
        decision = "AVOID"

    # Gate modifiers
    evidence = gates.get("evidence", {}).get("status", "PASS")
    risk = gates.get("risk", {}).get("status", "LOW")
    coverage = gates.get("coverage", {}).get("status", "FULL")

    # Evidence gate: if FAIL → force WATCH max
    if evidence == "FAIL":
        if decision in ("STRONG_BUY", "BUY"):
            decision = "WATCH"
    elif evidence == "WEAK":
        if decision == "STRONG_BUY":
            decision = "BUY"

    # Risk gate: HIGH → downgrade one level
    if risk == "HIGH":
        downgrades = {"STRONG_BUY": "BUY", "BUY": "WATCH", "WATCH": "REDUCE"}
        decision = downgrades.get(decision, decision)

    # Coverage gate: LOW → NO_DECISION
    if coverage == "LOW":
        decision = "NO_DECISION"

    return decision


# ══════════════════════════════════════════════════════════
#  CONFIDENCE ENGINE
# ══════════════════════════════════════════════════════════

def _compute_confidence(scores: dict, gates: dict) -> dict:
    """
    Confidence depends on: signal agreement, data coverage, conflicts, density.
    """
    evidence = gates.get("evidence", {})
    risk = gates.get("risk", {})
    coverage = gates.get("coverage", {})

    # Agreement score (0-100)
    agreement = (evidence.get("modules_agreeing", 0) / 4) * 100

    # Risk penalty
    risk_penalty = {"LOW": 0, "MEDIUM": 15, "HIGH": 30}.get(risk.get("status", "LOW"), 0)

    # Coverage bonus
    coverage_bonus = {"FULL": 20, "PARTIAL": 10, "LOW": 0}.get(coverage.get("status", "FULL"), 0)

    # Score variance penalty (high variance = less confidence)
    sm = scores.get("smart_money_score", 50)
    cex = scores.get("cex_score", 50)
    token = scores.get("token_score", 50)
    wallet = scores.get("wallet_score", 50)
    variance = max(sm, cex, token, wallet) - min(sm, cex, token, wallet)
    variance_penalty = min(20, variance * 0.4)

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
            "agreement": round(agreement),
            "coverage_bonus": coverage_bonus,
            "risk_penalty": risk_penalty,
            "variance_penalty": round(variance_penalty),
        },
    }


# ══════════════════════════════════════════════════════════
#  SETUP CLASSIFIER
# ══════════════════════════════════════════════════════════

def _classify_setup(market_ctx: dict) -> dict:
    """
    Determines setup type: Accumulation, Distribution, Rotation,
    Breakout Setup, Liquidity Shock, Neutral Market.
    """
    ctx = market_ctx.get("context", {})
    scores = market_ctx.get("scores", {})

    cex = ctx.get("cex", {})
    sm = ctx.get("smart_money", {})
    token = ctx.get("token", {})
    wallet = ctx.get("wallet", {})

    shock = cex.get("liquidity_shock", "neutral")
    regime = token.get("regime", "neutral")
    sm_conviction = sm.get("conviction", 0)
    wallet_dir = wallet.get("direction", "neutral")
    composite = scores.get("composite", 50)

    # Liquidity Shock takes priority
    if "bullish" in shock:
        return {"type": "Liquidity Shock", "bias": "bullish", "description": "Buy-side liquidity imbalance detected across exchanges"}
    if "bearish" in shock:
        return {"type": "Liquidity Shock", "bias": "bearish", "description": "Sell-side liquidity imbalance detected across exchanges"}

    # Accumulation
    if regime == "accumulation" and sm_conviction >= 60 and wallet_dir == "buy":
        return {"type": "Accumulation", "bias": "bullish", "description": "Smart money accumulating with strong conviction, wallet activity confirms"}

    if regime == "accumulation" and composite >= 55:
        return {"type": "Accumulation", "bias": "bullish", "description": "Token regime indicates accumulation phase with positive composite"}

    # Distribution
    if regime == "distribution" and composite <= 45:
        return {"type": "Distribution", "bias": "bearish", "description": "Token regime indicates distribution phase, composite confirms bearish bias"}

    # Breakout Setup
    inventory = cex.get("inventory_state", "stable")
    if inventory == "shrinking" and sm_conviction >= 50 and composite >= 60:
        return {"type": "Breakout Setup", "bias": "bullish", "description": "Exchange inventory shrinking + smart money conviction = potential breakout"}

    # Rotation
    if wallet_dir == "buy" and regime == "neutral" and composite >= 45 and composite <= 60:
        return {"type": "Rotation", "bias": "neutral", "description": "Capital rotating between positions, no clear directional conviction"}

    # Neutral
    return {"type": "Neutral Market", "bias": "neutral", "description": "No clear setup detected — market in equilibrium"}


# ══════════════════════════════════════════════════════════
#  RISK ENGINE
# ══════════════════════════════════════════════════════════

def _build_risks(market_ctx: dict, gates: dict) -> list:
    """Aggregate all risk factors from gate analysis + additional checks."""
    risks = list(gates.get("risk", {}).get("factors", []))

    ctx = market_ctx.get("context", {})
    cex = ctx.get("cex", {})
    wallet = ctx.get("wallet", {})

    # Additional contextual risks
    if cex.get("stablecoin_bias") == "selling" or cex.get("stablecoin_net", 0) < 0:
        risks.append("Stablecoin outflow — buy-side liquidity draining")

    if wallet.get("avg_smart_score", 0) < 40:
        risks.append("Low actor credibility — smart score below threshold")

    return risks[:6]


# ══════════════════════════════════════════════════════════
#  EVIDENCE ENGINE
# ══════════════════════════════════════════════════════════

def _build_evidence(market_ctx: dict) -> list:
    """Build per-module evidence blocks."""
    ctx = market_ctx.get("context", {})
    signals = market_ctx.get("signals", {})
    evidence = []

    # Smart Money evidence
    sm = ctx.get("smart_money", {})
    if sm.get("signal_count", 0) > 0:
        evidence.append({
            "module": "Smart Money",
            "summary": f"{sm.get('net_flow_fmt', '?')} inflow, conviction {sm.get('conviction', 0)}%",
            "detail": f"{sm.get('clusters', 0)} token clusters, {sm.get('signal_count', 0)} active signals",
            "signals": signals.get("smart_money", [])[:3],
        })

    # CEX evidence
    cex = ctx.get("cex", {})
    evidence.append({
        "module": "CEX",
        "summary": f"Bias: {cex.get('market_bias', 'neutral')}, Shock: {cex.get('liquidity_shock', 'neutral')}",
        "detail": f"Inventory: {cex.get('inventory_state', 'unknown')}, Pressure: {cex.get('pressure_bias', 'neutral')}",
        "signals": signals.get("cex", [])[:3],
    })

    # Token evidence
    token = ctx.get("token", {})
    evidence.append({
        "module": "Token",
        "summary": f"Regime: {token.get('regime', 'neutral')}, Pattern: {token.get('pattern', 'none')}",
        "detail": f"Confidence: {token.get('confidence', 0)}%, {token.get('token_count', 0)} tokens tracked",
        "signals": signals.get("token", [])[:3],
    })

    # Wallet evidence
    wallet = ctx.get("wallet", {})
    if wallet.get("active_actors", 0) > 0:
        evidence.append({
            "module": "Wallet",
            "summary": f"Direction: {wallet.get('direction', 'neutral')}, {wallet.get('active_actors', 0)} active actors",
            "detail": f"Smart score avg: {wallet.get('avg_smart_score', 0)}, Net: {wallet.get('net_flow_fmt', '?')}",
            "signals": signals.get("wallet", [])[:3],
        })

    return evidence


# ══════════════════════════════════════════════════════════
#  DIAGNOSTICS ENGINE
# ══════════════════════════════════════════════════════════

def _build_diagnostics(gates: dict, confidence: dict) -> dict:
    """Build diagnostics summary from gates and confidence analysis."""
    evidence_gate = gates.get("evidence", {})
    risk_gate = gates.get("risk", {})
    coverage_gate = gates.get("coverage", {})

    # Count confirmed vs contradicting vs neutral modules
    verdicts = evidence_gate.get("verdicts", {})
    confirmed = sum(1 for v in verdicts.values() if v == "supports")
    contradicted = sum(1 for v in verdicts.values() if v == "contradicts")
    neutral = sum(1 for v in verdicts.values() if v == "neutral")

    return {
        "integrity": {
            "confirmed": confirmed,
            "contradicted": contradicted,
            "neutral": neutral,
            "total": 4,
            "agreement_rate": round(confirmed / 4 * 100),
        },
        "data_quality": {
            "coverage": coverage_gate.get("status", "UNKNOWN"),
            "missing_sources": coverage_gate.get("issues", []),
            "risk_level": risk_gate.get("status", "UNKNOWN"),
        },
        "confidence_breakdown": confidence.get("factors", {}),
    }


# ══════════════════════════════════════════════════════════
#  WINDOW ESTIMATOR
# ══════════════════════════════════════════════════════════

def _estimate_window(setup: dict, confidence: dict) -> str:
    """Estimate actionable time window based on setup type and confidence."""
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
#  MAIN ENTRY
# ══════════════════════════════════════════════════════════

def get_engine_context(chain_id: int = 1, window: str = "30d") -> dict:
    ck = f"engine_v3:{chain_id}:{window}"
    cached = _cache_get(ck)
    if cached is not None:
        return cached

    # ── Fetch Market Context ──
    from market_context.service import get_market_context
    market_ctx = get_market_context(chain_id=chain_id, window=window)

    scores = market_ctx.get("scores", {})
    composite = scores.get("composite", 50)

    # ── Decision Gates ──
    evidence_gate = _evidence_gate(market_ctx)
    risk_gate = _risk_gate(market_ctx)
    coverage_gate = _coverage_gate(market_ctx)

    gates = {
        "evidence": evidence_gate,
        "risk": risk_gate,
        "coverage": coverage_gate,
    }

    # ── Decision ──
    decision = _classify_decision(composite, gates)

    # ── Confidence ──
    confidence = _compute_confidence(scores, gates)

    # ── Setup ──
    setup = _classify_setup(market_ctx)

    # ── Window ──
    action_window = _estimate_window(setup, confidence)

    # ── Risks ──
    risks = _build_risks(market_ctx, gates)

    # ── Evidence ──
    evidence = _build_evidence(market_ctx)

    # ── Diagnostics ──
    diagnostics = _build_diagnostics(gates, confidence)

    # ── Context Matrix (compressed state per module) ──
    context_matrix = market_ctx.get("context", {})

    result = {
        "decision": decision,
        "confidence": confidence,
        "setup": setup,
        "window": action_window,

        "scores": {
            "composite": composite,
            "smart_money": scores.get("smart_money_score", 50),
            "cex": scores.get("cex_score", 50),
            "token": scores.get("token_score", 50),
            "wallet": scores.get("wallet_score", 50),
            "weights": scores.get("weights", {}),
        },

        "gates": gates,

        "drivers": market_ctx.get("drivers", []),
        "risks": risks,

        "context_matrix": context_matrix,
        "evidence": evidence,
        "signals": market_ctx.get("signals", {}),

        "diagnostics": diagnostics,

        "meta": {
            "chain_id": chain_id,
            "window": window,
            "version": "3.0",
        },
    }

    _cache_set(ck, result)
    return result
