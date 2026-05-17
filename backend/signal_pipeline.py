"""
Actor Signal Pipeline — P0 implementation
Converts parsed_tweets → actor_signal_events with price alignment and actor intelligence.

Pipeline stages:
  P0.1: Signalization — parsed_tweets → actor_signal_events
  P0.2: Price alignment — enrich with returns at +1h/+4h/+24h + BTC benchmark
  P0.3: Actor intelligence — hit_rate, avg_rel_ret, early_ratio, role classification
  P0.4: Dataset assembly — ready for ML labeling
"""

import os
import re
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")

_client = None
_db = None
_conn_db = None


def get_dbs():
    global _client, _db, _conn_db
    if _client is None:
        _client = AsyncIOMotorClient(MONGO_URL)
        _db = _client[DB_NAME]
        _conn_db = _client["connections_db"]
    return _db, _conn_db


# ─── Signal type classification ───
CONVICTION_WORDS = ["bullish", "buying", "accumulating", "long", "moon", "pump", "send it", "aping", "all in"]
WARNING_WORDS = ["bearish", "dump", "crash", "sell", "short", "rug", "scam", "overvalued", "exit"]
LISTING_WORDS = ["listed", "listing", "launch", "live on", "trading on"]
ROTATION_WORDS = ["rotating", "moving to", "switching", "from.*to", "selling.*buying"]
ACCUMULATION_WORDS = ["dca", "accumulate", "adding", "stacking", "loading"]


def classify_signal_type(text):
    """Classify tweet into signal type based on content."""
    t = text.lower()
    if any(w in t for w in LISTING_WORDS):
        return "listing"
    if any(re.search(w, t) for w in ROTATION_WORDS):
        return "rotation"
    if any(w in t for w in ACCUMULATION_WORDS):
        return "accumulation"
    if any(w in t for w in WARNING_WORDS):
        return "warning"
    if any(w in t for w in CONVICTION_WORDS):
        return "conviction"
    return "mention"


