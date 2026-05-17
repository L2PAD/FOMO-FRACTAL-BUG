"""
Entities V2 — Actor Intelligence Layer
=========================================================
Phase E-UI:
  1. Impact Engine — quantifies market influence
  2. Timeline Engine — temporal activity stream
  3. Interaction Engine — entity relationship graph

Actor Intelligence Layer (Phase A):
  4. Market Pressure — buy/sell pressure analysis
  5. Actor Strategy — strategy classification
  6. Actor Conviction — conviction level
  7. Actor Regime — current operating regime
  8. Actor Playbook — pattern sequence
  9. Cluster Intelligence — cluster roles, flow weight, token profile
  10. Token Dependency — stablecoin/eth/top token dependency
  11. Quick Tags — rule-based tags
  12. Actor Highlights — key insights
  13. Entity Summary — rule-based text summary
  14. Unified Intelligence Endpoint
"""

import os
import time
import math
from datetime import datetime, timezone
from pymongo import MongoClient

_client = None
_db = None


def _get_db():
    global _client, _db
    if _db is None:
        _client = MongoClient(os.environ.get("MONGO_URL"))
        _db = _client[os.environ.get("DB_NAME", "test_database")]
        _ensure_indexes()
    return _db


_cache: dict = {}
_CACHE_TTL = 300  # default 5 min
_CACHE_TTL_SHORT = 60  # 1 min for heavy aggregation endpoints
_indexes_ensured = False


def _cache_get(k):
    e = _cache.get(k)
    return e["data"] if e and time.time() - e["ts"] < e.get("ttl", _CACHE_TTL) else None


def _cache_set(k, data, ttl=None):
    _cache[k] = {"data": data, "ts": time.time(), "ttl": ttl or _CACHE_TTL}


def _ensure_indexes():
    """Ensure MongoDB indexes for intelligence layer (idempotent)."""
    global _indexes_ensured
    if _indexes_ensured:
        return
    try:
        db = _get_db()
        # Intelligence history — adaptive snapshots
        db["entity_intelligence_history"].create_index(
            [("entity", 1), ("timestamp", -1)], background=True
        )
        db["entity_intelligence_history"].create_index(
            [("entity", 1)], background=True
        )
        # Flows — frequently queried by slug
        db["entity_flows_v2"].create_index(
            [("slug", 1)], background=True
        )
        db["entity_flows_v2"].create_index(
            [("entity_slug", 1)], background=True
        )
        # Clusters — frequently queried by slug
        db["entity_clusters_v2"].create_index(
            [("slug", 1)], background=True
        )
        db["entity_clusters_v2"].create_index(
            [("entity_slug", 1)], background=True
        )
        # Token matrix
        db["entity_token_matrix_v2"].create_index(
            [("slug", 1)], background=True
        )
        db["entity_token_matrix_v2"].create_index(
            [("entity_slug", 1)], background=True
        )
        # Interactions (if collection exists)
        db["entity_interactions_v2"].create_index(
            [("slug", 1)], background=True
        )
        _indexes_ensured = True
    except Exception as e:
        print(f"[Entities] Index setup warning: {e}")


def _clamp(v, lo=0, hi=100):
    return int(max(lo, min(hi, round(v))))


def _fmt_usd(v):
    a = abs(v)
    if a >= 1e9:
        return f"${a / 1e9:.1f}B"
    if a >= 1e6:
        return f"${a / 1e6:.1f}M"
    if a >= 1e3:
        return f"${a / 1e3:.1f}K"
    return f"${a:.0f}"


# ══════════════════════════════════════════════════════════
#  1. ACTOR MARKET IMPACT
# ══════════════════════════════════════════════════════════

def get_entity_impact(slug: str) -> dict | None:
    """
    Compute actor market impact from:
      - portfolio_value → capital weight
      - flow_volume → market activity
      - cluster_size → network reach
      - exchange_interaction → market access
    """
    ck = f"entity_impact:{slug}"
    cached = _cache_get(ck)
    if cached is not None:
        return cached

    db = _get_db()

    # Check entity exists
    entity = db["entities_v2"].find_one({"slug": slug}, {"_id": 0})
    if not entity:
        return None

    # Portfolio value
    holdings = db["entity_holdings_v2"].find_one({"slug": slug}, {"_id": 0})
    portfolio_value = holdings.get("total_value_usd", 0) if holdings else 0

    # Flow volume
    flows = db["entity_flows_v2"].find_one({"slug": slug}, {"_id": 0})
    flow_volume = 0
    if flows and flows.get("all_time"):
        at = flows["all_time"]
        flow_volume = at.get("inflow_usd", 0) + at.get("outflow_usd", 0)

    # Cluster size
    clusters = list(db["entity_clusters_v2"].find({"entity_slug": slug}, {"_id": 0}))
    cluster_wallets = sum(c.get("cluster_size", 0) for c in clusters)

    # Exchange interactions
    exchange_count = 0
    if flows and flows.get("exchange_interactions"):
        exchange_count = len(flows["exchange_interactions"])

    # Behaviour
    behaviour = db["entity_behaviour_v2"].find_one({"entity_slug": slug}, {"_id": 0})
    behaviour_type = behaviour.get("behaviour_type", "unknown") if behaviour else "unknown"
    confidence = behaviour.get("confidence", 0) if behaviour else 0

    # ── Score Components ──
    # Portfolio impact (log scale, cap at $10B)
    if portfolio_value > 0:
        portfolio_score = _clamp(math.log10(max(portfolio_value, 1)) * 12)
    else:
        portfolio_score = 0

    # Flow impact (log scale)
    if flow_volume > 0:
        flow_score = _clamp(math.log10(max(flow_volume, 1)) * 11)
    else:
        flow_score = 0

    # Network reach
    network_score = _clamp(min(cluster_wallets / 10, 100))

    # Exchange access
    exchange_score = _clamp(exchange_count * 20)

    # Composite impact
    impact_score = _clamp(
        portfolio_score * 0.35 +
        flow_score * 0.30 +
        network_score * 0.20 +
        exchange_score * 0.15
    )

    # Impact level
    if impact_score >= 75:
        level = "SYSTEMIC"
    elif impact_score >= 55:
        level = "HIGH"
    elif impact_score >= 35:
        level = "MEDIUM"
    else:
        level = "LOW"

    # Drivers
    drivers = []
    if portfolio_value >= 1_000_000:
        drivers.append(f"Portfolio {_fmt_usd(portfolio_value)}")
    if flow_volume >= 500_000:
        drivers.append(f"Flow volume {_fmt_usd(flow_volume)}")
    if cluster_wallets >= 20:
        drivers.append(f"{cluster_wallets} wallet cluster network")
    if exchange_count >= 2:
        drivers.append(f"Interacts with {exchange_count} exchanges")
    if behaviour_type in ("market_making", "liquidity_provision"):
        drivers.append(f"Acts as {behaviour_type.replace('_', ' ')}")

    result = {
        "slug": slug,
        "impact_score": impact_score,
        "impact_level": level,
        "components": {
            "portfolio": {"score": portfolio_score, "value": portfolio_value, "fmt": _fmt_usd(portfolio_value)},
            "flow": {"score": flow_score, "volume": flow_volume, "fmt": _fmt_usd(flow_volume)},
            "network": {"score": network_score, "wallets": cluster_wallets},
            "exchange": {"score": exchange_score, "count": exchange_count},
        },
        "drivers": drivers,
        "behaviour": behaviour_type,
        "confidence": round(confidence, 2),
    }

    _cache_set(ck, result)
    return result


# ══════════════════════════════════════════════════════════
#  2. ENTITY TIMELINE
# ══════════════════════════════════════════════════════════

