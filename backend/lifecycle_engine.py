"""
Lifecycle Engine — Real asset lifecycle computation from exchange data.

Phases: ACCUMULATION → IGNITION → EXPANSION → DISTRIBUTION

Data sources:
  - exchange_market_context: 10 symbols with 6 axes (Binance real data)
  - exchangemarketsnapshots: 106 tokens with change24h, volatility
  - entity_signals: project-level sentiment + velocity
"""

import math
import os
from datetime import datetime, timezone
from collections import defaultdict
import pymongo

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    return _client


def _ie():
    return _get_client()["intelligence_engine"]


def _cdb():
    return _get_client()["connections_db"]


# ─── PHASE SCORING ────────────────────────────────────────
# Uses real Binance axes: momentum, structure, participation,
# orderbookPressure, positioning, marketStress

def score_accumulation(axes: dict) -> float:
    """Flat price, growing interest, low volatility."""
    mom = axes.get("momentum", 0)
    struct = axes.get("structure", 0)
    part = axes.get("participation", 0)
    stress = axes.get("marketStress", 0)
    pos = axes.get("positioning", 0)

    flat_momentum = max(0, 1 - abs(mom) * 3)  # peaks at mom=0
    growing_interest = max(0, min(1, part))
    low_stress = max(0, 1 - stress * 2)
    neutral_positioning = max(0, 1 - abs(pos - 0.5) * 3)
    stable_structure = max(0, 1 - abs(struct) * 1.5)

    return (
        0.30 * flat_momentum
        + 0.25 * growing_interest
        + 0.20 * low_stress
        + 0.15 * neutral_positioning
        + 0.10 * stable_structure
    )


def score_ignition(axes: dict) -> float:
    """Breakout: positive momentum, participation rising."""
    mom = axes.get("momentum", 0)
    part = axes.get("participation", 0)
    pos = axes.get("positioning", 0)
    stress = axes.get("marketStress", 0)
    ob = axes.get("orderbookPressure", 0)

    pos_momentum = max(0, min(1, mom * 1.5))
    high_participation = max(0, min(1, part))
    active_positioning = max(0, min(1, pos))
    moderate_stress = max(0, min(1, stress * 2))
    orderbook_buy = max(0, min(1, ob * 5 + 0.5))

    return (
        0.30 * pos_momentum
        + 0.25 * high_participation
        + 0.20 * active_positioning
        + 0.15 * moderate_stress
        + 0.10 * orderbook_buy
    )


def score_expansion(axes: dict) -> float:
    """FOMO: high momentum, extreme participation, high stress."""
    mom = axes.get("momentum", 0)
    part = axes.get("participation", 0)
    pos = axes.get("positioning", 0)
    stress = axes.get("marketStress", 0)

    high_momentum = max(0, min(1, mom * 1.2))
    extreme_participation = max(0, min(1, (part - 0.3) * 2))
    high_positioning = max(0, min(1, pos))
    high_stress = max(0, min(1, stress * 2.5))
    momentum_x_participation = max(0, min(1, mom * part * 2))

    return (
        0.30 * high_momentum
        + 0.25 * extreme_participation
        + 0.20 * high_stress
        + 0.15 * high_positioning
        + 0.10 * momentum_x_participation
    )


def score_distribution(axes: dict) -> float:
    """Top: negative momentum, declining structure, high stress."""
    mom = axes.get("momentum", 0)
    struct = axes.get("structure", 0)
    part = axes.get("participation", 0)
    stress = axes.get("marketStress", 0)
    ob = axes.get("orderbookPressure", 0)

    neg_momentum = max(0, min(1, -mom * 1.5))
    neg_structure = max(0, min(1, -struct * 1.2))
    declining_part = max(0, min(1, 1 - part))
    high_stress = max(0, min(1, stress * 2))
    sell_pressure = max(0, min(1, 0.5 - ob * 5))

    return (
        0.30 * neg_momentum
        + 0.25 * neg_structure
        + 0.20 * high_stress
        + 0.15 * declining_part
        + 0.10 * sell_pressure
    )


