"""
Market Watcher — background service that monitors prediction markets.

Priority Queue:
  - Tier 1 (actionable, high edge, fresh/early repricing): every 2 min
  - Tier 2 (watchlist, medium edge): every 5 min
  - Tier 3 (low priority): every 15 min

Each cycle:
  1. Fetch markets from Polymarket
  2. Run full pipeline
  3. Save snapshots + deltas
  4. Compare with stored state
  5. Detect transitions → trigger alerts
  6. Update state store
  7. Assign priority tier for next cycle
"""
import asyncio
import logging
from datetime import datetime, timezone

from prediction import (
    polymarket_client, event_classifier, probability_engine,
    edge_engine, alignment_engine, resolution_engine,
    pricing_engine, recommendation_engine, sizing_engine, execution_engine,
)
from prediction.intelligence import catalyst_engine
from prediction.timing import repricing_detector, entry_timing_engine, market_stage_engine
from prediction.timing import state_transition_engine
from prediction.monitoring import market_state_store, snapshot_service, trigger_engine, alert_engine

from adapters import exchange_adapter, onchain_adapter, sentiment_adapter

logger = logging.getLogger("market_watcher")

# Watcher state
_running = False
_task = None
_last_cycle_at = None
_cycle_count = 0
_last_results = {}
_last_alerts = []
_market_tiers = {}  # market_id → {"tier": 1|2|3, "next_check": datetime}

CATALYST_TYPES = {"etf_catalyst", "listing_catalyst", "launch_catalyst", "token_launch"}

TIER_INTERVALS = {
    1: 120,   # 2 min
    2: 300,   # 5 min
    3: 900,   # 15 min
}


def _assign_tier(case: dict) -> int:
    """Assign priority tier based on case quality."""
    action = case.get("recommendation", {}).get("action", "")
    edge = abs(case.get("analysis", {}).get("net_edge", 0))
    rstate = case.get("repricing", {}).get("repricing_state", "")
    entry = case.get("entry_timing", {}).get("entry_action", "")
    stage = case.get("market_stage", "")

    # Tier 1: actionable, high edge, fresh/early repricing
    if action in ("YES_NOW", "NO_NOW"):
        return 1
    if entry in ("enter_now", "enter_limit") and rstate in ("fresh_mispricing", "early_repricing"):
        return 1
    if edge >= 0.10 and rstate in ("fresh_mispricing", "early_repricing"):
        return 1
    if stage == "triggered":
        return 1

    # Tier 2: watchlist, moderate edge
    if action in ("YES_SMALL", "NO_SMALL", "GOOD_IDEA_BAD_PRICE"):
        return 2
    if edge >= 0.05:
        return 2
    if rstate in ("active_repricing",):
        return 2
    if stage in ("forming", "repricing"):
        return 2

    # Tier 3: everything else
    return 3


def _should_check(market_id: str) -> bool:
    """Check if a market is due for monitoring."""
    info = _market_tiers.get(market_id)
    if not info:
        return True  # never checked
    now = datetime.now(timezone.utc)
    return now >= info.get("next_check", now)


