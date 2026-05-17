"""
OnChain Adapter — REAL data from multiple onchain collections.

Sources:
  - onchain_v2_snapshots: exchange inflow/outflow, net flows (BTC/ETH)
  - onchain_v2_altflow_points: DEX/CEX flow scores (WBTC/WETH mapped)
  - exchange_whale_events: whale positions & movements

Returns unified signal format: {bias, strength, confidence, flow, signals}

Directional logic:
  - outflow from exchanges → bullish (accumulation)
  - inflow to exchanges → bearish (distribution)
  - whale accumulation → bullish
  - whale distribution → bearish
"""
import os
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING


def _get_db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "intelligence_engine")]


# Map prediction assets to onchain symbols
ASSET_TO_SNAPSHOT_SYMBOL = {"BTC": "BTCUSDT", "ETH": "ETHUSDT"}
ASSET_TO_ALTFLOW_SYMBOL = {"BTC": "WBTC", "ETH": "WETH"}


def get_flow_signal(asset: str = "BTC") -> dict | None:
    """
    Get real on-chain flow signal for an asset.

    Returns unified format:
        {
            bias: "bullish"|"bearish"|"neutral",
            strength: 0.0-1.0,
            confidence: 0.0-1.0,
            flow: "bullish"|"bearish"|"neutral",
            net_flow_usd: float,
            signals: [str],
            event_count: int,
            whale_bias: "bullish"|"bearish"|"neutral",
            exchange_flow_bias: "bullish"|"bearish"|"neutral",
            dex_flow_bias: "bullish"|"bearish"|"neutral"
        }
    or None if unavailable.
    """
    try:
        db = _get_db()

        exchange_signal = _get_exchange_flow(db, asset)
        altflow_signal = _get_altflow(db, asset)
        whale_signal = _get_whale_signal(db, asset)

        # If nothing at all, return None
        if not exchange_signal and not altflow_signal and not whale_signal:
            return None

        # Combine signals
        biases = []
        strengths = []
        confidences = []
        signals = []
        net_flow_usd = 0

        if exchange_signal:
            biases.append(exchange_signal["bias"])
            strengths.append(exchange_signal["strength"])
            confidences.append(exchange_signal["confidence"])
            signals.extend(exchange_signal["signals"])
            net_flow_usd = exchange_signal.get("net_flow_usd", 0)

        if altflow_signal:
            biases.append(altflow_signal["bias"])
            strengths.append(altflow_signal["strength"])
            confidences.append(altflow_signal["confidence"])
            signals.extend(altflow_signal["signals"])

        if whale_signal:
            biases.append(whale_signal["bias"])
            strengths.append(whale_signal["strength"])
            confidences.append(whale_signal["confidence"])
            signals.extend(whale_signal["signals"])

        # Combine bias: majority vote
        bull = sum(1 for b in biases if b == "bullish")
        bear = sum(1 for b in biases if b == "bearish")
        if bull > bear:
            combined_bias = "bullish"
        elif bear > bull:
            combined_bias = "bearish"
        else:
            combined_bias = "neutral"

        # Combined strength: weighted average
        combined_strength = sum(strengths) / len(strengths) if strengths else 0
        combined_confidence = sum(confidences) / len(confidences) if confidences else 0.3

        event_count = len(signals)

        return {
            "bias": combined_bias,
            "strength": round(combined_strength, 4),
            "confidence": round(combined_confidence, 4),
            "flow": combined_bias,
            "net_flow_usd": net_flow_usd,
            "signals": signals[:8],
            "event_count": event_count,
            "whale_bias": whale_signal["bias"] if whale_signal else "neutral",
            "exchange_flow_bias": exchange_signal["bias"] if exchange_signal else "neutral",
            "dex_flow_bias": altflow_signal["bias"] if altflow_signal else "neutral",
        }
    except Exception:
        return None


