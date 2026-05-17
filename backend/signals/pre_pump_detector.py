"""
Pre-Pump Detector
=================
Final detection layer on top of existing intelligence edges.
Catches the moment: signal appeared, pump hasn't started yet.

Conditions for PRE_PUMP (all 4 blocks must pass):
  1. Early attention: entity_pressure growing, 3+ unique actors, mostly EARLY
  2. Quality actors: at least 1 alpha_source OR 2+ high-score actors
  3. Graph flow: attention_flow OR fund-level pressure on project
  4. Price hasn't moved yet: rel_ret_1h < threshold

Hard filters (NO signal if):
  - position == LATE
  - intent == HYPE without alpha actors
  - rel_ret_1h already too high
  - single actor noise (no confirmation)
  - no token_of bridge

Output: {token, signal, score, confidence, why: {pressure, actors, flow, early_ratio}}
Edge type: pre_pump_detected
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger("pre_pump_detector")

# ── Thresholds ──
MIN_UNIQUE_ACTORS = 3
MIN_ALPHA_SOURCES = 1
MIN_HIGH_SCORE_ACTORS = 2
MAX_REL_RET_1H = 2.0  # percent — price hasn't pumped yet
MIN_EARLY_RATIO = 0.4
MIN_PRE_PUMP_SCORE = 35


async def detect_pre_pump(db, token_id: str) -> dict:
    """
    Detect pre-pump signal for a single token.

    Returns:
        {is_pre_pump, token, score, confidence, direction, why, filters}
    """
    # ── 0. Check token_of bridge exists (hard filter) ──
    bridge = await db.graph_edges.find_one(
        {"from_node_id": token_id, "relation_type": "token_of"},
        {"_id": 0, "to_node_id": 1}
    )
    if not bridge:
        return {"is_pre_pump": False, "token": token_id, "reason": "no_token_of_bridge"}

    project_id = bridge["to_node_id"]

    # ── 1. Early Attention (entity_pressure + unique actors) ──
    mention_edges = await db.graph_edges.find(
        {"to_node_id": token_id, "relation_type": "MENTIONED_TOKEN"},
        {"_id": 0, "from_node_id": 1}
    ).to_list(200)

    unique_actors = list(set(e["from_node_id"] for e in mention_edges))
    actor_count = len(unique_actors)

    if actor_count < MIN_UNIQUE_ACTORS:
        return {"is_pre_pump": False, "token": token_id, "reason": f"too_few_actors ({actor_count} < {MIN_UNIQUE_ACTORS})"}

    # Entity pressure
    pressure_state = await db.graph_edge_state.find_one(
        {"to_node_id": token_id, "relation_type": "entity_pressure"},
        {"_id": 0, "weight_current": 1, "weight_total": 1, "count": 1}
    )
    pressure_score = 0.0
    if pressure_state:
        w = pressure_state.get("weight_current", 0)
        pressure_score = min(w / 5.0, 1.0)

    # Early ratio: proportion of EARLY signals from actors
    early_count = 0
    late_count = 0
    hype_only = True

    for actor_id in unique_actors[:20]:
        handle = actor_id.replace("twitter:", "")
        events = await db.actor_signal_events.find(
            {"actor": {"$regex": f"^@?{handle}$", "$options": "i"}},
            {"_id": 0, "position": 1, "intent": 1}
        ).to_list(10)

        for ev in events:
            pos = (ev.get("position") or "").upper()
            intent = (ev.get("intent") or "").upper()
            if pos == "EARLY":
                early_count += 1
            elif pos == "LATE":
                late_count += 1
            if intent != "HYPE":
                hype_only = False

    total_positions = early_count + late_count
    early_ratio = early_count / max(total_positions, 1)

    # Hard filter: mostly LATE
    if total_positions > 0 and early_ratio < 0.3:
        return {"is_pre_pump": False, "token": token_id, "reason": f"mostly_late (early_ratio={early_ratio:.2f})"}

    # Hard filter: HYPE without alpha
    alpha_edges = await db.graph_edges.find(
        {"to_node_id": token_id, "relation_type": "alpha_source"},
        {"_id": 0, "from_node_id": 1}
    ).to_list(10)

    if hype_only and len(alpha_edges) < MIN_ALPHA_SOURCES:
        return {"is_pre_pump": False, "token": token_id, "reason": "hype_without_alpha"}

    # ── 2. Quality Actors ──
    alpha_count = len(alpha_edges)
    alpha_actor_ids = [e["from_node_id"] for e in alpha_edges]

    # Check high-score actors
    high_score_count = 0
    for actor_id in unique_actors[:20]:
        handle = actor_id.replace("twitter:", "")
        actor_profile = await db.actor_scores.find_one(
            {"actor": {"$regex": f"^@?{handle}$", "$options": "i"}},
            {"_id": 0, "score": 1, "hit_rate": 1}
        )
        if actor_profile and actor_profile.get("score", 0) >= 60:
            high_score_count += 1

    has_quality = alpha_count >= MIN_ALPHA_SOURCES or high_score_count >= MIN_HIGH_SCORE_ACTORS
    if not has_quality:
        return {"is_pre_pump": False, "token": token_id, "reason": f"no_quality_actors (alpha={alpha_count}, high_score={high_score_count})"}

    # ── 3. Graph Flow ──
    flow_edges = await db.graph_edges.find(
        {"to_node_id": project_id, "relation_type": "attention_flow"},
        {"_id": 0, "from_node_id": 1}
    ).to_list(50)
    flow_score = min(len(flow_edges) / 5.0, 1.0)

    # Fund-level pressure: check if any fund invested in this project
    fund_edges = await db.graph_edges.find(
        {"to_node_id": project_id, "relation_type": "invested_in"},
        {"_id": 0, "from_node_id": 1}
    ).to_list(20)
    fund_pressure = min(len(fund_edges) / 3.0, 1.0) if fund_edges else 0

    has_flow = flow_score > 0.2 or fund_pressure > 0.2
    if not has_flow:
        return {"is_pre_pump": False, "token": token_id, "reason": "no_graph_flow"}

    # ── 4. Price Check (hasn't pumped yet) ──
    symbol = token_id.replace("token:", "")
    token_data = await db.token_prices.find_one(
        {"symbol": {"$regex": f"^{symbol}$", "$options": "i"}},
        {"_id": 0, "rel_ret_1h": 1, "price_change_1h": 1}
    )
    rel_ret_1h = 0
    if token_data:
        rel_ret_1h = abs(token_data.get("rel_ret_1h", 0) or token_data.get("price_change_1h", 0) or 0)

    if rel_ret_1h > MAX_REL_RET_1H:
        return {"is_pre_pump": False, "token": token_id, "reason": f"price_already_moved (rel_ret_1h={rel_ret_1h:.2f}%)"}

    # ── Compute Pre-Pump Score ──
    actor_score_norm = min((alpha_count * 0.4 + high_score_count * 0.3) / 2, 1.0)
    early_score_norm = min(early_ratio, 1.0)

    pre_pump_score = round((
        pressure_score * 0.35 +
        actor_score_norm * 0.25 +
        max(flow_score, fund_pressure) * 0.20 +
        early_score_norm * 0.20
    ) * 100)

    pre_pump_score = min(pre_pump_score, 100)

    # ── Confidence ──
    confidence = round((
        (1.0 if actor_count >= 5 else actor_count / 5) * 0.3 +
        (1.0 if alpha_count >= 2 else alpha_count / 2) * 0.3 +
        early_ratio * 0.2 +
        (1.0 - min(rel_ret_1h / MAX_REL_RET_1H, 1.0)) * 0.2
    ) * 100)

    is_pre_pump = pre_pump_score >= MIN_PRE_PUMP_SCORE

    return {
        "is_pre_pump": is_pre_pump,
        "token": token_id,
        "project": project_id,
        "signal": "PRE_PUMP" if is_pre_pump else "NO_SIGNAL",
        "score": pre_pump_score,
        "confidence": confidence,
        "direction": "BULLISH",
        "why": {
            "pressure": round(pressure_score, 3),
            "actors": alpha_actor_ids[:5],
            "actor_count": actor_count,
            "alpha_sources": alpha_count,
            "high_score_actors": high_score_count,
            "flow": round(max(flow_score, fund_pressure), 3),
            "flow_type": "fund_pressure" if fund_pressure > flow_score else "attention_flow",
            "funds_invested": len(fund_edges),
            "early_ratio": round(early_ratio, 3),
            "rel_ret_1h": round(rel_ret_1h, 3),
        },
    }


async def run_pre_pump_scan(db, limit: int = 50) -> dict:
    """
    Scan all active tokens for pre-pump signals.
    Writes pre_pump_detected edges + signal_log entries.
    """
    from graph.graph_builder import upsert_edge

    # Find tokens with recent mentions (active tokens)
    pipeline = [
        {"$match": {"relation_type": "MENTIONED_TOKEN"}},
        {"$group": {"_id": "$to_node_id", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gte": 3}}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    active_tokens = await db.graph_edges.aggregate(pipeline).to_list(limit)

    pre_pumps = []
    scanned = 0
    now = datetime.now(timezone.utc)

    for token_doc in active_tokens:
        token_id = token_doc["_id"]
        scanned += 1

        result = await detect_pre_pump(db, token_id)

        if not result.get("is_pre_pump"):
            continue

        project_id = result.get("project")

        # Write pre_pump_detected edge
        if project_id:
            await upsert_edge(
                db, token_id, project_id,
                "pre_pump_detected", "SIGNAL",
                metadata={
                    "score": result["score"],
                    "confidence": result["confidence"],
                    "direction": result["direction"],
                    "why": result["why"],
                    "detected_at": now.isoformat(),
                }
            )

        # Write to signal_log
        await db.signal_log.insert_one({
            "entity": token_id,
            "entity_type": "token",
            "type": "PRE_PUMP",
            "strength": result["score"],
            "confidence": result["confidence"],
            "direction": result["direction"],
            "context": result["why"],
            "source": "pre_pump_detector",
            "timestamp": now.isoformat(),
        })

        pre_pumps.append({
            "token": token_id,
            "project": project_id,
            "score": result["score"],
            "confidence": result["confidence"],
            "why": result["why"],
        })

    logger.info(f"[PrePump] Scan complete: {len(pre_pumps)} pre-pumps from {scanned} tokens")

    return {
        "pre_pumps_detected": len(pre_pumps),
        "tokens_scanned": scanned,
        "pre_pumps": pre_pumps,
    }
