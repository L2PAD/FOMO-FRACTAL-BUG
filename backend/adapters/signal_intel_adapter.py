"""
Signal Intelligence Adapter — bridges Python prediction pipeline to Node.js Stage 6.

Calls the Node.js Prediction Intel service to get:
  - Source trust evaluation
  - Event interpretation with multi-channel impact
  - Already-priced detection
  - Smart drivers (human-readable explanations)

Returns aggregated signal batch for each market.
"""
import httpx
import logging
from typing import Optional

logger = logging.getLogger("prediction.signal_intel")

NODE_INTEL_URL = "http://localhost:8003/api/prediction-intel"


async def get_market_intelligence(
    market_id: str,
    asset: str,
    entities: list[str],
    event_type: str,
    current_prob: float,
    move_6h: float = 0,
    move_24h: float = 0,
    volume: float = 0,
    repricing_state: str | None = None,
) -> dict:
    """
    Get signal intelligence for a single market from Node.js layer.
    Returns aggregated signal batch with net impacts.
    """
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{NODE_INTEL_URL}/market/{market_id}",
                params={
                    "asset": asset,
                    "entities": ",".join(entities),
                    "eventType": event_type,
                    "currentProb": str(current_prob),
                    "move6h": str(move_6h),
                    "move24h": str(move_24h),
                    "volume": str(volume),
                    "repricingState": repricing_state or "",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data["data"]
    except Exception as e:
        logger.debug(f"Signal intel unavailable for {market_id}: {e}")

    return _empty_batch(market_id, asset)


async def get_batch_intelligence(
    markets: list[dict],
) -> dict[str, dict]:
    """
    Get signal intelligence for multiple markets at once.
    Returns {market_id: signal_batch}.
    """
    try:
        payload = {
            "markets": [
                {
                    "marketId": m["market_id"],
                    "asset": m.get("asset", "BTC"),
                    "entities": m.get("entities", [m.get("asset", "BTC")]),
                    "eventType": m.get("event_type", "unknown"),
                    "currentProb": m.get("current_prob", 0.5),
                    "move6h": m.get("move_6h", 0),
                    "move24h": m.get("move_24h", 0),
                    "volume": m.get("volume", 0),
                    "repricingState": m.get("repricing_state"),
                }
                for m in markets
            ]
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{NODE_INTEL_URL}/batch", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data.get("results", {})
    except Exception as e:
        logger.debug(f"Batch signal intel unavailable: {e}")

    return {}


def extract_smart_drivers(signal_batch: dict) -> dict:
    """
    Extract smart driver info from a signal batch for the case output.
    Returns dict with: top_driver, net_impacts, signal_count, dominant_bias, etc.
    """
    agg = signal_batch.get("aggregated", {})
    signals = signal_batch.get("signals", [])

    if not signals:
        return {
            "smart_drivers": [],
            "top_driver": None,
            "dominant_bias": "neutral",
            "signal_count": 0,
            "net_probability_impact": 0,
            "net_confidence_impact": 0,
            "net_alignment_impact": 0,
            "avg_novelty": 0,
            "avg_already_priced": 0,
        }

    # Top 3 smart drivers
    smart_drivers = [s.get("smartDriver", "") for s in signals[:3] if s.get("smartDriver")]

    return {
        "smart_drivers": smart_drivers,
        "top_driver": agg.get("topDriver"),
        "dominant_bias": agg.get("dominantBias", "neutral"),
        "signal_count": agg.get("signalCount", len(signals)),
        "net_probability_impact": agg.get("netProbabilityImpact", 0),
        "net_confidence_impact": agg.get("netConfidenceImpact", 0),
        "net_alignment_impact": agg.get("netAlignmentImpact", 0),
        "avg_novelty": agg.get("avgNovelty", 0),
        "avg_already_priced": agg.get("avgAlreadyPriced", 0),
    }


def _empty_batch(market_id: str, asset: str) -> dict:
    return {
        "marketId": market_id,
        "asset": asset,
        "signals": [],
        "aggregated": {
            "netProbabilityImpact": 0,
            "netConfidenceImpact": 0,
            "netAlignmentImpact": 0,
            "dominantBias": "neutral",
            "signalCount": 0,
            "avgNovelty": 0,
            "avgAlreadyPriced": 0,
            "topDriver": "No relevant signals",
        },
    }
