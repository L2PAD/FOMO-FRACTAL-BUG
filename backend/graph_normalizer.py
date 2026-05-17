"""
Graph Node ID Normalizer — Single Source of Truth
===================================================
Canonical format:  {type}:{lowercase_identifier}:{chain}

Supported node types:
  wallet, cluster, entity, token, exchange, dex, bridge,
  protocol, alert, narrative, route, signal, cex, contract

Supported edge types:
  transfer, deposit, withdraw, swap,
  accumulation, distribution, rotation,
  liquidity_provision, market_making,
  cluster_member, entity_control,
  corridor, capital_route,
  signal_link, risk_link, alert_link

Every builder, seeder, snapshot builder, and cache layer
MUST use normalize_node_id() to produce node IDs.
"""


# All valid node types in the unified schema
VALID_NODE_TYPES = {
    "wallet", "cluster", "entity", "token", "exchange", "dex",
    "bridge", "protocol", "alert", "narrative", "route", "signal",
    "cex", "contract",
}

# All valid edge types in the unified schema
VALID_EDGE_TYPES = {
    "transfer", "deposit", "withdraw", "swap",
    "accumulation", "distribution", "rotation",
    "liquidity_provision", "market_making",
    "cluster_member", "entity_control",
    "corridor", "capital_route",
    "signal_link", "risk_link", "alert_link",
}

# Canonical type aliases — collapse legacy types into standard ones
_TYPE_ALIASES = {
    "active_wallet": "wallet",
    "multi_exchange_user": "wallet",
    "whale": "wallet",
    "fund": "entity",
    "market_maker": "entity",
}


def normalize_node_id(node_type: str, identifier: str, chain: str = "ethereum") -> str:
    """
    Produce a canonical node ID.

    Args:
        node_type: wallet, cex, dex, token, bridge, contract, etc.
        identifier: Ethereum address or slug (lowercased automatically).
        chain: Network name (default: ethereum).

    Returns:
        Canonical node ID string.
    """
    t = _TYPE_ALIASES.get(node_type.lower(), node_type.lower())
    return f"{t}:{identifier.lower()}:{chain.lower()}"


def normalize_existing_id(node_id: str) -> str:
    """
    Re-normalize an existing node ID string.
    Handles the format  type:identifier:chain  — lowercases everything
    and applies type aliases.
    """
    parts = node_id.split(":")
    if len(parts) < 2:
        return node_id.lower()

    ntype = parts[0]
    chain = parts[2] if len(parts) >= 3 else "ethereum"
    identifier = ":".join(parts[1:-1]) if len(parts) >= 3 else parts[1]

    return normalize_node_id(ntype, identifier, chain)


def extract_address(node_id: str) -> str:
    """Extract the identifier (address) portion from a canonical node ID."""
    parts = node_id.split(":")
    if len(parts) >= 2:
        return parts[1].lower()
    return node_id.lower()


def parse_node_id(node_id: str):
    """
    Parse a node ID into its components.

    Returns:
        (type, identifier, chain) tuple
    """
    parts = node_id.split(":")
    if len(parts) >= 3:
        return parts[0].lower(), parts[1].lower(), parts[2].lower()
    if len(parts) == 2:
        return parts[0].lower(), parts[1].lower(), "ethereum"
    return "wallet", node_id.lower(), "ethereum"