def compute_lifecycle(axes: dict) -> dict:
    """Compute all 4 phase scores and determine state."""
    scores = {
        "accumulation": round(score_accumulation(axes), 3),
        "ignition": round(score_ignition(axes), 3),
        "expansion": round(score_expansion(axes), 3),
        "distribution": round(score_distribution(axes), 3),
    }

    # Normalize to sum=1
    total = sum(scores.values()) or 1
    scores = {k: round(v / total, 3) for k, v in scores.items()}

    # Determine dominant phase
    best = max(scores, key=scores.get)
    state = best.upper()
    confidence = scores[best]

    return {"scores": scores, "state": state, "confidence": round(confidence, 3)}


# ─── SNAPSHOT-BASED LIFECYCLE (for tokens without full context) ──

def lifecycle_from_snapshot(change24h: float, volatility: float) -> dict:
    """Infer lifecycle from price change and volatility."""
    pc = change24h or 0
    vol = abs(volatility or 0)

    scores = {
        "accumulation": 0.0,
        "ignition": 0.0,
        "expansion": 0.0,
        "distribution": 0.0,
    }

    if abs(pc) < 3 and vol < 0.3:
        scores["accumulation"] = 0.6
        scores["ignition"] = 0.15
        scores["expansion"] = 0.1
        scores["distribution"] = 0.15
    elif pc > 10 and vol > 0.3:
        scores["expansion"] = 0.5
        scores["ignition"] = 0.3
        scores["accumulation"] = 0.1
        scores["distribution"] = 0.1
    elif pc > 3:
        scores["ignition"] = 0.5
        scores["accumulation"] = 0.2
        scores["expansion"] = 0.2
        scores["distribution"] = 0.1
    elif pc < -5:
        scores["distribution"] = 0.5
        scores["accumulation"] = 0.2
        scores["ignition"] = 0.1
        scores["expansion"] = 0.2
    else:
        scores["accumulation"] = 0.35
        scores["distribution"] = 0.3
        scores["ignition"] = 0.2
        scores["expansion"] = 0.15

    best = max(scores, key=scores.get)
    return {"scores": scores, "state": best.upper(), "confidence": round(scores[best], 3)}


# ─── CLUSTER GROUPING ────────────────────────────────────────

CLUSTER_MAP = {
    "Layer 1": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT"],
    "Layer 2": ["XRPUSDT", "LINKUSDT"],
    "Meme": ["DOGEUSDT"],
}

# Reverse map
SYMBOL_CLUSTER = {}
for cluster, symbols in CLUSTER_MAP.items():
    for s in symbols:
        SYMBOL_CLUSTER[s] = cluster


def build_cluster_lifecycle(asset_states: list) -> list:
    """Aggregate asset lifecycles into cluster lifecycles."""
    clusters = defaultdict(list)

    for asset in asset_states:
        cluster = asset.get("cluster", "Other")
        clusters[cluster].append(asset)

    result = []
    for name, assets in clusters.items():
        if not assets:
            continue

        # Weighted average of scores by confidence
        agg_scores = {"accumulation": 0, "ignition": 0, "expansion": 0, "distribution": 0}
        total_w = 0
        for a in assets:
            w = a.get("confidence", 0.5)
            total_w += w
            for phase in agg_scores:
                agg_scores[phase] += a["scores"].get(phase, 0) * w

        if total_w > 0:
            agg_scores = {k: round(v / total_w, 3) for k, v in agg_scores.items()}

        best = max(agg_scores, key=agg_scores.get)

        result.append({
            "cluster": name,
            "state": best.upper(),
            "confidence": round(agg_scores[best], 3),
            "scores": agg_scores,
            "assetCount": len(assets),
            "window": "24h",
            "assets": [a["asset"] for a in assets],
        })

    result.sort(key=lambda x: -x["confidence"])
    return result


# ─── EARLY ROTATION DETECTION ────────────────────────────────

