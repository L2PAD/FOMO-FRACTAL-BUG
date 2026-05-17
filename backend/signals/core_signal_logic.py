"""
Core Signal Logic — Detection Primitives
==========================================
Extracted from signals_v3/signal_engine.py and signals/aggregator.py.
Single source of truth for signal classification.

DO NOT duplicate this logic anywhere else.
Overview and Graph both call detect_signal() via their adapters.
"""

import math


# ── Signal Type Constants ──

SIGNAL_TYPES = {
    "PUMP": "PUMP",
    "ACCUMULATION": "ACCUMULATION",
    "DISTRIBUTION": "DISTRIBUTION",
    "LIQUIDITY_MAGNET": "LIQUIDITY_MAGNET",
    "FLOW_ACCELERATION": "FLOW_ACCELERATION",
    "ACTOR_ACCUMULATION": "ACTOR_ACCUMULATION",
    "ACTOR_DISTRIBUTION": "ACTOR_DISTRIBUTION",
    "FUND_PRESSURE": "FUND_PRESSURE",
    "SETUP_CONFIRMATION": "SETUP_CONFIRMATION",
}


# ── Severity (from signals_v3/signal_engine.py) ──

def severity(score: int) -> str:
    """Classify signal score into severity tier."""
    if score >= 75:
        return "EXTREME"
    if score >= 60:
        return "STRONG"
    if score >= 40:
        return "WATCH"
    return "WEAK"


# ── Direction (from signals_v3/signal_engine.py) ──

_BULLISH_SETUPS = {"liquidity_shock", "smart_money_accumulation", "exchange_drain"}
_BEARISH_SETUPS = {"distribution_risk", "actor_conflict"}


def direction_from_setup(setup_type: str) -> str:
    """Map setup type to directional bias."""
    if setup_type in _BULLISH_SETUPS:
        return "BULLISH"
    if setup_type in _BEARISH_SETUPS:
        return "BEARISH"
    return "NEUTRAL"


def direction_from_score(score: float) -> str:
    """Simple directional classification from numeric score."""
    if score > 0.1:
        return "BULLISH"
    if score < -0.1:
        return "BEARISH"
    return "NEUTRAL"


# ── Multi-factor Scoring (from signals_v3/signal_engine.py) ──

def compute_score(
    engine_alignment: float,
    actor_strength: float,
    flow_intensity: float,
    liquidity_alignment: float,
    ranking_score: float,
    pulse_factor: float,
) -> int:
    """
    Weighted multi-factor signal score.
    All inputs are [0, 1]. Output: [0, 100].

    Weights:
      engine_alignment: 0.30  (setup/graph pressure)
      actor_strength:   0.20  (actor conviction)
      flow_intensity:   0.15  (flow/momentum)
      liquidity_alignment: 0.15  (liquidity target)
      ranking_score:    0.10  (opportunity rank)
      pulse_factor:     0.10  (market pulse)
    """
    raw = (
        engine_alignment * 0.30
        + actor_strength * 0.20
        + flow_intensity * 0.15
        + liquidity_alignment * 0.15
        + ranking_score * 0.10
        + pulse_factor * 0.10
    )
    return min(round(raw * 100), 100)


# ── Context Modifier (from signals_v3/signal_engine.py) ──

_BULLISH_REGIMES = {"bull_trend", "accumulation", "early_bull"}
_BEARISH_REGIMES = {"bear_trend", "distribution", "capitulation"}


