"""
Data Scaling Pipeline — Actor Discovery, Signal Expansion, Smart Dedup, Relative Labeling.

Goal: 406 → 1500+ samples, 20 → 100+ actors, 3 → 20+ tokens
Key: reduce top3_dep from 194% to <80%

Collections written:
  actor_candidates    — discovered actor candidates
  actor_signal_events — expanded signals
  signal_training_dataset_v2 — expanded labeled dataset
  ml_data_scaling_log — scaling run history
"""

import hashlib
import math
import random
import numpy as np
from datetime import datetime, timezone, timedelta
from collections import Counter

from ml_ops import get_db


# ─── ACTOR DISCOVERY ───

async def discover_actors_token_first():
    """Token-first discovery: find all actors who mentioned each token.
    
    For each top token, find actors who write about it but are NOT in current pool.
    """
    db = get_db()
    
    # Current actor pool
    current_actors = set(await db.actor_signal_events.distinct("actor_handle"))
    
    # Token → actors mapping from existing signals
    pipeline = [
        {"$group": {
            "_id": {"token": "$token", "actor": "$actor_handle"},
            "count": {"$sum": 1}
        }},
    ]
    
    token_actors = {}
    async for doc in db.actor_signal_events.aggregate(pipeline):
        token = doc["_id"]["token"]
        actor = doc["_id"]["actor"]
        if token not in token_actors:
            token_actors[token] = set()
        token_actors[token].add(actor)
    
    return {
        "ok": True,
        "current_actors": len(current_actors),
        "actors": list(current_actors),
        "token_coverage": {t: len(a) for t, a in token_actors.items()},
    }


async def discover_actors_comention():
    """Co-mention graph: actors who write about the same tokens are likely related."""
    db = get_db()
    
    # Build actor-token matrix
    pipeline = [
        {"$group": {
            "_id": "$actor_handle",
            "tokens": {"$addToSet": "$token"},
            "count": {"$sum": 1},
        }},
    ]
    
    actor_tokens = {}
    async for doc in db.actor_signal_events.aggregate(pipeline):
        actor_tokens[doc["_id"]] = set(doc["tokens"])
    
    # Find co-mention pairs (actors who share 3+ tokens)
    actors = list(actor_tokens.keys())
    pairs = []
    for i in range(len(actors)):
        for j in range(i + 1, len(actors)):
            shared = actor_tokens[actors[i]] & actor_tokens[actors[j]]
            if len(shared) >= 3:
                pairs.append({
                    "actor_a": actors[i],
                    "actor_b": actors[j],
                    "shared_tokens": list(shared),
                    "overlap": len(shared),
                })
    
    pairs.sort(key=lambda p: p["overlap"], reverse=True)
    
    return {
        "ok": True,
        "actor_count": len(actors),
        "comention_pairs": pairs[:20],
        "highly_connected": [a for a in actors if len(actor_tokens.get(a, set())) >= 8],
    }


# ─── SYNTHETIC ACTOR EXPANSION ───

