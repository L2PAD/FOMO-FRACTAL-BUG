"""Signal Intelligence Layer — API Routes."""

from fastapi import APIRouter, Query
from .aggregator import compute_unified_signal

router = APIRouter(prefix="/api/signals", tags=["signals"])


def _get_core_snapshot(scope="global", tf="1h"):
    """Fetch current Core Engine snapshot."""
    try:
        from core_engine.service import get_snapshot
        data = get_snapshot(scope, tf)
        if data.get("ok"):
            return data
    except Exception:
        pass
    return _empty_core()


def _get_macro_snapshot():
    """Fetch current Macro V2 snapshot."""
    try:
        from macro_v2.service import compute_macro
        data = compute_macro()
        if data.get("ok"):
            return data
    except Exception:
        pass
    return _empty_macro()


@router.get("/vfinal")
def get_unified_signal(
    asset: str = Query("BTCUSDT", description="Asset symbol"),
    tf: str = Query("1h", description="Timeframe for core engine"),
):
    """Get unified signal intelligence for an asset.

    Returns 3-level signal hierarchy:
      L1: Execution Signal (aggregate)
      L2: Structural Components (exchange, accDist, onchain)
      L3: Event Feed (triggers)
    """
    core_data = _get_core_snapshot(scope="global", tf=tf)
    macro_data = _get_macro_snapshot()

    result = compute_unified_signal(core_data, macro_data, asset=asset)
    return result


def _empty_core():
    return {
        "ok": False,
        "regime": {"dominant": "range", "confidence": 0.25, "probabilities": {}},
        "risk": {"totalIndex": 50, "level": "moderate", "breakdown": {}},
        "factors": {"structure": 50, "flow": 50, "liquidity": 50, "smartMoney": 50, "stability": 50},
        "pressure": {"netBias": 0, "biasLabel": "neutral", "biasScore": 0, "biasStrength": 0, "upward": 50, "downward": 50},
        "transition": {"shiftProbability": 0.2, "instability": 0.3},
        "execution": {"aggressionMultiplier": 0.5, "signalAmplification": 0.5, "strongActionsBlocked": False},
        "_raw_factors": {"flow_conv": 0},
    }


def _empty_macro():
    return {
        "ok": False,
        "raw": {"fearGreed": 50, "btcDom": 50, "stableDom": 10},
        "computed": {
            "regime": "NEUTRAL",
            "regimeProbs": {"FLIGHT_TO_BTC": 0.25, "ALT_ROTATION": 0.25, "CAPITAL_EXIT": 0.25, "NEUTRAL": 0.25},
            "riskOffProb": 0.5,
            "macroMult": 0.7,
            "strongActionsBlocked": False,
        },
        "capitalFlow": {
            "btc": {"pressure": "FLAT", "delta7d": 0},
            "alt": {"pressure": "INLINE", "delta7d": 0},
            "stable": {"pressure": "FLAT", "delta7d": 0},
        },
        "lmi": {"score": 0},
    }
