"""
Bot Detection Engine v2 — Real Compute Pipeline
================================================
Replaces mock data with computed intelligence from real Twitter parser data.

Pipeline:
  1. Engagement Anomaly Scoring (per actor)
  2. Audience Quality Index (real compute)
  3. Behavior Similarity (posting time + token overlap)
  4. Edge Score (weighted composite)
  5. Graph Clustering (connected components)
  6. Cluster Scoring + Confidence
  7. MongoDB sync (replace mock data)

Data sources:
  - twitter_results: tweets (text, likes, reposts, views, timestamps)
  - twitter_targets: actor metadata (followers, category, tier)
"""

import os
import re
import math
import logging
from datetime import datetime, timezone
from collections import defaultdict
from typing import Optional
from pymongo import MongoClient

logger = logging.getLogger("bot_detection_engine")

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")

_client: Optional[MongoClient] = None


def _db():
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URL)
    return _client[DB_NAME]


# ─── TOKEN EXTRACTION ────────────────────────────────────────
TOKEN_RE = re.compile(r'\$([A-Z]{2,10})\b')
KNOWN_TOKENS = {
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX",
    "DOT", "LINK", "MATIC", "UNI", "AAVE", "ARB", "OP", "APT",
    "SUI", "SEI", "TIA", "INJ", "FET", "RENDER", "WIF", "PEPE",
    "BONK", "JUP", "PENDLE", "ENA", "STRK", "PYTH", "W", "TAO",
}


def extract_tokens(text: str) -> list[str]:
    """Extract token mentions from tweet text."""
    found = TOKEN_RE.findall(text.upper())
    result = []
    for t in found:
        if t in KNOWN_TOKENS:
            result.append(t)
    # Also check for non-$ mentions of major tokens
    upper = text.upper()
    for tok in ["BTC", "ETH", "SOL", "BITCOIN", "ETHEREUM", "SOLANA"]:
        canonical = {"BITCOIN": "BTC", "ETHEREUM": "ETH", "SOLANA": "SOL"}.get(tok, tok)
        if tok in upper and canonical not in result:
            result.append(canonical)
    return list(set(result))


# ─── STEP 1: LOAD ACTOR DATA ─────────────────────────────────
def load_actors() -> dict:
    """Load all actors with their tweets and metadata."""
    db = _db()

    # Load metadata from twitter_targets
    meta_map = {}
    for t in db.twitter_targets.find({}, {"_id": 0}):
        handle = t.get("query", "").lower()
        if handle:
            m = t.get("metadata", {})
            meta_map[handle] = {
                "display_name": m.get("display_name", handle),
                "category": m.get("category", "unknown"),
                "followers": m.get("followers", 0),
                "tier": m.get("tier", 3),
            }

    # Load tweets grouped by author
    actors = {}
    for tweet in db.twitter_results.find({}, {"_id": 0}):
        username = (tweet.get("username") or "").lower().strip()
        if not username:
            continue

        if username not in actors:
            actors[username] = {
                "id": username,
                "tweets": [],
                "meta": meta_map.get(username, {}),
            }

        tokens = extract_tokens(tweet.get("text", ""))
        tweeted_at = tweet.get("tweetedAt")
        ts = 0
        if isinstance(tweeted_at, datetime):
            ts = int(tweeted_at.timestamp())

        actors[username]["tweets"].append({
            "text": tweet.get("text", ""),
            "likes": tweet.get("likes", 0) or 0,
            "reposts": tweet.get("reposts", 0) or 0,
            "replies": tweet.get("replies", 0) or 0,
            "views": tweet.get("views", 0) or 0,
            "tokens": tokens,
            "timestamp": ts,
            "hour_of_day": (ts % 86400) // 3600 if ts > 0 else 12,
        })

    return actors