def detect_rotations(cluster_states: list) -> list:
    """Detect capital rotation between clusters."""
    rotations = []

    for i, source in enumerate(cluster_states):
        for target in cluster_states[i + 1:]:
            # Source in DISTRIBUTION + target in ACCUMULATION/IGNITION = rotation
            src_dist = source["scores"].get("distribution", 0)
            tgt_acc = target["scores"].get("accumulation", 0) + target["scores"].get("ignition", 0)

            tgt_dist = target["scores"].get("distribution", 0)
            src_acc = source["scores"].get("accumulation", 0) + source["scores"].get("ignition", 0)

            # Check both directions
            for from_c, to_c, from_decay, to_tension in [
                (source, target, src_dist, tgt_acc),
                (target, source, tgt_dist, src_acc),
            ]:
                if from_decay < 0.2 or to_tension < 0.3:
                    continue

                erp = 0.5 * to_tension + 0.3 * from_decay + 0.2 * abs(to_tension - from_decay)
                erp = round(min(1, erp), 3)

                if erp < 0.35:
                    continue

                erp_class = "IMMINENT" if erp >= 0.75 else "BUILDING" if erp >= 0.6 else "WATCH"

                rotations.append({
                    "fromCluster": from_c["cluster"],
                    "toCluster": to_c["cluster"],
                    "erp": erp,
                    "class": erp_class,
                    "tensionScore": round(to_tension, 3),
                    "window": "24h",
                    "notes": {
                        "volatility": "compressed" if to_tension > 0.6 else "normal",
                        "funding": "diverging" if erp > 0.5 else "neutral",
                        "opportunityGrowth": f"+{int(to_tension * 30)}%",
                        "failedBreakouts": 0,
                    },
                })

    rotations.sort(key=lambda x: -x["erp"])
    return rotations


# ─── ENRICHMENT WITH ENTITY SIGNALS ──────────────────────────

SYMBOL_TO_ENTITY = {
    "BTCUSDT": "bitcoin", "ETHUSDT": "ethereum", "SOLUSDT": "solana",
    "BNBUSDT": "bnb", "DOGEUSDT": "dogecoin", "XRPUSDT": "xrp",
    "ADAUSDT": "cardano", "DOTUSDT": "polkadot", "AVAXUSDT": "avalanche",
    "LINKUSDT": "chainlink",
}


def enrich_with_entity_signals(asset_states: list, entity_map: dict) -> list:
    """Add sentiment and velocity from entity_signals."""
    for asset in asset_states:
        sym = asset.get("symbol", "")
        entity_id = SYMBOL_TO_ENTITY.get(sym, "")
        if entity_id and entity_id in entity_map:
            ent = entity_map[entity_id]
            asset["sentiment"] = ent.get("sentiment", 0)
            asset["velocity"] = ent.get("velocity", 0)
            asset["entityLabel"] = ent.get("label", entity_id)
    return asset_states


# ─── MAIN PIPELINE ────────────────────────────────────────────

