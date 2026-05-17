"""
Smart Money Brain Service
==========================
Sprint 1.3: Decision engine that aggregates all Smart Money signals
into a single Alpha Score per token.

Answers: Is smart money bullish or bearish on this asset?

Alpha Score = f(wallet_intelligence, timing, flow, cluster, pattern)
"""

from pymongo import DESCENDING
from collections import defaultdict
import math
from .service import _col, _timing_score, _fmt_usd, cache_get, cache_set


def _alpha_signal(score: float) -> str:
    if score >= 75:
        return "strong_bullish"
    if score >= 60:
        return "bullish"
    if score >= 40:
        return "neutral"
    if score >= 25:
        return "bearish"
    return "strong_bearish"


def get_brain_signals(chain_id: int = 1, window: str = "24h", limit: int = 10) -> list:
    """
    Compute Alpha Score per token based on all smart money signals.
    Integrates: wallet, timing, flow, cluster, and pattern intelligence.
    """
    ck = f"brain:{chain_id}:{window}:{limit}"
    cached = cache_get(ck)
    if cached is not None:
        return cached

    flows_col = _col("onchain_v2_entity_flows")
    scores_col = _col("onchainv2_actorscores")

    flows = list(
        flows_col.find({"chainId": chain_id, "window": window}, {"_id": 0})
        .sort("netUsd", DESCENDING)
        .limit(300)
    )

    latest_bucket = scores_col.find_one(
        {"chainId": chain_id, "window": window},
        sort=[("bucketTs", DESCENDING)],
    )
    bts = latest_bucket["bucketTs"] if latest_bucket else None
    scores_map = {}
    if bts:
        for s in scores_col.find({"chainId": chain_id, "window": window, "bucketTs": bts}, {"_id": 0}):
            scores_map[s.get("entityId", "")] = s

    # Get detected patterns for enrichment
    from .patterns import get_patterns
    detected_patterns = get_patterns(chain_id=chain_id, window=window, limit=20)
    pattern_map = {}
    for p in detected_patterns:
        tok = p.get("token", "")
        if tok and tok not in pattern_map:
            pattern_map[tok] = p

    # Aggregate per token
    token_data = defaultdict(lambda: {
        "net_flow": 0,
        "buy_flow": 0,
        "sell_flow": 0,
        "buy_count": 0,
        "sell_count": 0,
        "total_trades": 0,
        "timing_scores": [],
        "edge_scores": [],
        "wallets": set(),
        "dex_flow": 0,
        "cex_flow": 0,
    })

    for entity in flows:
        eid = entity.get("entityId", "")
        sd = scores_map.get(eid, {})
        edge = sd.get("edgeScore", 30)
        timing = _timing_score(entity)

        for tk in entity.get("tokenBreakdown", [])[:5]:
            sym = tk.get("tokenSymbol", "")
            if not sym:
                continue
            net = tk.get("netUsd", 0)
            td = token_data[sym]
            td["net_flow"] += net
            td["total_trades"] += entity.get("trades", 0)
            td["timing_scores"].append(timing)
            td["edge_scores"].append(edge)
            td["wallets"].add(eid)
            td["dex_flow"] += abs(entity.get("dexUsd", 0))
            td["cex_flow"] += abs(entity.get("cexUsd", 0))
            if net > 0:
                td["buy_flow"] += net
                td["buy_count"] += 1
            else:
                td["sell_flow"] += abs(net)
                td["sell_count"] += 1

    # Resolve entity IDs to wallet addresses from address labels
    labels_col = _col("onchain_v2_address_labels")
    all_entity_ids = set()
    for sym, td in token_data.items():
        all_entity_ids.update(td["wallets"])
    entity_to_addrs = {}
    if all_entity_ids:
        for doc in labels_col.find(
            {"chainId": chain_id, "entityId": {"$in": list(all_entity_ids)}},
            {"_id": 0, "entityId": 1, "address": 1}
        ).limit(500):
            eid = doc.get("entityId", "")
            addr = str(doc.get("address", "")).lower()
            if eid and addr:
                if eid not in entity_to_addrs:
                    entity_to_addrs[eid] = []
                if addr not in entity_to_addrs[eid] and len(entity_to_addrs[eid]) < 3:
                    entity_to_addrs[eid].append(addr)

    results = []
    for sym, td in token_data.items():
        if not td["timing_scores"] or abs(td["net_flow"]) < 10_000:
            continue

        # ── Component scores ──
        avg_edge = sum(td["edge_scores"]) / len(td["edge_scores"])
        avg_timing = sum(td["timing_scores"]) / len(td["timing_scores"])
        wallet_count = len(td["wallets"])

        # Wallet intelligence (0-25)
        wallet_score = min(25, (avg_edge / 100) * 25)

        # Timing intelligence (0-20)
        timing_score = min(20, max(0, (avg_timing + 10) / 25 * 20))

        # Flow intelligence (0-20) — directional
        net = td["net_flow"]
        flow_magnitude = min(abs(net), 50_000_000)
        flow_raw = (math.log10(max(flow_magnitude, 1)) / 8) * 20
        flow_direction = 1 if net > 0 else -1
        flow_score = flow_raw * flow_direction

        # Cluster intelligence (0-20)
        cluster_score = min(20, (wallet_count / 30) * 20)

        # Pattern intelligence (0-15) — from detected patterns + buy/sell ratio
        total_actors = td["buy_count"] + td["sell_count"]
        detected = pattern_map.get(sym)
        if detected:
            ptype = detected["pattern_type"]
            pconf = detected["confidence"] / 100
            if ptype == "accumulation":
                pattern_score = 15 * pconf
            elif ptype == "distribution":
                pattern_score = -15 * pconf
            elif ptype == "exit":
                pattern_score = -10 * pconf
            else:
                pattern_score = 0
        elif total_actors > 0:
            buy_ratio = td["buy_count"] / total_actors
            pattern_score = (buy_ratio - 0.5) * 30
        else:
            pattern_score = 0

        # ── Alpha Score (50 = neutral baseline) ──
        alpha_raw = 50 + wallet_score * 0.3 + timing_score * 0.2 + flow_score + cluster_score * 0.2 + pattern_score * 0.3
        alpha = max(0, min(100, int(alpha_raw)))
        signal = _alpha_signal(alpha)

        # ── Drivers ──
        drivers = []
        if net > 1_000_000:
            drivers.append(f"strong smart money inflow (+{_fmt_usd(net)})")
        elif net > 0:
            drivers.append(f"positive smart money flow (+{_fmt_usd(net)})")
        elif net < -1_000_000:
            drivers.append(f"smart money outflow ({_fmt_usd(net)})")
        elif net < 0:
            drivers.append(f"negative smart money flow ({_fmt_usd(net)})")

        if avg_timing >= 8:
            drivers.append("strong early entry timing")
        elif avg_timing >= 4:
            drivers.append("favorable wallet timing")

        if wallet_count >= 10:
            drivers.append(f"cluster activity ({wallet_count} wallets)")
        elif wallet_count >= 5:
            drivers.append(f"multiple wallets active ({wallet_count})")

        if td["buy_count"] > td["sell_count"] * 2:
            drivers.append("buy-side dominance")
        elif td["sell_count"] > td["buy_count"] * 2:
            drivers.append("sell-side dominance")

        if avg_edge >= 60:
            drivers.append("high-edge wallets involved")

        if td["dex_flow"] > td["cex_flow"] * 2:
            drivers.append("DEX-heavy activity")

        if detected:
            ptype = detected["pattern_type"]
            if ptype == "accumulation":
                drivers.append("accumulation pattern detected")
            elif ptype == "distribution":
                drivers.append("distribution pattern detected")
            elif ptype == "rotation":
                drivers.append("rotation pattern detected")
            elif ptype == "exit":
                drivers.append("exit pattern detected (risk-off)")

        # ── Resolve wallet addresses for this token ──
        token_wallets = []
        for eid in td["wallets"]:
            for addr in entity_to_addrs.get(eid, []):
                if addr not in token_wallets:
                    token_wallets.append(addr)
                if len(token_wallets) >= 5:
                    break
            if len(token_wallets) >= 5:
                break

        results.append({
            "token": sym,
            "alpha_score": alpha,
            "signal": signal,
            "pattern": detected["pattern_type"] if detected else None,
            "net_flow_usd": round(net, 2),
            "buy_flow_usd": round(td["buy_flow"], 2),
            "sell_flow_usd": round(td["sell_flow"], 2),
            "wallet_count": wallet_count,
            "avg_timing": round(avg_timing, 1),
            "avg_edge": round(avg_edge, 1),
            "drivers": drivers[:5],
            "wallet_addresses": token_wallets,
            "components": {
                "wallet": round(wallet_score, 1),
                "timing": round(timing_score, 1),
                "flow": round(flow_score, 1),
                "cluster": round(cluster_score, 1),
                "pattern": round(pattern_score, 1),
            },
        })

    results.sort(key=lambda r: abs(r["alpha_score"] - 50), reverse=True)
    result = results[:limit]
    cache_set(ck, result)
    return result
