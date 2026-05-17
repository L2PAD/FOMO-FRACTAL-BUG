"""
Price Tracker — periodically snapshots market prices for pending forecasts.

Runs every 5 minutes. For each unresolved forecast, fetches the current
market price from Polymarket Gamma API and appends it to a price_snapshots
array in the forecast_record. These snapshots are used to build the
pricePath (t0, t5m, t15m, t1h, t4h, tFinal, high, low) when resolving.
"""
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger("prediction_lab.price_tracker")

GAMMA_BASE = "https://gamma-api.polymarket.com"


async def track_pending_prices(db, limit: int = 100) -> dict:
    """Snapshot current prices for unresolved forecasts."""
    pending = list(db.forecast_records.find(
        {"resolved": False},
        {"_id": 0, "forecast_id": 1, "market_id": 1, "event_id": 1}
    ).sort("created_at", -1).limit(limit))

    if not pending:
        return {"tracked": 0}

    # Group by event_id to batch API calls
    event_map = {}
    for rec in pending:
        eid = rec["event_id"]
        if eid not in event_map:
            event_map[eid] = []
        event_map[eid].append(rec)

    tracked = 0
    now = datetime.now(timezone.utc).isoformat()

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            for event_id, records in event_map.items():
                try:
                    resp = await client.get(f"{GAMMA_BASE}/events/{event_id}")
                    if resp.status_code != 200:
                        continue

                    event_data = resp.json()
                    markets = event_data.get("markets", [])
                    price_map = {}

                    for m in markets:
                        mid = m.get("id", "")
                        try:
                            prices = m.get("outcomePrices", "[]")
                            if isinstance(prices, str):
                                prices = eval(prices)
                            if prices:
                                price_map[mid] = float(prices[0])
                        except Exception:
                            pass

                    for rec in records:
                        market_id = rec.get("market_id", "")
                        if market_id in price_map:
                            snapshot = {
                                "ts": now,
                                "price": price_map[market_id],
                            }
                            db.forecast_records.update_one(
                                {"forecast_id": rec["forecast_id"]},
                                {"$push": {"price_snapshots": snapshot}}
                            )
                            tracked += 1

                except Exception as e:
                    logger.debug(f"Price track error for event {event_id}: {e}")

    except Exception as e:
        logger.error(f"Price tracker batch error: {e}")

    if tracked:
        logger.info(f"Tracked prices for {tracked} forecasts")
    return {"tracked": tracked}