def context_modifier(direction: str, context: dict) -> int:
    """
    Additive score modifier based on market context.
    Formula: regime_alignment*8 + pressure_alignment*6 + ranking_bonus*4 - risk_penalty

    Args:
        direction: BULLISH / BEARISH / NEUTRAL
        context: {regime, pressure, ranking, risk}

    Returns:
        Integer modifier (-20..+18)
    """
    regime = context.get("regime", "neutral_chop")
    pressure = context.get("pressure", "neutral")
    ranking = context.get("ranking", 0)
    risk = context.get("risk", "moderate")

    # Regime alignment
    if direction == "BULLISH":
        regime_a = 8 if regime in _BULLISH_REGIMES else (-8 if regime in _BEARISH_REGIMES else 0)
    elif direction == "BEARISH":
        regime_a = 8 if regime in _BEARISH_REGIMES else (-8 if regime in _BULLISH_REGIMES else 0)
    else:
        regime_a = 0

    # Pressure alignment
    if direction == "BULLISH":
        pressure_a = 6 if pressure == "bullish" else (-6 if pressure == "bearish" else 0)
    elif direction == "BEARISH":
        pressure_a = 6 if pressure == "bearish" else (-6 if pressure == "bullish" else 0)
    else:
        pressure_a = 0

    # Ranking bonus
    ranking_b = 4 if ranking and ranking > 0 else 0

    # Risk penalty
    risk_p = {"low": 0, "moderate": 2, "elevated": 4, "high": 6}.get(risk, 2)

    return regime_a + pressure_a + ranking_b - risk_p


# ── Freshness Decay ──

def freshness(age_hours: float) -> float:
    """
    Signal freshness: 1.0 = just now, decays over time.
    Half-life: ~2 hours.
    """
    return max(0.0, round(math.exp(-age_hours / 2.88), 4))


# ── Signal Type Detection from Context ──

def detect_signal_type(context: dict) -> dict:
    """
    Core detection: given a unified context, determine signal type.

    Context fields (all optional, adapter fills what's available):
        mentions: int          — how many actors mention this token
        momentum: float [0,1]  — directional momentum
        pressure: float [0,1]  — entity_pressure (graph) or setup confidence
        alpha: float [0,1]     — alpha_source quality (graph) or actor strength
        flow: float [0,1]      — attention_flow (graph) or capital flow
        growth_rate: float     — recent growth (positive = up)
        actor_count: int       — unique actors involved
        setup_type: str        — if from engine setup (optional)

    Returns:
        {is_signal, type, strength, confidence, direction, severity}
    """
    mentions = context.get("mentions", 0)
    momentum = context.get("momentum", 0)
    pressure = context.get("pressure", 0)
    alpha = context.get("alpha", 0)
    flow = context.get("flow", 0)
    growth_rate = context.get("growth_rate", 0)
    actor_count = context.get("actor_count", 0)
    setup_type = context.get("setup_type", "")

    # ── Determine direction ──
    if setup_type:
        direction = direction_from_setup(setup_type)
    elif momentum > 0.1 or growth_rate > 0:
        direction = "BULLISH"
    elif momentum < -0.1 or growth_rate < 0:
        direction = "BEARISH"
    else:
        direction = "NEUTRAL"

    # ── Compute raw score ──
    score = compute_score(
        engine_alignment=pressure,
        actor_strength=alpha,
        flow_intensity=flow,
        liquidity_alignment=min(mentions / 10, 1.0) if mentions else 0,
        ranking_score=min(actor_count / 5, 1.0) if actor_count else 0,
        pulse_factor=abs(momentum),
    )

    # ── Determine signal type ──
    if setup_type:
        sig_type = SIGNAL_TYPES.get("SETUP_CONFIRMATION", "SETUP_CONFIRMATION")
    elif pressure >= 0.5 and actor_count >= 3:
        # Multiple actors pressuring = PUMP or ACCUMULATION
        if direction == "BULLISH":
            sig_type = "ACCUMULATION" if score < 70 else "PUMP"
        else:
            sig_type = "DISTRIBUTION"
    elif alpha >= 0.5:
        # High-quality actor signal
        sig_type = "ACTOR_ACCUMULATION" if direction == "BULLISH" else "ACTOR_DISTRIBUTION"
    elif flow >= 0.5:
        sig_type = "FLOW_ACCELERATION"
    elif mentions >= 5 and momentum > 0.3:
        sig_type = "ACCUMULATION" if direction == "BULLISH" else "DISTRIBUTION"
    else:
        sig_type = "ACCUMULATION" if direction == "BULLISH" else "DISTRIBUTION"

    # ── Thresholds ──
    is_signal = score >= 25
    confidence = min(round((pressure + alpha + flow) / 3 * 100), 100) if any([pressure, alpha, flow]) else 0

    return {
        "is_signal": is_signal,
        "type": sig_type,
        "strength": score,
        "confidence": confidence,
        "direction": direction,
        "severity": severity(score),
    }
