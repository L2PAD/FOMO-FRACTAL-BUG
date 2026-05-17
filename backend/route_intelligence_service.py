"""
Route Intelligence Service (CEX Flow v2)
=========================================
Detects multi-hop liquidity routes from graph_relations.

Pipeline:
  raw edges → build adjacency → stitch hops into routes → classify →
  score → filter wash/internal → output top routes + flow state

Route stitching rules:
  - Time window: 20 min between hops (configurable)
  - Amount tolerance: ±15% (±20% for bridge hops)
  - Routes up to depth 5

Route types:
  cex_bridge_dex, cex_wallet_accumulate, cex_cex_transfer,
  cex_distribute, dex_cex_return, bridge_route, wallet_dex_exit

Wash detection:
  - Cycle detection (A→B→C→A)
  - Same-entity return
  - Rapid same-volume reversal
"""

import os
from collections import defaultdict
from datetime import timezone

ROUTE_WINDOW_SEC = 20 * 60       # 20 minutes
AMOUNT_TOLERANCE = 0.15          # ±15%
BRIDGE_AMOUNT_TOLERANCE = 0.20   # ±20% for bridge hops
MAX_ROUTE_DEPTH = 5
MIN_ROUTE_VOLUME = 0             # show all routes

# Node type classification for hop labelling
HOP_LABELS = {
    "cex": "CEX", "exchange": "CEX",
    "dex": "DEX", "bridge": "Bridge",
    "wallet": "Wallet", "contract": "Protocol",
    "protocol": "Protocol", "entity": "Entity",
    "cluster": "Wallet", "token": None,   # skip tokens
}

# Known route patterns → human-readable labels
ROUTE_PATTERNS = {
    ("CEX", "Wallet"):                       ("cex_wallet_accumulate", "CEX → Wallet accumulate"),
    ("CEX", "Wallet", "CEX"):                ("cex_cex_transfer",     "CEX → CEX transfer"),
    ("CEX", "Wallet", "DEX"):                ("cex_wallet_dex",       "CEX → Wallet → DEX"),
    ("CEX", "Wallet", "Bridge"):             ("cex_bridge",           "CEX → Bridge out"),
    ("CEX", "Wallet", "Bridge", "Wallet"):   ("cex_bridge_route",     "CEX → Bridge → Wallet"),
    ("CEX", "Wallet", "Bridge", "Wallet", "DEX"): ("cex_bridge_dex", "CEX → Bridge → DEX"),
    ("CEX", "Wallet", "Bridge", "Wallet", "CEX"): ("cex_bridge_cex", "CEX → Bridge → CEX"),
    ("DEX", "Wallet", "CEX"):                ("dex_cex_return",       "DEX → CEX return"),
    ("DEX", "Wallet", "Bridge"):             ("dex_bridge",           "DEX → Bridge out"),
    ("Wallet", "DEX"):                       ("wallet_dex_exit",      "Wallet → DEX exit"),
    ("Wallet", "CEX"):                       ("wallet_cex_return",    "Wallet → CEX return"),
    ("Wallet", "Bridge"):                    ("wallet_bridge",        "Wallet → Bridge"),
    ("Bridge", "Wallet"):                    ("bridge_wallet",        "Bridge → Wallet"),
    ("Bridge", "Wallet", "DEX"):             ("bridge_dex",           "Bridge → DEX"),
    ("Bridge", "Wallet", "CEX"):             ("bridge_cex",           "Bridge → CEX"),
}


def _hop_label(node_type):
    """Map node type to hop label."""
    return HOP_LABELS.get(node_type, "Wallet")


def _amounts_compatible(a1, a2, is_bridge=False):
    """Check if two amounts are within tolerance. Skip check if either is 0."""
    if a1 == 0 or a2 == 0:
        return True  # can't compare, allow
    tol = BRIDGE_AMOUNT_TOLERANCE if is_bridge else AMOUNT_TOLERANCE
    return abs(a2 - a1) / max(a1, 1) <= tol


