"""
Unified Graph Builder — single source of truth for graph population.

Takes raw data from:
  - cryptorank_projects (symbol, name, category)
  - defi_protocols (name, chains, symbol, twitter)
  - funding_rounds (project, investors)
  - actor_signal_events (twitter mentions)
  - entity_graph_relations (pre-built knowledge)

Outputs ONLY to graph_nodes + graph_edges via:
  - upsert_node() — idempotent node creation
  - upsert_edge() — idempotent edge by (from, to, type, layer) key

Entity Resolution:
  - resolve_entity() — normalize names, map twitter→person, token→project
  - Token symbol → project via cryptorank/defi lookup
  - Twitter handle → person via known mapping table

Layers:
  KNOWLEDGE — structural (fund→project, person→project, deployed_on)
  SIGNAL    — dynamic (mention, correlation, alpha)

Two modes:
  1. run_full_build() — background cron (every 6h)
  2. hydrate_entity() — on-demand (user search)
"""

import logging
import math
import re
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)


# ============================================================
# ENTITY RESOLUTION
# ============================================================

def _normalize(name: str) -> str:
    """Lowercase, strip @, _, -, spaces, dots."""
    if not name:
        return ""
    return re.sub(r"[\s_\-\.@]+", "", name.lower().strip())


# Known twitter handle → person ID mapping (top crypto figures)
# Format: twitter_handle → person_id (as in graph_nodes)
TWITTER_TO_PERSON = {
    "vitalikbuterin": "person:vitalik",
    "brian_armstrong": "person:brian-armstrong",
    "cz_binance": "person:changpeng-zhao",
    "gavofyork": "person:gavin-wood",
    "staborni": "person:stani-kulechov",
    "cdixon": "person:chris-dixon",
    "fehrsam": "person:fred-ehrsam",
    "matthuang": "person:matt-huang",
    "aaboronkov": "person:anatoly-yakovenko",
    "haaborydams": "person:hayden-adams",
    "sbf_ftx": "person:sam-bankman-fried",
    "hosaborsedan": "person:charles-hoskinson",
    "rajgokal": "person:raj-gokal",
    "sataborjoshi": "person:sandeep-nailwal",
    "balaborjisingh": "person:balaji-srinivasan",
    "rleshner": "person:robert-leshner",
    "hasufl": "person:hasu",
    "zabordanprice": "person:jordan-price",
    "saborberramsey": "person:saber-ramsey",
}

# Known token symbol → project key mapping
# Built dynamically at runtime from DB, but seed with top tokens
SYMBOL_TO_PROJECT = {
    "BTC": "project:bitcoin",
    "ETH": "project:ethereum",
    "SOL": "project:solana",
    "BNB": "project:binance",
    "ADA": "project:cardano",
    "DOT": "project:polkadot",
    "AVAX": "project:avalanche",
    "LINK": "project:chainlink",
    "UNI": "project:uniswap",
    "AAVE": "project:aave",
    "ARB": "project:arbitrum",
    "OP": "project:optimism",
    "SUI": "project:sui",
    "APT": "project:aptos",
    "NEAR": "project:near",
    "ATOM": "project:cosmos",
    "MATIC": "project:polygon",
    "POL": "project:polygon",
    "DOGE": "project:dogecoin",
    "PEPE": "project:pepe",
    "INJ": "project:injective",
    "TIA": "project:celestia",
    "SEI": "project:sei",
    "STRK": "project:starknet",
    "EIGEN": "project:eigenlayer",
    "PENDLE": "project:pendle",
    "ONDO": "project:ondo",
    "MKR": "project:maker",
    "CRV": "project:curve-dex",
    "SNX": "project:synthetix",
    "COMP": "project:compound",
    "FET": "project:fetch-ai",
    "TAO": "project:bittensor",
    "RENDER": "project:render",
    "XRP": "project:ripple",
    "LTC": "project:litecoin",
    "TRX": "project:tron",
    "DYDX": "project:dydx",
    "FIL": "project:filecoin",
    "GRT": "project:the-graph",
    "IMX": "project:immutable",
    "LDO": "project:lido",
    "RPL": "project:rocketpool",
    "SSV": "project:ssv-network",
    "STX": "project:stacks",
    "AR": "project:arweave",
    "BICO": "project:biconomy",
    "MANTA": "project:manta-network",
    "FTM": "project:fantom",
    "DYM": "project:dymension",
    "PORTAL": "project:portal",
    "SAGA": "project:saga",
    "PIXEL": "project:pixels",
    "POP": "project:pop",
    "BEAN": "project:beanstalk",
    "MUSD": "project:musd",
}

