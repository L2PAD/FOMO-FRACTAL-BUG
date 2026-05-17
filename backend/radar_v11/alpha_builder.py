"""
P0.1 — Alpha Dynamic Universe Builder v2
=========================================
Z-score based scoring with full breakdown storage.

Formula:
  alphaScore = 0.35*volatility_z + 0.35*volume_z + 0.20*velocity_z + 0.10*(1-spreadPenalty)

Penalties:
  liqScore < 0.3 → alphaScore *= 0.85
  coverage < MIN_COVERAGE → alphaScore *= 0.70 + qualityFlag

Output:
  - exchange_alpha_candidates: full breakdown per build
  - exchange_symbol_universe_alpha_dynamic: active universe
"""

from typing import List, Dict, Optional
from pymongo import MongoClient, DESCENDING
from datetime import datetime, timezone
import os
import time
import math

_client = None
_db = None


def _get_db():
    global _client, _db
    if _db is None:
        mongo_url = os.environ.get("MONGO_URL")
        _client = MongoClient(mongo_url)
        _db = _client["intelligence_engine"]
    return _db


# ── Config ──

def _cfg():
    return {
        "top_n": int(os.environ.get("ALPHA_TOP_N", "200")),
        "rebuild_min": int(os.environ.get("ALPHA_REBUILD_MINUTES", "60")),
        "min_coverage_pct": int(os.environ.get("ALPHA_MIN_COVERAGE_PCT", "60")),
        "venues": os.environ.get("ALPHA_VENUES", "binance").split(","),
        "min_liq": float(os.environ.get("ALPHA_MIN_LIQ", "0.20")),
        "ema_alpha": 0.3,
        "inertia_bonus": 5,
        "min_lifetime_min": 120,
        "min_score_threshold": 30,
    }


# ── Ignore list ──

_IGNORE = {"BACKFILL2", "BACKFILLMAX", "BACKFILLSRC", "BACKFILLTEST",
           "COVERAGETEST", "LEGACYTICK", "RATELIMITBYPASS"}


# ── Data loading ──

def _load_raw_features() -> Dict[str, Dict]:
    """Load raw features from observations + snapshots."""
    db = _get_db()
    candidates = {}

    # 1. Rich observations
    pipeline = [
        {"$match": {"symbol": {"$nin": list(_IGNORE)}}},
        {"$sort": {"timestamp": DESCENDING}},
        {"$group": {"_id": "$symbol", "doc": {"$first": "$$ROOT"}}},
    ]
    for r in db["exchange_observations"].aggregate(pipeline):
        sym = r["_id"]
        doc = r["doc"]
        ind = doc.get("indicators", {})

        def _v(key):
            raw = ind.get(key, {})
            return raw.get("value", raw) if isinstance(raw, dict) else (raw or 0)

        candidates[sym] = {
            "source": "observations",
            "volume": abs(_v("relative_volume")),
            "volatility": abs(_v("atr_normalized")),
            "velocity": abs(_v("participation_intensity")),
            "spread": _v("spread_pressure"),
            "liqScore": max(0, 1 - _v("spread_pressure") * 0.5 - max(0, 1 - _v("depth_density")) * 0.5),
            "oi": _v("oi_level"),
            "timestamp": doc.get("timestamp", 0),
            "_raw": {
                "relative_volume": _v("relative_volume"),
                "atr_normalized": _v("atr_normalized"),
                "participation_intensity": _v("participation_intensity"),
                "spread_pressure": _v("spread_pressure"),
                "depth_density": _v("depth_density"),
            },
        }

    # 2. Snapshots (wider coverage)
    for doc in db["exchange_symbol_snapshots"].find({}, {"_id": 0}):
        sym = doc.get("base", "") + "USDT"
        if sym in candidates or sym in _IGNORE:
            continue
        f = doc.get("features", {})
        vol_log = f.get("volume_log") or 0
        ret_24h = f.get("ret_24h") or 0
        oi_usd = f.get("oi_usd") or 0

        volume_norm = max(0, min(1, (vol_log - 4) / 5)) if vol_log > 0 else 0
        candidates[sym] = {
            "source": "snapshot",
            "volume": volume_norm,
            "volatility": min(1, abs(ret_24h) * 5),
            "velocity": min(1, abs(ret_24h) * 3),
            "spread": 0.3,
            "liqScore": max(0.2, min(1, (vol_log - 5) / 4)) if vol_log > 0 else 0.2,
            "oi": min(1, oi_usd / 100_000_000) if oi_usd > 0 else 0,
            "timestamp": 0,
            "_raw": {
                "volume_log": vol_log,
                "ret_24h": ret_24h,
                "oi_usd": oi_usd,
            },
        }

    return candidates


