"""
Event Ingestion — orchestrates the full feed pipeline.

Pipeline:
  1. Fetch all active events from Gamma API (paginated)
  2. Filter crypto events
  3. Normalize events + markets
  4. Classify event types
  5. Detect asset groups + categories
  6. Build market snapshots
  7. Compute outcome-level overlays
  8. Aggregate into event-level overlays
  9. Score universe: HOT / ACTIONABLE / ALL
  10. Update health

Returns the full feed ready for API/UI consumption.
"""
import time
import logging
from datetime import datetime, timezone

from prediction.feed.event_source import fetch_all_active_events
from prediction.feed.crypto_filter import is_crypto_event, detect_asset_group, detect_category
from prediction.feed.event_normalizer import normalize_event
from prediction.feed.event_classifier import classify_event, is_multi_outcome
from prediction.feed.market_snapshot import build_snapshot, compute_freshness
from prediction.feed.outcome_overlay import compute_outcome_overlay
from prediction.feed.event_overlay_aggregator import aggregate_event_overlay
from prediction.feed.feed_health import update_health, record_error
from prediction.feed.structure_edge import analyze_ladder, get_outcome_structure_edge
from prediction.feed.fair_prob_v2 import compute_fair_prob
from prediction.feed.event_decision import decide_event
from prediction.feed.position_sizing import compute_position_sizing
from prediction.prediction_lab.forecast_recorder import record_forecast
from prediction.prediction_lab.db_helper import get_sync_db

logger = logging.getLogger("feed.ingestion")

# In-memory cache
_feed_cache = {"data": None, "ts": 0}
CACHE_TTL = 90  # seconds


async def ingest_feed(force_refresh: bool = False) -> dict:
    """Main feed pipeline — returns full feed for UI."""
    now = time.time()
    if not force_refresh and _feed_cache["data"] and (now - _feed_cache["ts"]) < CACHE_TTL:
        return _feed_cache["data"]

    try:
        # 1. Fetch all active events
        raw_events = await fetch_all_active_events(max_pages=5)
        logger.info(f"Fetched {len(raw_events)} total events")

        # 2. Filter crypto events
        crypto_events = [ev for ev in raw_events if is_crypto_event(ev)]
        logger.info(f"Crypto events: {len(crypto_events)}")

        # 3-8. Process each event
        feed_events = []
        total_markets = 0
        total_overlays = 0

        for raw_ev in crypto_events:
            event_card = _process_event(raw_ev)
            if event_card:
                feed_events.append(event_card)
                total_markets += event_card["markets_count"]
                total_overlays += event_card["overlay"]["outcomes_analyzed"]

        # 9. Score universe
        hot, actionable, rest = _score_universe(feed_events)

        # 10. Update health
        update_health(len(feed_events), total_markets, total_overlays)

        result = {
            "ok": True,
            "total_events": len(feed_events),
            "total_markets": total_markets,
            "hot_count": len(hot),
            "actionable_count": len(actionable),
            "hot": hot,
            "actionable": actionable,
            "all": feed_events,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "freshness": {
                "age_seconds": 0,
                "stale": False,
                "label": "live",
            },
        }

        _feed_cache["data"] = result
        _feed_cache["ts"] = time.time()
        return result

    except Exception as e:
        record_error()
        logger.error(f"Feed ingestion failed: {e}")
        if _feed_cache["data"]:
            # Return stale data with freshness warning
            stale = _feed_cache["data"].copy()
            stale["freshness"] = compute_freshness(_feed_cache["ts"])
            return stale
        return {"ok": False, "error": str(e), "total_events": 0}


def _process_event(raw_event: dict) -> dict | None:
    """Process a single raw event into a feed card.

    Phase 2 pipeline:
      1. Normalize + classify
      2. Structure Edge analysis (multi-outcome ladders)
      3. Fair Prob v2 per outcome (uses structure_edge)
      4. Outcome overlays (uses fair_prob_v2)
      5. Event Decision Engine (replaces old aggregator)
    """
    # Normalize
    normalized = normalize_event(raw_event)
    if not normalized["markets"]:
        return None

    # Classify
    event_type = classify_event(normalized)
    asset_group = detect_asset_group(raw_event)
    category = detect_category(raw_event)
    is_multi = is_multi_outcome(normalized)

    # Phase 2: Structure Edge for multi-outcome ladders
    structure_analysis = None
    if is_multi and len(normalized["markets"]) >= 3:
        try:
            structure_analysis = analyze_ladder(normalized["markets"])
        except Exception as e:
            logger.warning(f"Structure edge failed for {normalized['event_id']}: {e}")

    # Event context for fair_prob_v2
    event_context = {"end_date": normalized.get("end_date")}

    # Compute overlays with Phase 2 fair probability
    outcome_overlays = []
    for market in normalized["markets"]:
        if market.get("closed"):
            continue

        # Get structure edge for this specific outcome
        struct_edge = get_outcome_structure_edge(structure_analysis, market["market_id"])

        # Phase 2: Fair Prob v2 (multi-factor model)
        fp_result = compute_fair_prob(market, event_type, struct_edge, event_context)

        # Build overlay using v2 fair prob
        overlay = compute_outcome_overlay(market, event_type, fp_result, struct_edge)
        outcome_overlays.append(overlay)

    # Phase 2: Event Decision Engine (single decisive action per card)
    event_overlay = decide_event(normalized, outcome_overlays, structure_analysis)

    # Phase 2: Position Sizing (how much to bet)
    sizing = compute_position_sizing(
        {**normalized, "event_type": event_type, "markets": normalized["markets"]},
        event_overlay,
        structure_analysis,
    )
    event_overlay["sizing"] = sizing

    # Phase 3: Confidence-Aware Pipeline (calibration → analytics → effective conf → gate → stability)
    try:
        lab_db = get_sync_db()
        if lab_db is not None:
            from prediction.feed.confidence_aware import apply_confidence_aware_pipeline
            from prediction.prediction_lab.forecast_recorder import build_family_key

            family_key = build_family_key(event_type, asset_group, normalized.get("end_date"), normalized.get("liquidity", 0))
            best_market_id = (event_overlay.get("best_pick") or {}).get("market_id", "")

            apply_confidence_aware_pipeline(
                event_overlay=event_overlay,
                sizing=sizing,
                family_key=family_key,
                market_id=best_market_id,
                db=lab_db,
            )
    except Exception as e:
        logger.debug(f"Confidence-aware pipeline skipped: {e}")

    # Prediction Lab: Record forecast snapshot (fire-and-forget)
    try:
        lab_db = get_sync_db()
        if lab_db is not None:
            record_forecast(
                {**normalized, "event_type": event_type, "asset_group": asset_group,
                 "category": category, "is_multi": is_multi},
                event_overlay, outcome_overlays, structure_analysis, lab_db
            )
    except Exception as e:
        logger.debug(f"Forecast recording skipped: {e}")

    # Build event card
    return {
        "event_id": normalized["event_id"],
        "title": normalized["title"],
        "slug": normalized["slug"],
        "end_date": normalized["end_date"],
        "volume": normalized["volume"],
        "volume_24h": normalized["volume_24h"],
        "liquidity": normalized["liquidity"],
        "image": normalized.get("image", ""),
        "is_multi": is_multi,
        "markets_count": normalized["markets_count"],
        "event_type": event_type,
        "asset_group": asset_group,
        "category": category,
        "markets": _prepare_markets_for_ui(normalized["markets"], outcome_overlays),
        "overlay": event_overlay,
        "tier": "all",  # will be set by _score_universe
    }