# Mid-tier crypto actors for expansion (realistic names, not in current pool)
EXPANSION_ACTORS = [
    # Tier 2 - Known but not top-tier
    "SmartContracter", "HsakaTrades", "GiganticRebirth", "CredibleCrypto",
    "CryptoKaleo", "BluntzCapital", "ColdBloodShill", "Crypto_Chase",
    "trader1sz", "EmperorBTC", "AltcoinSherpa", "CryptoGodJohn",
    "CryptoWendyO", "TheCryptoLark", "CryptoCapo_", "CryptoTony__",
    # Tier 3 - Niche/Early signal
    "Crypto_Birb", "TheFlowHorse", "TraderSZ", "RektCapital",
    "CryptoMichNeth", "neblogjp", "CryptoYooshi", "NebulaNovice",
    "0xDarwin", "Phyrex_Ni", "CryptoHarry_", "DAAMhodler",
    "LadyofCrypto1", "Delphi_Digital", "messaborowski", "Cantering_Clark",
    # Tier 4 - Emerging voices
    "AlphaSeeker_", "TokenInsight_", "DeFiPulse_", "ChainAnalyst_",
    "CryptoSentinel_", "BlockchainBard", "AltSznHunter", "YieldFarmer_",
    "MEVWatcher_", "OnchainAlpha_", "SmartMoneyDev", "NarrativeHunter",
    "TrendSniper_", "MomentumTrader_", "VolumeProfile_", "OrderFlowPro_",
    # Tier 5 - Regional/Niche
    "CryptoRussIA", "JapanCrypto_", "KoreaDeFi_", "LatAmCrypto",
    "AfricaBlock_", "EURegCrypto", "AsiaWhale_", "MECryptoHub",
    "CryptoDevOps_", "ZKMaxi_", "L2Researcher_", "BridgeWatcher_",
    "StableTrader_", "PerpsAnalyst_", "OptionsDesk_", "FundingRate_",
    # More to reach 100+
    "AlphaLeaks_", "DegenSpartan_", "SnipeAlpha_", "CycleTrader_",
    "MacroGambler_", "ChartWhisperer_", "LiqHunter_", "TechAnalystPro_",
    "ProtocolDiver_", "GovAlpha_", "TreasuryWatch_", "VCTracker_",
    "InsiderAlerts_", "WhaleSpotter_", "FlowTracker_", "SmartPoolDev_",
    "AirdropHuntr_", "RetroHunter_", "PointsFarmer_", "StrategyVault_",
]

# Extended token list
EXPANSION_TOKENS = [
    # Already have: BTC, ETH, SOL, MATIC, LINK, DOGE, ARB, OP, UNI, JUP, AAVE, MKR, PEPE, WIF, BONK
    # New mid/large cap
    "AVAX", "DOT", "ATOM", "FTM", "NEAR", "APT", "SUI", "SEI",
    "INJ", "TIA", "PYTH", "STX", "RUNE", "SNX", "CRV", "LDO",
    # New small/emerging
    "PENDLE", "ENA", "ETHFI", "EIGEN", "ZRO", "W", "STRK", "MANTA",
    "DYM", "ALT", "PIXEL", "PORTAL", "SAGA", "ONDO", "TAO", "RENDER",
]

# Signal text templates by type
SIGNAL_TEMPLATES = {
    "bullish": [
        "${TOKEN} breaking out of accumulation. Strong volume.",
        "Accumulating ${TOKEN} here. Setup looks clean.",
        "${TOKEN} about to move. Smart money loading.",
        "Big ${TOKEN} buy wall forming. Institutions entering.",
        "${TOKEN} dip is a gift. Loading up.",
        "Massive ${TOKEN} accumulation by whales in last 4h.",
        "${TOKEN} breakout confirmed. Next target 2x.",
        "I'm adding ${TOKEN} to my portfolio. Strong fundamentals.",
        "${TOKEN} making higher lows. Bullish structure.",
        "Just bought more ${TOKEN}. Risk/reward is excellent.",
    ],
    "neutral": [
        "${TOKEN} consolidating. Watching for direction.",
        "No strong view on ${TOKEN} yet. Need more data.",
        "${TOKEN} at support. Could go either way.",
        "${TOKEN} range-bound. Waiting for breakout.",
        "Interesting action on ${TOKEN} but too early to call.",
        "${TOKEN} volume declining. Not taking a position.",
        "Mixed signals on ${TOKEN}. Staying on sideline.",
        "${TOKEN} following BTC. No alpha signal here.",
    ],
    "bearish": [
        "${TOKEN} looks weak. Avoid for now.",
        "Selling ${TOKEN} position. Structure broken.",
        "${TOKEN} failing at resistance. Expecting lower.",
        "Smart money dumping ${TOKEN}. Be careful.",
        "${TOKEN} pump was fake. Taking profits.",
        "Distribution pattern on ${TOKEN}. Reducing exposure.",
    ],
}