def get_entity_timeline(slug: str) -> dict | None:
    """
    Build temporal activity stream showing:
      - flow events across time windows
      - token changes
      - behaviour shifts
      - cluster expansion events
    """
    ck = f"entity_timeline:{slug}"
    cached = _cache_get(ck)
    if cached is not None:
        return cached

    db = _get_db()

    entity = db["entities_v2"].find_one({"slug": slug}, {"_id": 0})
    if not entity:
        return None

    events = []
    now = time.time()

    # Flow events from time windows
    flows = db["entity_flows_v2"].find_one({"slug": slug}, {"_id": 0})
    if flows and flows.get("flows"):
        windows = ["24h", "7d", "30d"]
        for w in windows:
            wdata = flows["flows"].get(w, {})
            if wdata:
                net = wdata.get("net_flow_usd", 0)
                vol = wdata.get("inflow_usd", 0) + wdata.get("outflow_usd", 0)
                if vol > 0:
                    events.append({
                        "type": "flow",
                        "window": w,
                        "description": f"Net flow {_fmt_usd(net)} (volume {_fmt_usd(vol)})",
                        "value": net,
                        "volume": vol,
                        "direction": "inflow" if net >= 0 else "outflow",
                    })

    # Token matrix shifts
    matrix = db["entity_token_matrix_v2"].find_one({"slug": slug}, {"_id": 0})
    if matrix and matrix.get("tokens"):
        accum_tokens = [t for t in matrix["tokens"] if t.get("role") == "accumulation_token"]
        dist_tokens = [t for t in matrix["tokens"] if t.get("role") == "distribution_token"]
        liq_tokens = [t for t in matrix["tokens"] if t.get("role") == "liquidity_token"]
        if accum_tokens:
            events.append({
                "type": "token_shift",
                "window": "all",
                "description": f"Accumulating {len(accum_tokens)} tokens: {', '.join(t.get('symbol', '?') for t in accum_tokens[:3])}",
                "direction": "accumulation",
                "count": len(accum_tokens),
            })
        if dist_tokens:
            events.append({
                "type": "token_shift",
                "window": "all",
                "description": f"Distributing {len(dist_tokens)} tokens: {', '.join(t.get('symbol', '?') for t in dist_tokens[:3])}",
                "direction": "distribution",
                "count": len(dist_tokens),
            })
        if liq_tokens:
            events.append({
                "type": "token_shift",
                "window": "all",
                "description": f"Providing liquidity in {len(liq_tokens)} tokens",
                "direction": "liquidity",
                "count": len(liq_tokens),
            })

    # Behaviour classification event
    behaviour = db["entity_behaviour_v2"].find_one({"entity_slug": slug}, {"_id": 0})
    if behaviour:
        events.append({
            "type": "behaviour",
            "window": "latest",
            "description": f"Classified as {behaviour.get('behaviour_type', 'unknown')} (confidence {behaviour.get('confidence', 0):.0%})",
            "behaviour_type": behaviour.get("behaviour_type", "unknown"),
            "confidence": round(behaviour.get("confidence", 0), 2),
        })

    # Cluster expansion
    clusters = list(db["entity_clusters_v2"].find({"entity_slug": slug}, {"_id": 0}))
    if clusters:
        total_wallets = sum(c.get("cluster_size", 0) for c in clusters)
        events.append({
            "type": "cluster",
            "window": "latest",
            "description": f"Cluster expanded to {total_wallets} wallets across {len(clusters)} clusters",
            "wallets": total_wallets,
            "clusters": len(clusters),
        })

    # Chain expansion
    chains = db["entity_chains_v2"].find_one({"slug": slug}, {"_id": 0})
    if chains and chains.get("chains"):
        active_chains = [c for c in chains["chains"] if c.get("tx_count", 0) > 0]
        if len(active_chains) > 1:
            chain_names = [c.get("chain_name", "?") for c in active_chains]
            events.append({
                "type": "multichain",
                "window": "latest",
                "description": f"Active on {len(active_chains)} chains: {', '.join(chain_names)}",
                "chains": len(active_chains),
            })

    # Window summaries
    window_summary = {}
    for w in ["24h", "7d", "30d"]:
        wevents = [e for e in events if e.get("window") == w]
        wflows = [e for e in wevents if e["type"] == "flow"]
        window_summary[w] = {
            "event_count": len(wevents),
            "net_flow": wflows[0]["value"] if wflows else 0,
            "volume": wflows[0]["volume"] if wflows else 0,
        }

    result = {
        "slug": slug,
        "name": entity.get("name", slug),
        "events": events,
        "event_count": len(events),
        "window_summary": window_summary,
    }

    _cache_set(ck, result)
    return result


# ══════════════════════════════════════════════════════════
#  3. INTERACTION NETWORK
# ══════════════════════════════════════════════════════════

def get_entity_interactions(slug: str) -> dict | None:
    """
    Build entity interaction graph:
      - entity → exchanges (from flow exchange_interactions)
      - entity → tokens (from token_matrix)
      - entity → protocols (from token_matrix / flows)
      - entity → other entities (from similarity)
    """
    ck = f"entity_interactions:{slug}"
    cached = _cache_get(ck)
    if cached is not None:
        return cached

    db = _get_db()

    entity = db["entities_v2"].find_one({"slug": slug}, {"_id": 0})
    if not entity:
        return None

    nodes = [{"id": slug, "type": "entity", "label": entity.get("name", slug), "is_self": True}]
    edges = []

    # Exchange interactions
    flows = db["entity_flows_v2"].find_one({"slug": slug}, {"_id": 0})
    if flows and flows.get("exchange_interactions"):
        for ex in flows["exchange_interactions"][:8]:
            ex_name = ex.get("exchange", ex.get("label", "Unknown"))
            ex_id = f"exchange_{ex_name.lower().replace(' ', '_')}"
            vol = ex.get("volume_usd", 0)
            nodes.append({"id": ex_id, "type": "exchange", "label": ex_name})
            edges.append({
                "source": slug,
                "target": ex_id,
                "type": "exchange_flow",
                "weight": vol,
                "label": _fmt_usd(vol),
            })

    # Token interactions
    matrix = db["entity_token_matrix_v2"].find_one({"slug": slug}, {"_id": 0})
    if matrix and matrix.get("tokens"):
        for t in matrix["tokens"][:10]:
            symbol = t.get("symbol", "?")
            token_id = f"token_{symbol.lower()}"
            role = t.get("role", "neutral_token")
            nodes.append({"id": token_id, "type": "token", "label": symbol, "role": role})
            edges.append({
                "source": slug,
                "target": token_id,
                "type": "token_interaction",
                "weight": t.get("dominance_pct", 0),
                "label": role.replace("_token", ""),
            })

    # Similar entities (other entities)
    similar = db["entity_similarity_v2"].find_one({"slug": slug}, {"_id": 0})
    if similar and similar.get("similar"):
        for s in similar["similar"][:5]:
            s_slug = s.get("slug", "?")
            s_id = f"entity_{s_slug}"
            nodes.append({"id": s_id, "type": "entity", "label": s.get("name", s_slug)})
            edges.append({
                "source": slug,
                "target": s_id,
                "type": "similarity",
                "weight": s.get("composite_score", 0),
                "label": f"{s.get('composite_score', 0):.0%} similar",
            })

    # Cluster connections
    clusters = list(db["entity_clusters_v2"].find({"entity_slug": slug}, {"_id": 0}))
    if clusters:
        for c in clusters[:5]:
            c_id = c.get("cluster_id", "?")
            nodes.append({"id": f"cluster_{c_id}", "type": "cluster", "label": f"Cluster {c_id[:8]}"})
            edges.append({
                "source": slug,
                "target": f"cluster_{c_id}",
                "type": "cluster_link",
                "weight": c.get("cluster_size", 0),
                "label": f"{c.get('cluster_size', 0)} wallets",
            })

    # Summary
    by_type = {}
    for n in nodes:
        t = n["type"]
        by_type[t] = by_type.get(t, 0) + 1

    result = {
        "slug": slug,
        "name": entity.get("name", slug),
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "by_type": by_type,
        },
    }

    _cache_set(ck, result)
    return result


