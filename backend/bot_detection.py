"""
Bot Detection API — Serves farm graph, bot farms, and audience quality data.
Reads from MongoDB collections: bot_farms, farm_graph_edges, audience_quality.
Pipeline endpoint triggers real compute via bot_detection_engine.
"""
import os
import logging
from fastapi import APIRouter, Query, BackgroundTasks
from pymongo import MongoClient
from typing import Optional

logger = logging.getLogger("bot_detection")

router = APIRouter(tags=["bot-detection"])

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")

_client: Optional[MongoClient] = None


def _db():
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URL)
    return _client[DB_NAME]


# Dynamic colors — cycle through palette for any number of farms
FARM_PALETTE = [
    '#ef4444', '#f59e0b', '#8b5cf6', '#3b82f6', '#ec4899',
    '#10b981', '#f97316', '#6366f1', '#14b8a6', '#e11d48',
]


@router.get("/api/connections/bot-farms")
async def get_bot_farms(limit: int = Query(100), minConfidence: float = Query(0.1)):
    db = _db()
    farms = list(db.bot_farms.find(
        {"confidence": {"$gte": minConfidence}},
        {"_id": 0}
    ).sort("clusterBotScore", -1).limit(limit))
    return {"ok": True, "data": farms, "total": len(farms)}


@router.get("/api/connections/network/farm-graph")
async def get_farm_graph(minScore: float = Query(0.1), limit: int = Query(200)):
    db = _db()
    edges_raw = list(db.farm_graph_edges.find(
        {"overlapScore": {"$gte": minScore}},
        {"_id": 0}
    ).sort("overlapScore", -1).limit(limit))

    # Build node set from edges
    node_ids = set()
    for e in edges_raw:
        node_ids.add(e["a"])
        node_ids.add(e["b"])

    # Enrich nodes with audience quality
    aq_map = {}
    for doc in db.audience_quality.find({"actorId": {"$in": list(node_ids)}}, {"_id": 0}):
        aq_map[doc["actorId"]] = doc

    # Build farmId→color map from existing farms
    farm_color_map = {}
    for farm in db.bot_farms.find({}, {"_id": 0, "farmId": 1, "actorIds": 1}):
        fid = farm.get("farmId", "")
        idx = int(fid.replace("farm_", "")) if fid.startswith("farm_") and fid.replace("farm_", "").isdigit() else hash(fid)
        farm_color_map[fid] = FARM_PALETTE[abs(idx) % len(FARM_PALETTE)]
        # Map actor→farmId
        for actor_id in farm.get("actorIds", []):
            if actor_id not in aq_map:
                aq_map[actor_id] = {}
            aq_map[actor_id]["_farmId"] = fid

    nodes = []
    for nid in node_ids:
        aq = aq_map.get(nid, {})
        bot_pct = aq.get("pctBot", 0)
        level = aq.get("level", "UNKNOWN")
        risk = "high" if bot_pct > 40 else "medium" if bot_pct > 15 else "low"
        nodes.append({
            "id": nid,
            "label": f"@{nid}",
            "botScore": aq.get("botScore", bot_pct / 100),
            "audienceQuality": aq.get("aqi", 50),
            "pctHuman": aq.get("pctHuman", 50),
            "pctBot": bot_pct,
            "pctSuspicious": aq.get("pctSuspicious", 0),
            "level": level,
            "risk": risk,
            "farmId": aq.get("_farmId", ""),
            "avatar": f"https://unavatar.io/twitter/{nid}",
        })

    edges = []
    for e in edges_raw:
        fid = e.get("farmId", "")
        color = farm_color_map.get(fid, "#94a3b8")
        edges.append({
            "a": e["a"],
            "b": e["b"],
            "source": e["a"],
            "target": e["b"],
            "weight": e.get("overlapScore", e.get("edgeScore", 0.5)),
            "overlapScore": e.get("overlapScore", e.get("edgeScore", 0.5)),
            "edgeScore": e.get("edgeScore", e.get("overlapScore", 0.5)),
            "behaviorSimilarity": e.get("behaviorSimilarity", 0),
            "timeSimilarity": e.get("timeSimilarity", 0),
            "tokenSimilarity": e.get("tokenSimilarity", 0),
            "sharedTokens": e.get("sharedTokens", []),
            "sharedSuspects": e.get("sharedSuspects", 0),
            "evidence": e.get("evidence", []),
            "farmId": fid,
            "farmName": e.get("farmName", ""),
            "color": color,
        })

    return {"nodes": nodes, "edges": edges}


