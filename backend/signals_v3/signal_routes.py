"""
Signals V3 Routes
=================
GET /api/signals                — unified signals stream (chain-aware)
GET /api/signals/stats          — signal summary statistics
GET /api/signals/{id}/evolution — signal phase history
GET /api/signals/chains         — allowed EVM chains config
"""

from fastapi import APIRouter, Query, Path
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/signals", tags=["signals_v3"])


@router.get("/entity")
def entity_signals(
    chain: str = Query(None),
    min_score: int = Query(None),
):
    """On-chain entity intelligence signals only."""
    try:
        from entity_intelligence.signal_enrichment import generate_entity_signals
        signals = generate_entity_signals(chain_filter=chain)
        if min_score is not None:
            signals = [s for s in signals if s["score"] >= min_score]
        return JSONResponse(content={
            "ok": True,
            "signals": signals,
            "count": len(signals),
            "source": "entity_intelligence",
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})



@router.get("/stats")
def signals_stats():
    """Signal summary statistics (unified: engine + entity)."""
    try:
        from .signal_engine import get_signal_stats, generate_signals
        from entity_intelligence.signal_enrichment import generate_entity_signals

        # Engine signals stats (original)
        engine_stats = get_signal_stats()

        # Add entity signals
        try:
            entity_sigs = generate_entity_signals()
        except Exception:
            entity_sigs = []

        # Merge stats
        all_signals = generate_signals() + entity_sigs
        total = len(all_signals)
        strong = sum(1 for s in all_signals if s.get("severity") in ("STRONG", "EXTREME"))
        extreme = sum(1 for s in all_signals if s.get("severity") == "EXTREME")
        bullish = sum(1 for s in all_signals if s.get("direction") == "BULLISH")
        bearish = sum(1 for s in all_signals if s.get("direction") == "BEARISH")
        avg_score = round(sum(s.get("score", 0) for s in all_signals) / max(total, 1))

        by_type = {}
        for s in all_signals:
            st = s.get("signal_type", "UNKNOWN")
            by_type[st] = by_type.get(st, 0) + 1

        cluster_ids = set(s.get("cluster_id") for s in all_signals if s.get("cluster_id"))
        max_cluster_score = max((s.get("cluster_score", 0) for s in all_signals), default=0)

        return JSONResponse(content={
            "ok": True,
            "total": total,
            "strong": strong,
            "extreme": extreme,
            "bullish": bullish,
            "bearish": bearish,
            "avg_score": avg_score,
            "by_type": by_type,
            "top_signal": engine_stats.get("top_signal"),
            "has_cluster": len(cluster_ids) > 0,
            "cluster_count": len(cluster_ids),
            "max_cluster_score": max_cluster_score,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/chains")
def signals_chains():
    """Return allowed EVM chains config."""
    from .network_guard import CHAIN_CONFIG, ALLOWED_CHAINS
    return JSONResponse(content={
        "ok": True,
        "allowed_chains": ALLOWED_CHAINS,
        "chains": CHAIN_CONFIG,
    })


@router.get("/{signal_id}/evolution")
def signal_evolution(signal_id: str = Path(...)):
    """Get phase history for a specific signal."""
    try:
        from .signal_engine import get_signal_evolution
        phases = get_signal_evolution(signal_id)
        return JSONResponse(content={"ok": True, "phases": phases, "count": len(phases)})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("")
def signals_list(
    severity: str = Query(None),
    direction: str = Query(None),
    signal_type: str = Query(None),
    status: str = Query(None),
    min_score: int = Query(None),
    chain: str = Query(None),
    source: str = Query(None, description="Filter: engine, entity, all"),
):
    """Unified signals stream: engine + entity intelligence signals."""
    try:
        from .signal_engine import get_signals
        from entity_intelligence.signal_enrichment import generate_entity_signals

        filters = {}
        if severity:
            filters["severity"] = severity
        if direction:
            filters["direction"] = direction
        if signal_type:
            filters["signal_type"] = signal_type
        if status:
            filters["status"] = status
        if min_score is not None:
            filters["min_score"] = min_score

        signals = []

        # Engine signals
        if source in (None, "all", "engine"):
            engine_signals = get_signals(filters if filters else None)
            # Engine signals are all ETH - filter if non-ETH chain requested
            if chain and chain not in (None, "all", "ethereum"):
                engine_signals = []
            signals.extend(engine_signals)

        # Entity Intelligence signals (on-chain)
        if source in (None, "all", "entity"):
            try:
                entity_signals = generate_entity_signals(chain_filter=chain)
                # Apply same filters
                if filters.get("severity"):
                    entity_signals = [s for s in entity_signals if s["severity"] == filters["severity"]]
                if filters.get("direction"):
                    entity_signals = [s for s in entity_signals if s["direction"] == filters["direction"]]
                if filters.get("signal_type"):
                    entity_signals = [s for s in entity_signals if s["signal_type"] == filters["signal_type"]]
                if filters.get("status"):
                    entity_signals = [s for s in entity_signals if s["status"] == filters["status"]]
                if filters.get("min_score"):
                    entity_signals = [s for s in entity_signals if s["score"] >= filters["min_score"]]
                signals.extend(entity_signals)
            except Exception as e:
                import traceback
                traceback.print_exc()

        # Discovery signals (smart money, clusters)
        if source in (None, "all", "entity", "discovery"):
            try:
                from pymongo import MongoClient
                import os as _os
                _mc = MongoClient(_os.environ["MONGO_URL"])
                _db = _mc[_os.environ.get("DB_NAME", "intelligence_engine")]
                disc_query = {}
                if chain:
                    disc_query["chain"] = chain
                if filters.get("signal_type"):
                    disc_query["signal_type"] = filters["signal_type"]
                disc_sigs = list(_db.discovery_signals.find(disc_query, {"_id": 0}).sort("score", -1).limit(30))
                # Enrich CLUSTER_ACTIVITY signals with wallet addresses
                cluster_ids = [ds["cluster_id"] for ds in disc_sigs if ds.get("signal_type") == "CLUSTER_ACTIVITY" and ds.get("cluster_id")]
                cluster_wallets = {}
                if cluster_ids:
                    for cdoc in _db.wallet_clusters.find({"cluster_id": {"$in": cluster_ids}}, {"_id": 0, "cluster_id": 1, "wallets": 1}):
                        cluster_wallets[cdoc["cluster_id"]] = cdoc.get("wallets", [])
                # Ensure all timestamps are serializable + attach wallets
                for ds in disc_sigs:
                    for key in list(ds.keys()):
                        val = ds[key]
                        if hasattr(val, 'isoformat'):
                            ds[key] = val.isoformat()
                    if ds.get("signal_type") == "CLUSTER_ACTIVITY" and ds.get("cluster_id") in cluster_wallets:
                        ds["cluster_wallets"] = cluster_wallets[ds["cluster_id"]]
                # Apply filters
                if filters.get("severity"):
                    disc_sigs = [s for s in disc_sigs if s.get("severity") == filters["severity"]]
                if filters.get("direction"):
                    disc_sigs = [s for s in disc_sigs if s.get("direction") == filters["direction"]]
                if filters.get("min_score"):
                    disc_sigs = [s for s in disc_sigs if s.get("score", 0) >= filters["min_score"]]
                signals.extend(disc_sigs)
            except Exception:
                pass

        # Chain filter
        if chain:
            signals = [s for s in signals if s.get("chain", "ethereum") == chain]

        # Sort by score
        signals.sort(key=lambda s: s.get("score", 0), reverse=True)

        return JSONResponse(content={
            "ok": True,
            "signals": signals,
            "count": len(signals),
            "sources": {
                "engine": sum(1 for s in signals if s.get("source") not in ("entity_intelligence", "discovery_worker")),
                "entity_intelligence": sum(1 for s in signals if s.get("source") == "entity_intelligence"),
                "discovery": sum(1 for s in signals if s.get("source") == "discovery_worker"),
            },
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
