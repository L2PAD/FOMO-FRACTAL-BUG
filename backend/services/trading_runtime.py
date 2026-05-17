"""
Trading Runtime — Native FastAPI module (T1).

Replaces the retired Trading Terminal side-car with cognition-native logic:
  * fuses TA + sentiment + fractal into a trading verdict
  * derives entry / stop / target from real structure levels
  * runs paper-trading book against live prices
  * NO external broker, NO :8002 side-car, NO HTTP shim

The verdict engine reads ONLY in-process cognition state (no HTTP loop-back).
"""
from __future__ import annotations

import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pymongo import MongoClient, DESCENDING

load_dotenv(Path(__file__).parent.parent / ".env", override=False)
logger = logging.getLogger("trading_runtime")

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "test_database")

_client = MongoClient(MONGO_URL)
_db = _client[DB_NAME]

paper_accounts = _db["paper_accounts_v2"]
paper_orders = _db["paper_orders_v2"]
paper_positions = _db["paper_positions_v2"]
paper_events = _db["paper_events_v2"]
# T11.1c — canonical outcome ledger for attribution.  Written exactly
# ONCE per closed position (unique key by positionId).  IMMUTABLE
# forward-only — no retroactive writes, no backfill.
paper_outcomes = _db["paper_outcomes"]

paper_accounts.create_index([("accountId", 1)], unique=True)
paper_orders.create_index([("accountId", 1), ("createdAt", DESCENDING)])
paper_positions.create_index([("accountId", 1), ("status", 1)])
paper_positions.create_index([("symbol", 1), ("status", 1)])
paper_events.create_index([("ts", DESCENDING)])
# T11.1c — idempotency invariant: a close MUST NOT duplicate outcome.
paper_outcomes.create_index([("positionId", 1)], unique=True)
paper_outcomes.create_index([("lineageId", 1)])
paper_outcomes.create_index([("symbol", 1), ("closedAt", DESCENDING)])
paper_outcomes.create_index([("closedAt", DESCENDING)])


def _write_paper_outcome_t11_1c(
    closed_pos: dict,
    close_price: float,
    pnl_usd: float,
    pnl_pct: float,
    reason: str,
    detection_mode: str,
) -> Optional[str]:
    """T11.1c — Forward-only outcome writer.

    Writes one immutable row per closed position into `paper_outcomes`
    so the attribution layer can derive raw/calibrated/sized/gated
    aggregates against ACTUAL closed lifecycles (not just gate
    decisions).

    INVARIANTS (load-bearing):
      * IDEMPOTENT — uses positionId as unique key.  Closing the same
        position twice (e.g. concurrent scheduler + manual) MUST NOT
        write two rows.  Returns None on duplicate.
      * FORWARD-ONLY — if the position was opened BEFORE T11.1c (no
        lineageId on the position doc) we DO NOT write a paper_outcomes
        row.  Old positions remain honestly partial; we never fabricate
        a lineage retrospectively.  Returns None.
      * IMMUTABLE — once written, the row is never updated (no PATCH
        / no UPSERT to existing).  Attribution reads it as-is.
      * NEVER MUTATES the trading flow — wrapped in try/except so a
        write failure cannot break the close path.
    """
    try:
        lineage_id = closed_pos.get("lineageId")
        if not lineage_id:
            # Forward-only: pre-T11.1c position → skip silently.
            return None
        # Already written?  (idempotency by positionId)
        existing = paper_outcomes.find_one({"positionId": closed_pos["positionId"]}, {"_id": 0, "outcomeId": 1})
        if existing:
            return existing.get("outcomeId")
        outcome_id = f"out_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        verdict_snapshot = closed_pos.get("verdictSnapshot") or {}
        raw_snapshot = verdict_snapshot.get("rawVerdictSnapshot") if isinstance(verdict_snapshot, dict) else None
        # Compute barsHeld in minutes (approximate — for attribution
        # we just need a magnitude, not exact tick precision).
        bars_held = None
        try:
            opened = datetime.fromisoformat(
                str(closed_pos.get("openedAt") or now).replace("Z", "+00:00")
            )
            closed = datetime.fromisoformat(str(now).replace("Z", "+00:00"))
            bars_held = max(0, int((closed - opened).total_seconds() / 60))
        except Exception:
            bars_held = 0
        outcome_doc = {
            "outcomeId":       outcome_id,
            "positionId":      closed_pos["positionId"],
            "orderId":         closed_pos.get("orderId"),
            "accountId":       closed_pos.get("accountId"),
            "lineageId":       lineage_id,
            "pipelineVersion": closed_pos.get("pipelineVersion"),
            "symbol":          closed_pos.get("symbol"),
            "side":            closed_pos.get("side"),
            "entry":           closed_pos.get("entryPrice"),
            "stop":            closed_pos.get("stopPrice"),
            "target":          closed_pos.get("targetPrice"),
            "exit":            round(float(close_price), 4),
            "sizeUsd":         closed_pos.get("sizeUsd"),
            "pnlUsd":          round(float(pnl_usd), 4),
            "pnlPct":          round(float(pnl_pct), 4),
            "outcome":         "win" if pnl_usd > 0 else "loss",
            "barsHeld":        bars_held,
            "openedAt":        closed_pos.get("openedAt"),
            "closedAt":        closed_pos.get("closedAt") or now,
            "closeReason":     reason,
            "detectionMode":   detection_mode,
            # Carry the immutable snapshots so attribution never needs
            # to JOIN against paper_positions_v2 / paper_orders_v2 to
            # reconstruct lineage.
            "verdictSnapshot":     verdict_snapshot,
            "rawVerdictSnapshot":  raw_snapshot,
            "createdAt":           now,
        }
        try:
            paper_outcomes.insert_one({**outcome_doc})
        except Exception as dup_err:
            # Race-condition idempotency (unique-key collision).  This
            # is the expected outcome of two concurrent close paths
            # touching the same position — NOT an error.
            if "duplicate key" in str(dup_err).lower() or "E11000" in str(dup_err):
                existing = paper_outcomes.find_one({"positionId": closed_pos["positionId"]}, {"_id": 0, "outcomeId": 1})
                return existing.get("outcomeId") if existing else None
            raise
        return outcome_id
    except Exception as e:
        logger.warning(f"[trading_runtime] T11.1c paper_outcomes write failed: {e}")
        return None

DEFAULT_ACCOUNT_ID = "default-paper-account"
DEFAULT_STARTING_BALANCE_USD = 10_000.0
DEFAULT_RISK_PER_TRADE_PCT = 1.0  # 1% of equity per trade


# ── Cognition fusion ──────────────────────────────────────────────────


def _direction_to_bias(d: Optional[str]) -> str:
    """Normalize cognition direction → trading bias."""
    if not d:
        return "WAIT"
    d = str(d).upper()
    if d in ("LONG", "LONG_BIAS", "BULLISH"):
        return "LONG"
    if d in ("SHORT", "SHORT_BIAS", "BEARISH"):
        return "SHORT"
    return "WAIT"


# ── P1-A · Symbol normalization (Stage A · forensic root-cause fix) ──
# Aggregator readers (_fetch_*) and the substrate writers
# (exchange_forecasts, fractal_native_v1, native_ta_v1, onchain_metrics,
# sentiment_runtime) are keyed on the bare ticker ("BTC", "ETH", …).
# Routes are called from clients with exchange-form symbols ("BTCUSDT",
# "ETH-USD", "SOL-PERP"). Without normalization, 4 of 5 modules would
# falsely deграйде just because of symbol format. This canonicalizer is
# the single source of truth for the input→canonical mapping inside the
# consensus engine. Everything downstream of build_verdict() stays
# canonical, so paper-trading / lineage / attribution remain coherent.
_CANONICAL_SUFFIXES = (
    "-PERPETUAL", "-PERP", "PERP",
    "-USDT", "USDT",
    "-USDC", "USDC",
    "-USD",  "USD",
    "-BUSD", "BUSD",
    "-FDUSD", "FDUSD",
    "-USDP", "USDP",
    "-DAI",  "DAI",
)


