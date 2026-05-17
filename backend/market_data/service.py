"""
P1.1/P1.2 — Market Data Service
Entry point for Radar to get aggregated market state + divergence.
Feature-flagged: DUAL_VENUE_ENABLED=false -> Binance only (venueCount=1).
"""

import os
from typing import Dict, List
from . import AggregatedMarketState
from .aggregator import aggregate, compute_divergence
from .binance_adapter import get_binance_batch
from .bybit_adapter import get_bybit_batch

DUAL_VENUE_ENABLED = os.environ.get("DUAL_VENUE_ENABLED", "false").lower() == "true"


def get_venue_info_batch(symbols: List[str]) -> Dict[str, AggregatedMarketState]:
    """
    Batch fetch venue info for symbols.
    When DUAL_VENUE_ENABLED=true, fetches both Binance + Bybit,
    computes divergence, and returns enriched AggregatedMarketState.
    """
    result = {}

    if not DUAL_VENUE_ENABLED:
        for sym in symbols:
            result[sym] = AggregatedMarketState(
                symbol=sym, venueCount=1, venues=["binance"],
                dataQuality={"venuesSeen": 1, "mode": "single"},
            )
        return result

    # Dual venue mode: fetch both
    binance_data = get_binance_batch(symbols)
    bybit_data = get_bybit_batch(symbols)

    for sym in symbols:
        binance = binance_data.get(sym)
        bybit = bybit_data.get(sym)

        has_binance = binance and binance.price > 0
        has_bybit = bybit and bybit.price > 0

        if has_binance and has_bybit:
            # P1.2: Compute divergence between venues
            div_score, div_label, div_reasons = compute_divergence(binance, bybit)

            result[sym] = AggregatedMarketState(
                symbol=sym,
                venueCount=2,
                venues=["binance", "bybit"],
                price=bybit.price,
                volume=bybit.volume24h,
                volatility=bybit.volatility,
                funding=bybit.funding,
                oi=bybit.oi,
                spread=bybit.spread,
                orderflow=bybit.orderflow_strength,
                dataQuality={
                    "venuesSeen": 2,
                    "mode": "dual",
                    "bybitFields": {
                        "hasPrice": bybit.price > 0,
                        "hasVolume": bybit.volume24h > 0,
                        "hasFunding": bybit.funding is not None and bybit.funding != 0,
                        "hasOI": bybit.oi is not None and bybit.oi > 0,
                    },
                },
                divergenceScore=div_score,
                divergenceLabel=div_label,
                divergenceReasons=div_reasons,
            )
        else:
            result[sym] = AggregatedMarketState(
                symbol=sym, venueCount=1, venues=["binance"],
                dataQuality={"venuesSeen": 1, "mode": "dual_but_binance_only"},
            )

    return result