# ─── STEP 2: ENGAGEMENT ANOMALY SCORING ──────────────────────
def compute_engagement_anomaly(actor: dict) -> dict:
    """
    Detect engagement anomalies that indicate bot/fake activity.

    Formulas:
      engagementRate = totalEngagement / (followers * tweetCount)
      viewRate = totalViews / (followers * tweetCount)
      ghostScore = (1 - engagementRate) if engagement abnormally low
      inflationScore = likesToViewsRatio anomaly

    Returns normalized scores in [0, 1].
    """
    tweets = actor["tweets"]
    meta = actor.get("meta", {})
    followers = max(meta.get("followers", 0), 1)
    n = len(tweets)

    if n == 0:
        return {
            "engagementRate": 0,
            "viewRate": 0,
            "ghostScore": 1.0,
            "inflationScore": 0.5,
            "zeroEngagementRatio": 1.0,
            "avgLikes": 0,
            "avgViews": 0,
        }

    total_likes = sum(t["likes"] for t in tweets)
    total_reposts = sum(t["reposts"] for t in tweets)
    total_replies = sum(t["replies"] for t in tweets)
    total_views = sum(t["views"] for t in tweets)
    total_engagement = total_likes + total_reposts + total_replies

    avg_likes = total_likes / n
    avg_views = total_views / n

    # Engagement per follower per tweet
    eng_rate = min(total_engagement / (followers * n) * 100, 100) if followers > 0 else 0

    # View rate
    view_rate = min(total_views / (followers * n), 10) if followers > 0 else 0

    # Ghost score: high followers but zero/near-zero engagement
    ghost = 0.0
    if followers > 10000:
        expected_eng = followers * 0.001 * n  # expect at least 0.1% engagement
        if total_engagement < expected_eng * 0.1:
            ghost = min(1.0, 1.0 - (total_engagement / max(expected_eng, 1)))

    # Inflation score: likes/views ratio anomaly
    inflation = 0.0
    if total_views > 0:
        like_view_ratio = total_likes / total_views
        # Normal ratio ~1-5%, suspicious if >20% or <0.01%
        if like_view_ratio > 0.20:
            inflation = min(1.0, (like_view_ratio - 0.20) / 0.30)
        elif like_view_ratio < 0.001 and total_views > 1000:
            inflation = min(1.0, (0.001 - like_view_ratio) / 0.001)

    # Zero engagement ratio
    zero_count = sum(1 for t in tweets if t["likes"] == 0 and t["reposts"] == 0 and t["views"] == 0)
    zero_ratio = zero_count / n

    return {
        "engagementRate": round(eng_rate, 4),
        "viewRate": round(view_rate, 4),
        "ghostScore": round(ghost, 4),
        "inflationScore": round(inflation, 4),
        "zeroEngagementRatio": round(zero_ratio, 4),
        "avgLikes": round(avg_likes, 1),
        "avgViews": round(avg_views, 1),
    }