def _timing_compatible(prev_last_seen, next_first_seen):
    """Check if two hops are within the time window."""
    if prev_last_seen == 0 or next_first_seen == 0:
        return True
    diff = next_first_seen - prev_last_seen
    return -ROUTE_WINDOW_SEC <= diff <= ROUTE_WINDOW_SEC * 3


def _classify_route(hop_types):
    """Classify a route by its hop type sequence."""
    key = tuple(hop_types)
    if key in ROUTE_PATTERNS:
        return ROUTE_PATTERNS[key]

    # Try prefix matching (longest first)
    for length in range(len(key), 1, -1):
        prefix = key[:length]
        if prefix in ROUTE_PATTERNS:
            return ROUTE_PATTERNS[prefix]

    # Fallback: generate label from hop types
    label = " → ".join(hop_types)
    # Determine type from start/end
    start, end = hop_types[0], hop_types[-1]
    has_bridge = "Bridge" in hop_types
    if has_bridge:
        route_type = "bridge_route"
    elif start == "CEX" and end == "CEX":
        route_type = "cex_cex_transfer"
    elif start == "CEX":
        route_type = "cex_outflow"
    elif end == "CEX":
        route_type = "return_to_cex"
    else:
        route_type = "other_route"
    return (route_type, label)


def _compute_wash_score(route):
    """Compute wash/fake routing score for a route."""
    hops = route.get("hops", [])
    entities = route.get("entities", [])
    hop_types = route.get("hop_types", [])

    score = 0.0

    # 1. Loop detection: start entity == end entity
    if len(entities) >= 2 and entities[0] == entities[-1]:
        score += 0.35

    # 2. Same entity return: start type == end type == CEX
    if len(hop_types) >= 2 and hop_types[0] == hop_types[-1] == "CEX":
        score += 0.30

    # 3. Rapid reversal: short route with similar amounts
    if len(hops) >= 2:
        first_amt = hops[0].get("amount", 0)
        last_amt = hops[-1].get("amount", 0)
        if first_amt > 0 and last_amt > 0:
            if abs(last_amt - first_amt) / max(first_amt, 1) < 0.05:
                score += 0.20

    # 4. Very short time span for round-trip
    start_time = route.get("start_time", 0)
    end_time = route.get("end_time", 0)
    if start_time > 0 and end_time > 0:
        duration = end_time - start_time
        if duration < 600 and len(hops) >= 3:  # < 10 min for 3+ hops
            score += 0.15

    return min(score, 1.0)


def _compute_route_score(route):
    """Score a route for importance."""
    volume = route.get("volume_usd", 0)
    hops = route.get("hops", [])
    hop_types = route.get("hop_types", [])

    # Volume score (log scale, max at $10M+)
    import math
    vol_score = min(1.0, math.log10(max(volume, 1)) / 7) if volume > 0 else 0

    # Continuity score: how many hops have compatible amounts
    continuity = 1.0
    if len(hops) >= 2:
        compatible = 0
        for i in range(len(hops) - 1):
            if _amounts_compatible(hops[i].get("amount", 0), hops[i + 1].get("amount", 0)):
                compatible += 1
        continuity = compatible / (len(hops) - 1)

    # Entity confidence: how many hops have known types (not plain wallet)
    known = sum(1 for t in hop_types if t in ("CEX", "DEX", "Bridge", "Protocol"))
    entity_conf = known / max(len(hop_types), 1)

    # Timing score: how well hops are time-connected
    timing = 1.0
    if len(hops) >= 2:
        timed = 0
        for i in range(len(hops) - 1):
            ls = hops[i].get("last_seen", 0)
            fs = hops[i + 1].get("first_seen", 0)
            if _timing_compatible(ls, fs):
                timed += 1
        timing = timed / (len(hops) - 1)

    return round(
        vol_score * 0.35 +
        continuity * 0.25 +
        entity_conf * 0.20 +
        timing * 0.20,
        3
    )


