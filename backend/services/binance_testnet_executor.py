"""
T10.2C — Binance Spot Testnet Executor (execution semantics validation)

ARCHITECTURAL INVARIANTS (HARDCODED — NOT ENV, NOT CONFIG, NOT TOGGLEABLE):

  A. TESTNET_ONLY = True               (Python-level constant)
  B. SYMBOL_ALLOWLIST = {BTC/USDT}     (no ETH, no SOL, no futures, no margin)
  C. MAX_NOTIONAL_USD = 25.0           (backend-enforced hard cap)
  D. Every submit → immutable receipt + broker ack + transport status + lineageId
  E. No auto-resubmit ever             (unique(lineageId) at DB level)
  F. Failures = observational, NEVER self-healing

ARCHITECTURAL CONTRACT (frozen):

  * Single attempt per lineageId.  A second submit for the same lineageId
    raises CONFLICT — by design, retry is forbidden at the architecture
    layer, NOT at a config layer.
  * execution_receipts is APPEND-ONLY.  No update path exists in code.
    No reconciliation rewrites.  Every attempt is an immutable fact.
  * MOCK MODE and TESTNET MODE produce OBSERVATIONALLY IDENTICAL receipts
    (same schema, same status semantics, same lineage linkage, same
    persistence behavior).  Only `transport.mode` and `brokerAck.mock`
    differ, plus exchangeOrderId is synthetic in mock mode.
  * Failure-mode invariant: every preflight failure produces a receipt
    with status="preflight_fail" — failures are NEVER silently dropped.

NOT IN SCOPE (this sprint):

  * Mainnet, futures, margin, leverage, multi-symbol
  * Env-toggle to live, runtime API param to live
  * Retry engine, auto-resubmit, "fix-failed" path
  * Frontend submit UI, "go live" buttons, websocket streaming
"""
from __future__ import annotations

import os
import time
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING, DESCENDING

load_dotenv()

logger = logging.getLogger("t10_2c.testnet_executor")

# ── HARDCODED ARCHITECTURAL INVARIANTS ──────────────────────────────
# These MUST NOT become env vars, config flags, or runtime params.
# Changing any of them requires an explicit code change + a new sprint.
TESTNET_ONLY: bool = True
SYMBOL_ALLOWLIST: frozenset[str] = frozenset({"BTC/USDT", "BTCUSDT", "BTC"})
MAX_NOTIONAL_USD: float = 25.0
EXECUTION_PIPELINE_VERSION: str = "t6+t8+t9+t10+tier4c1+t10_2c"

# ── Storage ─────────────────────────────────────────────────────────
_client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
_db = _client[os.environ.get("DB_NAME", "test_database")]

execution_receipts = _db["execution_receipts"]
# APPEND-ONLY invariant enforced at DB level:
#   * unique(lineageId) — retry is forbidden architecturally
#   * idx by (createdAt desc) — efficient read for ledger
#   * idx by status — efficient filter for preflight/transport_error sieve
execution_receipts.create_index([("lineageId", ASCENDING)], unique=True)
execution_receipts.create_index([("createdAt", DESCENDING)])
execution_receipts.create_index([("status", ASCENDING)])

gate_decisions   = _db["gate_decisions"]
operator_access  = _db["operator_access"]
paper_positions  = _db["paper_positions_v2"]


# ── Status enum (locked to attribution-grade semantics) ─────────────
STATUS_SUBMITTED       = "submitted"        # broker accepted, real or mock
STATUS_PREFLIGHT_FAIL  = "preflight_fail"   # observational gate-side reject
STATUS_BROKER_REJECT   = "broker_reject"    # broker received and rejected
STATUS_TRANSPORT_ERROR = "transport_error"  # network/SDK error before broker

VALID_STATUSES = {
    STATUS_SUBMITTED,
    STATUS_PREFLIGHT_FAIL,
    STATUS_BROKER_REJECT,
    STATUS_TRANSPORT_ERROR,
}

# ── Mode resolution ─────────────────────────────────────────────────


