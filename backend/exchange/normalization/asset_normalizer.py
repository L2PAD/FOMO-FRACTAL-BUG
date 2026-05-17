"""
Asset Normalizer — Block 7.3
==============================
Makes signals cross-asset comparable by normalizing against
each asset's volatility and volume profile.

Principle: same normalized value ≈ same signal strength across assets.

Normalized fields are ADDED alongside originals (no mutation).
  - imbalance → imbalance_norm
  - liq_long/short → liq_long_norm / liq_short_norm
  - funding_score → funding_norm
  - volatility → volatility_norm
"""

from assets.asset_registry import get_asset_profile


def normalize_imbalance(raw: float, asset: str) -> float:
    """Normalize order flow imbalance by asset liquidity.
    Lower liquidity = same $ imbalance is a stronger signal.
    SOL (volume_threshold=0.5) → -0.3 becomes -0.6 (stronger)
    BTC (volume_threshold=1.0) → -0.3 stays -0.3 (baseline)"""
    scale = get_asset_profile(asset)["volume_threshold"]
    if scale <= 0:
        return _clamp(raw)
    return _clamp(raw / scale)


def normalize_liquidations(volume: float, asset: str) -> float:
    """Normalize liquidation volume by asset's liquidity.
    Reference: 100K USD as BTC baseline significant liquidation.
    Result: 1.0 ≈ baseline significant event for the asset."""
    scale = get_asset_profile(asset)["volume_threshold"]
    reference = 100_000  # BTC baseline: 100K USD = significant liq event
    if scale <= 0 or reference <= 0:
        return 0.0
    return round(volume / (reference * scale), 4)


def normalize_funding(score: float, asset: str) -> float:
    """Normalize funding score by asset volatility.
    Higher vol assets have noisier funding → need stronger threshold."""
    vol = get_asset_profile(asset)["volatility"]
    return _clamp(score / (vol * 5))


def normalize_volatility(vol: float, asset: str) -> float:
    """Normalize volatility relative to asset's baseline.
    Result: 1.0 = normal, >1.0 = elevated, <1.0 = suppressed."""
    base = get_asset_profile(asset)["volatility"]
    if base <= 0:
        return 1.0
    return round(vol / base, 4)


def normalize_features(features: dict, asset: str) -> dict:
    """Add normalized versions of all key signals.
    Original fields are preserved — only *_norm fields are added."""
    norm = {}

    # Order flow imbalance
    imbalance = features.get("imbalance", 0)
    norm["imbalance_norm"] = round(normalize_imbalance(imbalance, asset), 4)

    # Liquidations
    liq_long = features.get("liq_long", features.get("longVolume", 0))
    liq_short = features.get("liq_short", features.get("shortVolume", 0))
    norm["liq_long_norm"] = round(normalize_liquidations(liq_long, asset), 2)
    norm["liq_short_norm"] = round(normalize_liquidations(liq_short, asset), 2)

    # Funding
    funding = features.get("funding_score", 0)
    norm["funding_norm"] = round(normalize_funding(funding, asset), 4)

    # Volatility
    vol = features.get("volatility", features.get("vol", 0))
    norm["volatility_norm"] = round(normalize_volatility(vol, asset), 4)

    return {**features, **norm}


def _clamp(v: float, lo: float = -5.0, hi: float = 5.0) -> float:
    """Clamp to prevent extreme outliers."""
    return max(lo, min(hi, v))
