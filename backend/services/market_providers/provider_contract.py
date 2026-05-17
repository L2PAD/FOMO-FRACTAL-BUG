"""
market_providers · provider contract — Phase D · Pass 1.

Capability boundary for market-data providers.  NOT a multi-provider
weighted consensus engine.  NOT arbitrage logic.  NOT provider scoring.

V1 contract: a single canonical shape for price reads with explicit
degraded continuity (cache fallback during cooldown) rather than hard
failure.

Canonical price shape:
    {
        "ok": bool,
        "symbol": str,
        "price": float | None,
        "source": str,              # provider id
        "degraded": bool,           # true when served from cache during cooldown
        "as_of": str,               # ISO of fetch / cache-write
        "reason": str | None,       # populated when ok=false
    }
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class MarketProvider(ABC):
    """Minimal capability surface for a price provider."""

    name: str = "abstract"

    @abstractmethod
    def get_price(self, symbol: str) -> Optional[dict]:
        """Return canonical price shape or None on hard failure.

        Implementations MUST never raise — must degrade honestly via the
        cache layer or return None for unsupported symbols."""
        raise NotImplementedError

    @abstractmethod
    def supports(self, symbol: str) -> bool:
        """Whether the provider knows this symbol mapping."""
        raise NotImplementedError