# ── Z-score normalization ──

def _zscore_array(values: List[float]) -> List[float]:
    """Compute z-scores, handling edge cases."""
    if not values:
        return []
    n = len(values)
    if n == 1:
        return [0.0]

    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    std = math.sqrt(var) if var > 0 else 1.0

    if std < 1e-8:
        return [0.0] * n

    return [(v - mean) / std for v in values]


def _zscore_to_pct(z: float) -> float:
    """Convert z-score to 0..1 percentile-like score (sigmoid-ish clamp)."""
    return max(0, min(1, (z + 2) / 4))


# ── Alpha score computation ──

def _compute_scores(candidates: Dict[str, Dict], cfg: Dict) -> List[Dict]:
    """Compute alphaScore using z-score normalization."""
    symbols = list(candidates.keys())
    if not symbols:
        return []

    # Extract raw arrays
    vol_raw = [candidates[s]["volume"] for s in symbols]
    volatility_raw = [candidates[s]["volatility"] for s in symbols]
    velocity_raw = [candidates[s]["velocity"] for s in symbols]
    spread_raw = [candidates[s]["spread"] for s in symbols]

    # Z-score normalize
    vol_z = _zscore_array(vol_raw)
    volatility_z = _zscore_array(volatility_raw)
    velocity_z = _zscore_array(velocity_raw)

    results = []
    for i, sym in enumerate(symbols):
        c = candidates[sym]

        # Convert z-scores to 0..1
        vol_pct = _zscore_to_pct(vol_z[i])
        vol_pct_z = _zscore_to_pct(volatility_z[i])
        vel_pct = _zscore_to_pct(velocity_z[i])
        spread_penalty = min(1, max(0, c["spread"]))

        # Formula: 0.35*volatility + 0.35*volume + 0.20*velocity + 0.10*(1-spread)
        raw_score = (
            0.35 * vol_pct_z +
            0.35 * vol_pct +
            0.20 * vel_pct +
            0.10 * (1 - spread_penalty)
        )

        # Penalties
        quality_flags = []
        liq = c["liqScore"]
        if liq < 0.3:
            raw_score *= 0.85
            quality_flags.append("LOW_LIQUIDITY")

        # Coverage check
        source_cov = 100 if c["source"] == "observations" else 60
        if source_cov < cfg["min_coverage_pct"]:
            raw_score *= 0.70
            quality_flags.append("SPARSE_DATA")

        if c["volatility"] < 0.01:
            quality_flags.append("NO_VOLATILITY")
        if c["volume"] < 0.01:
            quality_flags.append("NO_VOLUME")

        alpha_score = int(round(100 * max(0, min(1, raw_score))))

        results.append({
            "symbol": sym,
            "venue": "binance",
            "alphaScore": alpha_score,
            "breakdown": {
                "volZ": round(vol_z[i], 3),
                "volatilityZ": round(volatility_z[i], 3),
                "velocityZ": round(velocity_z[i], 3),
                "spreadPenalty": round(spread_penalty, 3),
                "liqPenalty": round(1 - liq, 3),
                "raw": {
                    "volume": round(c["volume"], 4),
                    "volatility": round(c["volatility"], 4),
                    "velocity": round(c["velocity"], 4),
                    "spread": round(c["spread"], 4),
                    "liqScore": round(liq, 4),
                },
            },
            "sourceCoverage": {
                "type": c["source"],
                "pct": source_cov,
            },
            "qualityFlags": quality_flags,
            "source": c["source"],
            "liqScore": liq,
        })

    return results


