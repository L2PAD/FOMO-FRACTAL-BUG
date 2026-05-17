"""
Wallet Strategy Detection
===========================
Sprint 1.6: Classifies wallet behavior into strategy types.

Strategies:
  - early_accumulator: buys before trend, holds, buys in parts
  - momentum_trader: enters during trend, trades frequently
  - rotation_trader: rotates capital between assets
  - distribution_wallet: sells on highs, reduces exposure
  - liquidity_provider: interacts with pools, provides liquidity
"""

from pymongo import DESCENDING
from collections import defaultdict
import math
from .service import _col, _timing_score, _clean, _time_ago, cache_get, cache_set


def _classify_strategy(entity: dict, token_breakdown: list, timing: float) -> dict:
    """Classify a wallet's strategy based on its behavior profile."""
    net_usd = entity.get("netUsd", 0) or 0
    trades = entity.get("trades", 0) or 0
    tokens = token_breakdown or []
    token_count = len(tokens)

    # Analyze token distribution
    has_positive = any(t.get("netUsd", 0) > 0 for t in tokens)
    has_negative = any(t.get("netUsd", 0) < 0 for t in tokens)
    max_token_flow = max((abs(t.get("netUsd", 0)) for t in tokens), default=0)
    total_abs_flow = sum(abs(t.get("netUsd", 0)) for t in tokens)

    # Concentration: how focused is the wallet on few tokens
    concentration = max_token_flow / total_abs_flow if total_abs_flow > 0 else 0

    # Detect rotation: buying some, selling others
    buy_tokens = [t for t in tokens if t.get("netUsd", 0) > 0]
    sell_tokens = [t for t in tokens if t.get("netUsd", 0) < 0]
    is_rotating = len(buy_tokens) >= 1 and len(sell_tokens) >= 1

    # --- Strategy Classification ---

    # Rotation Trader: buying some tokens, selling others
    if is_rotating and len(buy_tokens) >= 1 and len(sell_tokens) >= 1:
        buy_vol = sum(t.get("netUsd", 0) for t in buy_tokens)
        sell_vol = abs(sum(t.get("netUsd", 0) for t in sell_tokens))
        if sell_vol > 0 and buy_vol / sell_vol > 0.3:
            confidence = min(90, 50 + int(min(len(buy_tokens), 3) * 10 + min(len(sell_tokens), 3) * 5))
            return {
                "strategy": "rotation_trader",
                "confidence": confidence,
                "detail": f"rotating from {len(sell_tokens)} to {len(buy_tokens)} tokens",
            }

    # Early Accumulator: positive flow, early timing, moderate trades
    if net_usd > 0 and timing >= 3 and concentration >= 0.4:
        confidence = min(90, 40 + int(timing * 3 + concentration * 20))
        return {
            "strategy": "early_accumulator",
            "confidence": confidence,
            "detail": f"early entry with timing +{timing:.0f}",
        }

    # Momentum Trader: positive flow, high trade frequency, lower timing
    if net_usd > 0 and trades >= 10 and timing < 3:
        confidence = min(85, 40 + int(min(trades, 50) * 0.5 + 20))
        return {
            "strategy": "momentum_trader",
            "confidence": confidence,
            "detail": f"{trades} trades, momentum entry",
        }

    # Distribution Wallet: negative flow, selling concentrated
    if net_usd < 0 and concentration >= 0.3:
        confidence = min(85, 45 + int(concentration * 30))
        return {
            "strategy": "distribution_wallet",
            "confidence": confidence,
            "detail": f"reducing exposure, net outflow",
        }

    # Default: active trader
    if trades >= 5:
        return {
            "strategy": "active_trader",
            "confidence": 40,
            "detail": f"{trades} trades across {token_count} tokens",
        }

    return {
        "strategy": "passive",
        "confidence": 30,
        "detail": "limited activity",
    }


def get_wallet_strategies(chain_id: int = 1, window: str = "24h", limit: int = 15) -> list:
    ck = f"wstrat:{chain_id}:{window}:{limit}"
    cached = cache_get(ck)
    if cached is not None:
        return cached

    flows_col = _col("onchain_v2_entity_flows")
    labels_col = _col("onchain_v2_address_labels")

    flows = list(
        flows_col.find({"chainId": chain_id, "window": window}, {"_id": 0})
        .sort("netUsd", DESCENDING)
        .limit(200)
    )

    labels_map = {}
    for lbl in labels_col.find({"chainId": chain_id}, {"_id": 0}):
        a = lbl.get("address", "").lower()
        if a:
            labels_map[a] = lbl

    def resolve_name(entity_id: str) -> str:
        if ":" in entity_id:
            parts = entity_id.split(":")
            addr = parts[1] if len(parts) > 1 else ""
            if addr.startswith("0x") and addr.lower() in labels_map:
                lbl = labels_map[addr.lower()]
                return lbl.get("label", lbl.get("name", entity_id))
        for lbl in labels_map.values():
            if lbl.get("entityId") == entity_id:
                return lbl.get("label", lbl.get("name", entity_id))
        name = entity_id.replace("_", " ").replace(":", " ")
        if name.startswith("unknown ") and len(name) > 20:
            addr = name.split(" ")[-1]
            return f"{addr[:6]}...{addr[-4:]}" if len(addr) > 10 else name
        return name

    results = []
    for entity in flows:
        eid = entity.get("entityId", "")
        if not eid:
            continue

        tokens = entity.get("tokenBreakdown", [])
        timing = _timing_score(entity)
        strat = _classify_strategy(entity, tokens, timing)

        if strat["strategy"] == "passive":
            continue

        net_usd = entity.get("netUsd", 0) or 0
        trades = entity.get("trades", 0)

        # Top tokens for this wallet
        top_tokens = sorted(tokens, key=lambda t: abs(t.get("netUsd", 0)), reverse=True)[:3]
        token_names = [t.get("tokenSymbol", "?") for t in top_tokens if t.get("tokenSymbol")]

        results.append({
            "wallet": eid,
            "name": resolve_name(eid),
            "strategy": strat["strategy"],
            "confidence": strat["confidence"],
            "detail": strat["detail"],
            "net_flow_usd": round(net_usd, 2),
            "trades": trades,
            "tokens": token_names,
            "timing_score": round(timing, 1),
            "last_activity": _time_ago(entity.get("lastSeen") or entity.get("updatedAt")),
        })

    results.sort(key=lambda r: r["confidence"], reverse=True)
    out = results[:limit]
    cache_set(ck, out)
    return out
