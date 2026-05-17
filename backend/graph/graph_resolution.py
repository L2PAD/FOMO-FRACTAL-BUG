"""
Entity Resolution Recovery Layer
=================================
Reduces unresolved_nodes_pct by linking orphan nodes to canonical entities.

Three resolution passes:
  1. Token address → symbol → project (0x... → CRV → project:curve-dex)
  2. Project → protocol merge (project:aave-v3 → protocol:aave)
  3. Twitter → person link expansion

Plus: alias store for tracking merges, adjusted health metrics.

Infra types (wallet, exchange, cex, cluster, dex, bridge, contract) are
excluded from unresolved_pct — they are expected orphans from on-chain data.

Target: meaningful unresolved from ~218 to <50 (~75% reduction).
"""

import logging
import re
import math
from datetime import datetime, timezone
from collections import defaultdict

logger = logging.getLogger(__name__)

# Node types that are expected to be orphaned (on-chain infra)
INFRA_TYPES = {"wallet", "exchange", "cex", "cluster", "dex", "bridge", "contract", "entity"}

# Meaningful types for resolution
MEANINGFUL_TYPES = {"project", "protocol", "token", "twitter_account", "person", "fund", "chain", "developer"}


def _normalize(s: str) -> str:
    """Normalize for matching: lowercase, strip non-alphanumeric."""
    if not s:
        return ""
    return re.sub(r"[^a-z0-9]", "", s.lower().strip())


def name_similarity(a: str, b: str) -> float:
    """Simple name similarity. 1.0=exact, 0.85=containment, 0-1=overlap."""
    na = _normalize(a)
    nb = _normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.85
    common = set(na) & set(nb)
    return round(len(common) / max(len(na), len(nb)), 4)


# ── Alias Store ──

async def add_alias(db, canonical_id: str, alias_value: str, source: str):
    """Store alias mapping. Never lose data."""
    now = datetime.now(timezone.utc)
    await db.entity_aliases.update_one(
        {"canonical_id": canonical_id},
        {
            "$addToSet": {
                "aliases": {"value": alias_value, "source": source, "added_at": now}
            },
            "$setOnInsert": {"canonical_id": canonical_id, "created_at": now},
            "$set": {"updated_at": now},
        },
        upsert=True,
    )


# ── Merge Engine ──

async def merge_nodes(db, source_id: str, target_id: str, source_label: str = ""):
    """
    Merge source node into target node:
    1. Re-wire all edges from source → target
    2. Re-wire edge_state
    3. Save alias
    4. Delete source node (data preserved via alias)
    """
    if source_id == target_id:
        return False

    # Re-wire edges
    for field in ("from_node_id", "to_node_id"):
        await db.graph_edges.update_many(
            {field: source_id},
            {"$set": {field: target_id}},
        )

    # Re-wire edge_state
    for field in ("from_node_id", "to_node_id"):
        await db.graph_edge_state.update_many(
            {field: source_id},
            {"$set": {field: target_id}},
        )

    # Save alias
    await add_alias(db, target_id, source_id, "auto_merge")
    if source_label:
        await add_alias(db, target_id, source_label, "auto_merge_label")

    # Delete source node
    await db.graph_nodes.delete_one({"id": source_id})

    return True


# ============================================================
# PASS 1: Token Address → Symbol → Project
# ============================================================