@router.get("/api/connections/network/actor/{actor_id}")
async def get_actor_details(actor_id: str):
    db = _db()
    aq = db.audience_quality.find_one({"actorId": actor_id}, {"_id": 0})
    if not aq:
        aq = {"actorId": actor_id, "pctHuman": 50, "pctBot": 0, "pctSuspicious": 0, "aqi": 50, "level": "UNKNOWN"}

    farms = list(db.bot_farms.find(
        {"actorIds": actor_id},
        {"_id": 0, "farmId": 1, "name": 1, "botRatio": 1, "confidence": 1, "riskLevel": 1, "actorIds": 1}
    ))

    connections = list(db.farm_graph_edges.find(
        {"$or": [{"a": actor_id}, {"b": actor_id}]},
        {"_id": 0}
    ))
    connected_to = set()
    for c in connections:
        if c["a"] != actor_id:
            connected_to.add(c["a"])
        if c["b"] != actor_id:
            connected_to.add(c["b"])

    return {
        "ok": True,
        "data": {
            "actorId": actor_id,
            "avatar": f"https://unavatar.io/twitter/{actor_id}",
            "audienceQuality": aq,
            "farms": farms,
            "connections": list(connected_to),
            "totalConnections": len(connected_to),
            "riskLevel": "HIGH" if aq.get("pctBot", 0) > 40 else "MEDIUM" if aq.get("pctBot", 0) > 15 else "LOW",
        }
    }


# ─── PIPELINE TRIGGER ─────────────────────────────────────────

_pipeline_status = {"running": False, "last_run": None, "last_stats": None}


@router.post("/api/connections/network/recompute")
async def recompute_bot_detection(background_tasks: BackgroundTasks,
                                  min_tweets: int = Query(2),
                                  top_n: int = Query(80)):
    """Trigger bot detection pipeline recomputation."""
    if _pipeline_status["running"]:
        return {"ok": False, "error": "Pipeline already running"}

    def _run():
        try:
            _pipeline_status["running"] = True
            from bot_detection_engine import run_and_sync
            stats = run_and_sync(min_tweets=min_tweets, top_n=top_n)
            _pipeline_status["last_stats"] = stats
            _pipeline_status["last_run"] = stats.get("computedAt")
            logger.info(f"Pipeline complete: {stats}")
        except Exception as exc:
            logger.error(f"Pipeline error: {exc}", exc_info=True)
            _pipeline_status["last_stats"] = {"error": str(exc)}
        finally:
            _pipeline_status["running"] = False

    background_tasks.add_task(_run)
    return {"ok": True, "message": "Pipeline started in background"}


@router.get("/api/connections/network/pipeline-status")
async def pipeline_status():
    """Check pipeline status."""
    return {"ok": True, **_pipeline_status}