def _resolve_mode() -> str:
    """Return 'testnet' if testnet credentials are present, else 'mock'.

    Mode is decided INSIDE the executor — never user-configurable,
    never frontend-toggleable, never a runtime API param.
    """
    key = (os.environ.get("BINANCE_TESTNET_API_KEY") or "").strip()
    sec = (os.environ.get("BINANCE_TESTNET_API_SECRET") or "").strip()
    return "testnet" if (key and sec) else "mock"


# ── Preflight ──────────────────────────────────────────────────────


def _normalise_symbol(sym: str) -> str:
    s = (sym or "").upper().strip()
    if s in ("BTC", "BTCUSDT"):
        return "BTC/USDT"
    return s


def _preflight(
    *, lineage_id: str, operator_user_id: str, symbol: str, size_usd: float,
) -> dict:
    """Returns {ok: bool, failedCheck: str|None, checks: dict, gate_row, op_row}.

    Five hardcoded checks — ordering is deliberate (cheapest first, most
    invariant-bound last).  Each check is observational; failure produces
    a receipt, never an exception that escapes."""
    checks: dict[str, bool] = {}

    # 1. Symbol allowlist
    sym_canon = _normalise_symbol(symbol)
    checks["symbolAllowed"] = sym_canon in SYMBOL_ALLOWLIST
    if not checks["symbolAllowed"]:
        return {"ok": False, "failedCheck": "symbolAllowed", "checks": checks,
                "gate_row": None, "op_row": None, "symbol": sym_canon}

    # 2. Notional cap
    try:
        size_f = float(size_usd)
    except (TypeError, ValueError):
        size_f = -1.0
    checks["notionalOk"] = (0.0 < size_f <= MAX_NOTIONAL_USD)
    if not checks["notionalOk"]:
        return {"ok": False, "failedCheck": "notionalOk", "checks": checks,
                "gate_row": None, "op_row": None, "symbol": sym_canon}

    # 3. Lineage check — gate must have allowed this decision
    gate_row = gate_decisions.find_one(
        {"lineageId": lineage_id},
        {"_id": 0},
    )
    checks["lineageOk"] = bool(
        gate_row and gate_row.get("permission") == "allowed"
    )
    if not checks["lineageOk"]:
        return {"ok": False, "failedCheck": "lineageOk", "checks": checks,
                "gate_row": gate_row, "op_row": None, "symbol": sym_canon}

    # 4. Operator authority — explicit live + console grants required
    op_row = operator_access.find_one(
        {"userId": operator_user_id},
        {"_id": 0},
    )
    has_live = bool(
        op_row
        and (op_row.get("liveAuthority") or {}).get("granted") is True
        and op_row.get("consoleAccess") is True
    )
    checks["authorityOk"] = has_live
    if not checks["authorityOk"]:
        return {"ok": False, "failedCheck": "authorityOk", "checks": checks,
                "gate_row": gate_row, "op_row": op_row, "symbol": sym_canon}

    # 5. Hardcoded testnet-only invariant — paranoia check (a code change
    # that flipped this constant would still get caught here).
    checks["testnetOnly"] = TESTNET_ONLY is True
    if not checks["testnetOnly"]:
        return {"ok": False, "failedCheck": "testnetOnly", "checks": checks,
                "gate_row": gate_row, "op_row": op_row, "symbol": sym_canon}

    return {"ok": True, "failedCheck": None, "checks": checks,
            "gate_row": gate_row, "op_row": op_row, "symbol": sym_canon}


# ── Mock + real transports ──────────────────────────────────────────


