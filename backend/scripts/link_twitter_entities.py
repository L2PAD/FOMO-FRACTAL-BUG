"""
Twitter → Entity Graph Linking (with Confidence Scores)
========================================================

Links twitter_account nodes to person and project nodes in entity_graph_relations.
Uses multi-signal confidence scoring:
  - Name similarity (fuzzy match)
  - Known alias whitelist
  - Category alignment
  - Indirect bridging (twitter → person → project)

Only creates edges with matchConfidence > 0.8

Source trace: all edges get source='twitter_linker'
"""

import asyncio
import os
import sys
import logging
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher

from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("TwitterLinker")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")

CONFIDENCE_THRESHOLD = 0.8

# Known twitter handle → person ID whitelist (manually verified against DB)
TWITTER_PERSON_WHITELIST = {
    "twitter:vitalikbuterin": "person:vitalik",
    "twitter:cz_binance": "person:cz",
    "twitter:brian_armstrong": "person:brian-armstrong",
    "twitter:aaboronkov": "person:anatoly-yakovenko",
    "twitter:gavofyork": "person:gavin-wood",
    "twitter:haaborydams": "person:hayden-adams",
    "twitter:staborni": "person:stani-kulechov",
    "twitter:cdixon": "person:chris-dixon",
    "twitter:fehrsam": "person:fred-ehrsam",
    "twitter:matthuang": "person:matt-huang",
}

# Known twitter handle → project ID whitelist (protocol official accounts, verified against DB)
TWITTER_PROJECT_WHITELIST = {
    "twitter:uniswap": "project:uniswap",
    "twitter:aaveaave": "project:aave",
    "twitter:curvefinance": "project:curve-dex",
    "twitter:lidofinance": "project:lido",
    "twitter:eigenlayer": "project:eigenlayer",
    "twitter:pendlefinance": "project:pendle",
    "twitter:synthetixio": "project:synthetix",
    "twitter:daborydaborx": "project:dydx",
    "twitter:optimaborismfnd": "project:optimism",
    "twitter:arbitrum": "project:arbitrum",
    "twitter:0xpolygon": "project:polygon",
    "twitter:avaborax": "project:avalanche",
    "twitter:sui_network": "project:sui",
    "twitter:aptos": "project:aptos",
    "twitter:zaborksync": "project:zksync",
    "twitter:celestia": "project:celestia",
    "twitter:moabornad_xyz": "project:monad",
    "twitter:beaborrachain": "project:berachain",
    "twitter:sei_network": "project:sei",
    "twitter:injective": "project:injective",
    "twitter:scrollaborz_io": "project:scroll",
    "twitter:blaborast": "project:blast",
    "twitter:coinaborbase": "project:coinbase",
    "twitter:kaborraken": "project:kraken",
    "twitter:okx": "project:okx",
    "twitter:bybit_official": "project:bybit",
    "twitter:makerdao": "project:maker",
    "twitter:binance": "project:binance-cex",
}


def normalize_name(name):
    """Normalize a name for comparison"""
    if not name:
        return ""
    name = name.lower().strip()
    name = re.sub(r'[^a-z0-9\s]', '', name)
    name = re.sub(r'\s+', ' ', name)
    return name


def name_similarity(name1, name2):
    """Calculate similarity between two names (0-1)"""
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)
    if not n1 or not n2:
        return 0.0
    if n1 == n2:
        return 1.0
    # Check if one contains the other
    if n1 in n2 or n2 in n1:
        return 0.9
    return SequenceMatcher(None, n1, n2).ratio()


def compute_twitter_person_confidence(twitter_node, person_node, whitelist_match=False):
    """
    Compute confidence score for twitter → person link.

    Signals:
      +0.5  exact display_name match
      +0.3  whitelist match
      +0.2  high fuzzy similarity (>0.85)
      +0.1  category alignment (founder→person with founder role)
    """
    tw_meta = twitter_node.get("metadata", {})
    tw_display = tw_meta.get("display_name", "")
    person_label = person_node.get("label", "")

    confidence = 0.0
    signals = []

    # Signal 1: Name similarity
    sim = name_similarity(tw_display, person_label)
    if sim >= 0.95:
        confidence += 0.5
        signals.append(f"exact_name_match({sim:.2f})")
    elif sim >= 0.85:
        confidence += 0.35
        signals.append(f"high_name_sim({sim:.2f})")
    elif sim >= 0.7:
        confidence += 0.2
        signals.append(f"partial_name_sim({sim:.2f})")

    # Signal 2: Whitelist
    if whitelist_match:
        confidence += 0.3
        signals.append("whitelist")

    # Signal 3: Category alignment
    tw_cat = tw_meta.get("category", "")
    p_role = person_node.get("metadata", {}).get("primary_role", "").lower()
    if tw_cat == "founder" and ("founder" in p_role or "co-founder" in p_role or "ceo" in p_role):
        confidence += 0.1
        signals.append("role_align")
    elif tw_cat == "vc" and "partner" in p_role:
        confidence += 0.1
        signals.append("role_align_vc")

    # Signal 4: Tier boost (tier 1 accounts are more likely correctly mapped)
    if tw_meta.get("tier") == 1:
        confidence += 0.05
        signals.append("tier1")

    return min(confidence, 1.0), signals


