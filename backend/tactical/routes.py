"""
Tactical Layer — API Routes
==============================
Block X Phase X.C

GET /api/tactical/1d — Current tactical assessment for 1D horizon
"""

import traceback
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/tactical", tags=["tactical-layer"])


@router.get("/1d")
async def tactical_1d(
    asset: str = Query("BTC", description="Asset symbol"),
):
    """
    Block X.C — 1D Tactical Intelligence.

    Returns current tactical assessment including:
    - tacticalBias (bullish/neutral/bearish)
    - tradeQuality (high/medium/low)
    - executionAdvice (normal/reduced/wait/avoid_aggressive)
    - reasonFlags (which signals fired)
    - execution impact (how this affects position sizing)
    """
    try:
        from tactical.tactical_assembler import build_tactical_assessment
        result = build_tactical_assessment(asset=asset)

        if not result.get("ok"):
            return {
                "ok": False,
                "error": result.get("error", "Unknown error"),
                "tacticalBias": "neutral",
                "tradeQuality": "low",
                "executionAdvice": "wait",
                "volatilityExpectation": "unknown",
                "reasonFlags": ["no_data"],
                "note": result.get("advice", {}).get("note", "No data available"),
            }

        advice = result["advice"]
        fusion = result["fusion"]
        signals = result["signals"]

        # Build execution impact description
        impact = _compute_execution_impact(advice, fusion)

        return {
            "ok": True,
            "timestamp": result["timestamp"],
            "asset": result["asset"],
            "snapshotAge": result.get("snapshot_age_seconds"),

            # Primary payload
            "tacticalBias": advice.get("tacticalBias", "neutral"),
            "tradeQuality": advice.get("tradeQuality", "medium"),
            "executionAdvice": advice.get("executionAdvice", "normal"),
            "volatilityExpectation": advice.get("volatilityExpectation", "moderate"),
            "note": advice.get("note", ""),

            # Signal details
            "signalStrength": round(fusion.get("signal_strength", 0), 3),
            "fusionScore": round(fusion.get("score", 0), 2),
            "activeSignals": fusion.get("active_signals", []),
            "reasonFlags": advice.get("reasonFlags", []),

            # Individual signals (for UI breakdown)
            "signals": {
                "orderflow": {
                    "bearish": signals.get("bearish_orderflow", False),
                    "bullish": signals.get("bullish_orderflow", False),
                },
                "liquidations": {
                    "forcedSelling": signals.get("forced_selling", False),
                    "forcedBuying": signals.get("forced_buying", False),
                    "imbalanceDirection": signals.get("liquidation_imbalance_direction"),
                },
                "funding": {
                    "crowdedLongs": signals.get("crowded_longs", False),
                    "crowdedShorts": signals.get("crowded_shorts", False),
                },
                "absorption": {
                    "sellerExhaustion": signals.get("seller_exhaustion", False),
                    "buyerExhaustion": signals.get("buyer_exhaustion", False),
                },
            },

            # Execution impact
            "executionImpact": impact,

            # Block 7.3: Normalized features (cross-asset comparable)
            "normalized": result.get("normalized", {}),
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e), "trace": traceback.format_exc()},
        )


def _compute_execution_impact(advice: dict, fusion: dict) -> dict:
    """Compute how tactical assessment affects execution — decision enhancer."""
    bias = advice.get("tacticalBias", "neutral")
    exec_advice = advice.get("executionAdvice", "normal")
    strength = fusion.get("signal_strength", 0)
    active = fusion.get("active_signals", [])

    impacts = []
    size_modifier = "unchanged"
    size_pct = 100

    # ── Execution advice → concrete sizing impact ──
    if exec_advice == "wait":
        impacts.append("Avoid new positions until conditions stabilize")
        size_modifier = "strongly_reduced"
        size_pct = 30
    elif exec_advice == "reduced":
        impacts.append("Reduce directional exposure by ~40%")
        size_modifier = "reduced"
        size_pct = 60
    elif exec_advice == "avoid_aggressive":
        impacts.append("Limit aggressive entries, tighten stops by 20%")
        size_modifier = "mildly_reduced"
        size_pct = 80
    else:
        impacts.append("Standard execution parameters")
        size_pct = 100

    # ── Bias → directional impact ──
    if bias == "bearish":
        impacts.append("Short-term bearish pressure: tighten long stops")
        if strength > 0.3:
            impacts.append("Consider delaying new long entries")
    elif bias == "bullish":
        impacts.append("Short-term bullish momentum: favorable for longs")
        if strength > 0.3:
            impacts.append("Wider stop tolerance on long positions")

    # ── Signal-specific impacts ──
    if "crowded_longs" in active:
        impacts.append("Crowded longs detected: reversal risk elevated")
    if "crowded_shorts" in active:
        impacts.append("Crowded shorts: potential squeeze risk")
    if "forced_selling" in active:
        impacts.append("Forced liquidations active: increased volatility")
    if "forced_buying" in active:
        impacts.append("Short squeeze in progress: rapid upside possible")

    return {
        "sizeModifier": size_modifier,
        "sizePct": size_pct,
        "impacts": impacts,
        "overridesStrategicForecast": False,
        "note": "Tactical 1D context enhances execution — does not override 7D/30D direction",
    }
