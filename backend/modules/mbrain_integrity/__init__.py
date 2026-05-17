"""
MBrain Directional Integrity — Module 1: Distribution Audit
═══════════════════════════════════════════════════════════════════════════
Read-only diagnostic of TA-side-car directional generation.

DESIGN CONSTRAINTS (per audit directive):
  • READ-ONLY      — never writes to trading_os, never mutates side-car state
  • HTTP-ONLY      — pulls /api/audit/decisions through the existing gateway
  • AIR-GAPPED     — no imports from /app/F-TRADE-MODULE/, no direct mongo
                     access to trading_os
  • NO SYNTHETIC   — historical real data only; no price reversal, no
                     scenario synthesis
  • NO PRODUCTION INFLUENCE — does not touch aggregator_v1 / shadow fusion

SCOPE OF MODULE 1 (distribution-only):
  • Bucketize TA decisions by:
      asset · timeframe · raw_direction · enforced_direction · final_action
      · confidence_bucket · blocked · reason_chain
  • Compute:
      LONG/SHORT/HOLD share + Shannon entropy + |long-short| imbalance
      + HOLD suppression analysis (SHORT-into-HOLD migration)
      + survival rates  raw → enforced → final  (where SHORT dies)
  • Optional regime tagging (volatility / macro) is OUT OF SCOPE for M1
    (will be added in Module 2 once the data substrate is known).

STORAGE:
  Snapshots written to FOMO `mbrain_integrity_runs` collection
  (in `test_database` — same DB as shadow fusion, NOT trading_os).
"""
from __future__ import annotations

import logging
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

import httpx
from pymongo import DESCENDING, MongoClient

logger = logging.getLogger("mbrain_integrity.distribution")

# ── Constants ─────────────────────────────────────────────────────────────
DB_NAME = os.environ.get("DB_NAME", "test_database")
RUNS_COLLECTION = "mbrain_integrity_runs"
GATEWAY_AUDIT = "/api/audit/decisions"
GATEWAY_BASE = os.environ.get("TRADING_TERMINAL_UPSTREAM", "http://localhost:8002")
HTTP_TIMEOUT = 30.0

CONFIDENCE_BUCKETS = [
    (0.0, 0.5, "lt_0.5"),
    (0.5, 0.6, "0.5_0.6"),
    (0.6, 0.7, "0.6_0.7"),
    (0.7, 0.8, "0.7_0.8"),
    (0.8, 0.9, "0.8_0.9"),
    (0.9, 1.01, "ge_0.9"),
]

DIRECTIONS = ("LONG", "SHORT", "NEUTRAL", "OTHER")


def _db():
    return MongoClient(os.environ["MONGO_URL"])[DB_NAME]


# ── HTTP collector (the only contact point with side-car) ─────────────────

def fetch_audit_decisions(limit: int = 5000) -> list[dict]:
    """Pull raw audit decisions from side-car through HTTP only."""
    url = f"{GATEWAY_BASE}{GATEWAY_AUDIT}?limit={int(limit)}"
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as cl:
            r = cl.get(url)
            r.raise_for_status()
            data = r.json()
        rows = data.get("decisions") or []
        return rows
    except Exception as exc:
        logger.warning("fetch_audit_decisions failed: %s", exc)
        return []


# ── Pure analysis (no side-effects) ───────────────────────────────────────

def _normalise_direction(raw: str) -> str:
    """Map various direction labels to a canonical {LONG, SHORT, NEUTRAL, OTHER}."""
    if not raw:
        return "OTHER"
    s = str(raw).upper().strip()
    if s in ("LONG", "BUY", "BULL", "BULLISH"):
        return "LONG"
    if s in ("SHORT", "SELL", "BEAR", "BEARISH"):
        return "SHORT"
    if s in ("NEUTRAL", "HOLD", "WAIT", "FLAT", "RANGE"):
        return "NEUTRAL"
    return "OTHER"


def _confidence_bucket(c) -> str:
    try:
        v = float(c)
    except Exception:
        return "unknown"
    for lo, hi, name in CONFIDENCE_BUCKETS:
        if lo <= v < hi:
            return name
    return "ge_0.9" if v >= 0.9 else "unknown"


def _shannon_entropy(probs: list[float]) -> float:
    """Entropy in bits. 0.0 = fully determined; log2(k) = uniform across k bins."""
    h = 0.0
    for p in probs:
        if p > 0:
            h -= p * math.log2(p)
    return round(h, 4)


def _safe_share(num: int, den: int) -> float:
    return round(num / den, 4) if den else 0.0


