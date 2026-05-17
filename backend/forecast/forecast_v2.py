"""
Forecast V2 — Score Enhancement (Shadow Mode)
================================================
Sprint 4 C3: Makes the SCORE itself intelligent, so Decision V2 amplifies
rather than compensates.

Blocks:
  C3.1 — New score formula (base + exchange + structure)
  C3.2 — Volatility gating
  C3.3 — Momentum boost
  C3.4 — Liquidation signal
  C3.5 — Trend memory
  C3.6 — Score clamp
  C3.7 — Output to audit
  C3.8 — Shadow mode

Does NOT replace base_score in production. Logs to audit["forecast_v2"].
"""

from typing import Dict, Any

# ── C3.8: Shadow mode control ──
FORECAST_V2_MODE = "shadow"  # "shadow" | "live"


def _extract_structure_bias(audit: dict) -> float:
    """C3.1: Extract structure bias from structure_v2 data."""
    sv2 = audit.get("structure_v2", {})
    if not isinstance(sv2, dict):
        return 0.0

    bearish = sv2.get("bearish", 0) or 0
    bullish = sv2.get("bullish", 0) or 0
    state = sv2.get("state", "")

    # Strong state-based signal
    if state in ("breakdown", "bearish_trend"):
        return -0.3
    if state in ("bullish_trend", "breakout"):
        return 0.3

    # Probability-weighted bias
    diff = bullish - bearish
    if abs(diff) > 0.3:
        return max(-0.3, min(0.3, diff * 0.6))

    return 0.0


def _fetch_previous_score(db, asset: str, horizon: str) -> float:
    """C3.5: Get previous forecast score for trend memory."""
    if db is None:
        return 0.0
    try:
        doc = db["exchange_forecasts"].find_one(
            {"symbol": f"{asset}USDT", "horizon": horizon,
             "audit.scoreFinal": {"$exists": True}},
            {"_id": 0, "audit.scoreFinal": 1},
            sort=[("createdAt", -1)],
        )
        if doc:
            return doc.get("audit", {}).get("scoreFinal", 0) or 0
    except Exception:
        pass
    return 0.0


def compute_forecast_v2(
    base_score: float,
    exchange_signal: dict,
    audit: dict,
    features: dict,
    price: float,
    db=None,
    asset: str = "",
    horizon: str = "7D",
) -> Dict[str, Any]:
    """
    Compute enhanced Forecast V2 score.

    Args:
        base_score: scoreFinal from V1 pipeline
        exchange_signal: dict with micro_bias, funding_bias, orderflow_bias, etc.
        audit: full forecast audit for structure_v2, interaction, etc.
        features: dict with momentum, volatility, ret_7d, etc.
        price: current entry price
        db: pymongo db for trend memory lookup
        asset: asset symbol (BTC, ETH, etc.)
        horizon: forecast horizon (7D, 24H, 30D)

    Returns:
        dict with V2 score + audit trail.
    """
    # ── Extract components ──
    micro_bias = exchange_signal.get("micro_bias", 0.0) if exchange_signal else 0.0
    funding_bias = exchange_signal.get("funding_bias", 0.0) if exchange_signal else 0.0
    orderflow_bias = exchange_signal.get("orderflow_bias", 0.0) if exchange_signal else 0.0

    structure_bias = _extract_structure_bias(audit)

    momentum = features.get("momentum", 0) or 0 if isinstance(features, dict) else 0
    volatility = features.get("volatility", 0) or 0 if isinstance(features, dict) else 0

    # ── C3.1: New score formula (additive — preserves base, adds signal) ──
    exchange_contrib = micro_bias * 0.3
    structure_contrib = structure_bias * 0.2
    final_score = base_score + exchange_contrib + structure_contrib

    # ── C3.2: Volatility gating ──
    vol_gated = False
    if volatility < 0.02 and volatility > 0:
        final_score *= 0.5
        vol_gated = True

    # ── C3.3: Momentum boost ──
    momentum_boost = 0.0
    if momentum > 0.05:
        momentum_boost = 0.1
    elif momentum < -0.05:
        momentum_boost = -0.1
    final_score += momentum_boost

    # ── C3.4: Liquidation signal ──
    liq_long = exchange_signal.get("liq_long", 0) if exchange_signal else 0
    liq_short = exchange_signal.get("liq_short", 0) if exchange_signal else 0
    # Try to get from exchange context if not in signal
    if liq_long == 0 and liq_short == 0:
        ctx = audit.get("exchange_context", {})
        if isinstance(ctx, dict):
            liq_long = ctx.get("liq_long", 0) or 0
            liq_short = ctx.get("liq_short", 0) or 0

    liq_delta = liq_long - liq_short
    liq_bias = max(-1.0, min(1.0, liq_delta / 1e6)) if liq_delta != 0 else 0.0
    final_score += liq_bias * 0.2

    # ── C3.5: Trend memory ──
    prev_score = _fetch_previous_score(db, asset, horizon)
    trend_memory = prev_score * 0.2
    final_score += trend_memory

    # ── C3.6: Score clamp ──
    final_score = max(-1.0, min(1.0, final_score))

    # ── C3.7: Audit output ──
    return {
        "mode": FORECAST_V2_MODE,
        "base_score": round(base_score, 6),
        "final_score": round(final_score, 6),
        "score_delta": round(final_score - base_score, 6),
        "components": {
            "base_contribution": round(base_score, 6),
            "exchange_contribution": round(exchange_contrib, 6),
            "structure_contribution": round(structure_contrib, 6),
            "momentum_boost": round(momentum_boost, 4),
            "liq_bias": round(liq_bias, 6),
            "trend_memory": round(trend_memory, 6),
        },
        "inputs": {
            "micro_bias": round(micro_bias, 4),
            "structure_bias": round(structure_bias, 4),
            "structure_state": audit.get("structure_v2", {}).get("state", "unknown") if isinstance(audit.get("structure_v2"), dict) else "unknown",
            "momentum": round(momentum, 6),
            "volatility": round(volatility, 6),
            "liq_long": liq_long,
            "liq_short": liq_short,
            "prev_score": round(prev_score, 6),
        },
        "gates": {
            "volatility_gated": vol_gated,
        },
    }
