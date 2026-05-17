"""
Asset Registry — Block 7.1 · P1-C expanded
==========================================
Single source of truth for all supported assets in the forecast /
exchange-forecasts pipeline.

P1-C scope: BTC, ETH, SOL, DOGE, LINK, AVAX, ARB, OP, ADA, BNB, XRP
(production universe agreed with operator on 2026-05-15).

The forecast generator iterates SUPPORTED_ASSETS, so any asset listed
here will get its `exchange_forecasts` row created on each scheduler
tick, provided the price_provider can return ≥ 14 daily candles.
"""

ASSET_REGISTRY = {
    "BTC": {
        "type": "major",
        "symbol": "BTCUSDT",
        "liquidity": "high",
        "volatility": 0.02,
        "volume_threshold": 1.0,
    },
    "ETH": {
        "type": "major",
        "symbol": "ETHUSDT",
        "liquidity": "high",
        "volatility": 0.025,
        "volume_threshold": 0.8,
    },
    "SOL": {
        "type": "alt",
        "symbol": "SOLUSDT",
        "liquidity": "medium",
        "volatility": 0.04,
        "volume_threshold": 0.5,
    },
    # ── P1-C · Production universe expansion ────────────────────────
    "DOGE": {
        "type": "alt",
        "symbol": "DOGEUSDT",
        "liquidity": "high",
        "volatility": 0.05,
        "volume_threshold": 0.5,
    },
    "LINK": {
        "type": "alt",
        "symbol": "LINKUSDT",
        "liquidity": "medium",
        "volatility": 0.04,
        "volume_threshold": 0.4,
    },
    "AVAX": {
        "type": "alt",
        "symbol": "AVAXUSDT",
        "liquidity": "medium",
        "volatility": 0.045,
        "volume_threshold": 0.4,
    },
    "ARB": {
        "type": "alt",
        "symbol": "ARBUSDT",
        "liquidity": "medium",
        "volatility": 0.055,
        "volume_threshold": 0.3,
    },
    "OP": {
        "type": "alt",
        "symbol": "OPUSDT",
        "liquidity": "medium",
        "volatility": 0.055,
        "volume_threshold": 0.3,
    },
    "ADA": {
        "type": "alt",
        "symbol": "ADAUSDT",
        "liquidity": "medium",
        "volatility": 0.04,
        "volume_threshold": 0.4,
    },
    "BNB": {
        "type": "major",
        "symbol": "BNBUSDT",
        "liquidity": "high",
        "volatility": 0.025,
        "volume_threshold": 0.7,
    },
    "XRP": {
        "type": "major",
        "symbol": "XRPUSDT",
        "liquidity": "high",
        "volatility": 0.035,
        "volume_threshold": 0.6,
    },
}

SUPPORTED_ASSETS = list(ASSET_REGISTRY.keys())


def get_asset_profile(asset: str) -> dict:
    """Return asset profile. Falls back to BTC if unknown."""
    return ASSET_REGISTRY.get((asset or "").upper(), ASSET_REGISTRY["BTC"])


def is_supported(asset: str) -> bool:
    """Return True if `asset` is in the active production universe."""
    return (asset or "").upper() in ASSET_REGISTRY
