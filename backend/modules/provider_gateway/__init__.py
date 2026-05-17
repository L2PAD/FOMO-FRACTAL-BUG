"""
Provider Gateway Module
=======================

Unified gateway for all external data providers.
Handles API key rotation, proxy failover, rate limiting and health monitoring.

Categories:
- Category A: Requires API keys (CoinGecko, CoinMarketCap, Messari)
- Category B: Public APIs (DefiLlama, DexScreener, GeckoTerminal, CoinGlass)

Architecture:
    Client Request → Provider Gateway → Provider Router → Proxy Pool → API Key Pool → External API
"""

from .models import (
    Provider, ProviderInstance, ProviderCapability,
    AuthType, ProviderStatus, ProviderCategory
)
from .gateway import ProviderGateway
from .registry import ProviderRegistry
from .health import HealthMonitor
from .api.routes import router as provider_router

__all__ = [
    'Provider',
    'ProviderInstance',
    'ProviderCapability',
    'AuthType',
    'ProviderStatus',
    'ProviderCategory',
    'ProviderGateway',
    'ProviderRegistry',
    'HealthMonitor',
    'provider_router'
]