# ══════════════════════════════════════════════════════════
#  ACTOR INTELLIGENCE LAYER — Phase A
# ══════════════════════════════════════════════════════════

STABLECOIN_ADDRESSES = {
    "0xdac17f958d2ee523a2206206994597c13d831ec7",  # USDT
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",  # USDC
    "0x6b175474e89094c44da98b954eedeac495271d0f",  # DAI
    "0x4fabb145d64652a948d72533023f6e7a623c7c53",  # BUSD
    "0x8e870d67f660d95d5be530380d0ec0bd388289e1",  # USDP
    "0x4c9edd5852cd905f086c759e8383e09bff1e68b3",  # USDe
}

ETH_ADDRESSES = {
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",  # WETH
    "0xae7ab96520de3a18e5e111b5eaab095312d7fe84",  # stETH
    "0xbe9895146f7af43049ca1c1ae358b0541ea49704",  # cbETH
}


def _load_entity_data(slug: str) -> dict | None:
    """Load all entity data needed for intelligence computations (cached)."""
    ck = f"entity_data:{slug}"
    cached = _cache_get(ck)
    if cached is not None:
        return cached

    db = _get_db()

    entity = db["entities_v2"].find_one({"slug": slug}, {"_id": 0})
    if not entity:
        return None

    flows = db["entity_flows_v2"].find_one(
        {"$or": [{"slug": slug}, {"entity_slug": slug}]}, {"_id": 0}
    )
    matrix = db["entity_token_matrix_v2"].find_one(
        {"$or": [{"slug": slug}, {"entity_slug": slug}]}, {"_id": 0}
    )
    holdings = db["entity_holdings_v2"].find_one(
        {"$or": [{"slug": slug}, {"entity_slug": slug}]}, {"_id": 0}
    )
    behaviour = db["entity_behaviour_v2"].find_one(
        {"$or": [{"slug": slug}, {"entity_slug": slug}]}, {"_id": 0}
    )
    clusters = db["entity_clusters_v2"].find_one(
        {"$or": [{"slug": slug}, {"entity_slug": slug}]}, {"_id": 0}
    )

    result = {
        "entity": entity,
        "flows": flows or {},
        "matrix": matrix or {},
        "holdings": holdings or {},
        "behaviour": behaviour or {},
        "clusters": clusters or {},
    }
    _cache_set(ck, result)
    return result


# ──────────────────────────────────────────────
#  4. MARKET PRESSURE
# ──────────────────────────────────────────────

def compute_market_pressure(data: dict) -> dict:
    """
    Determine buy/sell pressure from flow dynamics.
    Signals: net flow direction, stablecoin flows, velocity trend.
    Output: bullish / bearish / neutral + score + drivers.
    """
    flows = data["flows"]
    matrix = data["matrix"]

    all_time = flows.get("all_time", {})
    inflow = all_time.get("inflow_usd", 0)
    outflow = all_time.get("outflow_usd", 0)
    total = inflow + outflow
    net = all_time.get("net_flow_usd", inflow - outflow)

    if total <= 0:
        return {"pressure": "neutral", "score": 0, "drivers": ["no flow data"]}

    score = 0.0
    drivers = []

    # Signal 1: Net flow direction
    inflow_ratio = inflow / total
    if inflow_ratio >= 0.65:
        score += 30
        drivers.append("Strong net inflow")
    elif inflow_ratio >= 0.55:
        score += 15
        drivers.append("Positive net inflow")
    elif inflow_ratio <= 0.35:
        score -= 30
        drivers.append("Strong net outflow")
    elif inflow_ratio <= 0.45:
        score -= 15
        drivers.append("Negative net flow")

    # Signal 2: Stablecoin inflow = buying power
    stable_dep = matrix.get("stablecoin_dependency", 0)
    if stable_dep >= 0.7:
        if inflow_ratio >= 0.55:
            score += 20
            drivers.append("Stablecoin inflow dominance")
        elif inflow_ratio <= 0.45:
            score -= 20
            drivers.append("Stablecoin outflow pressure")

    # Signal 3: Flow velocity (high velocity amplifies signal)
    velocity = flows.get("flow_velocity", 0)
    if velocity >= 500_000:
        amplifier = min(15, int(velocity / 500_000) * 5)
        score = score * 1.2 if score > 0 else score * 1.2
        drivers.append(f"High velocity ({_fmt_usd(velocity)}/day)")

    # Signal 4: Window trend (24h vs 7d momentum)
    windows = flows.get("flows", {})
    w24h = windows.get("24h", {})
    w7d = windows.get("7d", {})
    net_24h = w24h.get("net_flow_usd", 0)
    net_7d = w7d.get("net_flow_usd", 0)

    if net_24h > 0 and net_7d > 0:
        score += 10
        drivers.append("Consistent inflow across windows")
    elif net_24h < 0 and net_7d < 0:
        score -= 10
        drivers.append("Consistent outflow across windows")
    elif net_24h > 0 and net_7d < 0:
        drivers.append("Recent inflow reversal")
    elif net_24h < 0 and net_7d > 0:
        drivers.append("Recent outflow reversal")

    # Normalize to -100..+100, then classify
    score = max(-100, min(100, score))

    if score >= 25:
        pressure = "bullish"
    elif score <= -25:
        pressure = "bearish"
    else:
        pressure = "neutral"

    return {
        "pressure": pressure,
        "score": round(score),
        "inflow_ratio": round(inflow_ratio, 4),
        "net_flow_usd": round(net, 2),
        "drivers": drivers[:5],
    }


# ──────────────────────────────────────────────
#  5. ACTOR STRATEGY
# ──────────────────────────────────────────────

def compute_actor_strategy(data: dict) -> dict:
    """
    Classify the actor's primary strategy.
    Based on behaviour type, flow patterns, token matrix, holdings.
    Output: strategy label + confidence + drivers.
    """
    behaviour = data["behaviour"]
    matrix = data["matrix"]
    flows = data["flows"]
    holdings = data["holdings"]

    beh_type = behaviour.get("behaviour_type", "mixed")
    beh_conf = behaviour.get("confidence", 0)
    stable_dep = matrix.get("stablecoin_dependency", 0)
    velocity = flows.get("flow_velocity", 0)
    portfolio_value = holdings.get("total_value_usd", 0)

    role_breakdown = matrix.get("role_breakdown", {})
    liq_share = role_breakdown.get("liquidity_token", {}).get("volume_usd", 0)
    total_vol = matrix.get("total_flow_volume_usd", 0)
    liq_ratio = liq_share / total_vol if total_vol > 0 else 0

    drivers = []

    # Strategy mapping (rule-based)
    if beh_type == "liquidity_provision":
        strategy = "Liquidity Provider"
        drivers.append(f"Behaviour: liquidity provision ({beh_conf:.0%})")
        if stable_dep >= 0.7:
            drivers.append("Stablecoin-centric liquidity")
    elif beh_type == "market_making":
        strategy = "Market Maker"
        drivers.append(f"Behaviour: market making ({beh_conf:.0%})")
        if velocity >= 500_000:
            drivers.append(f"High velocity: {_fmt_usd(velocity)}/day")
    elif beh_type == "accumulation":
        if stable_dep >= 0.6:
            strategy = "Strategic Accumulator"
            drivers.append("Accumulation with stablecoin base")
        else:
            strategy = "Token Accumulator"
            drivers.append("Active token accumulation")
        drivers.append(f"Behaviour confidence: {beh_conf:.0%}")
    elif beh_type == "distribution":
        strategy = "Distributor"
        drivers.append(f"Distribution pattern ({beh_conf:.0%})")
    elif beh_type == "treasury":
        strategy = "Treasury Manager"
        drivers.append("Low velocity, concentrated holdings")
        if portfolio_value >= 1_000_000:
            drivers.append(f"Portfolio: {_fmt_usd(portfolio_value)}")
    else:
        # Mixed — try to infer from data
        if liq_ratio >= 0.4 and stable_dep >= 0.5:
            strategy = "Liquidity Provider"
            drivers.append("High liquidity token ratio")
        elif velocity >= 500_000:
            strategy = "Active Trader"
            drivers.append("High flow velocity")
        elif portfolio_value >= 10_000_000 and velocity <= 50_000:
            strategy = "Passive Holder"
            drivers.append("Large portfolio, low activity")
        else:
            strategy = "Mixed Strategy"
            drivers.append("No dominant strategy pattern")

    return {
        "strategy": strategy,
        "confidence": round(beh_conf, 2),
        "drivers": drivers[:5],
    }