def run_lifecycle_pipeline() -> dict:
    ie = _ie()
    cdb = _cdb()

    # 1. Load exchange_market_context (10 symbols with full axes)
    contexts = list(ie.exchange_market_context.find({}, {"_id": 0}))

    # 2. Load exchange snapshots (106 tokens)
    snapshots = list(ie.exchangemarketsnapshots.find({}, {"_id": 0}))
    snap_map = {s["symbol"]: s for s in snapshots}

    # 3. Load entity signals for enrichment
    entity_signals_raw = list(ie.entity_signals.find(
        {"entityType": "project"},
        {"_id": 0, "entityId": 1, "entityLabel": 1, "sentiment": 1,
         "features": 1, "importanceScore": 1}
    ))
    entity_map = {}
    for es in entity_signals_raw:
        eid = es.get("entityId", "")
        nv = es.get("features", {}).get("newsVelocity", 0)
        tv = es.get("features", {}).get("twitterVelocity", 0)
        entity_map[eid] = {
            "label": es.get("entityLabel", eid),
            "sentiment": es.get("sentiment", 0),
            "velocity": nv + tv,
            "importance": es.get("importanceScore", 0),
        }

    # 4. Compute asset lifecycles from exchange context (high quality)
    asset_states = []
    processed_symbols = set()

    for ctx in contexts:
        symbol = ctx.get("symbol", "")
        axes = ctx.get("axes", {})
        regime = ctx.get("regime", {})

        lc = compute_lifecycle(axes)
        snap = snap_map.get(symbol, {})

        asset_states.append({
            "asset": symbol.replace("USDT", ""),
            "symbol": symbol,
            "state": lc["state"],
            "confidence": lc["confidence"],
            "scores": lc["scores"],
            "window": "24h",
            "dataQuality": "full",
            "priceChange24h": round(snap.get("change24h", 0) or 0, 2),
            "volatility": round(snap.get("volatility", 0) or 0, 3),
            "regime": regime.get("type", {}).get("type", "NEUTRAL") if isinstance(regime.get("type"), dict) else regime.get("type", "NEUTRAL"),
            "cluster": SYMBOL_CLUSTER.get(symbol, "Other"),
        })
        processed_symbols.add(symbol)

    # 5. Add remaining snapshots (lower quality — price/vol only)
    for snap in snapshots:
        symbol = snap.get("symbol", "")
        if symbol in processed_symbols or not symbol:
            continue

        pc = snap.get("change24h", 0) or 0
        vol = snap.get("volatility", 0) or 0
        lc = lifecycle_from_snapshot(pc, vol)
        clean = symbol.replace("USDT", "").replace("1000", "").replace("000", "")

        asset_states.append({
            "asset": clean,
            "symbol": symbol,
            "state": lc["state"],
            "confidence": lc["confidence"],
            "scores": lc["scores"],
            "window": "24h",
            "dataQuality": "snapshot",
            "priceChange24h": round(pc, 2),
            "volatility": round(abs(vol), 3),
            "cluster": "Alt",
        })
        processed_symbols.add(symbol)

    # 6. Enrich with entity signals
    asset_states = enrich_with_entity_signals(asset_states, entity_map)

    # Sort by confidence
    asset_states.sort(key=lambda x: -x["confidence"])

    # 7. Build cluster lifecycles
    cluster_states = build_cluster_lifecycle(asset_states)

    # 8. Detect rotations
    rotations = detect_rotations(cluster_states)

    # 9. Stats
    phase_counts = {"ACCUMULATION": 0, "IGNITION": 0, "EXPANSION": 0, "DISTRIBUTION": 0}
    for a in asset_states:
        phase_counts[a["state"]] = phase_counts.get(a["state"], 0) + 1

    # 10. Decision layer — score + action for each asset
    btc_return = 0
    for a in asset_states:
        if a.get("symbol") == "BTCUSDT":
            btc_return = a.get("priceChange24h", 0)
            break

    twitter_data = _load_twitter_token_data()

    for a in asset_states:
        sym = a["asset"]
        tw = twitter_data.get(sym, {})
        a["mentions"] = tw.get("mentions", 0)
        a["mentionsGrowth"] = tw.get("velocity", 0)
        a["uniqueAuthors"] = tw.get("uniqueAuthors", 0)
        a["engagementRate"] = tw.get("engagement", 0)

        decision = compute_decision(a, btc_return)
        a["score"] = decision["score"]
        a["action"] = decision["action"]
        a["entry"] = decision["entry"]

    # Sort by score (best opportunities first)
    asset_states.sort(key=lambda x: -x["score"])

    # 11. Early pump detector
    pump_signals = detect_early_pumps(asset_states, btc_return)

    # 12. Dominant state
    dominant_phase = max(phase_counts, key=phase_counts.get)
    dominant_count = phase_counts[dominant_phase]

    market_action = _market_action(dominant_phase, phase_counts)

    return {
        "assets": asset_states,
        "clusters": cluster_states,
        "rotations": rotations,
        "pumpSignals": pump_signals,
        "marketState": {
            "dominant": dominant_phase,
            "dominantCount": dominant_count,
            "action": market_action,
            "phaseCounts": phase_counts,
        },
        "stats": {
            "totalAssets": len(asset_states),
            "totalClusters": len(cluster_states),
            "phaseCounts": phase_counts,
            "computedAt": datetime.now(timezone.utc).isoformat(),
        },
    }


# ─── TWITTER TOKEN DATA ──────────────────────────────────────