def compute_distribution(rows: list[dict]) -> dict:
    """Aggregate raw audit decisions into distribution metrics. No side-effects."""
    n = len(rows)
    if n == 0:
        return {
            "ok": True,
            "n": 0,
            "note": "No decisions returned by side-car. Either runtime "
                    "session is fresh or audit channel is empty.",
        }

    raw_dir = Counter()
    enforced_dir = Counter()
    final_act = Counter()
    confidence_dist = Counter()
    blocked_n = 0
    block_reasons = Counter()

    by_asset: dict[str, Counter] = defaultdict(Counter)             # raw direction
    by_timeframe: dict[str, Counter] = defaultdict(Counter)         # raw direction
    by_conf: dict[str, Counter] = defaultdict(Counter)              # raw direction
    by_asset_enforced: dict[str, Counter] = defaultdict(Counter)    # enforced
    survival_long = {"raw": 0, "enforced": 0, "final_allowed": 0}
    survival_short = {"raw": 0, "enforced": 0, "final_allowed": 0}
    survival_neutral = {"raw": 0, "enforced": 0, "final_allowed": 0}

    raw_to_enforced = Counter()         # transitions: (raw_dir → enforced_dir)
    enforced_to_final = Counter()       # transitions: (enforced_dir → final_action)

    simulated_n = 0

    for r in rows:
        sym = (r.get("symbol") or "").upper()
        tf = r.get("timeframe") or "?"
        raw = r.get("decision_raw") or {}
        enf = r.get("decision_enforced") or {}
        fa = r.get("final_action") or "?"
        rd = _normalise_direction(raw.get("direction"))
        ed = _normalise_direction(enf.get("direction"))
        cb = _confidence_bucket(raw.get("confidence"))
        blocked = bool(r.get("blocked"))
        reasons_text = " ".join(raw.get("reasons") or []).lower()
        if "simulated" in reasons_text:
            simulated_n += 1

        raw_dir[rd] += 1
        enforced_dir[ed] += 1
        final_act[fa] += 1
        confidence_dist[cb] += 1
        if blocked:
            blocked_n += 1
            br = r.get("block_reason") or "unspecified"
            block_reasons[br] += 1

        if sym:
            by_asset[sym][rd] += 1
            by_asset_enforced[sym][ed] += 1
        by_timeframe[tf][rd] += 1
        by_conf[cb][rd] += 1

        raw_to_enforced[(rd, ed)] += 1
        enforced_to_final[(ed, fa)] += 1

        target = (
            survival_long if rd == "LONG"
            else survival_short if rd == "SHORT"
            else survival_neutral if rd == "NEUTRAL"
            else None
        )
        if target is not None:
            target["raw"] += 1
            if ed == rd:
                target["enforced"] += 1
            if not blocked and fa.startswith("ALLOW"):
                target["final_allowed"] += 1

    # Top-level shares (raw direction)
    long_share = _safe_share(raw_dir["LONG"], n)
    short_share = _safe_share(raw_dir["SHORT"], n)
    neutral_share = _safe_share(raw_dir["NEUTRAL"], n)
    other_share = _safe_share(raw_dir["OTHER"], n)
    imbalance = round(abs(long_share - short_share), 4)
    entropy = _shannon_entropy([long_share, short_share, neutral_share, other_share])

    # HOLD suppression score: how much SHORT could have been suppressed into HOLD?
    # Heuristic: in a balanced regime LONG and SHORT should be roughly equal.
    # If LONG >> SHORT and NEUTRAL is large, the gap (LONG - SHORT) is a *floor*
    # estimate of HOLD-absorbed SHORT.
    hold_suppression_floor = max(0.0, long_share - short_share)
    # Non-trivial only if HOLD itself is large enough to plausibly absorb that.
    hold_can_absorb = neutral_share >= hold_suppression_floor
    hold_suppression_score = round(
        hold_suppression_floor if hold_can_absorb else 0.0, 4
    )

    def to_share_dict(c: Counter, total: int):
        return {k: _safe_share(c.get(k, 0), total) for k in DIRECTIONS}

    asset_breakdown = {
        a: {
            "n": sum(c.values()),
            "raw_share": to_share_dict(c, sum(c.values())),
            "enforced_share": to_share_dict(by_asset_enforced.get(a, Counter()), sum(c.values())),
            "imbalance": round(abs(_safe_share(c.get("LONG", 0), sum(c.values())) -
                                   _safe_share(c.get("SHORT", 0), sum(c.values()))), 4),
            "entropy": _shannon_entropy([
                _safe_share(c.get(k, 0), sum(c.values())) for k in DIRECTIONS
            ]),
        }
        for a, c in by_asset.items()
    }
    timeframe_breakdown = {
        tf: {
            "n": sum(c.values()),
            "raw_share": to_share_dict(c, sum(c.values())),
            "imbalance": round(abs(_safe_share(c.get("LONG", 0), sum(c.values())) -
                                   _safe_share(c.get("SHORT", 0), sum(c.values()))), 4),
        }
        for tf, c in by_timeframe.items()
    }
    confidence_breakdown = {
        cb: {
            "n": sum(c.values()),
            "raw_share": to_share_dict(c, sum(c.values())),
        }
        for cb, c in by_conf.items()
    }

    survival = {
        "LONG": survival_long,
        "SHORT": survival_short,
        "NEUTRAL": survival_neutral,
    }
    # Survival rates per stage
    survival_rates = {}
    for d, s in survival.items():
        if s["raw"] == 0:
            survival_rates[d] = {"raw_to_enforced": None, "enforced_to_final": None}
        else:
            survival_rates[d] = {
                "raw_to_enforced": _safe_share(s["enforced"], s["raw"]),
                "enforced_to_final": _safe_share(s["final_allowed"], s["raw"]),
            }

    return {
        "ok": True,
        "n": n,
        "simulated_data_share": _safe_share(simulated_n, n),
        # ─── Top-level integrity metrics ───
        "raw_direction_share": {
            "LONG": long_share, "SHORT": short_share,
            "NEUTRAL": neutral_share, "OTHER": other_share,
        },
        "enforced_direction_share": {
            k: _safe_share(enforced_dir.get(k, 0), n) for k in DIRECTIONS
        },
        "final_action_share": {
            k: _safe_share(v, n) for k, v in final_act.items()
        },
        "directional_entropy_bits": entropy,
        "directional_entropy_max_bits": round(math.log2(4), 4),  # 4 bins → 2 bits max
        "directional_imbalance": imbalance,
        "hold_suppression_floor": hold_suppression_floor,
        "hold_suppression_score": hold_suppression_score,
        "blocked_share": _safe_share(blocked_n, n),
        "block_reasons": dict(block_reasons),
        # ─── Bucketized breakdowns ───
        "by_asset": asset_breakdown,
        "by_timeframe": timeframe_breakdown,
        "by_confidence": confidence_breakdown,
        # ─── Survival trace ───
        "survival_counts": survival,
        "survival_rates": survival_rates,
        # ─── Raw transitions (for funnel viz) ───
        "raw_to_enforced_transitions": {
            f"{a}->{b}": v for (a, b), v in raw_to_enforced.items()
        },
        "enforced_to_final_transitions": {
            f"{a}->{b}": v for (a, b), v in enforced_to_final.items()
        },
    }