# ─── STEP 3: AUDIENCE QUALITY INDEX ──────────────────────────
def compute_audience_quality(actor: dict, engagement: dict) -> dict:
    """
    Compute AQI for an actor based on engagement patterns.

    Formula:
      engagementQuality = 1 - ghostScore * 0.6 - zeroEngagementRatio * 0.4
      consistencyScore = 1 - stddev(likes) / mean(likes)
      categoryTrust = tier-based weight
      aqi = engagementQuality * 0.45 + consistencyScore * 0.25 + categoryTrust * 0.15 + viewHealthScore * 0.15
      pctBot = (ghostScore * 0.35 + inflationScore * 0.25 + zeroEngagementRatio * 0.25 + (1 - consistencyScore) * 0.15)
    """
    tweets = actor["tweets"]
    meta = actor.get("meta", {})
    n = len(tweets)

    # Engagement quality
    eng_quality = max(0, 1.0
                      - engagement["ghostScore"] * 0.6
                      - engagement["zeroEngagementRatio"] * 0.4)

    # Consistency: low variance in engagement = more organic
    consistency = 0.5
    if n >= 3:
        likes_list = [t["likes"] for t in tweets]
        mean_l = sum(likes_list) / n
        if mean_l > 0:
            variance = sum((val - mean_l) ** 2 for val in likes_list) / n
            std = math.sqrt(variance)
            cv = std / mean_l  # coefficient of variation
            consistency = max(0, min(1, 1.0 - cv / 3.0))

    # Category trust (known founders/VCs more trusted)
    tier = meta.get("tier", 3)
    category = meta.get("category", "unknown")
    trust_map = {"founder": 0.85, "vc": 0.80, "research": 0.75, "protocol": 0.70,
                 "infra": 0.70, "exchange": 0.65, "media": 0.60,
                 "trader": 0.50, "influencer": 0.45, "detective": 0.70}
    category_trust = trust_map.get(category, 0.40)
    if tier == 1:
        category_trust = min(1.0, category_trust + 0.10)
    elif tier >= 3:
        category_trust = max(0.1, category_trust - 0.10)

    # View health: views should correlate with followers
    view_health = 0.5
    followers = meta.get("followers", 0)
    if followers > 0 and n > 0:
        avg_views = engagement["avgViews"]
        expected_view_ratio = avg_views / followers
        # Good: 5-50% of followers see each tweet
        if 0.01 <= expected_view_ratio <= 0.5:
            view_health = 0.8
        elif expected_view_ratio > 0.5:
            view_health = 0.9  # viral
        else:
            view_health = max(0.1, expected_view_ratio / 0.01)

    # Composite AQI
    aqi = (eng_quality * 0.45
           + consistency * 0.25
           + category_trust * 0.15
           + view_health * 0.15)

    # Bot probability
    pct_bot = (engagement["ghostScore"] * 0.35
               + engagement["inflationScore"] * 0.25
               + engagement["zeroEngagementRatio"] * 0.25
               + (1.0 - consistency) * 0.15)

    pct_bot = min(1.0, max(0.0, pct_bot))
    pct_suspicious = min(1.0, max(0.0, (pct_bot * 0.5 + engagement["inflationScore"] * 0.5)))
    pct_human = max(0.0, 1.0 - pct_bot - pct_suspicious)

    # Level classification
    aqi_pct = round(aqi * 100)
    if aqi_pct >= 75:
        level = "ELITE"
    elif aqi_pct >= 55:
        level = "GOOD"
    elif aqi_pct >= 35:
        level = "MODERATE"
    else:
        level = "RISKY"

    return {
        "actorId": actor["id"],
        "aqi": aqi_pct,
        "pctHuman": round(pct_human * 100, 1),
        "pctBot": round(pct_bot * 100, 1),
        "pctSuspicious": round(pct_suspicious * 100, 1),
        "botScore": round(pct_bot, 4),
        "level": level,
        "breakdown": {
            "engagementQuality": round(eng_quality, 4),
            "consistency": round(consistency, 4),
            "categoryTrust": round(category_trust, 4),
            "viewHealth": round(view_health, 4),
        },
        "engagement": {
            "ghostScore": engagement["ghostScore"],
            "inflationScore": engagement["inflationScore"],
            "zeroEngagementRatio": engagement["zeroEngagementRatio"],
            "avgLikes": engagement["avgLikes"],
            "avgViews": engagement["avgViews"],
        },
        "tweetCount": len(actor["tweets"]),
        "followers": meta.get("followers", 0),
        "category": meta.get("category", "unknown"),
        "computedAt": datetime.now(timezone.utc).isoformat(),
    }


