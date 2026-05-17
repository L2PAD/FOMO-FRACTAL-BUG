"""
Alt Alpha Engine — Real-time alt season intelligence from actual market data.

Data sources:
  - intelligence_engine.exchangemarketsnapshots  (106 tokens, 24h changes)
  - intelligence_engine.exchange_market_context   (BTC/ETH/SOL axes from Binance)
  - intelligence_engine.twitter_results           (470 tweets, token mentions)
  - intelligence_engine.market_data               (CoinGecko top 200)
  - connections_db.influencer_clusters            (5 clusters)
  - connections_db.twitter_token_velocity_hourly  (token velocity)
  - connections_db.connections_unified_accounts   (influencer profiles)
  - intelligence_engine.audience_quality          (bot scores)
"""

import math
import re
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
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


# ─── DATA LOADER ─────────────────────────────────────────

def load_data() -> dict:
    ie = _ie()
    cdb = _cdb()

    # 1. Exchange snapshots — all alt 24h changes
    snapshots = list(ie.exchangemarketsnapshots.find({}, {"_id": 0}))
    
    # 2. Exchange market context — BTC/ETH/SOL axes from Binance
    contexts = {
        doc["symbol"]: doc
        for doc in ie.exchange_market_context.find({}, {"_id": 0})
    }

    # 3. Twitter results — token mentions
    tweets = list(ie.twitter_results.find(
        {}, {"_id": 0, "text": 1, "username": 1, "likes": 1, "retweets": 1, "replies": 1}
    ))

    # 4. Influencer clusters
    clusters = list(cdb.influencer_clusters.find({}, {"_id": 0}))

    # 5. Token velocity
    velocity = {
        doc["token"]: doc
        for doc in cdb.twitter_token_velocity_hourly.find({}, {"_id": 0})
    }

    # 6. Unified accounts (for follower weights)
    accounts = {
        doc["handle"]: doc
        for doc in cdb.connections_unified_accounts.find({}, {"_id": 0})
    }

    # 7. Bot scores from audience_quality
    bot_scores = {}
    for doc in ie.audience_quality.find({}, {"_id": 0, "actorId": 1, "pctBot": 1}):
        bot_scores[doc.get("actorId", "")] = doc.get("pctBot", 0)

    return {
        "snapshots": snapshots,
        "contexts": contexts,
        "tweets": tweets,
        "clusters": clusters,
        "velocity": velocity,
        "accounts": accounts,
        "bot_scores": bot_scores,
    }


# ─── TWITTER ANALYSIS ────────────────────────────────────

def analyze_twitter(tweets: list, accounts: dict) -> dict:
    """Extract token mentions, author stats, engagement from tweets."""
    token_re = re.compile(r"\$([A-Z]{2,10})")

    btc_mentions = 0
    alt_mentions = 0
    token_stats = defaultdict(lambda: {
        "mentions": 0,
        "unique_authors": set(),
        "total_engagement": 0,
        "total_followers": 0,
        "author_count": 0,
    })

    for tw in tweets:
        text = (tw.get("text") or "").upper()
        tokens = set(token_re.findall(text))
        username = (tw.get("username") or "").lower()
        engagement = (tw.get("likes") or 0) + (tw.get("retweets") or 0) + (tw.get("replies") or 0)
        followers = accounts.get(username, {}).get("followers", 0)

        for t in tokens:
            if t in ("BTC", "BITCOIN"):
                btc_mentions += 1
            else:
                alt_mentions += 1

            ts = token_stats[t]
            ts["mentions"] += 1
            ts["unique_authors"].add(username)
            ts["total_engagement"] += engagement
            ts["total_followers"] += followers
            ts["author_count"] += 1

    # Finalize
    result = {}
    for symbol, ts in token_stats.items():
        n = ts["author_count"] or 1
        result[symbol] = {
            "mentions": ts["mentions"],
            "uniqueAuthors": len(ts["unique_authors"]),
            "authors": list(ts["unique_authors"]),
            "engagement": ts["total_engagement"] / n,
            "avgFollowers": ts["total_followers"] / n,
        }

    return {
        "btcMentions": btc_mentions,
        "altMentions": alt_mentions,
        "tokens": result,
    }