def _canonical_symbol(s: Optional[str]) -> str:
    """Strip common exchange quote suffixes → bare ticker.

    Examples:
      BTCUSDT     → BTC
      ETH-USD     → ETH
      SOL-PERP    → SOL
      BTC         → BTC  (no-op)
      DOGEUSDC    → DOGE
    Order matters: longer suffixes first so we don't strip "USD" off
    "USDC" or "USDT".
    """
    if not s:
        return ""
    out = str(s).upper().strip()
    # Strip a single matching suffix (longest match wins).
    for suf in _CANONICAL_SUFFIXES:
        if out.endswith(suf) and len(out) > len(suf):
            out = out[: -len(suf)]
            # Some venues use a separator before quote (BTC-USD, BTC_USDT).
            while out and out[-1] in ("-", "_", "/", ":"):
                out = out[:-1]
            break
    return out


def _fetch_exchange(symbol: str) -> dict:
    """
    TRADING-ACTIVATION-4 · Read latest exchange forecast snapshot.
    Maps direction → LONG/SHORT/WAIT bias for the 5-module vote.
    """
    sym = symbol.upper()
    try:
        # Prefer the most recent forecast in our canonical collection
        fc = _db["exchange_forecasts"].find_one(
            {"asset": sym}, {"_id": 0}, sort=[("createdAt", DESCENDING)]
        )
        if fc:
            return fc
    except Exception as e:
        logger.warning(f"[trading_runtime] exchange fetch fallback for {sym}: {e}")
    return {}


def _fetch_onchain(symbol: str) -> dict:
    """
    TRADING-ACTIVATION-4 · Read on-chain metrics — **per-symbol first**, then
    chain-level fallback.  The per-asset doc (PROD-GAP-3) is keyed by `symbol`
    and built from cryptorank + hyperliquid + ccxt momentum.  If absent, fall
    back to the legacy chain-level (`chain:"ethereum"`) snapshot so we never
    regress the consensus.
    """
    sym = symbol.upper()
    try:
        # 1. Per-asset snapshot (preferred — PROD-GAP-3)
        per = _db["onchain_metrics"].find_one(
            {"symbol": sym}, {"_id": 0}, sort=[("createdAt", DESCENDING)]
        )
        if per:
            return per
        # 2. Legacy chain-level snapshot (Ethereum macro)
        snap = _db["onchain_metrics"].find_one(
            {"chain": "ethereum"}, {"_id": 0}, sort=[("createdAt", DESCENDING)]
        )
        if snap:
            return snap
    except Exception as e:
        logger.warning(f"[trading_runtime] onchain fetch fallback for {symbol}: {e}")
    return {}


def _fetch_ta(symbol: str) -> dict:
    """Read latest native TA snapshot directly from in-process service."""
    try:
        from services.technical_analysis import analyze as _ta_analyze
        return _ta_analyze(symbol.upper()) or {}
    except Exception as e:
        logger.warning(f"[trading_runtime] TA fetch fallback for {symbol}: {e}")
    snap = _db["ta_snapshots"].find_one(
        {"symbol": symbol.upper()}, {"_id": 0}, sort=[("asOf", DESCENDING)]
    )
    return snap or {}


def _fetch_sentiment(symbol: str) -> dict:
    """Read latest sentiment verdict from runtime service."""
    try:
        from services.sentiment_runtime import runtime as _sent_runtime
        return _sent_runtime(symbol.upper()) or {}
    except Exception as e:
        logger.warning(f"[trading_runtime] sentiment fallback for {symbol}: {e}")
    snap = _db["sentiment_runtime_snapshots"].find_one(
        {"symbol": symbol.upper()}, {"_id": 0}, sort=[("asOf", DESCENDING)]
    )
    return snap or {}


def _fetch_fractal(symbol: str) -> dict:
    """Read latest fractal runtime snapshot."""
    try:
        from services.fractal_runtime import runtime as _frac_runtime
        return _frac_runtime(symbol.upper()) or {}
    except Exception as e:
        logger.warning(f"[trading_runtime] fractal fallback for {symbol}: {e}")
    snap = _db["fractal_runtime_snapshots"].find_one(
        {"symbol": symbol.upper()}, {"_id": 0}, sort=[("asOf", DESCENDING)]
    )
    return snap or {}


def _current_price(symbol: str, ta: dict) -> float:
    """Best-effort current price: TA → observations → exchange_forecasts."""
    if ta.get("currentPrice"):
        return float(ta["currentPrice"])
    obs = _db["observations"].find_one(
        {"symbol": symbol.upper()},
        {"_id": 0, "price": 1},
        sort=[("timestamp", DESCENDING)],
    )
    if obs and obs.get("price"):
        return float(obs["price"])
    fc = _db["exchange_forecasts"].find_one(
        {"asset": symbol.upper()},
        {"_id": 0, "entry": 1},
        sort=[("createdAt", DESCENDING)],
    )
    return float(fc.get("entry", 0)) if fc else 0.0


# ── Verdict engine ────────────────────────────────────────────────────