@router.get("/api/connections/network/compare")
async def compare_actors(a: str = Query(...), b: str = Query(...)):
    """
    Audience Overlap Intelligence: compare ANY two actors.
    On-the-fly analysis for actors not yet in audience_quality.
    """
    db = _db()
    a_lower = a.lower().strip().lstrip('@')
    b_lower = b.lower().strip().lstrip('@')

    if a_lower == b_lower:
        return {"ok": False, "error": "Cannot compare actor with itself"}

    from bot_detection_engine import (
        load_actors, compute_engagement_anomaly, compute_audience_quality,
        compute_behavior_similarity, compute_edge
    )

    # Load ALL actors from twitter_results
    all_actors = load_actors()

    def get_or_compute_aq(handle):
        """Get from DB or compute on-the-fly."""
        aq = db.audience_quality.find_one({"actorId": handle}, {"_id": 0})
        if aq:
            return aq, "analyzed"

        # Check if we have tweets for this actor
        actor = all_actors.get(handle)
        if actor and actor["tweets"]:
            eng = compute_engagement_anomaly(actor)
            aq = compute_audience_quality(actor, eng)
            return aq, "computed"

        # Check twitter_targets for metadata
        target = db.twitter_targets.find_one(
            {"query": {"$regex": f"^{handle}$", "$options": "i"}},
            {"_id": 0}
        )
        if target:
            meta = target.get("metadata", {})
            return {
                "actorId": handle,
                "aqi": 50, "pctBot": 0, "pctHuman": 100, "pctSuspicious": 0,
                "botScore": 0, "level": "UNKNOWN",
                "category": meta.get("category", "unknown"),
                "followers": meta.get("followers", 0),
                "tweetCount": 0,
                "engagement": {"ghostScore": 0, "inflationScore": 0, "zeroEngagementRatio": 0, "avgLikes": 0, "avgViews": 0},
                "breakdown": {},
            }, "metadata_only"

        return None, "not_found"

    aq_a, status_a = get_or_compute_aq(a_lower)
    aq_b, status_b = get_or_compute_aq(b_lower)

    # Handle missing actors
    missing_info = []
    if not aq_a:
        missing_info.append(f"@{a_lower}")
    if not aq_b:
        missing_info.append(f"@{b_lower}")

    if missing_info:
        return {
            "ok": False,
            "error": f"No data found for {', '.join(missing_info)}. These accounts need to be added to the monitoring list first.",
            "suggestion": "Add these accounts to Twitter targets to start collecting their data for analysis.",
            "missingActors": [h.lstrip('@') for h in missing_info],
        }

    # Compute behavior similarity
    actor_a = all_actors.get(a_lower)
    actor_b = all_actors.get(b_lower)

    if actor_a and actor_b:
        behavior = compute_behavior_similarity(actor_a, actor_b)
        edge_data = compute_edge(actor_a, actor_b, aq_a, aq_b)
        edge = edge_data or {
            "edgeScore": 0, "behaviorSimilarity": behavior["behaviorSimilarity"],
            "timeSimilarity": behavior["timeSimilarity"], "tokenSimilarity": behavior["tokenSimilarity"],
            "engPatternSimilarity": behavior["engPatternSimilarity"], "sharedTokens": behavior["sharedTokens"],
            "suspicionWeight": 0,
        }
    else:
        # Metadata-only comparison
        edge = {"edgeScore": 0, "behaviorSimilarity": 0, "timeSimilarity": 0,
                "tokenSimilarity": 0, "engPatternSimilarity": 0, "sharedTokens": [], "suspicionWeight": 0}

    # Compute overlap metrics
    bot_a = aq_a.get("pctBot", 0) / 100
    bot_b = aq_b.get("pctBot", 0) / 100
    behavior_sim = edge.get("behaviorSimilarity", 0)
    time_sim = edge.get("timeSimilarity", 0)
    token_sim = edge.get("tokenSimilarity", 0)
    eng_sim = edge.get("engPatternSimilarity", 0)
    edge_score = edge.get("edgeScore", 0) or edge.get("overlapScore", 0)
    shared_tokens = edge.get("sharedTokens", [])
    suspicion = edge.get("suspicionWeight", 0)

    estimated_overlap = min(1.0, behavior_sim * 0.6 + token_sim * 0.3 + eng_sim * 0.1)
    unique_a = max(0, 1.0 - estimated_overlap)
    unique_b = max(0, 1.0 - estimated_overlap)

    overlap_bot = (bot_a + bot_b) / 2
    overlap_engagement = 1.0 - (aq_a.get("engagement", {}).get("zeroEngagementRatio", 0) + aq_b.get("engagement", {}).get("zeroEngagementRatio", 0)) / 2

    unique_avg = (unique_a + unique_b) / 2
    relationship_score = min(1.0, estimated_overlap * 0.5 + (1 - unique_avg) * 0.3 + overlap_bot * 0.2)

    if estimated_overlap > 0.5 and overlap_bot > 0.3:
        classification = "Bot Amplification Network"
        risk = "HIGH"
    elif estimated_overlap > 0.4:
        classification = "Coordinated Audience"
        risk = "MEDIUM"
    elif estimated_overlap > 0.2:
        classification = "Weak Connection"
        risk = "LOW"
    else:
        classification = "Independent Audiences"
        risk = "NONE"

    interp = []
    # Data quality note
    data_notes = []
    if status_a == "computed":
        data_notes.append(f"@{a_lower} analyzed on-the-fly from {aq_a.get('tweetCount', 0)} tweets")
    if status_b == "computed":
        data_notes.append(f"@{b_lower} analyzed on-the-fly from {aq_b.get('tweetCount', 0)} tweets")
    if status_a == "metadata_only":
        data_notes.append(f"@{a_lower}: limited data (metadata only, no tweets captured yet)")
    if status_b == "metadata_only":
        data_notes.append(f"@{b_lower}: limited data (metadata only, no tweets captured yet)")

    if estimated_overlap > 0.4:
        interp.append(f"Strong behavioral overlap detected ({int(estimated_overlap*100)}%). These accounts behave very similarly.")
    elif estimated_overlap > 0.2:
        interp.append(f"Moderate behavioral overlap ({int(estimated_overlap*100)}%). Some coordinated patterns visible.")
    else:
        interp.append(f"Low overlap ({int(estimated_overlap*100)}%). Audiences appear largely independent.")

    if time_sim > 0.6:
        interp.append(f"Posting times are highly synchronized ({int(time_sim*100)}% overlap). Could indicate shared management.")
    if token_sim > 0.3:
        interp.append(f"Significant token overlap: {', '.join(f'${t}' for t in shared_tokens[:5])}. Coordinated narrative likely.")
    if overlap_bot > 0.25:
        interp.append(f"Combined bot influence is elevated ({int(overlap_bot*100)}%). Shared audience may be partially artificial.")
    if overlap_bot <= 0.15 and not data_notes:
        interp.append("Audience quality is healthy. Connection appears organic.")

    if risk == "HIGH":
        how_to_use = "These accounts likely share or recycle audience. Do NOT trust combined reach. Signals from both carry the same weight as one."
    elif risk == "MEDIUM":
        how_to_use = "Coordinated but possibly real connection. Track both — if they diverge, pay attention."
    elif risk == "LOW":
        how_to_use = "Weak correlation. Independent perspectives. Good for signal diversification."
    else:
        how_to_use = "No meaningful overlap. Independent voices. Their agreement on a token is a stronger signal."

    shared_farm = None
    for farm in db.bot_farms.find({}, {"_id": 0}):
        members = farm.get("actorIds", [])
        if a_lower in members and b_lower in members:
            shared_farm = {"farmId": farm.get("farmId"), "name": farm.get("name"), "riskLevel": farm.get("riskLevel")}
            break

    def actor_summary(aq, status):
        return {
            "id": aq.get("actorId", ""),
            "pctBot": aq.get("pctBot", 0),
            "pctHuman": aq.get("pctHuman", 0),
            "aqi": aq.get("aqi", 0),
            "level": aq.get("level", "UNKNOWN"),
            "category": aq.get("category", "unknown"),
            "followers": aq.get("followers", 0),
            "tweetCount": aq.get("tweetCount", 0),
            "dataStatus": status,
        }

    return {
        "ok": True,
        "actorA": actor_summary(aq_a, status_a),
        "actorB": actor_summary(aq_b, status_b),
        "overlap": {
            "estimated": round(estimated_overlap, 4),
            "uniqueA": round(unique_a, 4),
            "uniqueB": round(unique_b, 4),
            "behaviorSimilarity": round(behavior_sim, 4),
            "timeSimilarity": round(time_sim, 4),
            "tokenSimilarity": round(token_sim, 4),
            "engPatternSimilarity": round(eng_sim, 4),
            "edgeScore": round(edge_score, 4),
            "sharedTokens": shared_tokens,
        },
        "quality": {
            "overlapBotRatio": round(overlap_bot, 4),
            "overlapEngagement": round(overlap_engagement, 4),
            "suspicionWeight": round(suspicion, 4),
            "relationshipScore": round(relationship_score, 4),
        },
        "classification": classification,
        "risk": risk,
        "interpretation": interp,
        "dataNotes": data_notes,
        "howToUse": how_to_use,
        "sharedCluster": shared_farm,
    }