async def resolve_token_addresses(db):
    """
    Map on-chain token addresses (token:0x...) to symbol tokens and projects.
    Uses defi_protocols and cryptorank_projects for address→symbol lookup.
    """
    # Build address → (symbol, name) lookup from DB
    address_map = {}

    # From defi_protocols (has address field sometimes)
    async for doc in db.defi_protocols.find(
        {"symbol": {"$exists": True, "$ne": ""}},
        {"_id": 0, "symbol": 1, "name": 1, "address": 1}
    ):
        addr = (doc.get("address") or "").lower()
        sym = doc["symbol"].upper()
        name = doc.get("name", "")
        if addr and addr.startswith("0x"):
            address_map[addr] = (sym, name)

    # Known top token addresses (hardcoded for critical tokens)
    KNOWN_ADDRESSES = {
        "0x0000000000000000000000000000000000000000": ("ETH", "Ethereum"),
        "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": ("WETH", "Wrapped Ether"),
        "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": ("WBTC", "Wrapped Bitcoin"),
        "0x514910771af9ca656af840dff83e8264ecf986ca": ("LINK", "Chainlink"),
        "0xd533a949740bb3306d119cc777fa900ba034cd52": ("CRV", "Curve DAO"),
        "0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9": ("AAVE", "Aave"),
        "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984": ("UNI", "Uniswap"),
        "0x6b3595068778dd592e39a122f4f5a5cf09c90fe2": ("SUSHI", "SushiSwap"),
        "0xdac17f958d2ee523a2206206994597c13d831ec7": ("USDT", "Tether"),
        "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": ("USDC", "USD Coin"),
        "0x6b175474e89094c44da98b954eedeac495271d0f": ("DAI", "Dai"),
        "0xac3e018457b222d93114458476f3e3416abbe38f": ("sfrxETH", "Staked Frax Ether"),
        "0x5a98fcbea516cf06857215779fd812ca3bef1b32": ("LDO", "Lido DAO"),
        "0xae78736cd615f374d3085123a210448e74fc6393": ("rETH", "Rocket Pool ETH"),
        "0xaf88d065e77c8cc2239327c5edb3a432268e5831": ("USDC", "USD Coin"),
        "0x4200000000000000000000000000000000000042": ("OP", "Optimism"),
        "0x4200000000000000000000000000000000000006": ("WETH", "Wrapped Ether"),
        "0x8292bb45bf1ee4d140127049757c2e0ff06317ed": ("RLUSD", "Ripple USD"),
        "0xc011a73ee8576fb46f5e1c5751ca3b9fe0af2a6f": ("SNX", "Synthetix"),
        "0x4fabb145d64652a948d72533023f6e7a623c7c53": ("BUSD", "Binance USD"),
        "0x8e870d67f660d95d5be530380d0ec0bd388289e1": ("USDP", "Pax Dollar"),
        "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9": ("USDT", "Tether"),
        "0x82af49447d8a07e3bd95bd0d56f35241523fbab1": ("WETH", "Wrapped Ether"),
        "0x912ce59144191c1204e64559fe8253a0e49e6548": ("ARB", "Arbitrum"),
        "0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2": ("MKR", "Maker"),
        "0xc00e94cb662c3520282e6f5717214004a7f26888": ("COMP", "Compound"),
        "0xae7ab96520de3a18e5e111b5eaab095312d7fe84": ("stETH", "Lido Staked ETH"),
        "0xbe9895146f7af43049ca1c1ae358b0541ea49704": ("cbETH", "Coinbase Wrapped Staked ETH"),
        "0x7d1afa7b718fb893db30a3abc0cfc608aacfebb0": ("MATIC", "Polygon"),
        "0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce": ("SHIB", "Shiba Inu"),
        "0x75231f58b43240c9718dd58b4967c5114342a86c": ("OKB", "OKB"),
        "0x2af5d2ad76741191d15dfe7bf6ac92d4bd912ca3": ("LEO", "LEO Token"),
    }
    address_map.update({k.lower(): v for k, v in KNOWN_ADDRESSES.items()})

    # Find orphan token nodes with addresses
    orphan_tokens = await db.graph_nodes.find(
        {"type": "token", "id": {"$regex": "^token:0x"}},
        {"_id": 0, "id": 1, "label": 1}
    ).to_list(500)

    resolved = 0
    merged = 0

    for t in orphan_tokens:
        node_id = t["id"]  # e.g. token:0xd533...:ethereum
        parts = node_id.replace("token:", "").split(":")
        addr = parts[0].lower() if parts else ""
        chain = parts[1] if len(parts) > 1 else ""

        # Try address map first
        if addr in address_map:
            symbol, name = address_map[addr]
        else:
            # Fallback: use label as symbol hint (e.g. label="WBTC" → symbol=WBTC)
            label = (t.get("label") or "").strip()
            if label and not label.startswith("0x") and len(label) <= 12:
                symbol = label.upper()
                name = label
            else:
                continue

        canonical_token_id = f"token:{symbol}"

        # Check if canonical token node exists
        exists = await db.graph_nodes.count_documents({"id": canonical_token_id})

        if exists:
            # Merge address token into symbol token
            ok = await merge_nodes(db, node_id, canonical_token_id, t.get("label", ""))
            if ok:
                merged += 1
        else:
            # Rename this node to canonical symbol
            await db.graph_nodes.update_one(
                {"id": node_id},
                {"$set": {
                    "id": canonical_token_id,
                    "label": symbol,
                    "type": "token",
                    "metadata.original_address": addr,
                    "metadata.chain": chain,
                    "metadata.resolved": True,
                }}
            )
            # Also update edges
            for field in ("from_node_id", "to_node_id"):
                await db.graph_edges.update_many(
                    {field: node_id}, {"$set": {field: canonical_token_id}}
                )
            await add_alias(db, canonical_token_id, node_id, "address_resolve")

        resolved += 1

    logger.info(f"[Resolution] Token addresses: {resolved} resolved, {merged} merged")
    return {"resolved": resolved, "merged": merged}


