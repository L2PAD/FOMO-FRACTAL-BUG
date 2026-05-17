"""
BinanceReadonlyAdapter — observability bridge to Binance Spot (mainnet).

Strict observability only. The class:
  * Holds the ccxt instance in a *private* attribute (``_client``)
  * Implements ONLY the six whitelist methods from ``ReadonlyExchangeAdapter``
  * Detects trading permissions on the configured API key and degrades
    capability to TRADING_PERMISSIONS_DETECTED if any write capability
    is granted by the user (canTrade, canWithdraw, etc.)
  * Filters every output to the curated symbol whitelist
  * Honestly reports degraded state on timeout / 451 / rate-limit / auth-fail

Imports here are isolated — broker_bridge.py must never import ccxt.
"""
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone
from typing import Optional

from .base import (
    ExchangeCapability,
    ReadonlyExchangeAdapter,
    SUPPORTED_WHITELIST,
    WhitelistViolation,
)

logger = logging.getLogger("exchange.binance_readonly")

# Quote asset surfaced in balances output. Curated like the symbol set.
QUOTE_ASSET = "USDT"


class BinanceReadonlyAdapter(ReadonlyExchangeAdapter):
    """Binance Spot read-only adapter (mainnet)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        *,
        timeout_ms: int = 10_000,
        rate_limit: bool = True,
    ) -> None:
        self._api_key = (
            api_key
            or os.getenv("BROKER_BINANCE_API_KEY")
            or os.getenv("BROKER_API_KEY")
            or ""
        ).strip()
        self._api_secret = (
            api_secret
            or os.getenv("BROKER_BINANCE_API_SECRET")
            or os.getenv("BROKER_API_SECRET")
            or ""
        ).strip()
        self._timeout_ms = int(timeout_ms)
        self._rate_limit = bool(rate_limit)

        self._client = None  # ccxt.binance | None — PRIVATE, must not leak
        self._init_error: Optional[str] = None
        self._capability = ExchangeCapability.UNCONFIGURED

        # heartbeat state
        self._last_ok_iso: Optional[str] = None
        self._last_err: Optional[str] = None
        self._lock = threading.Lock()

        if self._api_key and self._api_secret:
            self._build_client()

    # ── Construction & permission probe ──────────────────────────────

    def _build_client(self) -> None:
        try:
            import ccxt  # local import — keeps ccxt OUT of broker_bridge
        except Exception as e:  # pragma: no cover
            self._init_error = f"ccxt_not_available: {e}"
            self._capability = ExchangeCapability.DEGRADED
            return

        try:
            self._client = ccxt.binance({
                "apiKey": self._api_key,
                "secret": self._api_secret,
                "enableRateLimit": self._rate_limit,
                "timeout": self._timeout_ms,
                "options": {
                    # spot only; never touch futures
                    "defaultType": "spot",
                    "adjustForTimeDifference": True,
                },
            })
            # Pinned to the public + private read endpoints we actually call.
            # We never set `sandbox` here — mainnet read-only by design for T10.2B.
            self._capability = ExchangeCapability.DEGRADED  # until first probe
            self._probe_permissions_safe()
        except Exception as e:
            self._init_error = f"ccxt_init_failed: {e}"
            self._capability = ExchangeCapability.DEGRADED
            self._client = None

    def _probe_permissions_safe(self) -> None:
        """Pull account info to verify the key is read-only.

        Binance returns ``info.canTrade / canWithdraw / canDeposit`` flags
        on ``fetch_balance``. We treat ANY True flag (beyond canDeposit
        which is harmless) as a degradation event.
        """
        try:
            bal = self._call_fetch_balance()
            info = (bal or {}).get("info") or {}
            can_trade = bool(info.get("canTrade"))
            can_withdraw = bool(info.get("canWithdraw"))
            if can_trade or can_withdraw:
                self._capability = ExchangeCapability.TRADING_PERMISSIONS_DETECTED
                self._last_err = (
                    f"api_key_has_trading_permissions "
                    f"(canTrade={can_trade}, canWithdraw={can_withdraw})"
                )
            else:
                self._capability = ExchangeCapability.READONLY_VERIFIED
                self._last_err = None
        except Exception as e:
            self._capability = ExchangeCapability.DEGRADED
            self._last_err = f"permission_probe_failed: {e!r}"

    # ── Private guarded ccxt invocations ─────────────────────────────
    # Each is a thin wrapper so that broker_bridge.py NEVER reaches into
    # the ccxt instance directly. No getattr. No dynamic dispatch.

    def _call_fetch_balance(self) -> dict:
        if self._client is None:
            raise RuntimeError("client_not_initialized")
        with self._lock:
            data = self._client.fetch_balance()
            self._mark_ok()
            return data

    def _call_fetch_markets(self) -> list:
        if self._client is None:
            raise RuntimeError("client_not_initialized")
        with self._lock:
            data = self._client.fetch_markets()
            self._mark_ok()
            return data

    def _call_fetch_ticker(self, pair: str) -> dict:
        if self._client is None:
            raise RuntimeError("client_not_initialized")
        with self._lock:
            data = self._client.fetch_ticker(pair)
            self._mark_ok()
            return data

    def _call_fetch_status(self) -> dict:
        if self._client is None:
            raise RuntimeError("client_not_initialized")
        with self._lock:
            data = self._client.fetch_status()
            self._mark_ok()
            return data

    def _call_load_markets(self) -> dict:
        if self._client is None:
            raise RuntimeError("client_not_initialized")
        with self._lock:
            data = self._client.load_markets(reload=True)
            self._mark_ok()
            return data

    def _mark_ok(self) -> None:
        self._last_ok_iso = datetime.now(timezone.utc).isoformat()

    def _mark_err(self, e: Exception) -> None:
        self._last_err = f"{type(e).__name__}: {e}"
        # Any transport failure flips capability into degraded unless we
        # already detected trading permissions (which is sticky).
        if self._capability != ExchangeCapability.TRADING_PERMISSIONS_DETECTED:
            self._capability = ExchangeCapability.DEGRADED

    # ── State properties ─────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "binance_readonly"

    @property
    def configured(self) -> bool:
        return bool(self._api_key) and bool(self._api_secret) and self._client is not None

    @property
    def connected(self) -> bool:
        return self.configured and self._last_ok_iso is not None

    @property
    def capability(self) -> ExchangeCapability:
        return self._capability

    # ── Whitelist methods ────────────────────────────────────────────

    def heartbeat(self) -> dict:
        """Lightweight liveness probe. Calls fetch_status; never raises."""
        if not self.configured:
            return {
                "ok": False,
                "asOf": datetime.now(timezone.utc).isoformat(),
                "lastSuccessfulHeartbeat": None,
                "lastError": self._init_error or "unconfigured",
            }
        try:
            self._call_fetch_status()
            ok = True
        except Exception as e:
            self._mark_err(e)
            ok = False
        return {
            "ok": ok,
            "asOf": datetime.now(timezone.utc).isoformat(),
            "lastSuccessfulHeartbeat": self._last_ok_iso,
            "lastError": self._last_err,
        }

    def fetch_balance(self) -> dict:
        if not self.configured:
            return {
                "ok": False, "balances": [], "asOf": datetime.now(timezone.utc).isoformat(),
                "note": self._init_error or "unconfigured",
            }
        try:
            raw = self._call_fetch_balance()
        except Exception as e:
            self._mark_err(e)
            return {
                "ok": False, "balances": [], "asOf": datetime.now(timezone.utc).isoformat(),
                "note": self._last_err,
            }
        # Re-probe on every balance read so capability stays current.
        info = (raw or {}).get("info") or {}
        if info.get("canTrade") or info.get("canWithdraw"):
            self._capability = ExchangeCapability.TRADING_PERMISSIONS_DETECTED

        balances: list[dict] = []
        # Filter to whitelist + quote asset
        keep_assets = set(SUPPORTED_WHITELIST) | {QUOTE_ASSET}
        totals = raw.get("total") or {}
        free = raw.get("free") or {}
        used = raw.get("used") or {}
        for asset in keep_assets:
            t = float(totals.get(asset) or 0.0)
            if t == 0 and float(free.get(asset) or 0.0) == 0 and float(used.get(asset) or 0.0) == 0:
                continue
            balances.append({
                "asset": asset,
                "free": float(free.get(asset) or 0.0),
                "locked": float(used.get(asset) or 0.0),
                "total": t,
            })
        return {
            "ok": True,
            "connected": True,
            "balances": balances,
            "asOf": datetime.now(timezone.utc).isoformat(),
        }

    def fetch_markets(self) -> list[dict]:
        if not self.configured:
            return []
        try:
            raw = self._call_fetch_markets()
        except Exception as e:
            self._mark_err(e)
            return []
        out: list[dict] = []
        keep_quote = QUOTE_ASSET
        for m in raw or []:
            base = (m.get("base") or "").upper()
            quote = (m.get("quote") or "").upper()
            if base not in SUPPORTED_WHITELIST or quote != keep_quote:
                continue
            limits = m.get("limits") or {}
            amount = limits.get("amount") or {}
            cost = limits.get("cost") or {}
            precision = m.get("precision") or {}
            out.append({
                "symbol": base,
                "pair": f"{base}{quote}",
                "minNotionalUsd": float(cost.get("min") or 10.0),
                "minQty": float(amount.get("min") or 0.0),
                "tickSize": float(precision.get("price") or 0.0)
                if isinstance(precision.get("price"), (int, float)) else 0.0,
                "tradable": False,  # T10.2B invariant — observability only
                "source": "binance_readonly",
            })
        return out

    def fetch_ticker(self, symbol: str) -> dict:
        sym = self._assert_symbol(symbol)
        if not self.configured:
            return {
                "ok": False, "symbol": sym,
                "note": self._init_error or "unconfigured",
                "asOf": datetime.now(timezone.utc).isoformat(),
            }
        pair = f"{sym}/{QUOTE_ASSET}"
        try:
            t = self._call_fetch_ticker(pair)
        except Exception as e:
            self._mark_err(e)
            return {
                "ok": False, "symbol": sym, "note": self._last_err,
                "asOf": datetime.now(timezone.utc).isoformat(),
            }
        return {
            "ok": True,
            "symbol": sym,
            "pair": pair,
            "bid": t.get("bid"),
            "ask": t.get("ask"),
            "last": t.get("last"),
            "asOf": datetime.now(timezone.utc).isoformat(),
        }

    def fetch_status(self) -> dict:
        if not self.configured:
            return {"ok": False, "status": "unconfigured",
                    "note": self._init_error or "no_credentials"}
        try:
            s = self._call_fetch_status()
        except Exception as e:
            self._mark_err(e)
            return {"ok": False, "status": "degraded", "note": self._last_err}
        return {
            "ok": True,
            "status": s.get("status") or "unknown",
            "updated": s.get("updated"),
            "asOf": datetime.now(timezone.utc).isoformat(),
        }

    def load_markets(self) -> dict:
        if not self.configured:
            return {"ok": False, "count": 0, "note": self._init_error or "unconfigured"}
        try:
            m = self._call_load_markets()
        except Exception as e:
            self._mark_err(e)
            return {"ok": False, "count": 0, "note": self._last_err}
        # Count only the whitelist subset
        n = sum(
            1 for k in (m or {}).keys()
            if "/" in k and k.split("/")[0] in SUPPORTED_WHITELIST and k.split("/")[1] == QUOTE_ASSET
        )
        return {
            "ok": True,
            "count": int(n),
            "asOf": datetime.now(timezone.utc).isoformat(),
        }

    # ── Diagnostic snapshot (read-only) ──────────────────────────────

    def snapshot(self) -> dict:
        """Read-only state snapshot for broker status endpoint."""
        return {
            "name": self.name,
            "configured": self.configured,
            "connected": self.connected,
            "capability": self._capability.value,
            "lastSuccessfulHeartbeat": self._last_ok_iso,
            "lastError": self._last_err,
            "initError": self._init_error,
            "timeoutMs": self._timeout_ms,
            "rateLimitEnabled": self._rate_limit,
            "whitelist": sorted(SUPPORTED_WHITELIST),
            "quoteAsset": QUOTE_ASSET,
        }
