"""
Smart Money Map Service
========================
Sprint 1.4: Capital route aggregation for Smart Money.

Shows where smart money capital flows:
  - Source → Intermediate → Destination routes
  - Route types: accumulation, distribution, rotation, exit
  - Destination heat: top tokens by smart inflow
  - Source heat: top entities by outflow
  - Flow summary: route counts by type
"""

from pymongo import DESCENDING
from collections import defaultdict
import math
from .service import _col, _clean, _fmt_usd, cache_get, cache_set
from mock_wallets import get_wallets_for_entity

STABLECOINS = {"USDT", "USDC", "DAI", "BUSD", "TUSD", "FRAX", "LUSD", "GUSD", "USDP"}


def get_map_data(chain_id: int = 1, window: str = "24h", limit: int = 15) -> dict:
    """Build the Smart Money capital flow map."""
    ck = f"map:{chain_id}:{window}:{limit}"
    cached = cache_get(ck)
    if cached is not None:
        return cached

    flows_col = _col("onchain_v2_entity_flows")
    scores_col = _col("onchainv2_actorscores")
    labels_col = _col("onchain_v2_address_labels")

    flows = list(
        flows_col.find({"chainId": chain_id, "window": window}, {"_id": 0})
        .sort("netUsd", DESCENDING)
        .limit(200)
    )

    # Labels for name resolution
    labels_map = {}
    for lbl in labels_col.find({"chainId": chain_id}, {"_id": 0}):
        a = lbl.get("address", "").lower()
        if a:
            labels_map[a] = lbl

    # Actor scores
    latest = scores_col.find_one({"chainId": chain_id, "window": window}, sort=[("bucketTs", DESCENDING)])
    bts = latest["bucketTs"] if latest else None
    scores_map = {}
    if bts:
        for s in scores_col.find({"chainId": chain_id, "window": window, "bucketTs": bts}, {"_id": 0}):
            scores_map[s.get("entityId", "")] = s

    def _resolve(eid):
        """Resolve entity name and type."""
        # Known entity ID patterns
        known_ids = {
            "unknown:address": ("Smart wallet cluster", "smart_money"),
            "dex:market": ("DEX Market", "dex"),
            "whale:unknown": ("Whale wallet", "whale"),
            "uniswap-router": ("Uniswap Router", "protocol"),
            "uniswap-router-v3": ("Uniswap V3 Router", "protocol"),
        }
        if eid in known_ids:
            return known_ids[eid]

        if eid.startswith("0x"):
            lbl = labels_map.get(eid.lower(), {})
            name = lbl.get("name", "")
            etype = lbl.get("type", "unknown")
            if name and name.lower() != "unknown":
                return _clean(name), etype

        sd = scores_map.get(eid, {})
        name = sd.get("entityName", "")
        etype = sd.get("entityType", "unknown")
        if name and name.lower() != "unknown":
            return _clean(name), etype

        # Fallback: capitalize the ID itself
        if not eid.startswith("0x") and ":" not in eid:
            return _clean(eid.replace("-", " ").title()), "exchange"

        t = etype.lower()
        if t in ("whale", "smart_money"):
            return "Smart wallet", t
        if t in ("protocol", "dex"):
            return "Protocol contract", t
        return "Active wallet", etype

    # ── Build routes ──
    routes = []
    destination_heat = defaultdict(float)
    source_heat = defaultdict(lambda: {"name": "", "type": "", "flow": 0})
    flow_summary = {"accumulation": 0, "distribution": 0, "rotation": 0, "exit": 0}

    for entity in flows:
        eid = entity.get("entityId", "")
        ename, etype = _resolve(eid)
        net = entity.get("netUsd", 0)
        sd = scores_map.get(eid, {})
        edge = sd.get("edgeScore", 30)
        tokens = entity.get("tokenBreakdown", [])

        for tk in tokens[:3]:
            sym = tk.get("tokenSymbol", "")
            tk_net = tk.get("netUsd", 0)
            if not sym or abs(tk_net) < 10_000:
                continue

            # Determine route type
            if sym in STABLECOINS and tk_net > 0:
                route_type = "exit"
            elif tk_net > 0:
                route_type = "accumulation"
            else:
                route_type = "distribution"

            # Determine protocol (intermediate)
            dex = abs(entity.get("dexUsd", 0))
            cex = abs(entity.get("cexUsd", 0))
            if dex > cex:
                protocol = "DEX"
            elif cex > dex:
                protocol = "CEX"
            else:
                protocol = "Direct"

            impact = min(100, int((math.log10(max(abs(tk_net), 1)) / 8) * 60 + (edge / 100) * 40))
            conf = min(95, max(20, int((edge / 100) * 40 + (min(abs(tk_net), 10_000_000) / 10_000_000) * 40 + 20)))

            routes.append({
                "route_type": route_type,
                "source_entity": ename,
                "source_type": etype,
                "source_wallet": eid if eid.startswith("0x") else "",
                "protocol": protocol,
                "token": sym,
                "volume_usd": round(abs(tk_net), 2),
                "net_flow_usd": round(tk_net, 2),
                "impact_score": impact,
                "confidence": conf,
                "wallet_addresses": get_wallets_for_entity(ename, limit=2),
            })

            # Aggregate heats
            if tk_net > 0 and sym not in STABLECOINS:
                destination_heat[sym] += tk_net
            elif tk_net < 0:
                destination_heat[sym] += tk_net

            sh = source_heat[ename]
            sh["name"] = ename
            sh["type"] = etype
            sh["flow"] += abs(tk_net)

            flow_summary[route_type] = flow_summary.get(route_type, 0) + 1

    # ── Detect rotation routes ──
    # Find entities that sell token A and buy token B
    entity_token_flows = defaultdict(lambda: defaultdict(float))
    for entity in flows:
        eid = entity.get("entityId", "")
        for tk in entity.get("tokenBreakdown", [])[:5]:
            sym = tk.get("tokenSymbol", "")
            tk_net = tk.get("netUsd", 0)
            if sym and abs(tk_net) > 50_000:
                entity_token_flows[eid][sym] += tk_net

    for eid, token_flows in entity_token_flows.items():
        sells = [(sym, net) for sym, net in token_flows.items() if net < -50_000 and sym not in STABLECOINS]
        buys = [(sym, net) for sym, net in token_flows.items() if net > 50_000 and sym not in STABLECOINS]
        for sell_sym, sell_net in sells:
            for buy_sym, buy_net in buys:
                if sell_sym == buy_sym:
                    continue
                ename, etype = _resolve(eid)
                vol = min(abs(sell_net), buy_net)
                routes.append({
                    "route_type": "rotation",
                    "source_entity": ename,
                    "source_type": etype,
                    "source_wallet": eid if eid.startswith("0x") else "",
                    "protocol": "DEX",
                    "token": f"{sell_sym} -> {buy_sym}",
                    "from_token": sell_sym,
                    "to_token": buy_sym,
                    "volume_usd": round(vol, 2),
                    "net_flow_usd": round(buy_net, 2),
                    "impact_score": min(100, int((math.log10(max(vol, 1)) / 8) * 70 + 20)),
                    "confidence": min(85, max(30, int(vol / 100_000))),
                    "wallet_addresses": get_wallets_for_entity(ename, limit=2),
                })
                flow_summary["rotation"] += 1

    # Sort routes by impact
    routes.sort(key=lambda r: r["impact_score"], reverse=True)

    # Build destination heat list
    dest_list = [{"token": sym, "net_flow_usd": round(net, 2)} for sym, net in sorted(destination_heat.items(), key=lambda x: abs(x[1]), reverse=True) if abs(net) > 10_000][:10]

    # Build source heat list
    src_list = [{"name": v["name"], "type": v["type"], "total_flow_usd": round(v["flow"], 2)} for v in sorted(source_heat.values(), key=lambda x: x["flow"], reverse=True)][:10]

    result = {
        "routes": routes[:limit],
        "destination_heat": dest_list,
        "source_heat": src_list,
        "flow_summary": flow_summary,
    }
    cache_set(ck, result)
    return result