# ─── STEP 4: BEHAVIOR SIMILARITY ─────────────────────────────
def compute_behavior_similarity(actor_a: dict, actor_b: dict) -> dict:
    """
    Compute behavioral similarity between two actors.

    Formulas:
      postingTimeSimilarity = 1 - |mean_hour(A) - mean_hour(B)| / 12
      tokenSimilarity = |tokens(A) ∩ tokens(B)| / min(|tokens(A)|, |tokens(B)|)
      engagementPatternSimilarity = 1 - |engRate(A) - engRate(B)| / max(engRate)
      behaviorSimilarity = timeSim * 0.3 + tokenSim * 0.5 + engPatternSim * 0.2
    """
    tweets_a = actor_a["tweets"]
    tweets_b = actor_b["tweets"]

    if not tweets_a or not tweets_b:
        return {"timeSimilarity": 0, "tokenSimilarity": 0, "engPatternSimilarity": 0,
                "behaviorSimilarity": 0, "sharedTokens": []}

    # Posting time similarity — detect coordinated bursts (not just avg hour)
    hours_a = [t["hour_of_day"] for t in tweets_a if t["timestamp"] > 0]
    hours_b = [t["hour_of_day"] for t in tweets_b if t["timestamp"] > 0]

    time_sim = 0.3  # baseline
    if hours_a and hours_b:
        mean_a = sum(hours_a) / len(hours_a)
        mean_b = sum(hours_b) / len(hours_b)
        diff = min(abs(mean_a - mean_b), 24 - abs(mean_a - mean_b))  # circular
        avg_sim = max(0, 1.0 - diff / 12.0)

        # Also check if posting within same hours (distribution overlap)
        hist_a = [0] * 24
        hist_b = [0] * 24
        for h in hours_a:
            hist_a[int(h) % 24] += 1
        for h in hours_b:
            hist_b[int(h) % 24] += 1
        # Normalize
        sum_a = max(sum(hist_a), 1)
        sum_b = max(sum(hist_b), 1)
        dist_overlap = sum(min(hist_a[i] / sum_a, hist_b[i] / sum_b) for i in range(24))

        time_sim = avg_sim * 0.4 + dist_overlap * 0.6

    # Token overlap — with IDF weighting (common tokens like BTC count less)
    tokens_a = set()
    tokens_b = set()
    for t in tweets_a:
        tokens_a.update(t["tokens"])
    for t in tweets_b:
        tokens_b.update(t["tokens"])

    shared_tokens = tokens_a & tokens_b
    # IDF: penalize ubiquitous tokens
    COMMON_TOKENS = {"BTC", "ETH", "SOL", "BNB"}
    rare_shared = shared_tokens - COMMON_TOKENS
    common_shared = shared_tokens & COMMON_TOKENS

    token_sim = 0.0
    min_size = min(len(tokens_a), len(tokens_b))
    if min_size > 0:
        # Rare tokens: full weight. Common: 0.2 weight
        weighted_overlap = len(rare_shared) + len(common_shared) * 0.2
        weighted_max = min_size
        token_sim = min(1.0, weighted_overlap / max(weighted_max, 1))

    # Engagement pattern similarity
    avg_eng_a = sum(t["likes"] + t["reposts"] for t in tweets_a) / len(tweets_a) if tweets_a else 0
    avg_eng_b = sum(t["likes"] + t["reposts"] for t in tweets_b) / len(tweets_b) if tweets_b else 0
    max_eng = max(avg_eng_a, avg_eng_b, 1)
    eng_sim = max(0, 1.0 - abs(avg_eng_a - avg_eng_b) / max_eng)

    # Composite
    behavior_sim = time_sim * 0.3 + token_sim * 0.5 + eng_sim * 0.2

    return {
        "timeSimilarity": round(time_sim, 4),
        "tokenSimilarity": round(token_sim, 4),
        "engPatternSimilarity": round(eng_sim, 4),
        "behaviorSimilarity": round(behavior_sim, 4),
        "sharedTokens": sorted(shared_tokens),
    }


# ─── STEP 5: EDGE SCORE ──────────────────────────────────────
def compute_edge(actor_a: dict, actor_b: dict, aq_a: dict, aq_b: dict) -> dict | None:
    """
    Compute edge score between two actors.

    Formula:
      suspicionWeight = (botScore(A) + botScore(B)) / 2
      edgeScore = behaviorSimilarity * 0.5 + suspicionWeight * 0.3 + tokenOverlapBonus * 0.2

    Returns None if edge score below threshold.
    """
    behavior = compute_behavior_similarity(actor_a, actor_b)

    bot_a = aq_a.get("botScore", 0)
    bot_b = aq_b.get("botScore", 0)
    suspicion_weight = (bot_a + bot_b) / 2

    # Token overlap bonus (more shared tokens = stronger signal)
    n_shared = len(behavior["sharedTokens"])
    token_bonus = min(1.0, n_shared / 3.0) if n_shared > 0 else 0

    edge_score = (behavior["behaviorSimilarity"] * 0.5
                  + suspicion_weight * 0.3
                  + token_bonus * 0.2)

    # Minimum threshold — raise to filter noise
    if edge_score < 0.30:
        return None

    # Shared suspects count (estimated from bot scores)
    followers_a = actor_a.get("meta", {}).get("followers", 0)
    followers_b = actor_b.get("meta", {}).get("followers", 0)
    estimated_shared = int(min(followers_a, followers_b) * edge_score * 0.01)

    return {
        "a": actor_a["id"],
        "b": actor_b["id"],
        "edgeScore": round(edge_score, 4),
        "overlapScore": round(edge_score, 4),  # backward compat
        "behaviorSimilarity": behavior["behaviorSimilarity"],
        "timeSimilarity": behavior["timeSimilarity"],
        "tokenSimilarity": behavior["tokenSimilarity"],
        "engPatternSimilarity": behavior["engPatternSimilarity"],
        "suspicionWeight": round(suspicion_weight, 4),
        "sharedTokens": behavior["sharedTokens"],
        "sharedSuspects": max(estimated_shared, len(behavior["sharedTokens"])),
        "evidence": [],
        "computedAt": datetime.now(timezone.utc).isoformat(),
    }


