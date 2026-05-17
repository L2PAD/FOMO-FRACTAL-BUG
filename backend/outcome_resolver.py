"""
Outcome Resolver — closes the feedback loop.

Periodically scans `sentiment_training_dataset_v3` for unresolved outcomes.
For each sample older than the minimum window, fetches actual price return
and marks tradeable = True/False.

Pipeline:
  UNRESOLVED → age check → fetch price → compute return → label → update

Resolution Windows:
  - 1h:  quick flip signal (min age = 70min to allow data settle)
  - 4h:  swing trade signal (min age = 260min)
  - 24h: position signal (min age = 25h)

Trade Label Logic (V1 — legacy):
  - GOOD:    24h BTC-relative return > 2%
  - BAD:     24h BTC-relative return < -2%
  - NEUTRAL: in between (not tradeable)

Label Logic V2 (Shadow Mode):
  - STRONG_GOOD / WEAK_GOOD / NEUTRAL / WEAK_BAD / STRONG_BAD
  - Peak-aware: uses max/min price in window, not just final
  - Horizon-aware thresholds
  - Written to audit.labels_v2 (does NOT change production label)
"""

import math
from datetime import datetime, timezone, timedelta
from ml_ops import get_db
from enrichment_layer import _find_nearest_price, _compute_return

COLLECTION = "sentiment_training_dataset_v3"

# Min age (seconds) before we attempt to resolve each window
MIN_AGE_1H = 70 * 60       # 70min
MIN_AGE_4H = 260 * 60      # 4h20m
MIN_AGE_24H = 25 * 3600    # 25h

# Tradeable thresholds (% BTC-relative) — V1 legacy
GOOD_THRESHOLD = 2.0
BAD_THRESHOLD = -2.0

# ─── Label V2: Horizon-aware thresholds (%) ───
LABEL_V2_THRESHOLDS = {
    "24H": {"weak": 1.5, "strong": 2.5},
    "7D":  {"weak": 2.0, "strong": 5.0},
    "30D": {"weak": 4.0, "strong": 10.0},
}
# Default fallback for unknown horizons
LABEL_V2_DEFAULT = {"weak": 1.5, "strong": 3.0}


