"""
Live Intelligence Engine — controlled live updates for HOT markets.

Architecture:
  1. Background task polls Polymarket prices for HOT markets every 5s
  2. Compares with cached overlay → computes delta
  3. Update Gate blocks noise (edge_delta < 2%, conf_delta < 3%)
  4. Only meaningful changes update the live state
  5. Client polls /api/live/feed every 5-10s

Key principle: minimum updates, maximum meaning.
No websockets needed — controlled polling is sufficient.
"""
import time
import asyncio
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger("feed.live_engine")

GAMMA_BASE = "https://gamma-api.polymarket.com"

# Polling intervals (seconds)
HOT_INTERVAL = 5
ACTIONABLE_INTERVAL = 15

# Thresholds
PRICE_CHANGE_THRESHOLD = 0.01   # 1% price change to trigger overlay refresh
EDGE_DELTA_THRESHOLD = 0.02     # 2% edge change to emit update
CONF_DELTA_THRESHOLD = 0.03     # 3% confidence change to emit update
MIN_REFRESH_INTERVAL = 20       # seconds between overlay refreshes per market
STALE_THRESHOLD_HOT = 20        # seconds before HOT market is STALE
STALE_THRESHOLD_ACTIONABLE = 45
STALE_THRESHOLD_ALL = 180

# In-memory live state: market_id → LiveMarketState
_live_states: dict[str, dict] = {}

# Metrics
_metrics = {
    "cycles": 0,
    "prices_fetched": 0,
    "updates_total": 0,
    "updates_emitted": 0,
    "updates_blocked": 0,
    "overlay_recalc": 0,
    "last_cycle_at": None,
    "avg_cycle_ms": 0,
}


def get_live_state(market_id: str) -> dict | None:
    """Get live state for a specific market."""
    return _live_states.get(market_id)


def get_all_live_states() -> dict:
    """Get all live states."""
    return dict(_live_states)


def get_live_metrics() -> dict:
    """Get live engine metrics."""
    now = time.time()
    hot_count = sum(1 for s in _live_states.values() if s.get("tier") == "hot")
    stale_count = sum(1 for s in _live_states.values() if _is_stale(s, now))

    return {
        **_metrics,
        "hot_live": hot_count,
        "total_tracked": len(_live_states),
        "stale_count": stale_count,
    }


def enrich_event_with_live(event: dict) -> dict:
    """Enrich a cached event with live state (freshness, prices, stale)."""
    markets = event.get("markets", [])
    now = time.time()

    any_live = False
    any_stale = False
    freshest = None

    for m in markets:
        mid = m.get("market_id", "")
        live = _live_states.get(mid)
        if live:
            any_live = True
            # Update market price from live data
            if live.get("live_price") is not None:
                m["live_price"] = live["live_price"]
                m["live_spread"] = live.get("live_spread")

            is_stale = _is_stale(live, now)
            if is_stale:
                any_stale = True

            freshness_sec = int(now - live.get("price_updated_at", now))
            m["freshness_seconds"] = freshness_sec
            m["is_stale"] = is_stale

            if freshest is None or freshness_sec < freshest:
                freshest = freshness_sec

    # Event-level live info
    event["live"] = {
        "is_live": any_live,
        "is_stale": any_stale and not any_live,
        "freshness_seconds": freshest,
        "state": "STALE" if (any_stale and not any_live) else ("LIVE" if any_live else "OFFLINE"),
    }

    return event


def _is_stale(state: dict, now: float) -> bool:
    """Check if a live state is stale based on tier."""
    last_update = state.get("price_updated_at", 0)
    elapsed = now - last_update
    tier = state.get("tier", "all")

    if tier == "hot":
        return elapsed > STALE_THRESHOLD_HOT
    elif tier == "actionable":
        return elapsed > STALE_THRESHOLD_ACTIONABLE
    return elapsed > STALE_THRESHOLD_ALL


# ──────── Background Live Cycle ────────