def _load_twitter_token_data() -> dict:
    """Load twitter mentions per token for scoring."""
    import re
    ie = _ie()
    cdb = _cdb()

    token_re = re.compile(r"\$([A-Z]{2,10})")
    token_data = {}

    # From twitter_results
    tweets = list(ie.twitter_results.find({}, {"_id": 0, "text": 1, "username": 1, "likes": 1, "retweets": 1}))
    from collections import defaultdict
    stats = defaultdict(lambda: {"mentions": 0, "authors": set(), "engagement": 0})
    for tw in tweets:
        text = (tw.get("text") or "").upper()
        tokens = set(token_re.findall(text))
        eng = (tw.get("likes") or 0) + (tw.get("retweets") or 0)
        for t in tokens:
            if t in ("BTC", "BITCOIN", "USDT", "USD", "CRYPTO"):
                continue
            stats[t]["mentions"] += 1
            stats[t]["authors"].add((tw.get("username") or "").lower())
            stats[t]["engagement"] += eng

    # From token velocity
    for doc in cdb.twitter_token_velocity_hourly.find({}, {"_id": 0}):
        sym = (doc.get("token") or "").upper()
        if sym in stats:
            stats[sym]["mentions"] += doc.get("mentions", 0) or 0
            stats[sym]["velocity"] = doc.get("zVelocity", 0) or 0

    for sym, s in stats.items():
        n = max(1, s["mentions"])
        token_data[sym] = {
            "mentions": s["mentions"],
            "uniqueAuthors": len(s["authors"]),
            "engagement": round(s["engagement"] / n, 2),
            "velocity": s.get("velocity", min(s["mentions"] / 30.0, 2.0)),
        }

    return token_data


# ─── DECISION SCORING ─────────────────────────────────────────

PHASE_WEIGHT = {
    "ACCUMULATION": 0.6,
    "IGNITION": 1.0,
    "EXPANSION": 0.7,
    "DISTRIBUTION": 0.2,
}


def _normalize(value, vmin, vmax):
    if value <= vmin:
        return 0.0
    if value >= vmax:
        return 1.0
    return (value - vmin) / (vmax - vmin)


def compute_decision(asset: dict, btc_return: float) -> dict:
    """Score + Action + Entry for an asset."""
    phase = asset.get("state", "NEUTRAL").upper()
    pc24 = asset.get("priceChange24h", 0)
    vol = asset.get("volatility", 0)
    mentions_growth = asset.get("mentionsGrowth", 0)
    eng = asset.get("engagementRate", 0)

    # Momentum score
    momentum = (
        _normalize(pc24, 0, 20) * 0.35
        + _normalize(abs(vol) * 100, 0, 100) * 0.25
        + _normalize(mentions_growth, 0, 3) * 0.25
        + _normalize(eng, 0, 10) * 0.15
    )
    if pc24 < 0:
        momentum *= 0.4

    # Phase weight
    pw = PHASE_WEIGHT.get(phase, 0.5)

    # Relative strength vs BTC
    rs = pc24 - btc_return
    rs_score = _normalize(rs, -10, 20)

    # Final score
    score = momentum * 0.5 + pw * 0.3 + rs_score * 0.2
    score = max(0, min(1, score))

    # Action
    action = _get_action(score, phase)

    # Entry type
    entry = _get_entry(phase)

    return {
        "score": round(score, 3),
        "action": action,
        "entry": entry,
    }


def _get_action(score: float, phase: str) -> str:
    if phase == "DISTRIBUTION":
        return "EXIT"
    if score > 0.75 and phase == "IGNITION":
        return "STRONG BUY"
    if score > 0.6:
        return "BUY"
    if score > 0.45:
        return "HOLD"
    return "AVOID"


def _get_entry(phase: str) -> str:
    return {
        "ACCUMULATION": "EARLY",
        "IGNITION": "BREAKOUT",
        "EXPANSION": "LATE",
        "DISTRIBUTION": "NO ENTRY",
    }.get(phase, "NEUTRAL")