def _classify_module_health(name: str, raw: dict, db) -> dict:
    """
    P0 SIGNAL HYGIENE · honest per-module degradation classifier.

    Returns: {degraded: bool, reason: str|None}

    Rule of the house: if a module cannot produce a signal that is
    independent of the other modules and grounded in primary data, it
    MUST be marked degraded and abstain from the vote.  A degraded
    module is NOT a WAIT vote — it is silence.

    Honest degradation rules per module:
      sentiment: degraded if the sentiment substrate is dominated by
                 headlines with empty `llm_analysis` and defaulted
                 score=0.5 (no real NLP confirmation).  This catches
                 the "RSS headlines defaulted to bullish" failure mode.
      fractal:   degraded if there is no `intelligence_telemetry` for
                 the asset — fractal then falls back to
                 `decision_history`, which is exchange-derived → the
                 vote becomes circular and must not count.
      onchain:   degraded if neither `onchain_metrics` nor
                 `onchain_events` collection exists / has data, OR if
                 the payload itself is empty.  Currently always
                 degraded until RPC keys are provisioned.
      exchange:  degraded if no exchange_forecast for the asset within
                 24h (stale model output cannot be used as fresh vote).
      ta:        degraded if TA cannot produce structural levels
                 (support/resistance both null/zero) — without
                 levels the TA opinion is unfounded.
    """
    name = (name or "").lower()
    try:
        if name == "sentiment":
            # Examine substrate quality on top of runtime's own degraded flag.
            if not raw or raw.get("ok") is False or raw.get("degraded") is True:
                return {"degraded": True, "reason": "sentiment_runtime_self_degraded"}
            try:
                cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
                total_recent = db.sentiment_events.count_documents({"createdAt": {"$gte": cutoff}})
                if total_recent == 0:
                    return {"degraded": True, "reason": "no_sentiment_events_24h"}
                defaulted = db.sentiment_events.count_documents({
                    "createdAt": {"$gte": cutoff},
                    "weightedScore": 0.5,
                    "$or": [
                        {"raw.llm_analysis": {}},
                        {"raw.llm_analysis": {"$exists": False}},
                    ],
                })
                defaulted_share = defaulted / max(total_recent, 1)
                if defaulted_share >= 0.70:
                    return {
                        "degraded": True,
                        "reason": "inferred_only_no_primary_sentiment_confirmation",
                    }
            except Exception as e:
                return {"degraded": True, "reason": f"sentiment_substrate_check_failed_{type(e).__name__}"}
            return {"degraded": False, "reason": None}

        if name == "fractal":
            if not raw or raw.get("ok") is False or raw.get("state") in ("unavailable", "empty"):
                return {"degraded": True, "reason": "fractal_runtime_unavailable"}
            # P1 · Fractal is "honest active" ONLY if the underlying
            # source is fractal_native_v1 (recurrence / analog engine).
            # If the runtime fell back to anything else (decision_history
            # echo, snapshot_memory, regime-only context) we treat the
            # vote as circular / non-independent and abstain.
            src = str(raw.get("source") or "").lower()
            if src != "fractal_native_v1":
                return {
                    "degraded": True,
                    "reason": f"circular_or_non_native_fractal_source_{src or 'unknown'}",
                }
            return {"degraded": False, "reason": None}

        if name == "onchain":
            try:
                cols = set(db.list_collection_names())
                has_metrics = "onchain_metrics" in cols and db.onchain_metrics.estimated_document_count() > 0
                has_events = "onchain_events" in cols and db.onchain_events.estimated_document_count() > 0
                if not (has_metrics or has_events):
                    return {"degraded": True, "reason": "no_onchain_metrics_available"}
            except Exception as e:
                return {"degraded": True, "reason": f"onchain_substrate_check_failed_{type(e).__name__}"}
            if not raw:
                return {"degraded": True, "reason": "onchain_payload_empty"}
            return {"degraded": False, "reason": None}

        if name == "exchange":
            if not raw:
                return {"degraded": True, "reason": "no_exchange_forecast_available"}
            ts = raw.get("createdAt")
            # createdAt can be unix-ms int or ISO string; tolerate both.
            try:
                if isinstance(ts, (int, float)):
                    age_h = (datetime.now(timezone.utc).timestamp() * 1000 - float(ts)) / 1000 / 3600
                elif isinstance(ts, str):
                    age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(ts.replace("Z", "+00:00"))).total_seconds() / 3600
                else:
                    age_h = None
            except Exception:
                age_h = None
            if age_h is not None and age_h > 24:
                return {"degraded": True, "reason": "exchange_forecast_stale_over_24h"}
            return {"degraded": False, "reason": None}

        if name == "ta":
            if not raw:
                return {"degraded": True, "reason": "ta_runtime_empty"}
            sup = float(raw.get("support") or 0.0)
            res = float(raw.get("resistance") or 0.0)
            if sup <= 0 and res <= 0:
                return {"degraded": True, "reason": "ta_structural_levels_missing"}
            return {"degraded": False, "reason": None}

    except Exception as e:
        return {"degraded": True, "reason": f"classifier_error_{type(e).__name__}"}

    return {"degraded": False, "reason": None}


