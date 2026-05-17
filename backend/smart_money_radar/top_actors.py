"""
Smart Money Top Actors Service
================================
Sprint 1.5: Ranks wallets/entities by smart money influence.

Metrics:
  - smart_score: composite of edge, timing, flow
  - activity_score: trade frequency + token diversity
  - net_flow: USD net flow
  - cluster_count: how many token clusters this entity participates in
"""

from pymongo import DESCENDING
from collections import defaultdict
import math
from .service import _col, _timing_score, _clean, _time_ago, _fmt_usd, cache_get, cache_set
from mock_wallets import get_wallets_for_entity


def get_top_actors(chain_id: int = 1, window: str = "24h", limit: int = 10) -> list:
    ck = f"actors:{chain_id}:{window}:{limit}"
    cached = cache_get(ck)
    if cached is not None:
        return cached

    flows_col = _col("onchain_v2_entity_flows")
    scores_col = _col("onchainv2_actorscores")
    labels_col = _col("onchain_v2_address_labels")

    flows = list(
        flows_col.find({"chainId": chain_id, "window": window}, {"_id": 0})
        .sort("netUsd", DESCENDING)
        .limit(300)
    )

    # Actor scores
    latest = scores_col.find_one(
        {"chainId": chain_id, "window": window},
        sort=[("bucketTs", DESCENDING)],
    )
    bts = latest["bucketTs"] if latest else None
    scores_map = {}
    if bts:
        for s in scores_col.find({"chainId": chain_id, "window": window, "bucketTs": bts}, {"_id": 0}):
            scores_map[s.get("entityId", "")] = s

    # Labels for name resolution
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

    # Build per-entity profile
    actors = {}
    for entity in flows:
        eid = entity.get("entityId", "")
        if not eid:
            continue

        sd = scores_map.get(eid, {})
        edge = sd.get("edgeScore", 30)
        timing = _timing_score(entity)
        net_usd = entity.get("netUsd", 0) or entity.get("netAbsUsd", 0)
        trades = entity.get("trades", 0)
        tokens = entity.get("tokenBreakdown", [])

        # Token diversity
        token_syms = set()
        for tk in tokens[:10]:
            sym = tk.get("tokenSymbol", "")
            if sym:
                token_syms.add(sym)

        # Smart Score: edge + timing + flow magnitude
        flow_mag = min(abs(net_usd), 50_000_000)
        flow_component = min(30, (math.log10(max(flow_mag, 1)) / 8) * 30)
        edge_component = min(35, (edge / 100) * 35)
        timing_component = min(20, max(0, (timing + 10) / 25 * 20))
        diversity_bonus = min(15, len(token_syms) * 3)
        smart_score = int(min(99, max(5, edge_component + timing_component + flow_component + diversity_bonus)))

        # Activity Score: trades + token diversity
        trade_component = min(50, (min(trades, 100) / 100) * 50)
        diversity_component = min(30, len(token_syms) * 6)
        flow_activity = min(20, (math.log10(max(abs(net_usd), 1)) / 8) * 20)
        activity_score = int(min(99, max(5, trade_component + diversity_component + flow_activity)))

        resolved_name = resolve_name(eid)
        mock_addrs = get_wallets_for_entity(resolved_name, limit=3)
        # Use first mock address as the primary wallet if eid doesn't look like an address
        primary_wallet = mock_addrs[0] if mock_addrs and not eid.startswith("0x") else eid

        actors[eid] = {
            "wallet": primary_wallet,
            "name": resolved_name,
            "smart_score": smart_score,
            "activity_score": activity_score,
            "net_flow_usd": round(net_usd, 2),
            "net_flow_fmt": _fmt_usd(net_usd),
            "trades": trades,
            "token_count": len(token_syms),
            "tokens": sorted(list(token_syms))[:5],
            "edge_score": round(edge, 1),
            "timing_score": round(timing, 1),
            "last_activity": _time_ago(entity.get("lastSeen") or entity.get("updatedAt")),
            "wallet_addresses": mock_addrs,
        }

    # Sort by smart_score descending
    result = sorted(actors.values(), key=lambda a: a["smart_score"], reverse=True)
    out = result[:limit]
    cache_set(ck, out)
    return out
