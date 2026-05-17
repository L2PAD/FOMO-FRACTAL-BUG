"""
Graph Projection Layer — Phase A Core
=======================================
Intermediate layer between Graph Engine and ForceGraphViewer (UI).

Pipeline:
  graph_storage → graph_engine → graph_projection → graph_api → ForceGraphViewer

4 Projection Steps:
  1. Node Compression — collapse many wallets into cluster nodes
  2. Entity Promotion — wallet → entity when entity is known
  3. Route Aggregation — many small txs → one aggregated edge
  4. Graph Window — limit depth=2, nodes≤150, edges≤400

Graph Rendering Contract (NEVER CHANGE):
  Node: { id, label, type, chain, address }
  Edge: { source, target, direction, type, amountUsd }

ForceGraphViewer must never know about Graph Engine internals.
"""

from collections import defaultdict
from graph_normalizer import normalize_node_id, parse_node_id
from identity_resolver_service import dedupe_edges_for_level, dedupe_nodes_for_level
import graph_storage as storage


async def project_graph(
    db,
    center_node_id,
    depth=2,
    max_nodes=150,
    max_edges=400,
    mode=None,
    start_time=None,
    end_time=None,
    level=None,
    chains=None,
):
    """
    Main projection entry point. Returns UI-compatible {nodes, edges}.
    
    Args:
        level: Identity hierarchy level (wallet, cluster, entity, None=wallet)
        chains: Optional list of chain keys (e.g., ['ethereum', 'arbitrum'])
    """
    storage.init_storage(db)

    # Step 0: Get raw graph from storage (chain-filtered)
    raw_nodes, raw_edges = await storage.build_graph_from_relations(
        center_node_id,
        depth=depth,
        limit_nodes=max_nodes * 2,
        limit_edges=max_edges * 2,
        start_time=start_time,
        end_time=end_time,
        chains=chains,
    )

    if not raw_nodes and not raw_edges:
        return {"nodes": [], "edges": [], "meta": {"source": "empty", "mode": mode, "level": level}}

    # Step 1: Node Compression
    nodes, edges, compression_map = _compress_clusters(raw_nodes, raw_edges, max_nodes)

    # Step 2: Entity Promotion
    nodes, edges = _promote_entities(nodes, edges)

    # Step 3: Route Aggregation
    edges = _aggregate_routes(edges, max_edges)

    # Step 4: Mode Filtering (skip cex_flow — handled post-render in render endpoint)
    if mode and mode != "cex_flow":
        nodes, edges = _apply_mode_filter(nodes, edges, mode)

    # Step 5: Identity Hierarchy (collapse to requested level)
    effective_level = level or "wallet"
    if effective_level in ("cluster", "entity"):
        nodes = await dedupe_nodes_for_level(db, nodes, effective_level)
        edges = await dedupe_edges_for_level(db, edges, effective_level)

    # Step 6: Graph Window
    nodes = nodes[:max_nodes]
    edge_node_ids = {n["id"] for n in nodes}
    edges = [e for e in edges if e["source"] in edge_node_ids and e["target"] in edge_node_ids]
    edges = edges[:max_edges]

    projected_nodes = [_to_ui_node(n) for n in nodes]
    projected_edges = [_to_ui_edge(e) for e in edges]

    return {
        "nodes": projected_nodes,
        "edges": projected_edges,
        "meta": {
            "source": "projection",
            "mode": mode,
            "level": effective_level,
            "raw_nodes": len(raw_nodes),
            "raw_edges": len(raw_edges),
            "projected_nodes": len(projected_nodes),
            "projected_edges": len(projected_edges),
            "compressions": len(compression_map),
        },
    }


# ========================================================
# Step 1: NODE COMPRESSION
# ========================================================