def build_verdict(symbol: str) -> dict:
    """
    P0 SIGNAL HYGIENE · Fuse 5 core modules into a trading verdict, but
    only count votes from modules whose data is actually independent
    and primary.  Degraded modules ABSTAIN — they do NOT vote WAIT,
    they vote nothing.

    Decision rule:
      - need ≥3 ACTIVE (non-degraded) modules
      - within active set, majority must agree (≥ ceil(activeCount/2)+1
        for clean majority, OR ≥3 directionally)
      - avg confidence of agreers ≥ 0.45
      - else WAIT with explicit blocker

    P1-A · Symbol normalization (forensic Stage A fix):
    Input may arrive in any exchange form (BTCUSDT, ETH-USD, SOL-PERP).
    We canonicalize ONCE here, and every downstream reader (_fetch_*,
    classifier, lineage, paper-trading hooks) operates on the bare
    ticker. The original input form is preserved in `inputSymbol` so
    clients can correlate their request with the verdict.
    """
    input_symbol = (symbol or "").strip()
    canonical = _canonical_symbol(input_symbol)
    sym = canonical  # internal contract: everything below is canonical
    ta = _fetch_ta(sym)
    sent = _fetch_sentiment(sym)
    frac = _fetch_fractal(sym)
    exch = _fetch_exchange(sym)
    onch = _fetch_onchain(sym)

    ta_bias = _direction_to_bias(ta.get("direction"))
    sent_bias = _direction_to_bias(sent.get("direction"))
    frac_bias = _direction_to_bias(frac.get("direction"))
    exch_bias = _direction_to_bias(exch.get("direction"))
    onch_bias = _direction_to_bias(onch.get("direction"))

    ta_conf = float(ta.get("confidence") or 0.0)
    sent_conf = float(sent.get("confidence") or 0.0)
    frac_conf = float(frac.get("confidence") or 0.0)
    exch_conf = float(exch.get("confidence") or 0.0)
    onch_conf = float(onch.get("confidence") or 0.0)

    # ── P0 SIGNAL HYGIENE: classify each module before counting votes
    raw_payloads = {
        "ta": ta, "sentiment": sent, "fractal": frac,
        "exchange": exch, "onchain": onch,
    }
    health = {name: _classify_module_health(name, payload, _db) for name, payload in raw_payloads.items()}

    price = _current_price(sym, ta)
    support = float(ta.get("support") or 0.0)
    resistance = float(ta.get("resistance") or 0.0)

    # Per-module: bias + confidence + active/abstain flag.
    module_biases = {
        "ta":        (ta_bias,   ta_conf),
        "sentiment": (sent_bias, sent_conf),
        "fractal":   (frac_bias, frac_conf),
        "exchange":  (exch_bias, exch_conf),
        "onchain":   (onch_bias, onch_conf),
    }

    # Degraded modules ABSTAIN (silence ≠ WAIT-vote).
    active_modules = [m for m, h in health.items() if not h["degraded"]]
    abstained_modules = [m for m, h in health.items() if h["degraded"]]
    degraded_modules = list(abstained_modules)  # alias for clarity in surface

    # Vote tally — ONLY over active modules.
    active_biases = {m: module_biases[m] for m in active_modules}
    long_votes = sum(1 for (b, _c) in active_biases.values() if b == "LONG")
    short_votes = sum(1 for (b, _c) in active_biases.values() if b == "SHORT")
    wait_votes = sum(1 for (b, _c) in active_biases.values() if b == "WAIT")
    active_count = len(active_modules)

    reasons: list[str] = []
    blocked_by: list[str] = []

    # P0 policy: need ≥3 active modules AND majority within active.
    MIN_ACTIVE_FOR_DECISION = 3
    action = "WAIT"
    chosen_confs: list[float] = []

    if active_count < MIN_ACTIVE_FOR_DECISION:
        blocked_by.append(
            f"insufficient_independent_active_modules ({active_count}/5 active · "
            f"{len(abstained_modules)} abstained)"
        )
    else:
        # Need strict majority within active set (more than half).
        majority_in_active = (active_count // 2) + 1
        if long_votes >= majority_in_active and short_votes == 0:
            chosen_confs = [c for (b, c) in active_biases.values() if b == "LONG"]
            avg = sum(chosen_confs) / max(len(chosen_confs), 1)
            if avg >= 0.45:
                action = "LONG"
                reasons.append(
                    f"{long_votes}/{active_count} active modules aligned LONG (avg conf {avg:.2f})"
                )
            else:
                blocked_by.append(f"LONG agreement weak (avg conf {avg:.2f} < 0.45)")
        elif short_votes >= majority_in_active and long_votes == 0:
            chosen_confs = [c for (b, c) in active_biases.values() if b == "SHORT"]
            avg = sum(chosen_confs) / max(len(chosen_confs), 1)
            if avg >= 0.45:
                action = "SHORT"
                reasons.append(
                    f"{short_votes}/{active_count} active modules aligned SHORT (avg conf {avg:.2f})"
                )
            else:
                blocked_by.append(f"SHORT agreement weak (avg conf {avg:.2f} < 0.45)")
        else:
            if long_votes > 0 and short_votes > 0:
                blocked_by.append("active modules split between LONG and SHORT")
            elif wait_votes >= majority_in_active:
                blocked_by.append(
                    f"{wait_votes}/{active_count} active modules WAIT — no directional majority"
                )
            else:
                blocked_by.append(
                    f"no directional majority in active set ({long_votes}L/{short_votes}S/{wait_votes}W of {active_count})"
                )

    # Always surface abstentions as transparent blockers
    if abstained_modules:
        blocked_by.append(
            "degraded_modules_abstained: " + ", ".join(
                f"{m}({health[m]['reason']})" for m in abstained_modules
            )
        )

    # Per-module reasoning hooks
    if ta.get("reasons"):
        reasons.append(f"TA: {'; '.join(ta['reasons'][:2])}")
    if sent.get("reason"):
        r = sent["reason"] if isinstance(sent["reason"], list) else [sent["reason"]]
        reasons.append(f"Sentiment: {'; '.join(r[:2])}")
    if frac.get("reasons"):
        reasons.append(f"Fractal: {'; '.join(frac['reasons'][:2])}")

    # Structure-derived levels
    entry: Optional[float] = None
    stop: Optional[float] = None
    target: Optional[float] = None
    rr: Optional[float] = None
    size_usd: Optional[float] = None
    risk_band = "N/A"

    if action != "WAIT" and price > 0:
        entry = round(price, 2)
        if action == "LONG":
            stop = round(support, 2) if support > 0 and support < price else round(price * 0.97, 2)
            target = round(resistance, 2) if resistance > 0 and resistance > price else round(price * 1.06, 2)
            if stop and stop >= entry:
                stop = round(entry * 0.97, 2)
                reasons.append("stop fallback: 3% below entry (structure level invalid)")
        else:  # SHORT
            stop = round(resistance, 2) if resistance > 0 and resistance > price else round(price * 1.03, 2)
            target = round(support, 2) if support > 0 and support < price else round(price * 0.94, 2)
            if stop and stop <= entry:
                stop = round(entry * 1.03, 2)
                reasons.append("stop fallback: 3% above entry (structure level invalid)")

        # RR
        if entry and stop and target:
            risk_per_unit = abs(entry - stop)
            reward_per_unit = abs(target - entry)
            rr = round(reward_per_unit / risk_per_unit, 2) if risk_per_unit > 0 else None
            if rr is not None and rr < 1.5:
                blocked_by.append(f"R:R {rr} below threshold 1.5")

        # Size based on equity × risk pct
        acc = _ensure_account(DEFAULT_ACCOUNT_ID)
        equity = float(acc.get("equityUsd", DEFAULT_STARTING_BALANCE_USD))
        risk_usd = equity * (DEFAULT_RISK_PER_TRADE_PCT / 100.0)
        if entry and stop:
            unit_risk = abs(entry - stop) / entry
            if unit_risk > 0:
                size_usd = round(risk_usd / unit_risk, 2)

        # Risk band
        avg_conf = sum(chosen_confs) / max(len(chosen_confs), 1)
        if avg_conf >= 0.70:
            risk_band = "LOW"
        elif avg_conf >= 0.55:
            risk_band = "MED"
        else:
            risk_band = "HIGH"

    overall_conf = round(
        (ta_conf + sent_conf + frac_conf + exch_conf + onch_conf) / 5.0, 3
    ) if (ta_conf or sent_conf or frac_conf or exch_conf or onch_conf) else 0.0

    # Alignment score now computed over ACTIVE modules only (abstain ≠ vote)
    alignment_score = round(
        (long_votes - short_votes) / max(active_count, 1), 3
    ) if active_count > 0 else 0.0

    base_verdict = {
        "symbol": sym,
        "inputSymbol": input_symbol or sym,
        "canonicalSymbol": sym,
        "action": action,
        "entry": entry,
        "stop": stop,
        "target": target,
        "rr": rr,
        "risk": risk_band,
        "sizeUsd": size_usd,
        "confidence": overall_conf,
        "reasons": reasons,
        "blockedBy": blocked_by,
        "alignment": {
            # 5 core modules — emit per-module bias for visibility, but
            # active modules are the only ones that contributed a vote.
            "ta":        ta_bias if "ta" in active_modules else "ABSTAIN",
            "sentiment": sent_bias if "sentiment" in active_modules else "ABSTAIN",
            "fractal":   frac_bias if "fractal" in active_modules else "ABSTAIN",
            "exchange":  exch_bias if "exchange" in active_modules else "ABSTAIN",
            "onchain":   onch_bias if "onchain" in active_modules else "ABSTAIN",
            # Active-only vote tally
            "longVotes":  long_votes,
            "shortVotes": short_votes,
            "waitVotes":  wait_votes,
            "score":      alignment_score,
            # P0 SIGNAL HYGIENE · transparency over the active set
            "activeVotes":       active_count,
            "activeModules":     active_modules,
            "abstainedModules":  abstained_modules,
            "degradedModules":   degraded_modules,
            "minActiveForDecision": MIN_ACTIVE_FOR_DECISION,
            # majorityThreshold kept for back-compat; semantics: majority
            # within ACTIVE set (≥ activeCount//2 + 1), floor 3.
            "majorityThreshold": max(3, (active_count // 2) + 1) if active_count >= MIN_ACTIVE_FOR_DECISION else MIN_ACTIVE_FOR_DECISION,
            "totalModules": 5,
        },
        "currentPrice": price if price > 0 else None,
        "support": support if support > 0 else None,
        "resistance": resistance if resistance > 0 else None,
        "moduleConfidence": {
            "ta":        round(ta_conf, 3),
            "sentiment": round(sent_conf, 3),
            "fractal":   round(frac_conf, 3),
            "exchange":  round(exch_conf, 3),
            "onchain":   round(onch_conf, 3),
        },
        # P0 SIGNAL HYGIENE · honest degraded flags with reasons.
        # A degraded module abstains from the vote (silence ≠ WAIT).
        "moduleDegraded": {
            "ta":        bool(health["ta"]["degraded"]),
            "sentiment": bool(health["sentiment"]["degraded"]),
            "fractal":   bool(health["fractal"]["degraded"]),
            "exchange":  bool(health["exchange"]["degraded"]),
            "onchain":   bool(health["onchain"]["degraded"]),
        },
        "degradationReasons": {
            "ta":        health["ta"]["reason"],
            "sentiment": health["sentiment"]["reason"],
            "fractal":   health["fractal"]["reason"],
            "exchange":  health["exchange"]["reason"],
            "onchain":   health["onchain"]["reason"],
        },
        # Polymarket is interpretation layer, NOT a core driver — it's
        # surfaced separately from `alignment`. Trading verdict does NOT
        # take Polymarket vote into majority.
        "asOf": datetime.now(timezone.utc).isoformat(),
        "source": "trading_runtime_v3_5core_hygiene",
    }

    # ── T11.1b — RAW LINEAGE CAPTURE (forward-only, immutable) ──
    # Generate the lineageId BEFORE any layer is applied.  It becomes
    # the canonical spine that ties together: raw → calibrated → sized
    # → gated → submitted → outcome.  Same id propagates through every
    # downstream collection (paper_positions, paper_orders, paper_outcomes,
    # gate_decisions, attribution).  Once written, NEVER mutated.
    import copy as _copy
    lineage_id = f"lin_{uuid.uuid4().hex[:18]}"
    base_verdict["lineageId"] = lineage_id
    base_verdict["pipelineVersion"] = "t6+t8+t9+t10+tier4c1"
    # The raw snapshot is the pre-adjustment cognition output — a deep
    # copy taken before calibration / sizing / gate ever touch it.
    base_verdict["rawVerdictSnapshot"] = {
        "lineageId":      lineage_id,
        "action":         action,
        "confidence":     overall_conf,
        "entry":          entry,
        "stop":           stop,
        "target":         target,
        "rr":             rr,
        "symbol":         sym,
        "inputSymbol":    input_symbol or sym,
        "canonicalSymbol": sym,
        "timestamp":      base_verdict["asOf"],
        "modelVersion":   "trading_runtime_v1",
        "marketContext": {
            "currentPrice": price if price > 0 else None,
            "support":      support if support > 0 else None,
            "resistance":   resistance if resistance > 0 else None,
            "moduleConfidence": dict(base_verdict["moduleConfidence"]),
            "alignment":        dict(base_verdict["alignment"]),
        },
        "reasons":      list(reasons),
        "blockedBy":    list(blocked_by),
        "rawRisk":      risk_band,
        "rawSizeUsd":   size_usd,
    }
    # Defensive: snapshot must not be a live reference into base_verdict
    base_verdict["rawVerdictSnapshot"] = _copy.deepcopy(base_verdict["rawVerdictSnapshot"])

    # T4 — overlay calibration block (and graduated adjustments)
    try:
        from services import calibration as _calib
        base_verdict = _calib.apply_to_verdict(base_verdict)
    except Exception as _e:
        logger.warning(f"[trading_runtime] calibration overlay failed: {_e}")

    # T8 — adaptive capital restraint layer (sizing block, replaces sizeUsd)
    try:
        from services import adaptive_risk as _adaptive
        acc = _ensure_account(DEFAULT_ACCOUNT_ID)
        open_positions_raw = list(
            paper_positions.find(
                {"accountId": DEFAULT_ACCOUNT_ID, "status": "OPEN"},
                {"_id": 0},
            )
        )
        # Enrich with live unrealized PnL for T9 drawdown calc
        for p in open_positions_raw:
            cur = _current_price(p["symbol"], _fetch_ta(p["symbol"]))
            if cur > 0 and p.get("entryPrice"):
                qty = p["sizeUsd"] / p["entryPrice"]
                if (p.get("side") or "").upper() == "LONG":
                    p["unrealizedPnlUsd"] = (cur - p["entryPrice"]) * qty
                else:
                    p["unrealizedPnlUsd"] = (p["entryPrice"] - cur) * qty
            else:
                p["unrealizedPnlUsd"] = 0.0

        sizing = _adaptive.compute_adaptive_sizing(
            base_verdict, acc, open_positions_raw, DEFAULT_RISK_PER_TRADE_PCT,
        )
        base_verdict["sizing"] = sizing
        # Final deployable size always comes from sizing.final
        action_now = (base_verdict.get("action") or "").upper()
        if action_now in ("LONG", "SHORT") and sizing.get("final", 0.0) > 0:
            base_verdict["sizeUsd"] = sizing["final"]
        else:
            base_verdict["sizeUsd"] = None
            # Append a transparent blocker if the *adaptive* layer was the
            # killer (calibration may have already pushed action → WAIT).
            fzr = sizing.get("forcedZeroReason")
            if fzr in ("book_saturated", "size_below_min_deployable") and action_now in ("LONG", "SHORT"):
                base_verdict["actionBeforeSizing"] = action_now
                base_verdict["action"] = "WAIT"
                base_verdict["entry"] = None
                base_verdict["stop"] = None
                base_verdict["target"] = None
                base_verdict["rr"] = None
                base_verdict.setdefault("blockedBy", []).append(
                    "adaptive_layer_zeroed_size"
                    + (f" ({fzr})" if fzr else "")
                )
                base_verdict.setdefault("reasons", []).append(
                    sizing.get("explanation") or "adaptive sizing zeroed size"
                )
    except Exception as _e:
        logger.warning(f"[trading_runtime] adaptive sizing failed: {_e}")
        open_positions_raw = []
        acc = _ensure_account(DEFAULT_ACCOUNT_ID)

    # T9 — portfolio exposure gate (caps + correlation + drawdown + cooldown)
    try:
        from services import portfolio_gate as _gate
        base_verdict = _gate.apply_portfolio_gate(base_verdict, acc, open_positions_raw)
    except Exception as _e:
        logger.warning(f"[trading_runtime] portfolio gate failed: {_e}")

    return base_verdict


def scan_opportunities(symbols: list[str]) -> dict:
    """Run verdict over a watchlist; bucket by action."""
    out = {"WAIT": [], "LONG": [], "SHORT": []}
    asOf = datetime.now(timezone.utc).isoformat()
    for s in symbols:
        try:
            v = build_verdict(s)
            out[v["action"]].append({
                "symbol": v["symbol"],
                "action": v["action"],
                "confidence": v["confidence"],
                "rr": v["rr"],
                "risk": v["risk"],
                "alignment": v["alignment"]["score"],
                "blockedBy": v["blockedBy"][:2],
            })
        except Exception as e:
            logger.exception(f"[trading_runtime] scan {s} failed: {e}")
            out["WAIT"].append({"symbol": s, "error": str(e)})
    return {
        "ok": True,
        "asOf": asOf,
        "watchlist": symbols,
        "counts": {k: len(v) for k, v in out.items()},
        "opportunities": out,
    }


# ── Paper trading ─────────────────────────────────────────────────────


def _ensure_account(account_id: str) -> dict:
    acc = paper_accounts.find_one({"accountId": account_id}, {"_id": 0})
    if acc:
        return acc
    doc = {
        "accountId": account_id,
        "startingBalanceUsd": DEFAULT_STARTING_BALANCE_USD,
        "balanceUsd": DEFAULT_STARTING_BALANCE_USD,
        "equityUsd": DEFAULT_STARTING_BALANCE_USD,
        "realizedPnlUsd": 0.0,
        "unrealizedPnlUsd": 0.0,
        "openPositions": 0,
        "totalTrades": 0,
        "wins": 0,
        "losses": 0,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    paper_accounts.insert_one({**doc})
    return doc


def get_account(account_id: str = DEFAULT_ACCOUNT_ID) -> dict:
    acc = _ensure_account(account_id)
    # Refresh unrealized
    open_pos = list(paper_positions.find({"accountId": account_id, "status": "OPEN"}, {"_id": 0}))
    unrealized = 0.0
    for p in open_pos:
        cur = _current_price(p["symbol"], _fetch_ta(p["symbol"]))
        if cur > 0 and p.get("entryPrice"):
            qty = p["sizeUsd"] / p["entryPrice"]
            if p["side"] == "LONG":
                unrealized += (cur - p["entryPrice"]) * qty
            else:
                unrealized += (p["entryPrice"] - cur) * qty
    paper_accounts.update_one(
        {"accountId": account_id},
        {"$set": {
            "unrealizedPnlUsd": round(unrealized, 2),
            "equityUsd": round(acc["balanceUsd"] + unrealized, 2),
            "openPositions": len(open_pos),
        }},
    )
    acc = paper_accounts.find_one({"accountId": account_id}, {"_id": 0})
    return acc


def list_orders(account_id: str = DEFAULT_ACCOUNT_ID, limit: int = 50) -> list[dict]:
    return list(
        paper_orders.find({"accountId": account_id}, {"_id": 0})
        .sort("createdAt", DESCENDING)
        .limit(limit)
    )


def list_positions(account_id: str = DEFAULT_ACCOUNT_ID, status: str = "OPEN") -> list[dict]:
    q = {"accountId": account_id}
    if status != "ALL":
        q["status"] = status
    out = list(paper_positions.find(q, {"_id": 0}).sort("openedAt", DESCENDING))
    # Compute live unrealized
    for p in out:
        if p.get("status") == "OPEN" and p.get("entryPrice"):
            cur = _current_price(p["symbol"], _fetch_ta(p["symbol"]))
            if cur > 0:
                qty = p["sizeUsd"] / p["entryPrice"]
                if p["side"] == "LONG":
                    pnl = (cur - p["entryPrice"]) * qty
                    pnl_pct = (cur - p["entryPrice"]) / p["entryPrice"] * 100
                else:
                    pnl = (p["entryPrice"] - cur) * qty
                    pnl_pct = (p["entryPrice"] - cur) / p["entryPrice"] * 100
                p["currentPrice"] = round(cur, 2)
                p["unrealizedPnlUsd"] = round(pnl, 2)
                p["unrealizedPnlPct"] = round(pnl_pct, 2)
    return out


def submit_paper_order(
    symbol: str,
    account_id: str = DEFAULT_ACCOUNT_ID,
    override_action: Optional[str] = None,
    override_size_usd: Optional[float] = None,
) -> dict:
    """Build verdict for symbol; if action is LONG/SHORT (or override), open paper position.

    If override_action forces LONG/SHORT past a WAIT verdict, structural levels
    (support/resistance) are still used to derive entry/stop/target.
    """
    verdict = build_verdict(symbol)
    action = (override_action or verdict["action"]).upper()
    if action not in ("LONG", "SHORT"):
        return {
            "ok": False,
            "error": "verdict_is_wait",
            "detail": "Verdict engine returned WAIT — paper order refused. Pass override_action to force.",
            "verdict": verdict,
        }

    acc = _ensure_account(account_id)

    # Already-open position guard
    existing = paper_positions.find_one({
        "accountId": account_id,
        "symbol": symbol.upper(),
        "status": "OPEN",
    })
    if existing:
        return {
            "ok": False,
            "error": "position_already_open",
            "positionId": existing["positionId"],
        }

    # If verdict was WAIT but action overridden — derive levels from structure now.
    entry = verdict.get("entry")
    stop = verdict.get("stop")
    target = verdict.get("target")
    if not (entry and stop and target):
        price = verdict.get("currentPrice") or 0.0
        support = verdict.get("support") or 0.0
        resistance = verdict.get("resistance") or 0.0
        if price <= 0:
            return {"ok": False, "error": "no_current_price", "verdict": verdict}
        entry = round(price, 2)
        if action == "LONG":
            stop = round(support, 2) if (support and support < price) else round(price * 0.97, 2)
            target = round(resistance, 2) if (resistance and resistance > price) else round(price * 1.06, 2)
            if stop >= entry:
                stop = round(entry * 0.97, 2)
        else:
            stop = round(resistance, 2) if (resistance and resistance > price) else round(price * 1.03, 2)
            target = round(support, 2) if (support and support < price) else round(price * 0.94, 2)
            if stop <= entry:
                stop = round(entry * 1.03, 2)
        verdict["entry"] = entry
        verdict["stop"] = stop
        verdict["target"] = target
        risk_per_unit = abs(entry - stop)
        reward_per_unit = abs(target - entry)
        verdict["rr"] = round(reward_per_unit / risk_per_unit, 2) if risk_per_unit > 0 else None
        verdict["overrideApplied"] = True

    size_usd = float(override_size_usd or verdict.get("sizeUsd") or 0)
    if size_usd <= 0:
        # Auto-size from equity × risk_pct if not given
        equity = float(acc.get("equityUsd", DEFAULT_STARTING_BALANCE_USD))
        risk_usd = equity * (DEFAULT_RISK_PER_TRADE_PCT / 100.0)
        unit_risk = abs(entry - stop) / entry if entry > 0 else 0
        size_usd = round(risk_usd / unit_risk, 2) if unit_risk > 0 else 0
    if size_usd <= 0:
        return {"ok": False, "error": "invalid_size", "verdict": verdict}
    if size_usd > acc["balanceUsd"]:
        return {"ok": False, "error": "insufficient_balance", "balance": acc["balanceUsd"]}

    now = datetime.now(timezone.utc).isoformat()
    order_id = f"ord_{uuid.uuid4().hex[:10]}"
    position_id = f"pos_{uuid.uuid4().hex[:10]}"

    order_doc = {
        "orderId": order_id,
        "accountId": account_id,
        "symbol": symbol.upper(),
        "side": action,
        "type": "MARKET",
        "entryPrice": entry,
        "stopPrice": stop,
        "targetPrice": target,
        "sizeUsd": size_usd,
        "status": "FILLED",
        "filledAt": now,
        "verdict": {
            "rr": verdict.get("rr"),
            "risk": verdict.get("risk"),
            "confidence": verdict.get("confidence"),
            "alignment": verdict.get("alignment"),
            "originalAction": verdict.get("action"),
            "overrideApplied": verdict.get("overrideApplied", False),
        },
        # T11.1c — forward-only lineage spine on the order ledger.
        # Carries the canonical lineageId + pipelineVersion + the FULL
        # verdictSnapshot (including rawVerdictSnapshot when present).
        # Old orders remain untouched — these fields are simply absent
        # on pre-T11.1c rows, and downstream readers (attribution
        # summary) treat missing lineageId as "legacy pre-spine" data.
        "lineageId":       verdict.get("lineageId"),
        "pipelineVersion": verdict.get("pipelineVersion"),
        "verdictSnapshot": verdict,
        "createdAt": now,
        "positionId": position_id,
    }
    paper_orders.insert_one({**order_doc})

    position_doc = {
        "positionId": position_id,
        "orderId": order_id,
        "accountId": account_id,
        "symbol": symbol.upper(),
        "side": action,
        "entryPrice": entry,
        "stopPrice": stop,
        "targetPrice": target,
        "sizeUsd": size_usd,
        "status": "OPEN",
        "openedAt": now,
        "lastEvalAt": now,
        "closedAt": None,
        "closePrice": None,
        "realizedPnlUsd": 0.0,
        "realizedPnlPct": 0.0,
        "closeReason": None,
        # T11.1b — propagate the canonical lineage identity + full
        # verdict snapshot (including rawVerdictSnapshot) so the
        # outcome layer downstream can attribute back across all four
        # pipeline views.  Both fields are IMMUTABLE from this point.
        "lineageId":       verdict.get("lineageId"),
        "pipelineVersion": verdict.get("pipelineVersion"),
        "verdictSnapshot": verdict,
    }
    paper_positions.insert_one({**position_doc})
    # T11.1c — ORDER_FILLED event now carries lineage; old events
    # remain untouched (no migration).
    paper_events.insert_one({
        "ts": now, "type": "ORDER_FILLED", "orderId": order_id,
        "positionId": position_id, "symbol": symbol.upper(),
        "side": action, "entry": entry, "sizeUsd": size_usd,
        "lineageId":       verdict.get("lineageId"),
        "pipelineVersion": verdict.get("pipelineVersion"),
    })
    # T11.1c — new POSITION_OPENED event with full lineage payload.
    # Distinct from ORDER_FILLED so attribution drilldowns can read
    # position lifecycle without re-deriving from order rows.  Carries
    # rawVerdictSnapshot reference (NOT a fresh copy) — same identity
    # as in paper_positions_v2.verdictSnapshot.rawVerdictSnapshot.
    paper_events.insert_one({
        "ts": now, "type": "POSITION_OPENED",
        "positionId": position_id, "orderId": order_id,
        "symbol": symbol.upper(), "side": action,
        "entry": entry, "stop": stop, "target": target,
        "sizeUsd": size_usd,
        "lineageId":         verdict.get("lineageId"),
        "pipelineVersion":   verdict.get("pipelineVersion"),
        "rawVerdictSnapshot": verdict.get("rawVerdictSnapshot"),
    })

    return {
        "ok": True,
        "orderId": order_id,
        "positionId": position_id,
        "symbol": symbol.upper(),
        "side": action,
        "entry": entry,
        "stop": stop,
        "target": target,
        "sizeUsd": size_usd,
        "verdict": verdict,
    }


def close_paper_position(
    position_id: str,
    account_id: str = DEFAULT_ACCOUNT_ID,
    reason: str = "manual",
) -> dict:
    pos = paper_positions.find_one(
        {"positionId": position_id, "accountId": account_id, "status": "OPEN"},
        {"_id": 0},
    )
    if not pos:
        return {"ok": False, "error": "position_not_found_or_closed"}

    cur = _current_price(pos["symbol"], _fetch_ta(pos["symbol"]))
    if cur <= 0:
        return {"ok": False, "error": "no_current_price"}

    qty = pos["sizeUsd"] / pos["entryPrice"]
    if pos["side"] == "LONG":
        pnl_usd = (cur - pos["entryPrice"]) * qty
        pnl_pct = (cur - pos["entryPrice"]) / pos["entryPrice"] * 100
    else:
        pnl_usd = (pos["entryPrice"] - cur) * qty
        pnl_pct = (pos["entryPrice"] - cur) / pos["entryPrice"] * 100

    now = datetime.now(timezone.utc).isoformat()
    paper_positions.update_one(
        {"positionId": position_id},
        {"$set": {
            "status": "CLOSED",
            "closedAt": now,
            "closePrice": round(cur, 2),
            "realizedPnlUsd": round(pnl_usd, 2),
            "realizedPnlPct": round(pnl_pct, 2),
            "closeReason": reason,
        }},
    )

    # Update account
    acc = paper_accounts.find_one({"accountId": account_id}, {"_id": 0})
    new_balance = round(acc["balanceUsd"] + pnl_usd, 2)
    wins = acc.get("wins", 0) + (1 if pnl_usd > 0 else 0)
    losses = acc.get("losses", 0) + (1 if pnl_usd <= 0 else 0)
    paper_accounts.update_one(
        {"accountId": account_id},
        {"$set": {
            "balanceUsd": new_balance,
            "realizedPnlUsd": round(acc.get("realizedPnlUsd", 0.0) + pnl_usd, 2),
            "totalTrades": acc.get("totalTrades", 0) + 1,
            "wins": wins,
            "losses": losses,
        }},
    )
    paper_events.insert_one({
        "ts": now, "type": "POSITION_CLOSED", "positionId": position_id,
        "symbol": pos["symbol"], "side": pos["side"],
        "exit": round(cur, 2), "pnlUsd": round(pnl_usd, 2),
        "pnlPct": round(pnl_pct, 2), "reason": reason,
        # T11.1c — propagate lineage onto the close event so the
        # event stream can be replayed end-to-end without joining
        # against paper_positions_v2.
        "lineageId":       pos.get("lineageId"),
        "pipelineVersion": pos.get("pipelineVersion"),
    })

    # T11.1c — Forward-only outcome writer.  Writes one immutable row
    # to paper_outcomes IFF the position carries a lineageId (post-T11.1c).
    # Pre-T11.1c positions: skip silently (no retroactive fabrication).
    try:
        _closed_for_outcome = paper_positions.find_one(
            {"positionId": position_id}, {"_id": 0}
        ) or pos
        _write_paper_outcome_t11_1c(
            closed_pos=_closed_for_outcome,
            close_price=cur,
            pnl_usd=pnl_usd,
            pnl_pct=pnl_pct,
            reason=reason,
            detection_mode="manual",
        )
    except Exception as _e:
        logger.warning(f"[trading_runtime] T11.1c outcome write skipped (manual): {_e}")

    # T4 — outcome writeback for manual close
    try:
        from services import calibration as _calib
        closed_pos = paper_positions.find_one({"positionId": position_id}, {"_id": 0}) or pos
        order = paper_orders.find_one(
            {"orderId": closed_pos.get("orderId")}, {"_id": 0, "verdict": 1}
        ) or {}
        _calib.record_outcome(
            closed_pos, close_price=cur, reason=reason,
            verdict_snapshot=order.get("verdict"),
        )
    except Exception as _e:
        logger.warning(f"[trading_runtime] calibration writeback failed (manual): {_e}")

    return {
        "ok": True,
        "positionId": position_id,
        "closePrice": round(cur, 2),
        "pnlUsd": round(pnl_usd, 2),
        "pnlPct": round(pnl_pct, 2),
        "reason": reason,
    }


def evaluate_stop_target_hits(account_id: str = DEFAULT_ACCOUNT_ID) -> dict:
    """Auto-close OPEN positions whose stop or target was hit.

    Hit detection uses 1-minute bar high/low from Binance (via bar_data.py)
    for the window since each position's `lastEvalAt`. If bar data is
    unavailable (network/region), falls back to last-tick price comparison
    (recorded as `detectionMode: 'tick'` on the event).

    Idempotent: positions whose `status != 'OPEN'` are skipped, so a
    concurrent/duplicate scheduler tick will NOT double-close.

    When both stop and target are inside the same bar's range, **stop wins**
    (conservative — paper assumes worst-case fill order within a bar).
    """
    from services import bar_data  # local import to keep cycle-free

    closed: list[dict] = []
    scanned = 0
    bar_used = 0
    tick_used = 0
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    for pos in list(
        paper_positions.find({"accountId": account_id, "status": "OPEN"}, {"_id": 0})
    ):
        scanned += 1
        sym = pos["symbol"]
        side = pos["side"]
        stop_px = float(pos["stopPrice"])
        target_px = float(pos["targetPrice"])

        # Compute window: bars STRICTLY after lastEvalAt (or openedAt as fallback).
        last_eval_iso = pos.get("lastEvalAt") or pos.get("openedAt")
        try:
            last_eval_ms = int(
                datetime.fromisoformat(last_eval_iso.replace("Z", "+00:00")).timestamp() * 1000
            )
        except Exception:
            last_eval_ms = now_ms - 60_000  # 1m ago as safe default

        # Cap window to avoid pulling huge bar history on cold reboot.
        if now_ms - last_eval_ms > 60 * 60 * 1000:  # > 60 min
            last_eval_ms = now_ms - 60 * 60 * 1000

        hit_reason: Optional[str] = None
        hit_price: Optional[float] = None
        detection_mode = "tick"

        bars = bar_data.fetch_recent_1m_bars(sym, since_ms=last_eval_ms, limit=10) if bar_data.supported(sym) else []
        if bars:
            bar_used += 1
            for b in bars:
                hi = b["high"]
                lo = b["low"]
                # Order-of-events: assume worst case → check stop FIRST.
                if side == "LONG":
                    if lo <= stop_px:
                        hit_reason, hit_price = "stop", stop_px
                        break
                    if hi >= target_px:
                        hit_reason, hit_price = "target", target_px
                        break
                else:  # SHORT
                    if hi >= stop_px:
                        hit_reason, hit_price = "stop", stop_px
                        break
                    if lo <= target_px:
                        hit_reason, hit_price = "target", target_px
                        break
            detection_mode = "bar_1m"
        else:
            # Fallback: tick-based check
            tick_used += 1
            cur = _current_price(sym, _fetch_ta(sym))
            if cur <= 0:
                # Update lastEvalAt anyway so scheduler doesn't keep retrying same window
                paper_positions.update_one(
                    {"positionId": pos["positionId"], "status": "OPEN"},
                    {"$set": {"lastEvalAt": datetime.now(timezone.utc).isoformat()}},
                )
                continue
            if side == "LONG":
                if cur <= stop_px:
                    hit_reason, hit_price = "stop", cur
                elif cur >= target_px:
                    hit_reason, hit_price = "target", cur
            else:
                if cur >= stop_px:
                    hit_reason, hit_price = "stop", cur
                elif cur <= target_px:
                    hit_reason, hit_price = "target", cur

        if hit_reason and hit_price is not None:
            # Idempotent close: enforce OPEN→CLOSED transition atomically.
            res = paper_positions.update_one(
                {"positionId": pos["positionId"], "status": "OPEN"},
                {"$set": {"_closing_lock": True}},
            )
            if res.modified_count != 1:
                # Someone else closed it concurrently — skip.
                continue
            close_res = _close_at_price(
                pos, account_id, close_price=hit_price, reason=hit_reason, detection_mode=detection_mode
            )
            if close_res.get("ok"):
                closed.append({**close_res, "detectionMode": detection_mode})
        else:
            # No hit — just advance lastEvalAt
            paper_positions.update_one(
                {"positionId": pos["positionId"], "status": "OPEN"},
                {"$set": {"lastEvalAt": datetime.now(timezone.utc).isoformat()}},
            )

    return {
        "ok": True,
        "scanned": scanned,
        "closed": closed,
        "count": len(closed),
        "barUsed": bar_used,
        "tickUsed": tick_used,
        "asOf": datetime.now(timezone.utc).isoformat(),
    }


def _close_at_price(
    pos: dict,
    account_id: str,
    close_price: float,
    reason: str,
    detection_mode: str = "manual",
) -> dict:
    """Internal close at a specific price (used by auto-evaluate path).

    Caller is responsible for having already locked the position via
    an atomic `_closing_lock` set on an OPEN doc.
    """
    qty = pos["sizeUsd"] / pos["entryPrice"]
    if pos["side"] == "LONG":
        pnl_usd = (close_price - pos["entryPrice"]) * qty
        pnl_pct = (close_price - pos["entryPrice"]) / pos["entryPrice"] * 100
    else:
        pnl_usd = (pos["entryPrice"] - close_price) * qty
        pnl_pct = (pos["entryPrice"] - close_price) / pos["entryPrice"] * 100

    now = datetime.now(timezone.utc).isoformat()
    paper_positions.update_one(
        {"positionId": pos["positionId"]},
        {"$set": {
            "status": "CLOSED",
            "closedAt": now,
            "closePrice": round(close_price, 2),
            "realizedPnlUsd": round(pnl_usd, 2),
            "realizedPnlPct": round(pnl_pct, 2),
            "closeReason": reason,
            "detectionMode": detection_mode,
        }, "$unset": {"_closing_lock": ""}},
    )

    acc = paper_accounts.find_one({"accountId": account_id}, {"_id": 0})
    new_balance = round(acc["balanceUsd"] + pnl_usd, 2)
    wins = acc.get("wins", 0) + (1 if pnl_usd > 0 else 0)
    losses = acc.get("losses", 0) + (1 if pnl_usd <= 0 else 0)
    paper_accounts.update_one(
        {"accountId": account_id},
        {"$set": {
            "balanceUsd": new_balance,
            "realizedPnlUsd": round(acc.get("realizedPnlUsd", 0.0) + pnl_usd, 2),
            "totalTrades": acc.get("totalTrades", 0) + 1,
            "wins": wins,
            "losses": losses,
        }},
    )
    paper_events.insert_one({
        "ts": now, "type": "POSITION_CLOSED", "positionId": pos["positionId"],
        "symbol": pos["symbol"], "side": pos["side"],
        "exit": round(close_price, 2), "pnlUsd": round(pnl_usd, 2),
        "pnlPct": round(pnl_pct, 2), "reason": reason,
        "detectionMode": detection_mode,
        # T11.1c — propagate lineage on the close event.
        "lineageId":       pos.get("lineageId"),
        "pipelineVersion": pos.get("pipelineVersion"),
    })

    # T11.1c — Forward-only outcome writer.  Same invariants as the
    # manual close path: idempotent by positionId, skipped silently
    # for pre-T11.1c positions, wrapped in try/except so it never
    # breaks the close flow.
    try:
        _closed_for_outcome = paper_positions.find_one(
            {"positionId": pos["positionId"]}, {"_id": 0}
        ) or pos
        _write_paper_outcome_t11_1c(
            closed_pos=_closed_for_outcome,
            close_price=close_price,
            pnl_usd=pnl_usd,
            pnl_pct=pnl_pct,
            reason=reason,
            detection_mode=detection_mode,
        )
    except Exception as _e:
        logger.warning(f"[trading_runtime] T11.1c outcome write skipped (auto): {_e}")

    # T4 — outcome writeback + calibration refresh
    try:
        from services import calibration as _calib
        # Reload position with all post-close fields, then writeback
        closed_pos = paper_positions.find_one({"positionId": pos["positionId"]}, {"_id": 0}) or pos
        order = paper_orders.find_one(
            {"orderId": closed_pos.get("orderId")}, {"_id": 0, "verdict": 1}
        ) or {}
        _calib.record_outcome(
            closed_pos,
            close_price=close_price,
            reason=reason,
            verdict_snapshot=order.get("verdict"),
        )
    except Exception as _e:
        logger.warning(f"[trading_runtime] calibration writeback failed: {_e}")

    return {
        "ok": True,
        "positionId": pos["positionId"],
        "symbol": pos["symbol"],
        "side": pos["side"],
        "closePrice": round(close_price, 2),
        "pnlUsd": round(pnl_usd, 2),
        "pnlPct": round(pnl_pct, 2),
        "reason": reason,
    }


def list_events(account_id: Optional[str] = DEFAULT_ACCOUNT_ID, limit: int = 50) -> list[dict]:
    return list(paper_events.find({}, {"_id": 0}).sort("ts", DESCENDING).limit(limit))


def runtime_status() -> dict:
    """Public runtime status — for /api/trading/runtime/status."""
    acc = _ensure_account(DEFAULT_ACCOUNT_ID)
    return {
        "ok": True,
        "source": "trading_runtime_v1",
        "mode": "paper",
        "sidecar": None,
        "cognitionLayers": {
            "ta": "in-process",
            "sentiment": "in-process",
            "fractal": "in-process",
        },
        "account": {
            "accountId": acc["accountId"],
            "balanceUsd": acc["balanceUsd"],
            "equityUsd": acc.get("equityUsd"),
            "openPositions": acc.get("openPositions", 0),
            "totalTrades": acc.get("totalTrades", 0),
        },
        "config": {
            "startingBalanceUsd": DEFAULT_STARTING_BALANCE_USD,
            "riskPerTradePct": DEFAULT_RISK_PER_TRADE_PCT,
        },
        "asOf": datetime.now(timezone.utc).isoformat(),
    }
