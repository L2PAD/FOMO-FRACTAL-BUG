"""
Core Engine V2 — Providers.
Fetch data from Labs, Macro V2, Divergence, Integrity.
"""

import os
import time
import requests
from labs.service import compute_single_asset
from labs.providers import get_all_symbols


def get_labs_features(symbol: str) -> dict:
    """Extract normalized features from Labs V2 for a single asset."""
    result = compute_single_asset(symbol)
    labs_map = {x["lab"]: x for x in result.get("labs", [])}

    def _g(lab_key, field, default=0.0):
        return float(labs_map.get(lab_key, {}).get(field, default))

    return {
        "regime_abn": _g("regime", "abnormality"),
        "regime_risk": _g("regime", "riskContribution"),
        "regime_conv": _g("regime", "convictionContribution"),
        "regime_state": labs_map.get("regime", {}).get("state", "unknown"),

        "volatility_abn": _g("volatility", "abnormality"),
        "volatility_state": labs_map.get("volatility", {}).get("state", "unknown"),

        "liquidity_risk": _g("liquidity", "riskContribution"),
        "liquidity_abn": _g("liquidity", "abnormality"),

        "stress_risk": _g("market_stress", "riskContribution"),
        "stress_abn": _g("market_stress", "abnormality"),

        "manipulation_risk": _g("manipulation", "riskContribution"),
        "manipulation_abn": _g("manipulation", "abnormality"),

        "conflict_risk": _g("signal_conflict", "riskContribution"),
        "conflict_abn": _g("signal_conflict", "abnormality"),

        "flow_abn": _g("flow", "abnormality"),
        "flow_conv": _g("flow", "convictionContribution"),
        "flow_state": labs_map.get("flow", {}).get("state", "unknown"),

        "volume_abn": _g("volume", "abnormality"),
        "momentum_abn": _g("momentum", "abnormality"),
        "momentum_conv": _g("momentum", "convictionContribution"),
        "momentum_state": labs_map.get("momentum", {}).get("state", "unknown"),

        "participation_abn": _g("participation", "abnormality"),
        "participation_state": labs_map.get("participation", {}).get("state", "unknown"),

        "whale_abn": _g("whale", "abnormality"),
        "whale_conv": _g("whale", "convictionContribution"),
        "liquidation_risk": _g("liquidation", "riskContribution"),

        "data_quality_conf": _g("data_quality", "confidence"),
        "compression": _g("volatility", "abnormality"),

        # Aggregated Labs state
        "integrity": result.get("integrity", {}),
        "labs_state": result.get("overallState", {}),
        "total_risk_labs": result.get("totalRisk", {}),
    }


_macro_v2_cache = {"data": None, "ts": 0}


def get_macro_context() -> dict:
    """Fetch macro context from Macro V2 engine (Python).
    
    Adapter: converts MacroV2 snapshot → CoreMacroContext format.
    Core never computes macro — it only consumes the ready result.
    """
    now = time.time()
    if _macro_v2_cache["data"] and (now - _macro_v2_cache["ts"]) < 60:
        return _macro_v2_cache["data"]

    try:
        from macro_v2.service import compute_macro
        snap = compute_macro()
        if snap.get("ok"):
            c = snap["computed"]
            r = snap.get("raw", {})
            result = {
                # Pre-computed multiplier from Macro V2 (the single source of truth)
                "multiplier": c["macroMult"],
                # Gates from Macro V2 (Core does NOT compute these)
                "strongActionsBlocked": c["strongActionsBlocked"],
                "altExposureReduced": c["altExposureReduced"],
                # Regime context for explain/UI
                "regime": c["regime"],
                "regimeLabel": c["regime"].replace("_", " ").title(),
                "riskOffProb": c["riskOffProb"],
                "fearGreed": r.get("fearGreed", 50),
                "fearGreedLabel": _fg_label(r.get("fearGreed", 50)),
                # Availability
                "available": True,
                "dataSource": snap.get("dataSource", "synthetic"),
            }
            _macro_v2_cache["data"] = result
            _macro_v2_cache["ts"] = now
            return result
    except Exception as e:
        print(f"[Core] Macro V2 unavailable: {e}")

    # Degraded mode: macro disabled, multiplier = 1.0, no blocks
    return {
        "multiplier": 1.0,
        "strongActionsBlocked": False,
        "altExposureReduced": False,
        "regime": "NEUTRAL",
        "regimeLabel": "Neutral",
        "riskOffProb": 0.5,
        "fearGreed": 50,
        "fearGreedLabel": "NEUTRAL",
        "available": False,
        "dataSource": "unavailable",
    }


def _fg_label(fg):
    if fg <= 20:
        return "EXTREME_FEAR"
    if fg <= 40:
        return "FEAR"
    if fg <= 60:
        return "NEUTRAL"
    if fg <= 80:
        return "GREED"
    return "EXTREME_GREED"


def get_divergence_for_symbol(symbol: str) -> dict:
    """Get venue divergence data if available."""
    try:
        from market_data.service import get_venue_info_batch
        info = get_venue_info_batch([symbol])
        vi = info.get(symbol)
        if vi and vi.divergenceScore > 0:
            return {
                "score": vi.divergenceScore,
                "label": vi.divergenceLabel,
                "reasons": list(vi.divergenceReasons) if vi.divergenceReasons else [],
                "available": True,
            }
    except Exception:
        pass
    return {"score": 0, "label": "NONE", "reasons": [], "available": False}


def get_all_universe_symbols() -> list:
    """Get all symbols for universe computation."""
    return get_all_symbols()