def _compress_clusters(nodes, edges, max_nodes):
    """
    Collapse wallet groups into their cluster node when graph is too large.
    If a cluster has many wallets, replace them with a single cluster node.
    """
    compression_map = {}  # old_id → cluster_node_id

    if len(nodes) <= max_nodes:
        return nodes, edges, compression_map

    # Group nodes by cluster_id
    cluster_groups = defaultdict(list)
    unclustered = []
    for n in nodes:
        cid = n.get("cluster_id")
        if cid and n.get("type") == "wallet":
            cluster_groups[cid].append(n)
        else:
            unclustered.append(n)

    # For clusters with >3 members, compress into single cluster node
    compressed_nodes = list(unclustered)
    for cid, members in cluster_groups.items():
        if len(members) > 3:
            # Create compressed cluster node
            total_flow = sum(m.get("total_flow_usd", 0) for m in members)
            cluster_node = {
                "id": normalize_node_id("cluster", cid, "ethereum"),
                "type": "cluster",
                "label": _get_cluster_label(cid, members),
                "address": cid,
                "chain": "ethereum",
                "degree": sum(m.get("degree", 0) for m in members),
                "total_flow_usd": total_flow,
                "metadata": {"members_count": len(members)},
            }
            compressed_nodes.append(cluster_node)
            for m in members:
                compression_map[m["id"]] = cluster_node["id"]
        else:
            compressed_nodes.extend(members)

    # Update edges to point to compressed nodes
    updated_edges = []
    for e in edges:
        new_source = compression_map.get(e.get("source", ""), e.get("source", ""))
        new_target = compression_map.get(e.get("target", ""), e.get("target", ""))
        e_copy = dict(e)
        e_copy["source"] = new_source
        e_copy["target"] = new_target
        updated_edges.append(e_copy)

    return compressed_nodes, updated_edges, compression_map


def _get_cluster_label(cluster_id, members):
    """Generate a descriptive cluster label."""
    # Check if any member has an entity name
    for m in members:
        entity = m.get("entity", "")
        if entity:
            return entity
    # Fall back to cluster_id-based label
    return f"Cluster ({len(members)} wallets)"


# ========================================================
# Step 2: ENTITY PROMOTION
# ========================================================

def _promote_entities(nodes, edges):
    """
    When a wallet belongs to a known entity, promote its label and type.
    wallet:0xabc → entity:binance (but keep position/color unchanged)
    """
    for node in nodes:
        if node.get("type") == "wallet" and node.get("entity"):
            # Promote label to entity name, keep the same node ID
            entity_name = node["entity"]
            node["label"] = entity_name
            # Don't change type — UI uses type for colors, we just improve label

    return nodes, edges


# ========================================================
# Step 3: ROUTE AGGREGATION
# ========================================================

def _aggregate_routes(edges, max_edges):
    """
    Aggregate multiple edges between the same pair into a single thicker edge.
    wallet → dex (×3 transfers) → single edge with sum amount.
    """
    if len(edges) <= max_edges:
        return edges

    # Group by (source, target)
    pair_map = defaultdict(list)
    for e in edges:
        key = (e.get("source", ""), e.get("target", ""))
        pair_map[key].append(e)

    aggregated = []
    for (src, tgt), group in pair_map.items():
        if len(group) == 1:
            aggregated.append(group[0])
        else:
            # Merge into single edge
            total_amount = sum(e.get("amountUsd", 0) for e in group)
            total_tx = sum(e.get("txCount", 0) for e in group)
            # Use the most significant edge type
            best = max(group, key=lambda e: e.get("amountUsd", 0))
            merged = dict(best)
            merged["amountUsd"] = total_amount
            merged["txCount"] = total_tx
            merged["id"] = f"{src}-{tgt}-aggregated"
            all_tags = []
            for e in group:
                all_tags.extend(e.get("tags", []))
            merged["tags"] = list(set(all_tags))[:10]
            aggregated.append(merged)

    return aggregated


# ========================================================
# Step 4: MODE FILTERING
# ========================================================

MODE_NODE_TYPES = {
    "smart_money": {"wallet", "cluster", "entity", "token", "exchange"},
    "cex_flow": {"exchange", "cex", "wallet", "token"},
    "token_rotation": {"token", "wallet", "cluster", "dex"},
    "entity": {"entity", "protocol", "exchange", "dex", "wallet"},
    "risk": {"wallet", "cluster", "entity", "exchange", "alert"},
}

MODE_EDGE_TYPES = {
    "smart_money": {"accumulation", "distribution", "rotation", "capital_route", "transfer", "cluster_member", "swap"},
    "cex_flow": {"deposit", "withdraw", "liquidity_provision", "market_making", "transfer"},
    "token_rotation": {"rotation", "swap", "accumulation", "distribution", "transfer"},
    "entity": {"entity_control", "transfer", "deposit", "withdraw", "accumulation", "distribution", "swap", "cluster_member"},
    "risk": {"transfer", "risk_link", "alert_link", "deposit", "withdraw", "swap"},
}