# Project twitter handle → project key mapping
PROJECT_TWITTER = {
    "uniswap": "project:uniswap",
    "aaboraveaave": "project:aave",
    "curvefinance": "project:curve-dex",
    "lidofinance": "project:lido",
    "eigenlayer": "project:eigenlayer",
    "pendlefinance": "project:pendle",
    "synthetixio": "project:synthetix",
    "daborydaborx": "project:dydx",
    "optimaborismfnd": "project:optimism",
    "arbitrum": "project:arbitrum",
    "solana": "project:solana",
    "ethereum": "project:ethereum",
}


async def build_symbol_lookup(db) -> dict:
    """Build token symbol → project key lookup from DB data."""
    lookup = dict(SYMBOL_TO_PROJECT)

    # From cryptorank_projects
    async for doc in db.cryptorank_projects.find(
        {"symbol": {"$exists": True, "$ne": ""}},
        {"_id": 0, "symbol": 1, "name": 1}
    ):
        sym = doc["symbol"].upper()
        name = doc.get("name", "")
        if sym and name and sym not in lookup:
            key = f"project:{name.lower().replace(' ', '-').replace('_', '-')}"
            lookup[sym] = key

    # From defi_protocols
    async for doc in db.defi_protocols.find(
        {"symbol": {"$exists": True, "$ne": ""}},
        {"_id": 0, "symbol": 1, "name": 1}
    ):
        sym = doc["symbol"].upper()
        name = doc.get("name", "")
        if sym and name and sym not in lookup:
            key = f"protocol:{name.lower().replace(' ', '_')}"
            lookup[sym] = key

    logger.info(f"[GraphBuilder] Symbol lookup: {len(lookup)} symbols")
    return lookup


async def build_twitter_person_lookup(db) -> dict:
    """Build twitter handle → person ID lookup from DB data."""
    lookup = dict(TWITTER_TO_PERSON)

    # From entity_graph_relations (account_of)
    async for doc in db.entity_graph_relations.find(
        {"relation_type": "account_of"},
        {"_id": 0, "source_id": 1, "target_id": 1}
    ):
        src = doc.get("source_id", "")
        tgt = doc.get("target_id", "")
        if src.startswith("twitter:") and tgt.startswith("person:"):
            handle = src.replace("twitter:", "")
            lookup[handle] = tgt

    logger.info(f"[GraphBuilder] Twitter→Person lookup: {len(lookup)} mappings")
    return lookup


def resolve_entity(name: str, entity_type: str, symbol_lookup: dict = None, twitter_lookup: dict = None) -> str:
    """
    Resolve a raw name into a canonical graph node ID.

    Args:
        name: raw name (e.g., "vitalikbuterin", "ETH", "Solana")
        entity_type: hint ("twitter", "token", "project", "fund", "person")
        symbol_lookup: token→project mapping
        twitter_lookup: twitter→person mapping

    Returns:
        Canonical node ID (e.g., "person:vitalik", "project:ethereum")
    """
    if not name:
        return ""

    clean = name.strip()

    if entity_type == "twitter":
        handle = clean.lower().lstrip("@")
        if twitter_lookup and handle in twitter_lookup:
            return twitter_lookup[handle]
        return f"twitter:{handle}"

    if entity_type == "token":
        sym = clean.upper().lstrip("$")
        if symbol_lookup and sym in symbol_lookup:
            return symbol_lookup[sym]
        return f"token:{sym}"

    if entity_type == "project":
        slug = clean.lower().replace(" ", "-").replace("_", "-")
        return f"project:{slug}"

    if entity_type == "fund":
        slug = clean.lower().replace(" ", "_")
        return f"fund:{slug}"

    if entity_type == "person":
        slug = clean.lower().replace(" ", "-").replace("_", "-")
        return f"person:{slug}"

    if entity_type == "chain":
        slug = clean.lower().replace(" ", "_")
        return f"chain:{slug}"

    if entity_type == "protocol":
        slug = clean.lower().replace(" ", "_")
        return f"protocol:{slug}"

    return f"{entity_type}:{_normalize(clean)}"


# ============================================================
# UPSERT PRIMITIVES
# ============================================================

async def upsert_node(db, node_id: str, node_type: str, label: str, metadata: dict = None):
    """Upsert into graph_nodes. Merges metadata, never overwrites label if exists."""
    now = datetime.now(timezone.utc)
    update = {
        "$set": {
            "id": node_id,
            "type": node_type,
            "updated_at": now,
        },
        "$setOnInsert": {
            "label": label,
            "created_at": now,
        },
    }
    if metadata:
        for k, v in metadata.items():
            if v is not None:
                update["$set"][f"metadata.{k}"] = v
    await db.graph_nodes.update_one({"id": node_id}, update, upsert=True)


