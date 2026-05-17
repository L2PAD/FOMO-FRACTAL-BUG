"""
Edge Engine — computes tradable edge between fair and implied probability.

edge = fair_prob - implied_prob - penalties
"""


def compute_edge(market: dict, probability: dict) -> dict:
    """
    Compute edge between model probability and market implied probability.

    Args:
        market: normalized market dict with yes_price, spread, liquidity
        probability: output from probability_engine.compute_probability()

    Returns:
        dict with implied_prob, fair_prob, raw_edge, net_edge, penalties
    """
    implied = market.get("yes_price", 0.5)
    fair = probability.get("fair_yes_prob", 0.5)

    raw_edge = fair - implied

    # Penalties
    spread = market.get("spread", 0)
    spread_penalty = spread * 0.5

    liquidity = market.get("liquidity", 0)
    liquidity_penalty = 0.02 if liquidity < 10000 else (0.01 if liquidity < 50000 else 0)

    net_edge = raw_edge - spread_penalty - liquidity_penalty

    return {
        "implied_prob": round(implied, 4),
        "fair_prob": round(fair, 4),
        "raw_edge": round(raw_edge, 4),
        "net_edge": round(net_edge, 4),
        "penalties": {
            "spread": round(spread_penalty, 4),
            "liquidity": round(liquidity_penalty, 4),
        },
    }