def _get_exchange_flow(db, asset: str) -> dict | None:
    """Exchange inflow/outflow from onchain_v2_snapshots."""
    symbol = ASSET_TO_SNAPSHOT_SYMBOL.get(asset)
    if not symbol:
        return None

    snap = db["onchain_v2_snapshots"].find_one(
        {"symbol": symbol},
        {"_id": 0},
        sort=[("createdAt", DESCENDING)],
    )
    if not snap:
        return None

    inflow = snap.get("exchangeInflowUsd", 0)
    outflow = snap.get("exchangeOutflowUsd", 0)
    net = snap.get("netFlowUsd", outflow - inflow)

    signals = []
    # Net outflow = bullish (coins leaving exchanges)
    if net < -10_000_000:
        bias = "bullish"
        strength = min(1.0, abs(net) / 100_000_000)
        signals.append(f"Exchange net outflow ${abs(net)/1e6:.0f}M (accumulation)")
    elif net > 10_000_000:
        bias = "bearish"
        strength = min(1.0, abs(net) / 100_000_000)
        signals.append(f"Exchange net inflow ${net/1e6:.0f}M (distribution)")
    else:
        bias = "neutral"
        strength = 0.1
        signals.append("Exchange flow balanced")

    active = snap.get("activeAddresses", 0)
    if active > 40000:
        signals.append(f"High network activity ({active:,} addresses)")
    elif active > 0:
        signals.append(f"Network activity: {active:,} addresses")

    quality = snap.get("sourceQuality", 0.5)

    return {
        "bias": bias,
        "strength": round(strength, 4),
        "confidence": round(min(0.8, quality + 0.2), 4),
        "signals": signals,
        "net_flow_usd": net,
    }


def _get_altflow(db, asset: str) -> dict | None:
    """DEX flow data from onchain_v2_altflow_points."""
    symbol = ASSET_TO_ALTFLOW_SYMBOL.get(asset)
    if not symbol:
        return None

    point = db["onchain_v2_altflow_points"].find_one(
        {"symbol": symbol, "window": "24h"},
        {"_id": 0},
        sort=[("createdAt", DESCENDING)],
    )
    if not point:
        return None

    score = point.get("score", 0)
    conf = point.get("confidence", 0.3)
    dex_net = point.get("dexNetUsd", 0)
    cex_net = point.get("cexNetUsd", 0)
    drivers = point.get("drivers", [])

    signals = []
    if score > 0.2:
        bias = "bullish"
        signals.append("DEX flow shows buying pressure")
    elif score < -0.2:
        bias = "bearish"
        signals.append("DEX flow shows selling pressure")
    else:
        bias = "neutral"
        signals.append("DEX flow neutral")

    for d in drivers[:2]:
        signals.append(d)

    strength = min(1.0, abs(score))

    return {
        "bias": bias,
        "strength": round(strength, 4),
        "confidence": round(min(0.7, conf + 0.1), 4),
        "signals": signals,
    }


def _get_whale_signal(db, asset: str) -> dict | None:
    """Whale positioning from exchange_whale_events."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7))
    cutoff_ts = cutoff.timestamp() * 1000  # ms

    symbol_pattern = f"{asset}USDT"
    events = list(db["exchange_whale_events"].find(
        {"symbol": symbol_pattern, "timestamp": {"$gte": cutoff_ts}},
        {"_id": 0, "eventType": 1, "side": 1, "deltaUsd": 1, "totalSizeUsd": 1},
    ).sort("timestamp", DESCENDING).limit(20))

    if not events:
        return None

    net_delta = 0
    signals = []
    long_opens = 0
    short_opens = 0

    for e in events:
        etype = e.get("eventType", "")
        side = e.get("side", "")
        delta = e.get("deltaUsd", 0)

        if etype == "OPEN" and side == "LONG":
            long_opens += 1
            net_delta += abs(delta)
        elif etype == "OPEN" and side == "SHORT":
            short_opens += 1
            net_delta -= abs(delta)
        elif etype == "CLOSE" and side == "SHORT":
            net_delta += abs(delta) * 0.5  # closing shorts = mildly bullish
        elif etype == "CLOSE" and side == "LONG":
            net_delta -= abs(delta) * 0.5

    if long_opens > short_opens:
        bias = "bullish"
        signals.append(f"Whales opening {long_opens} longs vs {short_opens} shorts")
    elif short_opens > long_opens:
        bias = "bearish"
        signals.append(f"Whales opening {short_opens} shorts vs {long_opens} longs")
    else:
        bias = "neutral"
        signals.append("Whale activity mixed")

    strength = min(1.0, abs(net_delta) / 200_000_000)
    confidence = min(0.7, len(events) / 15.0)

    return {
        "bias": bias,
        "strength": round(strength, 4),
        "confidence": round(confidence, 4),
        "signals": signals,
    }