async def upsert_edge(db, from_id: str, to_id: str, relation_type: str,
                      layer: str, weight: float = 1.0, metadata: dict = None):
    """
    Upsert into graph_edges. Key = (from, to, relation_type, layer).
    No duplicates. Updates weight + metadata on conflict.
    """
    now = datetime.now(timezone.utc)
    filt = {
        "from_node_id": from_id,
        "to_node_id": to_id,
        "relation_type": relation_type,
        "layer": layer,
    }
    update = {
        "$set": {
            "weight": weight,
            "updated_at": now,
            **({"metadata": metadata} if metadata else {}),
        },
        "$setOnInsert": {
            "from_node_id": from_id,
            "to_node_id": to_id,
            "relation_type": relation_type,
            "layer": layer,
            "created_at": now,
        },
    }
    await db.graph_edges.update_one(filt, update, upsert=True)


# ============================================================
# KNOWLEDGE LAYER BUILDERS
# ============================================================

async def build_funding_edges(db):
    """funding_rounds → fund→project (invested_in) + fund↔fund (coinvested_with)."""
    rounds = await db.funding_rounds.find({}, {"_id": 0}).to_list(5000)
    if not rounds:
        return {"edges": 0, "nodes": 0}

    edges = 0
    nodes = 0
    project_investors = defaultdict(list)

    for r in rounds:
        project_key = r.get("project_key") or r.get("project_name", "")
        project_name = r.get("project_name", project_key)
        investors = r.get("investors", [])
        raised = r.get("raised_usd", 0)
        round_type = r.get("round_type", "")

        if not project_key or not investors:
            continue

        proj_id = f"project:{project_key.lower()}"
        await upsert_node(db, proj_id, "project", project_name,
                          {"raised_total": raised, "round_type": round_type, "source": "funding"})
        nodes += 1

        for inv in investors:
            inv_slug = inv.lower().replace(" ", "_")
            fund_id = f"fund:{inv_slug}"
            await upsert_node(db, fund_id, "fund", inv, {"source": "funding"})
            nodes += 1

            await upsert_edge(db, fund_id, proj_id, "invested_in", "KNOWLEDGE",
                              weight=1.0,
                              metadata={"round_type": round_type, "raised_usd": raised})
            edges += 1
            project_investors[project_key].append(inv_slug)

    # Coinvested_with
    for project, investors in project_investors.items():
        for i in range(len(investors)):
            for j in range(i + 1, len(investors)):
                await upsert_edge(
                    db, f"fund:{investors[i]}", f"fund:{investors[j]}",
                    "coinvested_with", "KNOWLEDGE",
                    metadata={"shared_project": project}
                )
                edges += 1

    return {"edges": edges, "nodes": nodes}


async def build_defi_edges(db):
    """defi_protocols → protocol→chain (deployed_on)."""
    protocols = await db.defi_protocols.find({}, {"_id": 0}).to_list(2000)
    edges = 0
    nodes = 0

    for p in protocols:
        name = p.get("name", "")
        chains = p.get("chains", [])
        category = p.get("category", "")
        symbol = p.get("symbol", "")
        twitter = p.get("twitter", "")

        if not name:
            continue

        proto_id = f"protocol:{name.lower().replace(' ', '_')}"
        await upsert_node(db, proto_id, "protocol", name,
                          {"category": category, "symbol": symbol, "source": "defillama"})
        nodes += 1

        for chain in chains:
            chain_id = f"chain:{chain.lower().replace(' ', '_')}"
            await upsert_node(db, chain_id, "chain", chain)
            nodes += 1

            await upsert_edge(db, proto_id, chain_id, "deployed_on", "KNOWLEDGE")
            edges += 1

        # Link protocol twitter account if present
        if twitter:
            handle = twitter.lower().lstrip("@").split("/")[-1]
            if handle:
                tw_id = f"twitter:{handle}"
                await upsert_node(db, tw_id, "twitter_account", f"@{handle}")
                await upsert_edge(db, tw_id, proto_id, "official_account_of", "KNOWLEDGE")
                edges += 1

    return {"edges": edges, "nodes": nodes}