def _market_action(dominant: str, counts: dict) -> dict:
    """Generate market-level action advice."""
    actions_map = {
        "IGNITION": {
            "headline": "Momentum phase active",
            "do": ["Enter momentum plays", "Focus on high velocity tokens", "Watch for breakout confirmations"],
            "dont": ["Avoid lagging sectors", "Don't chase 24h+ pumps", "Skip distribution phase tokens"],
        },
        "EXPANSION": {
            "headline": "Trend expansion in progress",
            "do": ["Scale into winners", "Hold momentum positions", "Watch for distribution signals"],
            "dont": ["Don't open new large positions", "Avoid FOMO entries", "Start taking partial profits"],
        },
        "ACCUMULATION": {
            "headline": "Market building base",
            "do": ["Identify early narratives", "Build positions slowly", "Watch for ignition triggers"],
            "dont": ["Don't expect quick gains", "Avoid leverage", "Skip low-liquidity tokens"],
        },
        "DISTRIBUTION": {
            "headline": "Smart money exiting",
            "do": ["Take profits", "Reduce exposure", "Move to stables"],
            "dont": ["Don't open new longs", "Avoid dip buying", "Don't ignore warning signs"],
        },
    }
    return actions_map.get(dominant, actions_map["ACCUMULATION"])


# ─── EARLY PUMP DETECTOR ──────────────────────────────────────
# Formula: pumpScore = velocity * 0.5 + unique * 0.3 + phase * 0.2
# velocity = mentions relative to baseline (avg across tokens)
# unique = uniqueAuthors / mentions (anti-bot filter)
# phase = lifecycle phase boost

def detect_early_pumps(assets: list, btc_return: float) -> list:
    """Find tokens with early pump signals using velocity + unique + phase."""
    # Compute baseline: average mentions across all tokens with data
    all_mentions = [a.get("mentions", 0) for a in assets if a.get("mentions", 0) > 0]
    if not all_mentions:
        return []
    avg_mentions = sum(all_mentions) / len(all_mentions)
    if avg_mentions < 1:
        avg_mentions = 1

    # Also load hourly velocity data for richer signal
    try:
        cdb = _cdb()
        vel_docs = {d["token"]: d for d in cdb.twitter_token_velocity_hourly.find({}, {"_id": 0})}
    except Exception:
        vel_docs = {}

    signals = []

    for a in assets:
        phase = a.get("state", "")
        mentions = a.get("mentions", 0)
        unique_authors = a.get("uniqueAuthors", 0)

        # Skip tokens without twitter signal
        if mentions < 2:
            # Check hourly velocity data as fallback
            vel_doc = vel_docs.get(a["asset"], {})
            vel_mentions = vel_doc.get("mentions", 0)
            if vel_mentions < 10:
                continue
            # Use velocity data
            mentions = vel_mentions
            unique_authors = max(1, unique_authors)

        # Skip distribution
        if phase == "DISTRIBUTION":
            continue

        # 1. Velocity: mentions relative to baseline
        velocity = mentions / avg_mentions
        if velocity > 3:
            velocity_score = 1.0
        elif velocity > 2:
            velocity_score = 0.7
        elif velocity > 1.5:
            velocity_score = 0.4
        else:
            velocity_score = 0.0

        # 2. Unique ratio: anti-bot filter
        unique_ratio = unique_authors / max(1, mentions)
        if unique_ratio > 0.7:
            unique_score = 1.0
        elif unique_ratio > 0.5:
            unique_score = 0.7
        else:
            unique_score = 0.3

        # 3. Phase boost
        phase_map = {"IGNITION": 1.0, "ACCUMULATION": 0.6, "EXPANSION": 0.3}
        phase_score = phase_map.get(phase, 0)

        # Final pump score
        pump_score = velocity_score * 0.5 + unique_score * 0.3 + phase_score * 0.2

        if pump_score < 0.4:
            continue

        # Entry window based on velocity + phase
        if velocity > 2.5 and phase == "IGNITION":
            entry = "EARLY"
        elif velocity > 2 and phase == "IGNITION":
            entry = "OPEN"
        elif phase == "EXPANSION":
            entry = "LATE"
        else:
            entry = "AVOID"

        signals.append({
            "symbol": a["asset"],
            "score": round(pump_score, 2),
            "velocity": round(velocity, 2),
            "unique": round(unique_ratio, 2),
            "phase": phase,
            "entry": entry,
        })

    signals.sort(key=lambda x: -x["score"])
    return signals[:10]