@router.get("/api/connections/network/actors-list")
async def get_actors_list(q: str = Query("", description="Search filter")):
    """Return all actors available for comparison. Optional search filter."""
    db = _db()

    # Already analyzed (high quality)
    analyzed = list(db.audience_quality.find(
        {}, {"_id": 0, "actorId": 1, "aqi": 1, "level": 1, "category": 1, "followers": 1}
    ).sort("aqi", -1))
    analyzed_ids = {a["actorId"] for a in analyzed}

    # All unique tweet authors not yet analyzed (use aggregation for speed)
    pipeline = [
        {"$group": {"_id": {"$toLower": "$username"}, "count": {"$sum": 1}}},
    ]
    author_counts = {doc["_id"]: doc["count"] for doc in db.twitter_results.aggregate(pipeline) if doc["_id"]}

    extra = []
    for author, count in author_counts.items():
        if author not in analyzed_ids and count >= 1:
            extra.append({"actorId": author, "aqi": 0, "level": "UNANALYZED", "category": "unknown", "followers": 0, "tweetCount": count})

    # Twitter targets with metadata but no tweets
    targets = list(db.twitter_targets.find({}, {"_id": 0, "query": 1, "metadata": 1}))
    seen = analyzed_ids | {e["actorId"] for e in extra}
    for t in targets:
        handle = t.get("query", "").lower()
        if handle and handle not in seen:
            meta = t.get("metadata", {})
            extra.append({"actorId": handle, "aqi": 0, "level": "TARGET", "category": meta.get("category", "unknown"), "followers": meta.get("followers", 0), "tweetCount": 0})

    # Sort extras by tweet count
    extra.sort(key=lambda x: -(x.get("tweetCount", 0)))

    all_actors = analyzed + extra

    # Apply search filter if provided
    if q.strip():
        q_lower = q.strip().lower().lstrip('@')
        all_actors = [a for a in all_actors if q_lower in a["actorId"]]

    return {"ok": True, "actors": all_actors, "analyzedCount": len(analyzed), "totalCount": len(analyzed) + len(extra)}