# ============================================================
# PASS 2: Project → Protocol merge
# ============================================================

async def resolve_project_protocol_links(db):
    """
    Link orphan projects AND chain-specific protocols to existing parent protocols.
    e.g., project:aave-v3 → protocol:aave (via name similarity)
    e.g., protocol:uniswap:ethereum → protocol:uniswap (chain-qualified merge)
    """
    # Get orphan projects (no edges)
    connected = set()
    async for e in db.graph_edges.find({}, {"_id": 0, "from_node_id": 1, "to_node_id": 1, "from": 1, "to": 1}):
        fid = e.get("from_node_id") or e.get("from")
        tid = e.get("to_node_id") or e.get("to")
        if fid:
            connected.add(fid)
        if tid:
            connected.add(tid)

    orphan_projects = await db.graph_nodes.find(
        {"type": "project"},
        {"_id": 0, "id": 1, "label": 1}
    ).to_list(500)
    orphan_projects = [p for p in orphan_projects if p["id"] not in connected]

    # Get all protocols (including chain-qualified)
    all_protocols = await db.graph_nodes.find(
        {"type": "protocol"},
        {"_id": 0, "id": 1, "label": 1}
    ).to_list(500)

    # Separate base protocols from chain-qualified ones
    base_protocols = []
    chain_protocols = []
    for p in all_protocols:
        pid = p["id"].replace("protocol:", "")
        if ":" in pid:  # e.g. uniswap:ethereum
            chain_protocols.append(p)
        else:
            base_protocols.append(p)

    # Build protocol name lookup from base protocols
    proto_lookup = {}
    for p in base_protocols:
        name = _normalize(p.get("label", ""))
        if name:
            proto_lookup[name] = p["id"]
        slug = _normalize(p["id"].replace("protocol:", ""))
        if slug:
            proto_lookup[slug] = p["id"]

    linked = 0
    from graph.graph_builder import upsert_edge

    # Link orphan projects → base protocols
    for proj in orphan_projects:
        proj_name = _normalize(proj.get("label", ""))
        proj_slug = _normalize(proj["id"].replace("project:", ""))

        match_id = None
        sim = 0
        for name_key, proto_id in proto_lookup.items():
            sim = name_similarity(proj_slug, name_key)
            if sim >= 0.85:
                match_id = proto_id
                break

        if match_id:
            await upsert_edge(
                db, proj["id"], match_id, "related_to", "KNOWLEDGE",
                metadata={"source": "auto_resolution", "similarity": sim}
            )
            await add_alias(db, match_id, proj["id"], "project_protocol_link")
            linked += 1

    # Link chain-qualified protocols → base protocols
    chain_linked = 0
    for cp in chain_protocols:
        if cp["id"] in connected:
            continue  # already has edges

        # Extract base name: protocol:uniswap:ethereum → uniswap
        parts = cp["id"].replace("protocol:", "").split(":")
        base_name = parts[0] if parts else ""

        # Try multiple target patterns
        candidates = [
            f"protocol:{base_name}",          # protocol:uniswap
            f"protocol:{base_name}_v3",       # protocol:uniswap_v3
            f"protocol:{base_name}_v2",       # protocol:uniswap_v2
            f"project:{base_name}",           # project:uniswap
        ]

        matched_id = None
        for cand in candidates:
            exists = await db.graph_nodes.count_documents({"id": cand})
            if exists and cand != cp["id"]:
                matched_id = cand
                break

        if matched_id:
            await upsert_edge(
                db, cp["id"], matched_id, "instance_of", "KNOWLEDGE",
                metadata={"source": "chain_protocol_resolution", "chain": parts[1] if len(parts) > 1 else ""}
            )
            await add_alias(db, matched_id, cp["id"], "chain_protocol_link")
            chain_linked += 1

    logger.info(f"[Resolution] Project→Protocol: {linked} linked, {chain_linked} chain protocols linked")
    return {"linked": linked, "orphan_projects": len(orphan_projects), "chain_linked": chain_linked}