# ── Anti-flicker selection ──

def _select_with_antiflicker(scored: List[Dict], cfg: Dict) -> List[Dict]:
    """Select top N with EMA smoothing + inertia bonus."""
    db = _get_db()
    col = db["exchange_symbol_universe_alpha_dynamic"]

    # Load current universe
    current = {}
    for d in col.find({}, {"_id": 0, "symbol": 1, "alphaScore": 1, "updatedAt": 1}):
        current[d["symbol"]] = {
            "score": d.get("alphaScore", 0),
            "updatedAt": d.get("updatedAt"),
        }

    now = datetime.now(timezone.utc)
    alpha = cfg["ema_alpha"]

    for item in scored:
        sym = item["symbol"]
        prev = current.get(sym)

        if prev:
            # EMA smoothing
            ema = (1 - alpha) * item["alphaScore"] + alpha * prev["score"]
            item["alphaScore"] = int(round(ema))

            # Inertia bonus
            item["alphaScore"] = min(100, item["alphaScore"] + cfg["inertia_bonus"])

            # Min lifetime protection
            prev_time = prev.get("updatedAt")
            if prev_time:
                if prev_time.tzinfo is None:
                    prev_time = prev_time.replace(tzinfo=timezone.utc)
                age_min = (now - prev_time).total_seconds() / 60
                if age_min < cfg["min_lifetime_min"] and item["alphaScore"] < cfg["min_score_threshold"]:
                    item["alphaScore"] = cfg["min_score_threshold"]
                    item["qualityFlags"] = item.get("qualityFlags", []) + ["KEPT_BY_LIFETIME"]

    # Filter and sort
    filtered = [
        s for s in scored
        if s["alphaScore"] >= cfg["min_score_threshold"]
        and s["liqScore"] >= cfg["min_liq"]
    ]
    filtered.sort(key=lambda x: x["alphaScore"], reverse=True)
    return filtered[:cfg["top_n"]]


# ── DB write ──

def _write_candidates(scored: List[Dict], selected: List[Dict], cfg: Dict) -> Dict:
    """Write candidates + universe to DB."""
    db = _get_db()
    now = datetime.now(timezone.utc)

    # 1. Write exchange_alpha_candidates (full breakdown)
    cand_col = db["exchange_alpha_candidates"]
    cand_col.create_index([("ts", DESCENDING), ("alphaScore", DESCENDING)])
    cand_col.create_index([("symbol", 1), ("ts", DESCENDING)])

    batch = []
    for rank, item in enumerate(selected, 1):
        batch.append({
            "symbol": item["symbol"],
            "venue": item.get("venue", "binance"),
            "alphaScore": item["alphaScore"],
            "rank": rank,
            "ts": now,
            "breakdown": item["breakdown"],
            "sourceCoverage": item["sourceCoverage"],
            "qualityFlags": item.get("qualityFlags", []),
        })

    if batch:
        cand_col.insert_many(batch)

    # 2. Write exchange_symbol_universe_alpha_dynamic
    uni_col = db["exchange_symbol_universe_alpha_dynamic"]
    uni_col.create_index("symbol", unique=True)
    uni_col.create_index([("alphaScore", DESCENDING)])

    selected_syms = set()
    for rank, item in enumerate(selected, 1):
        uni_col.update_one(
            {"symbol": item["symbol"]},
            {"$set": {
                "symbol": item["symbol"],
                "rank": rank,
                "alphaScore": item["alphaScore"],
                "source": item["source"],
                "updatedAt": now,
                "breakdown": item["breakdown"],
                "qualityFlags": item.get("qualityFlags", []),
            }},
            upsert=True,
        )
        selected_syms.add(item["symbol"])

    removed = uni_col.delete_many({"symbol": {"$nin": list(selected_syms)}})

    return {
        "candidatesWritten": len(batch),
        "universeWritten": len(selected),
        "removed": removed.deleted_count,
        "ts": now.isoformat(),
    }


