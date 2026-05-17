"""
Forecast Resolver — checks if markets resolved and captures final outcomes.

Periodically scans unresolved forecast_records, queries Polymarket for
resolution status, and writes forecast_results with:
  - Binary correctness + rank distance
  - Brier score
  - pricePath (t0 → tFinal with snapshots)
  - Opportunity Capture (did price ever move in our direction?)
  - Entry Quality Proxy (bestPossible - actualEntry)

Has retry logic with max 5 attempts and exponential backoff delay tracking.
"""
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger("prediction_lab.resolver")

GAMMA_BASE = "https://gamma-api.polymarket.com"
MAX_ATTEMPTS = 5
# Minimum seconds between retry attempts (exponential: 60, 120, 240, 480, 960)
BASE_RETRY_DELAY = 60


async def resolve_pending_forecasts(db, limit: int = 50) -> dict:
    """Resolve pending forecasts. Returns stats."""
    now = datetime.now(timezone.utc)

    pending = list(db.forecast_records.find(
        {"resolved": False, "resolve_attempts": {"$lt": MAX_ATTEMPTS}},
        {"_id": 0}
    ).sort("created_at", 1).limit(limit))

    if not pending:
        return {"checked": 0, "resolved": 0, "failed": 0}

    # Filter out records still in backoff period
    eligible = []
    for rec in pending:
        last_attempt = rec.get("last_attempt_at")
        attempts = rec.get("resolve_attempts", 0)
        if last_attempt and attempts > 0:
            try:
                last_ts = datetime.fromisoformat(last_attempt.replace("Z", "+00:00"))
                backoff = BASE_RETRY_DELAY * (2 ** (attempts - 1))
                if (now - last_ts).total_seconds() < backoff:
                    continue
            except Exception:
                pass
        eligible.append(rec)

    if not eligible:
        return {"checked": 0, "resolved": 0, "failed": 0, "in_backoff": len(pending)}

    resolved_count = 0
    failed_count = 0

    # Group by event_id for efficient API calls
    event_ids = list(set(r["event_id"] for r in eligible))
    resolved_events = await _fetch_resolved_events(event_ids)

    for record in eligible:
        event_id = record["event_id"]
        event_data = resolved_events.get(event_id)

        if not event_data:
            # Event not resolved yet
            db.forecast_records.update_one(
                {"forecast_id": record["forecast_id"]},
                {
                    "$inc": {"resolve_attempts": 1},
                    "$set": {"last_attempt_at": now.isoformat()},
                }
            )
            continue

        try:
            result = _build_result(record, event_data)
            if result:
                db.forecast_results.insert_one(result)
                db.forecast_records.update_one(
                    {"forecast_id": record["forecast_id"]},
                    {"$set": {"resolved": True}}
                )
                resolved_count += 1
                logger.info(f"Resolved {record['forecast_id']}: {result['correctness']}")
            else:
                db.forecast_records.update_one(
                    {"forecast_id": record["forecast_id"]},
                    {
                        "$inc": {"resolve_attempts": 1},
                        "$set": {"last_attempt_at": now.isoformat()},
                    }
                )
                failed_count += 1
        except Exception as e:
            logger.error(f"Error resolving {record['forecast_id']}: {e}")
            db.forecast_records.update_one(
                {"forecast_id": record["forecast_id"]},
                {
                    "$inc": {"resolve_attempts": 1},
                    "$set": {"last_attempt_at": now.isoformat()},
                }
            )
            failed_count += 1

    # Ensure indexes
    db.forecast_results.create_index("forecast_id", unique=True, background=True)
    db.forecast_results.create_index("family_key", background=True)
    db.forecast_results.create_index("resolved_at", background=True)

    return {"checked": len(eligible), "resolved": resolved_count, "failed": failed_count}


async def _fetch_resolved_events(event_ids: list[str]) -> dict:
    """Fetch resolution data for events from Polymarket."""
    resolved = {}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            for eid in event_ids:
                try:
                    resp = await client.get(f"{GAMMA_BASE}/events/{eid}")
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("closed") or data.get("resolved"):
                            resolved[eid] = data
                except Exception as e:
                    logger.debug(f"Event {eid} fetch error: {e}")
    except Exception as e:
        logger.error(f"Batch fetch error: {e}")
    return resolved