# ──────────────────────────────────────────────
#  6. ACTOR CONVICTION
# ──────────────────────────────────────────────

def compute_actor_conviction(data: dict) -> dict:
    """
    Measure actor's conviction level.
    Signals: portfolio concentration, flow consistency, position size, holding time.
    Output: low / moderate / high / extreme + score + drivers.
    """
    holdings = data["holdings"]
    flows = data["flows"]
    matrix = data["matrix"]
    behaviour = data["behaviour"]

    score = 0
    drivers = []

    # Signal 1: Portfolio concentration
    portfolio = holdings.get("portfolio", {})
    concentration = portfolio.get("concentration_score", 0)
    if concentration >= 80:
        score += 30
        drivers.append("Highly concentrated portfolio")
    elif concentration >= 60:
        score += 20
        drivers.append("Concentrated portfolio")
    elif concentration >= 40:
        score += 10
        drivers.append("Moderately diversified")

    # Signal 2: Flow direction consistency
    all_time = flows.get("all_time", {})
    inflow = all_time.get("inflow_usd", 0)
    outflow = all_time.get("outflow_usd", 0)
    total = inflow + outflow
    if total > 0:
        bias = abs(inflow - outflow) / total
        if bias >= 0.5:
            score += 25
            drivers.append("Strong directional conviction")
        elif bias >= 0.3:
            score += 15
            drivers.append("Moderate directional bias")

    # Signal 3: Top token dependency (conviction in specific assets)
    top3 = matrix.get("top3_concentration", 0)
    if top3 >= 0.8:
        score += 20
        drivers.append("Focused on top assets")
    elif top3 >= 0.6:
        score += 10
        drivers.append("Top 3 asset focus")

    # Signal 4: Behaviour confidence (high confidence = clear pattern = conviction)
    beh_conf = behaviour.get("confidence", 0)
    if beh_conf >= 0.7:
        score += 15
        drivers.append("Clear behaviour pattern")
    elif beh_conf >= 0.4:
        score += 5

    # Signal 5: Position size (larger = more conviction)
    portfolio_value = holdings.get("total_value_usd", 0)
    if portfolio_value >= 10_000_000:
        score += 10
        drivers.append(f"Large position: {_fmt_usd(portfolio_value)}")
    elif portfolio_value >= 1_000_000:
        score += 5

    score = max(0, min(100, score))

    if score >= 75:
        conviction = "extreme"
    elif score >= 50:
        conviction = "high"
    elif score >= 25:
        conviction = "moderate"
    else:
        conviction = "low"

    return {
        "conviction": conviction,
        "score": score,
        "drivers": drivers[:5],
    }


# ──────────────────────────────────────────────
#  7. ACTOR REGIME
# ──────────────────────────────────────────────

def compute_actor_regime(data: dict) -> dict:
    """
    Determine the current operating regime.
    Based on recent flow direction + token matrix roles + velocity.
    Output: accumulation / distribution / liquidity / dormant / rotation.
    """
    flows = data["flows"]
    matrix = data["matrix"]
    behaviour = data["behaviour"]

    beh_type = behaviour.get("behaviour_type", "mixed")
    velocity = flows.get("flow_velocity", 0)

    all_time = flows.get("all_time", {})
    inflow = all_time.get("inflow_usd", 0)
    outflow = all_time.get("outflow_usd", 0)
    total = inflow + outflow

    role_breakdown = matrix.get("role_breakdown", {})
    accum_vol = role_breakdown.get("accumulation_token", {}).get("volume_usd", 0)
    distrib_vol = role_breakdown.get("distribution_token", {}).get("volume_usd", 0)
    liq_vol = role_breakdown.get("liquidity_token", {}).get("volume_usd", 0)
    total_matrix = matrix.get("total_flow_volume_usd", 0)

    drivers = []

    # Dormant check
    if total <= 0 and velocity <= 0:
        return {"regime": "dormant", "drivers": ["No flow activity detected"]}

    if velocity <= 1000 and total <= 10_000:
        return {"regime": "dormant", "drivers": ["Minimal activity"]}

    # Check token role dominance
    if total_matrix > 0:
        accum_ratio = accum_vol / total_matrix
        distrib_ratio = distrib_vol / total_matrix
        liq_ratio = liq_vol / total_matrix
    else:
        accum_ratio = distrib_ratio = liq_ratio = 0

    # Rotation: both accumulation and distribution active
    if accum_ratio >= 0.2 and distrib_ratio >= 0.2:
        rotation_signal = True
        drivers.append("Active token rotation")
    else:
        rotation_signal = False

    # Determine regime by dominant signal
    if liq_ratio >= 0.4 or beh_type == "liquidity_provision":
        regime = "liquidity"
        drivers.append("Liquidity provision dominant")
    elif rotation_signal and beh_type in ("market_making", "mixed"):
        regime = "rotation"
        drivers.append("Buying and selling simultaneously")
    elif total > 0:
        inflow_ratio = inflow / total
        if inflow_ratio >= 0.6 or beh_type == "accumulation":
            regime = "accumulation"
            drivers.append("Net inflow dominant")
        elif inflow_ratio <= 0.4 or beh_type == "distribution":
            regime = "distribution"
            drivers.append("Net outflow dominant")
        elif beh_type == "treasury":
            regime = "dormant"
            drivers.append("Treasury holding mode")
        else:
            regime = "rotation"
            drivers.append("Balanced flows")
    else:
        regime = "dormant"
        drivers.append("Insufficient data")

    return {
        "regime": regime,
        "drivers": drivers[:5],
    }


# ──────────────────────────────────────────────
#  8. ACTOR PLAYBOOK
# ──────────────────────────────────────────────