# ── Main build ──

_last_build = None


def build_alpha_universe() -> Dict:
    """Full pipeline: load → score → select → write."""
    global _last_build
    cfg = _cfg()
    t0 = time.time()

    # Load
    raw = _load_raw_features()
    t_load = time.time() - t0

    # Score
    scored = _compute_scores(raw, cfg)
    t_score = time.time() - t0

    # Select
    selected = _select_with_antiflicker(scored, cfg)
    t_select = time.time() - t0

    # Write
    write_result = _write_candidates(scored, selected, cfg)
    t_write = time.time() - t0

    # Stats
    scores = [s["alphaScore"] for s in selected]
    src_counts = {}
    for s in selected:
        src_counts[s["source"]] = src_counts.get(s["source"], 0) + 1

    flag_counts = {}
    for s in selected:
        for f in s.get("qualityFlags", []):
            flag_counts[f] = flag_counts.get(f, 0) + 1

    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    status = "OK"
    if len(selected) < 50:
        status = "DEGRADED"
    if avg_score < 30:
        status = "DEGRADED"

    result = {
        "ok": True,
        "status": status,
        "config": {k: v for k, v in cfg.items() if k != "ema_alpha"},
        "timing": {
            "loadMs": round(t_load * 1000),
            "scoreMs": round((t_score - t_load) * 1000),
            "selectMs": round((t_select - t_score) * 1000),
            "writeMs": round((t_write - t_select) * 1000),
            "totalMs": round(t_write * 1000),
        },
        "candidates": {
            "total": len(raw),
            "observations": sum(1 for c in raw.values() if c["source"] == "observations"),
            "snapshots": sum(1 for c in raw.values() if c["source"] == "snapshot"),
        },
        "selected": {
            "count": len(selected),
            "sources": src_counts,
            "scoreRange": {"min": min(scores, default=0), "max": max(scores, default=0)},
            "avgScore": avg_score,
        },
        "qualityFlags": dict(sorted(flag_counts.items(), key=lambda x: -x[1])),
        "write": write_result,
        "top10": [
            {"rank": i + 1, "symbol": s["symbol"], "score": s["alphaScore"],
             "source": s["source"], "flags": s.get("qualityFlags", [])}
            for i, s in enumerate(selected[:10])
        ],
        "builtAt": datetime.now(timezone.utc).isoformat(),
    }

    _last_build = result
    return result


def get_last_build_result() -> Optional[Dict]:
    return _last_build


# ── Readers ──

def get_dynamic_alpha_symbols() -> List[str]:
    """Current active alpha universe symbols."""
    db = _get_db()
    docs = list(
        db["exchange_symbol_universe_alpha_dynamic"]
        .find({}, {"_id": 0, "symbol": 1, "alphaScore": 1})
        .sort("alphaScore", DESCENDING)
    )
    return [d["symbol"] for d in docs]


def get_dynamic_alpha_meta() -> Dict:
    """Metadata about current alpha universe."""
    db = _get_db()
    col = db["exchange_symbol_universe_alpha_dynamic"]
    count = col.count_documents({})
    if count == 0:
        return {"type": "dynamic", "count": 0, "status": "EMPTY", "source": "dynamic", "updatedAt": None}

    latest = col.find_one({}, {"_id": 0, "updatedAt": 1}, sort=[("updatedAt", DESCENDING)])
    scores = [d["alphaScore"] for d in col.find({}, {"_id": 0, "alphaScore": 1})]
    sources = {}
    for d in col.find({}, {"_id": 0, "source": 1}):
        s = d.get("source", "unknown")
        sources[s] = sources.get(s, 0) + 1

    return {
        "type": "dynamic",
        "source": "dynamic",
        "count": count,
        "status": "OK" if count >= 50 else "DEGRADED",
        "avgScore": round(sum(scores) / len(scores), 1) if scores else 0,
        "minScore": min(scores, default=0),
        "maxScore": max(scores, default=0),
        "sources": sources,
        "updatedAt": str(latest.get("updatedAt", "")) if latest else None,
    }