def _build_result(record: dict, event_data: dict) -> dict | None:
    """Build a forecast result with full pricePath, opportunity capture, and entry quality."""
    markets = event_data.get("markets", [])
    if not markets:
        return None

    predicted_market_id = record.get("market_id", "")
    predicted_market = None
    resolved_winner = None

    for m in markets:
        mid = m.get("id", "")
        if mid == predicted_market_id:
            predicted_market = m

        outcomes = m.get("outcomes", [])
        for oi, outcome in enumerate(outcomes):
            price_str = m.get("outcomePrices", "[]")
            try:
                prices = eval(price_str) if isinstance(price_str, str) else price_str
            except Exception:
                prices = []

            if prices and len(prices) > oi:
                try:
                    p = float(prices[oi])
                    if p > 0.95:
                        resolved_winner = {
                            "market_id": mid,
                            "outcome_label": outcome,
                            "outcome_index": oi,
                            "final_price": p,
                        }
                except (ValueError, TypeError):
                    pass

    # Get final price for the predicted market
    t_final = None
    if predicted_market:
        try:
            prices_str = predicted_market.get("outcomePrices", "[]")
            prices = eval(prices_str) if isinstance(prices_str, str) else prices_str
            if prices:
                t_final = float(prices[0])
        except Exception:
            pass

    # Build pricePath from snapshots
    t0 = record.get("market_prob", 0)
    snapshots = record.get("price_snapshots", [])

    # Extract trajectory from snapshots
    price_path = _build_price_path(t0, snapshots, t_final)

    # --- Binary correctness ---
    action = record.get("action", "WATCH")
    binary_correct = None

    if action in ("BUY_YES", "BUY_NO") and predicted_market:
        if resolved_winner:
            if action == "BUY_YES" and resolved_winner["market_id"] == predicted_market_id:
                binary_correct = True
            elif action == "BUY_NO" and resolved_winner["market_id"] != predicted_market_id:
                binary_correct = True
            else:
                binary_correct = False

    # --- Brier score ---
    brier_score = None
    fair_prob = record.get("fair_prob", 0)
    if binary_correct is not None:
        if action == "BUY_YES":
            actual_outcome = 1.0 if (resolved_winner and resolved_winner["market_id"] == predicted_market_id) else 0.0
        else:
            actual_outcome = 0.0 if (resolved_winner and resolved_winner["market_id"] == predicted_market_id) else 1.0
        brier_score = round((fair_prob - actual_outcome) ** 2, 4)

    # --- Realized edge ---
    realized_edge = None
    market_prob = record.get("market_prob", 0)
    if binary_correct is not None:
        actual_val = 1.0 if binary_correct else 0.0
        if action == "BUY_NO":
            actual_val = 1.0 - actual_val
        realized_edge = round(actual_val - market_prob, 4)

    # --- Rank distance (multi-outcome) ---
    top_pick_correct = None
    rank_distance = None
    if record.get("is_multi") and record.get("outcomes") and resolved_winner:
        selected_outcomes = [o for o in record["outcomes"] if o.get("selected")]
        if selected_outcomes:
            selected = selected_outcomes[0]
            top_pick_correct = selected["market_id"] == resolved_winner["market_id"]
            for i, o in enumerate(record["outcomes"]):
                if o["market_id"] == resolved_winner["market_id"]:
                    rank_distance = i
                    break

    # --- Confidence error ---
    conf_map = {"high": 0.8, "medium": 0.55, "low": 0.3}
    confidence_num = conf_map.get(record.get("confidence", "low"), 0.3)
    confidence_error = None
    if binary_correct is not None:
        actual_val = 1.0 if binary_correct else 0.0
        confidence_error = round(abs(confidence_num - actual_val), 4)

    # --- Opportunity Capture ---
    # Did the price ever move in our predicted direction?
    opportunity_captured = _compute_opportunity_captured(action, t0, snapshots, t_final)

    # --- Entry Quality Proxy ---
    # How close was our entry to the best possible price
    entry_quality = _compute_entry_quality(action, t0, snapshots)

    # --- Correctness label ---
    if binary_correct is True:
        correctness = "CORRECT"
    elif binary_correct is False:
        correctness = "WRONG"
    else:
        correctness = "MIXED"

    return {
        "forecast_id": record["forecast_id"],
        "event_id": record["event_id"],
        "market_id": predicted_market_id,
        "family_key": record.get("family_key", ""),
        "asset": record.get("asset", ""),
        "market_type": record.get("market_type", ""),
        "is_multi": record.get("is_multi", False),
        "action": action,
        "question": record.get("question", ""),
        "resolved_at": datetime.now(timezone.utc).isoformat(),

        # Prediction snapshot
        "market_prob": market_prob,
        "fair_prob": fair_prob,
        "edge": record.get("edge", 0),
        "edge_pct": record.get("edge_pct", 0),
        "confidence": record.get("confidence", "low"),
        "size_label": record.get("size_label", "NONE"),

        # Resolution
        "resolved_winner": resolved_winner,
        "correctness": correctness,
        "binary_correct": binary_correct,
        "top_pick_correct": top_pick_correct,
        "rank_distance": rank_distance,

        # Metrics
        "brier_score": brier_score,
        "realized_edge": realized_edge,
        "confidence_error": confidence_error,

        # Price Path (trajectory analysis)
        "price_path": price_path,

        # Opportunity & Entry Quality
        "opportunity_captured": opportunity_captured,
        "entry_quality": entry_quality,
    }


