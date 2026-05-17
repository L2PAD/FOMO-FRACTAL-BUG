"""
Market Gateway Module
Provider-agnostic market data gateway with dynamic routing
"""

from .gateway import MarketGateway, market_gateway
from .cache import CacheLayer
from .api.routes import router as market_gateway_router

__all__ = [
    "MarketGateway",
    "market_gateway",
    "CacheLayer",
    "market_gateway_router"
]
