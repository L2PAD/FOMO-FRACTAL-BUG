"""
Historical Replay Engine (BLOCK 7)
====================================
Runs the System Aggregator on historical evaluated forecasts
to compare Aggregator V1 vs Decision V2 (or V1 decision).

Answers:
  1. Is Aggregator better than raw Decision?
  2. Does FP grow?
  3. Do sentiment/fractals actually help?
  4. Is confidence calibrated?
"""

from forecast.system.aggregator import AggregatorInputs, compute_aggregated_signal


def _classify_outcome(direction: str, actual_return: float) -> str:
    """Classify a forecast as TP, FP, or NEUTRAL."""
    if direction in ("LONG", "SHORT"):
        if (direction == "LONG" and actual_return > 0) or \
           (direction == "SHORT" and actual_return < 0):
            return "TP"
        return "FP"
    return "NEUTRAL"


def _compute_metrics(results: list, dir_key: str, conf_key: str) -> dict:
    """Compute standard metrics for a set of results."""
    tp = fp = neutral = 0
    conf_sum = 0.0
    conf_buckets = {"high": {"tp": 0, "fp": 0}, "mid": {"tp": 0, "fp": 0}, "low": {"tp": 0, "fp": 0}}

    for r in results:
        direction = r[dir_key]
        confidence = r.get(conf_key, 0) or 0
        actual_return = r["actual_return"]
        outcome = _classify_outcome(direction, actual_return)

        if outcome == "TP":
            tp += 1
        elif outcome == "FP":
            fp += 1
        else:
            neutral += 1

        conf_sum += confidence

        # Bucket
        if confidence >= 0.7:
            bk = "high"
        elif confidence >= 0.4:
            bk = "mid"
        else:
            bk = "low"

        if outcome in ("TP", "FP"):
            conf_buckets[bk][outcome.lower()] += 1

    directional = tp + fp
    accuracy = round(tp / max(directional, 1), 4)
    fp_rate = round(fp / max(directional, 1), 4)
    directional_share = round(directional / max(len(results), 1), 4)
    avg_conf = round(conf_sum / max(len(results), 1), 4)

    # Per-bucket accuracy
    bucket_accuracy = {}
    for bk, counts in conf_buckets.items():
        dt = counts["tp"] + counts["fp"]
        bucket_accuracy[bk] = {
            "accuracy": round(counts["tp"] / max(dt, 1), 4),
            "count": dt,
        }

    return {
        "accuracy": accuracy,
        "fp_rate": fp_rate,
        "tp": tp,
        "fp": fp,
        "neutral": neutral,
        "directional": directional,
        "directional_share": directional_share,
        "avg_confidence": avg_conf,
        "confidence_buckets": bucket_accuracy,
    }


