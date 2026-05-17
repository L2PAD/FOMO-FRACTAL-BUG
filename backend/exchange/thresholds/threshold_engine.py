"""
Threshold Engine — Block 7.4
==============================
Dynamic, asset-aware thresholds for signal classification.

7.3 made signals comparable (normalization).
7.4 makes decisions correct per asset (threshold adaptation).

Higher vol → harder to trigger directional signals (less noise).
Lower liquidity → more sensitive to liquidation events.
"""

from assets.asset_registry import get_asset_profile

# Thresholds calibrated for NORMALIZED values (post-7.3)
BASE_THRESHOLDS = {
    "imbalance": 0.3,           # strong directional imbalance
    "imbalance_mild": 0.15,     # mild imbalance (with aggressor confirmation)
    "dominance": 0.55,          # order flow dominance (raw ratio, no normalization)
    "funding": 1.0,             # overcrowded funding signal
    "funding_negative": -1.2,   # overcrowded shorts funding
    "liquidation": 1.0,         # significant liquidation event (norm)
    "liq_ratio_high": 0.65,     # liq skewed to longs
    "liq_ratio_low": 0.35,      # liq skewed to shorts
    "oi_delta": 3.0,            # OI change % (raw)
    "vol_delta": 30.0,          # volume delta (raw)
}


def get_asset_thresholds(asset: str) -> dict:
    """Return asset-adapted thresholds.

    Scaling logic:
      - vol_factor: higher volatility → raise directional thresholds (reduce noise)
      - liq_factor: lower liquidity → lower liquidation threshold (more sensitive)
    """
    profile = get_asset_profile(asset)
    vol = profile["volatility"]
    liquidity = profile["liquidity"]

    # Volatility scaling: BTC(0.02)→1.10, ETH(0.025)→1.125, SOL(0.04)→1.20
    vol_factor = 1 + (vol * 5)

    # Liquidity scaling for liquidation sensitivity
    if liquidity == "high":
        liq_factor = 1.0
    elif liquidity == "medium":
        liq_factor = 0.8
    else:
        liq_factor = 0.6

    return {
        "imbalance": BASE_THRESHOLDS["imbalance"] * vol_factor,
        "imbalance_mild": BASE_THRESHOLDS["imbalance_mild"] * vol_factor,
        "dominance": BASE_THRESHOLDS["dominance"],          # raw ratio, no scaling
        "funding": BASE_THRESHOLDS["funding"] * vol_factor,
        "funding_negative": BASE_THRESHOLDS["funding_negative"] * vol_factor,
        "liquidation": BASE_THRESHOLDS["liquidation"] * liq_factor,
        "liq_ratio_high": BASE_THRESHOLDS["liq_ratio_high"],  # ratio, no scaling
        "liq_ratio_low": BASE_THRESHOLDS["liq_ratio_low"],
        "oi_delta": BASE_THRESHOLDS["oi_delta"],              # raw, no scaling
        "vol_delta": BASE_THRESHOLDS["vol_delta"],
    }