# ============================================================
# PASS 3: Enhanced Token → Project bridges
# ============================================================

async def enhance_token_project_bridges(db):
    """
    Additional token→project linking pass.
    Uses cryptorank_projects and defi_protocols for symbol matching.
    """
    from graph.graph_builder import upsert_edge, upsert_node, build_symbol_lookup

    symbol_lookup = await build_symbol_lookup(db)

    # Find token nodes without token_of edges
    tokens_with_bridge = set()
    async for e in db.graph_edges.find(
        {"relation_type": "token_of"},
        {"_id": 0, "from_node_id": 1}
    ):
        tokens_with_bridge.add(e["from_node_id"])

    all_tokens = await db.graph_nodes.find(
        {"type": "token"},
        {"_id": 0, "id": 1, "label": 1}
    ).to_list(500)

    unbridged = [t for t in all_tokens if t["id"] not in tokens_with_bridge]
    bridged = 0

    for t in unbridged:
        symbol = t["id"].replace("token:", "").upper()
        # Skip address tokens
        if symbol.startswith("0X"):
            continue

        project_id = symbol_lookup.get(symbol)
        if not project_id:
            continue

        # Ensure project node exists
        exists = await db.graph_nodes.count_documents({"id": project_id})
        if not exists:
            label = project_id.replace("project:", "").replace("-", " ").title()
            await upsert_node(db, project_id, "project", label, {"source": "token_bridge_recovery"})

        await upsert_edge(
            db, t["id"], project_id, "token_of", "KNOWLEDGE",
            metadata={"source": "resolution_recovery", "symbol": symbol}
        )
        bridged += 1

    logger.info(f"[Resolution] Token→Project bridges: {bridged} new (of {len(unbridged)} unbridged)")
    return {"bridged": bridged, "unbridged_before": len(unbridged)}


# ============================================================
# PASS 4: Twitter → Person/Project link expansion
# ============================================================

# Known twitter handles → entity mappings for high-profile accounts
TWITTER_HANDLE_MAP = {
    # Persons
    "naval": "person:naval-ravikant",
    "suzhu": "person:su-zhu",
    "kylelogandavies": "person:kyle-davies",
    "bantg": "person:banteg",
    "runekek": "person:rune-christensen",
    "dcfgod": "person:dcfgod",
    "ryansadams": "person:ryan-sean-adams",
    "trustlessstate": "person:david-hoffman",
    "defi_dad": "person:defi-dad",
    "zeneca": "person:zeneca",
    "gcrclassic": "person:gcr",
    "loomdart": "person:loomdart",
    "trader_xo": "person:trader-xo",
    "blknoiz06": "person:blknoiz06",
    "embercn": "person:embercn",
    "spotonchain": "person:spotonchain",
    "tayvano_": "person:tay-vano",
    "themooncarl": "person:themooncarl",
    "daancrypto": "person:daancrypto",
    "iamdcinvestor": "person:dcinvestor",
    "crypto_ed_nl": "person:crypto-ed",
    "crypto_mckenna": "person:crypto-mckenna",
    "defi_mochi": "person:defi-mochi",
    # Projects / Media / Analytics
    "coindesk": "project:coindesk",
    "messaricrypto": "project:messari",
    "theblock__": "project:the-block",
    "blockworks_": "project:blockworks",
    "dlnewsinfo": "project:dl-news",
    "decrypt_co": "project:decrypt",
    "wublockchain": "project:wu-blockchain",
    "defillama": "project:defillama",
    "duneanalytics": "project:dune-analytics",
    "glassnode": "project:glassnode",
    "cryptorank_io": "project:cryptorank",
    "artemis_xyz": "project:artemis",
    "metamask": "project:metamask",
    "rabbywallet": "project:rabby",
    # Protocol accounts
    "uniswap": "project:uniswap",
    "aaboraveaave": "project:aave",
    "curvefinance": "project:curve-dex",
    "lidofinance": "project:lido",
    "eigenlayer": "project:eigenlayer",
    "pendlefinance": "project:pendle",
    "synthetixio": "project:synthetix",
    "optimaborismfnd": "project:optimism",
    "arbitrum": "project:arbitrum",
    "solana": "project:solana",
    "ethereum": "project:ethereum",
}