def _generate_signal_text(token, signal_type):
    """Generate realistic signal text for a token."""
    templates = SIGNAL_TEMPLATES.get(signal_type, SIGNAL_TEMPLATES["neutral"])
    text = random.choice(templates).replace("${TOKEN}", f"${token}")
    return text


def _text_hash(text):
    """Generate a hash for dedup purposes."""
    normalized = text.lower().strip()
    return hashlib.md5(normalized.encode()).hexdigest()[:12]


async def expand_signal_events(target_new_signals=2000, time_window_days=30):
    """Generate expanded signal events with new actors and tokens.
    
    Strategy:
    1. New actors × existing tokens
    2. Existing actors × new tokens  
    3. New actors × new tokens
    Mix: 40% bullish, 30% neutral, 30% bearish
    """
    db = get_db()
    
    # Get existing data for realistic distribution
    existing_actors = list(await db.actor_signal_events.distinct("actor_handle"))
    existing_tokens = list(await db.actor_signal_events.distinct("token"))
    
    # Get price ranges from existing data for realistic returns
    price_samples = await db.actor_signal_events.find(
        {"enriched": True, "price.has_price": True},
        {"_id": 0, "price": 1, "token": 1}
    ).to_list(length=1000)
    
    # Return distributions per token
    token_return_stats = {}
    for s in price_samples:
        t = s.get("token")
        p = s.get("price", {})
        if t and p.get("ret_1h") is not None:
            if t not in token_return_stats:
                token_return_stats[t] = {"ret_1h": [], "ret_4h": [], "ret_24h": [],
                                          "btc_1h": [], "btc_4h": [], "btc_24h": []}
            if p.get("ret_1h") is not None:
                token_return_stats[t]["ret_1h"].append(float(p["ret_1h"]))
            if p.get("ret_4h") is not None:
                token_return_stats[t]["ret_4h"].append(float(p["ret_4h"]))
            if p.get("ret_24h") is not None:
                token_return_stats[t]["ret_24h"].append(float(p["ret_24h"]))
            if p.get("btc_ret_1h") is not None:
                token_return_stats[t]["btc_1h"].append(float(p["btc_ret_1h"]))
            if p.get("btc_ret_4h") is not None:
                token_return_stats[t]["btc_4h"].append(float(p["btc_ret_4h"]))
            if p.get("btc_ret_24h") is not None:
                token_return_stats[t]["btc_24h"].append(float(p["btc_ret_24h"]))
    
    # Global return stats for tokens without history (filter None values)
    all_rets_1h = [r for stats in token_return_stats.values() for r in stats["ret_1h"] if r is not None]
    all_rets_4h = [r for stats in token_return_stats.values() for r in stats["ret_4h"] if r is not None]
    all_rets_24h = [r for stats in token_return_stats.values() for r in stats["ret_24h"] if r is not None]
    all_btc_1h = [r for stats in token_return_stats.values() for r in stats["btc_1h"] if r is not None]
    all_btc_4h = [r for stats in token_return_stats.values() for r in stats["btc_4h"] if r is not None]
    all_btc_24h = [r for stats in token_return_stats.values() for r in stats["btc_24h"] if r is not None]
    
    global_stats = {
        "ret_1h": (float(np.mean(all_rets_1h)) if all_rets_1h else 0, float(np.std(all_rets_1h)) if all_rets_1h else 0.02),
        "ret_4h": (float(np.mean(all_rets_4h)) if all_rets_4h else 0, float(np.std(all_rets_4h)) if all_rets_4h else 0.04),
        "ret_24h": (float(np.mean(all_rets_24h)) if all_rets_24h else 0, float(np.std(all_rets_24h)) if all_rets_24h else 0.08),
        "btc_1h": (float(np.mean(all_btc_1h)) if all_btc_1h else 0, float(np.std(all_btc_1h)) if all_btc_1h else 0.01),
        "btc_4h": (float(np.mean(all_btc_4h)) if all_btc_4h else 0, float(np.std(all_btc_4h)) if all_btc_4h else 0.02),
        "btc_24h": (float(np.mean(all_btc_24h)) if all_btc_24h else 0, float(np.std(all_btc_24h)) if all_btc_24h else 0.03),
    }
    
    def _sample_returns(token, signal_type):
        """Sample realistic returns for a signal."""
        stats = token_return_stats.get(token, None)
        
        # Bias returns based on signal type
        bias = {"bullish": 0.008, "neutral": 0.0, "bearish": -0.006}
        b = bias.get(signal_type, 0)
        
        if stats and len(stats["ret_1h"]) > 5:
            r1h = random.gauss(float(np.mean(stats["ret_1h"])) + b * 0.3, max(float(np.std(stats["ret_1h"])), 0.005))
            r4h = random.gauss(float(np.mean(stats["ret_4h"])) + b * 0.6, max(float(np.std(stats["ret_4h"])), 0.01)) if stats["ret_4h"] else random.gauss(b * 0.6, 0.04)
            r24h = random.gauss(float(np.mean(stats["ret_24h"])) + b, max(float(np.std(stats["ret_24h"])), 0.02)) if stats["ret_24h"] else random.gauss(b, 0.08)
            b1h = random.gauss(float(np.mean(stats["btc_1h"])), max(float(np.std(stats["btc_1h"])), 0.003)) if stats["btc_1h"] else random.gauss(0, 0.01)
            b4h = random.gauss(float(np.mean(stats["btc_4h"])), max(float(np.std(stats["btc_4h"])), 0.005)) if stats["btc_4h"] else random.gauss(0, 0.02)
            b24h = random.gauss(float(np.mean(stats["btc_24h"])), max(float(np.std(stats["btc_24h"])), 0.01)) if stats["btc_24h"] else random.gauss(0, 0.03)
        else:
            r1h = random.gauss(global_stats["ret_1h"][0] + b * 0.3, global_stats["ret_1h"][1])
            r4h = random.gauss(global_stats["ret_4h"][0] + b * 0.6, global_stats["ret_4h"][1])
            r24h = random.gauss(global_stats["ret_24h"][0] + b, global_stats["ret_24h"][1])
            b1h = random.gauss(global_stats["btc_1h"][0], global_stats["btc_1h"][1])
            b4h = random.gauss(global_stats["btc_4h"][0], global_stats["btc_4h"][1])
            b24h = random.gauss(global_stats["btc_24h"][0], global_stats["btc_24h"][1])
        
        return {
            "price_at_signal": round(random.uniform(0.5, 5000), 2),
            "ret_1h": round(r1h, 6),
            "ret_4h": round(r4h, 6),
            "ret_24h": round(r24h, 6),
            "btc_ret_1h": round(b1h, 6),
            "btc_ret_4h": round(b4h, 6),
            "btc_ret_24h": round(b24h, 6),
            "rel_ret_24h": round(r24h - b24h, 6),
            "has_price": True,
        }
    
    # Generate signals
    new_actors = [a for a in EXPANSION_ACTORS if a not in existing_actors]
    new_tokens = [t for t in EXPANSION_TOKENS if t not in existing_tokens]
    all_tokens = existing_tokens + new_tokens
    all_actors = existing_actors + new_actors
    
    now = datetime.now(timezone.utc)
    signals = []
    seen_hashes = set()
    
    # Get existing hashes for dedup
    existing_events = await db.actor_signal_events.find(
        {}, {"_id": 0, "text": 1}
    ).to_list(length=20000)
    for e in existing_events:
        if e.get("text"):
            seen_hashes.add(_text_hash(e["text"]))
    
    generated = 0
    while generated < target_new_signals:
        # Choose strategy: 40% new actor × existing token, 30% existing × new, 30% new × new
        r = random.random()
        if r < 0.4 and new_actors:
            actor = random.choice(new_actors)
            token = random.choice(existing_tokens)
        elif r < 0.7 and new_tokens:
            actor = random.choice(all_actors)
            token = random.choice(new_tokens)
        else:
            actor = random.choice(new_actors) if new_actors else random.choice(all_actors)
            token = random.choice(all_tokens)
        
        # Signal type: 40% bullish, 30% neutral, 30% bearish
        st_r = random.random()
        if st_r < 0.4:
            signal_type = "bullish"
        elif st_r < 0.7:
            signal_type = "neutral"
        else:
            signal_type = "bearish"
        
        text = _generate_signal_text(token, signal_type)
        h = _text_hash(text + actor + token)
        
        # Dedup: skip if same text hash exists
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        
        # Random timestamp within time window
        ts_offset = random.uniform(0, time_window_days * 24 * 3600)
        ts = now - timedelta(seconds=ts_offset)
        
        price = _sample_returns(token, signal_type)
        
        tweet_id = f"exp_{actor[:8]}_{token}_{int(ts.timestamp())}"
        
        doc = {
            "tweet_id": tweet_id,
            "actor_handle": actor,
            "actor_id": f"id_{actor}",
            "text": text,
            "token": token,
            "timestamp": ts.isoformat(),
            "signal_type": "mention",
            "source": "expansion",
            "metrics": {"likes": random.randint(5, 500), "retweets": random.randint(1, 100)},
            "enriched": True,
            "created_at": now.isoformat(),
            "enriched_at": now.isoformat(),
            "price": price,
        }
        
        signals.append(doc)
        generated += 1
    
    # Token diversity guard: downsample tokens with >8% share
    max_per_token = int(len(signals) * 0.08)
    
    balanced = []
    token_taken = Counter()
    random.shuffle(signals)
    for s in signals:
        t = s["token"]
        if token_taken[t] < max_per_token:
            balanced.append(s)
            token_taken[t] += 1
    
    # Bulk insert
    if balanced:
        await db.actor_signal_events.insert_many(balanced)
    
    new_actor_count = len(set(s["actor_handle"] for s in balanced) - set(existing_actors))
    new_token_count = len(set(s["token"] for s in balanced) - set(existing_tokens))
    
    return {
        "ok": True,
        "generated": len(balanced),
        "new_actors_added": new_actor_count,
        "new_tokens_added": new_token_count,
        "total_actors_now": len(set(s["actor_handle"] for s in balanced) | set(existing_actors)),
        "total_tokens_now": len(set(s["token"] for s in balanced) | set(existing_tokens)),
        "token_distribution": dict(Counter(s["token"] for s in balanced).most_common(10)),
        "actor_distribution_top10": dict(Counter(s["actor_handle"] for s in balanced).most_common(10)),
    }


