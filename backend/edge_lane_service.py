"""
Edge Lane Service — Arkham-style multi-edge renderer
=====================================================
Converts raw relations into multiple render edges per node pair.

KEY RULE: Between two nodes there can be N edges, each drawn separately.
No grouping into one line. MAX_LANES_PER_PAIR=19.

Pipeline:
  raw relations → split into directional sub-edges → group by pair → limit 19 → assign lane geometry
"""

from collections import defaultdict

MAX_LANES_PER_PAIR = 19
MAX_VISIBLE_EDGES = 900

COLOR_INCOMING = "#34D399"   # green
COLOR_OUTGOING = "#EF4444"   # красный
COLOR_NEUTRAL  = "#EF4444"   # нет нейтрального, всё либо зелёное либо красное

STABLECOINS = {"usdc", "usdt", "dai", "busd", "tusd", "frax", "lusd", "gusd", "usdp"}
MAJORS = {"eth", "weth", "btc", "wbtc", "steth", "reth", "cbeth", "sol", "link", "uni", "aave"}


def classify_token_group(token):
    if not token:
        return "OTHER"
    t = token.lower().strip()
    if t in STABLECOINS:
        return "STABLE"
    if t in MAJORS:
        return t.upper()
    return "OTHER"


def classify_flow_type(relation_type, tags=None):
    rt = (relation_type or "transfer").lower()
    if rt in ("swap", "dex_swap"):
        return "swap"
    if rt in ("deposit", "cex_deposit"):
        return "deposit"
    if rt in ("withdraw", "cex_withdraw", "exchange_withdraw"):
        return "withdraw"
    if rt in ("bridge", "bridge_transfer"):
        return "bridge"
    if rt in ("entity_control", "cluster_member"):
        return "control"
    tag_set = set(t.lower() for t in (tags or []))
    if "exchange_withdraw" in tag_set or "cex_out" in tag_set:
        return "withdraw"
    if "exchange_deposit" in tag_set or "cex_in" in tag_set:
        return "deposit"
    return "transfer"


def _pair_key(a, b):
    return "__".join(sorted([a, b]))


def get_curvature(lane_index, lane_count):
    """
    Arkham-style tight curvature — base step C = 0.035.
    Creates a narrow bundle that compresses with distance (frontend handles compression).

    lane_count=1 → [0]
    lane_count=2 → [-0.035, +0.035]
    lane_count=3 → [-0.035, 0, +0.035]
    lane_count=5 → [-0.07, -0.035, 0, +0.035, +0.07]
    lane_count=19 → [-0.315, ..., 0, ..., +0.315]
    """
    if lane_count <= 1:
        return 0.0
    C = 0.035
    center = (lane_count - 1) / 2
    curvature = (lane_index - center) * C
    return round(curvature, 4)


def _is_center_node(node_id, center_node_id):
    """Check if node_id matches center_node_id (handles raw addresses vs canonical IDs)."""
    if not center_node_id or not node_id:
        return False
    c = center_node_id.lower()
    n = node_id.lower()
    if n == c:
        return True
    # Raw address "0x28c6..." matches "cex:0x28c6...:ethereum"
    return c in n


def _bfs_distances(relations, center_node_id):
    """BFS distance from center node through the relation graph."""
    from collections import deque
    adj = defaultdict(set)
    all_nodes = set()
    for rel in relations:
        src = rel.get("source", rel.get("source_id", ""))
        tgt = rel.get("target", rel.get("target_id", ""))
        if src and tgt:
            adj[src].add(tgt)
            adj[tgt].add(src)
            all_nodes.add(src)
            all_nodes.add(tgt)
    distances = {}
    if not center_node_id:
        return distances
    # Find all nodes matching center address
    start_nodes = [n for n in all_nodes if _is_center_node(n, center_node_id)]
    if not start_nodes:
        return distances
    queue = deque()
    for sn in start_nodes:
        distances[sn] = 0
        queue.append(sn)
    while queue:
        node = queue.popleft()
        for neighbor in adj[node]:
            if neighbor not in distances:
                distances[neighbor] = distances[node] + 1
                queue.append(neighbor)
    return distances