# ─── TOKEN ASSEMBLY ──────────────────────────────────────

def assemble_tokens(snapshots, twitter_data, velocity, bot_scores) -> list:
    """Merge all data sources into unified token objects."""
    # Map snapshots by clean symbol
    snap_map = {}
    for s in snapshots:
        sym = (s.get("symbol") or "").replace("USDT", "")
        if sym:
            snap_map[sym] = s

    # All known symbols from snapshots + twitter + velocity
    all_symbols = set(snap_map.keys())
    all_symbols.update(twitter_data["tokens"].keys())
    all_symbols.update(velocity.keys())
    # Remove noise
    all_symbols -= {"BTC", "BITCOIN", "USDT", "USD", "CRYPTO", "NFT", "ETH"}

    tokens = []
    for sym in all_symbols:
        snap = snap_map.get(sym, {})
        tw = twitter_data["tokens"].get(sym, {})
        vel = velocity.get(sym, {})

        price_change = snap.get("change24h", 0) or 0
        vol = snap.get("volatility", 0) or 0
        price = snap.get("price", 0) or 0

        mentions = tw.get("mentions", 0) + (vel.get("mentions", 0) or 0)
        unique_authors = tw.get("uniqueAuthors", 0)
        engagement = tw.get("engagement", 0)
        avg_followers = tw.get("avgFollowers", 0)
        z_velocity = vel.get("zVelocity", 0) or 0
        coordination = vel.get("coordinationFlag", False)

        # Compute velocity from mentions if zVelocity is 0
        effective_velocity = z_velocity if z_velocity != 0 else min(mentions / 50.0, 1.0)

        # Volume spike proxy
        volume_spike = min(abs(vol), 1.0)

        # Risk from bot scores (average of authors who mentioned)
        risk = 0.0
        authors_list = tw.get("authors", [])
        if bot_scores and authors_list:
            risk_vals = [bot_scores[a] for a in authors_list if a in bot_scores]
            if risk_vals:
                risk = sum(risk_vals) / len(risk_vals) / 100.0  # normalize to 0-1

        tokens.append({
            "symbol": sym,
            "price": price,
            "priceChange24h": price_change,
            "volatility": vol,
            "volumeSpike": volume_spike,
            "mentions": mentions,
            "uniqueAuthors": unique_authors,
            "engagement": engagement,
            "avgFollowers": avg_followers,
            "velocity": effective_velocity,
            "coordination": coordination,
            "riskScore": risk,
        })

    return tokens


# ─── ALPHA SCORE (per token) ─────────────────────────────

def compute_alpha_score(t: dict) -> float:
    """Main formula: attention * 0.4 + quality * 0.2 + momentum * 0.3 - risk * 0.3"""
    attention = (
        math.log(t["mentions"] + 1) * 0.4
        + t["velocity"] * 0.3
        + math.log(t["uniqueAuthors"] + 1) * 0.3
    )

    quality = (
        math.log(t["avgFollowers"] + 1) * 0.5
        + t["engagement"] * 0.5
    )
    # Normalize quality to 0-1 range (log(5M) ~ 15.4)
    quality = min(quality / 15.0, 1.0)

    # Normalize attention (log(200) ~ 5.3 max)
    attention = min(attention / 5.0, 1.0)

    momentum = (
        min(abs(t["priceChange24h"]) / 50.0, 1.0) * 0.6
        + t["volumeSpike"] * 0.4
    )
    # Direction matters
    if t["priceChange24h"] < 0:
        momentum *= 0.3  # negative price = low momentum

    risk = t["riskScore"]

    score = attention * 0.4 + quality * 0.2 + momentum * 0.3 - risk * 0.3
    return max(0, min(1, score))