def _mock_submit(symbol: str, side: str, size_usd: float) -> dict:
    """Mock broker transport — deterministic, no network.

    Returns the SAME shape a real ccxt.binance().create_order would
    return (subset we care about), plus a `mock: True` marker."""
    now_ms = int(time.time() * 1000)
    mock_order_id = f"mock_{uuid.uuid4().hex[:12]}"
    # Synthetic fill price.  We pick the entry price as fill — caller
    # will pass `entry` for that. Tests use a fixed sentinel for
    # deterministic assertions.
    return {
        "transport": {
            "mode":        "mock",
            "status":      "ok",
            "latencyMs":   0,
            "errorCode":   None,
            "errorMessage": None,
        },
        "brokerAck": {
            "mock":            True,
            "exchangeOrderId": None,            # mock has no real id
            "mockOrderId":     mock_order_id,
            "filledQty":       round(size_usd / 100_000.0, 8),  # rough qty
            "avgFillPrice":    None,            # mock leaves price null
            "raw": {
                "id":     mock_order_id,
                "symbol": symbol,
                "side":   side.upper(),
                "type":   "MARKET",
                "amount": round(size_usd / 100_000.0, 8),
                "status": "open",
                "timestamp": now_ms,
                "_synthetic": True,
            },
        },
        "status": STATUS_SUBMITTED,
    }


def _testnet_submit(symbol: str, side: str, size_usd: float) -> dict:
    """Real Binance Spot Testnet transport via ccxt.

    Single-attempt only.  No retries.  On any exception we record a
    transport_error receipt; on broker-side reject we record a
    broker_reject receipt.  Both are observational."""
    import ccxt  # local import — never load at module level
    t0 = time.time()
    try:
        ex = ccxt.binance({
            "apiKey":   os.environ["BINANCE_TESTNET_API_KEY"],
            "secret":   os.environ["BINANCE_TESTNET_API_SECRET"],
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })
        # CCXT convention for binance spot testnet:
        ex.set_sandbox_mode(True)
        # Use a market price reference for size→qty conversion.
        ticker = ex.fetch_ticker(symbol)
        price = float(ticker.get("last") or ticker.get("close") or 0.0)
        if price <= 0:
            raise RuntimeError("no_ticker_price")
        qty = round(size_usd / price, 6)
        order = ex.create_order(symbol, "market", side.lower(), qty)
        latency_ms = int((time.time() - t0) * 1000)
        return {
            "transport": {
                "mode":        "testnet",
                "status":      "ok",
                "latencyMs":   latency_ms,
                "errorCode":   None,
                "errorMessage": None,
            },
            "brokerAck": {
                "mock":            False,
                "exchangeOrderId": str(order.get("id") or ""),
                "mockOrderId":     None,
                "filledQty":       float(order.get("filled") or 0.0),
                "avgFillPrice":    float(order.get("average") or order.get("price") or 0.0) or None,
                "raw":             order,
            },
            # Map ccxt status → our canonical status.
            "status": (
                STATUS_BROKER_REJECT
                if (order.get("status") or "").lower() in ("rejected", "canceled")
                else STATUS_SUBMITTED
            ),
        }
    except Exception as e:  # noqa: BLE001
        latency_ms = int((time.time() - t0) * 1000)
        return {
            "transport": {
                "mode":        "testnet",
                "status":      "error",
                "latencyMs":   latency_ms,
                "errorCode":   type(e).__name__,
                "errorMessage": str(e)[:300],
            },
            "brokerAck": {
                "mock":            False,
                "exchangeOrderId": None,
                "mockOrderId":     None,
                "filledQty":       0.0,
                "avgFillPrice":    None,
                "raw":             None,
            },
            "status": STATUS_TRANSPORT_ERROR,
        }


# ── Public entry point ─────────────────────────────────────────────


class TestnetExecutorConflict(Exception):
    """A receipt for this lineageId already exists.  Architecturally
    retries are forbidden — second submit MUST not silently overwrite."""


