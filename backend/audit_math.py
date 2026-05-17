"""
Mathematical Audit — BTC Prediction Pipeline
Layers: Target, ExpectedMove, Confidence, Distribution, Overfitting
"""
import json
from pymongo import MongoClient, DESCENDING
import os

db = MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "market_core")]

def audit_all():
    results = {}

    # ── LAYER 1: Target calculation ──
    print("=" * 60)
    print("LAYER 1: TARGET CALCULATION")
    print("=" * 60)

    forecasts_7d = list(db["exchange_forecasts"].find(
        {"asset": "BTC", "horizon": "7D"},
        {"_id": 0, "entryPrice": 1, "targetPrice": 1, "expectedMovePct": 1,
         "direction": 1, "confidence": 1, "confidenceRaw": 1, "createdBucket": 1}
    ).sort("createdBucket", DESCENDING).limit(10))

    target_errors = []
    for f in forecasts_7d:
        entry = f.get("entryPrice", 0)
        target = f.get("targetPrice", 0)
        move_pct = f.get("expectedMovePct", 0)
        if entry > 0:
            recalc = entry * (1 + move_pct / 100)
            diff = abs(recalc - target)
            ok = diff < 0.01
            target_errors.append({
                "bucket": f["createdBucket"],
                "entry": entry,
                "move_pct": move_pct,
                "target": target,
                "recalc": round(recalc, 2),
                "diff": round(diff, 4),
                "ok": ok,
            })
            status = "✓" if ok else "✗ BUG"
            print(f"  [{status}] {f['createdBucket']}: entry=${entry:,.0f} move={move_pct:+.2f}% → target=${target:,.0f} (recalc=${recalc:,.0f}, diff={diff:.4f})")

    all_ok = all(e["ok"] for e in target_errors)
    results["target"] = {"pass": all_ok, "errors": [e for e in target_errors if not e["ok"]]}
    print(f"\n  RESULT: {'PASS' if all_ok else 'FAIL'}\n")

    # ── LAYER 2: Expected Move derivation ──
    print("=" * 60)
    print("LAYER 2: EXPECTED MOVE ANALYSIS")
    print("=" * 60)

    move_issues = []
    for f in forecasts_7d:
        move = f.get("expectedMovePct", 0)
        direction = f.get("direction", "NEUTRAL")
        conf = f.get("confidence", 0)

        # Check: direction vs move sign consistency
        sign_ok = True
        if direction == "LONG" and move <= 0:
            sign_ok = False
        elif direction == "SHORT" and move >= 0:
            sign_ok = False

        # Check: extreme moves
        extreme = abs(move) > 20

        # Check: confidence NOT embedded in move (confidence should not multiply move)
        # If move was confidence-adjusted, we'd expect high-confidence → large move correlation
        # We'll check this statistically below

        issue = None
        if not sign_ok:
            issue = f"DIRECTION_SIGN_MISMATCH: {direction} but move={move:+.2f}%"
        elif extreme:
            issue = f"EXTREME_MOVE: {move:+.2f}% (>20%)"

        if issue:
            move_issues.append({"bucket": f["createdBucket"], "issue": issue})

        status = "✓" if not issue else f"✗ {issue}"
        print(f"  [{status}] {f['createdBucket']}: dir={direction} move={move:+.2f}% conf={conf:.2f}")

    # Check confidence-move independence
    moves = [abs(f.get("expectedMovePct", 0)) for f in forecasts_7d]
    confs = [f.get("confidence", 0) for f in forecasts_7d]
    if len(moves) > 2:
        # Simple correlation
        mean_m = sum(moves) / len(moves)
        mean_c = sum(confs) / len(confs)
        cov = sum((m - mean_m) * (c - mean_c) for m, c in zip(moves, confs)) / len(moves)
        std_m = (sum((m - mean_m)**2 for m in moves) / len(moves)) ** 0.5
        std_c = (sum((c - mean_c)**2 for c in confs) / len(confs)) ** 0.5
        corr = cov / (std_m * std_c) if std_m > 0 and std_c > 0 else 0
        conf_in_move = abs(corr) > 0.8
        print(f"\n  Confidence-Move correlation: {corr:.4f} {'⚠ HIGH (confidence may be embedded in move)' if conf_in_move else '✓ Independent'}")
    else:
        corr = 0
        conf_in_move = False

    results["expectedMove"] = {
        "pass": len(move_issues) == 0 and not conf_in_move,
        "issues": move_issues,
        "confMoveCorrelation": round(corr, 4),
        "confEmbeddedInMove": conf_in_move,
    }
    print(f"\n  RESULT: {'PASS' if results['expectedMove']['pass'] else 'FAIL'}\n")

    # ── LAYER 3: Confidence calibration ──
    print("=" * 60)
    print("LAYER 3: CONFIDENCE CALIBRATION")
    print("=" * 60)

    evaluated = list(db["exchange_forecasts"].find(
        {"asset": "BTC", "horizon": "7D", "outcome": {"$ne": None}},
        {"_id": 0, "confidence": 1, "outcome": 1, "direction": 1}
    ).sort("createdBucket", DESCENDING).limit(60))

    if evaluated:
        total = len(evaluated)
        dir_hits = sum(1 for e in evaluated if e.get("outcome", {}).get("directionMatch"))
        tp_hits = sum(1 for e in evaluated if e.get("outcome", {}).get("label") == "TP")
        historical_hit_rate = dir_hits / total if total > 0 else 0
        win_rate = tp_hits / total if total > 0 else 0

        avg_conf = sum(e.get("confidence", 0) for e in evaluated) / total
        max_conf = max(e.get("confidence", 0) for e in evaluated)

        # Check: average confidence should NOT exceed historical hit rate significantly
        conf_exceeds_accuracy = avg_conf > historical_hit_rate * 1.5

        print(f"  Evaluated forecasts: {total}")
        print(f"  Historical directional hit rate: {historical_hit_rate:.2%}")
        print(f"  Historical win rate (TP): {win_rate:.2%}")
        print(f"  Average confidence: {avg_conf:.2%}")
        print(f"  Max confidence: {max_conf:.2%}")
        print(f"  Conf > historical accuracy: {'⚠ YES' if conf_exceeds_accuracy else '✓ NO'}")

        # Calibration buckets: bin by confidence and check hit rate per bin
        bins = {"low": [], "mid": [], "high": []}
        for e in evaluated:
            c = e.get("confidence", 0)
            hit = 1 if e.get("outcome", {}).get("directionMatch") else 0
            if c < 0.3:
                bins["low"].append(hit)
            elif c < 0.5:
                bins["mid"].append(hit)
            else:
                bins["high"].append(hit)

        print(f"\n  Calibration buckets:")
        monotonic = True
        prev_rate = -1
        for bname, bhits in bins.items():
            if bhits:
                rate = sum(bhits) / len(bhits)
                print(f"    {bname} (n={len(bhits)}): hit_rate={rate:.2%}")
                if rate < prev_rate:
                    monotonic = False
                prev_rate = rate
            else:
                print(f"    {bname}: no data")

        print(f"  Monotonic calibration: {'✓ YES' if monotonic else '⚠ NO (higher confidence should have higher hit rate)'}")

        results["confidence"] = {
            "pass": not conf_exceeds_accuracy,
            "historicalHitRate": round(historical_hit_rate, 4),
            "winRate": round(win_rate, 4),
            "avgConfidence": round(avg_conf, 4),
            "confExceedsAccuracy": conf_exceeds_accuracy,
            "monotonicCalibration": monotonic,
            "evaluatedCount": total,
        }
    else:
        print("  No evaluated forecasts found")
        results["confidence"] = {"pass": True, "note": "no evaluated data"}

    print(f"\n  RESULT: {'PASS' if results['confidence']['pass'] else 'FAIL'}\n")

    # ── LAYER 4: Distribution vs Direction consistency ──
    print("=" * 60)
    print("LAYER 4: DISTRIBUTION vs DIRECTION CONSISTENCY")
    print("=" * 60)

    # Current forecast
    latest = forecasts_7d[0] if forecasts_7d else None
    if latest and evaluated:
        direction = latest.get("direction", "NEUTRAL")
        move = latest.get("expectedMovePct", 0)
        conf = latest.get("confidence", 0)

        # Count historical direction distribution
        up_count = sum(1 for f in forecasts_7d if f.get("direction") in ("LONG", "UP"))
        down_count = sum(1 for f in forecasts_7d if f.get("direction") in ("SHORT", "DOWN"))
        neutral_count = sum(1 for f in forecasts_7d if f.get("direction") == "NEUTRAL")

        # Distribution from evaluated forecasts (targets)
        up_eval = sum(1 for e in evaluated if (e.get("outcome", {}).get("directionMatch", False) and e.get("direction") in ("LONG", "UP")))
        total_eval = len(evaluated)

        # Use risk profile from graph3 calculation
        up_targets = 0
        down_targets = 0
        neutral_targets = 0
        for d in evaluated:
            entry_p = d.get("entryPrice") or d.get("basePrice", 0)
            target_p = d.get("targetPrice", entry_p) if "targetPrice" in d else entry_p
            # get from full forecast
            full = db["exchange_forecasts"].find_one(
                {"createdBucket": d.get("createdBucket"), "asset": "BTC", "horizon": "7D"},
                {"_id": 0, "entryPrice": 1, "targetPrice": 1}
            )
            if full:
                entry_p = full.get("entryPrice", 0)
                target_p = full.get("targetPrice", entry_p)
            if entry_p > 0:
                m = (target_p - entry_p) / entry_p
                if m > 0.01:
                    up_targets += 1
                elif m < -0.01:
                    down_targets += 1
                else:
                    neutral_targets += 1

        total_targets = up_targets + down_targets + neutral_targets
        upside_pct = up_targets / total_targets if total_targets > 0 else 0
        downside_pct = down_targets / total_targets if total_targets > 0 else 0

        print(f"  Current forecast: dir={direction} move={move:+.2f}% conf={conf:.2%}")
        print(f"  Historical target distribution: upside={upside_pct:.0%} downside={downside_pct:.0%}")

        inconsistent = False
        reason = None
        if direction == "LONG" and downside_pct > upside_pct:
            if conf >= 0.5:
                inconsistent = True
                reason = "LONG with downside>upside AND high confidence"
            else:
                reason = f"LONG with downside>upside but low confidence ({conf:.0%}) — acceptable"
            print(f"  ⚠ Direction=LONG but historical downside({downside_pct:.0%}) > upside({upside_pct:.0%})")
            print(f"    → {reason}")
        elif direction == "SHORT" and upside_pct > downside_pct:
            if conf >= 0.5:
                inconsistent = True
                reason = "SHORT with upside>downside AND high confidence"
            else:
                reason = f"SHORT with upside>downside but low confidence ({conf:.0%}) — acceptable"
            print(f"  ⚠ {reason}")
        else:
            print(f"  ✓ Distribution aligns with direction")

        # Check extreme moves
        if abs(move) > 20:
            print(f"  ✗ EXTREME MOVE: {move:+.2f}% > 20%")
            inconsistent = True

        results["distribution"] = {
            "pass": not inconsistent,
            "currentDirection": direction,
            "currentMove": move,
            "currentConfidence": conf,
            "historicalUpside": round(upside_pct, 4),
            "historicalDownside": round(downside_pct, 4),
            "inconsistency": reason,
        }
    else:
        results["distribution"] = {"pass": True, "note": "insufficient data"}

    print(f"\n  RESULT: {'PASS' if results['distribution']['pass'] else 'FAIL'}\n")

    # ── LAYER 5: Overfitting sanity check ──
    print("=" * 60)
    print("LAYER 5: OVERFITTING SANITY CHECK")
    print("=" * 60)

    if evaluated:
        # Baseline: historical mean return
        from forecast.price_provider import get_price_series
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=180)).strftime("%Y-%m-%d")
        end = now.strftime("%Y-%m-%d")
        prices = get_price_series("BTC", start, end)
        sorted_dates = sorted(prices.keys())

        if len(sorted_dates) > 14:
            returns_7d = []
            for i in range(7, len(sorted_dates)):
                p_now = prices[sorted_dates[i]]
                p_prev = prices[sorted_dates[i - 7]]
                if p_prev > 0:
                    returns_7d.append((p_now - p_prev) / p_prev)

            baseline_mean = sum(returns_7d) / len(returns_7d) if returns_7d else 0
            baseline_abs_mean = sum(abs(r) for r in returns_7d) / len(returns_7d) if returns_7d else 0

            model_moves = [abs(f.get("expectedMovePct", 0)) / 100 for f in forecasts_7d]
            model_avg = sum(model_moves) / len(model_moves) if model_moves else 0

            ratio = model_avg / baseline_abs_mean if baseline_abs_mean > 0 else 0
            overfitting = ratio > 3 and results["confidence"].get("winRate", 0) < 0.4

            print(f"  Baseline 7D abs mean return: {baseline_abs_mean:.4%}")
            print(f"  Model avg abs move: {model_avg:.4%}")
            print(f"  Ratio (model/baseline): {ratio:.2f}x")
            print(f"  Win rate: {results['confidence'].get('winRate', 0):.2%}")
            print(f"  Overfitting signal: {'⚠ YES' if overfitting else '✓ NO'}")

            results["overfitting"] = {
                "pass": not overfitting,
                "baselineAbsMeanReturn": round(baseline_abs_mean, 6),
                "modelAvgAbsMove": round(model_avg, 6),
                "ratio": round(ratio, 2),
                "overfitting": overfitting,
            }
        else:
            print("  Not enough price data for baseline")
            results["overfitting"] = {"pass": True, "note": "insufficient price data"}
    else:
        results["overfitting"] = {"pass": True, "note": "no evaluated data"}

    print(f"\n  RESULT: {'PASS' if results['overfitting']['pass'] else 'FAIL'}\n")

    # ── SUMMARY ──
    print("=" * 60)
    print("AUDIT SUMMARY")
    print("=" * 60)
    for layer, res in results.items():
        status = "✓ PASS" if res.get("pass") else "✗ FAIL"
        print(f"  {layer}: {status}")

    all_pass = all(r.get("pass") for r in results.values())
    print(f"\n  OVERALL: {'✓ ALL PASS' if all_pass else '✗ ISSUES FOUND'}")

    return results


if __name__ == "__main__":
    r = audit_all()
    with open("/tmp/audit_results.json", "w") as f:
        json.dump(r, f, indent=2)
    print(f"\nFull results saved to /tmp/audit_results.json")
