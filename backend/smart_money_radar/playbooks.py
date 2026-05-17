"""
Smart Money Playbooks
=======================
Sprint 1.6: Combines signals + wallet strategies into actionable playbooks.

A Playbook = a cluster of wallets executing a similar strategy on the same token.
"""

from .signals_engine import get_signals
from .wallet_strategies import get_wallet_strategies
from .service import _fmt_usd, cache_get, cache_set
from collections import defaultdict


STRATEGY_TO_SIGNAL = {
    "early_accumulator": "accumulation",
    "momentum_trader": "momentum",
    "rotation_trader": "rotation",
    "distribution_wallet": "distribution",
}

PLAYBOOK_LABELS = {
    "accumulation": "Early Accumulation",
    "momentum": "Momentum Entry",
    "rotation": "Capital Rotation",
    "distribution": "Smart Distribution",
    "cluster_activity": "Cluster Activity",
    "exit": "Risk-Off Exit",
    "weakening": "Weakening Signal",
}


def get_playbooks(chain_id: int = 1, window: str = "24h", limit: int = 8) -> list:
    ck = f"playbooks:{chain_id}:{window}:{limit}"
    cached = cache_get(ck)
    if cached is not None:
        return cached

    signals = get_signals(chain_id=chain_id, window=window, limit=20)
    strategies = get_wallet_strategies(chain_id=chain_id, window=window, limit=50)

    # Group strategies by token + signal type
    strat_by_token = defaultdict(list)
    for s in strategies:
        for token in s.get("tokens", []):
            mapped_signal = STRATEGY_TO_SIGNAL.get(s["strategy"], s["strategy"])
            strat_by_token[(token, mapped_signal)].append(s)

    playbooks = []
    seen = set()

    for sig in signals:
        token = sig["token"]
        stype = sig["signal_type"]
        key = (token, stype)

        if key in seen:
            continue
        seen.add(key)

        # Find matching wallets
        matching_wallets = strat_by_token.get(key, [])

        # Also check broader matches (same token, any compatible strategy)
        for s in strategies:
            if token in s.get("tokens", []) and s not in matching_wallets:
                mapped = STRATEGY_TO_SIGNAL.get(s["strategy"], "")
                if mapped == stype or (stype in ("accumulation", "momentum") and s["strategy"] in ("early_accumulator", "momentum_trader")):
                    matching_wallets.append(s)

        # Deduplicate wallets
        unique_wallets = {}
        for w in matching_wallets:
            if w["wallet"] not in unique_wallets:
                unique_wallets[w["wallet"]] = w
        matching_wallets = list(unique_wallets.values())

        # Calculate playbook conviction (signal conviction + wallet cluster bonus)
        cluster_bonus = min(10, len(matching_wallets) * 3)
        playbook_conviction = min(99, sig["conviction"] + cluster_bonus)

        # Build playbook
        label = PLAYBOOK_LABELS.get(stype, stype.replace("_", " ").title())

        playbook = {
            "playbook_id": sig["signal_id"],
            "label": label,
            "token": token,
            "signal_type": stype,
            "conviction": playbook_conviction,
            "capital_usd": sig["capital_usd"],
            "capital_fmt": sig["capital_fmt"],
            "wallet_count": max(sig["wallet_count"], len(matching_wallets)),
            "drivers": sig["drivers"],
            "wallets": [
                {
                    "name": w["name"],
                    "strategy": w["strategy"],
                    "confidence": w["confidence"],
                }
                for w in matching_wallets[:5]
            ],
        }

        if stype == "rotation":
            playbook["from_token"] = sig.get("from_token", "")
            playbook["to_token"] = sig.get("to_token", "")

        playbooks.append(playbook)

    playbooks.sort(key=lambda p: p["conviction"], reverse=True)
    out = playbooks[:limit]
    cache_set(ck, out)
    return out