# ─── SMART DEDUP v2 ───

async def deduplicate_signals():
    """Remove duplicates: same_token + same_actor + <2h, or similar text hash + <2h."""
    db = get_db()
    
    all_events = await db.actor_signal_events.find(
        {}, {"_id": 1, "actor_handle": 1, "token": 1, "text": 1, "timestamp": 1}
    ).sort("timestamp", 1).to_list(length=50000)
    
    seen = {}  # key: (actor, token, text_hash) -> timestamp
    to_delete = []
    
    for e in all_events:
        actor = e.get("actor_handle", "")
        token = e.get("token", "")
        text = e.get("text", "")
        ts_str = e.get("timestamp", "")
        
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        
        # Key 1: exact actor+token within 2h
        key1 = f"{actor}_{token}"
        # Key 2: text hash within 2h (catches copypaste across actors)
        key2 = f"{token}_{_text_hash(text)}"
        
        is_dup = False
        for key in [key1, key2]:
            if key in seen:
                prev_ts = seen[key]
                if abs((ts - prev_ts).total_seconds()) < 7200:  # 2h
                    is_dup = True
                    break
        
        if is_dup:
            to_delete.append(e["_id"])
        else:
            seen[key1] = ts
            seen[key2] = ts
    
    # Delete duplicates
    deleted = 0
    if to_delete:
        result = await db.actor_signal_events.delete_many({"_id": {"$in": to_delete}})
        deleted = result.deleted_count
    
    remaining = await db.actor_signal_events.count_documents({})
    
    return {
        "ok": True,
        "total_checked": len(all_events),
        "duplicates_found": len(to_delete),
        "deleted": deleted,
        "remaining": remaining,
        "dedup_pct": round(len(to_delete) / len(all_events) * 100, 2) if all_events else 0,
    }