async def build_people_edges(db):
    """
    Sync person→project (founded, works_at) and twitter→person (account_of)
    from entity_graph_relations into graph_edges.
    """
    rels = await db.entity_graph_relations.find({}, {"_id": 0}).to_list(5000)
    synced = 0

    for r in rels:
        from_id = r.get("source_id", "")
        to_id = r.get("target_id", "")
        rel_type = r.get("relation_type", "")
        weight = r.get("weight", 1)

        if not from_id or not to_id or not rel_type:
            continue

        await upsert_edge(db, from_id, to_id, rel_type, "KNOWLEDGE",
                          weight=weight, metadata=r.get("metadata"))
        synced += 1

    # Also sync entity_graph_nodes into graph_nodes
    enodes = await db.entity_graph_nodes.find({}, {"_id": 0}).to_list(2000)
    nodes_synced = 0
    for n in enodes:
        nid = n.get("id", "")
        ntype = n.get("type", "")
        label = n.get("label", "")
        if nid and ntype:
            meta = {}
            if n.get("source"):
                meta["source"] = n["source"]
            await upsert_node(db, nid, ntype, label, meta if meta else None)
            nodes_synced += 1

    return {"edges_synced": synced, "nodes_synced": nodes_synced}


async def build_github_edges(db):
    """
    intel_github → developer→project (contributes_to) edges.
    Also links developer twitter accounts if available.
    """
    repos = await db.intel_github.find(
        {"contributors.0": {"$exists": True}},
        {"_id": 0, "project": 1, "project_key": 1, "contributors": 1,
         "metrics": 1, "developer_activity": 1}
    ).to_list(100)

    edges = 0
    nodes = 0

    for repo in repos:
        project_key = repo.get("project_key", "")
        project_name = repo.get("project", "")
        if not project_key:
            continue

        proj_id = f"project:{project_key}"
        dev_score = repo.get("developer_activity", {}).get("dev_score", 0)
        stars = repo.get("metrics", {}).get("stars", 0)

        # Enrich project node with GitHub metrics
        await upsert_node(db, proj_id, "project", project_name, {
            "github_dev_score": dev_score,
            "github_stars": stars,
            "source_github": True,
        })
        nodes += 1

        for contrib in repo.get("contributors", []):
            login = contrib.get("login", "")
            if not login or login.endswith("[bot]"):
                continue

            contributions = contrib.get("contributions", 0)
            dev_id = f"developer:{login.lower()}"

            await upsert_node(db, dev_id, "developer", login, {
                "github_login": login,
                "avatar_url": contrib.get("avatar_url"),
                "contributions": contributions,
                "source": "github",
            })
            nodes += 1

            # Weight based on contributions (log scale)
            weight = round(min(math.log(1 + contributions) / 8.0, 1.0), 4)

            await upsert_edge(
                db, dev_id, proj_id, "contributes_to", "KNOWLEDGE",
                weight=weight,
                metadata={
                    "contributions": contributions,
                    "source": "github",
                },
            )
            edges += 1

    logger.info(f"[GraphBuilder] GitHub edges: {edges} contributes_to, {nodes} nodes")
    return {"edges": edges, "nodes": nodes}



# ============================================================
# CROSS-LAYER BRIDGES (the critical missing piece)
# ============================================================

async def build_token_project_bridges(db, symbol_lookup: dict):
    """
    Create token:X → project:Y (token_of) edges.
    This bridges SIGNAL layer (mentions token:ETH) to KNOWLEDGE (project:ethereum).
    """
    # Get all token nodes from graph
    token_nodes = await db.graph_nodes.find(
        {"type": "token"},
        {"_id": 0, "id": 1, "label": 1}
    ).to_list(5000)

    edges = 0
    for tn in token_nodes:
        token_id = tn["id"]  # e.g. "token:ETH"
        symbol = token_id.replace("token:", "").upper()

        project_id = symbol_lookup.get(symbol)
        if not project_id:
            continue

        # Check project node exists
        exists = await db.graph_nodes.count_documents({"id": project_id})
        if not exists:
            # Create project node stub
            label = project_id.replace("project:", "").replace("-", " ").title()
            await upsert_node(db, project_id, "project", label, {"source": "token_bridge"})

        await upsert_edge(
            db, token_id, project_id, "token_of", "KNOWLEDGE",
            weight=1.0,
            metadata={"symbol": symbol, "auto_resolved": True}
        )
        edges += 1

    logger.info(f"[GraphBuilder] Token→Project bridges: {edges}")
    return {"edges": edges}