# ─── STEP 6: BUILD EVIDENCE ──────────────────────────────────
def build_evidence(edge: dict, aq_a: dict, aq_b: dict) -> list[str]:
    """Generate human-readable evidence for an edge."""
    ev = []
    if edge["tokenSimilarity"] > 0.5:
        tokens = ", ".join(edge["sharedTokens"][:5])
        ev.append(f"High token overlap ({int(edge['tokenSimilarity']*100)}%): {tokens}")
    if edge["timeSimilarity"] > 0.7:
        ev.append(f"Synchronized posting times ({int(edge['timeSimilarity']*100)}% match)")
    if edge["suspicionWeight"] > 0.3:
        ev.append(f"Both actors have elevated bot scores ({int(edge['suspicionWeight']*100)}%)")
    if edge["engPatternSimilarity"] > 0.8:
        ev.append("Nearly identical engagement patterns")
    if aq_a.get("engagement", {}).get("zeroEngagementRatio", 0) > 0.5:
        ev.append(f"@{edge['a']}: {int(aq_a['engagement']['zeroEngagementRatio']*100)}% zero-engagement tweets")
    if aq_b.get("engagement", {}).get("zeroEngagementRatio", 0) > 0.5:
        ev.append(f"@{edge['b']}: {int(aq_b['engagement']['zeroEngagementRatio']*100)}% zero-engagement tweets")
    return ev