async def run_live_cycle(feed_cache: dict):
    """Single live cycle: fetch prices → compute deltas → update gate → emit.

    Called from the background task every HOT_INTERVAL seconds.
    """
    if not feed_cache or not feed_cache.get("ok"):
        return

    cycle_start = time.time()
    _metrics["cycles"] += 1

    # Get HOT events
    hot_events = feed_cache.get("hot", [])
    actionable_events = feed_cache.get("actionable", [])

    # Collect event IDs for HOT
    events_to_poll = list(hot_events)

    # Every 3rd cycle, also poll actionable (~15s)
    cycle_num = _metrics["cycles"]
    if cycle_num % 3 == 0:
        events_to_poll.extend(actionable_events)

    if not events_to_poll:
        return

    # Collect unique event IDs
    event_ids = list({ev.get("event_id") for ev in events_to_poll if ev.get("event_id")})

    # Fetch live prices from Polymarket (by event)
    live_prices = await _fetch_live_prices_by_event(event_ids)
    _metrics["prices_fetched"] += len(live_prices)

    # Build market → event mapping
    market_to_info = {}
    for ev in events_to_poll:
        tier = "hot" if ev in hot_events else "actionable"
        for m in ev.get("markets", []):
            mid = str(m.get("market_id", ""))
            if mid:
                market_to_info[mid] = {"event": ev, "market": m, "tier": tier}

    now = time.time()
    emitted = 0
    blocked = 0
    recalc = 0

    for mid, price_data in live_prices.items():
        info = market_to_info.get(mid)
        if not info:
            continue

        market = info["market"]
        tier = info["tier"]
        new_price = price_data.get("price", 0)

        prev_state = _live_states.get(mid, {})
        prev_price = prev_state.get("live_price", market.get("yes_price", 0))

        # Compute price change
        price_delta = abs(new_price - prev_price) if prev_price else 0

        # Check if overlay refresh needed
        last_refresh = prev_state.get("last_overlay_refresh", 0)
        time_since_refresh = now - last_refresh
        needs_refresh = (
            price_delta >= PRICE_CHANGE_THRESHOLD or
            time_since_refresh >= MIN_REFRESH_INTERVAL * 2
        )

        if needs_refresh:
            recalc += 1

        # Compute edge delta from overlay
        overlay = info["event"].get("overlay", {})
        bp = overlay.get("best_pick", {}) or {}
        old_edge = abs(bp.get("edge", 0))

        # Quick edge recalc: edge ~ fair_prob - market_prob
        fair_prob = bp.get("fair_prob", new_price)
        new_edge = abs(fair_prob - new_price) if fair_prob else 0
        edge_delta = abs(new_edge - old_edge)

        # Update gate
        should_emit = _update_gate(
            edge_delta=edge_delta,
            price_delta=price_delta,
            needs_refresh=needs_refresh,
        )

        _metrics["updates_total"] += 1

        if should_emit:
            emitted += 1
        else:
            blocked += 1

        # Always update live state
        _live_states[mid] = {
            "market_id": mid,
            "tier": tier,
            "live_price": round(new_price, 4),
            "live_spread": price_data.get("spread"),
            "prev_price": round(prev_price, 4) if prev_price else None,
            "price_delta": round(price_delta, 4),
            "edge_delta": round(edge_delta, 4),
            "price_updated_at": now,
            "last_overlay_refresh": now if needs_refresh else last_refresh,
            "update_emitted": should_emit,
        }

    _metrics["updates_emitted"] += emitted
    _metrics["updates_blocked"] += blocked
    _metrics["overlay_recalc"] += recalc
    _metrics["last_cycle_at"] = datetime.now(timezone.utc).isoformat()

    cycle_ms = (time.time() - cycle_start) * 1000
    _metrics["avg_cycle_ms"] = round(
        (_metrics["avg_cycle_ms"] * 0.9 + cycle_ms * 0.1), 1
    )

    if emitted > 0 or _metrics["cycles"] % 20 == 0:
        logger.info(f"Live: {len(live_prices)} prices, emit={emitted}, block={blocked}, recalc={recalc}, {cycle_ms:.0f}ms")


def _update_gate(edge_delta: float, price_delta: float, needs_refresh: bool) -> bool:
    """Update gate: block noise, only emit meaningful changes."""
    # Always emit if significant edge change
    if edge_delta >= EDGE_DELTA_THRESHOLD:
        return True

    # Emit if significant price move AND refresh needed
    if price_delta >= PRICE_CHANGE_THRESHOLD and needs_refresh:
        return True

    # Block everything else
    return False


async def _fetch_live_prices_by_event(event_ids: list[str]) -> dict:
    """Fetch current prices from Polymarket for markets in given events.

    Returns: {market_id: {price, spread}}
    """
    result = {}
    if not event_ids:
        return result

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            # Batch events (max 5 concurrent)
            for i in range(0, len(event_ids), 5):
                chunk = event_ids[i:i + 5]
                tasks = []
                for eid in chunk:
                    tasks.append(client.get(f"{GAMMA_BASE}/events/{eid}"))

                responses = await asyncio.gather(*tasks, return_exceptions=True)

                for resp in responses:
                    if isinstance(resp, Exception):
                        continue
                    if resp.status_code != 200:
                        continue

                    try:
                        event_data = resp.json()
                        markets = event_data.get("markets", [])
                        for m in markets:
                            mid = str(m.get("id", ""))
                            if not mid:
                                continue
                            try:
                                prices_str = m.get("outcomePrices", "[]")
                                prices = eval(prices_str) if isinstance(prices_str, str) else prices_str
                                if prices:
                                    yes_price = float(prices[0])
                                    no_price = float(prices[1]) if len(prices) > 1 else (1 - yes_price)
                                    spread = abs(yes_price + no_price - 1)
                                    result[mid] = {
                                        "price": yes_price,
                                        "spread": round(spread, 4),
                                    }
                            except Exception:
                                pass
                    except Exception:
                        pass

    except Exception as e:
        logger.error(f"Live price fetch error: {e}")

    return result


# ──────── Background Task ────────

async def start_live_engine():
    """Start the live intelligence engine background loop."""
    from prediction.feed.event_ingestion import _feed_cache

    await asyncio.sleep(45)  # Wait for first feed sync
    logger.info("[LiveEngine] Started (HOT=5s, ACTIONABLE=15s)")

    while True:
        try:
            cache_data = _feed_cache.get("data")
            if cache_data:
                await run_live_cycle(cache_data)
        except Exception as e:
            logger.error(f"[LiveEngine] Cycle error: {e}")

        await asyncio.sleep(HOT_INTERVAL)