def _prepare_markets_for_ui(markets: list[dict], overlays: list[dict]) -> list[dict]:
    """Prepare market list for frontend card display."""
    overlay_map = {o["market_id"]: o for o in overlays}
    result = []
    for m in markets:
        ov = overlay_map.get(m["market_id"])
        result.append({
            "market_id": m["market_id"],
            "question": m["question"],
            "group_title": m.get("group_title", ""),
            "yes_price": m["yes_price"],
            "no_price": m["no_price"],
            "best_bid": m.get("best_bid", 0),
            "best_ask": m.get("best_ask", 0),
            "spread": m.get("spread", 0),
            "volume": m.get("volume", 0),
            "liquidity": m.get("liquidity", 0),
            "overlay": {
                "fair_prob": ov["fair_prob"] if ov else None,
                "edge": ov["edge"] if ov else None,
                "edge_pct": ov["edge_pct"] if ov else None,
                "confidence": ov["confidence"] if ov else None,
                "action": ov["action"] if ov else None,
                "structure_edge": ov.get("structure_edge", 0) if ov else None,
            } if ov else None,
        })
    return result


def _score_universe(events: list[dict]) -> tuple[list, list, list]:
    """Score events into HOT / ACTIONABLE / ALL.

    HOT: High volume + ending soon + trending
    ACTIONABLE: Significant edge + decent confidence + executable
    ALL: everything
    """
    hot = []
    actionable = []

    for ev in events:
        score_hot = 0
        score_actionable = 0

        # HOT scoring: volume + recency
        vol_24h = ev.get("volume_24h", 0)
        if vol_24h > 500000:
            score_hot += 3
        elif vol_24h > 100000:
            score_hot += 2
        elif vol_24h > 20000:
            score_hot += 1

        total_vol = ev.get("volume", 0)
        if total_vol > 1000000:
            score_hot += 2
        elif total_vol > 100000:
            score_hot += 1

        # Ending soon bonus
        end_date = ev.get("end_date")
        if end_date:
            try:
                end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                hours_left = (end - datetime.now(timezone.utc)).total_seconds() / 3600
                if 0 < hours_left < 24:
                    score_hot += 2
                elif 0 < hours_left < 72:
                    score_hot += 1
            except Exception:
                pass

        # ACTIONABLE scoring: edge + confidence + execution
        overlay = ev.get("overlay", {})
        best_pick = overlay.get("best_pick") or overlay.get("strongest_edge")
        if best_pick:
            abs_edge = abs(best_pick.get("edge", 0))
            if abs_edge > 0.05:
                score_actionable += 3
            elif abs_edge > 0.025:
                score_actionable += 2
            elif abs_edge > 0.01:
                score_actionable += 1

            conf = best_pick.get("confidence", "low")
            if conf == "high":
                score_actionable += 2
            elif conf == "medium":
                score_actionable += 1

            exec_style = best_pick.get("execution", {}).get("style", "")
            if exec_style in ("MARKET_OK", "LIMIT_PREFERRED"):
                score_actionable += 1

        # Multiple outcomes with edge = more actionable
        outcomes_with_edge = overlay.get("outcomes_with_edge", 0)
        if outcomes_with_edge >= 3:
            score_actionable += 1

        # Classify
        if score_hot >= 3:
            ev["tier"] = "hot"
            hot.append(ev)
        elif score_actionable >= 3:
            ev["tier"] = "actionable"
            actionable.append(ev)
        else:
            ev["tier"] = "all"

    # Sort: hot by volume, actionable by edge
    hot.sort(key=lambda x: x.get("volume_24h", 0), reverse=True)
    actionable.sort(
        key=lambda x: abs((x.get("overlay", {}).get("best_pick") or {}).get("edge", 0) or 0),
        reverse=True,
    )

    return hot, actionable, events
