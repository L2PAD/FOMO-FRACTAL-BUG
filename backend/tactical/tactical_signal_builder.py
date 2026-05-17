"""
Tactical Signal Builder
=========================
Block X — Task X.2 + Block 7.4 (Threshold Adaptation)

Transforms raw microstructure snapshots into discrete, explainable signals.
Each signal is deterministic — no ML, no black boxes.
Every signal has a clear threshold and clear meaning.

Block 7.4: Uses *_norm values with asset-adaptive thresholds.
"""

from tactical.tactical_types import TacticalSignals, MicrostructureSnapshot
from exchange.thresholds.threshold_engine import get_asset_thresholds


def build_tactical_signals(snap: MicrostructureSnapshot, asset: str = "BTC") -> TacticalSignals:
    """
    Extract tactical signals from a microstructure snapshot.

    Block 7.4: uses normalized values + dynamic thresholds per asset.
    Each signal is a boolean flag with a clear, asset-adapted threshold.
    Only fires on strong, unambiguous conditions.
    """
    th = get_asset_thresholds(asset)

    # ── 1. Order Flow Signals (use imbalance_norm) ──
    imbalance_norm = snap.get("imbalance_norm", snap.get("imbalance", 0.0))
    dominance = snap.get("dominance", 0.5)
    aggressor = snap.get("aggressor_bias", "NEUTRAL")

    # Strong sell-side pressure: clear imbalance + dominant flow
    bearish_orderflow = (
        imbalance_norm <= -th["imbalance"]
        and dominance >= th["dominance"]
    ) or (
        aggressor in ("BEAR", "SELL")
        and imbalance_norm < -th["imbalance_mild"]
    )

    # Strong buy-side pressure
    bullish_orderflow = (
        imbalance_norm >= th["imbalance"]
        and dominance >= th["dominance"]
    ) or (
        aggressor in ("BULL", "BUY")
        and imbalance_norm > th["imbalance_mild"]
    )

    # ── 2. Liquidation Signals (cascade = boolean, no change) ──
    cascade_active = snap.get("cascade_active", False)
    cascade_dir = snap.get("cascade_direction", "")
    cascade_phase = snap.get("cascade_phase", "")

    forced_selling = (
        cascade_active
        and cascade_dir == "LONG"
        and cascade_phase in ("START", "PEAK", "ACTIVE")
    )

    forced_buying = (
        cascade_active
        and cascade_dir == "SHORT"
        and cascade_phase in ("START", "PEAK", "ACTIVE")
    )

    # Liquidation volume imbalance (use *_norm values)
    liq_long_norm = snap.get("liq_long_norm", 0) or 0
    liq_short_norm = snap.get("liq_short_norm", 0) or 0
    total_liq_norm = liq_long_norm + liq_short_norm
    liq_imbalance_dir = None

    if total_liq_norm > th["liquidation"]:
        ratio = liq_long_norm / max(total_liq_norm, 0.001)
        if ratio > th["liq_ratio_high"]:
            liq_imbalance_dir = "long"   # longs getting wiped -> bearish
        elif ratio < th["liq_ratio_low"]:
            liq_imbalance_dir = "short"  # shorts getting wiped -> bullish

    # ── 3. Funding Signals (use funding_norm) ──
    funding_label = snap.get("funding_label", "NEUTRAL")
    funding_norm = snap.get("funding_norm", snap.get("funding_score", 0.0))

    crowded_longs = (
        funding_label in ("BULLISH_EXTREME", "LONG_UNWIND")
        or funding_norm > th["funding"]
    )

    crowded_shorts = (
        funding_label in ("BEARISH_EXTREME", "SHORT_COVER")
        or funding_norm < th["funding_negative"]
    )

    # ── 4. Absorption Signals (boolean, no normalization) ──
    absorption = snap.get("absorption", False)
    absorption_side = snap.get("absorption_side", "")

    seller_exhaustion = absorption and absorption_side == "ASK"
    buyer_exhaustion = absorption and absorption_side == "BID"

    # ── 5. Volatility Signal (raw thresholds) ──
    oi_delta = abs(snap.get("oi_delta_pct", 0))
    vol_delta = abs(snap.get("volume_delta", 0))

    high_volatility = oi_delta > th["oi_delta"] or vol_delta > th["vol_delta"]

    return {
        "bearish_orderflow": bearish_orderflow,
        "bullish_orderflow": bullish_orderflow,
        "forced_selling": forced_selling,
        "forced_buying": forced_buying,
        "crowded_longs": crowded_longs,
        "crowded_shorts": crowded_shorts,
        "seller_exhaustion": seller_exhaustion,
        "buyer_exhaustion": buyer_exhaustion,
        "high_volatility": high_volatility,
        "liquidation_imbalance_direction": liq_imbalance_dir,
    }