def _apply_mode_filter(nodes, edges, mode):
    """Filter nodes and edges to match the selected graph mode."""
    allowed_node_types = MODE_NODE_TYPES.get(mode, set())
    allowed_edge_types = MODE_EDGE_TYPES.get(mode, set())

    if not allowed_node_types:
        return nodes, edges

    # Special handling for cex_flow: only keep edges touching a CEX/exchange node
    if mode == "cex_flow":
        return _apply_cex_flow_filter(nodes, edges, allowed_edge_types)

    filtered_nodes = [n for n in nodes if n.get("type", "wallet") in allowed_node_types]
    node_ids = {n["id"] for n in filtered_nodes}

    filtered_edges = [
        e for e in edges
        if e.get("type", "transfer") in allowed_edge_types
        and e.get("source", "") in node_ids
        and e.get("target", "") in node_ids
    ]

    return filtered_nodes, filtered_edges


CEX_NODE_TYPES = {"cex", "exchange"}
CEX_EDGE_TYPES = {"deposit", "withdraw"}

def _apply_cex_flow_filter(nodes, edges, allowed_edge_types):
    """
    CEX Flow filter: show only flows directly involving CEX/exchange activity.
    Strategy:
    1. Find explicit CEX/exchange nodes (by type or id prefix)
    2. Keep edges that touch a CEX node OR are deposit/withdraw type (inherently CEX-related)
    3. Keep only nodes that appear in those filtered edges
    """
    # Identify explicit CEX node IDs
    cex_node_ids = set()
    for n in nodes:
        ntype = (n.get("type") or "wallet").lower()
        nid = n.get("id", "")
        if ntype in CEX_NODE_TYPES or nid.startswith("cex:") or nid.startswith("exchange:"):
            cex_node_ids.add(nid)

    all_node_ids = {n.get("id", "") for n in nodes}
    filtered_edges = []
    connected_node_ids = set()

    for e in edges:
        src = e.get("source", "")
        tgt = e.get("target", "")
        etype = e.get("type", "transfer")
        if etype not in allowed_edge_types:
            continue
        if src not in all_node_ids or tgt not in all_node_ids:
            continue
        # Keep if: touches a CEX node OR edge type is inherently CEX-related
        if src in cex_node_ids or tgt in cex_node_ids or etype in CEX_EDGE_TYPES:
            filtered_edges.append(e)
            connected_node_ids.add(src)
            connected_node_ids.add(tgt)

    if not connected_node_ids:
        return [], []

    filtered_nodes = [n for n in nodes if n.get("id", "") in connected_node_ids]
    return filtered_nodes, filtered_edges


# ========================================================
# UI CONTRACT FORMATTERS
# ========================================================

def _to_ui_node(node):
    """Convert internal node to Graph Rendering Contract format."""
    label = (node.get("label", "") or "").replace("_", " ")
    return {
        "id": node.get("id", ""),
        "label": label,
        "type": node.get("type", "wallet"),
        "chain": node.get("chain", "ethereum"),
        "address": node.get("address", ""),
        # Extended fields (don't break UI)
        "degree": node.get("degree", 0),
        "totalFlowUsd": node.get("total_flow_usd", 0),
        "importanceScore": node.get("importance_score", 0),
        "smartMoneyScore": node.get("smart_money_score", 0),
        "riskScore": node.get("risk_score", 0),
        "alphaScore": node.get("alpha_score", 0),
        "capitalInfluenceScore": node.get("capital_influence_score", 0),
        "clusterId": node.get("cluster_id", ""),
        "actorType": node.get("actor_type", ""),
        "behavior": node.get("behavior", ""),
        "entity": node.get("entity", ""),
        "metadata": node.get("metadata", {}),
    }


def _to_ui_edge(edge):
    """Convert internal edge to Graph Rendering Contract format."""
    return {
        "id": edge.get("id", ""),
        "source": edge.get("source", ""),
        "target": edge.get("target", ""),
        "direction": edge.get("direction", "out"),
        "type": edge.get("type", "transfer"),
        "amountUsd": edge.get("amountUsd", 0),
        # Extended fields
        "txCount": edge.get("txCount", 0),
        "confidence": edge.get("confidence", 0),
        "tags": edge.get("tags", []),
        "flowDirection": edge.get("flowDirection", ""),
        "signalStrength": edge.get("signalStrength", 0),
        "chain": edge.get("chain", "ethereum"),
    }
