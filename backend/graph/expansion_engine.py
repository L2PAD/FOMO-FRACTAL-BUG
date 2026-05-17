"""
Expansion Engine
================
Controlled graph growth when:
  - new_edges_6h < threshold (graph stalling)
  - actor_gini > 0.6 (concentration too high)

Three expansion modes:
  A. Actor Expansion — find new actors for active tokens
  B. Token Expansion — add tokens frequently mentioned by actors
  C. Missing Link Expansion — create attention_flow where gaps exist

Limits per cycle:
  max_new_actors = 20
  max_new_tokens = 10

NEVER runs unconditionally. Only on trigger.
"""

import logging
import re
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("expansion_engine")

# ── Expansion Limits ──
MAX_NEW_ACTORS_PER_CYCLE = 20
MAX_NEW_TOKENS_PER_CYCLE = 10

# ── Trigger Thresholds ──
NEW_EDGES_6H_THRESHOLD = 10
ACTOR_GINI_THRESHOLD = 0.6


async def should_expand(db) -> dict:
    """
    Check if expansion should trigger.
    Returns {should_expand: bool, reason: str, metrics: dict}
    """
    # Check new_edges_6h
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
    new_edges = await db.graph_edges.count_documents({
        "created_at": {"$gte": cutoff}
    })

    # Check actor_gini from latest health log
    latest_health = await db.graph_health_log.find_one(
        {}, {"_id": 0, "actor_gini": 1},
        sort=[("timestamp", -1)]
    )
    actor_gini = 0.0
    if latest_health:
        actor_gini = latest_health.get("actor_gini", 0)

    low_growth = new_edges < NEW_EDGES_6H_THRESHOLD
    high_gini = actor_gini > ACTOR_GINI_THRESHOLD

    reasons = []
    if low_growth:
        reasons.append(f"low_growth (new_edges_6h={new_edges} < {NEW_EDGES_6H_THRESHOLD})")
    if high_gini:
        reasons.append(f"high_concentration (actor_gini={actor_gini:.4f} > {ACTOR_GINI_THRESHOLD})")

    return {
        "should_expand": low_growth or high_gini,
        "reason": " + ".join(reasons) if reasons else "no trigger",
        "metrics": {
            "new_edges_6h": new_edges,
            "actor_gini": actor_gini,
            "low_growth": low_growth,
            "high_gini": high_gini,
        }
    }


async def expand_actors(db) -> dict:
    """
    A. Actor Expansion
    Find tokens with high mention counts but few unique actors.
    Source new actors from actor_signal_events that aren't yet graph nodes.

    Limit: MAX_NEW_ACTORS_PER_CYCLE
    """
    from graph.graph_builder import upsert_node, upsert_edge

    # Find tokens with mentions
    pipeline = [
        {"$match": {"relation_type": "MENTIONED_TOKEN"}},
        {"$group": {
            "_id": "$to_node_id",
            "actors": {"$addToSet": "$from_node_id"},
            "count": {"$sum": 1}
        }},
        {"$match": {"count": {"$gte": 3}}},
        {"$sort": {"count": -1}},
        {"$limit": 30},
    ]
    active_tokens = await db.graph_edges.aggregate(pipeline).to_list(30)

    # Get existing twitter nodes
    existing_actors = set()
    async for n in db.graph_nodes.find({"type": "twitter_account"}, {"_id": 0, "id": 1}):
        existing_actors.add(n["id"])

    new_actors_added = 0
    new_edges_created = 0

    for token_data in active_tokens:
        if new_actors_added >= MAX_NEW_ACTORS_PER_CYCLE:
            break

        token_id = token_data["_id"]
        # Extract symbol from token_id (e.g., "token:SOL" → "SOL")
        symbol = token_id.replace("token:", "").upper()

        # Search for actors in signal events who mention this token but aren't in the graph
        events = await db.actor_signal_events.find(
            {"tokens": {"$regex": f"^\\$?{re.escape(symbol)}$", "$options": "i"}},
            {"_id": 0, "actor": 1, "timestamp": 1}
        ).to_list(50)

        for ev in events:
            if new_actors_added >= MAX_NEW_ACTORS_PER_CYCLE:
                break

            actor_name = (ev.get("actor") or "").strip().lstrip("@").lower()
            if not actor_name:
                continue

            actor_id = f"twitter:{actor_name}"

            # Skip if already exists
            if actor_id in existing_actors:
                continue

            # Validate: actor must have at least 2 events total (not noise)
            event_count = await db.actor_signal_events.count_documents(
                {"actor": {"$regex": f"^@?{re.escape(actor_name)}$", "$options": "i"}}
            )
            if event_count < 2:
                continue

            # Create actor node
            await upsert_node(
                db, actor_id, "twitter_account", f"@{actor_name}",
                {"source": "expansion_engine", "expanded_at": datetime.now(timezone.utc).isoformat()}
            )
            existing_actors.add(actor_id)
            new_actors_added += 1

            # Create MENTIONED_TOKEN edge
            await upsert_edge(
                db, actor_id, token_id, "MENTIONED_TOKEN", "SIGNAL",
                metadata={"source": "expansion_engine"}
            )
            new_edges_created += 1

    logger.info(f"[Expansion] Actor expansion: {new_actors_added} actors, {new_edges_created} edges")
    return {
        "new_actors": new_actors_added,
        "new_edges": new_edges_created,
    }


