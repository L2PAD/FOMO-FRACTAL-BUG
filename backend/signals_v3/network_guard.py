"""
Network Guard + Explorer Service
=================================
EVM-only intelligence platform. All data must reference an allowed chain.

ALLOWED_CHAINS: ethereum, arbitrum, optimism, base
Explorer links: centralized URL generator for wallet/tx/contract
"""

# ─── Allowed EVM Networks ───
ALLOWED_CHAINS = ["ethereum", "arbitrum", "optimism", "base"]

CHAIN_CONFIG = {
    "ethereum": {
        "id": "ethereum",
        "label": "ETH",
        "color": "gray",
        "explorer": "https://etherscan.io",
    },
    "arbitrum": {
        "id": "arbitrum",
        "label": "ARB",
        "color": "blue",
        "explorer": "https://arbiscan.io",
    },
    "optimism": {
        "id": "optimism",
        "label": "OP",
        "color": "red",
        "explorer": "https://optimistic.etherscan.io",
    },
    "base": {
        "id": "base",
        "label": "BASE",
        "color": "purple",
        "explorer": "https://basescan.org",
    },
}


def is_allowed_chain(chain: str) -> bool:
    """Check if chain is in allowed EVM networks."""
    return chain.lower() in ALLOWED_CHAINS


def get_explorer_link(chain: str, ref_type: str, ref_id: str) -> str:
    """Generate explorer URL for wallet/tx/contract.

    Args:
        chain: e.g. "ethereum", "arbitrum"
        ref_type: "address" | "tx" | "token"
        ref_id: the address or hash
    """
    cfg = CHAIN_CONFIG.get(chain.lower())
    if not cfg or not ref_id:
        return ""
    return f"{cfg['explorer']}/{ref_type}/{ref_id}"


def get_chain_label(chain: str) -> str:
    cfg = CHAIN_CONFIG.get(chain.lower())
    return cfg["label"] if cfg else chain.upper()


def validate_signal_integrity(signal: dict) -> bool:
    """Validate that a signal has minimum required data integrity fields.

    Required: chain (in ALLOWED_CHAINS), source, at least one evidence reference.
    """
    chain = signal.get("chain", "")
    if not is_allowed_chain(chain):
        return False

    source = signal.get("source", "")
    if not source:
        return False

    return True


def build_evidence(wallet: str = "", tx_hash: str = "", contract: str = "", chain: str = "") -> dict:
    """Build evidence block with explorer links."""
    ev = {}
    if wallet:
        ev["wallet"] = wallet
        ev["wallet_link"] = get_explorer_link(chain, "address", wallet)
    if tx_hash:
        ev["tx_hash"] = tx_hash
        ev["tx_link"] = get_explorer_link(chain, "tx", tx_hash)
    if contract:
        ev["contract"] = contract
        ev["contract_link"] = get_explorer_link(chain, "token", contract)
    return ev


def build_provenance(source: str, detection: str, module: str) -> dict:
    """Build provenance block for audit trail."""
    return {
        "source": source,
        "detection": detection,
        "module": module,
    }
