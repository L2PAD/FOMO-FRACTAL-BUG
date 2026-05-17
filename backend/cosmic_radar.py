"""
Cosmic Radar Engine — Real alpha detection system
Computes: velocity_norm, quality, zone classification, size_norm, radar_score
Stores snapshots in MongoDB for real velocity tracking over time.
"""
import os
import math
import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Query
from pymongo import MongoClient

router = APIRouter(prefix="/api/connections/radar", tags=["cosmic-radar"])

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")
NODE_BACKEND = "http://127.0.0.1:8003"

_client: Optional[MongoClient] = None


def _db():
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URL)
    return _client[DB_NAME]


def _clamp(v, lo, hi):
    return max(lo, min(v, hi))


def _compute_quality(acc: dict) -> float:
    authority = acc.get("authority") or 0
    winrate = acc.get("smart") or 0
    consistency = acc.get("confidence") or 0
    return authority * 0.4 + winrate * 0.4 + consistency * 0.2


def _compute_velocity_from_snapshots(handle: str, current_score: float) -> tuple:
    """Returns (velocity_norm, confidence_level, history_points)"""
    db = _db()
    now = datetime.now(timezone.utc)

    snap_7d = db.radar_snapshots.find_one(
        {"handle": handle, "timestamp": {"$lte": now - timedelta(days=6), "$gte": now - timedelta(days=8)}},
        sort=[("timestamp", -1)]
    )
    snap_1d = db.radar_snapshots.find_one(
        {"handle": handle, "timestamp": {"$lte": now - timedelta(hours=20), "$gte": now - timedelta(days=2)}},
        sort=[("timestamp", -1)]
    )

    if snap_7d and "score" in snap_7d:
        old = snap_7d["score"]
        vel = (current_score - old) / max(old, 0.01)
        return (_clamp(vel, -1, 1), "high", 2)

    if snap_1d and "score" in snap_1d:
        old = snap_1d["score"]
        vel = (current_score - old) / max(old, 0.01)
        return (_clamp(vel, -1, 1), "medium", 1)

    return (0.0, "none", 0)


def _classify_zone(velocity_norm: float, quality: float) -> str:
    if velocity_norm > 0.3 and quality > 0.6:
        return "alpha"
    if velocity_norm > 0.3 and quality <= 0.6:
        return "opportunity"
    if velocity_norm <= 0.3 and quality > 0.6:
        return "stable"
    return "noise"


def _compute_size(followers: int, engagement: float) -> float:
    raw = math.log(max(followers, 1) + 1) * max(engagement, 0.01) * 3
    return _clamp(raw, 4, 20)


def _signal_type(zone: str, badge: str) -> str:
    if badge == "breakout" or zone == "alpha":
        return "breakout"
    if badge == "rising" or zone == "opportunity":
        return "early"
    if zone == "stable":
        return "stable"
    return "noise"


def _get_real_trail(handle: str) -> list:
    """Get real trail from stored snapshots. Returns list of {x, y, t}"""
    db = _db()
    now = datetime.now(timezone.utc)
    snapshots = list(
        db.radar_snapshots.find(
            {"handle": handle, "timestamp": {"$gte": now - timedelta(days=8)}},
            {"_id": 0, "velocity_norm": 1, "quality": 1, "timestamp": 1}
        ).sort("timestamp", 1).limit(5)
    )
    trail = []
    for s in snapshots:
        trail.append({
            "x": round(s.get("velocity_norm", 0), 3),
            "y": round(s.get("quality", 0), 3),
            "t": s["timestamp"].isoformat() if isinstance(s.get("timestamp"), datetime) else str(s.get("timestamp", ""))
        })
    return trail


def _save_snapshot(handle: str, score: float, quality: float, velocity_norm: float, zone: str):
    db = _db()
    db.radar_snapshots.insert_one({
        "handle": handle,
        "score": round(score, 4),
        "quality": round(quality, 4),
        "velocity_norm": round(velocity_norm, 4),
        "zone": zone,
        "timestamp": datetime.now(timezone.utc),
    })