async def enhance_twitter_person_links(db):
    """
    Find orphan twitter accounts and try to link to person/project nodes.
    Uses:
      1. Known handle map (exact match)
      2. Name similarity matching against person nodes
      3. Name similarity matching against project/protocol nodes
      4. Label-based matching (twitter label → person label)
    """
    from graph.graph_builder import upsert_edge, upsert_node

    # Get twitter accounts with no account_of edge
    linked_twitters = set()
    async for e in db.graph_edges.find(
        {"relation_type": {"$in": ["account_of", "official_account_of"]}},
        {"_id": 0, "from_node_id": 1}
    ):
        linked_twitters.add(e["from_node_id"])

    all_twitters = await db.graph_nodes.find(
        {"type": "twitter_account"},
        {"_id": 0, "id": 1, "label": 1}
    ).to_list(1000)

    unlinked = [t for t in all_twitters if t["id"] not in linked_twitters]

    # Get all persons
    persons = await db.graph_nodes.find(
        {"type": "person"},
        {"_id": 0, "id": 1, "label": 1}
    ).to_list(200)

    # Get all projects (for official accounts)
    projects = await db.graph_nodes.find(
        {"type": {"$in": ["project", "protocol"]}},
        {"_id": 0, "id": 1, "label": 1}
    ).to_list(500)

    linked = 0
    created_persons = 0

    for tw in unlinked:
        handle = tw["id"].replace("twitter:", "").lower()
        label = (tw.get("label") or "").strip().lstrip("@")

        # ── 1. Check known handle map ──
        if handle in TWITTER_HANDLE_MAP:
            target_id = TWITTER_HANDLE_MAP[handle]
            rel = "account_of" if target_id.startswith("person:") else "official_account_of"

            # Ensure target node exists
            exists = await db.graph_nodes.count_documents({"id": target_id})
            if not exists:
                ntype = "person" if target_id.startswith("person:") else "project"
                nlabel = target_id.split(":")[-1].replace("-", " ").title()
                await upsert_node(db, target_id, ntype, nlabel, {"source": "twitter_handle_map"})
                if ntype == "person":
                    created_persons += 1

            await upsert_edge(
                db, tw["id"], target_id, rel, "KNOWLEDGE",
                metadata={"source": "handle_map_resolution"}
            )
            linked += 1
            continue

        # ── 2. Name similarity against persons (handle vs person slug) ──
        best_score = 0
        best_target = None
        best_rel = None

        for p in persons:
            person_slug = _normalize(p.get("label", ""))
            person_id_slug = _normalize(p["id"].replace("person:", ""))

            # Compare handle vs person slug
            sim = max(
                name_similarity(handle, person_slug),
                name_similarity(handle, person_id_slug),
            )
            # Also compare label vs person label (e.g. "@Vitalik Buterin" vs "Vitalik Buterin")
            if label:
                sim = max(sim, name_similarity(_normalize(label), person_slug))

            if sim > best_score and sim >= 0.75:
                best_score = sim
                best_target = p["id"]
                best_rel = "account_of"

        # ── 3. Name similarity against projects ──
        for p in projects:
            proj_slug = _normalize(p.get("label", ""))
            proj_id_slug = _normalize(p["id"].split(":")[-1])

            sim = max(
                name_similarity(handle, proj_slug),
                name_similarity(handle, proj_id_slug),
            )
            if label:
                sim = max(sim, name_similarity(_normalize(label), proj_slug))

            if sim > best_score and sim >= 0.80:
                best_score = sim
                best_target = p["id"]
                best_rel = "official_account_of"

        if best_target:
            await upsert_edge(
                db, tw["id"], best_target, best_rel, "KNOWLEDGE",
                metadata={"source": "resolution_recovery", "similarity": best_score}
            )
            linked += 1

    logger.info(
        f"[Resolution] Twitter links: {linked} new (of {len(unlinked)} unlinked), "
        f"{created_persons} person nodes created"
    )
    return {"linked": linked, "unlinked_before": len(unlinked), "created_persons": created_persons}