# ─── P0.1: Signalization ───
async def build_signal_events():
    """Convert parsed_tweets → actor_signal_events."""
    db, conn_db = get_dbs()
    
    tweets = await conn_db.parsed_tweets.find(
        {}, {"_id": 0}
    ).sort("createdAt", -1).to_list(length=2000)
    
    if not tweets:
        return {"ok": False, "error": "No parsed_tweets found"}
    
    events = []
    for tw in tweets:
        author = tw.get("author", {})
        handle = author.get("username", author.get("handle", "unknown"))
        tokens = tw.get("tokens", [])
        text = tw.get("text", "")
        created_at = tw.get("createdAt")
        
        if not tokens or not handle or handle == "unknown":
            continue
        
        signal_type = classify_signal_type(text)
        
        for token in tokens:
            events.append({
                "tweet_id": tw.get("id", ""),
                "actor_handle": handle,
                "actor_id": author.get("id", ""),
                "text": text[:500],
                "token": token,
                "timestamp": created_at,
                "signal_type": signal_type,
                "source": "twitter_kol",
                "metrics": {
                    "likes": tw.get("likes", 0),
                    "reposts": tw.get("reposts", 0),
                    "replies": tw.get("replies", 0),
                    "views": tw.get("views", 0),
                },
                "enriched": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
    
    if events:
        await db.actor_signal_events.delete_many({})
        await db.actor_signal_events.insert_many(events)
    
    return {
        "ok": True,
        "total_tweets": len(tweets),
        "signal_events_created": len(events),
        "unique_actors": len(set(e["actor_handle"] for e in events)),
        "unique_tokens": len(set(e["token"] for e in events)),
        "signal_types": dict(__import__("collections").Counter(e["signal_type"] for e in events)),
    }


# ─── P0.2: Price Alignment ───
def _token_to_symbol(token):
    """Map token name to exchange symbol (e.g., BTC → BTCUSDT)."""
    return f"{token.upper()}USDT"


async def _get_price_at(db, symbol, ts_ms, window_ms=3600000):
    """Find closest price to timestamp from market_price_history or exchange_observations."""
    # Try market_price_history first (1h candles)
    candle = await db.market_price_history.find_one(
        {"symbol": symbol, "ts": {"$lte": ts_ms, "$gte": ts_ms - window_ms * 2}},
        {"_id": 0, "c": 1, "ts": 1},
        sort=[("ts", -1)]
    )
    if candle:
        return candle.get("c")
    
    # Fallback to exchange_observations
    obs = await db.exchange_observations.find_one(
        {"symbol": symbol, "timestamp": {"$lte": ts_ms, "$gte": ts_ms - window_ms * 2}},
        {"_id": 0, "market.price": 1, "timestamp": 1},
        sort=[("timestamp", -1)]
    )
    if obs:
        return obs.get("market", {}).get("price")
    
    return None


async def _get_price_after(db, symbol, ts_ms, offset_hours):
    """Get price at ts + offset_hours."""
    target_ts = ts_ms + (offset_hours * 3600000)
    window = 3600000  # 1h tolerance
    
    candle = await db.market_price_history.find_one(
        {"symbol": symbol, "ts": {"$lte": target_ts + window, "$gte": target_ts - window}},
        {"_id": 0, "c": 1, "ts": 1},
        sort=[("ts", 1)]
    )
    if candle:
        return candle.get("c")
    
    obs = await db.exchange_observations.find_one(
        {"symbol": symbol, "timestamp": {"$lte": target_ts + window, "$gte": target_ts - window}},
        {"_id": 0, "market.price": 1},
        sort=[("timestamp", 1)]
    )
    if obs:
        return obs.get("market", {}).get("price")
    
    return None


def _ts_to_ms(ts):
    """Convert various timestamp formats to milliseconds."""
    if isinstance(ts, (int, float)):
        if ts > 1e12:
            return ts
        return ts * 1000
    if isinstance(ts, datetime):
        return ts.timestamp() * 1000
    if isinstance(ts, str):
        # Try Twitter format first: "Wed Mar 25 02:23:09 +0000 2026"
        try:
            dt = datetime.strptime(ts, "%a %b %d %H:%M:%S %z %Y")
            return dt.timestamp() * 1000
        except (ValueError, TypeError):
            pass
        for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%SZ"]:
            try:
                return datetime.strptime(ts.replace("+00:00", "Z").rstrip("Z") + "Z", fmt.replace("%z", "Z")).replace(tzinfo=timezone.utc).timestamp() * 1000
            except (ValueError, TypeError):
                continue
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000
        except Exception:
            pass
    return None


async def enrich_with_prices():
    """Add price alignment to actor_signal_events."""
    db, _ = get_dbs()
    
    events = await db.actor_signal_events.find(
        {"enriched": False}
    ).to_list(length=5000)
    
    if not events:
        return {"ok": True, "message": "No events to enrich", "enriched": 0}
    
    enriched_count = 0
    skipped = 0
    
    for event in events:
        token = event.get("token")
        ts = event.get("timestamp")
        ts_ms = _ts_to_ms(ts)
        
        if not ts_ms:
            skipped += 1
            continue
        
        symbol = _token_to_symbol(token)
        btc_symbol = "BTCUSDT"
        
        # Get prices
        price_at = await _get_price_at(db, symbol, ts_ms)
        price_1h = await _get_price_after(db, symbol, ts_ms, 1)
        price_4h = await _get_price_after(db, symbol, ts_ms, 4)
        price_24h = await _get_price_after(db, symbol, ts_ms, 24)
        
        btc_at = await _get_price_at(db, btc_symbol, ts_ms)
        btc_1h = await _get_price_after(db, btc_symbol, ts_ms, 1)
        btc_4h = await _get_price_after(db, btc_symbol, ts_ms, 4)
        btc_24h = await _get_price_after(db, btc_symbol, ts_ms, 24)
        
        def _ret(p_after, p_at):
            if p_after and p_at and p_at > 0:
                return round((p_after - p_at) / p_at, 6)
            return None
        
        ret_1h = _ret(price_1h, price_at)
        ret_4h = _ret(price_4h, price_at)
        ret_24h = _ret(price_24h, price_at)
        btc_ret_1h = _ret(btc_1h, btc_at)
        btc_ret_4h = _ret(btc_4h, btc_at)
        btc_ret_24h = _ret(btc_24h, btc_at)
        
        rel_ret_24h = None
        if ret_24h is not None and btc_ret_24h is not None:
            rel_ret_24h = round(ret_24h - btc_ret_24h, 6)
        
        price_data = {
            "price_at_signal": price_at,
            "ret_1h": ret_1h,
            "ret_4h": ret_4h,
            "ret_24h": ret_24h,
            "btc_ret_1h": btc_ret_1h,
            "btc_ret_4h": btc_ret_4h,
            "btc_ret_24h": btc_ret_24h,
            "rel_ret_24h": rel_ret_24h,
            "has_price": price_at is not None,
        }
        
        await db.actor_signal_events.update_one(
            {"_id": event["_id"]},
            {"$set": {"price": price_data, "enriched": True, "enriched_at": datetime.now(timezone.utc).isoformat()}}
        )
        enriched_count += 1
    
    return {"ok": True, "enriched": enriched_count, "skipped": skipped, "total": len(events)}


# ─── P0.3: Actor Intelligence ───
async def compute_actor_metrics():
    """Compute per-actor performance metrics from enriched signal events."""
    db, _ = get_dbs()
    
    events = await db.actor_signal_events.find(
        {"enriched": True, "price.has_price": True},
        {"_id": 0}
    ).to_list(length=10000)
    
    if not events:
        return {"ok": True, "message": "No enriched events", "actors": 0}
    
    # Group by actor
    actor_signals = {}
    for e in events:
        handle = e.get("actor_handle")
        if handle not in actor_signals:
            actor_signals[handle] = []
        actor_signals[handle].append(e)
    
    actor_profiles = []
    for handle, signals in actor_signals.items():
        total = len(signals)
        
        rets_24h = [s["price"]["ret_24h"] for s in signals if s["price"].get("ret_24h") is not None]
        rel_rets = [s["price"]["rel_ret_24h"] for s in signals if s["price"].get("rel_ret_24h") is not None]
        
        # Hit rate: % of signals where token outperformed BTC in 24h
        hits = [r for r in rel_rets if r > 0]
        hit_rate = len(hits) / len(rel_rets) if rel_rets else 0
        
        # Average relative return
        avg_rel_ret = sum(rel_rets) / len(rel_rets) if rel_rets else 0
        avg_abs_ret = sum(rets_24h) / len(rets_24h) if rets_24h else 0
        
        # Early ratio: signals where price moved AFTER signal (ret_1h small, ret_24h meaningful)
        early_count = 0
        late_count = 0
        for s in signals:
            p = s["price"]
            r1 = p.get("ret_1h")
            r24 = p.get("ret_24h")
            if r1 is not None and r24 is not None:
                if abs(r1) < 0.005 and abs(r24) > 0.006:  # Price didn't react in 1h but moved in 24h
                    early_count += 1
                elif abs(r1) > 0.01:  # Price already moving when signal came
                    late_count += 1
        
        timed = early_count + late_count
        early_ratio = early_count / timed if timed > 0 else 0
        late_ratio = late_count / timed if timed > 0 else 0
        
        # Role classification
        if hit_rate > 0.6 and early_ratio > 0.5:
            role = "DRIVER"
        elif hit_rate > 0.5 and early_ratio < 0.3:
            role = "AMPLIFIER"
        elif hit_rate < 0.4:
            role = "NOISE"
        else:
            role = "TRACKER"
        
        # Signal types distribution
        from collections import Counter
        type_dist = dict(Counter(s.get("signal_type") for s in signals))
        
        profile = {
            "actor_handle": handle,
            "total_signals": total,
            "signals_with_price": len(rets_24h),
            "hit_rate_24h": round(hit_rate, 4),
            "avg_rel_ret_24h": round(avg_rel_ret, 6),
            "avg_abs_ret_24h": round(avg_abs_ret, 6),
            "early_ratio": round(early_ratio, 4),
            "late_ratio": round(late_ratio, 4),
            "role": role,
            "signal_types": type_dist,
            "avg_likes": round(sum(s["metrics"]["likes"] for s in signals) / total, 0) if total > 0 else 0,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }
        actor_profiles.append(profile)
    
    # Save to DB
    if actor_profiles:
        await db.actor_intelligence.delete_many({})
        await db.actor_intelligence.insert_many(actor_profiles)
        # Remove _id injected by insert_many
        for p in actor_profiles:
            p.pop("_id", None)
    
    return {
        "ok": True,
        "actors": len(actor_profiles),
        "roles": dict(__import__("collections").Counter(p["role"] for p in actor_profiles)),
        "top_drivers": sorted(
            [p for p in actor_profiles if p["role"] == "DRIVER"],
            key=lambda x: -x["hit_rate_24h"]
        )[:5],
        "profiles": sorted(actor_profiles, key=lambda x: -x["hit_rate_24h"]),
    }


# ─── P0.4: Dataset Assembly (v3 — tightened labels + actor power + coordination + binary target) ───
async def build_training_dataset():
    """Assemble ML training dataset with proper labeling and feature engineering."""
    db, _ = get_dbs()
    
    # Load actor profiles
    actors = await db.actor_intelligence.find({}, {"_id": 0}).to_list(length=1000)
    actor_map = {a["actor_handle"]: a for a in actors}
    
    # Load ALL enriched events (for coordination computation)
    all_events = await db.actor_signal_events.find(
        {"enriched": True, "price.has_price": True},
        {"_id": 0}
    ).to_list(length=10000)
    
    if not all_events:
        return {"ok": True, "message": "No enriched events", "samples": 0}
    
    # ── Pre-compute coordination index: how many actors mentioned same token within 1h ──
    from collections import defaultdict
    token_time_events = defaultdict(list)
    for e in all_events:
        ts_ms = _ts_to_ms(e.get("timestamp"))
        if ts_ms:
            token_time_events[e["token"]].append({
                "ts": ts_ms, "actor": e["actor_handle"]
            })
    
    def _coordination(token, ts_ms, window_ms=3600000):
        """Count unique actors mentioning same token within ±1h window."""
        events_for_token = token_time_events.get(token, [])
        nearby = [ev for ev in events_for_token if abs(ev["ts"] - ts_ms) <= window_ms]
        unique_actors = set(ev["actor"] for ev in nearby)
        return len(unique_actors), len(nearby)
    
    samples = []
    for e in all_events:
        p = e.get("price", {})
        actor = actor_map.get(e.get("actor_handle"), {})
        
        rel_ret_24h = p.get("rel_ret_24h")
        ret_1h = p.get("ret_1h")
        ret_4h = p.get("ret_4h")
        ret_24h_abs = p.get("ret_24h")
        
        if rel_ret_24h is None:
            continue
        
        ts_ms = _ts_to_ms(e.get("timestamp"))
        
        # ── Signal Position ──
        position = "UNKNOWN"
        if ret_1h is not None:
            if abs(ret_1h) < 0.005:
                position = "EARLY"
            elif abs(ret_1h) < 0.01:
                position = "MID"
            else:
                position = "LATE"
        
        # ── Coordination ──
        coord_actors, coord_mentions = _coordination(e["token"], ts_ms) if ts_ms else (0, 0)
        
        # ── Actor quality ──
        actor_hit = actor.get("hit_rate_24h", 0)
        actor_early = actor.get("early_ratio", 0)
        actor_ret = actor.get("avg_rel_ret_24h", 0)
        actor_signals = actor.get("total_signals", 0)
        actor_role = actor.get("role", "UNKNOWN")
        is_quality_actor = actor_hit > 0.5
        
        # ── TIGHTENED LABELS ──
        # ENTRY: early position + strong rel return + quality actor
        # FOLLOW: mid position + decent return (already moving but not late)
        # EXIT: late / weak follow-through / bad return
        # NOISE: everything else
        early = position == "EARLY"
        mid = position == "MID"
        late = position == "LATE"
        
        strong_alpha = rel_ret_24h > 0.008     # top ~20% relative performance
        decent_alpha = rel_ret_24h > 0.004     # top ~35%
        negative_alpha = rel_ret_24h < -0.004  # bottom ~35%
        
        if early and strong_alpha and is_quality_actor:
            label_4 = "ENTRY"
        elif early and strong_alpha:
            label_4 = "ENTRY"       # Strong alpha even without quality actor
        elif mid and decent_alpha:
            label_4 = "FOLLOW"
        elif late and decent_alpha:
            label_4 = "FOLLOW"      # Late but still has juice
        elif negative_alpha:
            label_4 = "EXIT"
        elif late:
            label_4 = "EXIT"        # Late position = likely exit liquidity
        else:
            label_4 = "NOISE"
        
        # ── BINARY TARGET (P0 priority) ──
        tradeable = label_4 in ("ENTRY", "FOLLOW")
        label_binary = "TRADEABLE" if tradeable else "NON_TRADEABLE"
        
        sample = {
            "tweet_id": e.get("tweet_id"),
            "actor_handle": e.get("actor_handle"),
            "token": e.get("token"),
            "timestamp": e.get("timestamp"),
            "signal_type": e.get("signal_type"),
            "source": e.get("source", "original"),
            # ── Actor features ──
            "f_actor_hit_rate": actor_hit,
            "f_actor_early_ratio": actor_early,
            "f_actor_avg_rel_ret": actor_ret,
            "f_actor_signal_count": actor_signals,
            "f_actor_role": actor_role,
            # ── Signal features ──
            "f_signal_position": position,
            "f_signal_type": e.get("signal_type", "mention"),
            "f_likes": e.get("metrics", {}).get("likes", 0),
            "f_views": e.get("metrics", {}).get("views", 0),
            "f_reposts": e.get("metrics", {}).get("reposts", 0),
            # ── Price features ──
            "f_ret_1h": ret_1h,
            "f_ret_4h": ret_4h,
            "f_price_at_signal": p.get("price_at_signal"),
            # ── Coordination features ──
            "f_coord_unique_actors_1h": coord_actors,
            "f_coord_mentions_1h": coord_mentions,
            "f_coord_density": coord_mentions / max(coord_actors, 1),
            # ── Raw returns (for evaluation, not training) ──
            "ret_24h_abs": ret_24h_abs,
            "rel_ret_24h": rel_ret_24h,
            "btc_ret_24h": p.get("btc_ret_24h"),
            # ── Labels ──
            "label_4class": label_4,
            "label_binary": label_binary,
            "tradeable": tradeable,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        samples.append(sample)
    
    if samples:
        await db.signal_training_dataset_v2.delete_many({})
        await db.signal_training_dataset_v2.insert_many(samples)
        for s in samples:
            s.pop("_id", None)
    
    from collections import Counter
    label4_dist = dict(Counter(s["label_4class"] for s in samples))
    binary_dist = dict(Counter(s["label_binary"] for s in samples))
    position_dist = dict(Counter(s["f_signal_position"] for s in samples))
    
    # Quick stats on coordination
    coord_vals = [s["f_coord_unique_actors_1h"] for s in samples]
    avg_coord = sum(coord_vals) / len(coord_vals) if coord_vals else 0
    
    return {
        "ok": True,
        "total_samples": len(samples),
        "label_4class": label4_dist,
        "label_binary": binary_dist,
        "position_distribution": position_dist,
        "avg_coordination_actors": round(avg_coord, 2),
        "unique_actors": len(set(s["actor_handle"] for s in samples)),
        "unique_tokens": len(set(s["token"] for s in samples)),
        "feature_count": len([k for k in samples[0].keys() if k.startswith("f_")]) if samples else 0,
    }


# ─── P1: XGBoost Training + Shadow Evaluation ───
FEATURE_COLS = [
    "f_actor_hit_rate",
    "f_actor_early_ratio",
    "f_actor_avg_rel_ret",
    "f_actor_signal_count",
    "f_likes",
    "f_views",
    "f_reposts",
    "f_ret_1h",
    "f_ret_4h",
    "f_coord_unique_actors_1h",
    "f_coord_mentions_1h",
    "f_coord_density",
]

CATEGORICAL_FEATURES = {
    "f_signal_position": {"EARLY": 0, "MID": 1, "LATE": 2, "UNKNOWN": 1},
    "f_actor_role": {"DRIVER": 3, "AMPLIFIER": 2, "TRACKER": 1, "NOISE": 0, "UNKNOWN": 0},
    "f_signal_type": {"conviction": 2, "accumulation": 2, "listing": 1, "rotation": 1, "warning": -1, "mention": 0},
}


def _build_feature_matrix(samples):
    """Convert samples to feature matrix + labels."""
    import numpy as np
    
    X = []
    y = []
    meta = []
    
    for s in samples:
        row = []
        for col in FEATURE_COLS:
            val = s.get(col)
            row.append(float(val) if val is not None else 0.0)
        
        for cat_col, mapping in CATEGORICAL_FEATURES.items():
            val = s.get(cat_col, "UNKNOWN")
            row.append(float(mapping.get(val, 0)))
        
        X.append(row)
        y.append(1 if s.get("tradeable") else 0)
        meta.append({
            "actor": s.get("actor_handle"),
            "token": s.get("token"),
            "rel_ret_24h": s.get("rel_ret_24h", 0),
            "label_4class": s.get("label_4class"),
        })
    
    feature_names = FEATURE_COLS + list(CATEGORICAL_FEATURES.keys())
    return np.array(X), np.array(y), meta, feature_names


async def train_xgboost_model():
    """Train binary XGBoost model: TRADEABLE vs NON_TRADEABLE."""
    import numpy as np
    from xgboost import XGBClassifier
    from sklearn.model_selection import cross_val_predict
    from sklearn.metrics import classification_report
    import pickle
    
    db, _ = get_dbs()
    
    samples = await db.signal_training_dataset_v2.find({}, {"_id": 0}).to_list(length=10000)
    if len(samples) < 50:
        return {"ok": False, "error": f"Not enough samples: {len(samples)}"}
    
    X, y, meta, feature_names = _build_feature_matrix(samples)
    
    # Class balance
    pos_count = int(y.sum())
    neg_count = len(y) - pos_count
    scale_pos = neg_count / max(pos_count, 1)
    
    model = XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        scale_pos_weight=scale_pos,
        eval_metric="logloss",
        use_label_encoder=False,
        random_state=42,
    )
    
    # Cross-validated predictions (leave-one-out would be too slow, use 5-fold)
    y_proba = cross_val_predict(model, X, y, cv=5, method="predict_proba")[:, 1]
    y_pred = (y_proba > 0.5).astype(int)
    
    # Train final model on all data
    model.fit(X, y)
    
    # Feature importance
    importances = dict(zip(feature_names, model.feature_importances_.tolist()))
    importances_sorted = dict(sorted(importances.items(), key=lambda x: -x[1]))
    
    # ── SHADOW EVALUATION (Trading Metrics) ──
    # Sort by predicted probability, take top 10% as "signals"
    top_k = max(int(len(y_proba) * 0.1), 5)
    top_indices = np.argsort(y_proba)[-top_k:]
    
    top_returns = [meta[i]["rel_ret_24h"] for i in top_indices if meta[i]["rel_ret_24h"] is not None]
    all_returns = [m["rel_ret_24h"] for m in meta if m["rel_ret_24h"] is not None]
    
    top_hits = sum(1 for r in top_returns if r > 0)
    top_avg_ret = sum(top_returns) / len(top_returns) if top_returns else 0
    baseline_avg = sum(all_returns) / len(all_returns) if all_returns else 0
    
    # Max drawdown on top signals
    cumulative = 0
    max_dd = 0
    peak = 0
    for r in sorted(top_returns):
        cumulative += r
        peak = max(peak, cumulative)
        max_dd = min(max_dd, cumulative - peak)
    
    # Precision at top signals
    top_actual = [y[i] for i in top_indices]
    precision_top = sum(top_actual) / len(top_actual) if top_actual else 0
    
    # Top signals detail
    top_signals = []
    for i in top_indices:
        top_signals.append({
            "actor": meta[i]["actor"],
            "token": meta[i]["token"],
            "predicted_prob": round(float(y_proba[i]), 4),
            "rel_ret_24h": meta[i]["rel_ret_24h"],
            "label": meta[i]["label_4class"],
            "actual_tradeable": bool(y[i]),
        })
    top_signals.sort(key=lambda x: -x["predicted_prob"])
    
    # Classification report
    report = classification_report(y, y_pred, target_names=["NON_TRADEABLE", "TRADEABLE"], output_dict=True)
    
    # Save model to DB as binary
    model_bytes = pickle.dumps(model)
    model_doc = {
        "name": "signal_quality_xgb_v1",
        "type": "xgboost_binary",
        "target": "tradeable",
        "features": feature_names,
        "model_binary": model_bytes,
        "metrics": {
            "classification_report": report,
            "feature_importance": importances_sorted,
        },
        "shadow_eval": {
            "top_k": top_k,
            "precision_at_top10pct": round(precision_top, 4),
            "hit_rate_top_signals": round(top_hits / len(top_returns), 4) if top_returns else 0,
            "avg_return_top_signals": round(top_avg_ret * 100, 4),
            "avg_return_baseline": round(baseline_avg * 100, 4),
            "alpha_vs_baseline": round((top_avg_ret - baseline_avg) * 100, 4),
            "max_drawdown_pct": round(max_dd * 100, 4),
        },
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "samples_count": len(samples),
    }
    
    await db.signal_models.delete_many({"name": "signal_quality_xgb_v1"})
    await db.signal_models.insert_one(model_doc)
    
    return {
        "ok": True,
        "model": "signal_quality_xgb_v1",
        "samples": len(samples),
        "class_balance": {"TRADEABLE": pos_count, "NON_TRADEABLE": neg_count},
        "classification": {
            "TRADEABLE": {
                "precision": round(report["TRADEABLE"]["precision"], 4),
                "recall": round(report["TRADEABLE"]["recall"], 4),
                "f1": round(report["TRADEABLE"]["f1-score"], 4),
            },
            "NON_TRADEABLE": {
                "precision": round(report["NON_TRADEABLE"]["precision"], 4),
                "recall": round(report["NON_TRADEABLE"]["recall"], 4),
                "f1": round(report["NON_TRADEABLE"]["f1-score"], 4),
            },
        },
        "shadow_eval": model_doc["shadow_eval"],
        "feature_importance_top5": dict(list(importances_sorted.items())[:5]),
        "top_signals": top_signals[:10],
    }


# ─── Full Pipeline ───
async def run_full_pipeline():
    """Run complete P0 pipeline: signalization → price → actors → dataset → live predictions."""
    results = {}
    
    # P0.1
    r1 = await build_signal_events()
    results["p01_signalization"] = r1
    if not r1.get("ok"):
        return {"ok": False, "stage": "P0.1", "error": r1}
    
    # P0.2
    r2 = await enrich_with_prices()
    results["p02_price_alignment"] = r2
    
    # P0.3
    r3 = await compute_actor_metrics()
    results["p03_actor_intelligence"] = r3
    
    # P0.4
    r4 = await build_training_dataset()
    results["p04_dataset"] = r4
    
    # P0.5 — Auto-log live predictions through active + shadow models
    try:
        from ml_ops import run_live_predictions
        r5 = await run_live_predictions()
        results["p05_live_predictions"] = r5
    except Exception as e:
        results["p05_live_predictions"] = {"ok": False, "error": str(e)}
    
    results["ok"] = True
    return results