def compute_actor_playbook(data: dict) -> dict:
    """
    Describe the actor's playbook as a pattern sequence.
    Combines strategy + regime + flow patterns.
    """
    strategy = compute_actor_strategy(data)
    regime = compute_actor_regime(data)
    pressure = compute_market_pressure(data)

    strategy_label = strategy["strategy"]
    regime_label = regime["regime"]
    pressure_label = pressure["pressure"]

    # Build playbook description
    parts = []

    # Primary pattern from strategy
    strategy_lower = strategy_label.lower()
    if "liquidity" in strategy_lower:
        parts.append("liquidity")
    elif "accumul" in strategy_lower:
        parts.append("accumulation")
    elif "distribut" in strategy_lower:
        parts.append("distribution")
    elif "market maker" in strategy_lower:
        parts.append("market making")
    elif "treasury" in strategy_lower:
        parts.append("treasury")
    elif "trader" in strategy_lower:
        parts.append("active trading")
    elif "holder" in strategy_lower:
        parts.append("passive holding")
    else:
        parts.append("mixed activity")

    # Transition arrow from regime
    if regime_label != parts[0].split()[0] if parts else "":
        if regime_label not in ("dormant",):
            parts.append(regime_label)

    # Deduplicate
    seen = set()
    unique_parts = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            unique_parts.append(p)

    playbook = " -> ".join(unique_parts) if len(unique_parts) > 1 else unique_parts[0]

    return {
        "playbook": playbook,
        "strategy": strategy_label,
        "regime": regime_label,
        "pressure": pressure_label,
    }


# ──────────────────────────────────────────────
#  9. CLUSTER INTELLIGENCE
# ──────────────────────────────────────────────

def compute_cluster_roles(data: dict) -> list[dict]:
    """
    Assign roles to each cluster: liquidity, trading, custody, treasury, routing, unknown.
    Also compute flow_weight and token_profile per cluster.
    """
    clusters_data = data["clusters"]
    cluster_list = clusters_data.get("clusters", [])

    if not cluster_list:
        return []

    result = []
    for cl in cluster_list:
        members = cl.get("members", [])
        size = cl.get("size", len(members))
        tier = cl.get("tier", "low")
        confidence = cl.get("confidence", 0)

        # Analyze member roles
        role_counts = {}
        total_transfers = 0
        total_tokens = 0
        for m in members:
            role = m.get("role", "peripheral")
            role_counts[role] = role_counts.get(role, 0) + 1
            total_transfers += m.get("transfer_count", 0)
            total_tokens += m.get("unique_tokens", 0)

        avg_transfers = total_transfers / max(size, 1)
        avg_tokens = total_tokens / max(size, 1)

        # Determine cluster role from member composition
        receivers = role_counts.get("receiver", 0)
        senders = role_counts.get("sender", 0)
        intermediaries = role_counts.get("intermediary", 0)

        if intermediaries >= size * 0.4:
            cluster_role = "routing"
        elif receivers >= size * 0.6 and avg_transfers <= 5:
            cluster_role = "custody"
        elif senders >= size * 0.6 and avg_transfers >= 10:
            cluster_role = "trading"
        elif receivers >= size * 0.5 and avg_transfers <= 3:
            cluster_role = "treasury"
        elif avg_transfers >= 8 and avg_tokens >= 3:
            cluster_role = "trading"
        elif intermediaries >= size * 0.3 and avg_transfers >= 5:
            cluster_role = "liquidity"
        else:
            cluster_role = "unknown"

        # Flow weight: how significant is this cluster
        activity = cl.get("activity_score", 0)
        flow_weight = round(min(1.0, (avg_transfers / 20) * 0.5 + activity * 0.5), 4)

        # Token profile
        if avg_tokens >= 5:
            token_profile = "diversified"
        elif avg_tokens >= 2:
            token_profile = "focused"
        else:
            token_profile = "single_asset"

        result.append({
            "cluster_id": cl.get("cluster_id", "unknown"),
            "tier": tier,
            "size": size,
            "cluster_role": cluster_role,
            "flow_weight": flow_weight,
            "token_profile": token_profile,
            "confidence": confidence,
            "avg_transfers": round(avg_transfers, 1),
            "avg_tokens": round(avg_tokens, 1),
            "member_roles": role_counts,
        })

    return result


# ──────────────────────────────────────────────
#  10. TOKEN DEPENDENCY
# ──────────────────────────────────────────────

def compute_token_dependency(data: dict) -> dict:
    """
    Calculate dependency metrics:
    - stablecoin_dependency: share of stablecoin volume
    - eth_dependency: share of ETH-related volume
    - top_token_dependency: share of single largest token
    """
    matrix = data["matrix"]
    tokens = matrix.get("tokens", [])
    total_vol = matrix.get("total_flow_volume_usd", 0)

    if total_vol <= 0 or not tokens:
        return {
            "stablecoin_dependency": 0,
            "eth_dependency": 0,
            "top_token_dependency": 0,
            "top_token_symbol": None,
        }

    stable_vol = 0
    eth_vol = 0
    top_vol = 0
    top_symbol = None

    for t in tokens:
        addr = t.get("token_address", "").lower()
        vol = t.get("flow_volume_usd", 0)

        if addr in STABLECOIN_ADDRESSES:
            stable_vol += vol
        if addr in ETH_ADDRESSES:
            eth_vol += vol
        if vol > top_vol:
            top_vol = vol
            top_symbol = t.get("symbol", "?")

    return {
        "stablecoin_dependency": round(stable_vol / total_vol, 4),
        "eth_dependency": round(eth_vol / total_vol, 4),
        "top_token_dependency": round(top_vol / total_vol, 4),
        "top_token_symbol": top_symbol,
    }


# ──────────────────────────────────────────────
#  11. QUICK TAGS
# ──────────────────────────────────────────────

def generate_quick_tags(data: dict, pressure: dict, strategy: dict, conviction: dict, regime: dict) -> list[str]:
    """
    Generate rule-based quick tags for the entity.
    """
    tags = []
    flows = data["flows"]
    matrix = data["matrix"]
    holdings = data["holdings"]
    clusters = data["clusters"]

    stable_dep = matrix.get("stablecoin_dependency", 0)
    velocity = flows.get("flow_velocity", 0)
    portfolio_value = holdings.get("total_value_usd", 0)
    cluster_count = len(clusters.get("clusters", []))
    total_discovered = clusters.get("total_discovered", 0)

    # Stablecoin tags
    if stable_dep >= 0.8:
        tags.append("Stablecoin Heavy")
    elif stable_dep >= 0.5:
        tags.append("Stablecoin Active")

    # Strategy-based tags
    strat = strategy.get("strategy", "")
    if "Liquidity" in strat:
        tags.append("Liquidity Provider")
    if "Market Maker" in strat:
        tags.append("Market Maker")
    if "Accumulator" in strat:
        tags.append("Accumulation Mode")
    if "Distributor" in strat:
        tags.append("Distribution Mode")
    if "Treasury" in strat:
        tags.append("Treasury")

    # Velocity tags
    if velocity >= 1_000_000:
        tags.append("High Velocity")
    elif velocity >= 100_000:
        tags.append("Active Flows")

    # Pressure tags
    p = pressure.get("pressure", "neutral")
    if p == "bullish":
        tags.append("Buy Pressure")
    elif p == "bearish":
        tags.append("Sell Pressure")

    # Conviction tags
    c = conviction.get("conviction", "low")
    if c in ("high", "extreme"):
        tags.append("High Conviction")

    # Network tags
    if total_discovered >= 50:
        tags.append("Large Network")
    elif total_discovered >= 20:
        tags.append("Growing Network")

    # Portfolio tags
    if portfolio_value >= 100_000_000:
        tags.append("Whale")
    elif portfolio_value >= 10_000_000:
        tags.append("Major Actor")

    # Regime tags
    r = regime.get("regime", "dormant")
    if r == "rotation":
        tags.append("Token Rotation")

    return tags[:8]  # Cap at 8 tags


# ──────────────────────────────────────────────
#  12. ACTOR HIGHLIGHTS
# ──────────────────────────────────────────────

