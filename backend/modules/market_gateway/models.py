"""
Market Gateway Data Models
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class ProviderStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


class QuoteData(BaseModel):
    asset: str
    price: float
    change_24h: Optional[float] = None
    change_7d: Optional[float] = None
    volume_24h: Optional[float] = None
    market_cap: Optional[float] = None
    source: str
    timestamp: int


class BulkQuoteResponse(BaseModel):
    ts: int
    quotes: List[QuoteData]
    sources_used: List[str]


class MarketOverview(BaseModel):
    ts: int
    market_cap_total: float
    btc_dominance: float
    eth_dominance: Optional[float] = None
    stablecoin_dominance: Optional[float] = None
    volume_24h: float
    active_cryptocurrencies: Optional[int] = None
    source: str


class CandleData(BaseModel):
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class CandlesResponse(BaseModel):
    ts: int
    asset: str
    interval: str
    candles: List[CandleData]
    source: str


class ExchangeInfo(BaseModel):
    exchange: str
    symbol: str
    price: Optional[float] = None
    volume_24h: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    spread: Optional[float] = None
    status: str


class ExchangesResponse(BaseModel):
    ts: int
    asset: str
    exchanges: List[ExchangeInfo]


class OrderbookEntry(BaseModel):
    price: float
    amount: float


class OrderbookResponse(BaseModel):
    ts: int
    asset: str
    exchange: str
    bids: List[OrderbookEntry]
    asks: List[OrderbookEntry]


class TradeData(BaseModel):
    id: str
    price: float
    amount: float
    side: str
    timestamp: int


class TradesResponse(BaseModel):
    ts: int
    asset: str
    exchange: str
    trades: List[TradeData]


class ProviderHealth(BaseModel):
    id: str
    name: str
    status: ProviderStatus
    latency_ms: Optional[float] = None
    last_check: Optional[datetime] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    ts: int
    providers: Dict[str, ProviderHealth]