def submit_testnet_order(
    *,
    lineage_id: str,
    operator_user_id: str,
    symbol: str,
    side: str,
    size_usd: float,
    submitted_by: str = "admin",
) -> dict:
    """Single immutable execution attempt.

    Returns the persisted receipt dict.  Never raises on preflight or
    broker failures — those produce observational receipts.  Raises
    TestnetExecutorConflict ONLY if a receipt already exists for this
    lineageId (architectural retry-forbidden invariant)."""
    # ── Architectural retry-forbidden invariant ────────────────────
    # We check BEFORE doing any work — saves a broker call on retry.
    if execution_receipts.count_documents({"lineageId": lineage_id}, limit=1) > 0:
        raise TestnetExecutorConflict(
            f"execution receipt already exists for lineageId={lineage_id}"
        )

    side_norm = (side or "").upper()
    pf = _preflight(
        lineage_id=lineage_id,
        operator_user_id=operator_user_id,
        symbol=symbol,
        size_usd=size_usd,
    )

    receipt_id = f"rcpt_{uuid.uuid4().hex[:12]}"
    started_at = datetime.now(timezone.utc).isoformat()
    mode = _resolve_mode()

    if not pf["ok"]:
        receipt = {
            "receiptId":       receipt_id,
            "lineageId":       lineage_id,
            "pipelineVersion": EXECUTION_PIPELINE_VERSION,
            "symbol":          pf["symbol"],
            "side":            side_norm,
            "sizeUsd":         size_usd,
            "operatorUserId":  operator_user_id,
            "submittedBy":     submitted_by,
            "preflight":       pf["checks"],
            "failedCheck":     pf["failedCheck"],
            "brokerAck":       None,
            "transport": {
                "mode":        mode,
                "status":      "not_attempted",
                "latencyMs":   0,
                "errorCode":   None,
                "errorMessage": None,
            },
            "status":          STATUS_PREFLIGHT_FAIL,
            "submittedAt":     started_at,
            "completedAt":     started_at,
            "createdAt":       started_at,
        }
        _insert_immutable(receipt)
        return receipt

    # Preflight passed → attempt transport.  Single attempt, no retry.
    if mode == "mock":
        transport_result = _mock_submit(pf["symbol"], side_norm, size_usd)
    else:
        transport_result = _testnet_submit(pf["symbol"], side_norm, size_usd)

    completed_at = datetime.now(timezone.utc).isoformat()
    receipt = {
        "receiptId":       receipt_id,
        "lineageId":       lineage_id,
        "pipelineVersion": EXECUTION_PIPELINE_VERSION,
        "symbol":          pf["symbol"],
        "side":            side_norm,
        "sizeUsd":         size_usd,
        "operatorUserId":  operator_user_id,
        "submittedBy":     submitted_by,
        "preflight":       pf["checks"],
        "failedCheck":     None,
        "brokerAck":       transport_result["brokerAck"],
        "transport":       transport_result["transport"],
        "status":          transport_result["status"],
        "submittedAt":     started_at,
        "completedAt":     completed_at,
        "createdAt":       started_at,
    }
    _insert_immutable(receipt)
    return receipt


def _insert_immutable(receipt: dict) -> None:
    """Single-shot insert.  The unique(lineageId) index guarantees no
    duplicate row even under racing concurrent calls."""
    try:
        execution_receipts.insert_one({**receipt})
    except Exception as e:  # noqa: BLE001
        # Convert duplicate-key into the architectural conflict signal.
        if "duplicate key" in str(e).lower() or "E11000" in str(e):
            raise TestnetExecutorConflict(
                f"execution receipt already exists for lineageId={receipt['lineageId']}"
            ) from e
        # Anything else is genuinely unexpected — log and re-raise.
        # An ABSENT receipt is worse than a misfiled one, so we don't
        # swallow this.
        logger.error(f"[t10_2c] receipt insert failed: {e}")
        raise


# ── Read-only listing helpers (used by route layer) ────────────────


def list_receipts(limit: int = 50) -> list[dict]:
    return list(
        execution_receipts.find({}, {"_id": 0}).sort("createdAt", -1).limit(int(limit))
    )


def get_receipt(receipt_id: str) -> Optional[dict]:
    return execution_receipts.find_one({"receiptId": receipt_id}, {"_id": 0})


def get_receipt_by_lineage(lineage_id: str) -> Optional[dict]:
    return execution_receipts.find_one({"lineageId": lineage_id}, {"_id": 0})
