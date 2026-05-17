"""
Corridor Detector Service
=========================
Detects liquidity corridor patterns in graph edges.

Patterns:
  1. DEX → BRIDGE → DEX
  2. DEX → BRIDGE → CEX
  3. CEX → BRIDGE → DEX

Input: aggregated relations (nodes + edges)
Output: list of Corridor objects

Guard: min corridor value = $50,000
"""

MIN_CORRIDOR_VALUE_USD = 50000

# Node types that qualify for corridor endpoints
DEX_TYPES = {"dex", "exchange"}
CEX_TYPES = {"cex"}
BRIDGE_TYPES = {"bridge"}

# Edge types that qualify for corridor segments
SWAP_EDGE_TYPES = {"swap", "transfer"}
BRIDGE_EDGE_TYPES = {"bridge", "exit"}
DEPOSIT_EDGE_TYPES = {"deposit", "transfer", "swap"}


def _node_type_set(node_id, node_map):
    """Get node type from node_map, return as lowercase"""
    node = node_map.get(node_id)
    if not node:
        return ""
    return (node.get("type") or node.get("entity_type") or "").lower()


def _is_dex(ntype):
    return ntype in DEX_TYPES


def _is_cex(ntype):
    return ntype in CEX_TYPES


def _is_bridge(ntype):
    return ntype in BRIDGE_TYPES


def detect_corridors(nodes, edges):
    """
    Detect liquidity corridors from aggregated graph data.

    Args:
        nodes: list of node dicts with at least {id, type}
        edges: list of edge dicts with at least {source, target, type, amountUsd}

    Returns:
        list of corridor dicts
    """
    if not nodes or not edges:
        return []

    # Build node lookup
    node_map = {}
    for n in nodes:
        nid = n.get("id", "")
        node_map[nid] = n

    # Build adjacency: source → list of edges
    adj = {}
    for e in edges:
        src = e.get("source") or e.get("from_node_id") or ""
        if src:
            adj.setdefault(src, []).append(e)

    corridors = []
    seen_corridors = set()

    # For each edge, try to extend into a 3-hop corridor
    for e1 in edges:
        src1 = e1.get("source") or e1.get("from_node_id") or ""
        tgt1 = e1.get("target") or e1.get("to_node_id") or ""
        type1 = (e1.get("type") or "").lower()
        t1_node = _node_type_set(tgt1, node_map)

        # Step 1: First edge should be swap/transfer FROM dex/cex
        s1_type = _node_type_set(src1, node_map)
        if not (_is_dex(s1_type) or _is_cex(s1_type)):
            continue
        if type1 not in SWAP_EDGE_TYPES and type1 not in BRIDGE_EDGE_TYPES:
            continue

        # Look for second edge from tgt1
        for e2 in adj.get(tgt1, []):
            tgt2 = e2.get("target") or e2.get("to_node_id") or ""
            type2 = (e2.get("type") or "").lower()
            t2_node = _node_type_set(tgt2, node_map)

            # Step 2: Must pass through bridge
            bridge_in_path = _is_bridge(t1_node) or _is_bridge(t2_node) or type2 in BRIDGE_EDGE_TYPES

            if not bridge_in_path:
                continue

            # Look for third edge from tgt2
            for e3 in adj.get(tgt2, []):
                tgt3 = e3.get("target") or e3.get("to_node_id") or ""
                t3_node = _node_type_set(tgt3, node_map)

                # Step 3: Final destination must be dex or cex
                if not (_is_dex(t3_node) or _is_cex(t3_node)):
                    continue

                # Validate corridor pattern
                pattern = _classify_pattern(s1_type, t3_node)
                if not pattern:
                    continue

                # Compute corridor value (max of any edge)
                amounts = [
                    e1.get("amountUsd") or 0,
                    e2.get("amountUsd") or 0,
                    e3.get("amountUsd") or 0,
                ]
                corridor_value = max(amounts)

                # Value guard
                if corridor_value < MIN_CORRIDOR_VALUE_USD:
                    continue

                # Build path
                path = [src1, tgt1, tgt2, tgt3]

                # Deduplicate
                corridor_key = f"{src1}->{tgt3}:{pattern}"
                if corridor_key in seen_corridors:
                    continue
                seen_corridors.add(corridor_key)

                # Collect chains
                chains = set()
                for nid in path:
                    node = node_map.get(nid, {})
                    chain = node.get("chain")
                    if chain and chain != "unknown":
                        chains.add(chain)

                corridors.append({
                    "id": f"corridor:{src1}-{tgt3}",
                    "source": src1,
                    "target": tgt3,
                    "pattern": pattern,
                    "amountUsd": corridor_value,
                    "path": path,
                    "chains": list(chains),
                })

    # Also try 2-hop corridors (direct: DEX → BRIDGE → CEX without intermediate)
    for e1 in edges:
        src1 = e1.get("source") or e1.get("from_node_id") or ""
        tgt1 = e1.get("target") or e1.get("to_node_id") or ""
        s1_type = _node_type_set(src1, node_map)
        t1_type = _node_type_set(tgt1, node_map)
        type1 = (e1.get("type") or "").lower()

        if not _is_bridge(t1_type) and type1 not in BRIDGE_EDGE_TYPES:
            continue

        for e2 in adj.get(tgt1, []):
            tgt2 = e2.get("target") or e2.get("to_node_id") or ""
            t2_type = _node_type_set(tgt2, node_map)

            pattern = _classify_pattern(s1_type, t2_type)
            if not pattern:
                continue

            amounts = [e1.get("amountUsd") or 0, e2.get("amountUsd") or 0]
            corridor_value = max(amounts)

            if corridor_value < MIN_CORRIDOR_VALUE_USD:
                continue

            path = [src1, tgt1, tgt2]
            corridor_key = f"{src1}->{tgt2}:{pattern}"
            if corridor_key in seen_corridors:
                continue
            seen_corridors.add(corridor_key)

            chains = set()
            for nid in path:
                node = node_map.get(nid, {})
                chain = node.get("chain")
                if chain and chain != "unknown":
                    chains.add(chain)

            corridors.append({
                "id": f"corridor:{src1}-{tgt2}",
                "source": src1,
                "target": tgt2,
                "pattern": pattern,
                "amountUsd": corridor_value,
                "path": path,
                "chains": list(chains),
            })

    return corridors


def _classify_pattern(source_type, target_type):
    """Classify corridor pattern based on source/target node types"""
    if _is_dex(source_type) and _is_dex(target_type):
        return "DEX_BRIDGE_DEX"
    if _is_dex(source_type) and _is_cex(target_type):
        return "DEX_BRIDGE_CEX"
    if _is_cex(source_type) and _is_dex(target_type):
        return "CEX_BRIDGE_DEX"
    if _is_cex(source_type) and _is_cex(target_type):
        return "CEX_BRIDGE_CEX"
    return None