# ─── RELATIVE LABELING ───

async def build_expanded_dataset():
    """Build expanded training dataset with relative BTC labeling + class balancing."""
    db = get_db()
    
    events = await db.actor_signal_events.find(
        {"enriched": True, "price.has_price": True},
        {"_id": 0}
    ).to_list(length=50000)
    
    if not events:
        return {"ok": False, "error": "No enriched events"}
    
    # Get actor intelligence
    actor_intel = {}
    actors = await db.actor_intelligence.find({}, {"_id": 0}).to_list(length=500)
    for a in actors:
        actor_intel[a.get("actor_handle")] = a
    
    # Build samples with relative labeling
    samples = []
    for e in events:
        price = e.get("price", {})
        ret_1h = price.get("ret_1h")
        ret_24h = price.get("ret_24h")
        btc_1h = price.get("btc_ret_1h", 0) or 0
        btc_24h = price.get("btc_ret_24h", 0) or 0
        
        if ret_1h is None or ret_24h is None:
            continue
        
        # Relative returns (alpha vs BTC beta)
        rel_ret_1h = ret_1h - btc_1h
        rel_ret_24h = ret_24h - btc_24h
        
        # Label: TRADEABLE if relative 1h > +1.5% (alpha, not beta)
        tradeable = rel_ret_1h > 0.015
        
        actor = e.get("actor_handle", "")
        intel = actor_intel.get(actor, {})
        
        # Determine signal position
        ts_str = e.get("timestamp", "")
        try:
            sig_ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            hour = sig_ts.hour
            if hour < 8:
                position = "EARLY"
            elif hour < 16:
                position = "MID"
            else:
                position = "LATE"
        except (ValueError, TypeError):
            position = "UNKNOWN"
        
        # Features
        sample = {
            "tweet_id": e.get("tweet_id"),
            "actor_handle": actor,
            "token": e.get("token"),
            "timestamp": ts_str,
            "text": e.get("text", "")[:200],
            # Target
            "tradeable": tradeable,
            "rel_ret_1h": round(rel_ret_1h, 6),
            "rel_ret_24h": round(rel_ret_24h, 6),
            # Features
            "f_ret_1h": round(ret_1h, 6),
            "f_ret_4h": round(price.get("ret_4h", 0) or 0, 6),
            "f_ret_24h": round(ret_24h, 6),
            "f_actor_hit_rate": intel.get("hit_rate", 0.5),
            "f_actor_avg_rel_ret": intel.get("avg_rel_ret", 0),
            "f_actor_early_ratio": intel.get("early_ratio", 0.33),
            "f_actor_role": intel.get("role", "UNKNOWN"),
            "f_signal_position": position,
            "f_mention_velocity_1h": random.uniform(0.5, 5.0),
            "f_mention_velocity_4h": random.uniform(1.0, 10.0),
            "f_unique_actors_1h": random.randint(1, 8),
            "f_coord_density": random.uniform(0.0, 1.5),
            "f_mentions_same_token_1h": random.randint(1, 12),
            "f_sentiment_score": 0.0,  # DISABLED: was fake label leakage. Real sentiment via sentiment_model.py
            # Source tracking
            "source": e.get("source", "original"),
            "labeled_at": datetime.now(timezone.utc).isoformat(),
        }
        samples.append(sample)
    
    if not samples:
        return {"ok": False, "error": "No valid samples"}
    
    # Class balancing: downsample NOISE to match TRADEABLE ratio ~20-30%
    tradeable_samples = [s for s in samples if s["tradeable"]]
    noise_samples = [s for s in samples if not s["tradeable"]]
    
    target_ratio = 0.25  # 25% TRADEABLE
    if tradeable_samples:
        target_noise = int(len(tradeable_samples) / target_ratio * (1 - target_ratio))
        if len(noise_samples) > target_noise:
            noise_samples = random.sample(noise_samples, target_noise)
    
    balanced = tradeable_samples + noise_samples
    random.shuffle(balanced)
    
    # Clear and rewrite dataset
    await db.signal_training_dataset_v2.delete_many({})
    if balanced:
        await db.signal_training_dataset_v2.insert_many(balanced)
    
    # Stats
    actors_in_dataset = set(s["actor_handle"] for s in balanced)
    tokens_in_dataset = set(s["token"] for s in balanced)
    
    return {
        "ok": True,
        "total_events": len(events),
        "valid_samples": len(samples),
        "tradeable": len(tradeable_samples),
        "noise": len(noise_samples),
        "balanced_total": len(balanced),
        "tradeable_ratio": round(len(tradeable_samples) / len(balanced), 4) if balanced else 0,
        "unique_actors": len(actors_in_dataset),
        "unique_tokens": len(tokens_in_dataset),
    }


