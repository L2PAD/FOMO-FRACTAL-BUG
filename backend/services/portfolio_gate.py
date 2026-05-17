"""
portfolio_gate — T9 · Portfolio Exposure Control + Drawdown Circuit Breaker.

Pipeline position:
    verdict → calibration → adaptive sizing → **portfolio_gate** → paper submit

T9 does NOT touch cognition. It does NOT modify calibration. It does NOT
re-scale lifetimeWeight / regimeWeight / uncertaintyPenalty.

T9 answers exactly ONE question, taking the system state AS-IS:

    "Can the portfolio safely absorb THIS deployment right now?"

If yes → verdict passes through with `portfolioGate.finalPermission='allowed'`.
If no  → action becomes WAIT, sizeUsd=null, blockedBy gets a transparent reason,
         and `portfolioGate.finalPermission='blocked'` with the failing rule.

Layers (any one blocks → finalPermission='blocked'):
  1. EXPOSURE CAPS
      * max open positions
      * max total notional / equity
      * max per-symbol exposure
      * max same-side exposure
  2. CORRELATION GUARD
      * majors L1 (BTC/ETH/SOL) treated as one correlated cluster
      * if N already same-side in that cluster → new same-side add blocked
  3. DAILY DRAWDOWN BREAKER
      * realized-today + current unrealized vs starting-of-day equity
      * if drawdown exceeds threshold → ALL new deployments → WAIT
      * existing positions can still be closed (paper/close path unaffected)
  4. LOSS STREAK COOLDOWN
      * N consecutive losses → cooldown for K hours
      * during cooldown, new deployments blocked

All thresholds live in module-level CONST tuples — kept as data, not magic.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pymongo import MongoClient, DESCENDING

load_dotenv(Path(__file__).parent.parent / ".env", override=False)
logger = logging.getLogger("portfolio_gate")

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "test_database")

_client = MongoClient(MONGO_URL)
_db = _client[DB_NAME]


# ── Thresholds (configurable, surfaced in /verdict response) ─────────


THRESHOLDS = {
    "maxOpenPositions": 5,
    "maxTotalNotionalRatio": 3.0,      # totalNotional / equity
    "maxPerSymbolRatio": 1.5,          # per-symbol notional / equity
    "maxSameSideRatio": 2.5,           # same-side notional / equity
    "maxCorrelatedRatio": 2.0,         # correlated-cluster notional / equity
    "dailyDrawdownPct": 5.0,           # negative % of start-of-day equity
    "lossStreakThreshold": 3,          # consecutive losses → cooldown
    "cooldownHours": 6,
}

# Correlation clusters. Same-direction inside cluster counts as correlated.
# Conservative seed — all majors-L1 treated as one cluster.
CORRELATION_CLUSTERS: dict[str, list[str]] = {
    "majors_l1": ["BTC", "ETH", "SOL"],
}


def _cluster_for(symbol: str) -> Optional[str]:
    sym = symbol.upper()
    for name, members in CORRELATION_CLUSTERS.items():
        if sym in members:
            return name
    return None


# ── Helpers ──────────────────────────────────────────────────────────


def _utc_midnight_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def _realized_today_usd(account_id: str) -> float:
    """Sum realizedPnlUsd of paper_positions_v2 closed since UTC midnight."""
    midnight = _utc_midnight_iso()
    cur = _db["paper_positions_v2"].find(
        {
            "accountId": account_id,
            "status": "CLOSED",
            "closedAt": {"$gte": midnight},
        },
        {"_id": 0, "realizedPnlUsd": 1},
    )
    return float(sum(float(r.get("realizedPnlUsd") or 0.0) for r in cur))


def _unrealized_pnl_usd(open_positions: list[dict]) -> float:
    """Caller already enriched OPEN positions with unrealizedPnlUsd (or 0)."""
    return float(sum(float(p.get("unrealizedPnlUsd") or 0.0) for p in open_positions))


def _consecutive_loss_streak(account_id: str, lookback: int = 10) -> tuple[int, Optional[str]]:
    """Walk last N closed positions newest→oldest; count contiguous losses.

    Returns (streak, lastLossClosedAtIso).
    """
    cur = _db["paper_positions_v2"].find(
        {"accountId": account_id, "status": "CLOSED"},
        {"_id": 0, "realizedPnlUsd": 1, "closedAt": 1},
        sort=[("closedAt", DESCENDING)],
    ).limit(lookback)
    streak = 0
    last_iso: Optional[str] = None
    for row in cur:
        pnl = float(row.get("realizedPnlUsd") or 0.0)
        if pnl < 0:
            streak += 1
            if last_iso is None:
                last_iso = row.get("closedAt")
        else:
            break
    return streak, last_iso


# ── Public entry point ───────────────────────────────────────────────


def apply_portfolio_gate(
    verdict: dict,
    account: dict,
    open_positions: list[dict],
) -> dict:
    """Evaluate portfolio constraints AGAINST the post-adaptive-sizing verdict.

    Mutates verdict in-place with `portfolioGate` block. If any rule blocks,
    flips action → WAIT, clears entry/stop/target/sizeUsd, appends blockedBy.

    Idempotent: never re-blocks a verdict that has already been gated.
    """
    action = (verdict.get("action") or "").upper()
    symbol = (verdict.get("symbol") or "").upper()
    sizing = verdict.get("sizing") or {}
    deployable_size = float(sizing.get("final") or 0.0)

    equity = float(account.get("equityUsd") or account.get("balanceUsd") or 0.0)
    if equity <= 0:
        equity = 1.0  # defensive — avoid div-by-zero in ratio math

    # ── Exposure totals (state of the book BEFORE this deployment) ─────
    total_notional = sum(float(p.get("sizeUsd") or 0.0) for p in open_positions)
    long_notional = sum(
        float(p.get("sizeUsd") or 0.0) for p in open_positions
        if (p.get("side") or "").upper() == "LONG"
    )
    short_notional = sum(
        float(p.get("sizeUsd") or 0.0) for p in open_positions
        if (p.get("side") or "").upper() == "SHORT"
    )
    per_symbol_notional = sum(
        float(p.get("sizeUsd") or 0.0) for p in open_positions
        if (p.get("symbol") or "").upper() == symbol
    )

    # ── Correlation cluster exposure ──────────────────────────────────
    cluster = _cluster_for(symbol)
    cluster_same_side_notional = 0.0
    cluster_same_side_count = 0
    if cluster is not None and action in ("LONG", "SHORT"):
        members = set(CORRELATION_CLUSTERS[cluster])
        for p in open_positions:
            sym_p = (p.get("symbol") or "").upper()
            side_p = (p.get("side") or "").upper()
            if sym_p in members and side_p == action:
                cluster_same_side_notional += float(p.get("sizeUsd") or 0.0)
                cluster_same_side_count += 1

    # ── Drawdown state ────────────────────────────────────────────────
    starting_equity = float(account.get("startingBalanceUsd") or equity)
    realized_today = _realized_today_usd(account.get("accountId", "default-paper-account"))
    unrealized_now = _unrealized_pnl_usd(open_positions)
    drawdown_usd = realized_today + unrealized_now  # negative → drawdown
    # express as % of start-of-day equity baseline (approximated by starting balance)
    baseline = starting_equity if starting_equity > 0 else equity
    drawdown_pct = round((drawdown_usd / baseline) * 100.0, 3) if baseline else 0.0
    breaker_active = drawdown_pct <= -float(THRESHOLDS["dailyDrawdownPct"])

    # ── Loss streak cooldown ──────────────────────────────────────────
    streak, last_loss_iso = _consecutive_loss_streak(
        account.get("accountId", "default-paper-account")
    )
    cooldown_active = False
    cooldown_until: Optional[str] = None
    if streak >= THRESHOLDS["lossStreakThreshold"] and last_loss_iso:
        try:
            last_dt = datetime.fromisoformat(last_loss_iso.replace("Z", "+00:00"))
            until = last_dt + timedelta(hours=THRESHOLDS["cooldownHours"])
            now = datetime.now(timezone.utc)
            if until > now:
                cooldown_active = True
                cooldown_until = until.isoformat()
        except Exception:
            pass

    # ── Build prospective book state IF this deployment were accepted ─
    prospective_total = total_notional + deployable_size
    prospective_same_side = (
        (long_notional + deployable_size) if action == "LONG"
        else (short_notional + deployable_size) if action == "SHORT"
        else total_notional
    )
    prospective_per_symbol = per_symbol_notional + (
        deployable_size if action in ("LONG", "SHORT") else 0.0
    )
    prospective_cluster = cluster_same_side_notional + (
        deployable_size if (cluster is not None and action in ("LONG", "SHORT")) else 0.0
    )
    prospective_open_count = len(open_positions) + (
        1 if action in ("LONG", "SHORT") and deployable_size > 0 else 0
    )

    # ── Caps evaluation ──────────────────────────────────────────────
    open_ratio = prospective_open_count / float(THRESHOLDS["maxOpenPositions"])
    total_ratio = (prospective_total / equity) if equity else 0.0
    per_symbol_ratio = (prospective_per_symbol / equity) if equity else 0.0
    same_side_ratio = (prospective_same_side / equity) if equity else 0.0
    cluster_ratio = (prospective_cluster / equity) if equity else 0.0

    reasons: list[str] = []
    blocked_by_rule: Optional[str] = None

    # 1. Drawdown breaker — highest priority (global circuit)
    if action in ("LONG", "SHORT") and deployable_size > 0 and breaker_active:
        blocked_by_rule = "daily_drawdown_circuit_breaker"
        reasons.append(
            f"Daily drawdown {drawdown_pct}% ≤ −{THRESHOLDS['dailyDrawdownPct']}% — "
            "circuit breaker engaged · new deployments suspended"
        )

    # 2. Cooldown after loss streak
    if (blocked_by_rule is None and action in ("LONG", "SHORT")
            and deployable_size > 0 and cooldown_active):
        blocked_by_rule = "loss_streak_cooldown"
        reasons.append(
            f"Loss streak {streak} ≥ {THRESHOLDS['lossStreakThreshold']} · "
            f"cooldown until {cooldown_until}"
        )

    # 3. Exposure caps
    if blocked_by_rule is None and action in ("LONG", "SHORT") and deployable_size > 0:
        if prospective_open_count > THRESHOLDS["maxOpenPositions"]:
            blocked_by_rule = "max_open_positions"
            reasons.append(
                f"Open positions would be {prospective_open_count} > "
                f"max {THRESHOLDS['maxOpenPositions']}"
            )
        elif total_ratio > THRESHOLDS["maxTotalNotionalRatio"]:
            blocked_by_rule = "max_total_notional"
            reasons.append(
                f"Total notional {total_ratio:.2f}× equity > "
                f"cap {THRESHOLDS['maxTotalNotionalRatio']}×"
            )
        elif per_symbol_ratio > THRESHOLDS["maxPerSymbolRatio"]:
            blocked_by_rule = "max_per_symbol_exposure"
            reasons.append(
                f"{symbol} exposure {per_symbol_ratio:.2f}× equity > "
                f"per-symbol cap {THRESHOLDS['maxPerSymbolRatio']}×"
            )
        elif same_side_ratio > THRESHOLDS["maxSameSideRatio"]:
            blocked_by_rule = "max_same_side_exposure"
            reasons.append(
                f"{action} side exposure {same_side_ratio:.2f}× equity > "
                f"same-side cap {THRESHOLDS['maxSameSideRatio']}×"
            )
        # 4. Correlation
        elif cluster is not None and cluster_ratio > THRESHOLDS["maxCorrelatedRatio"]:
            blocked_by_rule = "max_correlated_exposure"
            reasons.append(
                f"Cluster '{cluster}' same-side exposure {cluster_ratio:.2f}× equity > "
                f"correlated cap {THRESHOLDS['maxCorrelatedRatio']}× "
                f"(already {cluster_same_side_count} same-side in cluster)"
            )

    permission = "blocked" if blocked_by_rule else "allowed"

    gate_block = {
        "permission": permission,
        "blockReason": blocked_by_rule,
        "reasons": reasons,
        "caps": {
            "openPositions": {
                "current": len(open_positions),
                "prospective": prospective_open_count,
                "max": THRESHOLDS["maxOpenPositions"],
                "ratio": round(open_ratio, 3),
            },
            "totalNotional": {
                "currentUsd": round(total_notional, 2),
                "prospectiveUsd": round(prospective_total, 2),
                "equityUsd": round(equity, 2),
                "ratio": round(total_ratio, 3),
                "max": THRESHOLDS["maxTotalNotionalRatio"],
            },
            "perSymbol": {
                "symbol": symbol,
                "currentUsd": round(per_symbol_notional, 2),
                "prospectiveUsd": round(prospective_per_symbol, 2),
                "ratio": round(per_symbol_ratio, 3),
                "max": THRESHOLDS["maxPerSymbolRatio"],
            },
            "sameSide": {
                "side": action if action in ("LONG", "SHORT") else None,
                "currentUsd": round(
                    long_notional if action == "LONG"
                    else short_notional if action == "SHORT"
                    else 0.0, 2
                ),
                "prospectiveUsd": round(prospective_same_side, 2),
                "ratio": round(same_side_ratio, 3),
                "max": THRESHOLDS["maxSameSideRatio"],
            },
        },
        "correlation": {
            "cluster": cluster,
            "clusterMembers": CORRELATION_CLUSTERS.get(cluster or "", []),
            "sameSideCountInCluster": cluster_same_side_count,
            "currentClusterUsd": round(cluster_same_side_notional, 2),
            "prospectiveClusterUsd": round(prospective_cluster, 2),
            "ratio": round(cluster_ratio, 3),
            "max": THRESHOLDS["maxCorrelatedRatio"],
        },
        "drawdown": {
            "realizedTodayUsd": round(realized_today, 2),
            "unrealizedUsd": round(unrealized_now, 2),
            "drawdownUsd": round(drawdown_usd, 2),
            "drawdownPct": drawdown_pct,
            "thresholdPct": -float(THRESHOLDS["dailyDrawdownPct"]),
            "breakerActive": breaker_active,
            "baselineUsd": round(baseline, 2),
        },
        "cooldown": {
            "recentLossStreak": streak,
            "threshold": THRESHOLDS["lossStreakThreshold"],
            "cooldownActive": cooldown_active,
            "cooldownUntil": cooldown_until,
            "cooldownHours": THRESHOLDS["cooldownHours"],
        },
        "thresholds": dict(THRESHOLDS),
        "finalPermission": permission,
        "version": "t9.portfolio_exposure_gate.v1",
    }

    # ── Apply block if needed ────────────────────────────────────────
    if blocked_by_rule:
        verdict["actionBeforePortfolioGate"] = action
        verdict["action"] = "WAIT"
        verdict["entry"] = None
        verdict["stop"] = None
        verdict["target"] = None
        verdict["rr"] = None
        verdict["sizeUsd"] = None
        verdict.setdefault("blockedBy", []).append(blocked_by_rule)
        verdict.setdefault("reasons", []).extend(reasons)
        # Mirror the block into sizing for UI consistency — if T8 produced
        # a non-zero `final`, T9 effectively zeroes the deployable size now.
        if isinstance(verdict.get("sizing"), dict):
            verdict["sizing"]["forcedZeroReason"] = (
                verdict["sizing"].get("forcedZeroReason") or "portfolio_gate_blocked"
            )

    verdict["portfolioGate"] = gate_block

    # ── T11.1 — immutable forward-only counterfactual snapshot ──
    # Every gate evaluation (allowed OR blocked) writes an immutable
    # row to `gate_decisions`.  Attribution later reads these rows;
    # they are NEVER mutated or backfilled.  Snapshot-at-decision
    # captures both the pre-gate verdict shape and a counterfactual
    # description so the "what would have happened" view is anchored
    # in real captured state, not on-the-fly reconstruction.
    try:
        _persist_gate_decision(
            verdict=verdict,
            account=account,
            permission=permission,
            blocked_by=blocked_by_rule,
            reasons=reasons,
            gate_block=gate_block,
        )
    except Exception:
        # Persistence MUST NEVER break trading — log and proceed.
        # Attribution is observability; trading correctness is canonical.
        import logging
        logging.getLogger(__name__).exception("gate_decisions persistence failed")

    return verdict


# ── Immutable forward-only persistence for T11 attribution ──────────


import uuid as _uuid
from datetime import datetime as _dt, timezone as _tz

_gate_decisions = _db["gate_decisions"] if False else None  # bind below


def _gate_decisions_coll():
    """Lazy collection accessor + idempotent index setup."""
    global _gate_decisions
    if _gate_decisions is None:
        _gate_decisions = _db["gate_decisions"]
        try:
            _gate_decisions.create_index("decisionId", unique=True)
            _gate_decisions.create_index([("ts", DESCENDING)])
            _gate_decisions.create_index([("symbol", 1), ("ts", DESCENDING)])
            _gate_decisions.create_index([("permission", 1), ("ts", DESCENDING)])
        except Exception:
            pass
    return _gate_decisions


# Canonical pipeline identity — bumped whenever pipeline composition
# changes.  Attribution comparisons are only valid WITHIN the same
# pipelineVersion.
GATE_PIPELINE_VERSION = "t6+t8+t9+t10+tier4c1"


def _persist_gate_decision(
    *, verdict: dict, account: dict, permission: str,
    blocked_by: Optional[str], reasons: list, gate_block: dict,
):
    coll = _gate_decisions_coll()
    sizing = verdict.get("sizing") or {}
    # The action BEFORE this gate was applied — either the original
    # sized action if blocked or just verdict.action if allowed.
    pre_gate_action = (
        verdict.get("actionBeforePortfolioGate") or verdict.get("action") or ""
    ).upper()
    market_price = (
        verdict.get("entry") if pre_gate_action in ("LONG", "SHORT")
        else verdict.get("currentPrice")
    )
    doc = {
        "decisionId":       f"gd_{_uuid.uuid4().hex[:18]}",
        "pipelineVersion":  GATE_PIPELINE_VERSION,
        # T11.1b — canonical lineage spine.  Same id present on raw
        # snapshot, position doc, and outcome doc.  Stable across all
        # attribution joins.
        "lineageId":        verdict.get("lineageId"),
        "ts":               _dt.now(_tz.utc).isoformat(),
        "accountId":        account.get("accountId", "default-paper-account"),
        "symbol":           (verdict.get("symbol") or "").upper(),
        "permission":       permission,
        "blockReason":      blocked_by,
        "blockReasons":     list(reasons or []),
        # The verdict shape BEFORE the gate was applied — capture all
        # the layer outputs that arrived here (calibrated + sized).
        "verdictPreGate":   {
            "action":          pre_gate_action,
            "alignment":       verdict.get("alignment"),
            "risk":            verdict.get("risk"),
            "rr":              verdict.get("rr"),
            "sizing":          dict(sizing),
            "entry":           verdict.get("entry"),
            "stop":            verdict.get("stop"),
            "target":          verdict.get("target"),
        },
        # Counterfactual reference — what would have been deployed if
        # the gate had not blocked.  For ALLOWED rows this matches what
        # actually was deployed (used as a sanity baseline).
        "counterfactual": {
            "theoreticalEntry":     verdict.get("entry"),
            "theoreticalStop":      verdict.get("stop"),
            "theoreticalTarget":    verdict.get("target"),
            "theoreticalSizeUsd":   sizing.get("final"),
            "marketPriceAtDecision": market_price,
            "rr":                   verdict.get("rr"),
        },
        # Slim mirror of the gate block — full block lives on the
        # outcome doc too if execution proceeded, so we keep this lean
        # but auditable.
        "gateBlockSummary": {
            "permission":   gate_block.get("permission"),
            "blockReason":  gate_block.get("blockReason"),
            "caps":         gate_block.get("caps"),
            "correlation":  gate_block.get("correlation"),
            "drawdown":     gate_block.get("drawdown"),
            "cooldown":     gate_block.get("cooldown"),
            "version":      gate_block.get("version"),
        },
    }
    coll.insert_one(doc)
