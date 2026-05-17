"""
Smart Money Pattern Service
=============================
Sprint 1.3: Detects market phases from smart money behavior.

4 patterns:
  - ACCUMULATION: smart money buying, cluster buying, positive flow
  - DISTRIBUTION: smart money selling, cluster selling, negative flow
  - ROTATION: capital shifting from token A to token B
  - EXIT: capital moving to stablecoins / CEX (risk-off)
"""

from pymongo import DESCENDING
from collections import defaultdict
import math
from .service import _col, _timing_score, _fmt_usd, cache_get, cache_set

STABLECOINS = {"USDT", "USDC", "DAI", "BUSD", "TUSD", "FRAX", "LUSD", "GUSD", "USDP"}


def _pattern_confidence(net_flow: float, wallet_count: int, avg_timing: float, flow_ratio: float) -> int:
    """Pattern confidence 0-100."""
    flow_c = min(30, (math.log10(max(abs(net_flow), 1)) / 8) * 30)
    wallet_c = min(25, (wallet_count / 20) * 25)
    timing_c = min(25, max(0, (avg_timing + 10) / 25 * 25))
    ratio_c = min(20, flow_ratio * 20)
    return max(10, min(95, int(flow_c + wallet_c + timing_c + ratio_c)))


def get_patterns(chain_id: int = 1, window: str = "24h", limit: int = 10) -> list:
    """Detect smart money patterns from entity flows."""
    ck = f"patterns:{chain_id}:{window}:{limit}"
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

    # Get actor scores
    latest = scores_col.find_one({"chainId": chain_id, "window": window}, sort=[("bucketTs", DESCENDING)])
    bts = latest["bucketTs"] if latest else None
    scores_map = {}
    if bts:
        for s in scores_col.find({"chainId": chain_id, "window": window, "bucketTs": bts}, {"_id": 0}):
            scores_map[s.get("entityId", "")] = s

    # Aggregate per token
    token_agg = defaultdict(lambda: {
        "net_flow": 0, "buy_flow": 0, "sell_flow": 0,
        "buy_wallets": set(), "sell_wallets": set(),
        "all_wallets": set(), "total_trades": 0,
        "timing_scores": [], "edge_scores": [],
        "dex_flow": 0, "cex_flow": 0,
    })

    for entity in flows:
        eid = entity.get("entityId", "")
        sd = scores_map.get(eid, {})
        timing = _timing_score(entity)
        edge = sd.get("edgeScore", 30)

        for tk in entity.get("tokenBreakdown", [])[:5]:
            sym = tk.get("tokenSymbol", "")
            if not sym:
                continue
            net = tk.get("netUsd", 0)
            td = token_agg[sym]
            td["net_flow"] += net
            td["total_trades"] += entity.get("trades", 0)
            td["timing_scores"].append(timing)
            td["edge_scores"].append(edge)
            td["all_wallets"].add(eid)
            td["dex_flow"] += abs(entity.get("dexUsd", 0))
            td["cex_flow"] += abs(entity.get("cexUsd", 0))
            if net > 0:
                td["buy_flow"] += net
                td["buy_wallets"].add(eid)
            else:
                td["sell_flow"] += abs(net)
                td["sell_wallets"].add(eid)

    patterns = []

    # ── ACCUMULATION ──
    for sym, td in token_agg.items():
        if sym in STABLECOINS:
            continue
        if td["net_flow"] <= 50_000:
            continue
        buy_ratio = td["buy_flow"] / (td["buy_flow"] + td["sell_flow"] + 1)
        if buy_ratio < 0.6:
            continue

        avg_timing = sum(td["timing_scores"]) / max(len(td["timing_scores"]), 1)
        wallet_count = len(td["buy_wallets"])
        conf = _pattern_confidence(td["net_flow"], wallet_count, avg_timing, buy_ratio)

        drivers = []
        if wallet_count >= 5:
            drivers.append(f"cluster buying ({wallet_count} wallets)")
        elif wallet_count >= 2:
            drivers.append(f"multiple wallets accumulating ({wallet_count})")
        if td["net_flow"] >= 1_000_000:
            drivers.append(f"strong positive net flow (+{_fmt_usd(td['net_flow'])})")
        else:
            drivers.append(f"positive net flow (+{_fmt_usd(td['net_flow'])})")
        if avg_timing >= 5:
            drivers.append("favorable entry timing")
        if td["dex_flow"] > td["cex_flow"] * 1.5:
            drivers.append("DEX-concentrated buying")
        if buy_ratio >= 0.8:
            drivers.append("overwhelming buy-side dominance")

        patterns.append({
            "pattern_type": "accumulation",
            "token": sym,
            "net_flow_usd": round(td["net_flow"], 2),
            "confidence": conf,
            "wallet_count": wallet_count,
            "buy_ratio": round(buy_ratio, 2),
            "avg_timing": round(avg_timing, 1),
            "drivers": drivers[:5],
            "wallet_addresses": [w for w in list(td["buy_wallets"])[:15] if w.startswith("0x")],
        })

    # ── DISTRIBUTION ──
    for sym, td in token_agg.items():
        if sym in STABLECOINS:
            continue
        if td["net_flow"] >= -50_000:
            continue
        sell_ratio = td["sell_flow"] / (td["buy_flow"] + td["sell_flow"] + 1)
        if sell_ratio < 0.6:
            continue

        avg_timing = sum(td["timing_scores"]) / max(len(td["timing_scores"]), 1)
        wallet_count = len(td["sell_wallets"])
        conf = _pattern_confidence(abs(td["net_flow"]), wallet_count, avg_timing, sell_ratio)

        drivers = []
        if wallet_count >= 5:
            drivers.append(f"cluster selling ({wallet_count} wallets)")
        elif wallet_count >= 2:
            drivers.append(f"multiple wallets distributing ({wallet_count})")
        drivers.append(f"negative net flow ({_fmt_usd(td['net_flow'])})")
        if avg_timing >= 5:
            drivers.append("timed distribution")
        if td["cex_flow"] > td["dex_flow"] * 1.5:
            drivers.append("CEX-heavy selling (exchange deposits)")
        if sell_ratio >= 0.8:
            drivers.append("overwhelming sell-side pressure")

        patterns.append({
            "pattern_type": "distribution",
            "token": sym,
            "net_flow_usd": round(td["net_flow"], 2),
            "confidence": conf,
            "wallet_count": wallet_count,
            "buy_ratio": round(1 - sell_ratio, 2),
            "avg_timing": round(avg_timing, 1),
            "drivers": drivers[:5],
            "wallet_addresses": [w for w in list(td["sell_wallets"])[:15] if w.startswith("0x")],
        })

    # ── ROTATION ──
    accum_tokens = [p for p in patterns if p["pattern_type"] == "accumulation"]
    distrib_tokens = [p for p in patterns if p["pattern_type"] == "distribution"]

    for dist_p in distrib_tokens:
        for acc_p in accum_tokens:
            if dist_p["token"] == acc_p["token"]:
                continue
            # Check if wallets overlap
            dist_wallets = token_agg[dist_p["token"]]["sell_wallets"]
            acc_wallets = token_agg[acc_p["token"]]["buy_wallets"]
            overlap = dist_wallets & acc_wallets
            if len(overlap) < 1:
                continue

            rotation_volume = min(abs(dist_p["net_flow_usd"]), acc_p["net_flow_usd"])
            conf = min(dist_p["confidence"], acc_p["confidence"])
            # Boost confidence if there's wallet overlap
            overlap_bonus = min(15, len(overlap) * 5)
            conf = min(95, conf + overlap_bonus)

            drivers = [
                f"{dist_p['token']} outflow ({_fmt_usd(dist_p['net_flow_usd'])})",
                f"{acc_p['token']} inflow (+{_fmt_usd(acc_p['net_flow_usd'])})",
            ]
            if len(overlap) > 0:
                drivers.append(f"{len(overlap)} shared wallet(s) executing rotation")
            drivers.append("capital reallocation detected")

            patterns.append({
                "pattern_type": "rotation",
                "token": f"{dist_p['token']} -> {acc_p['token']}",
                "from_token": dist_p["token"],
                "to_token": acc_p["token"],
                "net_flow_usd": round(rotation_volume, 2),
                "confidence": conf,
                "wallet_count": len(overlap),
                "buy_ratio": 0.5,
                "avg_timing": round((dist_p["avg_timing"] + acc_p["avg_timing"]) / 2, 1),
                "drivers": drivers[:5],
                "wallet_addresses": [w for w in list(overlap)[:15] if w.startswith("0x")],
            })

    # ── EXIT ──
    stable_inflow = sum(token_agg[s]["net_flow"] for s in STABLECOINS if s in token_agg and token_agg[s]["net_flow"] > 0)
    total_cex_flow = sum(td["cex_flow"] for td in token_agg.values())
    total_dex_flow = sum(td["dex_flow"] for td in token_agg.values())
    total_sell = sum(td["sell_flow"] for sym, td in token_agg.items() if sym not in STABLECOINS)

    if stable_inflow > 100_000 or (total_cex_flow > total_dex_flow * 1.5 and total_sell > 500_000):
        exit_wallets = set()
        for s in STABLECOINS:
            if s in token_agg:
                exit_wallets.update(token_agg[s]["buy_wallets"])

        exit_volume = max(stable_inflow, total_sell * 0.3)
        conf = _pattern_confidence(exit_volume, len(exit_wallets), 5.0, 0.7)

        drivers = []
        if stable_inflow > 0:
            drivers.append(f"stablecoin inflow (+{_fmt_usd(stable_inflow)})")
        if total_cex_flow > total_dex_flow * 1.5:
            drivers.append("CEX deposits dominate (risk-off signal)")
        if total_sell > 1_000_000:
            drivers.append(f"aggregate selling pressure ({_fmt_usd(total_sell)})")
        drivers.append("capital moving to safety")

        patterns.append({
            "pattern_type": "exit",
            "token": "STABLECOINS",
            "net_flow_usd": round(exit_volume, 2),
            "confidence": conf,
            "wallet_count": len(exit_wallets),
            "buy_ratio": 0,
            "avg_timing": 5.0,
            "drivers": drivers[:5],
            "wallet_addresses": [w for w in list(exit_wallets)[:15] if w.startswith("0x")],
        })

    # Sort by confidence
    patterns.sort(key=lambda p: p["confidence"], reverse=True)
    result = patterns[:limit]
    cache_set(ck, result)
    return result