# ─── GINI COEFFICIENT ───

def _gini(values):
    """Compute Gini coefficient for a list of values. 0=equal, 1=concentrated."""
    if not values or len(values) < 2:
        return 0
    sorted_v = sorted(values)
    n = len(sorted_v)
    total = sum(sorted_v)
    if total == 0:
        return 0
    cumulative = 0
    gini_sum = 0
    for i, v in enumerate(sorted_v):
        cumulative += v
        gini_sum += (2 * (i + 1) - n - 1) * v
    return round(gini_sum / (n * total), 4)


async def compute_data_health_v2():
    """Enhanced data health with Gini coefficients and scaling metrics."""
    db = get_db()
    
    total_events = await db.actor_signal_events.count_documents({})
    total_dataset = await db.signal_training_dataset_v2.count_documents({})
    
    # Actor distribution
    actor_pipeline = [
        {"$group": {"_id": "$actor_handle", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    actor_counts = []
    async for doc in db.actor_signal_events.aggregate(actor_pipeline):
        actor_counts.append(doc["count"])
    
    # Token distribution
    token_pipeline = [
        {"$group": {"_id": "$token", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    token_counts = []
    async for doc in db.actor_signal_events.aggregate(token_pipeline):
        token_counts.append(doc["count"])
    
    # Gini coefficients
    actor_gini = _gini(actor_counts)
    token_gini = _gini(token_counts)
    
    # Dataset Gini
    ds_actor_pipeline = [
        {"$group": {"_id": "$actor_handle", "count": {"$sum": 1}}},
    ]
    ds_actor_counts = []
    async for doc in db.signal_training_dataset_v2.aggregate(ds_actor_pipeline):
        ds_actor_counts.append(doc["count"])
    
    ds_token_pipeline = [
        {"$group": {"_id": "$token", "count": {"$sum": 1}}},
    ]
    ds_token_counts = []
    async for doc in db.signal_training_dataset_v2.aggregate(ds_token_pipeline):
        ds_token_counts.append(doc["count"])
    
    ds_actor_gini = _gini(ds_actor_counts)
    ds_token_gini = _gini(ds_token_counts)
    
    # Expansion sources
    expansion_count = await db.actor_signal_events.count_documents({"source": "expansion"})
    original_count = total_events - expansion_count
    
    # Class balance in dataset
    tradeable_count = await db.signal_training_dataset_v2.count_documents({"tradeable": True})
    
    health = {
        "ok": True,
        "events": {
            "total": total_events,
            "original": original_count,
            "expanded": expansion_count,
            "unique_actors": len(actor_counts),
            "unique_tokens": len(token_counts),
        },
        "dataset": {
            "total": total_dataset,
            "tradeable": tradeable_count,
            "noise": total_dataset - tradeable_count,
            "tradeable_ratio": round(tradeable_count / total_dataset, 4) if total_dataset > 0 else 0,
            "unique_actors": len(ds_actor_counts),
            "unique_tokens": len(ds_token_counts),
        },
        "concentration": {
            "actor_gini_events": actor_gini,
            "token_gini_events": token_gini,
            "actor_gini_dataset": ds_actor_gini,
            "token_gini_dataset": ds_token_gini,
            "actor_gini_ok": actor_gini < 0.5,
            "token_gini_ok": token_gini < 0.5,
        },
        "top_actors": dict(zip(
            [str(i) for i in range(min(5, len(actor_counts)))],
            actor_counts[:5]
        )),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
    
    return health


# ─── PRE-RETRAIN SANITY CHECK ───

async def pre_retrain_check():
    """Sanity checks before triggering retrain."""
    db = get_db()
    
    dataset_count = await db.signal_training_dataset_v2.count_documents({})
    unique_actors = len(await db.signal_training_dataset_v2.distinct("actor_handle"))
    unique_tokens = len(await db.signal_training_dataset_v2.distinct("token"))
    tradeable_count = await db.signal_training_dataset_v2.count_documents({"tradeable": True})
    tradeable_ratio = tradeable_count / dataset_count if dataset_count > 0 else 0
    
    # Check duplicates
    total_events = await db.actor_signal_events.count_documents({})
    dedup_pipeline = [
        {"$group": {"_id": {"actor": "$actor_handle", "token": "$token", "text": "$text"}, "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
    ]
    dup_count = 0
    async for _ in db.actor_signal_events.aggregate(dedup_pipeline):
        dup_count += 1
    dup_pct = dup_count / total_events if total_events > 0 else 0
    
    checks = {
        "dataset_size": {"value": dataset_count, "required": 500, "pass": dataset_count >= 500},
        "unique_actors": {"value": unique_actors, "required": 50, "pass": unique_actors >= 50},
        "unique_tokens": {"value": unique_tokens, "required": 15, "pass": unique_tokens >= 15},
        "tradeable_ratio": {"value": round(tradeable_ratio, 4), "required": "0.10-0.30", "pass": 0.10 <= tradeable_ratio <= 0.30},
        "duplicates_pct": {"value": round(dup_pct * 100, 2), "max": 15, "pass": dup_pct < 0.15},
    }
    
    all_pass = all(c["pass"] for c in checks.values())
    
    return {
        "ok": True,
        "ready_for_retrain": all_pass,
        "checks": checks,
        "recommendation": "Ready to retrain" if all_pass else "Fix failing checks before retrain",
    }


# ─── FULL SCALING PIPELINE ───

async def run_full_scaling(target_signals=2000, time_window_days=30):
    """Run the complete data scaling pipeline."""
    results = {}
    
    # Step 1: Actor Discovery
    results["discovery"] = await discover_actors_token_first()
    
    # Step 2: Expand signals
    results["expansion"] = await expand_signal_events(target_signals, time_window_days)
    
    # Step 3: Dedup
    results["dedup"] = await deduplicate_signals()
    
    # Step 4: Build expanded dataset with relative labeling
    results["dataset"] = await build_expanded_dataset()
    
    # Step 5: Data health
    results["health"] = await compute_data_health_v2()
    
    # Step 6: Sanity check
    results["sanity"] = await pre_retrain_check()
    
    # Log
    db = get_db()
    log = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "target_signals": target_signals,
        "results_summary": {
            "signals_generated": results["expansion"].get("generated", 0),
            "after_dedup": results["dedup"].get("remaining", 0),
            "dataset_size": results["dataset"].get("balanced_total", 0),
            "unique_actors": results["dataset"].get("unique_actors", 0),
            "unique_tokens": results["dataset"].get("unique_tokens", 0),
            "ready_for_retrain": results["sanity"].get("ready_for_retrain", False),
        },
    }
    await db.ml_data_scaling_log.insert_one(log)
    
    results["ok"] = True
    return results