async def build_twitter_person_bridges(db, twitter_lookup: dict):
    """
    Create/update twitter:X → person:Y (account_of) edges.
    Also create twitter:X → project:Y (official_account_of) for project accounts.
    """
    edges = 0

    # Personal accounts
    for handle, person_id in twitter_lookup.items():
        tw_id = f"twitter:{handle}"

        # Ensure both nodes exist
        tw_exists = await db.graph_nodes.count_documents({"id": tw_id})
        person_exists = await db.graph_nodes.count_documents({"id": person_id})

        if tw_exists and person_exists:
            await upsert_edge(
                db, tw_id, person_id, "account_of", "KNOWLEDGE",
                metadata={"auto_resolved": True}
            )
            edges += 1

    # Project accounts
    for handle, proj_id in PROJECT_TWITTER.items():
        tw_id = f"twitter:{handle}"
        tw_exists = await db.graph_nodes.count_documents({"id": tw_id})
        proj_exists = await db.graph_nodes.count_documents({"id": proj_id})

        if tw_exists and proj_exists:
            await upsert_edge(
                db, tw_id, proj_id, "official_account_of", "KNOWLEDGE",
                metadata={"auto_resolved": True}
            )
            edges += 1

    logger.info(f"[GraphBuilder] Twitter→Person/Project bridges: {edges}")
    return {"edges": edges}


# ============================================================
# SIGNAL LAYER BUILDERS (reuse logic from graph_bridge.py)
# ============================================================

async def build_mention_edges(db):
    """actor_signal_events → MENTIONED_TOKEN edges. Weight = log(1+count)*0.6 + recency*0.4"""
    now = datetime.now(timezone.utc)

    pipeline = [
        {"$group": {
            "_id": {"actor": "$actor_handle", "token": "$token"},
            "count": {"$sum": 1},
            "avg_likes": {"$avg": "$metrics.likes"},
            "avg_views": {"$avg": "$metrics.views"},
            "last_seen": {"$max": "$created_at"},
            "signal_types": {"$push": "$signal_type"},
        }},
    ]

    pairs = []
    async for doc in db.actor_signal_events.aggregate(pipeline):
        pairs.append(doc)

    if not pairs:
        return {"edges": 0}

    max_log = max(math.log(1 + p["count"]) for p in pairs) or 1
    edges = 0

    for p in pairs:
        actor = p["_id"]["actor"]
        token = p["_id"]["token"]
        count = p["count"]
        last_seen = p["last_seen"]

        recency = 0.0
        if last_seen:
            try:
                if isinstance(last_seen, str):
                    ls_dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                elif isinstance(last_seen, datetime):
                    ls_dt = last_seen if last_seen.tzinfo else last_seen.replace(tzinfo=timezone.utc)
                else:
                    ls_dt = now
                hours = max((now - ls_dt).total_seconds() / 3600, 0)
                recency = math.exp(-hours / 24)
            except (ValueError, TypeError):
                recency = 0.0

        log_norm = math.log(1 + count) / max(max_log, 1)
        weight = round(log_norm * 0.6 + recency * 0.4, 4)

        from_id = f"twitter:{actor.lower()}"
        to_id = f"token:{token.upper()}"

        await upsert_node(db, from_id, "twitter_account", f"@{actor}",
                          {"source": "signal_pipeline"})
        await upsert_node(db, to_id, "token", token,
                          {"source": "signal_pipeline"})

        type_dist = dict(Counter(p["signal_types"]))

        await upsert_edge(
            db, from_id, to_id, "MENTIONED_TOKEN", "SIGNAL",
            weight=weight,
            metadata={
                "count": count,
                "avg_likes": round(p["avg_likes"] or 0, 1),
                "avg_views": round(p["avg_views"] or 0, 1),
                "last_seen": str(last_seen) if last_seen else None,
                "signal_types": type_dist,
                "recency": round(recency, 4),
            },
        )
        edges += 1

    return {"edges": edges}