# ── Snapshot persistence (FOMO-side, never trading_os) ────────────────────

def persist_snapshot(metrics: dict, source_count: int) -> str:
    """Write a snapshot to FOMO DB. Returns the inserted _id."""
    col = _db()[RUNS_COLLECTION]
    doc = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "module": "directional_integrity_v1",
        "source": "sidecar.audit.decisions",
        "source_count": int(source_count),
        "metrics": metrics,
    }
    res = col.insert_one(doc)
    return str(res.inserted_id)


def list_snapshots(limit: int = 50) -> list[dict]:
    col = _db()[RUNS_COLLECTION]
    cur = col.find({}, {"metrics": 0}).sort("ts", DESCENDING).limit(int(limit))
    out = []
    for d in cur:
        d["_id"] = str(d.get("_id"))
        out.append(d)
    return out


def latest_snapshot() -> dict | None:
    col = _db()[RUNS_COLLECTION]
    d = col.find_one({}, sort=[("ts", DESCENDING)])
    if not d:
        return None
    d["_id"] = str(d.get("_id"))
    return d


# ── Public façade ─────────────────────────────────────────────────────────

def run_distribution_audit(limit: int = 5000, persist: bool = True) -> dict:
    """End-to-end: pull → compute → optionally persist. Returns metrics."""
    rows = fetch_audit_decisions(limit=limit)
    metrics = compute_distribution(rows)
    out: dict[str, Any] = {
        "ok": metrics.get("ok", True),
        "fetched": len(rows),
        "metrics": metrics,
    }
    if persist and rows:
        out["snapshot_id"] = persist_snapshot(metrics, source_count=len(rows))
    return out


def _ensure_indexes() -> None:
    try:
        col = _db()[RUNS_COLLECTION]
        col.create_index([("ts", DESCENDING)])
        col.create_index("module")
    except Exception as exc:
        logger.warning("ensure_indexes failed: %s", exc)


_ensure_indexes()