def _generate_insights(actors: list) -> list:
    insights = []
    zone_counts = {"alpha": 0, "opportunity": 0, "stable": 0, "noise": 0}
    for a in actors:
        z = a.get("zone", "noise")
        zone_counts[z] = zone_counts.get(z, 0) + 1

    if zone_counts["alpha"] >= 2:
        insights.append({
            "type": "alpha_cluster",
            "text": f"{zone_counts['alpha']} actors in ALPHA zone",
            "severity": "high"
        })

    high_velocity = [a for a in actors if a.get("velocity_norm", 0) > 0.4]
    if len(high_velocity) >= 3:
        insights.append({
            "type": "momentum_surge",
            "text": f"{len(high_velocity)} actors with strong momentum",
            "severity": "medium"
        })

    opp_actors = [a for a in actors if a.get("zone") == "opportunity"]
    if len(opp_actors) >= 3:
        insights.append({
            "type": "early_trend",
            "text": f"{len(opp_actors)} actors in Opportunity — early trend forming",
            "severity": "medium"
        })

    return insights[:2]


@router.get("/cosmic")
async def cosmic_radar(limit: int = Query(100, ge=1, le=500)):
    """Main cosmic radar endpoint. Fetches actors, computes metrics, stores snapshots."""
    raw_accounts = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{NODE_BACKEND}/api/connections/radar/accounts", params={"limit": limit})
            if resp.status_code == 200:
                data = resp.json()
                raw_accounts = data.get("data", {}).get("accounts", [])
    except Exception:
        pass

    if not raw_accounts:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{NODE_BACKEND}/api/connections/unified", params={"facet": "REAL_TWITTER", "limit": limit})
                if resp.status_code == 200:
                    data = resp.json()
                    raw_accounts = data.get("data", [])
        except Exception:
            pass

    actors = []
    for acc in raw_accounts:
        handle = acc.get("username") or acc.get("handle", "").replace("@", "")
        if not handle:
            continue

        quality = _compute_quality(acc)
        followers = acc.get("followers") or 0
        engagement = acc.get("engagement") or acc.get("engagementRate") or 0
        influence = acc.get("influence") or 0
        authority = acc.get("authority") or 0
        smart = acc.get("smart") or 0
        confidence = acc.get("confidence") or 0

        composite_score = quality * 0.6 + influence * 0.4

        velocity_norm, history_confidence, history_points = _compute_velocity_from_snapshots(handle, composite_score)

        if history_confidence == "none":
            # Use multiple real data attributes for differentiated initial velocity
            raw_vel = acc.get("early_signal", {}).get("velocity", 0) / 100
            early_factor = (acc.get("early", 0) - 0.3) * 1.5
            eng_factor = (engagement - 0.3) * 2
            velocity_norm = _clamp(raw_vel * 0.4 + eng_factor * 0.3 + early_factor * 0.3, -1, 1)

        zone = _classify_zone(velocity_norm, quality)
        size_norm = _compute_size(followers, engagement)
        influence_weight = _clamp(math.log(max(followers, 1) + 1) / 20, 0, 1)
        radar_score = velocity_norm * 0.45 + quality * 0.4 + influence_weight * 0.15
        radar_score = _clamp(radar_score, -1, 1)

        badge = acc.get("early_signal", {}).get("badge", "none")
        sig_type = _signal_type(zone, badge)

        trail = _get_real_trail(handle)

        _save_snapshot(handle, composite_score, quality, velocity_norm, zone)

        actors.append({
            "author_id": acc.get("author_id") or handle,
            "username": handle,
            "display_name": acc.get("title") or acc.get("name") or handle,
            "avatar": acc.get("avatar") or f"https://unavatar.io/twitter/{handle}",
            "followers": followers,
            "velocity_norm": round(velocity_norm, 3),
            "quality": round(quality, 3),
            "zone": zone,
            "radar_score": round(radar_score, 3),
            "size_norm": round(size_norm, 1),
            "signal_type": sig_type,
            "trail": trail,
            "history_confidence": history_confidence,
            "authority": round(authority, 3),
            "winrate": round(smart, 3),
            "consistency": round(confidence, 3),
            "influence": round(influence, 3),
            "engagement": round(engagement, 3),
            "profile": acc.get("profile", "retail"),
            "risk_level": acc.get("risk_level", "medium"),
            "early_badge": badge,
        })

    actors.sort(key=lambda a: a["radar_score"], reverse=True)

    zone_counts = {"alpha": 0, "opportunity": 0, "stable": 0, "noise": 0}
    for a in actors:
        zone_counts[a["zone"]] = zone_counts.get(a["zone"], 0) + 1

    insights = _generate_insights(actors)

    return {
        "ok": True,
        "data": {
            "accounts": actors,
            "zone_counts": zone_counts,
            "insights": insights,
            "total": len(actors),
        }
    }