def run_replay(db, horizon_filter: str = "7D", limit: int = 500) -> dict:
    """
    Main replay function.
    Fetches historical evaluated forecasts, runs aggregator on each,
    and compares with original decision.
    """
    from forecast.system.sentiment_adapter import fetch_sentiment_for_asset
    from forecast.system.fractal_adapter import fetch_fractal_signal

    col = db["exchange_forecasts"]

    query = {
        "evaluated": True,
        "audit.scoreFinal": {"$exists": True},
        "outcome.realMovePct": {"$exists": True},
    }
    if horizon_filter:
        query["horizon"] = horizon_filter

    docs = list(col.find(
        query,
        {"_id": 0, "symbol": 1, "horizon": 1, "direction": 1, "confidence": 1,
         "audit.scoreFinal": 1, "audit.regime": 1, "audit.exchange_signal": 1,
         "audit.interaction": 1, "audit.decision_v2": 1, "audit.forecast_v2": 1,
         "outcome.realMovePct": 1, "outcome.label": 1},
    ).sort("createdAt", -1).limit(limit))

    if not docs:
        return {"ok": True, "error": "NO_DATA", "total": 0}

    # Pre-fetch sentiment and fractal for unique assets
    asset_cache = {}
    for d in docs:
        sym = d.get("symbol", "")
        asset = sym.replace("USDT", "") if sym.endswith("USDT") else sym
        if asset and asset not in asset_cache:
            asset_cache[asset] = {
                "sentiment": fetch_sentiment_for_asset(db, asset),
                "fractal": fetch_fractal_signal(db, asset),
            }

    results = []
    for d in docs:
        sym = d.get("symbol", "")
        asset = sym.replace("USDT", "") if sym.endswith("USDT") else sym
        audit = d.get("audit", {})
        outcome = d.get("outcome", {})

        score_final = audit.get("scoreFinal", 0) or 0
        regime = audit.get("regime", "RANGE") or "RANGE"

        # Exchange bias: try audit, fallback to 0
        ex_sig = audit.get("exchange_signal", {}) or {}
        micro_bias = ex_sig.get("micro_bias", 0) or 0

        # Interaction conflict
        interaction = audit.get("interaction", {}) or {}
        conflict = interaction.get("conflict_score", 0) or 0

        # Sentiment + Fractal from cache
        cached = asset_cache.get(asset, {})
        sent = cached.get("sentiment", {"score": 0, "confidence": 0})
        frac = cached.get("fractal", {"signal": 0, "confidence": 0})

        # Run aggregator
        agg_input = AggregatorInputs(
            forecast_score=score_final,
            exchange_bias=micro_bias,
            sentiment_score=sent["score"],
            sentiment_confidence=sent["confidence"],
            fractal_signal=frac["signal"],
            fractal_confidence=frac["confidence"],
            regime=regime,
            conflict_score=conflict,
            horizon=d.get("horizon", "24H"),
        )
        agg_output = compute_aggregated_signal(agg_input)

        # Decision V2 if available, otherwise use original direction/confidence
        dv2 = audit.get("decision_v2", {}) or {}
        decision_dir = dv2.get("direction") or d.get("direction", "NEUTRAL")
        decision_conf = dv2.get("confidence") or d.get("confidence", 0) or 0

        actual_return = outcome.get("realMovePct", 0) or 0

        results.append({
            "symbol": sym,
            "horizon": d.get("horizon"),
            "decision_direction": decision_dir,
            "decision_confidence": decision_conf,
            "agg_direction": agg_output.direction,
            "agg_confidence": agg_output.confidence,
            "agg_score": agg_output.final_score,
            "actual_return": actual_return,
            "components": agg_output.components,
        })

    # Compute comparison metrics
    decision_metrics = _compute_metrics(results, "decision_direction", "decision_confidence")
    agg_metrics = _compute_metrics(results, "agg_direction", "agg_confidence")

    # Agreement rate
    agreements = sum(1 for r in results if r["decision_direction"] == r["agg_direction"])
    agreement_pct = round(agreements / max(len(results), 1), 4)

    # Reversal capture
    reversal_decision = {"attempts": 0, "success": 0}
    reversal_agg = {"attempts": 0, "success": 0}
    for i, r in enumerate(results):
        if i == 0:
            continue
        prev = results[i - 1]
        prev_return = prev["actual_return"]
        curr_return = r["actual_return"]

        # Reversal = sign flip between consecutive periods
        if prev_return != 0 and curr_return != 0:
            if (prev_return > 0) != (curr_return > 0):
                # Decision
                if r["decision_direction"] in ("LONG", "SHORT"):
                    reversal_decision["attempts"] += 1
                    outcome = _classify_outcome(r["decision_direction"], curr_return)
                    if outcome == "TP":
                        reversal_decision["success"] += 1
                # Aggregator
                if r["agg_direction"] in ("LONG", "SHORT"):
                    reversal_agg["attempts"] += 1
                    outcome = _classify_outcome(r["agg_direction"], curr_return)
                    if outcome == "TP":
                        reversal_agg["success"] += 1

    for rev in (reversal_decision, reversal_agg):
        rev["rate"] = round(rev["success"] / max(rev["attempts"], 1), 4)

    # Component influence analysis
    component_impact = {"sentiment_helped": 0, "sentiment_hurt": 0,
                        "fractal_helped": 0, "fractal_hurt": 0}
    for r in results:
        actual = r["actual_return"]
        if r["agg_direction"] == "NEUTRAL":
            continue
        is_correct = _classify_outcome(r["agg_direction"], actual) == "TP"
        comp = r["components"]

        # Did sentiment push in the right direction?
        if comp.get("sentiment", 0) != 0:
            sent_aligned = (comp["sentiment"] > 0 and actual > 0) or (comp["sentiment"] < 0 and actual < 0)
            if sent_aligned:
                component_impact["sentiment_helped"] += 1
            else:
                component_impact["sentiment_hurt"] += 1

        if comp.get("fractal", 0) != 0:
            frac_aligned = (comp["fractal"] > 0 and actual > 0) or (comp["fractal"] < 0 and actual < 0)
            if frac_aligned:
                component_impact["fractal_helped"] += 1
            else:
                component_impact["fractal_hurt"] += 1

    return {
        "ok": True,
        "total": len(results),
        "horizon": horizon_filter,
        "decision_v2": decision_metrics,
        "aggregator_v1": agg_metrics,
        "agreement_pct": agreement_pct,
        "reversal": {
            "decision": reversal_decision,
            "aggregator": reversal_agg,
        },
        "component_impact": component_impact,
    }