def _build_price_path(t0: float, snapshots: list[dict], t_final: float | None) -> dict:
    """Build pricePath from snapshots.

    Returns: {t0, t5m, t15m, t1h, t4h, tFinal, high, low}
    """
    path = {
        "t0": round(t0, 4),
        "tFinal": round(t_final, 4) if t_final is not None else None,
    }

    if not snapshots:
        path["high"] = round(max(t0, t_final or t0), 4)
        path["low"] = round(min(t0, t_final or t0), 4)
        return path

    all_prices = [t0] + [s.get("price", t0) for s in snapshots]
    if t_final is not None:
        all_prices.append(t_final)

    path["high"] = round(max(all_prices), 4)
    path["low"] = round(min(all_prices), 4)

    # Extract time-bucketed snapshots (closest to 5m, 15m, 1h, 4h)
    if snapshots:
        try:
            first_ts = snapshots[0].get("ts", "")
            if first_ts:
                from datetime import datetime as dt
                base_time = dt.fromisoformat(first_ts.replace("Z", "+00:00"))

                targets = {
                    "t5m": 300,
                    "t15m": 900,
                    "t1h": 3600,
                    "t4h": 14400,
                }

                for label, target_secs in targets.items():
                    closest = None
                    closest_diff = float("inf")
                    for s in snapshots:
                        try:
                            s_time = dt.fromisoformat(s["ts"].replace("Z", "+00:00"))
                            diff = abs((s_time - base_time).total_seconds() - target_secs)
                            if diff < closest_diff and diff < target_secs * 0.5:
                                closest_diff = diff
                                closest = s.get("price")
                        except Exception:
                            pass
                    if closest is not None:
                        path[label] = round(closest, 4)
        except Exception:
            pass

    return path


def _compute_opportunity_captured(action: str, t0: float, snapshots: list[dict],
                                  t_final: float | None) -> bool | None:
    """Check if price ever moved in the direction we predicted.

    BUY_YES: price went above entry (market prob increased)
    BUY_NO: price went below entry (market prob decreased)
    """
    if action not in ("BUY_YES", "BUY_NO"):
        return None

    all_prices = [s.get("price", t0) for s in snapshots]
    if t_final is not None:
        all_prices.append(t_final)

    if not all_prices:
        return None

    if action == "BUY_YES":
        # Price needed to go UP from our entry
        return max(all_prices) > t0
    else:
        # BUY_NO: price needed to go DOWN
        return min(all_prices) < t0


def _compute_entry_quality(action: str, t0: float, snapshots: list[dict]) -> float | None:
    """Entry quality = bestPossible - actualEntry.

    For BUY_YES: best entry = lowest price seen → quality = t0 - min(prices)
    For BUY_NO: best entry = highest price seen → quality = max(prices) - t0

    Positive = we entered worse than the best moment
    Zero = perfect entry timing
    """
    if action not in ("BUY_YES", "BUY_NO"):
        return None

    prices = [s.get("price", t0) for s in snapshots]
    if not prices:
        return 0.0

    if action == "BUY_YES":
        best_possible = min(prices)
        return round(t0 - best_possible, 4)
    else:
        best_possible = max(prices)
        return round(best_possible - t0, 4)