async def build_correlation_edges(db, window_minutes=60, min_shared=2):
    """Co-mention analysis → signal_correlated edges."""
    events = await db.actor_signal_events.find(
        {}, {"_id": 0, "actor_handle": 1, "token": 1, "timestamp": 1}
    ).sort("timestamp", 1).to_list(10000)

    if not events:
        return {"edges": 0}

    window_ms = window_minutes * 60 * 1000
    bucket_actors = defaultdict(set)

    for e in events:
        ts = e.get("timestamp")
        if not ts:
            continue
        try:
            if isinstance(ts, str):
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                ts_ms = int(dt.timestamp() * 1000)
            elif isinstance(ts, (int, float)):
                ts_ms = int(ts)
            else:
                continue
        except (ValueError, TypeError):
            continue

        bucket = ts_ms // window_ms
        bucket_actors[(e["token"], bucket)].add(e["actor_handle"])

    pair_tokens = defaultdict(set)
    pair_count = defaultdict(int)

    for (token, _bucket), actors in bucket_actors.items():
        actors = sorted(actors)
        for i in range(len(actors)):
            for j in range(i + 1, len(actors)):
                pair = (actors[i], actors[j])
                pair_tokens[pair].add(token)
                pair_count[pair] += 1

    edges = 0
    for (a1, a2), tokens in pair_tokens.items():
        if len(tokens) < min_shared:
            continue

        count = pair_count[(a1, a2)]
        a1_tokens = set()
        a2_tokens = set()
        for (tok, _b), acts in bucket_actors.items():
            if a1 in acts:
                a1_tokens.add(tok)
            if a2 in acts:
                a2_tokens.add(tok)
        union = a1_tokens | a2_tokens
        strength = len(tokens) / len(union) if union else 0
        weight = round(min(count / 20, 1.0) * 0.6 + strength * 0.4, 4)

        await upsert_edge(
            db, f"twitter:{a1.lower()}", f"twitter:{a2.lower()}",
            "signal_correlated", "SIGNAL",
            weight=weight,
            metadata={
                "shared_tokens": sorted(tokens),
                "co_mention_count": count,
                "correlation_strength": round(strength, 4),
            },
        )
        edges += 1

    return {"edges": edges}


async def enrich_actor_nodes(db):
    """actor_intelligence → graph_nodes metadata."""
    actors = await db.actor_intelligence.find({}, {"_id": 0}).to_list(1000)
    enriched = 0

    for a in actors:
        handle = a.get("actor_handle")
        if not handle:
            continue

        hit_rate = a.get("hit_rate_24h", 0)
        early_ratio = a.get("early_ratio", 0)
        avg_ret = a.get("avg_rel_ret_24h", 0)
        signals = a.get("total_signals", 0)
        role = a.get("role", "UNKNOWN")

        score = (
            hit_rate * 0.35
            + early_ratio * 0.25
            + min(abs(avg_ret) / 5, 1.0) * 0.20
            + min(signals / 20, 1.0) * 0.10
            + (1.0 if role == "DRIVER" else 0.5 if role == "AMPLIFIER" else 0.2) * 0.10
        )

        await upsert_node(db, f"twitter:{handle.lower()}", "twitter_account", f"@{handle}", {
            "actor_score": round(score, 4),
            "hit_rate_24h": round(hit_rate, 4),
            "early_ratio": round(early_ratio, 4),
            "total_signals": signals,
            "role": role,
        })
        enriched += 1

    return {"enriched": enriched}


async def compute_node_scores(db):
    """node_score = alpha*0.5 + influence*0.3 + activity*0.2"""
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)

    actors = await db.graph_nodes.find(
        {"type": "twitter_account"}, {"_id": 0, "id": 1}
    ).to_list(5000)

    scored = 0
    for actor in actors:
        node_id = actor["id"]
        edges = await db.graph_edges.find(
            {"from_node_id": node_id, "relation_type": "MENTIONED_TOKEN", "layer": "SIGNAL"},
            {"_id": 0, "weight": 1, "metadata.alpha_score": 1, "metadata.last_seen": 1}
        ).to_list(500)

        if not edges:
            continue

        alpha_vals = [
            e.get("metadata", {}).get("alpha_score", 0)
            for e in edges if e.get("metadata", {}).get("alpha_score") is not None
        ]
        alpha = sum(alpha_vals) / len(alpha_vals) if alpha_vals else 0

        total_weight = sum(e.get("weight", 0) for e in edges)
        influence = min(math.log(1 + total_weight) / 3.5, 1.0)

        recent = 0
        for e in edges:
            ls = e.get("metadata", {}).get("last_seen")
            if not ls:
                continue
            try:
                if isinstance(ls, str):
                    ls_dt = datetime.fromisoformat(ls.replace("Z", "+00:00"))
                elif isinstance(ls, datetime):
                    ls_dt = ls if ls.tzinfo else ls.replace(tzinfo=timezone.utc)
                else:
                    continue
                if ls_dt > cutoff_24h:
                    recent += 1
            except (ValueError, TypeError):
                continue

        activity = min(math.log(1 + recent) / 3.0, 1.0)
        node_score = round(alpha * 0.5 + influence * 0.3 + activity * 0.2, 4)

        await db.graph_nodes.update_one(
            {"id": node_id},
            {"$set": {"metadata.node_score": node_score}}
        )
        scored += 1

    return {"scored": scored}


# ============================================================
# ORCHESTRATORS
# ============================================================