# ============================================================
# PASS 5: Ensure Twitter actors with signals are connected
# ============================================================

async def connect_signal_actors(db):
    """
    Twitter accounts that have MENTIONED_TOKEN edges but no account_of/official_account_of
    are legitimate signal actors. Mark them as resolved — they don't need person links,
    their value comes from SIGNAL layer connections.
    
    Also: check for twitter accounts that appear in actor_signal_events but
    have no graph edges at all — create edges from their mentions.
    """
    # Get all twitter nodes with NO edges
    connected = set()
    async for e in db.graph_edges.find({}, {"_id": 0, "from_node_id": 1, "to_node_id": 1, "from": 1, "to": 1}):
        fid = e.get("from_node_id") or e.get("from")
        tid = e.get("to_node_id") or e.get("to")
        if fid:
            connected.add(fid)
        if tid:
            connected.add(tid)

    orphan_twitter = []
    async for n in db.graph_nodes.find(
        {"type": "twitter_account"},
        {"_id": 0, "id": 1, "label": 1}
    ):
        if n["id"] not in connected:
            orphan_twitter.append(n)

    if not orphan_twitter:
        logger.info("[Resolution] Signal actors: 0 orphan twitter accounts")
        return {"connected": 0, "orphan_twitter": 0}

    # Try to find their mentions in actor_signal_events
    from graph.graph_builder import upsert_edge, upsert_node, build_symbol_lookup

    symbol_lookup = await build_symbol_lookup(db)
    reconnected = 0

    for tw in orphan_twitter:
        handle = tw["id"].replace("twitter:", "")

        # Check if they have signal events
        events = await db.actor_signal_events.find(
            {"actor": {"$regex": f"^@?{re.escape(handle)}$", "$options": "i"}},
            {"_id": 0, "tokens": 1}
        ).to_list(50)

        if not events:
            continue

        # Collect all mentioned tokens
        mentioned = set()
        for ev in events:
            for tok in (ev.get("tokens") or []):
                sym = tok.upper().lstrip("$")
                if sym in symbol_lookup:
                    mentioned.add(f"token:{sym}")
                elif len(sym) <= 10 and sym.isalpha():
                    mentioned.add(f"token:{sym}")

        # Create MENTIONED_TOKEN edges
        for token_id in mentioned:
            await upsert_edge(
                db, tw["id"], token_id, "MENTIONED_TOKEN", "SIGNAL",
                metadata={"source": "resolution_reconnect"}
            )

        if mentioned:
            reconnected += 1

    logger.info(f"[Resolution] Signal actors: {reconnected} reconnected (of {len(orphan_twitter)} orphan)")
    return {"connected": reconnected, "orphan_twitter": len(orphan_twitter)}


# ============================================================
# ORCHESTRATOR
# ============================================================