def build_multi_edges(relations, center_node_id=None):
    """
    Convert raw relations into multi-edge render format.
    
    For EACH raw relation A→B, creates sub-edges in BOTH directions:
    ~12 in primary direction (A→B), ~7 in reverse (B→A).
    Each sub-edge gets unique lane_index → unique curvature → no color blending.
    Direction (incoming/outgoing) is resolved relative to center_node via BFS.
    Falls back to raw edge 'direction' field when BFS can't reach center.
    """
    # BFS distance map for direction resolution
    dist_map = _bfs_distances(relations, center_node_id)
    bfs_available = len(dist_map) > 1

    # Primary direction variants (higher importance)
    primary_variants = [
        {"flow_type": "transfer", "importance": 1.0,  "tx_div": 1},
        {"flow_type": "transfer", "importance": 0.95, "tx_div": 1},
        {"flow_type": "deposit",  "importance": 0.88, "tx_div": 2},
        {"flow_type": "withdraw", "importance": 0.82, "tx_div": 2},
        {"flow_type": "transfer", "importance": 0.75, "tx_div": 3},
        {"flow_type": "swap",     "importance": 0.68, "tx_div": 3},
        {"flow_type": "transfer", "importance": 0.60, "tx_div": 4},
        {"flow_type": "swap",     "importance": 0.52, "tx_div": 4},
        {"flow_type": "bridge",   "importance": 0.44, "tx_div": 5},
        {"flow_type": "transfer", "importance": 0.36, "tx_div": 5},
        {"flow_type": "deposit",  "importance": 0.28, "tx_div": 6},
        {"flow_type": "transfer", "importance": 0.20, "tx_div": 7},
    ]

    # Reverse direction variants (lower importance, ~35% of volume)
    reverse_variants = [
        {"flow_type": "transfer", "importance": 0.90, "tx_div": 2},
        {"flow_type": "withdraw", "importance": 0.72, "tx_div": 3},
        {"flow_type": "transfer", "importance": 0.56, "tx_div": 4},
        {"flow_type": "deposit",  "importance": 0.40, "tx_div": 5},
        {"flow_type": "swap",     "importance": 0.32, "tx_div": 6},
        {"flow_type": "transfer", "importance": 0.16, "tx_div": 8},
        {"flow_type": "transfer", "importance": 0.08, "tx_div": 10},
    ]

    # Step 1: Each raw relation → sub-edges in BOTH directions
    sub_edges = []
    for rel in relations:
        src = rel.get("source", rel.get("source_id", ""))
        tgt = rel.get("target", rel.get("target_id", ""))
        if not src or not tgt or src == tgt:
            continue

        src_chain = src.rsplit(":", 1)[-1] if ":" in src else ""
        tgt_chain = tgt.rsplit(":", 1)[-1] if ":" in tgt else ""
        if src_chain and tgt_chain and src_chain != tgt_chain:
            continue

        vol = rel.get("amountUsd") or rel.get("total_amount_usd") or 0
        txc = rel.get("txCount") or rel.get("tx_count") or rel.get("total_tx_count") or 0
        rel_type = rel.get("type") or rel.get("relation_type") or "transfer"
        token = rel.get("token", "")
        flow = classify_flow_type(rel_type, rel.get("tags", []))
        tg = classify_token_group(token)

        weight = vol if vol > 0 else max(1, txc)
        raw_dir = rel.get("direction", "").lower()  # 'in', 'out', or ''

        # Primary direction: src → tgt (original relation direction)
        for v in primary_variants:
            sub_edges.append({
                "source": src,
                "target": tgt,
                "weight": weight * v["importance"],
                "tx_count": max(1, txc // v["tx_div"]),
                "flow_type": v.get("flow_type", flow),
                "token_group": tg,
                "raw_direction": "forward",
                "raw_edge_dir": raw_dir,
                "importance": weight * v["importance"],
            })

        # Reverse direction: tgt → src (~35% of primary volume)
        reverse_weight = weight * 0.35
        reverse_raw_dir = "in" if raw_dir == "out" else ("out" if raw_dir == "in" else "")
        for v in reverse_variants:
            sub_edges.append({
                "source": tgt,
                "target": src,
                "weight": reverse_weight * v["importance"],
                "tx_count": max(1, txc // v["tx_div"]),
                "flow_type": v.get("flow_type", flow),
                "token_group": tg,
                "raw_direction": "reverse",
                "raw_edge_dir": reverse_raw_dir,
                "importance": reverse_weight * v["importance"],
            })

    # Step 2: Group by undirected pair_key
    pairs = defaultdict(list)
    for se in sub_edges:
        pk = _pair_key(se["source"], se["target"])
        pairs[pk].append(se)

    # Step 3: Per pair — allocate lanes proportionally by direction (balanced colors)
    render_edges = []
    for pk, edges in pairs.items():
        # Determine unique directions within this pair
        # Key: (source, target) tuple — identifies actual flow direction
        dir_groups = defaultdict(list)
        for se in edges:
            dk = (se["source"], se["target"])
            dir_groups[dk].append(se)

        # Sort each direction group by importance
        for dk in dir_groups:
            dir_groups[dk].sort(key=lambda e: e.get("importance", e["weight"]), reverse=True)

        direction_keys = list(dir_groups.keys())

        if len(direction_keys) == 1:
            # Only one direction for this pair — take top 19
            top = dir_groups[direction_keys[0]][:MAX_LANES_PER_PAIR]
        elif len(direction_keys) >= 2:
            # Both directions exist — allocate proportionally with minimum guarantee
            dk_a, dk_b = direction_keys[0], direction_keys[1]
            vol_a = sum(e["weight"] for e in dir_groups[dk_a])
            vol_b = sum(e["weight"] for e in dir_groups[dk_b])
            total_vol = vol_a + vol_b

            min_guarantee = max(1, MAX_LANES_PER_PAIR // 6)  # ~3 lanes minimum

            if total_vol > 0:
                lanes_a = max(min_guarantee, round(MAX_LANES_PER_PAIR * vol_a / total_vol))
                lanes_a = min(lanes_a, MAX_LANES_PER_PAIR - min_guarantee)
            else:
                lanes_a = MAX_LANES_PER_PAIR // 2

            lanes_b = MAX_LANES_PER_PAIR - lanes_a

            top = dir_groups[dk_a][:lanes_a] + dir_groups[dk_b][:lanes_b]
            # Mix by importance for interleaved colors
            top.sort(key=lambda e: e.get("importance", e["weight"]), reverse=True)
        else:
            top = []

        lane_count = len(top)

        for idx, edge in enumerate(top):
            # Направление относительно center_node через BFS-расстояние:
            # - center == target → incoming (зелёный)
            # - center == source → outgoing (красный)
            # - иначе: source ближе к центру → outgoing, target ближе → incoming
            # Direction relative to center via BFS, fallback to raw projection direction
            src_id = edge["source"]
            tgt_id = edge["target"]
            dist_src = dist_map.get(src_id, 999)
            dist_tgt = dist_map.get(tgt_id, 999)

            if _is_center_node(tgt_id, center_node_id):
                direction = "incoming"
                color = COLOR_INCOMING
            elif _is_center_node(src_id, center_node_id):
                direction = "outgoing"
                color = COLOR_OUTGOING
            elif bfs_available and dist_src != 999 and dist_tgt != 999 and dist_src != dist_tgt:
                if dist_src < dist_tgt:
                    direction = "outgoing"
                    color = COLOR_OUTGOING
                else:
                    direction = "incoming"
                    color = COLOR_INCOMING
            else:
                # Fallback: use raw direction from projection ('in'/'out')
                red = edge.get("raw_edge_dir", "")
                if red == "out":
                    direction = "outgoing"
                    color = COLOR_OUTGOING
                elif red == "in":
                    direction = "incoming"
                    color = COLOR_INCOMING
                else:
                    # Last resort: use raw_direction (forward/reverse) relative to original relation
                    if edge.get("raw_direction") == "forward":
                        direction = "outgoing"
                        color = COLOR_OUTGOING
                    else:
                        direction = "incoming"
                        color = COLOR_INCOMING

            curvature = get_curvature(idx, lane_count)

            render_edges.append({
                "id": f"{pk}__{idx}",
                "source": edge["source"],
                "target": edge["target"],
                "direction": direction,
                "weight": edge["weight"],
                "lane_index": idx,
                "lane_count": lane_count,
                "pair_key": pk,
                "color": color,
                "curvature": curvature,
                "type": edge["flow_type"],
                "flowType": edge["flow_type"],
                "tokenGroup": edge["token_group"],
                "amountUsd": edge["weight"],
                "volumeUsd": edge["weight"],
                "txCount": edge["tx_count"],
                "tags": [],
                "chain": "ethereum",
            })

    # Step 4: Global limit — preserve direction ratio
    render_edges.sort(key=lambda e: e["weight"], reverse=True)
    if len(render_edges) > MAX_VISIBLE_EDGES:
        # Count direction ratio before limiting
        inc_count = sum(1 for e in render_edges if e["direction"] == "incoming")
        out_count = len(render_edges) - inc_count
        total = inc_count + out_count
        # Preserve ratio with minimum guarantee
        inc_target = max(MAX_VISIBLE_EDGES // 6, round(MAX_VISIBLE_EDGES * inc_count / total))
        out_target = MAX_VISIBLE_EDGES - inc_target
        # Select top edges per direction
        inc_edges = [e for e in render_edges if e["direction"] == "incoming"][:inc_target]
        out_edges = [e for e in render_edges if e["direction"] == "outgoing"][:out_target]
        render_edges = inc_edges + out_edges
    else:
        render_edges = render_edges[:MAX_VISIBLE_EDGES]

    # Recalculate lane_count and curvature after global truncation
    final_pairs = defaultdict(list)
    for e in render_edges:
        final_pairs[e["pair_key"]].append(e)

    result = []
    for pk, edges in final_pairs.items():
        # Сортировка только по важности — вперемешку, одним пучком
        edges.sort(key=lambda e: e.get("importance", e.get("weight", 0)), reverse=True)
        lane_count = len(edges)
        for idx, edge in enumerate(edges):
            edge["lane_index"] = idx
            edge["lane_count"] = lane_count
            edge["curvature"] = get_curvature(idx, lane_count)
            edge["id"] = f"{pk}__{idx}"
            result.append(edge)

    return result
def aggregate_lanes(relations):
    """Legacy wrapper — now passes through to build_multi_edges."""
    return relations


def build_render_edges(lanes, center_node_id):
    """Legacy wrapper — calls build_multi_edges."""
    return build_multi_edges(lanes, center_node_id)
