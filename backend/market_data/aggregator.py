"""
P1.1/P1.2 — Market Data Aggregator
Merges venue data into AggregatedMarketState + Divergence computation.
"""

from typing import List, Tuple
from . import NormalizedMarketData, AggregatedMarketState


# ── P1.2: Divergence normalization constants ──
FUND_NORM = 0.35   # 35% annualized diff → score 1.0
OI_NORM = 0.20     # 20% OI pct diff → score 1.0


def compute_divergence(
    binance: NormalizedMarketData, bybit: NormalizedMarketData
) -> Tuple[float, str, List[str]]:
    """
    P1.2: Compute divergence score between two venues.
    Returns (score 0..1, label, reasons[]).
    """
    # A) Funding mismatch
    fund_b = binance.funding or 0
    fund_y = bybit.funding or 0
    fund_diff = abs(fund_b - fund_y)
    fund = min(1.0, fund_diff / FUND_NORM) if FUND_NORM > 0 else 0

    # B) OI delta mismatch (pct difference)
    oi_b = binance.oi or 0
    oi_y = bybit.oi or 0
    oi_max = max(oi_b, oi_y)
    if oi_max > 0:
        oi_diff_pct = abs(oi_b - oi_y) / oi_max
    else:
        oi_diff_pct = 0
    oi = min(1.0, oi_diff_pct / OI_NORM) if OI_NORM > 0 else 0

    # C) Orderflow conflict
    b_bias = (binance.orderflow_bias or "neutral").lower()
    y_bias = (bybit.orderflow_bias or "neutral").lower()
    active = {"buy", "sell"}
    if b_bias in active and y_bias in active and b_bias != y_bias:
        flow = 1.0
    elif b_bias != y_bias and (b_bias in active or y_bias in active):
        flow = 0.5
    else:
        flow = 0.0

    score = min(1.0, max(0.0, 0.4 * fund + 0.4 * oi + 0.2 * flow))

    if score < 0.25:
        label = "LOW"
    elif score <= 0.55:
        label = "MID"
    else:
        label = "HIGH"

    reasons = []
    if fund >= 0.25:
        reasons.append("Funding mismatch")
    if oi >= 0.25:
        reasons.append("OI divergence")
    if flow >= 0.5:
        reasons.append("Orderflow conflict")

    return round(score, 4), label, reasons


def aggregate(symbol: str, venue_data: List[NormalizedMarketData]) -> AggregatedMarketState:
    """Aggregate normalized data from 1+ venues into a single state."""
    if not venue_data:
        return AggregatedMarketState(
            symbol=symbol, venueCount=0, venues=[],
            dataQuality={"venuesSeen": 0, "error": "no_data"},
        )

    if len(venue_data) == 1:
        d = venue_data[0]
        return AggregatedMarketState(
            symbol=symbol,
            venueCount=1,
            venues=[d.venue],
            price=d.price,
            volume=d.volume24h,
            volatility=d.volatility,
            funding=d.funding,
            oi=d.oi,
            spread=d.spread,
            orderflow=d.orderflow_strength,
            dataQuality={"venuesSeen": 1, "missingFields": []},
        )

    # ── Multi-venue aggregation ──
    venues = [d.venue for d in venue_data]

    # Price: VWAP weighted by volume24h
    total_volume = sum(d.volume24h for d in venue_data) or 1
    vwap_price = sum(d.price * d.volume24h for d in venue_data) / total_volume

    # Volatility: weighted avg by volume
    vols = [d for d in venue_data if d.volatility is not None]
    weighted_volatility = None
    if vols:
        vol_total = sum(d.volume24h for d in vols) or 1
        weighted_volatility = sum(d.volatility * d.volume24h for d in vols) / vol_total

    # OI: sum
    total_oi = sum(d.oi or 0 for d in venue_data) or None

    # Funding: weighted by OI
    weighted_funding = None
    oi_total = sum(d.oi or 0 for d in venue_data)
    if oi_total > 0:
        weighted_funding = sum((d.funding or 0) * (d.oi or 0) for d in venue_data) / oi_total

    # Spread: weighted minimum
    spreads = [d.spread for d in venue_data if d.spread is not None]
    agg_spread = min(spreads) if spreads else None

    # Orderflow: from venue with highest strength
    best_of = max(venue_data, key=lambda d: d.orderflow_strength or 0)
    agg_orderflow = best_of.orderflow_strength

    # Missing fields
    missing = []
    if weighted_volatility is None:
        missing.append("volatility")
    if total_oi is None:
        missing.append("oi")
    if weighted_funding is None:
        missing.append("funding")

    freshness = {}
    for d in venue_data:
        if d.timestamp:
            freshness[d.venue] = d.timestamp

    return AggregatedMarketState(
        symbol=symbol,
        venueCount=len(venue_data),
        venues=venues,
        price=round(vwap_price, 8),
        volume=round(total_volume, 2),
        volatility=round(weighted_volatility, 6) if weighted_volatility is not None else None,
        funding=round(weighted_funding, 8) if weighted_funding is not None else None,
        oi=round(total_oi, 2) if total_oi else None,
        spread=round(agg_spread, 6) if agg_spread is not None else None,
        orderflow=round(agg_orderflow, 4) if agg_orderflow else None,
        dataQuality={
            "venuesSeen": len(venue_data),
            "missingFields": missing,
            "sourceFreshness": freshness,
        },
    )
