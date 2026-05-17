"""
broker_bridge — T10.1 · Broker Readiness Bridge.

This module is the *first* mile of the live-execution path. Its only goal is
to make a live order **impossible by default** and to make every refusal
fully explainable.

Pipeline reminder:
    verdict
    → calibration (T4/T6)
    → adaptive sizing (T8)
    → portfolio gate (T9)
    → broker preflight (T10.1)
    → ? broker submit (T10.x — gated, default REFUSED)

What this layer DOES today:
  * publishes broker connectivity status (configured / connected / mode)
  * exposes a curated, hardcoded market list with min order sizes
  * validates a prospective order against live verdict state (preflight)
  * REFUSES every live submit by default — writes a full audit row
  * never imports or installs ccxt — if BROKER_PROVIDER='binance' is set,
    we'd shell into ccxt; without it we serve NoopBrokerAdapter cleanly

What this layer does NOT do today:
  * actually place real orders (T10.2+)
  * touch cognition, calibration, sizing or portfolio gate (all upstream)
  * provide any UI bypass — every path passes through these gates
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pymongo import MongoClient, DESCENDING

load_dotenv(Path(__file__).parent.parent / ".env", override=False)
logger = logging.getLogger("broker_bridge")

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "test_database")

_client = MongoClient(MONGO_URL)
_db = _client[DB_NAME]
broker_audit = _db["broker_audit_v1"]
broker_audit.create_index([("attemptAt", DESCENDING)])
broker_audit.create_index([("auditId", 1)], unique=True)


# ── Env-driven config (NEVER user-settable from UI) ──────────────────


def _env_truthy(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def broker_config() -> dict:
    """Snapshot of broker config — used by status endpoint + gate checks."""
    return {
        "liveMode": (os.getenv("BROKER_LIVE_MODE") or "off").lower(),
        "provider": (os.getenv("BROKER_PROVIDER") or "noop").lower(),
        "apiKeySet": bool(os.getenv("BROKER_BINANCE_API_KEY") or os.getenv("BROKER_API_KEY")),
        "apiSecretSet": bool(os.getenv("BROKER_BINANCE_API_SECRET") or os.getenv("BROKER_API_SECRET")),
        "riskAckSigned": _env_truthy("BROKER_RISK_ACK_SIGNED"),
    }


# ── Curated market list (hardcoded — same Binance defaults as bar_data) ─


# Format: {symbol: {pair, minNotionalUsd, minQty, tickSize}}
SUPPORTED_MARKETS: dict[str, dict] = {
    "BTC":  {"pair": "BTCUSDT",  "minNotionalUsd": 10.0, "minQty": 0.00001, "tickSize": 0.01},
    "ETH":  {"pair": "ETHUSDT",  "minNotionalUsd": 10.0, "minQty": 0.0001,  "tickSize": 0.01},
    "SOL":  {"pair": "SOLUSDT",  "minNotionalUsd": 10.0, "minQty": 0.001,   "tickSize": 0.01},
    "DOGE": {"pair": "DOGEUSDT", "minNotionalUsd": 10.0, "minQty": 1.0,     "tickSize": 0.00001},
    "ADA":  {"pair": "ADAUSDT",  "minNotionalUsd": 10.0, "minQty": 0.1,     "tickSize": 0.0001},
}


# ── Adapter abstraction ──────────────────────────────────────────────


class NoopBrokerAdapter:
    """Default adapter. Always connected=False — no real broker access.

    Used when:
      * BROKER_PROVIDER is unset / 'noop'
      * binance_readonly was selected but failed to initialize (e.g.
        credentials missing, ccxt unavailable)
    """

    name = "noop"

    @property
    def configured(self) -> bool:
        return False

    @property
    def connected(self) -> bool:
        return False

    @property
    def capability(self) -> str:
        return "unconfigured"

    def fetch_balances(self) -> dict:
        return {
            "ok": True,
            "connected": False,
            "balances": [],
            "note": "noop adapter — no broker configured",
        }

    def fetch_markets(self) -> list[dict]:
        return [
            {"symbol": s, **m, "tradable": False, "source": "curated_fallback"}
            for s, m in SUPPORTED_MARKETS.items()
        ]

    def heartbeat(self) -> dict:
        return {
            "ok": False,
            "asOf": datetime.now(timezone.utc).isoformat(),
            "lastSuccessfulHeartbeat": None,
            "lastError": "noop adapter — no live exchange transport",
        }

    def snapshot(self) -> dict:
        return {
            "name": self.name,
            "configured": False,
            "connected": False,
            "capability": "unconfigured",
            "lastSuccessfulHeartbeat": None,
            "lastError": None,
            "initError": None,
            "whitelist": sorted(SUPPORTED_MARKETS.keys()),
        }


def _adapter():
    """Adapter factory.

    T10.2B: read-only Binance is wired here when BROKER_PROVIDER=binance_readonly.
    Falls back to NoopBrokerAdapter when:
      * provider mismatched
      * credentials missing
      * ccxt module unavailable
    The Binance adapter is observability-only — its surface is constrained by
    ReadonlyExchangeAdapter (six whitelist methods + state properties).
    """
    provider = (os.getenv("BROKER_PROVIDER") or "noop").lower()
    if provider == "binance_readonly":
        try:
            from services.exchange import BinanceReadonlyAdapter
            return _BinanceAdapterFacade(BinanceReadonlyAdapter())
        except Exception as e:  # pragma: no cover
            logger.warning(f"[broker_bridge] binance_readonly init failed: {e}")
    return NoopBrokerAdapter()


# Module-level singleton so heartbeat / capability state persists across requests.
_ADAPTER_SINGLETON: Optional[object] = None


def _adapter_singleton():
    global _ADAPTER_SINGLETON
    if _ADAPTER_SINGLETON is None:
        _ADAPTER_SINGLETON = _adapter()
    return _ADAPTER_SINGLETON


class _BinanceAdapterFacade:
    """Local facade exposing only the surface broker_bridge needs.

    DELIBERATELY narrow. broker_bridge.py must NEVER reach into
    ``self._inner._client`` or use getattr on the underlying ccxt instance.
    Only the six whitelist methods + snapshot are surfaced here.
    """

    def __init__(self, inner):
        # Private — never expose outside this module.
        self._inner = inner

    name = "binance_readonly"

    @property
    def configured(self) -> bool:
        return bool(self._inner.configured)

    @property
    def connected(self) -> bool:
        return bool(self._inner.connected)

    @property
    def capability(self) -> str:
        return self._inner.capability.value

    def fetch_balances(self) -> dict:
        return self._inner.fetch_balance()

    def fetch_markets(self) -> list[dict]:
        markets_live = self._inner.fetch_markets() or []
        # Merge live metadata over our curated whitelist so all 5 always appear.
        live_by_sym = {m["symbol"]: m for m in markets_live}
        out: list[dict] = []
        for sym, curated in SUPPORTED_MARKETS.items():
            live = live_by_sym.get(sym)
            if live:
                out.append({
                    "symbol": sym,
                    "pair": live.get("pair") or curated["pair"],
                    "minNotionalUsd": live.get("minNotionalUsd") or curated["minNotionalUsd"],
                    "minQty": live.get("minQty") or curated["minQty"],
                    "tickSize": live.get("tickSize") or curated["tickSize"],
                    "tradable": False,
                    "source": "binance_readonly",
                })
            else:
                out.append({"symbol": sym, **curated, "tradable": False, "source": "curated_fallback"})
        return out

    def heartbeat(self) -> dict:
        return self._inner.heartbeat()

    def snapshot(self) -> dict:
        return self._inner.snapshot()


# ── Status / balances / markets (read-only) ──────────────────────────


def broker_status() -> dict:
    cfg = broker_config()
    a = _adapter_singleton()
    cap = getattr(a, "capability", "unconfigured")
    if callable(cap):
        cap = cap()
    # Backend-enforced capability downgrade — surfaced as a top-level field.
    snapshot = getattr(a, "snapshot", lambda: {})() or {}
    return {
        "ok": True,
        "asOf": datetime.now(timezone.utc).isoformat(),
        "adapter": a.name,
        "configured": a.configured,
        "connected": a.connected,
        "capability": cap,
        "mode": cfg["liveMode"],
        "config": cfg,
        "liveSubmitEnabled": False,  # T10.1 invariant — never True in this sprint
        "lastSuccessfulHeartbeat": snapshot.get("lastSuccessfulHeartbeat"),
        "lastError": snapshot.get("lastError"),
        "version": "t10_2b.broker_readiness_bridge.v1",
    }


def list_balances() -> dict:
    a = _adapter_singleton()
    return a.fetch_balances()


def list_markets() -> dict:
    a = _adapter_singleton()
    return {
        "ok": True,
        "count": len(SUPPORTED_MARKETS),
        "markets": a.fetch_markets(),
    }


def heartbeat_probe() -> dict:
    """Run a single heartbeat probe and surface the result. Used by /heartbeat
    endpoint and by the periodic poller. Never raises."""
    a = _adapter_singleton()
    hb = getattr(a, "heartbeat", None)
    if hb is None:
        return {"ok": False, "note": "adapter does not expose heartbeat"}
    try:
        return hb()
    except Exception as e:
        return {"ok": False, "note": f"heartbeat_failed: {e!r}"}


# ── Preflight (pure validation; no order placed) ─────────────────────


def preflight(payload: dict, verdict: Optional[dict] = None) -> dict:
    """Validate a prospective order BEFORE any live submit.

    Inputs:
        payload: {symbol, action, sizeUsd, accountId?}
        verdict: optional verdict snapshot (if missing, we re-fetch)

    Returns:
        {
          ok: bool,
          symbol, action, sizeUsd,
          marketSupported, minNotionalOk, sizeOk, sideOk,
          quoteAssetNotionalUsd,
          checks: [{name, passed, detail}, ...],
          refusedReasons: [...],
          asOf,
        }

    Idempotent / side-effect free. Audit row is only written by
    `attempt_live_submit`, NOT here.
    """
    symbol = (payload.get("symbol") or "").upper().strip()
    action = (payload.get("action") or "").upper().strip()
    size_usd = float(payload.get("sizeUsd") or 0.0)

    checks: list[dict] = []
    reasons: list[str] = []

    def _check(name: str, passed: bool, detail: str = ""):
        checks.append({"name": name, "passed": passed, "detail": detail})
        if not passed:
            reasons.append(name + (f" ({detail})" if detail else ""))

    market = SUPPORTED_MARKETS.get(symbol)
    _check("market_supported", market is not None,
           detail=f"{symbol} not in curated market list" if market is None else "")

    _check("side_valid", action in ("LONG", "SHORT"),
           detail=f"action='{action}' must be LONG or SHORT")

    _check("size_positive", size_usd > 0,
           detail=f"sizeUsd={size_usd} must be > 0")

    if market is not None:
        min_notional = float(market["minNotionalUsd"])
        _check("min_notional", size_usd >= min_notional,
               detail=f"sizeUsd={size_usd} < min ${min_notional}")
    else:
        _check("min_notional", False, detail="market_unknown")

    return {
        "ok": all(c["passed"] for c in checks),
        "symbol": symbol,
        "action": action,
        "sizeUsd": size_usd,
        "marketSupported": market is not None,
        "minNotionalOk": (size_usd >= float(market["minNotionalUsd"])) if market else False,
        "sizeOk": size_usd > 0,
        "sideOk": action in ("LONG", "SHORT"),
        "marketInfo": market,
        "checks": checks,
        "refusedReasons": reasons,
        "asOf": datetime.now(timezone.utc).isoformat(),
    }


# ── Live submit gate (always refuses in T10.1) ───────────────────────


GATE_RULES = [
    "live_mode_enabled",
    "broker_configured",
    "broker_connected",
    "exchange_capability_verified",
    "user_risk_ack_signed",
    "paper_scheduler_healthy",
    "verdict_directional",
    "portfolio_gate_allowed",
    "drawdown_breaker_off",
    "calibration_sample_sufficient",
    "sizing_final_positive",
    "preflight_passed",
]


def _evaluate_live_gate(verdict: dict, preflight_result: dict) -> tuple[list[dict], list[str]]:
    """Return (checks, refusedReasons). All rules must pass to allow live submit."""
    cfg = broker_config()
    a = _adapter_singleton()

    # Pull paper scheduler state (cheap, in-process import)
    try:
        from services import paper_runtime_scheduler as sched
        sched_ok = bool(sched.status().get("enabled"))
    except Exception:
        sched_ok = False

    cap = getattr(a, "capability", "unconfigured")
    if callable(cap):
        cap = cap()

    gate_block = verdict.get("portfolioGate") or {}
    drawdown_block = gate_block.get("drawdown") or {}
    cal_block = verdict.get("calibration") or {}
    sizing_block = verdict.get("sizing") or {}
    action = (verdict.get("action") or "").upper()

    pairs: list[tuple[str, bool, str]] = [
        ("live_mode_enabled", cfg["liveMode"] == "live",
         f"BROKER_LIVE_MODE='{cfg['liveMode']}'"),
        ("broker_configured", a.configured, f"adapter={a.name}"),
        ("broker_connected", a.connected, "no successful exchange call yet"),
        # T10.2B — backend-enforced capability downgrade. Anything other than
        # readonly_verified blocks live submit irrespective of every other rule.
        ("exchange_capability_verified", cap == "readonly_verified",
         f"capability={cap}"),
        ("user_risk_ack_signed", cfg["riskAckSigned"],
         "BROKER_RISK_ACK_SIGNED not set"),
        ("paper_scheduler_healthy", sched_ok, "paper runtime not enabled"),
        ("verdict_directional", action in ("LONG", "SHORT"),
         f"action='{action}'"),
        ("portfolio_gate_allowed",
         (gate_block.get("finalPermission") == "allowed"),
         f"gate={gate_block.get('blockReason') or 'missing'}"),
        ("drawdown_breaker_off", not bool(drawdown_block.get("breakerActive")),
         "daily drawdown circuit breaker engaged"),
        ("calibration_sample_sufficient", int(cal_block.get("sample") or 0) >= 5,
         f"sample={cal_block.get('sample') or 0} < 5"),
        ("sizing_final_positive", float(sizing_block.get("final") or 0) > 0,
         f"sizing.final={sizing_block.get('final')}"),
        ("preflight_passed", bool(preflight_result.get("ok")),
         "; ".join(preflight_result.get("refusedReasons", []))),
    ]

    checks: list[dict] = []
    reasons: list[str] = []
    for name, passed, detail in pairs:
        checks.append({"name": name, "passed": bool(passed), "detail": detail if not passed else ""})
        if not passed:
            reasons.append(name + (f" ({detail})" if detail else ""))
    return checks, reasons


def _write_audit(doc: dict) -> str:
    audit_id = f"baud_{uuid.uuid4().hex[:12]}"
    doc["auditId"] = audit_id
    doc["attemptAt"] = datetime.now(timezone.utc).isoformat()
    broker_audit.insert_one({**doc})
    return audit_id


def attempt_live_submit(payload: dict) -> dict:
    """The ONLY entry point for prospective live orders.

    T10.1 invariant: ALWAYS refuses (no real orders placed) — even if
    every gate passed, we short-circuit with finalStatus='refused_t10_1_safe_mode'
    because the actual broker.submitOrder() call site is not wired yet.

    Returns:
        {
          ok: False,
          finalStatus: 'refused' | 'refused_t10_1_safe_mode',
          refusedReasons: [...],
          auditId,
          preflight,
          gateChecks,
          verdictSnapshot, sizingSnapshot, gateSnapshot,
        }
    """
    # Rebuild a fresh verdict using the in-process pipeline.
    symbol = (payload.get("symbol") or "").upper().strip()
    if not symbol:
        return {"ok": False, "error": "symbol_required"}

    from services import trading_runtime as svc
    verdict = svc.build_verdict(symbol)

    pre = preflight(payload, verdict=verdict)
    checks, reasons = _evaluate_live_gate(verdict, pre)
    all_passed = len(reasons) == 0

    # T10.1 safe-mode trip: even if everything passes, REFUSE explicitly.
    if all_passed:
        final_status = "refused_t10_1_safe_mode"
        reasons.append("t10_1_safe_mode_active (broker submit path not yet wired)")
    else:
        final_status = "refused"

    audit_doc = {
        "mode": broker_config()["liveMode"],
        "symbol": symbol,
        "action": (payload.get("action") or "").upper(),
        "requestedSizeUsd": float(payload.get("sizeUsd") or 0.0),
        "verdictSnapshot": {
            "action": verdict.get("action"),
            "confidence": verdict.get("confidence"),
            "risk": verdict.get("risk"),
            "alignmentScore": (verdict.get("alignment") or {}).get("score"),
        },
        "sizingSnapshot": {
            "final": (verdict.get("sizing") or {}).get("final"),
            "lifetimeWeight": (verdict.get("sizing") or {}).get("lifetimeWeight"),
            "regimeWeight": (verdict.get("sizing") or {}).get("regimeWeight"),
            "exposureWeight": (verdict.get("sizing") or {}).get("exposureWeight"),
            "uncertaintyPenalty": (verdict.get("sizing") or {}).get("uncertaintyPenalty"),
        },
        "gateSnapshot": {
            "permission": (verdict.get("portfolioGate") or {}).get("permission"),
            "blockReason": (verdict.get("portfolioGate") or {}).get("blockReason"),
            "drawdownPct": ((verdict.get("portfolioGate") or {}).get("drawdown") or {}).get("drawdownPct"),
            "cooldownActive": ((verdict.get("portfolioGate") or {}).get("cooldown") or {}).get("cooldownActive"),
        },
        "preflight": pre,
        "gateChecks": checks,
        "refusedReasons": reasons,
        "finalStatus": final_status,
        "brokerOrderId": None,
    }
    audit_id = _write_audit(audit_doc)

    return {
        "ok": False,
        "finalStatus": final_status,
        "refusedReasons": reasons,
        "auditId": audit_id,
        "preflight": pre,
        "gateChecks": checks,
        "verdictSnapshot": audit_doc["verdictSnapshot"],
        "sizingSnapshot": audit_doc["sizingSnapshot"],
        "gateSnapshot": audit_doc["gateSnapshot"],
        "asOf": datetime.now(timezone.utc).isoformat(),
    }


def list_audit(limit: int = 50) -> list[dict]:
    return list(broker_audit.find({}, {"_id": 0}).sort("attemptAt", DESCENDING).limit(limit))