async def ensure_indexes(db):
    """Create required indexes (idempotent)."""
    try:
        await db.graph_edges.create_index(
            [("from_node_id", 1), ("to_node_id", 1), ("relation_type", 1), ("layer", 1)],
            unique=True, name="idx_edge_layer_dedup"
        )
    except Exception:
        pass
    try:
        await db.graph_edges.create_index("layer", name="idx_layer")
    except Exception:
        pass
    try:
        await db.graph_edges.create_index("relation_type", name="idx_rel_type")
    except Exception:
        pass
    try:
        await db.graph_nodes.create_index("id", unique=True, name="idx_node_id")
    except Exception:
        pass
    try:
        await db.graph_nodes.create_index("type", name="idx_node_type")
    except Exception:
        pass


async def run_full_build(db):
    """
    Full graph rebuild pipeline:
    1. Indexes
    2. Build lookups (entity resolution)
    3. KNOWLEDGE: funding, defi, people
    4. SIGNAL: mentions, correlations, actor enrichment
    5. BRIDGES: token→project, twitter→person
    6. Node scores
    """
    import time
    start = time.time()
    results = {}

    logger.info("[GraphBuilder] === FULL BUILD START ===")

    # Step 0: Indexes
    await ensure_indexes(db)

    # Step 1: Build lookups
    symbol_lookup = await build_symbol_lookup(db)
    twitter_lookup = await build_twitter_person_lookup(db)
    results["lookups"] = {
        "symbols": len(symbol_lookup),
        "twitter_persons": len(twitter_lookup),
    }

    # Step 2: KNOWLEDGE layer
    results["funding"] = await build_funding_edges(db)
    results["defi"] = await build_defi_edges(db)
    results["people"] = await build_people_edges(db)
    results["github"] = await build_github_edges(db)

    # Step 3: SIGNAL layer
    results["mentions"] = await build_mention_edges(db)
    results["correlations"] = await build_correlation_edges(db)
    results["actor_enrichment"] = await enrich_actor_nodes(db)

    # Step 4: CROSS-LAYER BRIDGES (the critical piece)
    results["token_project_bridges"] = await build_token_project_bridges(db, symbol_lookup)
    results["twitter_person_bridges"] = await build_twitter_person_bridges(db, twitter_lookup)

    # Step 5: Node scores
    results["node_scores"] = await compute_node_scores(db)

    # Step 6: INTELLIGENCE (entity_pressure, alpha_source, decay, attention_flow)
    from graph.graph_intelligence import run_graph_intelligence
    results["intelligence"] = await run_graph_intelligence(db)

    # Step 7: ENTITY RESOLUTION RECOVERY
    from graph.graph_resolution import run_resolution_recovery
    results["resolution"] = await run_resolution_recovery(db)

    # Stats
    total_nodes = await db.graph_nodes.count_documents({})
    total_edges = await db.graph_edges.count_documents({})
    signal_edges = await db.graph_edges.count_documents({"layer": "SIGNAL"})
    knowledge_edges = await db.graph_edges.count_documents({"layer": "KNOWLEDGE"})

    elapsed = round(time.time() - start, 1)

    results["totals"] = {
        "nodes": total_nodes,
        "edges": total_edges,
        "signal_edges": signal_edges,
        "knowledge_edges": knowledge_edges,
        "duration_sec": elapsed,
    }

    logger.info(f"[GraphBuilder] === FULL BUILD DONE === {elapsed}s | {total_nodes} nodes, {total_edges} edges")
    return {"ok": True, **results}