async def _find_peak_prices(token, ts_ms, window_ms):
    """
    Find max and min prices within [ts_ms, ts_ms + window_ms].
    Samples at multiple points within the window to approximate peaks.
    Returns (max_price, min_price) or (None, None).
    """
    db = get_db()
    symbol = token.upper() + "USDT"

    # Sample at intervals within the window
    num_samples = min(24, max(4, window_ms // (3600 * 1000)))  # 1 sample per hour, 4-24
    step = window_ms // num_samples

    prices = []
    for i in range(num_samples + 1):
        target_ms = ts_ms + i * step
        # Try exchange_observations first
        doc = await db.exchange_observations.find_one(
            {"symbol": symbol, "timestamp": {"$gte": target_ms - 1800000, "$lte": target_ms + 1800000}},
            {"_id": 0, "market.price": 1},
        )
        if doc and doc.get("market", {}).get("price"):
            prices.append(float(doc["market"]["price"]))
            continue

        # Fallback: market_price_history
        doc = await db.market_price_history.find_one(
            {"symbol": symbol, "ts": {"$gte": target_ms - 7200000, "$lte": target_ms + 7200000}},
            {"_id": 0, "c": 1},
        )
        if doc and doc.get("c"):
            prices.append(float(doc["c"]))

    if not prices:
        return None, None

    return max(prices), min(prices)


def compute_label_v2(move_up_peak, move_down_peak, final_return, horizon="24H"):
    """
    5-label classification based on peak movements + final return gate.

    Labels: STRONG_GOOD, WEAK_GOOD, NEUTRAL, WEAK_BAD, STRONG_BAD

    Logic:
      1. Strong up: peak up >= strong AND final > -weak/2
      2. Weak up:   peak up >= weak AND final > -weak/2
      3. Strong down: peak down >= strong AND final < weak/2
      4. Weak down:   peak down >= weak AND final < weak/2
      5. Otherwise:   NEUTRAL

    Returns: (label, confidence_score)
    """
    th = LABEL_V2_THRESHOLDS.get(horizon, LABEL_V2_DEFAULT)
    weak = th["weak"]
    strong = th["strong"]

    # Normalize for confidence score
    max_move = max(abs(move_up_peak), abs(move_down_peak), 0.01)
    move_strength_norm = min(max_move / strong, 1.0)
    final_norm = min(abs(final_return) / strong, 1.0) if strong > 0 else 0
    confidence_score = round(0.5 * move_strength_norm + 0.5 * final_norm, 4)

    # STRONG_GOOD: big peak up + final not crashed
    if move_up_peak >= strong and final_return > -(weak / 2):
        return "STRONG_GOOD", confidence_score

    # WEAK_GOOD: moderate peak up + final not crashed
    if move_up_peak >= weak and final_return > -(weak / 2):
        return "WEAK_GOOD", confidence_score

    # STRONG_BAD: big peak down + final not recovered
    if move_down_peak >= strong and final_return < (weak / 2):
        return "STRONG_BAD", confidence_score

    # WEAK_BAD: moderate peak down + final not recovered
    if move_down_peak >= weak and final_return < (weak / 2):
        return "WEAK_BAD", confidence_score

    return "NEUTRAL", confidence_score


# ─── Evaluation Alignment V1: Dynamic Windows ───

# Event time profiles: expected market reaction latency
EVENT_TIME_PROFILE = {
    "listing":      {"min_hours": 24, "max_hours": 72},
    "funding":      {"min_hours": 24, "max_hours": 120},
    "unlock":       {"min_hours": 6,  "max_hours": 72},
    "whale_move":   {"min_hours": 1,  "max_hours": 24},
    "social_spike": {"min_hours": 6,  "max_hours": 48},
    "narrative":    {"min_hours": 48, "max_hours": 240},
    "unknown":      {"min_hours": 24, "max_hours": 72},
}

HORIZON_TO_HOURS = {"24H": 24, "7D": 168, "30D": 720}

# Map sentiment.intent / signal.type → event_type
INTENT_TO_EVENT_TYPE = {
    "BULLISH_SIGNAL": "social_spike",
    "BEARISH_SIGNAL": "social_spike",
    "HYPE":           "narrative",
    "WARNING":        "whale_move",
    "INFORMATIONAL":  "unknown",
    "NOISE":          "unknown",
}

# Text-based event type hints (lowercased substrings)
# Ordered: more specific patterns first, generic last
TEXT_EVENT_HINTS = [
    # Listings & exchange events
    (["listing", "listed", "list on", "binance list", "coinbase list", "new listing"], "listing"),
    # Funding & investment
    (["funding", "raised", "series a", "series b", "investment", "venture"], "funding"),
    # Unlocks & supply events
    (["unlock", "vesting", "cliff", "token release", "burn", "mint", "supply"], "unlock"),
    # Whale / large movements
    (["whale", "large transfer", "wallet moved", "transferred", "wallet"], "whale_move"),
    # Hacks & exploits → treated as whale_move (sudden large movement)
    (["hack", "exploit", "rug", "scam", "drain"], "whale_move"),
    # Volume / price breakout signals
    (["volume spike", "volume surge", "breakout", "breaking out", "pump",
     "range high", "pushing high", "all-time high", "ath"], "social_spike"),
    # Technical analysis patterns → social_spike
    (["chart", "textbook", "accumulation", "support", "resistance",
     "looking strong", "strong here", "target:"], "social_spike"),
    # Capital deployment / bullish conviction → social_spike
    (["deployed capital", "deployed some capital", "buying", "bullish on",
     "here's why", "here is why", "nfa", "top picks", "picks for"], "social_spike"),
    # Narrative / fundamental analysis
    (["partnership", "collab", "integrat", "launch", "airdrop", "reward",
     "incentive", "campaign"], "narrative"),
    (["thesis", "undervalued", "roadmap", "fundamentals", "team",
     "ecosystem", "developments", "narrative", "getting started"], "narrative"),
    # News & upcoming
    (["big news", "coming soon", "stay tuned", "announcement", "update",
     "interesting", "worth watching"], "narrative"),
    # Regulatory
    (["etf", "sec", "regulat", "ban", "legal"], "narrative"),
    # DeFi yield
    (["staking", "yield", "apr", "apy"], "narrative"),
]


def detect_event_type(sample):
    """
    Detect event type from sample fields.
    Priority: signal.type → sentiment.intent → text hints → intent flags → actor → default.

    Returns: (event_type: str, confidence: float)
      confidence in [0..1] — how sure we are about the classification.
    """
    # Path 1: signal.type (dataset_entries format)
    signal_type = ""
    sig = sample.get("signal", {})
    if isinstance(sig, dict):
        signal_type = sig.get("type", "") or ""
    mapped = INTENT_TO_EVENT_TYPE.get(signal_type)
    if mapped and mapped != "unknown":
        return mapped, 0.9

    # Path 2: sentiment.intent (raw sample format)
    intent = ""
    sent = sample.get("sentiment", {})
    if isinstance(sent, dict):
        intent = sent.get("intent", "") or ""
    mapped = INTENT_TO_EVENT_TYPE.get(intent)
    if mapped and mapped != "unknown":
        return mapped, 0.85

    # Path 3: Text-based heuristics (BEFORE intent flags — more specific)
    raw_text = ""
    text_field = sample.get("text")
    if isinstance(text_field, dict):
        raw_text = (text_field.get("raw", "") or "").lower()
    elif isinstance(text_field, str):
        raw_text = text_field.lower()
    # Also try sentiment.text if top-level text is missing
    if not raw_text and isinstance(sent, dict):
        st = sent.get("text", "")
        if isinstance(st, str):
            raw_text = st.lower()
        elif isinstance(st, dict):
            raw_text = (st.get("raw", "") or "").lower()
    if raw_text:
        for keywords, etype in TEXT_EVENT_HINTS:
            if any(kw in raw_text for kw in keywords):
                return etype, 0.7

    # Path 4: Intent probability flags (dataset_entries format)
    if isinstance(sent, dict):
        bullish = sent.get("intent_bullish", 0) or 0
        bearish = sent.get("intent_bearish", 0) or 0
        hype = sent.get("intent_hype", 0) or 0
        warning = sent.get("intent_warning", 0) or 0
        max_intent = max(bullish, bearish, hype, warning)
        if max_intent > 0:
            conf = round(min(max_intent, 1.0), 2)
            if bullish == max_intent or bearish == max_intent:
                return "social_spike", conf
            if hype == max_intent:
                return "narrative", conf
            if warning == max_intent:
                return "whale_move", conf

    # Path 5: Actor role hint
    actor = sample.get("actor", {})
    if isinstance(actor, dict):
        role = actor.get("role", "")
        score = actor.get("score", 0) or actor.get("actor_score", 0) or 0
        if role == "TRACKER" and score >= 0.5:
            return "social_spike", 0.5

    return "unknown", 0.0


def get_dynamic_window(event_type, horizon="24H"):
    """
    Compute dynamic evaluation window based on event type and horizon.
    Returns dict with window_hours, min_hours, max_hours.
    """
    profile = EVENT_TIME_PROFILE.get(event_type, EVENT_TIME_PROFILE["unknown"])
    horizon_hours = HORIZON_TO_HOURS.get(horizon, 24)

    # Window = max(event latency, half the horizon) but capped at horizon
    window_hours = max(profile["max_hours"], horizon_hours * 0.5)
    window_hours = min(window_hours, horizon_hours)

    return {
        "window_hours": window_hours,
        "min_hours": profile["min_hours"],
        "max_hours": profile["max_hours"],
        "event_type": event_type,
    }


async def _find_peak_prices_with_timing(token, ts_ms, window_ms):
    """
    Extended peak finder that also returns time-to-peak.
    Returns (max_price, min_price, time_to_max_hours, time_to_min_hours) or (None, None, None, None).
    """
    db = get_db()
    symbol = token.upper() + "USDT"

    num_samples = min(48, max(4, window_ms // (3600 * 1000)))
    step = window_ms // num_samples

    price_series = []  # [(ms_offset, price)]
    for i in range(num_samples + 1):
        target_ms = ts_ms + i * step
        offset_ms = i * step

        doc = await db.exchange_observations.find_one(
            {"symbol": symbol, "timestamp": {"$gte": target_ms - 1800000, "$lte": target_ms + 1800000}},
            {"_id": 0, "market.price": 1},
        )
        if doc and doc.get("market", {}).get("price"):
            price_series.append((offset_ms, float(doc["market"]["price"])))
            continue

        doc = await db.market_price_history.find_one(
            {"symbol": symbol, "ts": {"$gte": target_ms - 7200000, "$lte": target_ms + 7200000}},
            {"_id": 0, "c": 1},
        )
        if doc and doc.get("c"):
            price_series.append((offset_ms, float(doc["c"])))

    if not price_series:
        return None, None, None, None

    max_entry = max(price_series, key=lambda x: x[1])
    min_entry = min(price_series, key=lambda x: x[1])

    max_price = max_entry[1]
    min_price = min_entry[1]
    time_to_max_hours = round(max_entry[0] / (3600 * 1000), 2)
    time_to_min_hours = round(min_entry[0] / (3600 * 1000), 2)

    return max_price, min_price, time_to_max_hours, time_to_min_hours


# ─── Production Rollout Config ───
LABELS_V2_PRODUCTION = True       # V2 5-label system is now production
SAMPLING_ROLLOUT_PCT = 10         # Sampling filter rollout: 10% initially

# ─── Rollout Control ───
ROLLOUT_STEPS = [10, 30, 70, 100]

# Ready conditions for promotion
ROLLOUT_READY_CONDITIONS = {
    "high_min": 10, "high_max": 20,
    "medium_min": 55, "medium_max": 65,
    "low_min": 15, "low_max": 25,
    "include_rate_min": 35, "include_rate_max": 55,
}

# Rollback thresholds (breach = instant rollback)
ROLLOUT_ROLLBACK_THRESHOLDS = {
    "high_max": 25,
    "low_min": 10,
    "include_rate_max": 65,
}

# Stability: must pass N consecutive checks before READY
ROLLOUT_STABILITY_REQUIRED = 3
ROLLOUT_COOLDOWN_HOURS = 12

# Runtime state (in-memory, persisted to DB on change)
_rollout_state = {
    "consecutive_passes": 0,
    "last_rollout_at": None,       # ISO timestamp
    "last_check_at": None,
    "last_rollback_at": None,
    "status": "STABLE",            # STABLE | READY_FOR_N | COOLDOWN | ROLLBACK
}

# ─── Sampling Strategy V1: Event Scoring ───

import random as _random

# Event type weights
EVENT_TYPE_WEIGHT = {
    "listing": 1.0, "funding": 0.9, "unlock": 0.8,
    "whale_move": 0.7, "social_spike": 0.6, "narrative": 0.5,
    "unknown": 0.3,
}

# Position weights
POSITION_WEIGHT = {"EARLY": 1.0, "MID": 0.7, "LATE": 0.4}

# Sampling thresholds
SAMPLING_HIGH = 0.6     # Always include
SAMPLING_MID = 0.3      # Include 40%
SAMPLING_MID_PROB = 0.4
SAMPLING_LOW_PROB = 0.10
EXPLORATION_RATE = 0.10  # 10% exploration


def compute_event_score(sample):
    """
    Compute event_score in [0..1] for sampling priority.

    Components:
      - signal_strength: mentions, unique actors, cluster, coordination
      - entity_importance: actor score, hit_rate, role
      - sentiment_shift: confidence * intent weight
      - volatility_context: market volatility + momentum
      - position_bonus: EARLY > MID > LATE
      - event_type_weight: listing > social_spike > unknown

    Returns: (event_score, breakdown_dict)
    """
    signal = sample.get("signal", {})
    actor = sample.get("actor", {})
    sentiment = sample.get("sentiment", {})
    market = sample.get("market", {})

    # 1. Signal strength (0-1)
    mentions = min(signal.get("mentions_1h", 0) / 10.0, 1.0)
    unique_actors = min(signal.get("unique_actors_1h", 0) / 5.0, 1.0)
    cluster = min(signal.get("cluster_size_1h", 0) / 5.0, 1.0)
    coordination = signal.get("coordination", 0)
    signal_strength = (mentions * 0.3 + unique_actors * 0.3 + cluster * 0.2 + coordination * 0.2)

    # 2. Entity importance (0-1)
    actor_score = min(actor.get("score", 0), 1.0)
    hit_rate = min(actor.get("hit_rate", 0), 1.0)
    role_bonus = 0.3 if actor.get("role") == "TRACKER" else 0.0
    entity_importance = min(actor_score * 0.4 + hit_rate * 0.4 + role_bonus, 1.0)

    # 3. Sentiment shift (0-1)
    confidence = sentiment.get("confidence", 0.5)
    intent = sentiment.get("intent", "NOISE")
    intent_weight = {"BULLISH_SIGNAL": 1.0, "BEARISH_SIGNAL": 1.0, "HYPE": 0.7,
                     "WARNING": 0.8, "INFORMATIONAL": 0.3, "NOISE": 0.1}.get(intent, 0.2)
    sentiment_shift = confidence * intent_weight

    # 4. Volatility context (0-1)
    vol = min(abs(market.get("volatility", 0)) / 5.0, 1.0)
    mom = min(abs(market.get("momentum", 0)) / 3.0, 1.0)
    volatility_context = vol * 0.6 + mom * 0.4

    # 5. Position bonus
    position = signal.get("position", "MID")
    position_bonus = POSITION_WEIGHT.get(position, 0.5)

    # 6. Event type weight
    event_type, event_type_conf = detect_event_type(sample)
    type_weight = EVENT_TYPE_WEIGHT.get(event_type, 0.3)

    # Weighted sum
    raw_score = (
        0.25 * signal_strength +
        0.20 * entity_importance +
        0.15 * sentiment_shift +
        0.15 * volatility_context +
        0.15 * position_bonus +
        0.10 * type_weight
    )

    # FIX 1: Normalize + stretch (score^0.82 — softened)
    raw_score = math.pow(max(raw_score, 0), 0.82)

    # FIX 4b: Soft floor suppression — restore Low bucket
    if raw_score < 0.33:
        raw_score *= 0.84

    # FIX 2: Boost top events (threshold 0.48, delta 0.07)
    if raw_score > 0.48:
        raw_score += 0.07

    # FIX 3: Type boost by event_type (reduced)
    type_boost = {
        "listing": 0.10, "funding": 0.08, "unlock": 0.06,
        "whale_move": 0.05, "social_spike": 0.03, "narrative": 0.03,
        "unknown": 0,
    }
    raw_score += type_boost.get(event_type, 0)

    # FIX 4: Clamp to [0, 1]
    event_score = round(min(raw_score, 1.0), 4)

    breakdown = {
        "signal_strength": round(signal_strength, 4),
        "entity_importance": round(entity_importance, 4),
        "sentiment_shift": round(sentiment_shift, 4),
        "volatility_context": round(volatility_context, 4),
        "position_bonus": round(position_bonus, 4),
        "event_type_weight": round(type_weight, 4),
        "event_type": event_type,
    }

    return event_score, breakdown


def sampling_decision(event_score, exploration=True):
    """
    Decide whether to include an event in the training dataset.
    Returns (include: bool, reason: str).
    """
    # High signal: always include
    if event_score >= SAMPLING_HIGH:
        return True, "high_signal"

    # Exploration: random 10% override
    if exploration and _random.random() < EXPLORATION_RATE:
        return True, "exploration"

    # Medium signal: include 40%
    if event_score >= SAMPLING_MID:
        if _random.random() < SAMPLING_MID_PROB:
            return True, "medium_signal"
        return False, "medium_rejected"

    # Low signal: include 10%
    if _random.random() < SAMPLING_LOW_PROB:
        return True, "low_signal"

    return False, "low_rejected"



def _iso_to_ms(iso_str):
    """Convert ISO timestamp string to milliseconds epoch."""
    try:
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except (ValueError, TypeError):
        return None


async def resolve_single(db, sample):
    """
    Resolve a single dataset v3 sample.
    Returns dict of updates or None if cannot resolve yet.
    """
    created_at = sample.get("meta", {}).get("created_at", "")
    token = sample.get("market", {}).get("token", "")
    price_at_signal = sample.get("market", {}).get("price_at_signal", 0)

    if not created_at or not token or not price_at_signal:
        return None

    ts_ms = _iso_to_ms(created_at)
    if not ts_ms:
        return None

    now = datetime.now(timezone.utc)
    try:
        signal_time = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None

    age_sec = (now - signal_time).total_seconds()

    # Not old enough for even 1h resolution
    if age_sec < MIN_AGE_1H:
        return None

    # Fetch actual returns at each window
    pnl_1h = None
    pnl_4h = None
    pnl_24h = None
    btc_rel_24h = 0

    # 1h return
    if age_sec >= MIN_AGE_1H:
        pnl_1h = await _compute_return(None, token, ts_ms, 60 * 60 * 1000, price_at_signal)

    # 4h return
    if age_sec >= MIN_AGE_4H:
        pnl_4h = await _compute_return(None, token, ts_ms, 4 * 60 * 60 * 1000, price_at_signal)

    # 24h return (required for full resolution)
    if age_sec >= MIN_AGE_24H:
        pnl_24h = await _compute_return(None, token, ts_ms, 24 * 60 * 60 * 1000, price_at_signal)

        # BTC-relative 24h return
        if token.upper() != "BTC":
            btc_at = await _find_nearest_price(None, "BTC", ts_ms)
            if btc_at and btc_at > 0:
                btc_ret_24h = await _compute_return(None, "BTC", ts_ms, 24 * 60 * 60 * 1000, btc_at)
                if btc_ret_24h is not None:
                    btc_rel_24h = (pnl_24h or 0) - btc_ret_24h

    # Determine resolution state
    updates = {}

    # Partial update: fill 1h/4h as they become available
    if pnl_1h is not None:
        updates["outcome.pnl_1h"] = round(pnl_1h, 4)
    if pnl_4h is not None:
        updates["outcome.pnl_4h"] = round(pnl_4h, 4)
    if pnl_24h is not None:
        updates["outcome.pnl_24h"] = round(pnl_24h, 4)

    # Full resolution only when 24h is available
    if pnl_24h is not None:
        rel_return = btc_rel_24h if token.upper() != "BTC" else pnl_24h

        # V1 label (kept for reference)
        if rel_return > GOOD_THRESHOLD:
            v1_tradeable = True
            v1_label = "GOOD"
        elif rel_return < BAD_THRESHOLD:
            v1_tradeable = False
            v1_label = "BAD"
        else:
            v1_tradeable = False
            v1_label = "NEUTRAL"

        updates["outcome.label_v1"] = v1_label
        updates["outcome.resolved"] = True
        updates["outcome.resolved_at"] = datetime.now(timezone.utc).isoformat()
        updates["outcome.btc_rel_24h"] = round(btc_rel_24h, 4)

        # ─── V2 Labels (peak-aware, dynamic window, 5-label) ───
        v2_label = None
        v2_confidence = None
        event_type = "unknown"
        try:
            horizon = "24H"
            event_type, event_type_conf = detect_event_type(sample)
            dw = get_dynamic_window(event_type, horizon)
            window_hours = dw["window_hours"]
            window_ms = int(window_hours * 3600 * 1000)

            max_price, min_price, time_to_max_h, time_to_min_h = \
                await _find_peak_prices_with_timing(token, ts_ms, window_ms)

            if max_price is not None and min_price is not None and price_at_signal > 0:
                move_up_peak = ((max_price - price_at_signal) / price_at_signal) * 100
                move_down_peak = ((price_at_signal - min_price) / price_at_signal) * 100
                final_return_pct = rel_return  # already in %

                # Early exit: strong signal within first 24h
                th = LABEL_V2_THRESHOLDS.get(horizon, LABEL_V2_DEFAULT)
                early_exit = False
                if move_up_peak >= th["strong"] and (time_to_max_h or 999) <= 24:
                    early_exit = True
                elif move_down_peak >= th["strong"] and (time_to_min_h or 999) <= 24:
                    early_exit = True

                v2_label, v2_confidence = compute_label_v2(
                    move_up_peak, move_down_peak, final_return_pct, horizon
                )

                # Peak vs final divergence
                peak_vs_final = abs(move_up_peak - final_return_pct) if move_up_peak > move_down_peak \
                    else abs(move_down_peak + final_return_pct)

                updates["audit.labels_v2"] = {
                    "old": v1_label,
                    "new": v2_label,
                    "confidence_score": v2_confidence,
                    "changed": v1_label != v2_label,
                }
                updates["audit.label_inputs"] = {
                    "move_up_peak": round(move_up_peak, 4),
                    "move_down_peak": round(move_down_peak, 4),
                    "final_return": round(final_return_pct, 4),
                    "horizon": horizon,
                    "thresholds": LABEL_V2_THRESHOLDS.get(horizon, LABEL_V2_DEFAULT),
                    "max_price": round(max_price, 6),
                    "min_price": round(min_price, 6),
                    "entry_price": round(price_at_signal, 6),
                }
                updates["audit.evaluation"] = {
                    "event_type": event_type,
                    "window_used_hours": window_hours,
                    "time_to_peak_up_hours": time_to_max_h,
                    "time_to_peak_down_hours": time_to_min_h,
                    "early_exit": early_exit,
                    "peak_vs_final_gap": round(peak_vs_final, 4),
                    "dynamic_window": dw,
                }

                # ─── Sampling (event scoring) ───
                event_score, score_breakdown = compute_event_score(sample)
                include_new, include_reason = sampling_decision(event_score)

                # Sampling rollout: apply filter based on rollout %
                use_sampling = _random.random() * 100 < SAMPLING_ROLLOUT_PCT
                if use_sampling:
                    sampling_active = True
                    final_included = include_new
                else:
                    sampling_active = False
                    final_included = True  # old behavior: include everything

                updates["audit.sampling"] = {
                    "event_score": event_score,
                    "included_old": True,
                    "included_new": include_new,
                    "include_reason": include_reason,
                    "event_type": event_type,
                    "breakdown": score_breakdown,
                    "sampling_active": sampling_active,
                    "final_included": final_included,
                }
        except Exception:
            pass  # never break production on V2/V3 errors

        # ─── Production label assignment ───
        if LABELS_V2_PRODUCTION and v2_label:
            updates["outcome.label"] = v2_label
            updates["outcome.label_version"] = "v2"
            # Tradeable: any non-NEUTRAL label
            updates["outcome.tradeable"] = v2_label != "NEUTRAL"
        else:
            updates["outcome.label"] = v1_label
            updates["outcome.tradeable"] = v1_tradeable
            updates["outcome.label_version"] = "v1"

    return updates if updates else None


async def run_outcome_resolution(limit=200):
    """
    Scan unresolved samples and resolve outcomes.
    Safe for repeated calls — idempotent.
    """
    db = get_db()
    col = db[COLLECTION]

    # Find unresolved samples, oldest first
    # Include all fields needed by detect_event_type (text, signal, sentiment, actor)
    cursor = col.find(
        {"outcome.resolved": False},
    ).sort("meta.created_at", 1).limit(limit)

    samples = await cursor.to_list(limit)

    resolved_count = 0
    partial_count = 0
    skipped = 0
    errors = 0

    for sample in samples:
        try:
            updates = await resolve_single(db, sample)
            if updates is None:
                skipped += 1
                continue

            await col.update_one(
                {"_id": sample["_id"]},
                {"$set": updates}
            )

            if updates.get("outcome.resolved"):
                resolved_count += 1
            else:
                partial_count += 1

        except Exception:
            errors += 1

    return {
        "ok": True,
        "resolved": resolved_count,
        "partial_updates": partial_count,
        "skipped": skipped,
        "errors": errors,
        "total_checked": len(samples),
    }


async def get_outcome_stats():
    """Get outcome resolution statistics."""
    db = get_db()
    col = db[COLLECTION]

    total = await col.count_documents({})
    resolved = await col.count_documents({"outcome.resolved": True})
    unresolved = await col.count_documents({"outcome.resolved": False})
    good = await col.count_documents({"outcome.label": "GOOD"})
    bad = await col.count_documents({"outcome.label": "BAD"})
    neutral = await col.count_documents({"outcome.label": "NEUTRAL"})
    tradeable = await col.count_documents({"outcome.tradeable": True})

    # Age of oldest unresolved
    oldest = await col.find_one(
        {"outcome.resolved": False},
        {"_id": 0, "meta.created_at": 1},
        sort=[("meta.created_at", 1)]
    )
    oldest_age_hours = None
    if oldest:
        try:
            ts = datetime.fromisoformat(str(oldest["meta"]["created_at"]).replace("Z", "+00:00"))
            oldest_age_hours = round((datetime.now(timezone.utc) - ts).total_seconds() / 3600, 1)
        except (ValueError, TypeError):
            pass

    return {
        "ok": True,
        "total": total,
        "resolved": resolved,
        "unresolved": unresolved,
        "labels": {
            "GOOD": good,
            "BAD": bad,
            "NEUTRAL": neutral,
        },
        "tradeable": tradeable,
        "tradeable_pct": round(tradeable / total * 100, 1) if total > 0 else 0,
        "resolution_pct": round(resolved / total * 100, 1) if total > 0 else 0,
        "oldest_unresolved_hours": oldest_age_hours,
    }



# ─── Signal Log Outcome Resolution ───

async def resolve_signal_log_outcomes(limit=200):
    """
    Resolve outcomes for signal_log entries (graph-originated signals).
    Uses the same logic: check price after 1h/4h/24h, label GOOD/BAD/NEUTRAL.
    """
    db = get_db()

    # Find signal_log entries without resolved outcome, oldest first
    cursor = db.signal_log.find(
        {"$or": [
            {"outcome.resolved": {"$exists": False}},
            {"outcome.resolved": False}
        ]},
        {"_id": 1, "entity": 1, "timestamp": 1, "strength": 1}
    ).sort("timestamp", 1).limit(limit)

    signals = await cursor.to_list(limit)

    resolved = 0
    skipped = 0
    errors = 0

    for sig in signals:
        try:
            ts_str = sig.get("timestamp", "")
            entity = sig.get("entity", "")
            token = entity.replace("token:", "").replace("project:", "").upper()

            if not ts_str or not token:
                skipped += 1
                continue

            ts_ms = _iso_to_ms(ts_str)
            if not ts_ms:
                skipped += 1
                continue

            try:
                signal_time = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                skipped += 1
                continue

            age_sec = (datetime.now(timezone.utc) - signal_time).total_seconds()

            # Need at least 25h for full resolution
            if age_sec < MIN_AGE_24H:
                skipped += 1
                continue

            # Get price at signal time
            price_at_signal = await _find_nearest_price(None, token, ts_ms)
            if not price_at_signal or price_at_signal <= 0:
                skipped += 1
                continue

            # Compute returns
            pnl_1h = await _compute_return(None, token, ts_ms, 60 * 60 * 1000, price_at_signal)
            pnl_4h = await _compute_return(None, token, ts_ms, 4 * 60 * 60 * 1000, price_at_signal)
            pnl_24h = await _compute_return(None, token, ts_ms, 24 * 60 * 60 * 1000, price_at_signal)

            if pnl_24h is None:
                skipped += 1
                continue

            # BTC-relative
            btc_rel = pnl_24h
            if token != "BTC":
                btc_at = await _find_nearest_price(None, "BTC", ts_ms)
                if btc_at and btc_at > 0:
                    btc_ret = await _compute_return(None, "BTC", ts_ms, 24 * 60 * 60 * 1000, btc_at)
                    if btc_ret is not None:
                        btc_rel = pnl_24h - btc_ret

            # Label (V1 — production)
            if btc_rel > GOOD_THRESHOLD:
                label = "GOOD"
                tradeable = True
            elif btc_rel < BAD_THRESHOLD:
                label = "BAD"
                tradeable = False
            else:
                label = "NEUTRAL"
                tradeable = False

            outcome = {
                "resolved": True,
                "resolved_at": datetime.now(timezone.utc).isoformat(),
                "tradeable": tradeable,
                "label": label,
                "pnl_1h": round(pnl_1h or 0, 4),
                "pnl_4h": round(pnl_4h or 0, 4),
                "pnl_24h": round(pnl_24h or 0, 4),
                "btc_rel_24h": round(btc_rel, 4),
            }

            # V2 shadow labels for signal_log
            try:
                max_price, min_price = await _find_peak_prices(token, ts_ms, 24 * 3600 * 1000)
                if max_price is not None and min_price is not None and price_at_signal > 0:
                    move_up = ((max_price - price_at_signal) / price_at_signal) * 100
                    move_down = ((price_at_signal - min_price) / price_at_signal) * 100
                    v2_label, v2_conf = compute_label_v2(move_up, move_down, btc_rel, "24H")
                    outcome["labels_v2"] = {
                        "old": label, "new": v2_label,
                        "confidence_score": v2_conf, "changed": label != v2_label,
                    }
                    outcome["label_inputs"] = {
                        "move_up_peak": round(move_up, 4),
                        "move_down_peak": round(move_down, 4),
                        "final_return": round(btc_rel, 4),
                    }
            except Exception:
                pass

            await db.signal_log.update_one(
                {"_id": sig["_id"]},
                {"$set": {"outcome": outcome}}
            )
            resolved += 1

        except Exception:
            errors += 1

    return {
        "ok": True,
        "resolved": resolved,
        "skipped": skipped,
        "errors": errors,
        "total_checked": len(signals),
    }



# ─── Rollout Health Check & Auto-Rollback ───

def check_rollout_health(distribution):
    """
    Check if current score distribution meets rollout conditions.
    Returns (healthy: bool, details: dict).
    """
    high_pct = distribution.get("high_pct", 0)
    medium_pct = distribution.get("medium_pct", 0)
    low_pct = distribution.get("low_pct", 0)
    include_rate = distribution.get("include_rate", 0)

    rc = ROLLOUT_READY_CONDITIONS
    rb = ROLLOUT_ROLLBACK_THRESHOLDS

    # Check rollback conditions first (critical)
    needs_rollback = False
    rollback_reasons = []
    if high_pct > rb["high_max"]:
        needs_rollback = True
        rollback_reasons.append(f"High {high_pct}% > {rb['high_max']}%")
    if low_pct < rb["low_min"]:
        needs_rollback = True
        rollback_reasons.append(f"Low {low_pct}% < {rb['low_min']}%")
    if include_rate > rb["include_rate_max"]:
        needs_rollback = True
        rollback_reasons.append(f"Include rate {include_rate}% > {rb['include_rate_max']}%")

    # Check ready conditions
    ready = (
        rc["high_min"] <= high_pct <= rc["high_max"] and
        rc["medium_min"] <= medium_pct <= rc["medium_max"] and
        rc["low_min"] <= low_pct <= rc["low_max"] and
        rc["include_rate_min"] <= include_rate <= rc["include_rate_max"]
    )

    return {
        "healthy": not needs_rollback,
        "ready_for_promotion": ready,
        "needs_rollback": needs_rollback,
        "rollback_reasons": rollback_reasons,
        "checks": {
            "high": {"value": high_pct, "range": [rc["high_min"], rc["high_max"]], "pass": rc["high_min"] <= high_pct <= rc["high_max"]},
            "medium": {"value": medium_pct, "range": [rc["medium_min"], rc["medium_max"]], "pass": rc["medium_min"] <= medium_pct <= rc["medium_max"]},
            "low": {"value": low_pct, "range": [rc["low_min"], rc["low_max"]], "pass": rc["low_min"] <= low_pct <= rc["low_max"]},
            "include_rate": {"value": include_rate, "range": [rc["include_rate_min"], rc["include_rate_max"]], "pass": rc["include_rate_min"] <= include_rate <= rc["include_rate_max"]},
        },
    }


def get_next_rollout_step():
    """Get the next rollout percentage step."""
    global SAMPLING_ROLLOUT_PCT
    current = SAMPLING_ROLLOUT_PCT
    for step in ROLLOUT_STEPS:
        if step > current:
            return step
    return current  # Already at max


def execute_rollback():
    """Roll back to previous sampling percentage."""
    global SAMPLING_ROLLOUT_PCT, _rollout_state
    current = SAMPLING_ROLLOUT_PCT
    prev = 10  # default fallback
    for step in ROLLOUT_STEPS:
        if step < current:
            prev = step
    SAMPLING_ROLLOUT_PCT = prev
    _rollout_state["status"] = "ROLLBACK"
    _rollout_state["last_rollback_at"] = datetime.now(timezone.utc).isoformat()
    _rollout_state["consecutive_passes"] = 0
    return {"old_pct": current, "new_pct": prev}


def execute_promotion():
    """Promote to next rollout step."""
    global SAMPLING_ROLLOUT_PCT, _rollout_state
    old = SAMPLING_ROLLOUT_PCT
    new = get_next_rollout_step()
    SAMPLING_ROLLOUT_PCT = new
    _rollout_state["status"] = "COOLDOWN"
    _rollout_state["last_rollout_at"] = datetime.now(timezone.utc).isoformat()
    _rollout_state["consecutive_passes"] = 0
    return {"old_pct": old, "new_pct": new}


def update_rollout_state(health_result):
    """Update rollout state based on health check."""
    global _rollout_state

    now = datetime.now(timezone.utc)
    _rollout_state["last_check_at"] = now.isoformat()

    # Check cooldown
    if _rollout_state.get("last_rollout_at"):
        try:
            last = datetime.fromisoformat(_rollout_state["last_rollout_at"])
            hours_since = (now - last).total_seconds() / 3600
            if hours_since < ROLLOUT_COOLDOWN_HOURS:
                _rollout_state["status"] = "COOLDOWN"
                return {
                    "status": "COOLDOWN",
                    "hours_remaining": round(ROLLOUT_COOLDOWN_HOURS - hours_since, 1),
                }
        except (ValueError, TypeError):
            pass

    # Auto-rollback
    if health_result["needs_rollback"]:
        rb = execute_rollback()
        return {"status": "ROLLBACK", **rb, "reasons": health_result["rollback_reasons"]}

    # Stability tracking
    if health_result["ready_for_promotion"]:
        _rollout_state["consecutive_passes"] += 1
        if _rollout_state["consecutive_passes"] >= ROLLOUT_STABILITY_REQUIRED:
            next_step = get_next_rollout_step()
            if next_step > SAMPLING_ROLLOUT_PCT:
                _rollout_state["status"] = f"READY_FOR_{next_step}%"
            else:
                _rollout_state["status"] = "FULLY_ROLLED_OUT"
        else:
            passes = _rollout_state['consecutive_passes']
            _rollout_state["status"] = f"STABILIZING ({passes}/{ROLLOUT_STABILITY_REQUIRED})"
    else:
        _rollout_state["consecutive_passes"] = 0
        _rollout_state["status"] = "NOT_READY"

    return {
        "status": _rollout_state["status"],
        "consecutive_passes": _rollout_state["consecutive_passes"],
        "stability_required": ROLLOUT_STABILITY_REQUIRED,
        "current_pct": SAMPLING_ROLLOUT_PCT,
        "next_step": get_next_rollout_step(),
    }