# ─── PHASE DETECTION ─────────────────────────────────────

def detect_phase(t: dict) -> str:
    vel = t["velocity"]
    pc = t["priceChange24h"]
    vol_spike = t["volumeSpike"]

    # EARLY: growing attention, price hasn't moved much
    if vel > 0.3 and pc < 5:
        return "EARLY"

    # MOMENTUM: price moving, volume confirming
    if pc > 10 and vol_spike > 0.3:
        return "MOMENTUM"

    # LATE: overextended
    if pc > 25:
        return "LATE"

    return "NEUTRAL"


# ─── BUILD SIGNAL ─────────────────────────────────────────

def build_signal(t: dict, phase: str) -> list:
    signals = []
    if t["velocity"] > 0.5:
        signals.append("Exploding mentions")
    if t["uniqueAuthors"] > 5:
        signals.append("Broad attention")
    if t["avgFollowers"] > 50000:
        signals.append("High-quality accounts")
    if t["priceChange24h"] < 5 and t["mentions"] > 3:
        signals.append("Still early")
    if t["coordination"]:
        signals.append("Cluster coordination")
    if t["priceChange24h"] > 10:
        signals.append("Strong momentum")
    if t["volumeSpike"] > 0.5:
        signals.append("Volume spike")
    return signals


def build_action(phase: str) -> str:
    return {
        "EARLY": "ACCUMULATE",
        "MOMENTUM": "RIDE",
        "LATE": "EXIT",
        "NEUTRAL": "WAIT",
    }.get(phase, "WAIT")


# ─── OPPORTUNITIES ────────────────────────────────────────

def compute_opportunities(tokens: list) -> list:
    scored = []
    for t in tokens:
        score = compute_alpha_score(t)
        phase = detect_phase(t)

        scored.append({
            "symbol": t["symbol"],
            "score": round(score, 3),
            "phase": phase,
            "action": build_action(phase),
            "signal": build_signal(t, phase),
            "confidence": round(score, 2),
            "priceChange24h": round(t["priceChange24h"], 2),
            "price": t["price"],
            "mentions": t["mentions"],
            "uniqueAuthors": t["uniqueAuthors"],
            "velocity": round(t["velocity"], 3),
            "volumeSpike": round(t["volumeSpike"], 3),
            "riskScore": round(t["riskScore"], 3),
        })

    # Filter LATE, sort by score
    result = [s for s in scored if s["phase"] != "LATE"]
    result.sort(key=lambda x: -x["score"])
    return result[:15]


# ─── TOKEN MOMENTUM ──────────────────────────────────────

def compute_token_momentum(tokens: list) -> list:
    scored = []
    for t in tokens:
        momentum = (
            t["velocity"] * 0.4
            + min(abs(t["priceChange24h"]) / 50.0, 1.0) * 0.3
            + min(t["mentions"] / 100.0, 1.0) * 0.3
        )
        phase = detect_phase(t)

        scored.append({
            "symbol": t["symbol"],
            "momentum": round(momentum, 3),
            "phase": phase,
            "score": round(momentum, 3),
            "priceChange24h": round(t["priceChange24h"], 2),
            "mentions": t["mentions"],
            "velocity": round(t["velocity"], 3),
        })

    scored.sort(key=lambda x: -x["momentum"])
    return scored[:25]


# ─── ALTSEASON INDEX ──────────────────────────────────────