# ─── STEP 7: GRAPH CLUSTERING ────────────────────────────────
def find_clusters(edges: list[dict], min_edge_score: float = 0.33) -> list[list[str]]:
    """
    Find connected components in the actor graph.
    Uses min_edge_score as threshold for cluster membership.
    Splits large clusters by removing weak internal edges.
    """
    # Build graph with only strong edges
    graph = defaultdict(set)
    edge_weights = {}
    for e in edges:
        if e["edgeScore"] >= min_edge_score:
            graph[e["a"]].add(e["b"])
            graph[e["b"]].add(e["a"])
            key = tuple(sorted([e["a"], e["b"]]))
            edge_weights[key] = e["edgeScore"]

    visited = set()
    raw_clusters = []

    for node in graph:
        if node in visited:
            continue
        stack = [node]
        cluster = []
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            cluster.append(current)
            for neighbor in graph[current]:
                if neighbor not in visited:
                    stack.append(neighbor)
        if len(cluster) >= 2:
            raw_clusters.append(sorted(cluster))

    # Split large clusters: if a cluster has >6 members, split by edge strength
    final_clusters = []
    for cluster in raw_clusters:
        if len(cluster) <= 6:
            final_clusters.append(cluster)
            continue

        # Find median edge weight within cluster
        members = set(cluster)
        internal_weights = []
        for (a, b), w in edge_weights.items():
            if a in members and b in members:
                internal_weights.append(w)
        if not internal_weights:
            final_clusters.append(cluster)
            continue

        # Use higher threshold (75th percentile) to split
        internal_weights.sort()
        split_threshold = internal_weights[len(internal_weights) * 3 // 4]

        # Re-cluster with higher threshold
        sub_graph = defaultdict(set)
        for (a, b), w in edge_weights.items():
            if a in members and b in members and w >= split_threshold:
                sub_graph[a].add(b)
                sub_graph[b].add(a)

        sub_visited = set()
        for node in members:
            if node in sub_visited or node not in sub_graph:
                continue
            stack = [node]
            sub_cluster = []
            while stack:
                current = stack.pop()
                if current in sub_visited:
                    continue
                sub_visited.add(current)
                sub_cluster.append(current)
                for neighbor in sub_graph.get(current, set()):
                    if neighbor not in sub_visited:
                        stack.append(neighbor)
            if len(sub_cluster) >= 2:
                final_clusters.append(sorted(sub_cluster))

    return final_clusters


# ─── STEP 8: CLUSTER SCORING ─────────────────────────────────
def compute_cluster_score(cluster: list[str], edges: list[dict],
                          aq_map: dict[str, dict]) -> dict:
    """
    Score a cluster (potential bot farm).

    Formulas:
      density = actual_edges / possible_edges
      avgBotScore = mean(botScore of members)
      avgEdgeScore = mean(edgeScore of internal edges)
      clusterBotScore = avgBotScore * 0.4 + avgEdgeScore * 0.3 + density * 0.2 + sizeFactor * 0.1
      confidence = min(1, clusterSize/5 * density * scoreConsistency)
    """
    members_set = set(cluster)

    # Internal edges
    internal_edges = [e for e in edges
                      if e["a"] in members_set and e["b"] in members_set]

    n = len(cluster)
    possible = n * (n - 1) / 2 if n >= 2 else 1
    density = len(internal_edges) / possible if possible > 0 else 0

    # Average bot score
    bot_scores = [aq_map.get(m, {}).get("botScore", 0) for m in cluster]
    avg_bot = sum(bot_scores) / len(bot_scores) if bot_scores else 0

    # Average edge score
    edge_scores = [e["edgeScore"] for e in internal_edges]
    avg_edge = sum(edge_scores) / len(edge_scores) if edge_scores else 0

    # Size factor
    size_factor = min(1.0, n / 10.0)

    # Composite
    cluster_bot_score = (avg_bot * 0.4
                         + avg_edge * 0.3
                         + density * 0.2
                         + size_factor * 0.1)

    # Confidence
    score_variance = 0
    if len(bot_scores) >= 2:
        mean_bs = sum(bot_scores) / len(bot_scores)
        score_variance = sum((s - mean_bs) ** 2 for s in bot_scores) / len(bot_scores)
    score_consistency = max(0, 1.0 - math.sqrt(score_variance) * 2)

    confidence = min(1.0, (n / 5.0) * density * score_consistency)

    # Risk level
    if cluster_bot_score > 0.6:
        risk = "HIGH"
    elif cluster_bot_score > 0.35:
        risk = "MEDIUM"
    else:
        risk = "LOW"

    # Collect shared tokens across cluster
    cluster_tokens = defaultdict(int)
    for e in internal_edges:
        for tok in e.get("sharedTokens", []):
            cluster_tokens[tok] += 1
    top_tokens = sorted(cluster_tokens.items(), key=lambda x: -x[1])[:5]

    # Generate evidence
    evidence = []
    if density > 0.7:
        evidence.append(f"Dense cluster: {int(density*100)}% connected")
    if avg_bot > 0.4:
        evidence.append(f"High average bot score: {int(avg_bot*100)}%")
    if top_tokens:
        tokens_str = ", ".join(f"${t[0]}" for t in top_tokens[:3])
        evidence.append(f"Coordinated token mentions: {tokens_str}")
    if avg_edge > 0.5:
        evidence.append(f"Strong behavioral similarity: {int(avg_edge*100)}%")

    return {
        "members": cluster,
        "memberCount": n,
        "clusterBotScore": round(cluster_bot_score, 4),
        "avgBotScore": round(avg_bot, 4),
        "avgEdgeScore": round(avg_edge, 4),
        "density": round(density, 4),
        "confidence": round(confidence, 4),
        "riskLevel": risk,
        "topTokens": [{"token": t[0], "mentions": t[1]} for t in top_tokens],
        "evidence": evidence,
        "confidenceBreakdown": {
            "clusterSize": n,
            "density": round(density, 4),
            "scoreConsistency": round(score_consistency, 4),
        },
    }


# ─── STEP 9: MAIN PIPELINE ───────────────────────────────────
def run_bot_detection(min_tweets: int = 2, top_n: int = 80) -> dict:
    """
    Run the complete bot detection pipeline.

    Args:
        min_tweets: minimum tweets for an actor to be included
        top_n: max actors to process (performance guard)

    Returns:
        dict with audience, edges, farms, stats
    """
    logger.info("Bot Detection Engine v2: starting pipeline...")

    # Step 1: Load actors
    actors = load_actors()
    logger.info(f"Loaded {len(actors)} actors from twitter_results")

    # Filter: only actors with enough tweets
    qualified = {k: v for k, v in actors.items() if len(v["tweets"]) >= min_tweets}
    # Sort by tweet count, take top N
    sorted_actors = sorted(qualified.values(), key=lambda a: -len(a["tweets"]))[:top_n]
    logger.info(f"Qualified actors (>={min_tweets} tweets): {len(sorted_actors)}")

    # Step 2: Compute engagement + audience quality
    aq_map = {}
    for actor in sorted_actors:
        engagement = compute_engagement_anomaly(actor)
        aq = compute_audience_quality(actor, engagement)
        aq_map[actor["id"]] = aq

    # Step 3: Compute edges (pairwise)
    edges = []
    n = len(sorted_actors)
    pairs_checked = 0
    for i in range(n):
        for j in range(i + 1, n):
            pairs_checked += 1
            a = sorted_actors[i]
            b = sorted_actors[j]
            edge = compute_edge(a, b, aq_map[a["id"]], aq_map[b["id"]])
            if edge:
                evidence = build_evidence(edge, aq_map[a["id"]], aq_map[b["id"]])
                edge["evidence"] = evidence
                edges.append(edge)

    logger.info(f"Computed {len(edges)} edges from {pairs_checked} pairs")

    # Step 4: Cluster detection
    clusters = find_clusters(edges)
    logger.info(f"Found {len(clusters)} clusters")

    # Step 5: Score clusters → farms
    farms = []
    for idx, cluster in enumerate(clusters):
        score = compute_cluster_score(cluster, edges, aq_map)
        farm = {
            "farmId": f"farm_{idx}",
            "name": f"Cluster #{idx + 1}",
            "actorIds": cluster,
            **score,
            "computedAt": datetime.now(timezone.utc).isoformat(),
        }
        farms.append(farm)

    # Sort farms by risk
    risk_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    farms.sort(key=lambda f: (risk_order.get(f["riskLevel"], 3), -f["clusterBotScore"]))

    # Name farms in human-readable format
    for i, farm in enumerate(farms):
        tokens = [t["token"] for t in farm.get("topTokens", [])[:2]]
        n_members = len(farm.get("actorIds", []))
        size_label = "Small" if n_members <= 2 else "Mid-size" if n_members <= 5 else "Large"

        if farm["riskLevel"] == "HIGH" and tokens:
            farm["name"] = f"Coordinated {' & '.join(tokens)} Push"
        elif tokens and len(tokens) >= 2:
            farm["name"] = f"Cross-Asset Coordination ({', '.join(tokens)})"
        elif tokens:
            farm["name"] = f"Coordinated {tokens[0]} Activity"
        elif farm["riskLevel"] == "HIGH":
            farm["name"] = f"High-Risk Cluster #{i + 1}"
        else:
            farm["name"] = f"{size_label} Coordination Cluster #{i + 1}"

    # Assign farmId to edges based on cluster membership
    actor_to_farm = {}
    for farm in farms:
        for actor_id in farm["actorIds"]:
            actor_to_farm[actor_id] = farm["farmId"]
    for edge in edges:
        fa = actor_to_farm.get(edge["a"], "")
        fb = actor_to_farm.get(edge["b"], "")
        if fa and fa == fb:
            edge["farmId"] = fa
        elif fa and fb:
            edge["farmId"] = fa  # cross-farm link
        else:
            edge["farmId"] = fa or fb or ""

    stats = {
        "totalActors": len(sorted_actors),
        "totalEdges": len(edges),
        "totalClusters": len(farms),
        "pairsChecked": pairs_checked,
        "highRiskClusters": sum(1 for f in farms if f["riskLevel"] == "HIGH"),
        "mediumRiskClusters": sum(1 for f in farms if f["riskLevel"] == "MEDIUM"),
        "computedAt": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(f"Pipeline complete: {stats}")
    return {
        "audience": list(aq_map.values()),
        "edges": edges,
        "farms": farms,
        "stats": stats,
    }


# ─── STEP 10: MONGO SYNC ─────────────────────────────────────
def sync_to_mongo(result: dict):
    """Write computed results to MongoDB, replacing mock data."""
    db = _db()

    # Sync audience_quality
    if result["audience"]:
        db.audience_quality.delete_many({})
        db.audience_quality.insert_many(result["audience"])
        logger.info(f"Synced {len(result['audience'])} audience_quality docs")

    # Sync farm_graph_edges
    if result["edges"]:
        db.farm_graph_edges.delete_many({})
        db.farm_graph_edges.insert_many(result["edges"])
        logger.info(f"Synced {len(result['edges'])} farm_graph_edges")

    # Sync bot_farms
    if result["farms"]:
        db.bot_farms.delete_many({})
        db.bot_farms.insert_many(result["farms"])
        logger.info(f"Synced {len(result['farms'])} bot_farms")

    logger.info("MongoDB sync complete")


# ─── ENTRY POINT ──────────────────────────────────────────────
def run_and_sync(min_tweets: int = 2, top_n: int = 80) -> dict:
    """Run pipeline and sync to MongoDB. Returns stats."""
    result = run_bot_detection(min_tweets=min_tweets, top_n=top_n)
    sync_to_mongo(result)
    return result["stats"]