async def run_cycle(limit: int = 100) -> dict:
    """Run one full watcher cycle."""
    global _last_cycle_at, _cycle_count, _last_results, _last_alerts

    _last_cycle_at = datetime.now(timezone.utc).isoformat()
    _cycle_count += 1

    markets = await polymarket_client.fetch_markets(limit=limit)

    exchange_btc = exchange_adapter.get_forecast("BTC", "30D")
    exchange_eth = exchange_adapter.get_forecast("ETH", "30D")
    onchain_btc = onchain_adapter.get_flow_signal("BTC")
    onchain_eth = onchain_adapter.get_flow_signal("ETH")
    sentiment_btc = sentiment_adapter.get_sentiment_signal("BTC")
    sentiment_eth = sentiment_adapter.get_sentiment_signal("ETH")

    cases = []
    alerts_fired = []
    skipped = 0
    tier_counts = {1: 0, 2: 0, 3: 0}

    for m in markets:
        mid = m["market_id"]

        # Priority gating: skip markets not due for check
        if not _should_check(mid):
            continue

        classified = event_classifier.classify(m["question"])
        etype = classified["event_type"]
        mtype = classified.get("market_type", "unknown")

        if etype == "unknown":
            skipped += 1
            continue

        asset = classified.get("asset", "BTC")
        onchain = onchain_btc if asset in ("BTC", None) else onchain_eth
        sentiment = sentiment_btc if asset in ("BTC", None) else sentiment_eth

        try:
            if mtype == "quant":
                exchange = exchange_btc if asset == "BTC" else exchange_eth
                case = _build_case_quant(m, classified, exchange, onchain, sentiment)
            elif mtype == "catalyst" or etype in CATALYST_TYPES:
                case = await _build_case_catalyst(m, classified, onchain, sentiment)
            else:
                skipped += 1
                continue

            # Save snapshot
            snapshot_service.save_snapshot(
                mid, m.get("yes_price", 0.5),
                m.get("volume", 0), m.get("liquidity", 0), m.get("spread", 0),
            )

            # Compute deltas
            deltas = snapshot_service.compute_deltas(
                mid, m.get("yes_price", 0.5), m.get("volume", 0),
            )

            # Repricing detection
            repricing = repricing_detector.analyze(
                m.get("yes_price", 0.5), case["analysis"]["fair_prob"],
                m.get("volume", 0), m.get("liquidity", 0), m.get("spread", 0),
                deltas,
            )
            case["repricing"] = repricing

            # Entry timing
            entry = entry_timing_engine.decide(
                edge=case["analysis"]["net_edge"],
                confidence=case["analysis"]["model_confidence"],
                alignment=case["analysis"]["alignment_score"],
                repricing_state=repricing["repricing_state"],
                spread=m.get("spread", 0),
                liquidity=m.get("liquidity", 0),
                resolution_risk=case["resolution"].get("resolution_risk_score", 0),
                action=case["recommendation"]["action"],
                acceleration=repricing.get("acceleration", 0),
                speed_score=repricing.get("speed_score", 0),
            )
            case["entry_timing"] = entry

            # Market stage
            stage = market_stage_engine.compute_stage(
                repricing["repricing_state"],
                case["analysis"]["net_edge"],
                case["analysis"]["model_confidence"],
                case["recommendation"]["action"],
                case["sizing"]["allowed"],
                deltas.get("snap_count", 0),
            )
            case["market_stage"] = stage

            # State transition detection
            old_state = market_state_store.get_state(mid)
            transitions = state_transition_engine.detect_transitions(old_state, case)

            # Trigger evaluation
            if transitions:
                triggers = trigger_engine.classify_transitions(transitions)
                signal_hash = market_state_store.compute_signal_hash(case)
                for trig in triggers:
                    if trig["priority"] in ("high", "medium"):
                        if trigger_engine.should_fire(mid, trig["alert_type"], signal_hash):
                            alert = alert_engine.create_alert(case, trig)
                            alerts_fired.append(alert)
                            trigger_engine.log_alert(mid, trig["alert_type"], signal_hash, alert)
                case["transitions"] = transitions

            # Update state store
            new_state = market_state_store.build_state_from_case(case)
            market_state_store.upsert_state(mid, new_state)

            # Assign tier for next cycle
            tier = _assign_tier(case)
            now = datetime.now(timezone.utc)
            from datetime import timedelta
            _market_tiers[mid] = {
                "tier": tier,
                "next_check": now + timedelta(seconds=TIER_INTERVALS[tier]),
            }
            tier_counts[tier] = tier_counts.get(tier, 0) + 1

            cases.append(case)

        except Exception as e:
            logger.warning(f"Watcher error on {mid}: {e}")
            skipped += 1

    _last_results = {
        "cycle": _cycle_count,
        "timestamp": _last_cycle_at,
        "total_markets": len(markets),
        "classified": len(cases),
        "skipped": skipped,
        "alerts_fired": len(alerts_fired),
        "tiers": tier_counts,
    }
    _last_alerts = alerts_fired

    return {
        "cases": cases,
        "alerts": alerts_fired,
        "summary": _last_results,
    }


async def _watcher_loop():
    """Background loop: runs cycle, sleeps, repeats."""
    global _running
    _running = True
    logger.info("Market watcher started")

    while _running:
        try:
            await run_cycle(limit=100)
            logger.info(f"Watcher cycle #{_cycle_count}: {_last_results}")
        except Exception as e:
            logger.error(f"Watcher cycle error: {e}")
        # Sleep for shortest tier interval (Tier 1 = 2 min)
        await asyncio.sleep(TIER_INTERVALS[1])


def start_watcher():
    """Start the watcher background task. Call from FastAPI lifespan."""
    global _task
    if _task is None or _task.done():
        loop = asyncio.get_event_loop()
        _task = loop.create_task(_watcher_loop())
        logger.info("Market watcher task created")


def stop_watcher():
    """Stop the watcher gracefully."""
    global _running, _task
    _running = False
    if _task and not _task.done():
        _task.cancel()
    logger.info("Market watcher stopped")


def get_watcher_status() -> dict:
    return {
        "running": _running,
        "last_cycle_at": _last_cycle_at,
        "cycle_count": _cycle_count,
        "last_results": _last_results,
        "market_tiers": {
            mid: {"tier": info["tier"]}
            for mid, info in list(_market_tiers.items())[:20]
        },
    }


# ---- Case builders (reuse routes.py logic) ----

def _build_case_quant(m, classified, exchange, onchain, sentiment):
    from prediction.routes import _build_quant_case
    return _build_quant_case(m, classified, exchange, onchain, sentiment)


async def _build_case_catalyst(m, classified, onchain, sentiment):
    from prediction.routes import _build_catalyst_case
    return await _build_catalyst_case(m, classified, onchain, sentiment)