def compute_twitter_project_confidence(twitter_node, project_node, whitelist_match=False, via_person=False):
    """
    Compute confidence score for twitter → project link.

    Signals:
      +0.85 whitelist match (manually verified official account)
      +0.2  protocol category + name match
    """
    tw_meta = twitter_node.get("metadata", {})
    confidence = 0.0
    signals = []

    if whitelist_match:
        confidence += 0.85
        signals.append("whitelist_verified")

    # Name match for protocol accounts
    tw_cat = tw_meta.get("category", "")
    if tw_cat in ("protocol", "exchange"):
        tw_display = normalize_name(tw_meta.get("display_name", ""))
        proj_label = normalize_name(project_node.get("label", ""))
        sim = name_similarity(tw_display, proj_label)
        if sim >= 0.8:
            confidence += 0.1
            signals.append(f"name_match({sim:.2f})")

    if tw_meta.get("tier") == 1:
        confidence += 0.05
        signals.append("tier1")

    return min(confidence, 1.0), signals


async def link_twitter_to_entities(db):
    """Main linking function"""
    logger.info("=" * 60)
    logger.info("TWITTER → ENTITY LINKING — START")
    logger.info("=" * 60)

    # Load all data
    twitters = {t['id']: t for t in await db.entity_graph_nodes.find(
        {"type": "twitter_account"}, {"_id": 0}
    ).to_list(500)}

    persons = {p['id']: p for p in await db.entity_graph_nodes.find(
        {"type": "person"}, {"_id": 0}
    ).to_list(500)}

    projects = {p['id']: p for p in await db.entity_graph_nodes.find(
        {"type": "project"}, {"_id": 0}
    ).to_list(500)}

    # Build person → project map from existing edges
    person_to_projects = {}
    async for edge in db.entity_graph_relations.find(
        {"relation_type": {"$in": ["founded", "works_at", "co-founded", "leads", "invested_in"]}},
        {"_id": 0}
    ):
        sid = edge['source_id']
        tid = edge['target_id']
        if sid.startswith("person:"):
            if sid not in person_to_projects:
                person_to_projects[sid] = []
            person_to_projects[sid].append(tid)

    logger.info(f"Loaded: {len(twitters)} twitter, {len(persons)} persons, {len(projects)} projects")
    logger.info(f"Person→Project bridges: {len(person_to_projects)}")

    now = datetime.now(timezone.utc)
    edges_created = 0
    edges_rejected = 0
    edges_by_type = {"twitter_person": 0, "twitter_project_direct": 0, "twitter_project_bridge": 0}

    # === PHASE 1: Twitter → Person ===
    logger.info("\n--- PHASE 1: Twitter → Person ---")

    for tw_id, tw_node in twitters.items():
        best_match = None
        best_confidence = 0
        best_signals = []
        is_whitelist = False

        # Check whitelist first
        if tw_id in TWITTER_PERSON_WHITELIST:
            wl_person_id = TWITTER_PERSON_WHITELIST[tw_id]
            if wl_person_id in persons:
                conf, sigs = compute_twitter_person_confidence(tw_node, persons[wl_person_id], whitelist_match=True)
                if conf > best_confidence:
                    best_match = wl_person_id
                    best_confidence = conf
                    best_signals = sigs
                    is_whitelist = True

        # Fuzzy match against all persons
        tw_display = tw_node.get("metadata", {}).get("display_name", "")
        if tw_display and not is_whitelist:
            for p_id, p_node in persons.items():
                conf, sigs = compute_twitter_person_confidence(tw_node, p_node)
                if conf > best_confidence:
                    best_match = p_id
                    best_confidence = conf
                    best_signals = sigs

        if best_match and best_confidence >= CONFIDENCE_THRESHOLD:
            edge = {
                "source_id": tw_id,
                "target_id": best_match,
                "relation_type": "account_of",
                "direction": "outgoing",
                "weight": round(best_confidence, 3),
                "first_seen": now,
                "last_seen": now,
                "metadata": {
                    "confidence": round(best_confidence, 3),
                    "signals": best_signals,
                    "linked_at": now.isoformat(),
                },
                "tags": ["twitter_link", "auto_linked"],
                "graph_version": "v2_entity",
                "source": "twitter_linker",
            }
            await db.entity_graph_relations.update_one(
                {"source_id": tw_id, "target_id": best_match, "relation_type": "account_of"},
                {"$set": edge},
                upsert=True,
            )
            edges_created += 1
            edges_by_type["twitter_person"] += 1
            logger.info(f"  LINKED {tw_id} → {best_match} (conf={best_confidence:.2f}, signals={best_signals})")
        elif best_match:
            edges_rejected += 1
            logger.debug(f"  REJECTED {tw_id} → {best_match} (conf={best_confidence:.2f} < {CONFIDENCE_THRESHOLD})")

    # === PHASE 2: Twitter → Project (direct whitelist) ===
    logger.info("\n--- PHASE 2: Twitter → Project (direct) ---")

    for tw_id, proj_id in TWITTER_PROJECT_WHITELIST.items():
        if tw_id not in twitters or proj_id not in projects:
            continue
        tw_node = twitters[tw_id]
        proj_node = projects[proj_id]
        conf, sigs = compute_twitter_project_confidence(tw_node, proj_node, whitelist_match=True)

        if conf >= CONFIDENCE_THRESHOLD:
            edge = {
                "source_id": tw_id,
                "target_id": proj_id,
                "relation_type": "official_account_of",
                "direction": "outgoing",
                "weight": round(conf, 3),
                "first_seen": now,
                "last_seen": now,
                "metadata": {
                    "confidence": round(conf, 3),
                    "signals": sigs,
                    "linked_at": now.isoformat(),
                },
                "tags": ["twitter_link", "official", "auto_linked"],
                "graph_version": "v2_entity",
                "source": "twitter_linker",
            }
            await db.entity_graph_relations.update_one(
                {"source_id": tw_id, "target_id": proj_id, "relation_type": "official_account_of"},
                {"$set": edge},
                upsert=True,
            )
            edges_created += 1
            edges_by_type["twitter_project_direct"] += 1
            logger.info(f"  LINKED {tw_id} → {proj_id} (conf={conf:.2f}, signals={sigs})")

    # === PHASE 3: Twitter → Project (via person bridge) ===
    logger.info("\n--- PHASE 3: Twitter → Project (via person bridge) ---")

    # Find all twitter→person edges we just created
    tw_person_edges = await db.entity_graph_relations.find(
        {"relation_type": "account_of", "source": "twitter_linker"},
        {"_id": 0, "source_id": 1, "target_id": 1, "weight": 1}
    ).to_list(500)

    for tw_edge in tw_person_edges:
        tw_id = tw_edge["source_id"]
        person_id = tw_edge["target_id"]
        tw_person_conf = tw_edge.get("weight", 0.5)

        # Check if this person has project links
        if person_id in person_to_projects:
            for proj_id in person_to_projects[person_id]:
                if proj_id not in projects:
                    continue
                tw_node = twitters.get(tw_id)
                proj_node = projects.get(proj_id)
                if not tw_node or not proj_node:
                    continue

                # Bridge confidence: since person→project is established truth,
                # the bridge confidence is based on twitter→person confidence
                # with a 0.9 discount for the indirect link
                conf = tw_person_conf * 0.9
                sigs = [f"via_person_bridge", f"person_bridge:{person_id}", f"tw_person_conf:{tw_person_conf:.2f}"]

                if tw_node.get("metadata", {}).get("tier") == 1:
                    conf = min(conf + 0.05, 1.0)
                    sigs.append("tier1")

                if conf >= CONFIDENCE_THRESHOLD:
                    edge = {
                        "source_id": tw_id,
                        "target_id": proj_id,
                        "relation_type": "associated_with",
                        "direction": "outgoing",
                        "weight": round(conf, 3),
                        "first_seen": now,
                        "last_seen": now,
                        "metadata": {
                            "confidence": round(conf, 3),
                            "signals": sigs,
                            "bridge_person": person_id,
                            "linked_at": now.isoformat(),
                        },
                        "tags": ["twitter_link", "bridge", "auto_linked"],
                        "graph_version": "v2_entity",
                        "source": "twitter_linker",
                    }
                    await db.entity_graph_relations.update_one(
                        {"source_id": tw_id, "target_id": proj_id, "relation_type": "associated_with", "source": "twitter_linker"},
                        {"$set": edge},
                        upsert=True,
                    )
                    edges_created += 1
                    edges_by_type["twitter_project_bridge"] += 1
                    logger.info(f"  BRIDGE {tw_id} → {person_id} → {proj_id} (conf={conf:.2f})")

    # === SUMMARY ===
    total_tw_edges = await db.entity_graph_relations.count_documents({"source": "twitter_linker"})

    logger.info("\n" + "=" * 60)
    logger.info("TWITTER → ENTITY LINKING — RESULTS")
    logger.info("=" * 60)
    logger.info(f"  Edges created/updated: {edges_created}")
    logger.info(f"  Edges rejected (low confidence): {edges_rejected}")
    logger.info(f"  Breakdown:")
    for k, v in edges_by_type.items():
        logger.info(f"    {k}: {v}")
    logger.info(f"  Total twitter_linker edges in DB: {total_tw_edges}")
    logger.info("=" * 60)

    return {
        "edges_created": edges_created,
        "edges_rejected": edges_rejected,
        "by_type": edges_by_type,
        "total_in_db": total_tw_edges,
    }


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    try:
        result = await link_twitter_to_entities(db)
        return result
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