def _detect_fan_patterns(adjacency, node_types_map):
    """Detect fan-out (1→N) and fan-in (N→1) patterns."""
    fan_outs = []
    fan_ins = defaultdict(lambda: {"sources": [], "total_amount": 0, "tx_count": 0})

    for src, targets in adjacency.items():
        if len(targets) >= 4:
            total_out = sum(e["amount"] for e in targets)
            fan_outs.append({
                "node": src,
                "label": node_types_map.get(src, {}).get("label", src[:20]),
                "target_count": len(targets),
                "total_amount": total_out,
                "type": "fan_out",
            })
        for edge in targets:
            tgt = edge["target"]
            fan_ins[tgt]["sources"].append(src)
            fan_ins[tgt]["total_amount"] += edge["amount"]
            fan_ins[tgt]["tx_count"] += edge.get("tx_count", 0)

    fan_in_list = []
    for node, info in fan_ins.items():
        if len(info["sources"]) >= 4:
            fan_in_list.append({
                "node": node,
                "label": node_types_map.get(node, {}).get("label", node[:20]),
                "source_count": len(info["sources"]),
                "total_amount": info["total_amount"],
                "type": "fan_in",
            })

    return fan_outs, fan_in_list


async def build_route_intelligence(db):
    """Main pipeline: build routes from graph_relations."""

    # 1. Load node types
    node_types_map = {}
    cursor = db["graph_nodes"].find({}, {"_id": 0, "id": 1, "type": 1, "label": 1})
    async for n in cursor:
        node_types_map[n["id"]] = {
            "type": n.get("type", "wallet"),
            "label": n.get("label", ""),
        }

    # 2. Load all relations into adjacency list
    adjacency = defaultdict(list)  # src → [{target, amount, tx_count, first_seen, last_seen, chain}]
    all_edges = []

    rel_cursor = db["graph_relations"].find({}, {"_id": 0})
    async for rel in rel_cursor:
        src = rel.get("source_id", "")
        tgt = rel.get("target_id", "")
        src_type = node_types_map.get(src, {}).get("type", "wallet")
        tgt_type = node_types_map.get(tgt, {}).get("type", "wallet")

        # Skip token nodes
        if src_type == "token" or tgt_type == "token":
            continue

        edge = {
            "source": src,
            "target": tgt,
            "amount": rel.get("total_amount_usd", 0) or 0,
            "tx_count": rel.get("total_tx_count", rel.get("tx_count", 0)) or 0,
            "first_seen": rel.get("first_seen", 0) or 0,
            "last_seen": rel.get("last_seen", 0) or 0,
            "chain": rel.get("chain", ""),
            "src_type": src_type,
            "tgt_type": tgt_type,
        }
        adjacency[src].append(edge)
        all_edges.append(edge)

    # 3. Route stitching via DFS from meaningful source nodes (CEX, Bridge, DEX)
    START_TYPES = {"cex", "exchange", "bridge", "dex", "cluster"}
    routes = []
    visited_paths = set()
    MAX_ROUTES = 5000  # Safety cap

    for start_node, info in node_types_map.items():
        if info["type"] not in START_TYPES:
            continue
        if start_node not in adjacency:
            continue
        if len(routes) >= MAX_ROUTES:
            break

        # DFS from this node — limit fan-out per node
        stack = [(start_node, [start_node], [], 0)]

        while stack and len(routes) < MAX_ROUTES:
            current, path, hops, depth = stack.pop()
            if depth >= MAX_ROUTE_DEPTH:
                continue

            # Limit edges explored per node to top by weight (amount or tx_count)
            edges = adjacency.get(current, [])
            edges_sorted = sorted(edges, key=lambda e: e.get("amount", 0) or e.get("tx_count", 0), reverse=True)[:20]

            for edge in edges_sorted:
                next_node = edge["target"]
                next_type = node_types_map.get(next_node, {}).get("type", "wallet")

                if next_type == "token":
                    continue
                if next_node in path:
                    continue

                # No strict timing/amount filter for aggregated data
                # (timing used only for scoring, not filtering)

                new_hops = hops + [edge]
                new_path = path + [next_node]

                # Register route if 2+ hops
                next_label = _hop_label(next_type)
                if next_label and len(new_hops) >= 2:
                    hop_type_seq = [_hop_label(node_types_map.get(p, {}).get("type", "wallet")) for p in new_path]
                    hop_type_seq = [h for h in hop_type_seq if h]

                    path_key = "→".join(new_path)
                    if path_key not in visited_paths:
                        visited_paths.add(path_key)

                        route_type, route_label = _classify_route(hop_type_seq)
                        # Use amount if available, else tx_count as proxy
                        volumes = [e["amount"] for e in new_hops if e["amount"] > 0]
                        volume = max(volumes) if volumes else 0
                        tx_total = sum(e["tx_count"] for e in new_hops)
                        chains = list(set(e["chain"] for e in new_hops if e["chain"]))
                        entities = [node_types_map.get(p, {}).get("label", p[:20]) for p in new_path]

                        route = {
                            "route_type": route_type,
                            "label": route_label,
                            "hop_types": hop_type_seq,
                            "entities": entities,
                            "chains": chains,
                            "volume_usd": round(volume, 2),
                            "tx_count": tx_total,
                            "start_time": new_hops[0].get("first_seen", 0),
                            "end_time": new_hops[-1].get("last_seen", 0),
                            "hops": new_hops,
                            "depth": len(new_hops),
                        }
                        route["confidence"] = _compute_route_score(route)
                        route["wash_score"] = _compute_wash_score(route)
                        routes.append(route)

                if depth + 1 < MAX_ROUTE_DEPTH:
                    stack.append((next_node, new_path, new_hops, depth + 1))

    # 4. Aggregate routes by type (keep best sample for each type)
    route_agg = defaultdict(lambda: {"volume_usd": 0, "tx_count": 0, "count": 0, "label": "", "avg_confidence": 0, "avg_wash": 0, "best_sample": None, "best_score": -1})
    for r in routes:
        rt = r["route_type"]
        route_agg[rt]["volume_usd"] += r["volume_usd"]
        route_agg[rt]["tx_count"] += r["tx_count"]
        route_agg[rt]["count"] += 1
        route_agg[rt]["label"] = r["label"]
        route_agg[rt]["avg_confidence"] += r["confidence"]
        route_agg[rt]["avg_wash"] += r["wash_score"]
        if r["confidence"] > route_agg[rt]["best_score"]:
            route_agg[rt]["best_score"] = r["confidence"]
            hops = r.get("hops", [])
            if hops:
                path_ids = [hops[0]["source"]] + [h["target"] for h in hops]
                route_agg[rt]["best_sample"] = path_ids

    for rt in route_agg:
        c = route_agg[rt]["count"]
        if c > 0:
            route_agg[rt]["avg_confidence"] = round(route_agg[rt]["avg_confidence"] / c, 3)
            route_agg[rt]["avg_wash"] = round(route_agg[rt]["avg_wash"] / c, 3)

    # Sort by volume, then by tx_count as fallback
    top_routes = sorted(
        [
            {
                "type": rt,
                "label": data["label"],
                "volume_usd": round(data["volume_usd"], 2),
                "tx_count": data["tx_count"],
                "route_count": data["count"],
                "confidence": data["avg_confidence"],
                "wash_score": data["avg_wash"],
                "sample_path": data.get("best_sample", []),
            }
            for rt, data in route_agg.items()
        ],
        key=lambda x: (x["volume_usd"], x["tx_count"]),
        reverse=True,
    )

    # 5. Fan patterns
    fan_outs, fan_ins = _detect_fan_patterns(adjacency, node_types_map)

    # 6. Compute enhanced flow state
    total_inflow = sum(e["amount"] for e in all_edges if node_types_map.get(e["target"], {}).get("type") in ("wallet", "cluster"))
    total_outflow = sum(e["amount"] for e in all_edges if node_types_map.get(e["source"], {}).get("type") in ("wallet", "cluster"))

    # Count route types for state determination
    bridge_vol = sum(r["volume_usd"] for r in top_routes if "bridge" in r["type"])
    cex_return_vol = sum(r["volume_usd"] for r in top_routes if "return" in r["type"] or "cex_cex" in r["type"])
    dex_exit_vol = sum(r["volume_usd"] for r in top_routes if "dex" in r["type"] and "cex" not in r["type"])
    accumulate_vol = sum(r["volume_usd"] for r in top_routes if "accumulate" in r["type"])
    distribute_vol = sum(len(f["target_count"] if isinstance(f["target_count"], list) else [f["target_count"]]) for f in fan_outs) if fan_outs else 0

    total_route_vol = sum(r["volume_usd"] for r in top_routes) or 1

    # Check for ROUTING pattern first (pass-through: balanced in/out)
    net = total_inflow - total_outflow
    if total_inflow > 0 and total_outflow > 0:
        ratio = min(total_inflow, total_outflow) / max(total_inflow, total_outflow)
        if ratio > 0.85:
            flow_state = "ROUTING"
            flow_driver = "cross-chain" if bridge_vol / total_route_vol > 0.2 else "pass-through"
        elif net >= 0:
            flow_state = "ACCUMULATION"
            cex_vol = sum(r["volume_usd"] for r in top_routes if r["type"].startswith("cex"))
            dex_vol = sum(r["volume_usd"] for r in top_routes if r["type"].startswith("dex"))
            bridge_v = sum(r["volume_usd"] for r in top_routes if r["type"].startswith("bridge"))
            dominant = max([("CEX", cex_vol), ("DEX", dex_vol), ("Bridge", bridge_v)], key=lambda x: x[1])
            flow_driver = f"{dominant[0]}-driven"
        else:
            flow_state = "DISTRIBUTION"
            if dex_exit_vol / total_route_vol > 0.3:
                flow_driver = "DEX exit"
            elif len(fan_outs) > 3:
                flow_driver = "fan-out"
            else:
                flow_driver = "outflow"
    elif net >= 0:
        flow_state = "ACCUMULATION"
        cex_vol = sum(r["volume_usd"] for r in top_routes if r["type"].startswith("cex"))
        flow_driver = "CEX-driven" if cex_vol / total_route_vol > 0.3 else "inflow"
    else:
        flow_state = "DISTRIBUTION"
        flow_driver = "outflow"

    # 7. Wash routes summary
    wash_routes = [r for r in routes if r["wash_score"] > 0.5]
    wash_volume = sum(r["volume_usd"] for r in wash_routes)

    return {
        "top_routes": top_routes[:15],
        "flow_state": flow_state,
        "flow_driver": flow_driver,
        "route_count": len(routes),
        "wash_volume_usd": round(wash_volume, 2),
        "wash_route_count": len(wash_routes),
        "fan_out_count": len(fan_outs),
        "fan_in_count": len(fan_ins),
        "fan_outs": sorted(fan_outs, key=lambda x: x["total_amount"], reverse=True)[:5],
        "fan_ins": sorted(fan_ins, key=lambda x: x["total_amount"], reverse=True)[:5],
    }



