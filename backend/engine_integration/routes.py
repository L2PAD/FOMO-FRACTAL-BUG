"""
Engine Integration Routes — E7: Snapshot Intelligence Layer
=============================================================
GET /api/engine/context         — Read from pre-computed snapshot (fast)
GET /api/engine/alerts          — Alert Engine (E6)
GET /api/engine/history/setups  — Setup history timeline
GET /api/engine/history/micro   — Micro snapshots for timeline
"""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/engine", tags=["engine-integration"])


@router.get("/context")
def engine_context(
    chainId: int = Query(1),
    window: str = Query("30d"),
):
    """
    Engine Context — reads from pre-computed snapshot.
    Falls back to live calculation if no snapshot or snapshot is stale (>180s).
    """
    try:
        from .engine_snapshot_service import get_latest_snapshot, get_snapshot_age_seconds

        snapshot = get_latest_snapshot()
        age = get_snapshot_age_seconds()

        if snapshot and age <= 180:
            # Serve from snapshot — fast path (20-40ms)
            snapshot["snapshot_meta"] = snapshot.get("snapshot_meta", {})
            snapshot["snapshot_meta"]["age_seconds"] = round(age, 1)
            snapshot["snapshot_meta"]["served_from"] = "snapshot"
            return JSONResponse(content={"ok": True, **snapshot})

        # Fallback — live calculation (snapshot missing or stale)
        from .service import get_integrated_engine_context
        ctx = get_integrated_engine_context(chain_id=chainId, window=window)
        ctx["snapshot_meta"] = {
            "age_seconds": 0,
            "served_from": "live",
            "engine_version": "4.5",
        }

        # Trigger background rebuild if stale
        if age > 180:
            try:
                from .engine_snapshot_service import build_engine_snapshot
                import threading
                threading.Thread(target=build_engine_snapshot, daemon=True).start()
            except Exception:
                pass

        return JSONResponse(content={"ok": True, **ctx})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/alerts")
def engine_alerts(limit: int = Query(50)):
    """E6: Get all active (non-expired) alerts."""
    try:
        from .engine_alert_service import get_all_alerts
        alerts = get_all_alerts(limit=limit)
        return JSONResponse(content={"ok": True, "alerts": alerts, "count": len(alerts)})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/history/setups")
def engine_setup_history(limit: int = Query(50)):
    """E7: Setup history timeline — tracks setup type/status changes over time."""
    try:
        from .engine_snapshot_service import get_setup_history
        history = get_setup_history(limit=limit)
        return JSONResponse(content={"ok": True, "history": history, "count": len(history)})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/history/micro")
def engine_micro_snapshots(limit: int = Query(100)):
    """E7: Micro snapshots for timeline visualization."""
    try:
        from .engine_snapshot_service import get_micro_snapshots
        snapshots = get_micro_snapshots(limit=limit)
        return JSONResponse(content={"ok": True, "snapshots": snapshots, "count": len(snapshots)})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/monitoring/events")
def monitoring_events(limit: int = Query(100)):
    """Monitoring Radar — categorized events with clustering and intensity."""
    try:
        from .engine_alert_service import get_all_alerts, CATEGORY_MAP, _impact_score
        alerts = get_all_alerts(limit=limit)

        # Enrich old alerts missing event_category / impact_score
        for a in alerts:
            if not a.get("event_category"):
                a["event_category"] = CATEGORY_MAP.get(a.get("type", ""), "critical")
            if not a.get("impact_score"):
                a["impact_score"] = _impact_score(a.get("severity", "INFO"), a.get("confidence", 0))

        # Cluster similar alerts (same type within 30min)
        clusters: dict = {}
        for a in alerts:
            cluster_key = a.get("type", "unknown")
            if cluster_key not in clusters:
                clusters[cluster_key] = {"count": 0, "latest": a, "events": []}
            clusters[cluster_key]["count"] += 1
            clusters[cluster_key]["events"].append(a)

        # Add cluster_size to each alert
        for a in alerts:
            a["cluster_size"] = clusters.get(a.get("type", ""), {}).get("count", 1)

        # Calculate intensity per category
        category_intensity: dict = {}
        for a in alerts:
            cat = a.get("event_category", "critical")
            if cat not in category_intensity:
                category_intensity[cat] = {"count": 0, "high_impact": 0}
            category_intensity[cat]["count"] += 1
            if a.get("impact_score") == "HIGH":
                category_intensity[cat]["high_impact"] += 1

        # Group by event_category
        categories = {"critical": [], "liquidity": [], "actor": [], "setup": [], "flow": []}
        for a in alerts:
            cat = a.get("event_category", "critical")
            if cat in categories:
                categories[cat].append(a)
            else:
                categories["critical"].append(a)

        # Compute category intensity levels
        intensity = {}
        for cat, stats in category_intensity.items():
            cnt = stats["count"]
            hi = stats["high_impact"]
            if hi >= 3 or cnt >= 8:
                intensity[cat] = "extreme"
            elif hi >= 1 or cnt >= 4:
                intensity[cat] = "high"
            elif cnt >= 2:
                intensity[cat] = "moderate"
            else:
                intensity[cat] = "low"

        return JSONResponse(content={
            "ok": True,
            "events": categories,
            "timeline": alerts[:30],
            "total": len(alerts),
            "intensity": intensity,
            "clusters": {k: v["count"] for k, v in clusters.items() if v["count"] > 1},
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