async def expand_tokens(db) -> dict:
    """
    B. Token Expansion
    Find tokens frequently mentioned in signal events that don't have graph nodes.

    Limit: MAX_NEW_TOKENS_PER_CYCLE
    """
    from graph.graph_builder import upsert_node, upsert_edge, SYMBOL_TO_PROJECT

    # Get existing token nodes
    existing_tokens = set()
    async for n in db.graph_nodes.find({"type": "token"}, {"_id": 0, "id": 1}):
        existing_tokens.add(n["id"].replace("token:", "").upper())

    # Aggregate most mentioned tokens from signal events
    pipeline = [
        {"$unwind": "$tokens"},
        {"$group": {"_id": {"$toUpper": "$tokens"}, "count": {"$sum": 1}}},
        {"$match": {"count": {"$gte": 3}}},
        {"$sort": {"count": -1}},
        {"$limit": 50},
    ]
    mentioned_tokens = await db.actor_signal_events.aggregate(pipeline).to_list(50)

    new_tokens_added = 0
    new_bridges = 0

    for t in mentioned_tokens:
        if new_tokens_added >= MAX_NEW_TOKENS_PER_CYCLE:
            break

        raw_symbol = (t["_id"] or "").strip().lstrip("$").upper()
        if not raw_symbol or len(raw_symbol) > 10 or not raw_symbol.isalpha():
            continue

        if raw_symbol in existing_tokens:
            continue

        # Create token node
        token_id = f"token:{raw_symbol}"
        await upsert_node(
            db, token_id, "token", raw_symbol,
            {"source": "expansion_engine", "mention_count": t["count"]}
        )
        existing_tokens.add(raw_symbol)
        new_tokens_added += 1

        # Try to create token_of bridge if project exists
        project_id = SYMBOL_TO_PROJECT.get(raw_symbol)
        if project_id:
            exists = await db.graph_nodes.count_documents({"id": project_id})
            if exists:
                await upsert_edge(
                    db, token_id, project_id, "token_of", "BRIDGE",
                    metadata={"source": "expansion_engine"}
                )
                new_bridges += 1

    logger.info(f"[Expansion] Token expansion: {new_tokens_added} tokens, {new_bridges} bridges")
    return {
        "new_tokens": new_tokens_added,
        "new_bridges": new_bridges,
    }


async def expand_missing_links(db) -> dict:
    """
    C. Missing Link Expansion
    Find gaps where:
      - actor → token (MENTIONED_TOKEN)
      - token → project (token_of)
      - fund → project (invested_in)
      BUT no actor → project (attention_flow)

    Creates attention_flow edges to close the loop.
    """
    from graph.graph_builder import upsert_edge

    # Get all token→project bridges
    token_to_project = {}
    async for e in db.graph_edges.find(
        {"relation_type": "token_of"},
        {"_id": 0, "from_node_id": 1, "to_node_id": 1}
    ):
        token_to_project[e["from_node_id"]] = e["to_node_id"]

    # Get existing attention_flow edges
    existing_flows = set()
    async for e in db.graph_edges.find(
        {"relation_type": "attention_flow"},
        {"_id": 0, "from_node_id": 1, "to_node_id": 1}
    ):
        existing_flows.add((e["from_node_id"], e["to_node_id"]))

    # Find actor→token mentions
    new_flows = 0

    pipeline = [
        {"$match": {"relation_type": "MENTIONED_TOKEN"}},
        {"$group": {
            "_id": {"actor": "$from_node_id", "token": "$to_node_id"},
            "count": {"$sum": 1}
        }},
        {"$match": {"count": {"$gte": 2}}},
        {"$limit": 200},
    ]
    mention_pairs = await db.graph_edges.aggregate(pipeline).to_list(200)

    for pair in mention_pairs:
        actor_id = pair["_id"]["actor"]
        token_id = pair["_id"]["token"]

        project_id = token_to_project.get(token_id)
        if not project_id:
            continue

        # Check if attention_flow already exists
        if (actor_id, project_id) in existing_flows:
            continue

        # Create attention_flow: actor → project
        await upsert_edge(
            db, actor_id, project_id, "attention_flow", "SIGNAL",
            metadata={
                "source": "expansion_engine",
                "via_token": token_id,
                "mention_count": pair["count"],
            }
        )
        existing_flows.add((actor_id, project_id))
        new_flows += 1

    logger.info(f"[Expansion] Missing links: {new_flows} attention_flow edges created")
    return {"new_attention_flows": new_flows}


async def run_expansion(db) -> dict:
    """
    Full expansion cycle. Only runs if triggers are met.

    Pipeline:
      1. Check triggers
      2. Actor expansion (max 20)
      3. Token expansion (max 10)
      4. Missing link expansion
    """
    import time
    start = time.time()

    trigger = await should_expand(db)

    if not trigger["should_expand"]:
        logger.info(f"[Expansion] No trigger: {trigger['reason']}")
        return {
            "expanded": False,
            "reason": trigger["reason"],
            "metrics": trigger["metrics"],
        }

    logger.info(f"[Expansion] === EXPANSION TRIGGERED: {trigger['reason']} ===")

    actors_result = await expand_actors(db)
    tokens_result = await expand_tokens(db)
    links_result = await expand_missing_links(db)

    duration = round(time.time() - start, 2)

    result = {
        "expanded": True,
        "reason": trigger["reason"],
        "metrics": trigger["metrics"],
        "actors": actors_result,
        "tokens": tokens_result,
        "links": links_result,
        "duration_sec": duration,
    }

    # Log expansion event
    await db.expansion_log.insert_one({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **result,
    })

    logger.info(
        f"[Expansion] Complete in {duration}s: "
        f"actors={actors_result['new_actors']}, "
        f"tokens={tokens_result['new_tokens']}, "
        f"flows={links_result['new_attention_flows']}"
    )

    return result
