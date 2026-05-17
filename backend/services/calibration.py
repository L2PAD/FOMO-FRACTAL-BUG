"""
calibration — T4 · Feedback / Calibration Runtime.

When a paper position is CLOSED, this module writes a structured outcome
record (`trading_outcomes_v2`) and refreshes the aggregated calibration
table (`trading_calibration_v2`).  The verdict engine reads the table to
decide whether the cognition fusion is historically reliable at the
current alignment quality.

Design discipline:
  * idempotent writeback by positionId (upsert, unique index)
  * recalibrate only the affected (symbol, side, alignmentBucket, risk)
    bucket — NOT a full table sweep
  * graduated reliability ladder (`weak_sample → emerging → usable →
    strong`) so a single bad trade can NEVER hard-block the verdict
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pymongo import MongoClient, DESCENDING

load_dotenv(Path(__file__).parent.parent / ".env", override=False)
logger = logging.getLogger("calibration")

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "test_database")

_client = MongoClient(MONGO_URL)
_db = _client[DB_NAME]

outcomes = _db["trading_outcomes_v2"]
calibration = _db["trading_calibration_v2"]

# Indexes (idempotent)
outcomes.create_index([("positionId", 1)], unique=True)
outcomes.create_index([("symbol", 1), ("side", 1), ("closedAt", DESCENDING)])
calibration.create_index(
    [("symbol", 1), ("side", 1), ("alignmentBucket", 1), ("risk", 1)],
    unique=True,
)

# T6 — Recent (windowed) calibration layer. NEVER overwrites lifetime;
# parallel collection so historical truth stays immutable.
calibration_recent = _db["trading_calibration_recent_v1"]
calibration_recent.create_index(
    [("symbol", 1), ("side", 1), ("alignmentBucket", 1), ("risk", 1), ("window", 1)],
    unique=True,
)

# Rolling windows (days). Order matters — shortest first for verdict overlay.
RECENT_WINDOWS: dict[str, int] = {"30d": 30, "90d": 90}
# Recent buckets are lazy-refreshed if older than this (seconds).
RECENT_REFRESH_TTL_SEC = 600  # 10 min


# ── Bucketing ─────────────────────────────────────────────────────────


def alignment_bucket(score: Optional[float]) -> str:
    """Map alignment score (-1.0 .. +1.0) → coarse bucket.

    Uses absolute value: direction is already encoded in `side`.
    """
    if score is None:
        return "unknown"
    a = abs(float(score))
    if a < 0.33:
        return "0_0.33"
    if a < 0.67:
        return "0.33_0.67"
    return "0.67_1.0"


def _reliability(sample: int) -> str:
    if sample < 5:
        return "weak_sample"
    if sample < 10:
        return "emerging"
    if sample < 25:
        return "usable"
    return "strong"


# ── Writeback ─────────────────────────────────────────────────────────


def record_outcome(position: dict, close_price: float, reason: str, verdict_snapshot: dict | None) -> dict:
    """Write outcome row for a closed position. Idempotent by positionId.

    Args:
        position: the position doc post-close (must include closedAt, closePrice,
                  realizedPnlUsd, realizedPnlPct, entryPrice, side, sizeUsd,
                  symbol, openedAt, positionId, orderId).
        close_price: actual fill price used to close.
        reason: 'stop' | 'target' | 'manual' | ...
        verdict_snapshot: the verdict object captured at submit time (may be None).
    """
    try:
        pos_id = position["positionId"]
        opened_at = position.get("openedAt")
        closed_at = position.get("closedAt") or datetime.now(timezone.utc).isoformat()

        try:
            bars_held = int(
                (
                    datetime.fromisoformat(closed_at.replace("Z", "+00:00")).timestamp()
                    - datetime.fromisoformat(opened_at.replace("Z", "+00:00")).timestamp()
                )
                // 60
            )
        except Exception:
            bars_held = 0

        pnl_pct = float(position.get("realizedPnlPct") or 0.0)
        outcome = "win" if pnl_pct > 0 else "loss"
        align = (verdict_snapshot or {}).get("alignment") or {}
        align_score = align.get("score")
        risk = (verdict_snapshot or {}).get("risk") or "N/A"
        rr = (verdict_snapshot or {}).get("rr")

        doc = {
            "positionId": pos_id,
            "orderId": position.get("orderId"),
            "symbol": position["symbol"],
            "side": position["side"],
            "entry": float(position["entryPrice"]),
            "close": float(close_price),
            "closeReason": reason,
            "outcome": outcome,
            "pnlPct": round(pnl_pct, 4),
            "pnlUsd": float(position.get("realizedPnlUsd") or 0.0),
            "barsHeld": bars_held,
            "alignmentScore": align_score,
            "alignmentBucket": alignment_bucket(align_score),
            "risk": risk,
            "rr": rr,
            "verdictSnapshot": verdict_snapshot,
            "openedAt": opened_at,
            "closedAt": closed_at,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        outcomes.update_one(
            {"positionId": pos_id},
            {"$set": doc, "$setOnInsert": {"firstSeenAt": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )

        # Refresh just the affected lifetime bucket
        _refresh_bucket(
            doc["symbol"], doc["side"], doc["alignmentBucket"], doc["risk"]
        )
        # T6 — refresh recent (windowed) buckets in parallel
        _refresh_recent_buckets(
            doc["symbol"], doc["side"], doc["alignmentBucket"], doc["risk"]
        )
        return {"ok": True, "positionId": pos_id, "outcome": outcome}
    except Exception as e:
        logger.exception(f"[calibration] writeback failed: {e}")
        return {"ok": False, "error": str(e)}


# ── Aggregation ───────────────────────────────────────────────────────


def _refresh_bucket(symbol: str, side: str, bucket: str, risk: str) -> None:
    """Recompute LIFETIME calibration for a single (symbol, side, bucket, risk) cell."""
    cur = outcomes.find(
        {"symbol": symbol, "side": side, "alignmentBucket": bucket, "risk": risk},
        {"_id": 0, "outcome": 1, "closeReason": 1, "pnlPct": 1, "barsHeld": 1},
    )
    rows = list(cur)
    sample = len(rows)
    wins = sum(1 for r in rows if r.get("outcome") == "win")
    losses = sample - wins
    target_hits = sum(1 for r in rows if r.get("closeReason") == "target")
    stop_hits = sum(1 for r in rows if r.get("closeReason") == "stop")
    pnl_sum = sum(float(r.get("pnlPct") or 0.0) for r in rows)
    bars_sum = sum(int(r.get("barsHeld") or 0) for r in rows)

    win_rate = round(wins / sample, 4) if sample else 0.0
    target_rate = round(target_hits / sample, 4) if sample else 0.0
    stop_rate = round(stop_hits / sample, 4) if sample else 0.0
    avg_pnl = round(pnl_sum / sample, 4) if sample else 0.0
    avg_bars = round(bars_sum / sample, 2) if sample else 0.0

    calibration.update_one(
        {"symbol": symbol, "side": side, "alignmentBucket": bucket, "risk": risk},
        {"$set": {
            "symbol": symbol,
            "side": side,
            "alignmentBucket": bucket,
            "risk": risk,
            "sample": sample,
            "wins": wins,
            "losses": losses,
            "winRate": win_rate,
            "targetRate": target_rate,
            "stopRate": stop_rate,
            "avgPnlPct": avg_pnl,
            "avgBarsHeld": avg_bars,
            "reliability": _reliability(sample),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )


def _refresh_recent_window(
    symbol: str, side: str, bucket: str, risk: str, window: str, days: int
) -> None:
    """Recompute a single windowed (symbol, side, bucket, risk, window) cell.

    T6 invariant: NEVER mutates `trading_calibration_v2` (lifetime). Only
    writes to `trading_calibration_recent_v1`.
    """
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    cur = outcomes.find(
        {
            "symbol": symbol, "side": side,
            "alignmentBucket": bucket, "risk": risk,
            "closedAt": {"$gte": cutoff},
        },
        {"_id": 0, "outcome": 1, "closeReason": 1, "pnlPct": 1, "barsHeld": 1},
    )
    rows = list(cur)
    sample = len(rows)
    wins = sum(1 for r in rows if r.get("outcome") == "win")
    losses = sample - wins
    target_hits = sum(1 for r in rows if r.get("closeReason") == "target")
    stop_hits = sum(1 for r in rows if r.get("closeReason") == "stop")
    pnl_sum = sum(float(r.get("pnlPct") or 0.0) for r in rows)
    bars_sum = sum(int(r.get("barsHeld") or 0) for r in rows)

    win_rate = round(wins / sample, 4) if sample else 0.0
    target_rate = round(target_hits / sample, 4) if sample else 0.0
    stop_rate = round(stop_hits / sample, 4) if sample else 0.0
    avg_pnl = round(pnl_sum / sample, 4) if sample else 0.0
    avg_bars = round(bars_sum / sample, 2) if sample else 0.0

    calibration_recent.update_one(
        {"symbol": symbol, "side": side, "alignmentBucket": bucket,
         "risk": risk, "window": window},
        {"$set": {
            "symbol": symbol, "side": side,
            "alignmentBucket": bucket, "risk": risk,
            "window": window, "windowDays": days,
            "windowStart": cutoff,
            "sample": sample, "wins": wins, "losses": losses,
            "winRate": win_rate, "targetRate": target_rate, "stopRate": stop_rate,
            "avgPnlPct": avg_pnl, "avgBarsHeld": avg_bars,
            "reliability": _reliability(sample),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )


def _refresh_recent_buckets(symbol: str, side: str, bucket: str, risk: str) -> None:
    """Refresh ALL configured recent windows for the cell."""
    for window, days in RECENT_WINDOWS.items():
        _refresh_recent_window(symbol, side, bucket, risk, window, days)


def _is_stale(updated_at_iso: Optional[str]) -> bool:
    """True if the bucket needs lazy refresh (older than TTL)."""
    if not updated_at_iso:
        return True
    try:
        from datetime import datetime as _dt
        last = _dt.fromisoformat(updated_at_iso.replace("Z", "+00:00")).timestamp()
        return (datetime.now(timezone.utc).timestamp() - last) > RECENT_REFRESH_TTL_SEC
    except Exception:
        return True


# ── Read API ──────────────────────────────────────────────────────────


def lookup(symbol: str, side: Optional[str] = None,
           bucket: Optional[str] = None, risk: Optional[str] = None) -> Optional[dict]:
    """Get LIFETIME calibration for a specific (symbol, side, bucket, risk) cell."""
    q: dict = {"symbol": symbol.upper()}
    if side:
        q["side"] = side.upper()
    if bucket:
        q["alignmentBucket"] = bucket
    if risk:
        q["risk"] = risk
    doc = calibration.find_one(q, {"_id": 0})
    return doc


def lookup_recent(symbol: str, side: str, bucket: str, risk: str,
                  window: str = "30d") -> Optional[dict]:
    """Get RECENT (windowed) calibration for a specific cell. Lazy-refreshes if stale."""
    q = {"symbol": symbol.upper(), "side": side.upper(),
         "alignmentBucket": bucket, "risk": risk, "window": window}
    doc = calibration_recent.find_one(q, {"_id": 0})
    if doc is None or _is_stale(doc.get("updatedAt")):
        days = RECENT_WINDOWS.get(window)
        if days is not None:
            _refresh_recent_window(symbol.upper(), side.upper(), bucket, risk, window, days)
            doc = calibration_recent.find_one(q, {"_id": 0})
    return doc


def report(symbol: str) -> dict:
    """Full calibration report for symbol — lifetime buckets, recent buckets, summary, warnings."""
    sym = symbol.upper()
    buckets = list(calibration.find({"symbol": sym}, {"_id": 0}).sort("sample", DESCENDING))

    # T6 — recent layer (regime memory)
    recent_30d = list(calibration_recent.find(
        {"symbol": sym, "window": "30d"}, {"_id": 0}
    ).sort("sample", DESCENDING))
    recent_90d = list(calibration_recent.find(
        {"symbol": sym, "window": "90d"}, {"_id": 0}
    ).sort("sample", DESCENDING))

    total_sample = sum(int(b.get("sample") or 0) for b in buckets)
    total_wins = sum(int(b.get("wins") or 0) for b in buckets)
    total_losses = sum(int(b.get("losses") or 0) for b in buckets)
    overall_winrate = round(total_wins / total_sample, 4) if total_sample else 0.0

    recent_30d_sample = sum(int(b.get("sample") or 0) for b in recent_30d)
    recent_30d_wins = sum(int(b.get("wins") or 0) for b in recent_30d)
    recent_30d_wr = round(recent_30d_wins / recent_30d_sample, 4) if recent_30d_sample else 0.0

    warnings: list[str] = []
    if total_sample == 0:
        warnings.append("no_outcomes_yet")
    elif total_sample < 10:
        warnings.append(f"insufficient_data (sample={total_sample}/10)")
    for b in buckets:
        s = int(b.get("sample") or 0)
        wr = float(b.get("winRate") or 0.0)
        if s >= 10 and wr < 0.40:
            warnings.append(
                f"toxic_bucket {b['side']} @ alignment={b['alignmentBucket']} risk={b['risk']} "
                f"winRate={wr} sample={s}"
            )

    # T6 — regime degradation detection (lifetime positive but recent negative)
    for r in recent_30d:
        if int(r.get("sample") or 0) < 5:
            continue
        rwr = float(r.get("winRate") or 0.0)
        lifetime_cell = next(
            (b for b in buckets
             if b["side"] == r["side"] and b["alignmentBucket"] == r["alignmentBucket"]
             and b["risk"] == r["risk"]),
            None,
        )
        if lifetime_cell and float(lifetime_cell.get("winRate") or 0.0) >= 0.50 and rwr < 0.40:
            warnings.append(
                f"regime_degradation {r['side']} @ alignment={r['alignmentBucket']} "
                f"risk={r['risk']} · lifetime={lifetime_cell.get('winRate')} · "
                f"recent30d={rwr} sample={r.get('sample')}"
            )

    return {
        "ok": True,
        "symbol": sym,
        "totalSample": total_sample,
        "totalWins": total_wins,
        "totalLosses": total_losses,
        "overallWinRate": overall_winrate,
        "reliability": _reliability(total_sample),
        "buckets": buckets,
        # T6 — dual-memory
        "recent30d": {
            "totalSample": recent_30d_sample,
            "totalWins": recent_30d_wins,
            "winRate": recent_30d_wr,
            "reliability": _reliability(recent_30d_sample),
            "buckets": recent_30d,
        },
        "recent90d": {
            "buckets": recent_90d,
        },
        "warnings": warnings,
        "thresholds": {
            "observe_only_max": 5,
            "warn_only_max": 10,
            "soft_adjust_max": 25,
            "hard_gate_min": 25,
            "recent_min_sample": 5,
            "recent_degradation_winrate": 0.40,
        },
        "asOf": datetime.now(timezone.utc).isoformat(),
    }


def calibration_block(verdict: dict) -> dict:
    """Build the per-verdict calibration block embedded in /verdict response.

    Returns: { sample, winRate, targetRate, avgPnlPct, reliability,
               appliedAdjustment, note }
    """
    sym = verdict.get("symbol")
    action = (verdict.get("action") or "").upper()
    align = (verdict.get("alignment") or {}).get("score")
    bucket = alignment_bucket(align)
    risk = verdict.get("risk") or "N/A"

    side_for_lookup = action if action in ("LONG", "SHORT") else None

    if side_for_lookup is None:
        return {
            "sample": 0,
            "winRate": None,
            "targetRate": None,
            "avgPnlPct": None,
            "reliability": "weak_sample",
            "alignmentBucket": bucket,
            "appliedAdjustment": "none_wait_verdict",
            "note": "verdict is WAIT — no calibration lookup",
        }

    cell = lookup(sym, side_for_lookup, bucket, risk) or {}
    sample = int(cell.get("sample") or 0)
    reliability = _reliability(sample)
    return {
        "sample": sample,
        "wins": int(cell.get("wins") or 0),
        "losses": int(cell.get("losses") or 0),
        "winRate": cell.get("winRate"),
        "targetRate": cell.get("targetRate"),
        "stopRate": cell.get("stopRate"),
        "avgPnlPct": cell.get("avgPnlPct"),
        "avgBarsHeld": cell.get("avgBarsHeld"),
        "reliability": reliability,
        "alignmentBucket": bucket,
        "risk": risk,
        # appliedAdjustment is set later by apply_to_verdict()
        "appliedAdjustment": "pending",
    }


def apply_to_verdict(verdict: dict) -> dict:
    """Mutate verdict in place with calibration block + graduated adjustments.

    T6 — DUAL-MEMORY priority hierarchy:
      1. If recent_30d sample >= 5 AND recent winRate < 0.40 AND lifetime
         winRate >= 0.50 → regime_degradation: soft-adjust regardless of
         lifetime ladder (recent negative dominates lifetime positive).
      2. If recent_30d sample >= 10 AND recent winRate < 0.35 → hard-gate
         even when lifetime sample is still emerging (active regime hostility).
      3. Otherwise fall through to lifetime-only ladder (T4 contract):
         * sample < 5    → observe only
         * 5 ≤ sample < 10 → warn only
         * 10 ≤ sample < 25 → soft adjust if winRate < 0.45
         * sample ≥ 25 → hard gate if winRate < 0.40

    Key invariant: recent path is GATED on minimum sample (≥5) so a
    single recent loss can never poison a long-built lifetime cell.
    """
    block = calibration_block(verdict)

    # Short-circuit for non-directional verdicts
    if (verdict.get("action") or "").upper() not in ("LONG", "SHORT"):
        verdict["calibration"] = block
        return verdict

    sample = block["sample"]
    wr = block.get("winRate") or 0.0

    # T6 — fetch recent (30d) cell
    sym = verdict.get("symbol")
    side = (verdict.get("action") or "").upper()
    bkt = block.get("alignmentBucket") or alignment_bucket(
        (verdict.get("alignment") or {}).get("score")
    )
    risk = block.get("risk") or verdict.get("risk") or "N/A"
    rec_cell = lookup_recent(sym, side, bkt, risk, "30d") or {}
    rec_sample = int(rec_cell.get("sample") or 0)
    rec_wr = float(rec_cell.get("winRate") or 0.0)

    block["recent30d"] = {
        "sample": rec_sample,
        "wins": int(rec_cell.get("wins") or 0),
        "losses": int(rec_cell.get("losses") or 0),
        "winRate": rec_cell.get("winRate"),
        "targetRate": rec_cell.get("targetRate"),
        "reliability": rec_cell.get("reliability") or "weak_sample",
    }

    # ── T6 path: regime degradation overrides ────────────────────────
    if rec_sample >= 10 and rec_wr < 0.35:
        # Active regime hostility — hard gate even if lifetime ok
        verdict["actionBeforeCalibration"] = verdict.get("action")
        verdict["action"] = "WAIT"
        verdict["entry"] = None
        verdict["stop"] = None
        verdict["target"] = None
        verdict["rr"] = None
        verdict["sizeUsd"] = None
        verdict.setdefault("blockedBy", []).append(
            f"current_regime_hostile (recent30d winRate={rec_wr}, sample={rec_sample})"
        )
        verdict.setdefault("reasons", []).append(
            "Calibration: current regime is actively hostile — deployment refused"
        )
        block["appliedAdjustment"] = "regime_hard_gate"
        block["regimeSignal"] = "actively_hostile"
        verdict["calibration"] = block
        return verdict

    if rec_sample >= 5 and rec_wr < 0.40 and sample >= 10 and wr >= 0.50:
        # Lifetime positive, recent regime degrading — soft adjust regardless
        old_conf = float(verdict.get("confidence") or 0.0)
        verdict["confidence"] = round(max(0.0, old_conf - 0.15), 3)
        verdict["riskBeforeCalibration"] = verdict.get("risk")
        verdict["risk"] = _bump_risk(verdict.get("risk"))
        block["appliedAdjustment"] = "regime_degradation_soft_adjust"
        block["regimeSignal"] = "degrading"
        verdict.setdefault("reasons", []).append(
            f"Calibration: lifetime held up ({int(wr * 100)}% over {sample}) but recent "
            f"follow-through deteriorated ({int(rec_wr * 100)}% over last 30d, sample={rec_sample})"
        )
        verdict["calibration"] = block
        return verdict

    # ── Default: lifetime-only ladder (T4 path) ──────────────────────
    if sample < 5:
        block["appliedAdjustment"] = "observe_only"
    elif sample < 10:
        block["appliedAdjustment"] = "warn_only"
        verdict.setdefault("reasons", []).append(
            f"Calibration: emerging sample ({sample}) for this alignment bucket — "
            f"observe before trusting"
        )
    elif sample < 25:
        if wr is not None and wr < 0.45:
            old_conf = float(verdict.get("confidence") or 0.0)
            verdict["confidence"] = round(max(0.0, old_conf - 0.10), 3)
            verdict["riskBeforeCalibration"] = verdict.get("risk")
            verdict["risk"] = _bump_risk(verdict.get("risk"))
            block["appliedAdjustment"] = "soft_adjust"
            verdict.setdefault("reasons", []).append(
                f"Calibration: historical winRate {wr} (sample={sample}) below 0.45 — "
                f"confidence reduced, risk bumped"
            )
        else:
            block["appliedAdjustment"] = "soft_pass"
    else:
        if wr is not None and wr < 0.40:
            verdict["actionBeforeCalibration"] = verdict.get("action")
            verdict["action"] = "WAIT"
            verdict["entry"] = None
            verdict["stop"] = None
            verdict["target"] = None
            verdict["rr"] = None
            verdict["sizeUsd"] = None
            verdict.setdefault("blockedBy", []).append(
                f"historically_unprofitable_at_this_alignment "
                f"(winRate={wr}, sample={sample})"
            )
            block["appliedAdjustment"] = "hard_gate_wait"
        elif wr is not None and wr < 0.50:
            old_conf = float(verdict.get("confidence") or 0.0)
            verdict["confidence"] = round(max(0.0, old_conf - 0.05), 3)
            block["appliedAdjustment"] = "strong_soft_adjust"
        else:
            block["appliedAdjustment"] = "strong_pass"

    # Annotate regime signal for transparency
    if rec_sample == 0:
        block["regimeSignal"] = "no_recent_sample"
    elif rec_sample < 5:
        block["regimeSignal"] = "recent_sample_emerging"
    elif rec_wr >= 0.55:
        block["regimeSignal"] = "current_regime_compatible"
    elif rec_wr >= 0.45:
        block["regimeSignal"] = "current_regime_mixed"
    else:
        block["regimeSignal"] = "current_regime_weak"

    verdict["calibration"] = block
    return verdict


def _bump_risk(risk: str | None) -> str:
    order = ["LOW", "MED", "HIGH"]
    if risk not in order:
        return risk or "N/A"
    idx = order.index(risk)
    return order[min(idx + 1, len(order) - 1)]