def generate_actor_highlights(data: dict, pressure: dict, token_dep: dict, cluster_roles: list) -> list[str]:
    """
    Generate key insight highlights for the entity.
    """
    highlights = []
    flows = data["flows"]
    matrix = data["matrix"]
    holdings = data["holdings"]
    clusters = data["clusters"]

    # Stablecoin concentration
    stable_dep = token_dep.get("stablecoin_dependency", 0)
    if stable_dep >= 0.5:
        highlights.append(f"Stablecoin concentration {round(stable_dep * 100)}%")

    # ETH dependency
    eth_dep = token_dep.get("eth_dependency", 0)
    if eth_dep >= 0.3:
        highlights.append(f"ETH dependency {round(eth_dep * 100)}%")

    # Top token dependency
    top_dep = token_dep.get("top_token_dependency", 0)
    top_sym = token_dep.get("top_token_symbol")
    if top_dep >= 0.5 and top_sym:
        highlights.append(f"Dominant asset: {top_sym} ({round(top_dep * 100)}%)")

    # Cluster expansion
    total_discovered = clusters.get("total_discovered", 0)
    known = clusters.get("known_addresses", 0)
    if total_discovered >= 10:
        highlights.append(f"Cluster expansion +{total_discovered} wallets")

    # Liquidity routing
    routing_clusters = [c for c in cluster_roles if c.get("cluster_role") == "routing"]
    if routing_clusters:
        highlights.append("Liquidity routing active")

    # Trading clusters
    trading_clusters = [c for c in cluster_roles if c.get("cluster_role") == "trading"]
    if trading_clusters:
        total_trading = sum(c.get("size", 0) for c in trading_clusters)
        highlights.append(f"Trading cluster: {total_trading} wallets")

    # Flow acceleration
    windows = flows.get("flows", {})
    w24h = windows.get("24h", {})
    w7d = windows.get("7d", {})
    vol_24h = w24h.get("inflow_usd", 0) + w24h.get("outflow_usd", 0)
    vol_7d = w7d.get("inflow_usd", 0) + w7d.get("outflow_usd", 0)
    if vol_7d > 0 and vol_24h > 0:
        daily_avg_7d = vol_7d / 7
        if daily_avg_7d > 0 and vol_24h > daily_avg_7d * 1.5:
            highlights.append("Flow acceleration detected")

    # Impact level (from existing impact data)
    impact_data = get_entity_impact(data["entity"]["slug"])
    if impact_data:
        level = impact_data.get("impact_level", "LOW")
        score = impact_data.get("impact_score", 0)
        highlights.append(f"Impact Level: {level} ({score})")

    # Portfolio size
    portfolio_value = holdings.get("total_value_usd", 0)
    if portfolio_value >= 1_000_000:
        highlights.append(f"Portfolio: {_fmt_usd(portfolio_value)}")

    return highlights[:8]


# ──────────────────────────────────────────────
#  13. ENTITY SUMMARY
# ──────────────────────────────────────────────

def generate_entity_summary(
    data: dict,
    pressure: dict,
    strategy: dict,
    conviction: dict,
    regime: dict,
    token_dep: dict,
) -> str:
    """
    Generate a rule-based text summary describing the entity's current state.
    No LLM — purely deterministic.
    """
    entity = data["entity"]
    name = entity.get("name", entity.get("slug", "Entity"))
    strat_label = strategy.get("strategy", "Mixed Strategy")
    regime_label = regime.get("regime", "dormant")
    pressure_label = pressure.get("pressure", "neutral")
    conviction_label = conviction.get("conviction", "low")
    stable_dep = token_dep.get("stablecoin_dependency", 0)
    clusters_data = data["clusters"]
    total_discovered = clusters_data.get("total_discovered", 0)

    parts = []

    # Opening: strategy
    parts.append(f"{name} acting as {strat_label.lower()}.")

    # Stablecoin dominance
    if stable_dep >= 0.7:
        parts.append("Stablecoin dominance high.")
    elif stable_dep >= 0.4:
        parts.append("Moderate stablecoin exposure.")

    # Cluster state
    if total_discovered >= 20:
        parts.append("Clusters expanding.")
    elif total_discovered >= 5:
        parts.append("Active cluster network.")

    # Regime signal
    if regime_label == "accumulation":
        parts.append("Accumulation signals detected.")
    elif regime_label == "distribution":
        parts.append("Distribution phase active.")
    elif regime_label == "liquidity":
        parts.append("Liquidity provision mode.")
    elif regime_label == "rotation":
        parts.append("Token rotation in progress.")
    elif regime_label == "dormant":
        parts.append("Currently dormant.")

    # Pressure
    if pressure_label == "bullish":
        parts.append("Buy pressure increasing.")
    elif pressure_label == "bearish":
        parts.append("Sell pressure detected.")

    # Conviction
    if conviction_label in ("high", "extreme"):
        parts.append(f"Conviction level: {conviction_label}.")

    return " ".join(parts)


# ══════════════════════════════════════════════════════════
#  14. UNIFIED INTELLIGENCE ENDPOINT
# ══════════════════════════════════════════════════════════