def get_alpha_candidates(page: int = 1, page_size: int = 25, venue: str = None) -> Dict:
    """Get paginated alpha candidates from latest build."""
    db = _get_db()
    col = db["exchange_alpha_candidates"]

    # Get latest ts
    latest = col.find_one({}, {"_id": 0, "ts": 1}, sort=[("ts", DESCENDING)])
    if not latest:
        return {"rows": [], "total": 0, "page": page, "pageSize": page_size}

    query = {"ts": latest["ts"]}
    if venue:
        query["venue"] = venue

    total = col.count_documents(query)
    skip = (max(1, page) - 1) * page_size

    docs = list(
        col.find(query, {"_id": 0})
        .sort("alphaScore", DESCENDING)
        .skip(skip)
        .limit(page_size)
    )

    # Serialize datetime
    for d in docs:
        if "ts" in d and hasattr(d["ts"], "isoformat"):
            d["ts"] = d["ts"].isoformat()

    return {
        "rows": docs,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
        "ts": latest["ts"].isoformat() if hasattr(latest["ts"], "isoformat") else str(latest["ts"]),
    }


def get_alpha_stats() -> Dict:
    """Admin stats: coverage, distribution, top movers."""
    db = _get_db()
    col = db["exchange_alpha_candidates"]

    # Get last 2 builds
    builds = list(col.aggregate([
        {"$group": {"_id": "$ts"}},
        {"$sort": {"_id": DESCENDING}},
        {"$limit": 2},
    ]))

    if not builds:
        return {"status": "NO_DATA"}

    latest_ts = builds[0]["_id"]
    latest = list(col.find({"ts": latest_ts}, {"_id": 0, "symbol": 1, "alphaScore": 1, "sourceCoverage": 1, "qualityFlags": 1}))

    # Coverage distribution
    obs_count = sum(1 for r in latest if r.get("sourceCoverage", {}).get("type") == "observations")
    snap_count = sum(1 for r in latest if r.get("sourceCoverage", {}).get("type") == "snapshot")
    avg_score = round(sum(r["alphaScore"] for r in latest) / len(latest), 1) if latest else 0

    # Flag distribution
    flag_dist = {}
    for r in latest:
        for f in r.get("qualityFlags", []):
            flag_dist[f] = flag_dist.get(f, 0) + 1

    # Movers (if 2 builds)
    movers = []
    if len(builds) >= 2:
        prev_ts = builds[1]["_id"]
        prev_map = {r["symbol"]: r["alphaScore"]
                    for r in col.find({"ts": prev_ts}, {"_id": 0, "symbol": 1, "alphaScore": 1})}

        for r in latest:
            prev_score = prev_map.get(r["symbol"])
            if prev_score is not None:
                delta = r["alphaScore"] - prev_score
                if abs(delta) > 3:
                    movers.append({"symbol": r["symbol"], "current": r["alphaScore"], "prev": prev_score, "delta": delta})

        movers.sort(key=lambda x: abs(x["delta"]), reverse=True)

    return {
        "totalCandidates": len(latest),
        "sources": {"observations": obs_count, "snapshots": snap_count},
        "avgScore": avg_score,
        "qualityFlags": flag_dist,
        "topMovers": movers[:10],
        "buildsTracked": len(builds),
        "latestBuild": latest_ts.isoformat() if hasattr(latest_ts, "isoformat") else str(latest_ts),
    }
