"""
Graph Entity Builder — converts raw parser data into unified graph entities.

Takes data from:
  - funding_rounds → invested_in, coinvested_with
  - defi_protocols → deployed_on (protocol → chain)
  - crypto_activities → activity_of (project → activity)  
  - token_unlocks → unlock_of (project → unlock)

Creates entity_graph_nodes + entity_graph_relations.
Then sync_knowledge_edges() in graph_bridge.py pushes to graph_edges.
"""

import logging
from datetime import datetime, timezone
from collections import defaultdict

logger = logging.getLogger(__name__)


async def _upsert_node(db, node_id, node_type, label, source, metadata=None):
    """Upsert entity_graph_node."""
    now = datetime.now(timezone.utc).isoformat()
    update = {
        "$set": {
            "id": node_id,
            "type": node_type,
            "label": label,
            "source": source,
            "updated_at": now,
        },
        "$setOnInsert": {"created_at": now},
    }
    if metadata:
        for k, v in metadata.items():
            update["$set"][f"metadata.{k}"] = v
    await db.entity_graph_nodes.update_one({"id": node_id}, update, upsert=True)


async def _upsert_relation(db, source_id, target_id, relation_type, source, weight=1, metadata=None):
    """Upsert entity_graph_relation."""
    now = datetime.now(timezone.utc).isoformat()
    filt = {
        "source_id": source_id,
        "target_id": target_id,
        "relation_type": relation_type,
    }
    update = {
        "$set": {
            "weight": weight,
            "source": source,
            "metadata": metadata or {},
            "updated_at": now,
        },
        "$setOnInsert": {
            "source_id": source_id,
            "target_id": target_id,
            "relation_type": relation_type,
            "created_at": now,
        },
    }
    await db.entity_graph_relations.update_one(filt, update, upsert=True)


# ─── FUNDING → GRAPH (invested_in, coinvested_with) ───

async def build_funding_graph(db):
    """
    funding_rounds → fund→project (invested_in) + fund↔fund (coinvested_with).
    """
    rounds = await db.funding_rounds.find({}, {"_id": 0}).to_list(5000)
    if not rounds:
        return {"nodes": 0, "relations": 0}

    nodes_created = 0
    relations_created = 0

    project_investors = defaultdict(list)

    for r in rounds:
        project_key = r.get("project_key") or r.get("project_name", "")
        project_name = r.get("project_name", project_key)
        investors = r.get("investors", [])
        raised = r.get("raised_usd", 0)
        round_type = r.get("round_type", "")

        if not project_key or not investors:
            continue

        # Create project node
        proj_id = f"project:{project_key.lower()}"
        await _upsert_node(db, proj_id, "project", project_name, "funding",
                           {"raised_total": raised, "round_type": round_type})
        nodes_created += 1

        for inv in investors:
            inv_lower = inv.lower().replace(" ", "_")
            fund_id = f"fund:{inv_lower}"
            await _upsert_node(db, fund_id, "fund", inv, "funding")
            nodes_created += 1

            # invested_in
            await _upsert_relation(db, fund_id, proj_id, "invested_in", "funding",
                                   metadata={"round_type": round_type, "raised_usd": raised})
            relations_created += 1

            project_investors[project_key].append(inv_lower)

    # Coinvested_with
    for project, investors in project_investors.items():
        for i in range(len(investors)):
            for j in range(i + 1, len(investors)):
                await _upsert_relation(
                    db, f"fund:{investors[i]}", f"fund:{investors[j]}",
                    "coinvested_with", "funding",
                    metadata={"shared_project": project}
                )
                relations_created += 1

    return {"nodes": nodes_created, "relations": relations_created}


# ─── DEFI PROTOCOLS → GRAPH (deployed_on) ───

async def build_defi_graph(db):
    """
    defi_protocols → protocol→chain (deployed_on).
    """
    protocols = await db.defi_protocols.find({}, {"_id": 0}).to_list(1000)
    nodes = 0
    relations = 0

    for p in protocols:
        name = p.get("name", "")
        chains = p.get("chains", [])
        category = p.get("category", "")
        url = p.get("url", "")

        if not name:
            continue

        proto_id = f"protocol:{name.lower().replace(' ', '_')}"
        await _upsert_node(db, proto_id, "protocol", name, "defillama",
                           {"category": category, "url": url})
        nodes += 1

        for chain in chains:
            chain_id = f"chain:{chain.lower().replace(' ', '_')}"
            await _upsert_node(db, chain_id, "chain", chain, "defillama")
            nodes += 1

            await _upsert_relation(db, proto_id, chain_id, "deployed_on", "defillama")
            relations += 1

    return {"nodes": nodes, "relations": relations}


# ─── CRYPTO ACTIVITIES → GRAPH ───

async def build_activities_graph(db):
    """
    crypto_activities → project→activity relations.
    """
    activities = await db.crypto_activities.find({}, {"_id": 0}).to_list(1000)
    nodes = 0
    relations = 0

    for a in activities:
        project_name = a.get("project") or a.get("name", "")
        activity_type = a.get("type") or a.get("category", "")

        if not project_name:
            continue

        proj_id = f"project:{project_name.lower().replace(' ', '_')}"
        act_id = f"activity:{project_name.lower().replace(' ', '_')}:{activity_type.lower()}"

        await _upsert_node(db, proj_id, "project", project_name, "dropstab")
        await _upsert_node(db, act_id, "activity", f"{project_name} {activity_type}", "dropstab",
                           {"activity_type": activity_type})
        nodes += 2

        await _upsert_relation(db, proj_id, act_id, "has_activity", "dropstab",
                               metadata={"type": activity_type})
        relations += 1

    return {"nodes": nodes, "relations": relations}


# ─── TOKEN UNLOCKS → GRAPH ───

async def build_unlocks_graph(db):
    """
    token_unlocks → project→unlock.
    """
    unlocks = await db.token_unlocks.find({}, {"_id": 0}).to_list(500)
    nodes = 0
    relations = 0

    for u in unlocks:
        project = u.get("project") or u.get("name", "")
        if not project:
            continue

        proj_id = f"project:{project.lower().replace(' ', '_')}"
        unlock_id = f"unlock:{project.lower().replace(' ', '_')}"

        await _upsert_node(db, proj_id, "project", project, "tokenunlocks")
        await _upsert_node(db, unlock_id, "unlock_event", f"{project} unlock", "tokenunlocks",
                           metadata={k: v for k, v in u.items() if k in ["date", "amount", "token", "type"]})
        nodes += 2

        await _upsert_relation(db, proj_id, unlock_id, "has_unlock", "tokenunlocks")
        relations += 1

    return {"nodes": nodes, "relations": relations}


# ─── ORCHESTRATOR ───

async def build_all_graph_entities(db):
    """Build graph entities from ALL raw parser data."""
    results = {}

    results["funding"] = await build_funding_graph(db)
    results["defi"] = await build_defi_graph(db)
    results["activities"] = await build_activities_graph(db)
    results["unlocks"] = await build_unlocks_graph(db)

    # Totals
    total_nodes = await db.entity_graph_nodes.count_documents({})
    total_relations = await db.entity_graph_relations.count_documents({})

    return {
        "ok": True,
        "builders": results,
        "total_nodes": total_nodes,
        "total_relations": total_relations,
    }
