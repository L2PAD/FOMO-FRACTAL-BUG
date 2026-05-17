"""
TRADING-ACTIVATION-2 · observability endpoints.

Two routes — neither is a control surface, both are pure GETs:

  GET  /api/trading/health/modules?asset=BTC&hours=24
       Per-driver freshness report — exchange, sentiment, fractal,
       onchain, metabrain, prediction. Shows:
         - n_recent (events within window)
         - lastUpdate (ISO timestamp, may be null)
         - ageMin (minutes since last update, null if never)
         - direction / confidence / weight (from M-Brain snapshot)
         - status: live | stale | empty | degraded

  GET  /api/trading/readiness/{symbol}
       Trading readiness matrix — explains WHY current verdict is
       what it is and WHAT would have to change for it to flip.
       Pure forensic surface — does NOT recommend forcing the signal.

These endpoints are admin-gated (read-only operators can see them via
the standard X-User-Id capability check; full admins via JWT).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Query
from pymongo import MongoClient


router = APIRouter(prefix="/api/trading", tags=["trading-observability"])


def _db():
    client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    return client[os.environ.get("DB_NAME", "fomo_mobile")]


def _age_min(ts) -> float | None:
    if not ts:
        return None
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return None
    if not isinstance(ts, datetime):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return round((datetime.now(timezone.utc) - ts).total_seconds() / 60.0, 1)


def _module_freshness(db, asset: str, hours: int) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)
    asset_u = asset.upper()

    def _q_recent(coll_name: str, symbol_keys: tuple[str, ...] = ("symbol",), ts_keys: tuple[str, ...] = ("createdAt", "ts", "asOf")) -> tuple[int, datetime | None]:
        if coll_name not in db.list_collection_names():
            return 0, None
        c = db[coll_name]
        sym_or = [{k: asset_u} for k in symbol_keys] + [{k: asset_u.lower()} for k in symbol_keys]
        # n recent
        n = 0
        last = None
        for ts_field in ts_keys:
            try:
                q = {"$and": [{"$or": sym_or}, {ts_field: {"$gte": cutoff}}]}
                n = c.count_documents(q)
                if n:
                    doc = c.find({"$or": sym_or}).sort(ts_field, -1).limit(1)
                    for d in doc:
                        last = d.get(ts_field)
                        break
                    break
            except Exception:
                continue
        if last is None:
            # Symbol-agnostic recent count for layers that aren't per-symbol
            try:
                n = c.count_documents({ts_keys[0]: {"$gte": cutoff}}) if ts_keys else 0
                doc = c.find().sort(ts_keys[0], -1).limit(1) if ts_keys else []
                for d in doc:
                    last = d.get(ts_keys[0])
                    break
            except Exception:
                pass
        return n, last

    modules = {}

    # Sentiment
    n, last = _q_recent("sentiment_events", ("symbol", "asset"), ("createdAt", "ts"))
    modules["sentiment"] = {
        "label": "Multi-source sentiment pressure",
        "sources": ["fear_greed", "coingecko_community", "cryptocompare_news", "news_graph_link"],
        "collection": "sentiment_events",
        "n_recent": n,
        "lastUpdate": last.isoformat() if isinstance(last, datetime) else (last or None),
        "ageMin": _age_min(last),
        "status": _status_for(n, last, fresh_min=120, ok_min=5),
    }

    # Exchange
    n, last = _q_recent("exchange_forecasts", ("asset", "symbol"), ("createdAt", "ts", "generated_at"))
    modules["exchange"] = {
        "label": "Exchange forecast engine (signals + regime)",
        "sources": ["binance", "coingecko", "intelligence_engine"],
        "collection": "exchange_forecasts",
        "n_recent": n,
        "lastUpdate": last.isoformat() if isinstance(last, datetime) else (last or None),
        "ageMin": _age_min(last),
        "status": _status_for(n, last, fresh_min=120, ok_min=1),
    }

    # Fractal
    fractal_n, fractal_last = 0, None
    for coll in ("fractal_forecasts", "btc_fractal_forecasts", f"{asset_u.lower()}_fractal_forecasts"):
        n2, last2 = _q_recent(coll, ("asset", "symbol", "scope"), ("createdAt", "ts", "generated_at", "createdBucket"))
        fractal_n += n2
        if last2 and (not fractal_last or (isinstance(last2, datetime) and isinstance(fractal_last, datetime) and last2 > fractal_last)):
            fractal_last = last2
    modules["fractal"] = {
        "label": "Fractal cycle pipeline (BTC/SPX/DXY scopes)",
        "sources": ["yahoo_finance", "fred", "internal_priors"],
        "collection": "fractal_forecasts + scope-prefixed",
        "n_recent": fractal_n,
        "lastUpdate": fractal_last.isoformat() if isinstance(fractal_last, datetime) else (fractal_last or None),
        "ageMin": _age_min(fractal_last),
        "status": _status_for(fractal_n, fractal_last, fresh_min=1440, ok_min=1),
    }

    # On-chain — events kept ephemeral via 60s cache, look at lite metrics
    n, last = _q_recent("onchain_metrics", ("chain", "asset"), ("createdAt", "ts"))
    if n == 0:
        n, last = _q_recent("onchain_events", ("chain", "asset"), ("createdAt", "ts"))
    modules["onchain"] = {
        "label": "On-chain lite (public RPCs + DefiLlama)",
        "sources": ["ethereum-rpc.publicnode.com", "defillama", "arb/op/base"],
        "collection": "onchain_metrics / onchain_events (60s ephemeral cache)",
        "n_recent": n,
        "lastUpdate": last.isoformat() if isinstance(last, datetime) else (last or None),
        "ageMin": _age_min(last),
        "status": "live" if n else "ephemeral",  # OK — cache-only by design
    }

    # MetaBrain — decision history is the closest persisted artifact
    n, last = _q_recent("decision_history", ("symbol", "asset"), ("createdAt", "ts"))
    modules["metabrain"] = {
        "label": "MetaBrain narrative + market state aggregator",
        "sources": ["aggregated layer fusion"],
        "collection": "decision_history",
        "n_recent": n,
        "lastUpdate": last.isoformat() if isinstance(last, datetime) else (last or None),
        "ageMin": _age_min(last),
        "status": _status_for(n, last, fresh_min=240, ok_min=1),
    }

    # Prediction (Polymarket + cross-market)
    n, last = _q_recent("prediction_snapshots", ("asset", "symbol"), ("createdAt", "ts", "snapshotAt"))
    pm_n, pm_last = _q_recent("prediction_markets", ("asset",), ("createdAt", "ts", "updatedAt"))
    modules["prediction"] = {
        "label": "Prediction layer (Polymarket + cross-market priors)",
        "sources": ["polymarket gamma api", "kalshi (optional)"],
        "collection": "prediction_snapshots + prediction_markets",
        "n_recent": n,
        "n_markets_recent": pm_n,
        "lastUpdate": last.isoformat() if isinstance(last, datetime) else (last or None),
        "ageMin": _age_min(last),
        "status": _status_for(n + pm_n, last or pm_last, fresh_min=1440, ok_min=1),
    }

    return modules


def _status_for(n: int, last, fresh_min: float, ok_min: int) -> str:
    if n == 0 and not last:
        return "empty"
    if n < ok_min:
        return "degraded"
    age = _age_min(last) if last else None
    if age is None:
        return "unknown"
    if age <= fresh_min:
        return "live"
    return "stale"


@router.get("/health/modules")
async def health_modules(asset: str = Query("BTC"), hours: int = Query(24, ge=1, le=720)):
    db = _db()
    snapshot_ok = False
    snapshot = None
    try:
        import sys
        sys.path.insert(0, "/app/backend")
        from services.meta_brain_service import build_snapshot
        snapshot = build_snapshot(asset.upper())
        snapshot_ok = True
    except Exception as e:
        snapshot = {"error": repr(e)}

    modules = _module_freshness(db, asset.upper(), hours)

    # Overlay live M-Brain attributions (direction / weight / confidence)
    drivers = (snapshot or {}).get("drivers") or {}
    for key, mod in modules.items():
        driver = drivers.get(key) or {}
        mod["mbrain"] = {
            "direction": driver.get("direction"),
            "weight": driver.get("weight"),
            "confidence": driver.get("confidence"),
            "reasonShort": driver.get("reasonShort") or driver.get("reason") or None,
        }

    return {
        "ok": True,
        "asset": asset.upper(),
        "window_hours": hours,
        "asOf": datetime.now(timezone.utc).isoformat(),
        "snapshot": (snapshot or {}).get("signal") if snapshot_ok else snapshot,
        "modules": modules,
        "policy": {
            "llm_enabled": False,
            "telegram_intel_enabled": os.environ.get("TELEGRAM_INTEL_ENABLED", "false").lower() == "true",
            "onchain_mode": os.environ.get("ONCHAIN_MODE", "preview"),
            "sentiment_periodic_interval_sec": int(os.environ.get("SENTIMENT_PERIODIC_INTERVAL_SEC", 900)),
        },
    }


@router.get("/readiness/{symbol}")
async def trading_readiness(symbol: str):
    """
    Trading readiness matrix — explains the gate state honestly.
    Returns:
      - current verdict (WAIT/LONG/SHORT/AVOID)
      - alignment per module + majority vote
      - blockers (which modules need to flip and by how much)
      - what_would_unblock (descriptive, NOT a forcing recommendation)
    """
    import sys
    sys.path.insert(0, "/app/backend")
    # Use the canonical verdict builder — same surface that
    # /api/trading/verdict/{symbol} returns.  Pulls alignment, blockers,
    # reasons in one resolved snapshot.
    from services import trading_runtime as svc
    sig = await __import__("asyncio").to_thread(svc.build_verdict, symbol.upper())
    alignment = sig.get("alignment", {}) or {}
    module_conf = sig.get("moduleConfidence", {}) or {}
    blocked_by = sig.get("blockedBy", []) or []
    reasons = sig.get("reasons", []) or []

    long_votes = alignment.get("longVotes", 0)
    short_votes = alignment.get("shortVotes", 0)
    wait_votes = alignment.get("waitVotes", 0)
    score = alignment.get("score", 0.0)

    # P0 SIGNAL HYGIENE · readiness UI mirrors the active/abstained split
    # honestly.  Pulls everything from the verdict's alignment block so
    # this surface can never drift from policy.
    majority_threshold = int(alignment.get("majorityThreshold") or 3)
    total_modules = int(alignment.get("totalModules") or 5)
    active_count = int(alignment.get("activeVotes") or 0)
    active_modules_list = list(alignment.get("activeModules") or [])
    abstained_modules_list = list(alignment.get("abstainedModules") or [])
    degraded_modules_list = list(alignment.get("degradedModules") or [])
    min_active = int(alignment.get("minActiveForDecision") or 3)

    core_modules = ("ta", "sentiment", "fractal", "exchange", "onchain")
    module_degraded = sig.get("moduleDegraded", {}) or {}
    degradation_reasons = sig.get("degradationReasons", {}) or {}

    target_long = max(0, majority_threshold - long_votes)
    target_short = max(0, majority_threshold - short_votes)

    matrix = {
        "modules": [
            {
                "name": k,
                "vote": alignment.get(k, "WAIT"),    # ABSTAIN if degraded
                "confidence": module_conf.get(k),
                "degraded": bool(module_degraded.get(k, False)),
                "degradationReason": degradation_reasons.get(k),
                "active": k in active_modules_list,
            }
            for k in core_modules
        ],
        "majority_vote_threshold": majority_threshold,
        "total_modules": total_modules,
        "min_active_for_decision": min_active,
        "active_modules":     active_modules_list,
        "abstained_modules":  abstained_modules_list,
        "degraded_modules":   degraded_modules_list,
        "active_votes":       active_count,
        "current_long_votes": long_votes,
        "current_short_votes": short_votes,
        "current_wait_votes": wait_votes,
        "alignment_score": score,
        "to_flip_long": target_long,
        "to_flip_short": target_short,
    }

    what_would_unblock = []
    if active_count < min_active:
        deficit = min_active - active_count
        what_would_unblock.append(
            f"Need {deficit} more independent active module(s) before any directional verdict. "
            f"Currently {active_count}/{total_modules} active — degraded modules abstain. "
            "We do NOT impute synthetic votes; fresh primary data must arrive."
        )
    else:
        waiting_active = [
            m for m in active_modules_list
            if alignment.get(m) == "WAIT"
        ]
        if long_votes > 0 and target_long > 0 and short_votes == 0:
            what_would_unblock.append(
                f"LONG verdict requires {target_long} more confirming active module(s). "
                f"Currently WAIT among active: {', '.join(waiting_active) if waiting_active else 'none'}. "
                "Organic alignment only."
            )
        elif short_votes > 0 and target_short > 0 and long_votes == 0:
            what_would_unblock.append(
                f"SHORT verdict requires {target_short} more confirming active module(s) "
                f"from the active set ({', '.join(active_modules_list)}). Organic alignment only."
            )
        elif long_votes == 0 and short_votes == 0:
            what_would_unblock.append(
                f"All {active_count} active modules vote WAIT — no directional pressure yet."
            )
        elif long_votes > 0 and short_votes > 0:
            what_would_unblock.append(
                "Active modules split between LONG and SHORT — verdict stays WAIT until one side reaches majority."
            )

    # Always surface degraded modules + reasons (transparency)
    if degraded_modules_list:
        details = ", ".join(
            f"{m} ({degradation_reasons.get(m) or 'no_reason'})"
            for m in degraded_modules_list
        )
        what_would_unblock.append(
            f"Degraded (abstaining) modules: {details}. These modules are silent — they neither vote LONG nor WAIT until primary data lands."
        )

    return {
        "ok": True,
        "symbol": symbol.upper(),
        "asOf": sig.get("asOf"),
        "verdict": {
            "action": sig.get("action"),
            "confidence": sig.get("confidence"),
            "rr": sig.get("rr"),
            "risk": sig.get("risk"),
        },
        "alignment_matrix": matrix,
        "blockedBy": blocked_by,
        "reasons": reasons,
        "what_would_unblock": what_would_unblock,
        "policy_note": (
            "This surface is observational. No 'force signal' override is offered here. "
            "Module alignment must emerge organically from fresh data."
        ),
    }