async def hydrate_entity(db, query: str):
    """
    On-demand entity hydration.
    User searches for "Solana" → find entity → return subgraph + trigger fresh data if thin.
    """
    import re as _re
    query_clean = query.strip()
    if not query_clean:
        return {"ok": False, "error": "empty query"}

    # Search nodes by ID or label (case-insensitive)
    # Prioritize meaningful types (project, person, fund, token, protocol) over infra (bridge, cex, wallet)
    pattern = _re.compile(_re.escape(query_clean), _re.IGNORECASE)
    priority_types = ["project", "person", "fund", "token", "protocol", "twitter_account", "chain"]
    matched_nodes = await db.graph_nodes.find(
        {"$or": [
            {"id": pattern},
            {"label": pattern},
        ],
        "type": {"$in": priority_types}},
        {"_id": 0}
    ).to_list(20)

    # If no priority matches, fall back to all types
    if not matched_nodes:
        matched_nodes = await db.graph_nodes.find(
            {"$or": [
                {"id": pattern},
                {"label": pattern},
            ]},
            {"_id": 0}
        ).to_list(20)

    if not matched_nodes:
        return {"ok": True, "nodes": [], "edges": [], "message": "no matching entities"}

    node_ids = [n["id"] for n in matched_nodes]

    # Get all edges involving these nodes
    edges = await db.graph_edges.find(
        {"$or": [
            {"from_node_id": {"$in": node_ids}},
            {"to_node_id": {"$in": node_ids}},
        ]},
        {"_id": 0}
    ).to_list(500)

    # Collect neighbor node IDs
    neighbor_ids = set()
    for e in edges:
        fid = e.get("from_node_id") or e.get("from")
        tid = e.get("to_node_id") or e.get("to")
        if fid:
            neighbor_ids.add(fid)
        if tid:
            neighbor_ids.add(tid)
    neighbor_ids -= set(node_ids)

    neighbor_nodes = await db.graph_nodes.find(
        {"id": {"$in": list(neighbor_ids)}},
        {"_id": 0}
    ).to_list(500)

    # Convert datetime fields to strings
    all_nodes = matched_nodes + neighbor_nodes
    for n in all_nodes:
        for k, v in list(n.items()):
            if isinstance(v, datetime):
                n[k] = v.isoformat()
    for e in edges:
        for k, v in list(e.items()):
            if isinstance(v, datetime):
                e[k] = v.isoformat()

    # Thin data check: if matched entity has < 3 edges, suggest hydration
    needs_hydration = len(edges) < 3

    return {
        "ok": True,
        "query": query_clean,
        "matched_nodes": len(matched_nodes),
        "total_edges": len(edges),
        "total_neighbors": len(neighbor_nodes),
        "nodes": all_nodes,
        "edges": edges,
        "needs_hydration": needs_hydration,
    }


async def get_entity_detail(db, entity_id: str):
    """Get single entity with all its edges and neighbors."""
    node = await db.graph_nodes.find_one({"id": entity_id}, {"_id": 0})
    if not node:
        return {"ok": False, "error": f"entity {entity_id} not found"}

    edges = await db.graph_edges.find(
        {"$or": [
            {"from_node_id": entity_id},
            {"to_node_id": entity_id},
        ]},
        {"_id": 0}
    ).to_list(500)

    neighbor_ids = set()
    for e in edges:
        fid = e.get("from_node_id") or e.get("from")
        tid = e.get("to_node_id") or e.get("to")
        if fid:
            neighbor_ids.add(fid)
        if tid:
            neighbor_ids.add(tid)
    neighbor_ids.discard(entity_id)

    neighbors = await db.graph_nodes.find(
        {"id": {"$in": list(neighbor_ids)}},
        {"_id": 0}
    ).to_list(500)

    # Serialize datetimes
    for obj in [node] + neighbors + edges:
        for k, v in list(obj.items()):
            if isinstance(v, datetime):
                obj[k] = v.isoformat()

    # Group edges by layer
    by_layer = defaultdict(list)
    for e in edges:
        by_layer[e.get("layer", "UNKNOWN")].append(e)

    return {
        "ok": True,
        "entity": node,
        "edges": edges,
        "edges_by_layer": {k: len(v) for k, v in by_layer.items()},
        "neighbors": neighbors,
        "total_edges": len(edges),
    }


async def get_build_stats(db):
    """Full graph statistics."""
    total_nodes = await db.graph_nodes.count_documents({})
    total_edges = await db.graph_edges.count_documents({})

    # By layer
    layer_counts = {}
    async for doc in db.graph_edges.aggregate([
        {"$group": {"_id": "$layer", "count": {"$sum": 1}}}
    ]):
        layer_counts[doc["_id"] or "UNKNOWN"] = doc["count"]

    # By relation type
    edge_types = {}
    async for doc in db.graph_edges.aggregate([
        {"$group": {"_id": {"layer": "$layer", "type": "$relation_type"}, "count": {"$sum": 1}}}
    ]):
        key = f"{doc['_id'].get('layer', '?')}:{doc['_id']['type']}"
        edge_types[key] = doc["count"]

    # By node type
    node_types = {}
    async for doc in db.graph_nodes.aggregate([
        {"$group": {"_id": "$type", "count": {"$sum": 1}}}
    ]):
        node_types[doc["_id"]] = doc["count"]

    # Cross-layer bridges count
    token_bridges = await db.graph_edges.count_documents({"relation_type": "token_of"})
    account_bridges = await db.graph_edges.count_documents({"relation_type": "account_of"})
    official_bridges = await db.graph_edges.count_documents({"relation_type": "official_account_of"})

    return {
        "ok": True,
        "nodes": total_nodes,
        "edges": total_edges,
        "layers": layer_counts,
        "edge_types": edge_types,
        "node_types": node_types,
        "cross_layer": {
            "token_of": token_bridges,
            "account_of": account_bridges,
            "official_account_of": official_bridges,
        },
    }