def compute_altseason_index(
    snapshots: list,
    twitter_data: dict,
    clusters: list,
    contexts: dict,
) -> dict:
    """
    index = outperformance*0.35 + twitterShare*0.20 + clusterStrength*0.20 + breadth*0.15 + marketBias*0.10
    """
    # 1. Outperformance: % of alts beating BTC
    btc_ctx = contexts.get("BTCUSDT", {})
    btc_momentum = (btc_ctx.get("axes", {}).get("momentum", 0))
    # Use BTC momentum as proxy for BTC return (range -1 to 1)
    btc_return_proxy = btc_momentum * 10  # scale to ~% range

    alt_returns = [s.get("change24h", 0) or 0 for s in snapshots]
    if alt_returns:
        outperforming = sum(1 for r in alt_returns if r > btc_return_proxy)
        outperformance = outperforming / len(alt_returns)
    else:
        outperformance = 0.5

    # 2. Twitter share: alt mentions / total
    btc_m = twitter_data["btcMentions"]
    alt_m = twitter_data["altMentions"]
    total_m = btc_m + alt_m
    twitter_share = alt_m / total_m if total_m > 0 else 0.5

    # 3. Cluster strength: clusters with high cohesion
    if clusters:
        strong = sum(1 for c in clusters if (c.get("metrics", {}).get("cohesion", 0)) > 0.6)
        cluster_strength = strong / len(clusters)
    else:
        cluster_strength = 0.5

    # 4. Breadth: % of alts in positive territory
    if alt_returns:
        positive = sum(1 for r in alt_returns if r > 0)
        breadth = positive / len(alt_returns)
    else:
        breadth = 0.5

    # 5. Market bias: from exchange contexts
    alt_contexts = {k: v for k, v in contexts.items() if k != "BTCUSDT"}
    if alt_contexts:
        avg_momentum = sum(
            v.get("axes", {}).get("momentum", 0) for v in alt_contexts.values()
        ) / len(alt_contexts)
        avg_participation = sum(
            v.get("axes", {}).get("participation", 0) for v in alt_contexts.values()
        ) / len(alt_contexts)
        market_bias = (avg_momentum + 1) / 2 * 0.5 + avg_participation * 0.5
    else:
        market_bias = 0.5

    index = (
        outperformance * 0.35
        + twitter_share * 0.20
        + cluster_strength * 0.20
        + breadth * 0.15
        + market_bias * 0.10
    )
    index_value = round(index * 100)

    return {
        "value": max(0, min(100, index_value)),
        "components": {
            "outperformance": round(outperformance, 3),
            "twitterShare": round(twitter_share, 3),
            "clusterStrength": round(cluster_strength, 3),
            "breadth": round(breadth, 3),
            "marketBias": round(market_bias, 3),
        },
    }


# ─── MARKET STATE ─────────────────────────────────────────

def compute_market_state(index_value: int) -> dict:
    if index_value > 75:
        return {"state": "FULL_ALT", "confidence": 0.9}
    if index_value > 60:
        return {"state": "ALTSEASON", "confidence": 0.75}
    if index_value > 45:
        return {"state": "EARLY_ALT", "confidence": 0.65}
    return {"state": "BTC_DOMINANCE", "confidence": 0.6}


# ─── MAIN PIPELINE ────────────────────────────────────────

def run_altseason_pipeline() -> dict:
    data = load_data()

    # Analyze twitter
    twitter_data = analyze_twitter(data["tweets"], data["accounts"])

    # Assemble tokens
    tokens = assemble_tokens(
        data["snapshots"],
        twitter_data,
        data["velocity"],
        data["bot_scores"],
    )

    # Compute altseason index
    index_data = compute_altseason_index(
        data["snapshots"],
        twitter_data,
        data["clusters"],
        data["contexts"],
    )

    # Market state
    market = compute_market_state(index_data["value"])

    # Token momentum
    momentum = compute_token_momentum(tokens)

    # Opportunities
    opportunities = compute_opportunities(tokens)

    return {
        "index": index_data["value"],
        "state": market["state"],
        "confidence": market["confidence"],
        "components": index_data["components"],
        "token_momentum": momentum,
        "top_opportunities": opportunities,
        "meta": {
            "totalTokens": len(tokens),
            "totalSnapshots": len(data["snapshots"]),
            "totalTweets": len(data["tweets"]),
            "totalClusters": len(data["clusters"]),
            "computedAt": datetime.now(timezone.utc).isoformat(),
        },
    }