async def build_entity_route_intelligence(db, entity_id, depth=2, limit=150):
    """Build route intelligence for a specific entity's subgraph.

    This fetches the same subgraph as the render endpoint, then runs
    route stitching on THOSE edges — so routes match what's on screen.
    """
    from graph_projection_service import project_graph

    # 1. Load node types
    node_types_map = {}
    cursor = db["graph_nodes"].find({}, {"_id": 0, "id": 1, "type": 1, "label": 1})
    async for n in cursor:
        node_types_map[n["id"]] = {
            "type": n.get("type", "wallet"),
            "label": n.get("label", ""),
        }

    # 2. Get subgraph via project_graph (same as render endpoint)
    try:
        result = await project_graph(
            db, center_node_id=entity_id,
            depth=depth, max_nodes=limit, max_edges=limit * 4,
        )
        raw_nodes = result.get("nodes", [])
        raw_edges = result.get("edges", [])
    except Exception:
        raw_nodes, raw_edges = [], []

    if not raw_edges:
        return _empty_result()

    # 3. Build adjacency from subgraph edges
    adjacency = defaultdict(list)
    all_edges = []
    node_ids = {n.get("id", n.get("node_id", "")) for n in raw_nodes}

    for edge in raw_edges:
        src = edge.get("source", edge.get("source_id", ""))
        tgt = edge.get("target", edge.get("target_id", ""))
        src_type = node_types_map.get(src, {}).get("type", "wallet")
        tgt_type = node_types_map.get(tgt, {}).get("type", "wallet")

        if src_type == "token" or tgt_type == "token":
            continue

        e = {
            "source": src,
            "target": tgt,
            "amount": edge.get("amountUsd", edge.get("weight", edge.get("total_amount_usd", 0))) or 0,
            "tx_count": edge.get("txCount", edge.get("tx_count", edge.get("total_tx_count", 0))) or 0,
            "first_seen": edge.get("first_seen", 0) or 0,
            "last_seen": edge.get("last_seen", 0) or 0,
            "chain": edge.get("chain", ""),
        }
        adjacency[src].append(e)
        all_edges.append(e)

    # 4. DFS route stitching (same logic as global, but on subgraph)
    START_TYPES = {"cex", "exchange", "bridge", "dex", "cluster"}
    routes = []
    visited_paths = set()

    for start_node in node_ids:
        info = node_types_map.get(start_node, {})
        if info.get("type", "wallet") not in START_TYPES:
            continue
        if start_node not in adjacency:
            continue

        stack = [(start_node, [start_node], [], 0)]
        while stack and len(routes) < 2000:
            current, path, hops, depth_i = stack.pop()
            if depth_i >= MAX_ROUTE_DEPTH:
                continue

            edges_sorted = sorted(
                adjacency.get(current, []),
                key=lambda x: x.get("amount", 0) or x.get("tx_count", 0),
                reverse=True,
            )[:20]

            for edge in edges_sorted:
                next_node = edge["target"]
                next_type = node_types_map.get(next_node, {}).get("type", "wallet")
                if _hop_label(next_type) is None:
                    continue
                if next_node in path:
                    continue

                new_hops = hops + [edge]
                new_path = path + [next_node]

                if len(new_hops) >= 2:
                    hop_type_seq = [
                        _hop_label(node_types_map.get(p, {}).get("type", "wallet")) or "Wallet"
                        for p in new_path
                    ]
                    path_key = "→".join(new_path)
                    if path_key not in visited_paths:
                        visited_paths.add(path_key)
                        route_type, route_label = _classify_route(hop_type_seq)
                        volumes = [e["amount"] for e in new_hops if e["amount"] > 0]
                        volume = max(volumes) if volumes else 0
                        tx_total = sum(e["tx_count"] for e in new_hops)
                        entities = [
                            node_types_map.get(p, {}).get("label", p[:20]) for p in new_path
                        ]
                        route = {
                            "route_type": route_type,
                            "label": route_label,
                            "hop_types": hop_type_seq,
                            "entities": entities,
                            "chains": list(set(e["chain"] for e in new_hops if e["chain"])),
                            "volume_usd": round(volume, 2),
                            "tx_count": tx_total,
                            "start_time": new_hops[0].get("first_seen", 0),
                            "end_time": new_hops[-1].get("last_seen", 0),
                            "hops": new_hops,
                            "depth": len(new_hops),
                        }
                        route["confidence"] = _compute_route_score(route)
                        route["wash_score"] = _compute_wash_score(route)
                        routes.append(route)

                if depth_i + 1 < MAX_ROUTE_DEPTH:
                    stack.append((next_node, new_path, new_hops, depth_i + 1))

    # 5. Aggregate routes (keep best sample for each type)
    route_agg = defaultdict(lambda: {"volume_usd": 0, "tx_count": 0, "count": 0, "label": "", "avg_confidence": 0, "avg_wash": 0, "best_sample": None, "best_score": -1})
    for r in routes:
        rt = r["route_type"]
        route_agg[rt]["volume_usd"] += r["volume_usd"]
        route_agg[rt]["tx_count"] += r["tx_count"]
        route_agg[rt]["count"] += 1
        route_agg[rt]["label"] = r["label"]
        route_agg[rt]["avg_confidence"] += r["confidence"]
        route_agg[rt]["avg_wash"] += r["wash_score"]
        # Keep the route with highest confidence as sample
        if r["confidence"] > route_agg[rt]["best_score"]:
            route_agg[rt]["best_score"] = r["confidence"]
            hops = r.get("hops", [])
            # Build sample_path from hops: [source of first hop] + [target of each hop]
            if hops:
                path_ids = [hops[0]["source"]] + [h["target"] for h in hops]
                route_agg[rt]["best_sample"] = path_ids

    for rt in route_agg:
        c = route_agg[rt]["count"]
        if c > 0:
            route_agg[rt]["avg_confidence"] = round(route_agg[rt]["avg_confidence"] / c, 3)
            route_agg[rt]["avg_wash"] = round(route_agg[rt]["avg_wash"] / c, 3)

    top_routes = sorted(
        [
            {"type": rt, "label": d["label"], "volume_usd": round(d["volume_usd"], 2),
             "tx_count": d["tx_count"], "route_count": d["count"],
             "confidence": d["avg_confidence"], "wash_score": d["avg_wash"],
             "sample_path": d.get("best_sample", [])}
            for rt, d in route_agg.items()
        ],
        key=lambda x: (x["volume_usd"], x["tx_count"]),
        reverse=True,
    )

    # 6. Fan patterns
    fan_outs, fan_ins = _detect_fan_patterns(adjacency, node_types_map)

    # 7. Flow state from routes
    total_inflow = sum(e["amount"] for e in all_edges if e["target"] == entity_id or node_types_map.get(e["target"], {}).get("type") in ("wallet", "cluster"))
    total_outflow = sum(e["amount"] for e in all_edges if e["source"] == entity_id or node_types_map.get(e["source"], {}).get("type") in ("wallet", "cluster"))
    total_route_vol = sum(r["volume_usd"] for r in top_routes) or 1

    bridge_vol = sum(r["volume_usd"] for r in top_routes if "bridge" in r["type"])
    net = total_inflow - total_outflow

    # Check for ROUTING first (balanced in/out = pass-through)
    if total_inflow > 0 and total_outflow > 0:
        ratio = min(total_inflow, total_outflow) / max(total_inflow, total_outflow)
        if ratio > 0.85:
            flow_state = "ROUTING"
            flow_driver = "cross-chain" if bridge_vol / total_route_vol > 0.2 else "pass-through"
        elif net >= 0:
            flow_state = "ACCUMULATION"
            cex_vol = sum(r["volume_usd"] for r in top_routes if r["type"].startswith("cex"))
            flow_driver = "CEX-driven" if cex_vol / total_route_vol > 0.3 else "inflow"
        else:
            flow_state = "DISTRIBUTION"
            dex_vol = sum(r["volume_usd"] for r in top_routes if "dex" in r["type"])
            if len(fan_outs) > 3:
                flow_driver = "fan-out"
            elif dex_vol / total_route_vol > 0.3:
                flow_driver = "DEX exit"
            else:
                flow_driver = "outflow"
    elif net >= 0:
        flow_state = "ACCUMULATION"
        cex_vol = sum(r["volume_usd"] for r in top_routes if r["type"].startswith("cex"))
        flow_driver = "CEX-driven" if cex_vol / total_route_vol > 0.3 else "inflow"
    else:
        flow_state = "DISTRIBUTION"
        flow_driver = "outflow"

    wash_routes = [r for r in routes if r["wash_score"] > 0.5]

    return {
        "top_routes": top_routes[:15],
        "flow_state": flow_state,
        "flow_driver": flow_driver,
        "route_count": len(routes),
        "wash_volume_usd": round(sum(r["volume_usd"] for r in wash_routes), 2),
        "wash_route_count": len(wash_routes),
        "fan_out_count": len(fan_outs),
        "fan_in_count": len(fan_ins),
        "edges_in_subgraph": len(all_edges),
        "nodes_in_subgraph": len(node_ids),
    }


def _empty_result():
    return {
        "top_routes": [],
        "flow_state": "ACCUMULATION",
        "flow_driver": "unknown",
        "route_count": 0,
        "wash_volume_usd": 0,
        "wash_route_count": 0,
        "fan_out_count": 0,
        "fan_in_count": 0,
        "edges_in_subgraph": 0,
        "nodes_in_subgraph": 0,
    }
