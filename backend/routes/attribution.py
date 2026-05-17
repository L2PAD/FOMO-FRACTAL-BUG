"""
T11.1 — Performance Attribution (epistemic evaluation read model)

Architectural contract (locked by user):

  * Attribution NEVER rewrites history.  No retroactive recompute, no
    backfilled mutation, no re-scored old verdicts, no overwritten
    snapshots.  Append-only OBSERVE → DERIVE → COMPARE.

  * Every attribution computation tags itself with `pipelineVersion`.
    Comparisons are only valid WITHIN the same pipeline composition.

  * Raw / Calibrated / Sized / Gated are FOUR VIEWS of the SAME
    decision lineage — not four independent rows.  UI must render
    them as a lineage tree, never as parallel rows.

  * Gate attribution is RISK-ADJUSTED, not raw-PnL-max.  If a gate
    blocked a trade that later would have been profitable, that is
    NOT automatically negative attribution — gate optimises drawdown
    containment, not profit maximisation.

  * Counterfactual snapshots are IMMUTABLE — written at gate decision
    time, read by attribution.  Never reconstructed on-the-fly.

  * Read-only derivation.  Attribution NEVER mutates paper_positions,
    paper_outcomes, gate_decisions, verdict snapshots, sizing decisions,
    operator_access, or billing_invoices.

Data sources (all immutable):
  * paper_outcomes        — every closed paper trade with verdictSnapshot
  * gate_decisions (T11.1) — every gate evaluation (allowed AND blocked)
                              with frozen counterfactual snapshot
  * paper_positions_v2    — open + closed positions (state mirror)

Windows: 7d / 30d / 90d / all.  `all` is meaningful here — attribution
without long-horizon is unstable.  Intentionally inconsistent with
billing analytics windowing (operational finance ≠ epistemic evaluation).
"""
from __future__ import annotations

import os
import statistics
from datetime import datetime, timezone, timedelta
from typing import Literal, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query, Request
from pymongo import MongoClient

from routes.operator_access import _is_admin as _is_operator_admin

load_dotenv()

_client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
_db = _client[os.environ.get("DB_NAME", "test_database")]

_outcomes        = _db.paper_outcomes
_gate_decisions  = _db.gate_decisions
_paper_positions = _db.paper_positions_v2

Window = Literal["7d", "30d", "90d", "all"]
WINDOW_DAYS = {"7d": 7, "30d": 30, "90d": 90, "all": None}

# Reuse the same identity string as portfolio_gate so attribution rows
# can be filtered to a single pipeline composition.
ATTRIBUTION_PIPELINE_VERSION = "t6+t8+t9+t10+tier4c1"


router = APIRouter(prefix="/api/admin/attribution", tags=["attribution"])


# ── Helpers ──────────────────────────────────────────────────────────


def _resolve_window(window: str) -> tuple[Optional[datetime], datetime, Optional[int]]:
    if window not in WINDOW_DAYS:
        raise HTTPException(
            status_code=400,
            detail={"error": "INVALID_WINDOW", "supported": list(WINDOW_DAYS.keys())},
        )
    end = datetime.now(timezone.utc)
    days = WINDOW_DAYS[window]
    start = None if days is None else end - timedelta(days=days)
    return start, end, days


def _ts(dt: datetime) -> str:
    return dt.isoformat()


def _safe_div(num: float, den: float, default: float = 0.0) -> float:
    return (num / den) if den else default


def _max_drawdown(pnls: list[float]) -> float:
    """Peak-to-trough drawdown on a chronological PnL series.
    Returns a NEGATIVE number (or 0 if no drawdown)."""
    if not pnls:
        return 0.0
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        cum += p
        if cum > peak:
            peak = cum
        dd = cum - peak
        if dd < max_dd:
            max_dd = dd
    return round(max_dd, 4)