@router.get("/api/connections/network/intelligence")
async def get_network_intelligence():
    """
    Generate actionable intelligence from bot detection data.
    Returns: primary cluster, signals, interpretation, actions.
    """
    db = _db()

    farms = list(db.bot_farms.find({}, {"_id": 0}).sort("clusterBotScore", -1))
    edges = list(db.farm_graph_edges.find({}, {"_id": 0}).sort("edgeScore", -1))
    aq_docs = list(db.audience_quality.find({}, {"_id": 0}))
    aq_map = {d["actorId"]: d for d in aq_docs}

    if not farms:
        return {"ok": True, "primary": None, "signals": [], "clusters": []}

    # Primary cluster = highest bot score
    primary = farms[0]
    primary_members = primary.get("actorIds", primary.get("members", []))

    # Generate signals
    signals = []

    # Signal 1: Coordinated Push
    top_tokens = primary.get("topTokens", [])
    if top_tokens:
        token_str = ", ".join(f"${t['token']}" for t in top_tokens[:3])
        members_str = ", ".join(f"@{m}" for m in primary_members[:4])
        signals.append({
            "type": "COORDINATED_PUSH",
            "severity": "HIGH" if primary.get("density", 0) > 0.7 else "MEDIUM",
            "title": f"Coordinated push detected on {top_tokens[0]['token']}",
            "description": f"{len(primary_members)} actors posting coordinated content around {token_str}",
            "detail": f"Actors: {members_str}",
            "action": "Watch for price spike → monitor for exit liquidity",
            "confidence": primary.get("confidence", 0),
        })

    # Signal 2: Bot Amplification
    high_bot_actors = [m for m in primary_members if aq_map.get(m, {}).get("pctBot", 0) > 20]
    if high_bot_actors:
        signals.append({
            "type": "BOT_AMPLIFICATION",
            "severity": "HIGH" if len(high_bot_actors) > 2 else "MEDIUM",
            "title": f"Bot amplification detected ({len(high_bot_actors)} actors)",
            "description": "High bot probability in cluster audience. Engagement likely artificial.",
            "detail": ", ".join(f"@{a} ({aq_map.get(a, {}).get('pctBot', 0):.0f}% bot)" for a in high_bot_actors[:5]),
            "action": "Do NOT trust engagement metrics from these actors",
            "confidence": min(1.0, sum(aq_map.get(a, {}).get("botScore", 0) for a in high_bot_actors) / max(len(high_bot_actors), 1)),
        })

    # Signal 3: Zero-engagement anomaly
    zero_eng_actors = [m for m in primary_members if aq_map.get(m, {}).get("engagement", {}).get("zeroEngagementRatio", 0) > 0.5]
    if zero_eng_actors:
        signals.append({
            "type": "GHOST_ACCOUNTS",
            "severity": "MEDIUM",
            "title": f"Ghost account activity ({len(zero_eng_actors)} actors)",
            "description": "Accounts with high follower counts but zero real engagement detected in cluster.",
            "detail": ", ".join(f"@{a}" for a in zero_eng_actors[:5]),
            "action": "These actors inflate perceived reach without real audience. Fade their signals.",
            "confidence": 0.7,
        })

    # Signal 4: Exit Risk (if cluster exists but engagement declining)
    avg_bot = primary.get("avgBotScore", 0)
    if avg_bot > 0.15 and primary.get("density", 0) > 0.5:
        signals.append({
            "type": "EXIT_RISK",
            "severity": "MEDIUM",
            "title": "Potential distribution phase",
            "description": "Dense coordinated cluster with elevated bot scores may indicate narrative exhaustion.",
            "action": "If already in position → tighten stops. If watching → wait for confirmation.",
            "confidence": min(1.0, avg_bot * 2),
        })

    # Enrich clusters with interpretation
    enriched_clusters = []
    for farm in farms:
        members = farm.get("actorIds", farm.get("members", []))

        # Interpretation — human-readable
        interp_lines = []
        n_members = len(members)
        density = farm.get("density", 0)
        avg_bot = farm.get("avgBotScore", 0)
        tokens = farm.get("topTokens", [])
        token_names = ", ".join(t["token"] for t in tokens[:3])

        if density > 0.7:
            interp_lines.append(f"{n_members} accounts are tightly interconnected ({int(density*100)}% density). This is NOT typical for independent actors.")
        elif density > 0.3:
            interp_lines.append(f"{n_members} accounts show moderate coordination patterns.")
        else:
            interp_lines.append(f"Loose connection between {n_members} accounts.")

        if avg_bot > 0.3:
            interp_lines.append(f"~{int(avg_bot*100)}% of their combined audience looks suspicious or bot-like. Engagement may be artificially inflated.")
        elif avg_bot > 0.15:
            interp_lines.append(f"~{int(avg_bot*100)}% of audience shows suspicious patterns. Some engagement may be inorganic.")

        if tokens:
            interp_lines.append(f"Coordinated posting around {token_names}. These accounts push similar narratives at overlapping times.")

        if not interp_lines:
            interp_lines.append("Weak correlation detected. Keep on watchlist.")

        # How to use — actionable guidance
        risk = farm.get("riskLevel", "LOW")
        if risk == "HIGH":
            action_text = "HIGH RISK: Likely coordinated manipulation. Do NOT follow these signals blindly. Watch for pump & dump pattern."
            how_to_use = [
                "If you see this cluster pushing a token → treat it as potential manipulation",
                "If price is rising → expect artificial pump, prepare to fade",
                "Do NOT enter positions based solely on these actors' signals"
            ]
        elif risk == "MEDIUM":
            action_text = "ELEVATED: Possible narrative coordination. Verify with on-chain data before acting."
            how_to_use = [
                "Early stage → potential signal, watch for confirmation from independent sources",
                "If cluster grows → stronger narrative forming, may ride with tight stops",
                "If bot score rises → fake engagement increasing, reduce conviction"
            ]
        else:
            action_text = "LOW: Weak correlation. Keep on watchlist for escalation."
            how_to_use = [
                "Monitor for escalation — weak signals can strengthen",
                "Cross-reference with other intelligence before acting"
            ]

        # Metric explanations
        metric_explanations = {
            "botScore": f"~{int(avg_bot*100)}% of their audience looks suspicious or low-quality. Higher = more likely fake engagement.",
            "density": f"{int(density*100)}% of all possible connections exist. 100% = everyone connected to everyone (highly coordinated).",
            "confidence": "How certain the system is about this cluster. Based on cluster size, density, and score consistency.",
        }

        enriched_clusters.append({
            "farmId": farm.get("farmId"),
            "name": farm.get("name"),
            "members": members,
            "memberCount": len(members),
            "clusterBotScore": farm.get("clusterBotScore", 0),
            "avgBotScore": farm.get("avgBotScore", 0),
            "density": density,
            "confidence": farm.get("confidence", 0),
            "riskLevel": risk,
            "topTokens": tokens,
            "evidence": farm.get("evidence", []),
            "interpretation": interp_lines,
            "action": action_text,
            "howToUse": how_to_use,
            "metricExplanations": metric_explanations,
            "confidenceBreakdown": farm.get("confidenceBreakdown", {}),
        })

    return {
        "ok": True,
        "primary": enriched_clusters[0] if enriched_clusters else None,
        "signals": signals,
        "clusters": enriched_clusters,
        "stats": {
            "totalActors": len(aq_docs),
            "totalEdges": len(edges),
            "totalClusters": len(farms),
        },
    }
