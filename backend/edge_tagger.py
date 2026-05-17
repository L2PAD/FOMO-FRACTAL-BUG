"""
Edge Tagger Service
====================
Automatically tags edges based on rules.

Tags:
  - large_transfer: amountUsd > $500,000
  - exchange_deposit: target is CEX
  - exchange_withdraw: source is CEX
  - bridge_exit: edge type is bridge/exit
  - dex_swap: edge type is swap or source/target is DEX
"""

LARGE_TRANSFER_THRESHOLD_USD = 500000

CEX_NODE_TYPES = {"cex", "exchange"}
DEX_NODE_TYPES = {"dex"}
BRIDGE_EDGE_TYPES = {"bridge", "exit"}
SWAP_EDGE_TYPES = {"swap"}


def tag_edges(edges, node_map):
    """
    Tag edges based on rules. Modifies edges in-place by adding 'tags' field.

    Args:
        edges: list of edge dicts
        node_map: dict of node_id → node dict (for type lookups)

    Returns:
        edges (same list, mutated with tags)
    """
    for edge in edges:
        tags = []

        amount = edge.get("amountUsd") or 0
        edge_type = (edge.get("type") or "").lower()
        source_id = edge.get("source") or edge.get("from_node_id") or ""
        target_id = edge.get("target") or edge.get("to_node_id") or ""

        source_node = node_map.get(source_id, {})
        target_node = node_map.get(target_id, {})
        source_type = (source_node.get("type") or source_node.get("entity_type") or "").lower()
        target_type = (target_node.get("type") or target_node.get("entity_type") or "").lower()

        # large_transfer
        if amount > LARGE_TRANSFER_THRESHOLD_USD:
            tags.append("large_transfer")

        # exchange_deposit: target is CEX
        if target_type in CEX_NODE_TYPES:
            tags.append("exchange_deposit")

        # exchange_withdraw: source is CEX
        if source_type in CEX_NODE_TYPES:
            tags.append("exchange_withdraw")

        # bridge_exit
        if edge_type in BRIDGE_EDGE_TYPES:
            tags.append("bridge_exit")

        # dex_swap
        if edge_type in SWAP_EDGE_TYPES or source_type in DEX_NODE_TYPES or target_type in DEX_NODE_TYPES:
            tags.append("dex_swap")

        edge["tags"] = tags

    return edges
