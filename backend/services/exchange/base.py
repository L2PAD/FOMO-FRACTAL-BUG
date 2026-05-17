"""
ReadonlyExchangeAdapter — abstract base.

Every concrete adapter MUST inherit from this class and MUST NOT expose
any method beyond the six whitelisted below.

The underlying transport (e.g. a ccxt exchange instance) MUST live in a
private attribute and MUST NEVER be returned, leaked, or proxied via
getattr / dynamic attribute access.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum


class ExchangeCapability(str, Enum):
    """Capability state surfaced to broker_bridge + UI.

    Backend-enforced — broker_bridge MUST treat anything other than
    READONLY_VERIFIED as a degraded state that forbids ANY future live
    submit, regardless of all other gate checks.
    """

    UNCONFIGURED = "unconfigured"
    READONLY_VERIFIED = "readonly_verified"
    DEGRADED = "degraded"
    TRADING_PERMISSIONS_DETECTED = "trading_permissions_detected"


# Curated universe — adapter rejects everything outside this set.
SUPPORTED_WHITELIST: frozenset[str] = frozenset({"BTC", "ETH", "SOL", "DOGE", "ADA"})


class WhitelistViolation(Exception):
    """Raised when a method is asked to operate on a non-whitelisted symbol."""


class ReadonlyExchangeAdapter(ABC):
    """Strict abstract base for read-only exchange transport adapters.

    Subclasses MUST:
      * Hold the underlying transport in a private attribute (e.g. ``_client``)
      * Implement ONLY the six whitelist methods + the four state properties
      * Reject any symbol not in ``SUPPORTED_WHITELIST`` via ``_assert_symbol``

    Subclasses MUST NOT:
      * Implement any method whose name contains ``create``, ``cancel``,
        ``submit``, ``withdraw``, ``transfer``, ``futures``, or ``leverage``
      * Expose the private transport in any return value, attribute, or
        delegated call
      * Use ``getattr(self._client, ...)`` to call methods not on this list
    """

    # ── State properties ─────────────────────────────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """Adapter identifier (e.g. ``'binance_readonly'``)."""

    @property
    @abstractmethod
    def configured(self) -> bool:
        """True iff credentials are present and adapter initialized."""

    @property
    @abstractmethod
    def connected(self) -> bool:
        """True iff at least one successful exchange call has happened."""

    @property
    @abstractmethod
    def capability(self) -> ExchangeCapability:
        """Current capability classification."""

    # ── Whitelist methods ────────────────────────────────────────────

    @abstractmethod
    def heartbeat(self) -> dict:
        """Lightweight liveness probe. Returns:
            {ok: bool, asOf, lastSuccessfulHeartbeat, lastError}
        Implementations MUST NOT raise; failures become degraded state.
        """

    @abstractmethod
    def fetch_balance(self) -> dict:
        """Return whitelisted-asset balances only (BTC/ETH/SOL/DOGE/ADA + USDT).

        Returns:
            {ok: bool, balances: [{asset, free, locked}], asOf, note?}
        Implementations MUST filter to whitelist + quote asset (USDT).
        """

    @abstractmethod
    def fetch_markets(self) -> list[dict]:
        """Return curated market list with min sizes from the exchange.

        Returns the same shape as the curated SUPPORTED_MARKETS in
        broker_bridge but populated with LIVE exchange metadata.
        """

    @abstractmethod
    def fetch_ticker(self, symbol: str) -> dict:
        """Last/bid/ask for a whitelisted symbol.

        MUST call ``self._assert_symbol(symbol)`` first.
        """

    @abstractmethod
    def fetch_status(self) -> dict:
        """Exchange system status (e.g. {ok, status, updated})."""

    @abstractmethod
    def load_markets(self) -> dict:
        """Refresh the local exchange-market cache. Returns lightweight summary."""

    # ── Helpers (final — not abstract) ───────────────────────────────

    def _assert_symbol(self, symbol: str) -> str:
        sym = (symbol or "").upper().strip()
        if sym not in SUPPORTED_WHITELIST:
            raise WhitelistViolation(
                f"symbol {sym!r} is not in the curated whitelist {sorted(SUPPORTED_WHITELIST)}"
            )
        return sym