def get_entity_intelligence(slug: str) -> dict | None:
    """
    Aggregating intelligence endpoint.
    Computes all intelligence layers and returns unified response.
    Saves adaptive snapshot for strategy drift tracking.
    """
    ck = f"entity_intelligence:{slug}"
    cached = _cache_get(ck)
    if cached is not None:
        return cached

    data = _load_entity_data(slug)
    if not data:
        return None

    # Core computations
    pressure = compute_market_pressure(data)
    strategy = compute_actor_strategy(data)
    conviction = compute_actor_conviction(data)
    regime = compute_actor_regime(data)
    playbook = compute_actor_playbook(data)
    cluster_roles = compute_cluster_roles(data)
    token_dep = compute_token_dependency(data)
    actor_impact = compute_actor_impact_score(data)
    token_pressure = compute_token_pressure(data)

    # UX layer
    quick_tags = generate_quick_tags(data, pressure, strategy, conviction, regime)
    highlights = generate_actor_highlights(data, pressure, token_dep, cluster_roles)
    summary = generate_entity_summary(data, pressure, strategy, conviction, regime, token_dep)

    result = {
        "slug": slug,
        "name": data["entity"].get("name", slug),
        "pressure": pressure["pressure"],
        "pressure_detail": pressure,
        "strategy": strategy["strategy"],
        "strategy_detail": strategy,
        "conviction": conviction["conviction"],
        "conviction_detail": conviction,
        "regime": regime["regime"],
        "regime_detail": regime,
        "playbook": playbook["playbook"],
        "playbook_detail": playbook,
        "actor_impact": actor_impact,
        "cluster_roles": cluster_roles,
        "token_dependency": token_dep,
        "token_pressure": token_pressure,
        "quick_tags": quick_tags,
        "highlights": highlights,
        "summary": summary,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    # Save adaptive snapshot for strategy drift
    try:
        save_intelligence_snapshot(slug, result)
    except Exception:
        pass  # Don't break intelligence on snapshot failure

    _cache_set(ck, result)
    return result


# ══════════════════════════════════════════════════════════
#  PHASE D — ACTOR INTELLIGENCE EXTENSIONS
# ══════════════════════════════════════════════════════════

# ──────────────────────────────────────────────
#  D1. ACTOR IMPACT SCORE
# ──────────────────────────────────────────────

# Log normalization thresholds (reasonable market maximums)
_NORM_PORTFOLIO_MAX = 50_000_000_000   # $50B
_NORM_FLOW_MAX = 10_000_000_000        # $10B
_NORM_CLUSTER_MAX = 1000               # 1000 wallets
_NORM_VELOCITY_MAX = 50_000_000        # $50M/day


def _log_normalize(value: float, max_val: float) -> float:
    """Log normalization: log(1+v) / log(1+max), capped at 1.0"""
    if value <= 0 or max_val <= 0:
        return 0.0
    return min(1.0, math.log(1 + value) / math.log(1 + max_val))


def compute_actor_impact_score(data: dict) -> dict:
    """
    Compute unified Actor Impact Score.
    Formula: 0.35*portfolio + 0.30*flow + 0.20*cluster + 0.15*velocity
    Log-normalized to prevent large exchanges from dominating.
    Categories: 0-25 LOW, 25-45 MEDIUM, 45-70 HIGH, 70+ SYSTEMIC
    """
    holdings = data["holdings"]
    flows = data["flows"]
    clusters = data["clusters"]

    portfolio_value = holdings.get("total_value_usd", 0)
    all_time = flows.get("all_time", {})
    flow_volume = all_time.get("inflow_usd", 0) + all_time.get("outflow_usd", 0)
    cluster_coverage = clusters.get("total_discovered", 0)
    velocity = flows.get("flow_velocity", 0)

    # Log-normalized components (0..1)
    norm_portfolio = _log_normalize(portfolio_value, _NORM_PORTFOLIO_MAX)
    norm_flow = _log_normalize(flow_volume, _NORM_FLOW_MAX)
    norm_cluster = _log_normalize(cluster_coverage, _NORM_CLUSTER_MAX)
    norm_velocity = _log_normalize(velocity, _NORM_VELOCITY_MAX)

    # Weighted sum → 0..100
    raw_score = (
        0.35 * norm_portfolio
        + 0.30 * norm_flow
        + 0.20 * norm_cluster
        + 0.15 * norm_velocity
    ) * 100

    score = round(max(0, min(100, raw_score)))

    if score >= 70:
        category = "SYSTEMIC"
    elif score >= 45:
        category = "HIGH"
    elif score >= 25:
        category = "MEDIUM"
    else:
        category = "LOW"

    drivers = []
    if norm_portfolio >= 0.5:
        drivers.append(f"Portfolio: {_fmt_usd(portfolio_value)}")
    if norm_flow >= 0.5:
        drivers.append(f"Flow volume: {_fmt_usd(flow_volume)}")
    if norm_cluster >= 0.5:
        drivers.append(f"Cluster coverage: {cluster_coverage} wallets")
    if norm_velocity >= 0.5:
        drivers.append(f"Velocity: {_fmt_usd(velocity)}/day")

    return {
        "impact_score": score,
        "impact_category": category,
        "components": {
            "portfolio": round(norm_portfolio * 100),
            "flow": round(norm_flow * 100),
            "cluster": round(norm_cluster * 100),
            "velocity": round(norm_velocity * 100),
        },
        "drivers": drivers,
    }


# ──────────────────────────────────────────────
#  D2. STRATEGY DRIFT TRACKING
# ──────────────────────────────────────────────

def _get_current_state_key(intelligence: dict) -> str:
    """Create a hashable key from the current intelligence state."""
    return "|".join([
        intelligence.get("strategy", ""),
        intelligence.get("pressure", ""),
        intelligence.get("regime", ""),
        intelligence.get("conviction", ""),
        intelligence.get("actor_impact", {}).get("impact_category", ""),
    ])


def save_intelligence_snapshot(slug: str, intelligence: dict):
    """
    Save an adaptive snapshot: only writes when state changes.
    Compares current state with last saved state.
    """
    db = _get_db()
    coll = db["entity_intelligence_history"]

    # Get last snapshot
    last = coll.find_one(
        {"entity": slug},
        {"_id": 0},
        sort=[("timestamp", -1)],
    )

    current_state = {
        "strategy": intelligence.get("strategy", ""),
        "pressure": intelligence.get("pressure", ""),
        "regime": intelligence.get("regime", ""),
        "conviction": intelligence.get("conviction", ""),
        "impact": intelligence.get("actor_impact", {}).get("impact_category", ""),
    }

    # Check if state changed
    if last:
        last_state = {
            "strategy": last.get("strategy", ""),
            "pressure": last.get("pressure", ""),
            "regime": last.get("regime", ""),
            "conviction": last.get("conviction", ""),
            "impact": last.get("impact", ""),
        }
        if current_state == last_state:
            return False  # No change, skip

    # Save new snapshot
    doc = {
        "entity": slug,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **current_state,
    }
    coll.insert_one(doc)
    return True


def get_strategy_history(slug: str, limit: int = 20) -> list[dict]:
    """Get strategy drift timeline for an entity (most recent first)."""
    db = _get_db()
    coll = db["entity_intelligence_history"]

    cursor = coll.find(
        {"entity": slug},
        {"_id": 0},
        sort=[("timestamp", -1)],
        limit=limit,
    )
    return list(cursor)


# ──────────────────────────────────────────────
#  D3. PRESSURE BY TOKEN
# ──────────────────────────────────────────────

def compute_token_pressure(data: dict) -> list[dict]:
    """
    Per-token pressure analysis.
    Combines flow_direction + token_role + velocity for each token.
    Output: list of {symbol, pressure, direction_score, role, velocity_score}
    """
    matrix = data["matrix"]
    flows = data["flows"]
    tokens = matrix.get("tokens", [])
    total_vol = matrix.get("total_flow_volume_usd", 0)

    if not tokens:
        return []

    flow_velocity = flows.get("flow_velocity", 0)
    global_velocity_high = flow_velocity >= 500_000

    result = []
    for t in tokens:
        symbol = t.get("symbol", "?")
        vol = t.get("flow_volume_usd", 0) or t.get("volume_usd", 0)
        role = t.get("role", "neutral_token")
        dominance = t.get("dominance_pct", 0)

        # Skip negligible tokens
        if vol <= 0 and dominance <= 0.01:
            continue

        # Signal 1: Flow direction from token role
        if role == "accumulation_token":
            direction_score = 30
        elif role == "distribution_token":
            direction_score = -30
        elif role == "liquidity_token":
            direction_score = 5
        else:
            direction_score = 0

        # Signal 2: Token role weight
        if role == "accumulation_token":
            role_score = 20
        elif role == "distribution_token":
            role_score = -20
        else:
            role_score = 0

        # Signal 3: Velocity amplifier
        velocity_score = 0
        if global_velocity_high and dominance >= 0.1:
            velocity_score = 10 if direction_score > 0 else -10 if direction_score < 0 else 0

        total_score = direction_score + role_score + velocity_score

        if total_score >= 20:
            pressure = "bullish"
        elif total_score <= -20:
            pressure = "bearish"
        else:
            pressure = "neutral"

        result.append({
            "symbol": symbol,
            "pressure": pressure,
            "score": total_score,
            "role": role.replace("_token", ""),
            "dominance": round(dominance, 4),
            "volume_usd": round(vol, 2),
        })

    # Sort by volume descending
    result.sort(key=lambda x: x["volume_usd"], reverse=True)
    return result[:15]  # Cap at top 15 tokens


# ──────────────────────────────────────────────
#  D4. ACTOR INTERACTION MAP
# ──────────────────────────────────────────────

def get_actor_flows() -> dict:
    """
    Cross-entity capital flow map.
    Analyzes flows between known entities to show capital routing.
    """
    ck = "actor_flows_map"
    cached = _cache_get(ck)
    if cached is not None:
        return cached

    db = _get_db()

    # Load all entities
    entities = list(db["entities_v2"].find({}, {"_id": 0, "slug": 1, "name": 1, "type": 1}))
    entity_slugs = {e["slug"] for e in entities}
    entity_names = {e["slug"]: e.get("name", e["slug"]) for e in entities}
    entity_types = {e["slug"]: e.get("type", "unknown") for e in entities}

    interactions = []

    # For each entity, check its interaction network for connections to other entities
    for entity in entities:
        slug = entity["slug"]
        inter = db["entity_interactions_v2"].find_one(
            {"$or": [{"slug": slug}, {"entity_slug": slug}]},
            {"_id": 0},
        )
        if not inter:
            continue

        # Look for entity-type nodes in the interaction graph
        nodes = inter.get("nodes", [])
        edges = inter.get("edges", [])

        for edge in edges:
            target_id = edge.get("target", "")
            target_node = next((n for n in nodes if n.get("id") == target_id), None)
            if not target_node:
                continue

            # Check if target is a known entity
            target_slug = target_node.get("id", "").lower().replace(" ", "-")
            target_type = target_node.get("type", "")

            if target_type == "entity" or target_slug in entity_slugs:
                # Determine interaction type
                edge_type = edge.get("type", "entity_flow")
                if "exchange" in edge_type:
                    interaction_type = "exchange_flow"
                elif "dex" in edge_type or "uniswap" in target_slug or "aave" in target_slug:
                    interaction_type = "dex_flow"
                elif "bridge" in edge_type:
                    interaction_type = "bridge_flow"
                else:
                    interaction_type = "entity_to_entity"

                interactions.append({
                    "from": slug,
                    "from_name": entity_names.get(slug, slug),
                    "to": target_slug,
                    "to_name": target_node.get("label", target_slug),
                    "volume_usd": edge.get("volume_usd", 0),
                    "tokens": edge.get("tokens", []),
                    "type": interaction_type,
                    "label": edge.get("label", ""),
                })

    # If no interaction data found, build from flow overlap analysis
    if not interactions:
        interactions = _build_flow_overlap_interactions(entities, db)

    # Sort by volume
    interactions.sort(key=lambda x: x.get("volume_usd", 0), reverse=True)

    # Enrich with wallet addresses
    all_slugs = set()
    for ix in interactions:
        all_slugs.add(ix["from"])
        all_slugs.add(ix.get("to", ""))
    slug_addrs = {}
    for slug in all_slugs:
        if slug:
            addrs = [
                doc["address"].lower()
                for doc in db["entity_addresses_v2"].find(
                    {"entity_slug": slug}, {"_id": 0, "address": 1}
                ).limit(3)
                if doc.get("address")
            ]
            if addrs:
                slug_addrs[slug] = addrs
    for ix in interactions:
        ix["from_wallets"] = slug_addrs.get(ix["from"], [])[:3]
        ix["to_wallets"] = slug_addrs.get(ix.get("to", ""), [])[:3]

    result = {
        "interactions": interactions[:30],
        "entity_count": len(entities),
        "total_interactions": len(interactions),
    }

    _cache_set(ck, result, ttl=_CACHE_TTL_SHORT)
    return result


def _build_flow_overlap_interactions(entities: list, db) -> list:
    """
    Fallback: build interactions from flow pattern analysis.
    If entities share similar token profiles and overlapping flow windows,
    they likely interact.
    """
    interactions = []
    entity_flows = {}

    # Load flow data for all entities
    for e in entities:
        slug = e["slug"]
        flow = db["entity_flows_v2"].find_one(
            {"$or": [{"slug": slug}, {"entity_slug": slug}]},
            {"_id": 0},
        )
        if flow:
            entity_flows[slug] = flow

    slugs = list(entity_flows.keys())

    for i, slug_a in enumerate(slugs):
        flow_a = entity_flows[slug_a]
        vol_a = (flow_a.get("all_time", {}).get("inflow_usd", 0)
                 + flow_a.get("all_time", {}).get("outflow_usd", 0))

        for slug_b in slugs[i + 1:]:
            flow_b = entity_flows[slug_b]
            vol_b = (flow_b.get("all_time", {}).get("inflow_usd", 0)
                     + flow_b.get("all_time", {}).get("outflow_usd", 0))

            # Estimate interaction volume as overlap
            min_vol = min(vol_a, vol_b)
            if min_vol <= 0:
                continue

            # Determine type based on entity types
            type_a = next((e.get("type", "") for e in entities if e["slug"] == slug_a), "")
            type_b = next((e.get("type", "") for e in entities if e["slug"] == slug_b), "")

            if type_a == "exchange" and type_b == "exchange":
                itype = "exchange_flow"
                overlap_ratio = 0.15
            elif "protocol" in (type_a, type_b):
                itype = "dex_flow"
                overlap_ratio = 0.10
            else:
                itype = "entity_to_entity"
                overlap_ratio = 0.05

            est_volume = min_vol * overlap_ratio
            if est_volume < 10_000:
                continue

            name_a = next((e.get("name", slug_a) for e in entities if e["slug"] == slug_a), slug_a)
            name_b = next((e.get("name", slug_b) for e in entities if e["slug"] == slug_b), slug_b)

            interactions.append({
                "from": slug_a,
                "from_name": name_a,
                "to": slug_b,
                "to_name": name_b,
                "volume_usd": round(est_volume, 2),
                "tokens": [],
                "type": itype,
                "label": f"~{_fmt_usd(est_volume)}",
            })

    return interactions


# ──────────────────────────────────────────────
#  D5. ACTOR vs ACTOR PRESSURE MAP
# ──────────────────────────────────────────────

def get_pressure_map() -> dict:
    """
    Aggregate pressure across all entities with impact weight.
    Returns bullish/bearish/neutral actor lists.
    """
    ck = "actor_pressure_map"
    cached = _cache_get(ck)
    if cached is not None:
        return cached

    db = _get_db()
    entities = list(db["entities_v2"].find({}, {"_id": 0, "slug": 1, "name": 1, "type": 1}))

    bullish = []
    bearish = []
    neutral = []

    for entity in entities:
        slug = entity["slug"]
        data = _load_entity_data(slug)
        if not data:
            continue

        pressure = compute_market_pressure(data)
        impact = compute_actor_impact_score(data)
        strategy = compute_actor_strategy(data)

        entry = {
            "entity": slug,
            "name": entity.get("name", slug),
            "type": entity.get("type", "unknown"),
            "pressure": pressure["pressure"],
            "pressure_score": pressure["score"],
            "impact": impact["impact_category"],
            "impact_score": impact["impact_score"],
            "strategy": strategy["strategy"],
            "drivers": pressure["drivers"][:3],
        }

        if pressure["pressure"] == "bullish":
            bullish.append(entry)
        elif pressure["pressure"] == "bearish":
            bearish.append(entry)
        else:
            neutral.append(entry)

    # Sort by impact score descending
    bullish.sort(key=lambda x: x["impact_score"], reverse=True)
    bearish.sort(key=lambda x: x["impact_score"], reverse=True)
    neutral.sort(key=lambda x: x["impact_score"], reverse=True)

    result = {
        "bullish_entities": bullish,
        "bearish_entities": bearish,
        "neutral_entities": neutral,
        "total_entities": len(entities),
        "bullish_count": len(bullish),
        "bearish_count": len(bearish),
        "neutral_count": len(neutral),
    }

    _cache_set(ck, result, ttl=_CACHE_TTL_SHORT)
    return result


# ──────────────────────────────────────────────
#  Helper: USD formatter
# ──────────────────────────────────────────────

def _fmt_usd(v):
    if not v:
        return "$0"
    a = abs(v)
    if a >= 1e9:
        return f"${v / 1e9:.2f}B"
    if a >= 1e6:
        return f"${v / 1e6:.2f}M"
    if a >= 1e3:
        return f"${v / 1e3:.1f}K"
    return f"${v:.0f}"