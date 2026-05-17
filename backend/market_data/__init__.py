"""
P1.1 — Market Data Contracts
Normalized venue-agnostic data structures.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict


@dataclass
class NormalizedMarketData:
    symbol: str
    venue: str                          # "binance" | "bybit"
    price: float = 0
    volume24h: float = 0
    volatility: Optional[float] = None
    funding: Optional[float] = None
    oi: Optional[float] = None
    spread: Optional[float] = None
    orderflow_bias: Optional[str] = None     # "buy" | "sell" | "neutral"
    orderflow_strength: Optional[float] = None
    timestamp: int = 0


@dataclass
class AggregatedMarketState:
    symbol: str
    venueCount: int = 1
    venues: List[str] = field(default_factory=lambda: ["binance"])
    price: float = 0
    volume: float = 0
    volatility: Optional[float] = None
    funding: Optional[float] = None
    oi: Optional[float] = None
    spread: Optional[float] = None
    orderflow: Optional[float] = None
    dataQuality: Dict = field(default_factory=dict)
    divergenceScore: float = 0.0
    divergenceLabel: str = "NONE"
    divergenceReasons: List[str] = field(default_factory=list)