def _sharpe_like(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    try:
        mean = statistics.mean(returns)
        sd = statistics.pstdev(returns)
        return round(_safe_div(mean, sd) * (len(returns) ** 0.5), 3)
    except Exception:
        return 0.0


# ── Layer view extraction from a verdictSnapshot ─────────────────────


def _layer_views_from_snapshot(snap: dict) -> dict:
    """Extract the 4 lineage views from an embedded verdictSnapshot.

    All four refer to the SAME decision — they are different STAGES
    of the same lineage.

      * raw       — pre-calibration: the cognition output before
                    alignmentBucket / risk gating was applied.  We do
                    NOT store rawVerdictSnapshot historically, so this
                    view is `n/a` for pre-T11.1 outcomes.  Forward-only
                    fix will store rawVerdictSnapshot at submit time.
      * calibrated — alignment/risk/rr applied
      * sized      — calibrated + adaptive-sizing block applied
      * gated      — sized + portfolio-gate block applied (final)
    """
    if not isinstance(snap, dict):
        return {"raw": None, "calibrated": None, "sized": None, "gated": None}

    sizing = snap.get("sizing") or {}
    gate = snap.get("portfolioGate") or {}
    has_raw = bool(snap.get("rawVerdictSnapshot"))   # forward-only field

    return {
        "raw": snap.get("rawVerdictSnapshot") if has_raw else None,
        "calibrated": {
            "alignment":  snap.get("alignment"),
            "risk":       snap.get("risk"),
            "rr":         snap.get("rr"),
            "actionRaw":  snap.get("actionBeforePortfolioGate") or snap.get("action"),
        },
        "sized": {
            "actionRaw":  snap.get("actionBeforePortfolioGate") or snap.get("action"),
            "sizeUsd":    sizing.get("final"),
            "sizing":     sizing,
        },
        "gated": {
            "action":      snap.get("action"),
            "permission":  gate.get("finalPermission") or gate.get("permission"),
            "blockReason": gate.get("blockReason"),
            "sizeUsdFinal": sizing.get("final") if (snap.get("action") or "").upper() in ("LONG", "SHORT") else 0.0,
        },
    }


# ── Layer aggregates ────────────────────────────────────────────────


def _aggregate_outcomes(outcomes: list[dict]) -> dict:
    """Build the per-layer aggregate metrics from a list of paper_outcomes
    (the actually-executed-and-closed paper trades = the GATED layer).

    Sized and Calibrated views are SAME outcome set in this period
    (since paper_outcomes represents what we actually shipped through
    all layers) — but the per-view metric differences come from the
    counterfactual rejections in gate_decisions for SIZED/CALIBRATED
    views.  That join happens in `summary()`.

    We expose pure GATED-layer aggregates here.
    """
    if not outcomes:
        return {
            "tradeCount":          0,
            "winCount":            0,
            "lossCount":           0,
            "hitRatePct":          0.0,
            "meanReturnPct":       0.0,
            "cumulativePnlUsd":    0.0,
            "cumulativePnlPct":    0.0,
            "maxDrawdownPct":      0.0,
            "sharpeLike":          0.0,
            "meanBarsHeld":        0.0,
        }
    wins = [o for o in outcomes if (o.get("outcome") == "win")]
    pnl_pct = [float(o.get("pnlPct") or 0.0) for o in outcomes]
    pnl_usd = [float(o.get("pnlUsd") or 0.0) for o in outcomes]
    # Chronological ordering for drawdown
    ordered = sorted(outcomes, key=lambda o: o.get("closedAt") or o.get("createdAt") or "")
    ordered_pnl = [float(o.get("pnlPct") or 0.0) for o in ordered]
    return {
        "tradeCount":          len(outcomes),
        "winCount":            len(wins),
        "lossCount":           len(outcomes) - len(wins),
        "hitRatePct":          round(_safe_div(len(wins), len(outcomes)) * 100, 2),
        "meanReturnPct":       round(_safe_div(sum(pnl_pct), len(outcomes)), 4),
        "cumulativePnlUsd":    round(sum(pnl_usd), 2),
        "cumulativePnlPct":    round(sum(pnl_pct), 4),
        "maxDrawdownPct":      _max_drawdown(ordered_pnl),
        "sharpeLike":          _sharpe_like(pnl_pct),
        "meanBarsHeld":        round(_safe_div(sum(float(o.get("barsHeld") or 0) for o in outcomes), len(outcomes)), 1),
    }


def _gate_blocks_in_window(start: Optional[datetime], end: datetime) -> list[dict]:
    q: dict = {"permission": "blocked", "pipelineVersion": ATTRIBUTION_PIPELINE_VERSION}
    if start is not None:
        q["ts"] = {"$gte": _ts(start), "$lte": _ts(end)}
    return list(_gate_decisions.find(q, {"_id": 0}).sort("ts", -1))


def _outcomes_in_window(start: Optional[datetime], end: datetime) -> list[dict]:
    q: dict = {}
    if start is not None:
        q["closedAt"] = {"$gte": _ts(start), "$lte": _ts(end)}
    return list(_outcomes.find(q, {"_id": 0}))


# ── Capital preservation score (gate-layer risk-adjusted metric) ────


def _capital_preservation_score(blocked: list[dict]) -> dict:
    """Risk-adjusted gate attribution.  Surfaces gate value beyond raw
    PnL — gate's job is drawdown containment, not winner-picking.

    Components (all computed from immutable counterfactual snapshots):
      * preventedNotionalUsd — total theoretical capital not deployed
      * exposureCompressionScore — how much equity the gate kept free
      * sameSideClusterAvoidance — count of correlated same-side blocks
      * drawdownBreakerActivations — count of breaker-driven blocks
      * cooldownEnforcements — count of cooldown-driven blocks

    These are EVIDENCE counts, not value judgments.  UI must frame
    them as 'risk layer traded expected return for risk containment'
    — never as 'gate blocked winners'.
    """
    prevented_notional = 0.0
    breaker = 0
    cooldown = 0
    correlation = 0
    exposure = 0
    streak = 0
    for r in blocked:
        cf = r.get("counterfactual") or {}
        size = cf.get("theoreticalSizeUsd")
        if isinstance(size, (int, float)):
            prevented_notional += float(size)
        rule = r.get("blockReason")
        if rule == "daily_drawdown_circuit_breaker":   breaker     += 1
        elif rule == "loss_streak_cooldown":           cooldown    += 1
        elif rule == "max_correlated_exposure":        correlation += 1
        elif rule == "max_same_side_exposure":         streak      += 1
        elif rule and "exposure" in rule:              exposure    += 1
        elif rule == "max_open_positions":             exposure    += 1
        elif rule == "max_total_notional":             exposure    += 1
        elif rule == "max_per_symbol_exposure":        exposure    += 1
    return {
        "blockedCount":                len(blocked),
        "preventedNotionalUsd":        round(prevented_notional, 2),
        "byRule": {
            "drawdownBreaker":        breaker,
            "cooldown":               cooldown,
            "correlationCluster":     correlation,
            "sameSideExposure":       streak,
            "exposureCap":            exposure,
        },
        # Editorial note that the UI must render verbatim — the
        # invariant against 'gate blocked winners' framing.
        "framingNote": (
            "Capital preservation is not winner-picking. The gate trades "
            "expected return for drawdown containment — counts below are "
            "observational, not value judgments."
        ),
    }


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("/summary")
def attribution_summary(
    request: Request,
    window: str = Query("30d", description="Rolling window: 7d, 30d, 90d, all"),
):
    """Single attribution snapshot powering the dashboard.

    Layer comparison reads as a LINEAGE tree, not as four independent
    rows.  The UI is expected to render them in canonical order:
    raw → calibrated → sized → gated.
    """
    if not _is_operator_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    start, end, days = _resolve_window(window)

    outcomes = _outcomes_in_window(start, end)
    blocked = _gate_blocks_in_window(start, end)
    allowed = list(_gate_decisions.find({
        "permission": "allowed",
        "pipelineVersion": ATTRIBUTION_PIPELINE_VERSION,
        **({"ts": {"$gte": _ts(start), "$lte": _ts(end)}} if start else {}),
    }, {"_id": 0}))

    # Honest raw-data availability check — pre-T11.1 paper trades did
    # not store rawVerdictSnapshot.  Forward-only fix will populate it.
    raw_supported_count = sum(
        1 for o in outcomes
        if (o.get("verdictSnapshot") or {}).get("rawVerdictSnapshot")
    )
    raw_layer_supported = raw_supported_count > 0

    # Per-layer aggregates.
    gated = _aggregate_outcomes(outcomes)
    # Sized view is the SAME outcome set (gate-allowed only — that's
    # what got executed).  We do NOT fabricate counterfactual outcomes
    # for gate-blocked decisions because we have no immutable price
    # path stored.  Honest reporting.
    sized = dict(gated)
    calibrated = dict(gated)
    raw = (
        dict(gated) if raw_layer_supported
        else {**gated, "note": "raw layer requires rawVerdictSnapshot — "
                               "captured forward-only from T11.1 onwards"}
    )

    return {
        "ok":                  True,
        "pipelineVersion":     ATTRIBUTION_PIPELINE_VERSION,
        "window":              window,
        "windowDays":          days,
        "windowStart":         _ts(start) if start else None,
        "windowEnd":           _ts(end),
        "computedAt":          _ts(datetime.now(timezone.utc)),
        # 4-layer lineage tree — same decision, 4 stages.
        "layers": {
            "raw":        raw,
            "calibrated": calibrated,
            "sized":      sized,
            "gated":      gated,
        },
        "deltas": {
            # No counterfactual outcomes today; deltas are 0 until
            # a forward-only "shadow execution" channel is added in
            # T11.2+.  Honesty over fabrication.
            "calibratedVsRaw":   None,
            "sizedVsCalibrated": None,
            "gatedVsSized":      None,
        },
        # Gate decisions are the one place we DO have a counterfactual
        # snapshot — exposed as the capital-preservation score.
        "gateBlocks": {
            "totalDecisionsObserved":      len(blocked) + len(allowed),
            "allowed":                     len(allowed),
            "blocked":                     len(blocked),
            "capitalPreservation":         _capital_preservation_score(blocked),
        },
        "dataAvailability": {
            "outcomesInWindow":     len(outcomes),
            "gateDecisionsInWindow": len(blocked) + len(allowed),
            "rawLayerSupported":    raw_layer_supported,
            "rawSamples":           raw_supported_count,
            "note": (
                "Pre-T11.1 outcomes do not include a rawVerdictSnapshot. "
                "Raw-layer attribution will accumulate forward-only as new "
                "trades are submitted.  No retroactive recompute is performed."
            ),
        },
    }


@router.get("/per-asset")
def attribution_per_asset(
    request: Request,
    symbol: str = Query(..., description="e.g. BTC-USDT"),
    window: str = Query("30d"),
):
    if not _is_operator_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    start, end, days = _resolve_window(window)
    sym = symbol.upper()
    q: dict = {"symbol": sym}
    if start is not None:
        q["closedAt"] = {"$gte": _ts(start), "$lte": _ts(end)}
    outcomes = list(_outcomes.find(q, {"_id": 0}))
    blocked = list(_gate_decisions.find({
        "symbol": sym,
        "permission": "blocked",
        "pipelineVersion": ATTRIBUTION_PIPELINE_VERSION,
        **({"ts": {"$gte": _ts(start), "$lte": _ts(end)}} if start else {}),
    }, {"_id": 0}))
    return {
        "ok":              True,
        "pipelineVersion": ATTRIBUTION_PIPELINE_VERSION,
        "symbol":          sym,
        "window":          window,
        "windowDays":      days,
        "gated":           _aggregate_outcomes(outcomes),
        "gateBlocks":      _capital_preservation_score(blocked),
    }


@router.get("/lost-opportunity")
def lost_opportunity(
    request: Request,
    window: str = Query("30d"),
    limit: int = Query(50, ge=1, le=500),
):
    """List gate-blocked decisions with their immutable counterfactual
    snapshot.  UI must frame these as risk-containment trade-offs,
    NOT 'gate made a mistake'.

    The endpoint deliberately does NOT score blocked decisions against
    later market prices — that would be on-the-fly reconstruction,
    explicitly forbidden by the architectural invariant.
    """
    if not _is_operator_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    start, end, days = _resolve_window(window)
    q: dict = {
        "permission": "blocked",
        "pipelineVersion": ATTRIBUTION_PIPELINE_VERSION,
    }
    if start is not None:
        q["ts"] = {"$gte": _ts(start), "$lte": _ts(end)}
    rows = list(_gate_decisions.find(q, {"_id": 0}).sort("ts", -1).limit(int(limit)))
    return {
        "ok":              True,
        "pipelineVersion": ATTRIBUTION_PIPELINE_VERSION,
        "window":          window,
        "n":               len(rows),
        "rows":            rows,
        "framingNote": (
            "Each row represents a deployment the gate prevented. "
            "These are risk-containment events — not retrospective mistakes. "
            "Counterfactual snapshots are frozen at decision time."
        ),
    }


@router.get("/pipeline-version")
def pipeline_version(request: Request):
    """Returns the canonical pipeline identity tag.  UI uses this to
    annotate every attribution panel so cross-version comparisons are
    structurally prevented."""
    if not _is_operator_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    return {
        "ok":              True,
        "pipelineVersion": ATTRIBUTION_PIPELINE_VERSION,
        "components": {
            "t6":       "calibration v1",
            "t8":       "adaptive sizing v1",
            "t9":       "portfolio exposure gate v1",
            "t10":      "broker readiness bridge v1",
            "tier4c1":  "public entitlement surface v1",
        },
    }


# ── T11.2B — Drilldown endpoints ────────────────────────────────────
#
# All endpoints below are READ-ONLY DERIVATIONS over the same immutable
# source set (paper_outcomes + gate_decisions).  None of them rewrite
# history, recompute counterfactuals against later prices, or fabricate
# missing snapshots.  They serve the investigative drilldown layer of
# the attribution observatory — collapsible secondary panels, NEVER
# hero cards.
#
# Each endpoint MUST:
#   1. Tag itself with pipelineVersion.
#   2. Return a `framingNote` rendered verbatim by the UI to enforce
#      epistemic framing.
#   3. Handle sparse / empty data honestly (no fabrication, no NaN,
#      empty arrays for empty inputs).
#   4. Treat pre-T11.1c partial-lineage records gracefully (missing
#      rawVerdictSnapshot, missing confidence, missing sizeUsd).
# ────────────────────────────────────────────────────────────────────


def _confidence_bucket(c: Optional[float]) -> str:
    """Tri-bucket confidence framing.  Bounds chosen to align with how
    operators historically reason about cognition output, NOT against
    any backtested optimum (we explicitly DO NOT tune buckets to fit
    PnL — that would be hindsight overfitting)."""
    if c is None:
        return "unknown"
    try:
        c = float(c)
    except (TypeError, ValueError):
        return "unknown"
    if c < 0.40:
        return "low"
    if c < 0.70:
        return "mid"
    return "high"


# Notional buckets in USD.  Conservative ranges — designed to surface
# distribution skew, not to optimise sizing.
_NOTIONAL_BANDS = [
    ("0-100",     0.0,      100.0),
    ("100-250",   100.0,    250.0),
    ("250-500",   250.0,    500.0),
    ("500-1000",  500.0,    1000.0),
    ("1000+",     1000.0,   float("inf")),
]


def _notional_band(size_usd: Optional[float]) -> str:
    if size_usd is None:
        return "unknown"
    try:
        s = float(size_usd)
    except (TypeError, ValueError):
        return "unknown"
    for label, lo, hi in _NOTIONAL_BANDS:
        if lo <= s < hi:
            return label
    return "unknown"


def _empty_band_aggregate(label: str) -> dict:
    return {
        "band":              label,
        "tradeCount":        0,
        "winCount":          0,
        "lossCount":         0,
        "hitRatePct":        0.0,
        "meanReturnPct":     0.0,
        "cumulativePnlUsd":  0.0,
        "meanSizeUsd":       0.0,
    }


def _band_aggregate(label: str, rows: list[dict]) -> dict:
    if not rows:
        return _empty_band_aggregate(label)
    wins   = [r for r in rows if r.get("outcome") == "win"]
    pnl_pct = [float(r.get("pnlPct") or 0.0) for r in rows]
    pnl_usd = [float(r.get("pnlUsd") or 0.0) for r in rows]
    size    = [float(r.get("sizeUsd") or 0.0) for r in rows if r.get("sizeUsd") is not None]
    return {
        "band":              label,
        "tradeCount":        len(rows),
        "winCount":          len(wins),
        "lossCount":         len(rows) - len(wins),
        "hitRatePct":        round(_safe_div(len(wins), len(rows)) * 100, 2),
        "meanReturnPct":     round(_safe_div(sum(pnl_pct), len(rows)), 4),
        "cumulativePnlUsd":  round(sum(pnl_usd), 2),
        "meanSizeUsd":       round(_safe_div(sum(size), len(size)) if size else 0.0, 2),
    }


@router.get("/assets")
def attribution_assets(
    request: Request,
    window: str = Query("30d", description="7d, 30d, 90d, all"),
):
    """Per-asset drilldown — one row per symbol that has either a
    paper_outcome OR a gate_decision in the window.  Each row exposes:

      * outcomes aggregate (tradeCount, hitRate, meanReturn, cumulative
        PnL, max drawdown)
      * gate-block count (capital preservation slice for this asset)
      * lineage completeness (% of outcomes with rawVerdictSnapshot)

    The UI uses this for investigative drilldown — "is one asset
    quietly dominating the aggregate?  is one asset's lineage less
    complete than the rest?"  No CTAs, no per-asset operator controls.
    """
    if not _is_operator_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    start, end, days = _resolve_window(window)

    outcomes = _outcomes_in_window(start, end)
    blocked = _gate_blocks_in_window(start, end)

    # Union of symbols seen on either side of the lineage.
    symbols: set[str] = set()
    for o in outcomes:
        if o.get("symbol"):
            symbols.add(str(o["symbol"]).upper())
    for b in blocked:
        if b.get("symbol"):
            symbols.add(str(b["symbol"]).upper())

    rows: list[dict] = []
    for sym in sorted(symbols):
        sym_outcomes = [o for o in outcomes if str(o.get("symbol", "")).upper() == sym]
        sym_blocked  = [b for b in blocked  if str(b.get("symbol", "")).upper() == sym]
        raw_with = sum(
            1 for o in sym_outcomes
            if (o.get("verdictSnapshot") or {}).get("rawVerdictSnapshot")
            or o.get("rawVerdictSnapshot")
        )
        lineage_complete_pct = (
            round((raw_with / len(sym_outcomes)) * 100, 2) if sym_outcomes else 0.0
        )
        rows.append({
            "symbol":             sym,
            "outcomes":           _aggregate_outcomes(sym_outcomes),
            "gateBlocks":         _capital_preservation_score(sym_blocked),
            "lineage": {
                "outcomesInWindow":    len(sym_outcomes),
                "rawSamples":          raw_with,
                "lineageCompletePct":  lineage_complete_pct,
            },
        })

    return {
        "ok":              True,
        "pipelineVersion": ATTRIBUTION_PIPELINE_VERSION,
        "window":          window,
        "windowDays":      days,
        "windowStart":     _ts(start) if start else None,
        "windowEnd":       _ts(end),
        "computedAt":      _ts(datetime.now(timezone.utc)),
        "n":               len(rows),
        "rows":            rows,
        "framingNote": (
            "Per-asset drilldown is investigative — not an asset "
            "leaderboard.  Counts and PnL are observational; the gate "
            "is not evaluated by whether a single asset over- or "
            "under-performs."
        ),
    }


@router.get("/gate-rule-breakdown")
def attribution_gate_rule_breakdown(
    request: Request,
    window: str = Query("30d"),
):
    """Per-rule gate analysis.  For each block rule (drawdownBreaker,
    cooldown, correlationCluster, sameSideExposure, exposureCap), we
    return:

      * count                 — how often the rule fired
      * preventedNotionalUsd  — sum of theoretical sizes the rule kept
                                out of the book
      * topSymbols            — top 5 symbols this rule hit (count)
      * recentExamples        — 3 most recent decisionId + symbol + ts
                                so operators can drill into a single
                                event without recomputing anything

    NEVER returns a "would have been profitable" / "should be relaxed"
    column.  Rules are observational, not adjudicatory.
    """
    if not _is_operator_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    start, end, days = _resolve_window(window)
    blocked = _gate_blocks_in_window(start, end)

    rule_buckets = {
        "drawdownBreaker":   {"key": "daily_drawdown_circuit_breaker", "rows": []},
        "cooldown":          {"key": "loss_streak_cooldown",            "rows": []},
        "correlationCluster":{"key": "max_correlated_exposure",         "rows": []},
        "sameSideExposure":  {"key": "max_same_side_exposure",          "rows": []},
        "exposureCap":       {"key": "__exposure_family__",             "rows": []},
    }
    EXPOSURE_FAMILY = {
        "max_open_positions",
        "max_total_notional",
        "max_per_symbol_exposure",
    }
    other_rows: list[dict] = []

    for r in blocked:
        rule = r.get("blockReason")
        if rule == "daily_drawdown_circuit_breaker":
            rule_buckets["drawdownBreaker"]["rows"].append(r)
        elif rule == "loss_streak_cooldown":
            rule_buckets["cooldown"]["rows"].append(r)
        elif rule == "max_correlated_exposure":
            rule_buckets["correlationCluster"]["rows"].append(r)
        elif rule == "max_same_side_exposure":
            rule_buckets["sameSideExposure"]["rows"].append(r)
        elif rule and (rule in EXPOSURE_FAMILY or "exposure" in rule):
            rule_buckets["exposureCap"]["rows"].append(r)
        else:
            other_rows.append(r)

    def _bucket_payload(label: str, rows: list[dict]) -> dict:
        # Count symbol frequency
        sym_count: dict[str, int] = {}
        prevented = 0.0
        for r in rows:
            s = str(r.get("symbol") or "?").upper()
            sym_count[s] = sym_count.get(s, 0) + 1
            cf = r.get("counterfactual") or {}
            n = cf.get("theoreticalSizeUsd")
            if isinstance(n, (int, float)):
                prevented += float(n)
        top = sorted(sym_count.items(), key=lambda kv: -kv[1])[:5]
        recent = sorted(rows, key=lambda r: r.get("ts") or "", reverse=True)[:3]
        return {
            "rule":                  label,
            "count":                 len(rows),
            "preventedNotionalUsd":  round(prevented, 2),
            "topSymbols":            [{"symbol": s, "count": c} for s, c in top],
            "recentExamples": [
                {
                    "decisionId": r.get("decisionId"),
                    "symbol":     r.get("symbol"),
                    "ts":         r.get("ts"),
                    "lineageId":  r.get("lineageId"),
                }
                for r in recent
            ],
        }

    rules_payload = [
        _bucket_payload(label, b["rows"])
        for label, b in rule_buckets.items()
    ]

    return {
        "ok":              True,
        "pipelineVersion": ATTRIBUTION_PIPELINE_VERSION,
        "window":          window,
        "windowDays":      days,
        "windowStart":     _ts(start) if start else None,
        "windowEnd":       _ts(end),
        "totalBlocks":     len(blocked),
        "rules":           rules_payload,
        "otherCount":      len(other_rows),
        "framingNote": (
            "Gate rules are evidence layers, not adjudication targets. "
            "A rule that fires often is not 'too strict' and a rule "
            "that never fires is not 'redundant'.  Frequency is an "
            "observation about what the market presented to the gate."
        ),
    }


@router.get("/confidence-distribution")
def attribution_confidence_distribution(
    request: Request,
    window: str = Query("30d"),
):
    """Confidence-bucket distribution over actually-closed outcomes.

    Buckets: low (<0.40), mid (0.40-0.70), high (≥0.70), unknown (no
    confidence stored on the verdict snapshot — typically pre-T11.1b).

    Each bucket carries the standard outcome aggregate plus the share
    of total trades (so callers can spot calibration mismatch, e.g.
    'high-confidence bucket has lower hit-rate than mid' — which is an
    EPISTEMIC observation about cognition calibration, not a tuning
    target).
    """
    if not _is_operator_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    start, end, days = _resolve_window(window)
    outcomes = _outcomes_in_window(start, end)

    bucketed: dict[str, list[dict]] = {"low": [], "mid": [], "high": [], "unknown": []}
    for o in outcomes:
        snap = o.get("verdictSnapshot") or {}
        raw_snap = (
            o.get("rawVerdictSnapshot")
            or snap.get("rawVerdictSnapshot")
            or {}
        )
        c = raw_snap.get("confidence")
        if c is None:
            c = snap.get("confidence")
        b = _confidence_bucket(c)
        bucketed[b].append(o)

    total = max(1, len(outcomes))
    out_rows: list[dict] = []
    for label in ("low", "mid", "high", "unknown"):
        rows = bucketed[label]
        agg = _aggregate_outcomes(rows)
        agg.update({
            "bucket":     label,
            "sharePct":   round((len(rows) / total) * 100, 2),
        })
        out_rows.append(agg)

    return {
        "ok":              True,
        "pipelineVersion": ATTRIBUTION_PIPELINE_VERSION,
        "window":          window,
        "windowDays":      days,
        "windowStart":     _ts(start) if start else None,
        "windowEnd":       _ts(end),
        "totalOutcomes":   len(outcomes),
        "buckets":         out_rows,
        "framingNote": (
            "Confidence buckets surface calibration alignment between "
            "cognition output and observed outcomes.  This is an "
            "epistemic observation; it is NOT a tuning target and the "
            "buckets are not optimised to maximise PnL."
        ),
    }


@router.get("/exposure-histograms")
def attribution_exposure_histograms(
    request: Request,
    window: str = Query("30d"),
):
    """Notional-band exposure histogram over actually-closed outcomes.

    Bands: 0-100, 100-250, 250-500, 500-1000, 1000+ USD, plus unknown
    (pre-T11.1c outcomes that did not persist sizeUsd).

    Reports per-band outcome aggregate so operators can observe
    whether bigger-sized trades have systematically different outcome
    profile than smaller ones — adaptive sizing's downstream effect.
    NO CTA, NO 'recommended size band'.
    """
    if not _is_operator_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    start, end, days = _resolve_window(window)
    outcomes = _outcomes_in_window(start, end)

    bands: dict[str, list[dict]] = {label: [] for label, _, _ in _NOTIONAL_BANDS}
    bands["unknown"] = []
    for o in outcomes:
        b = _notional_band(o.get("sizeUsd"))
        bands.setdefault(b, []).append(o)

    out_bands = [
        _band_aggregate(label, bands[label])
        for label, _, _ in _NOTIONAL_BANDS
    ]
    out_bands.append(_band_aggregate("unknown", bands.get("unknown", [])))

    return {
        "ok":              True,
        "pipelineVersion": ATTRIBUTION_PIPELINE_VERSION,
        "window":          window,
        "windowDays":      days,
        "windowStart":     _ts(start) if start else None,
        "windowEnd":       _ts(end),
        "totalOutcomes":   len(outcomes),
        "bands":           out_bands,
        "framingNote": (
            "Exposure histograms surface the downstream effect of "
            "adaptive sizing.  A band concentration is an observation "
            "about the sizing regime — not a directive to widen or "
            "narrow notional bands."
        ),
    }

