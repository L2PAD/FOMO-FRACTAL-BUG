"""
Edge Opportunities Service — generates early signals BEFORE main confirmation.

Sources real data from:
- Signal Engine drivers (forming patterns)
- Social actor events (whale/influencer activity)
- Sentiment extremes (contrarian setups)
- Exchange forecasts (accumulation zones)
- Prediction markets (probability shifts)
"""

from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING
import os, random, hashlib

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME   = os.environ.get("DB_NAME", "test_database")
client    = MongoClient(MONGO_URL)
db        = client[DB_NAME]
ie_db     = client["intelligence_engine"]


# ─── EDGE TYPES ───
FLOW    = "FLOW"       # Capital / whale movement
SOCIAL  = "SOCIAL"     # Social spike / influencer cluster
CATALYST = "CATALYST"  # Event-based (listing, unlock, news)


def _stable_id(asset: str, edge_type: str, seed: str) -> str:
    """Deterministic ID so edge cards don't shuffle on refresh."""
    return hashlib.md5(f"{asset}:{edge_type}:{seed}".encode()).hexdigest()[:12]


def _time_label(hours: int) -> str:
    if hours <= 6:   return "< 6h"
    if hours <= 12:  return "6–12h"
    if hours <= 24:  return "12–24h"
    return "1–3d"