async def run_resolution_recovery(db):
    """
    Full resolution pass. Run after graph_builder, before health check.
    
    Passes:
      1. Token addresses → symbol tokens (merge 0x... → canonical)
      2. Project → Protocol links (orphan projects → protocol match)
      3. Token → Project bridges (symbol matching)
      4. Twitter → Person/Project links (handle map + fuzzy)
      5. Signal actor reconnection (orphan twitters with mentions)
    """
    import time
    start = time.time()
    results = {}

    logger.info("[Resolution] === RECOVERY START ===")

    results["token_addresses"] = await resolve_token_addresses(db)
    results["project_protocol"] = await resolve_project_protocol_links(db)
    results["token_project_bridges"] = await enhance_token_project_bridges(db)
    results["twitter_person"] = await enhance_twitter_person_links(db)
    results["signal_actors"] = await connect_signal_actors(db)

    # Compute meaningful unresolved (excluding infra types)
    total_meaningful = await db.graph_nodes.count_documents({"type": {"$in": list(MEANINGFUL_TYPES)}})
    connected = set()
    async for e in db.graph_edges.find({}, {"_id": 0, "from_node_id": 1, "to_node_id": 1, "from": 1, "to": 1}):
        fid = e.get("from_node_id") or e.get("from")
        tid = e.get("to_node_id") or e.get("to")
        if fid:
            connected.add(fid)
        if tid:
            connected.add(tid)

    meaningful_orphans = 0
    async for n in db.graph_nodes.find(
        {"type": {"$in": list(MEANINGFUL_TYPES)}},
        {"_id": 0, "id": 1}
    ):
        if n["id"] not in connected:
            meaningful_orphans += 1

    meaningful_unresolved_pct = round(meaningful_orphans / max(total_meaningful, 1) * 100, 2)

    elapsed = round(time.time() - start, 1)

    results["summary"] = {
        "total_meaningful_nodes": total_meaningful,
        "meaningful_orphans": meaningful_orphans,
        "meaningful_unresolved_pct": meaningful_unresolved_pct,
        "duration_sec": elapsed,
    }

    # Also store alias count
    alias_count = await db.entity_aliases.count_documents({})
    results["summary"]["aliases_stored"] = alias_count

    logger.info(
        f"[Resolution] === DONE === {elapsed}s | "
        f"meaningful_unresolved: {meaningful_unresolved_pct}% "
        f"({meaningful_orphans}/{total_meaningful})"
    )

    return {"ok": True, **results}


async def get_resolution_stats(db):
    """Stats about resolution state."""
    # Count by type
    total_nodes = await db.graph_nodes.count_documents({})
    total_meaningful = await db.graph_nodes.count_documents({"type": {"$in": list(MEANINGFUL_TYPES)}})
    total_infra = await db.graph_nodes.count_documents({"type": {"$in": list(INFRA_TYPES)}})

    connected = set()
    async for e in db.graph_edges.find({}, {"_id": 0, "from_node_id": 1, "to_node_id": 1, "from": 1, "to": 1}):
        fid = e.get("from_node_id") or e.get("from")
        tid = e.get("to_node_id") or e.get("to")
        if fid:
            connected.add(fid)
        if tid:
            connected.add(tid)

    meaningful_orphans = 0
    infra_orphans = 0
    async for n in db.graph_nodes.find({}, {"_id": 0, "id": 1, "type": 1}):
        if n["id"] not in connected:
            if n["type"] in INFRA_TYPES:
                infra_orphans += 1
            elif n["type"] in MEANINGFUL_TYPES:
                meaningful_orphans += 1

    aliases = await db.entity_aliases.count_documents({})

    # Token bridge coverage
    total_tokens = await db.graph_nodes.count_documents({"type": "token"})
    bridged_tokens = len(set([
        e["from_node_id"] async for e in db.graph_edges.find(
            {"relation_type": "token_of"}, {"_id": 0, "from_node_id": 1}
        )
    ]))

    # Twitter link coverage
    total_tw = await db.graph_nodes.count_documents({"type": "twitter_account"})
    linked_tw = len(set([
        e["from_node_id"] async for e in db.graph_edges.find(
            {"relation_type": {"$in": ["account_of", "official_account_of"]}},
            {"_id": 0, "from_node_id": 1}
        )
    ]))

    return {
        "ok": True,
        "total_nodes": total_nodes,
        "meaningful_nodes": total_meaningful,
        "infra_nodes": total_infra,
        "meaningful_orphans": meaningful_orphans,
        "infra_orphans": infra_orphans,
        "meaningful_unresolved_pct": round(meaningful_orphans / max(total_meaningful, 1) * 100, 2),
        "raw_unresolved_pct": round((meaningful_orphans + infra_orphans) / max(total_nodes, 1) * 100, 2),
        "aliases": aliases,
        "token_bridge_coverage": f"{bridged_tokens}/{total_tokens}",
        "twitter_link_coverage": f"{linked_tw}/{total_tw}",
    }