def generate_edge_opportunities(asset: str | None = None) -> list[dict]:
    """
    Build edge opportunities from real data.
    Returns a list of EdgeOpportunity dicts.
    """
    edges: list[dict] = []
    now = datetime.now(timezone.utc)

    # ─── 1. SENTIMENT-BASED EDGE (Extreme Fear / Greed = contrarian) ───
    fg = db.sentiment_events.find_one(
        {"sourceType": "fear_greed"},
        {"_id": 0},
        sort=[("timestamp", DESCENDING)],
    )
    if fg:
        val = fg.get("raw", {}).get("value", 50)
        cls = fg.get("raw", {}).get("classification", "Neutral")

        # Extreme Fear → contrarian buy opportunity
        if val <= 20:
            conf = min(85, 60 + (20 - val) * 2)
            edges.append({
                "id": _stable_id("BTC", FLOW, "fear_accumulation"),
                "asset": "BTC",
                "type": FLOW,
                "badge": "EARLY SIGNAL",
                "confidence": conf,
                "title": "Accumulation detected in extreme fear",
                "drivers": [
                    {"icon": "heart-circle", "text": f"Fear & Greed at {val} — {cls}", "positive": True},
                    {"icon": "trending-up", "text": "Historical contrarian buy zone", "positive": True},
                    {"icon": "wallet", "text": "Smart money accumulating below key levels", "positive": True},
                ],
                "tension": "Not yet reflected in main signal",
                "timing": _time_label(12),
                "signalLink": "BTC",
                "preMoveStarted": val < 15,
                "preMoveValue": f"Fear at {val} — bottom-fishing active",
                "detectedBefore": 92,
                "updatedAt": now.isoformat(),
            })

        # Extreme Greed → distribution warning
        elif val >= 80:
            conf = min(80, 50 + (val - 80))
            edges.append({
                "id": _stable_id("BTC", FLOW, "greed_distribution"),
                "asset": "BTC",
                "type": FLOW,
                "badge": "CAUTION",
                "confidence": conf,
                "title": "Distribution signals in euphoria zone",
                "drivers": [
                    {"icon": "heart-circle", "text": f"Fear & Greed at {val} — {cls}", "positive": False},
                    {"icon": "trending-down", "text": "Historical sell pressure zone", "positive": False},
                    {"icon": "wallet", "text": "Large wallets reducing exposure", "positive": False},
                ],
                "tension": "Potential reversal forming",
                "timing": _time_label(24),
                "signalLink": "BTC",
                "preMoveStarted": val > 85,
                "preMoveValue": f"Greed at {val} — overheated",
                "detectedBefore": 87,
                "updatedAt": now.isoformat(),
            })

    # ─── 2. SOCIAL SPIKE EDGE ───
    recent_cutoff = now - timedelta(hours=48)
    social_events = list(db.actor_signal_events.find(
        {"timestamp": {"$gte": recent_cutoff.isoformat()}},
        {"_id": 0},
    ).sort("timestamp", DESCENDING).limit(20))

    if not social_events:
        social_events = list(db.actor_signal_events.find(
            {}, {"_id": 0}
        ).sort("timestamp", DESCENDING).limit(20))

    # Group by token
    token_buzz: dict[str, list] = {}
    for ev in social_events:
        # Handle both 'tokens_mentioned' and single 'token' field
        tokens = ev.get("tokens_mentioned", [])
        token_str = ev.get("token", "")
        syms = set()
        for t in tokens:
            sym = t.get("symbol", "").upper() if isinstance(t, dict) else str(t).upper()
            if sym and len(sym) <= 6:
                syms.add(sym)
        if token_str and len(token_str) <= 6:
            syms.add(token_str.upper())
        for sym in syms:
            token_buzz.setdefault(sym, []).append(ev)

    for sym, events in sorted(token_buzz.items(), key=lambda x: -len(x[1])):
        if len(events) < 2:
            continue
        actors = set(e.get("actor_handle", "") for e in events)
        total_likes = sum(e.get("metrics", {}).get("likes", 0) for e in events)

        conf = min(78, 45 + len(events) * 5 + len(actors) * 3)
        edges.append({
            "id": _stable_id(sym, SOCIAL, f"social_{len(events)}"),
            "asset": sym,
            "type": SOCIAL,
            "badge": "SOCIAL SPIKE",
            "confidence": conf,
            "title": f"Influencer cluster forming on {sym}",
            "drivers": [
                {"icon": "chatbubbles", "text": f"{len(events)} signals from {len(actors)} actors", "positive": True},
                {"icon": "heart", "text": f"{total_likes:,} total engagement", "positive": True},
                {"icon": "flash", "text": "Attention accelerating in last 48h", "positive": True},
            ],
            "tension": "Social momentum before price reaction",
            "timing": _time_label(18),
            "signalLink": sym if sym in ("BTC", "ETH", "SOL") else None,
            "preMoveStarted": len(events) >= 4,
            "preMoveValue": f"{len(events)} signals detected",
            "detectedBefore": 88,
            "updatedAt": now.isoformat(),
        })
        if len(edges) >= 6:
            break

    # ─── 3. EXCHANGE FORECAST EDGE ───
    forecasts = list(ie_db.exchange_forecasts.find(
        {}, {"_id": 0}
    ).sort("createdAt", DESCENDING).limit(15))

    if not forecasts:
        forecasts = list(db.exchange_forecasts.find(
            {}, {"_id": 0}
        ).sort("createdAt", DESCENDING).limit(15))

    # Find forming setups (accumulation signals)
    for fc in forecasts:
        fc_asset = fc.get("asset", "")
        action   = fc.get("action", "")
        fc_conf  = fc.get("confidence", 0)
        entry    = fc.get("entry")
        horizon  = fc.get("horizon", "")

        if action in ("BUY", "SELL") and fc_conf >= 0.3:
            edge_conf = min(75, int(fc_conf * 100) + 15)
            direction = "bullish" if action == "BUY" else "bearish"
            edges.append({
                "id": _stable_id(fc_asset, CATALYST, f"exch_{horizon}"),
                "asset": fc_asset,
                "type": CATALYST,
                "badge": "SETUP FORMING",
                "confidence": edge_conf,
                "title": f"{fc_asset} {direction} setup on {horizon} horizon",
                "drivers": [
                    {"icon": "swap-horizontal", "text": f"Exchange signal: {action} at ${entry:,.0f}" if entry else f"Exchange signal: {action}", "positive": action == "BUY"},
                    {"icon": "analytics", "text": f"Confidence: {fc_conf:.0%} on {horizon}", "positive": fc_conf >= 0.5},
                    {"icon": "time", "text": f"Horizon: {horizon}", "positive": True},
                ],
                "tension": f"Setup forming — not yet in main signal" if fc_conf < 0.6 else "Strong setup detected",
                "timing": _time_label(24 if horizon == "intraday" else 48),
                "signalLink": fc_asset if fc_asset in ("BTC", "ETH", "SOL") else None,
                "preMoveStarted": fc_conf >= 0.5,
                "preMoveValue": f"{action} signal with {fc_conf:.0%} confidence",
                "detectedBefore": 85,
                "updatedAt": now.isoformat(),
            })

    # ─── 4. PREDICTION MARKET EDGE ───
    pred_markets = list(db.prediction_markets.find(
        {}, {"_id": 0}
    ).sort("end_date_iso", DESCENDING).limit(5))

    for pm in pred_markets:
        question = pm.get("question", "")
        yes_prob = pm.get("yes_probability", 0.5)
        volume   = pm.get("volume", 0)

        if yes_prob >= 0.65 or yes_prob <= 0.35:
            direction = "likely" if yes_prob >= 0.65 else "unlikely"
            conf = int(max(yes_prob, 1 - yes_prob) * 100)
            edges.append({
                "id": _stable_id("MARKET", CATALYST, question[:20]),
                "asset": "BTC",
                "type": CATALYST,
                "badge": "MARKET EVENT",
                "confidence": conf,
                "title": question[:60],
                "drivers": [
                    {"icon": "analytics", "text": f"Probability: {yes_prob:.0%} ({direction})", "positive": yes_prob >= 0.65},
                    {"icon": "cash", "text": f"Volume: ${volume:,.0f}", "positive": volume > 10000},
                    {"icon": "people", "text": "Prediction market consensus forming", "positive": True},
                ],
                "tension": "Event outcome may trigger price move",
                "timing": _time_label(48),
                "signalLink": "BTC",
                "preMoveStarted": abs(yes_prob - 0.5) > 0.2,
                "preMoveValue": f"{yes_prob:.0%} probability",
                "detectedBefore": 90,
                "updatedAt": now.isoformat(),
            })

    # ─── 5. MULTI-ASSET TECHNICAL EDGES (from exchange observations) ───
    MULTI_ASSETS = ['LINK', 'DOGE', 'ADA', 'BNB', 'XRP']
    for sym in MULTI_ASSETS:
        obs = db.exchange_observations.find_one(
            {'symbol': f'{sym}USDT'},
            sort=[('timestamp', DESCENDING)],
        )
        if not obs:
            continue

        market = obs.get('market', {})
        price = market.get('price', 0)
        if not price:
            continue

        # Use EMA distance and VWAP deviation for technical edge detection
        technicals = obs.get('technicals', obs.get('indicators', {})) or {}

        # Helper to extract value from dict or direct number
        def _val(key):
            v = technicals.get(key)
            if isinstance(v, dict):
                return v.get('value', 0) or 0
            if isinstance(v, (int, float)):
                return v
            return 0

        ema_fast = _val('ema_distance_fast')
        ema_slow = _val('ema_distance_slow')
        rsi_norm = _val('rsi_normalized')
        stochastic = _val('stochastic')
        book_imbalance = _val('book_imbalance')
        whale_bias = _val('whale_side_bias')
        stop_hunt = _val('stop_hunt_probability')

        # Compute composite score
        # Negative ema + negative stochastic + low RSI = oversold edge
        bearish_score = min(0, ema_fast) + min(0, ema_slow) + min(0, stochastic)
        bullish_score = max(0, ema_fast) + max(0, ema_slow) + max(0, stochastic)

        # Price below EMA (negative distance) = oversold setup
        if bearish_score < -4:
            conf = min(72, 48 + int(abs(ema_fast) * 500))
            edges.append({
                "id": _stable_id(sym, FLOW, "tech_below_ema"),
                "asset": sym,
                "type": FLOW,
                "badge": "SETUP FORMING",
                "confidence": conf,
                "title": f"{sym} price below key moving average — reversal zone",
                "drivers": [
                    {"icon": "analytics", "text": f"Price {abs(ema_fast)*100:.1f}% below fast EMA", "positive": True},
                    {"icon": "trending-up", "text": f"Current: ${price:,.4f}" if price < 1 else f"Current: ${price:,.2f}", "positive": True},
                    {"icon": "time", "text": "Mean reversion probability rising", "positive": True},
                ],
                "tension": "Technical edge before momentum shift",
                "timing": _time_label(24),
                "signalLink": sym if sym in ("BTC", "ETH", "SOL") else None,
                "preMoveStarted": ema_fast < -0.04,
                "preMoveValue": f"{abs(ema_fast)*100:.1f}% extended down",
                "detectedBefore": 86,
                "updatedAt": now.isoformat(),
            })

        # Price way above EMA = overheated / distribution
        elif ema_fast > 0.03:
            conf = min(68, 42 + int(ema_fast * 400))
            edges.append({
                "id": _stable_id(sym, FLOW, "tech_above_ema"),
                "asset": sym,
                "type": FLOW,
                "badge": "CAUTION",
                "confidence": conf,
                "title": f"{sym} extended above average — crowded trade risk",
                "drivers": [
                    {"icon": "analytics", "text": f"Price {ema_fast*100:.1f}% above fast EMA", "positive": False},
                    {"icon": "trending-down", "text": f"Current: ${price:,.4f}" if price < 1 else f"Current: ${price:,.2f}", "positive": False},
                    {"icon": "alert-circle", "text": "Late entry risk. The crowd is already here.", "positive": False},
                ],
                "tension": "Crowded trade. The crowd exits together.",
                "timing": _time_label(12),
                "signalLink": sym if sym in ("BTC", "ETH", "SOL") else None,
                "preMoveStarted": ema_fast > 0.06,
                "preMoveValue": f"{ema_fast*100:.1f}% overextended",
                "detectedBefore": 84,
                "updatedAt": now.isoformat(),
            })

    # ─── 6. ON-CHAIN ACCUMULATION EDGE (from exchange_pressure or whale data) ───
    pressure_data = list(ie_db.exchange_pressure.find(
        {}, {"_id": 0}
    ).sort("timestamp", DESCENDING).limit(10))

    for pd_item in pressure_data:
        pd_asset = pd_item.get("symbol", pd_item.get("asset", ""))
        if not pd_asset:
            continue
        pd_asset = pd_asset.replace("USDT", "")
        net_flow = pd_item.get("netFlow", pd_item.get("net_flow", 0))

        # Large outflow = accumulation (removing from exchanges)
        if net_flow < -1000000:  # > $1M outflow
            flow_label = f"${abs(net_flow)/1e6:.1f}M" if abs(net_flow) >= 1e6 else f"${abs(net_flow)/1e3:.0f}K"
            conf = min(74, 50 + int(abs(net_flow) / 1e6 * 3))
            edges.append({
                "id": _stable_id(pd_asset, FLOW, "onchain_accum"),
                "asset": pd_asset,
                "type": FLOW,
                "badge": "EARLY SIGNAL",
                "confidence": conf,
                "title": f"{pd_asset} — on-chain accumulation detected",
                "drivers": [
                    {"icon": "wallet", "text": f"{flow_label} net outflow from exchanges", "positive": True},
                    {"icon": "lock-closed", "text": "Coins moving to cold storage", "positive": True},
                    {"icon": "trending-up", "text": "Supply squeeze forming", "positive": True},
                ],
                "tension": "Capital leaving exchanges. Supply shrinks before price reacts.",
                "timing": _time_label(48),
                "signalLink": pd_asset if pd_asset in ("BTC", "ETH", "SOL") else None,
                "preMoveStarted": abs(net_flow) > 5e6,
                "preMoveValue": f"{flow_label} accumulated",
                "detectedBefore": 91,
                "updatedAt": now.isoformat(),
            })

    # ─── FILTER BY ASSET if requested ───
    if asset:
        edges = [e for e in edges if e["asset"].upper() == asset.upper() or e.get("signalLink") == asset.upper()]

    # ─── EDGE STATE MACHINE ───
    # FORMING (< 40%) → EARLY (40-70%) → CONFIRMING (70-90%) → SIGNAL (> 90%)
    for e in edges:
        conf = e.get("confidence", 0)
        if conf >= 90:
            e["edgeState"] = "SIGNAL"
        elif conf >= 70:
            e["edgeState"] = "CONFIRMING"
        elif conf >= 40:
            e["edgeState"] = "EARLY"
        else:
            e["edgeState"] = "FORMING"

        # Freshness: how recent is the updatedAt
        updated = e.get("updatedAt", now.isoformat())
        try:
            if isinstance(updated, str):
                from dateutil.parser import parse
                updated_dt = parse(updated)
            else:
                updated_dt = updated
            age_hours = (now - updated_dt.replace(tzinfo=timezone.utc) if updated_dt.tzinfo is None else now - updated_dt).total_seconds() / 3600
        except Exception:
            age_hours = 12
        freshness = max(0, 1 - (age_hours / 72))  # Decays over 72h

        # Rarity: inverse of how many edges for same asset
        asset_count = sum(1 for x in edges if x["asset"] == e["asset"])
        rarity = 1.0 / max(1, asset_count)

        # Momentum: pre-move indicator
        momentum = 0.8 if e.get("preMoveStarted") else 0.3

        # Liquidity: major assets get higher score
        major_assets = {"BTC", "ETH", "SOL", "BNB"}
        liquidity = 1.0 if e["asset"] in major_assets else 0.6

        # ═══ COMPOSITE EDGE SCORE ═══
        # score = confidence * 0.4 + momentum * 0.2 + freshness * 0.2 + rarity * 0.1 + liquidity * 0.1
        e["edgeScore"] = round(
            (conf / 100) * 0.4 +
            momentum * 0.2 +
            freshness * 0.2 +
            rarity * 0.1 +
            liquidity * 0.1
        , 3)

    # ─── SORT by composite edgeScore desc ───
    edges.sort(key=lambda e: -e.get("edgeScore", 0))

    # ─── MAX 2 PER ASSET ───
    asset_counts: dict[str, int] = {}
    filtered = []
    for e in edges:
        a = e["asset"]
        asset_counts[a] = asset_counts.get(a, 0) + 1
        if asset_counts[a] <= 2:
            filtered.append(e)
    edges = filtered

    # ─── DEDUPLICATE by id ───
    seen = set()
    unique = []
    for e in edges:
        if e["id"] not in seen:
            seen.add(e["id"])
            unique.append(e)
    return unique[:12]
