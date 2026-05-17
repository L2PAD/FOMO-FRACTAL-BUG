"""
Auto Validation Engine (BLOCK 8)
==================================
Binary verdict: PASS / WARNING / FAIL
Based on backtest metrics comparison between Decision V2 and Aggregator V1.
"""


def validate_backtest(backtest: dict) -> dict:
    """
    Validate backtest results and produce a verdict.

    Rules:
      PASS: aggregator accuracy >= decision AND FP not worse by >5pp AND accuracy >= 0.45
      WARNING: minor degradation or marginal results
      FAIL: aggregator is worse than decision
    """
    if backtest.get("error") == "NO_DATA" or backtest.get("total", 0) < 10:
        return {
            "verdict": "INSUFFICIENT_DATA",
            "reasons": [f"Only {backtest.get('total', 0)} samples (need >= 10)"],
            "recommendation": "Wait for more data or expand horizon filter",
        }

    v1 = backtest["decision_v2"]
    v2 = backtest["aggregator_v1"]

    verdict = "PASS"
    reasons = []

    # 1. Accuracy comparison
    accuracy_delta = v2["accuracy"] - v1["accuracy"]
    if accuracy_delta < -0.05:
        verdict = "FAIL"
        reasons.append(f"accuracy drop: {accuracy_delta:+.4f} (aggregator={v2['accuracy']:.4f} vs decision={v1['accuracy']:.4f})")
    elif accuracy_delta < 0:
        if verdict != "FAIL":
            verdict = "WARNING"
        reasons.append(f"marginal accuracy drop: {accuracy_delta:+.4f}")

    # 2. FP guard
    fp_delta = v2["fp_rate"] - v1["fp_rate"]
    if fp_delta > 0.05:
        verdict = "FAIL"
        reasons.append(f"FP increased by {fp_delta:+.4f} (aggregator={v2['fp_rate']:.4f} vs decision={v1['fp_rate']:.4f})")
    elif fp_delta > 0.02:
        if verdict != "FAIL":
            verdict = "WARNING"
        reasons.append(f"FP slightly increased: {fp_delta:+.4f}")

    # 3. Directional sanity
    if v2["directional_share"] > 0.85:
        if verdict != "FAIL":
            verdict = "WARNING"
        reasons.append(f"too many signals: directional_share={v2['directional_share']:.4f}")

    # 4. Minimum baseline
    if v2["accuracy"] < 0.45:
        if verdict != "FAIL":
            verdict = "WARNING"
        reasons.append(f"below 45% baseline: accuracy={v2['accuracy']:.4f}")

    # 5. Confidence calibration check
    buckets = v2.get("confidence_buckets", {})
    high_acc = buckets.get("high", {}).get("accuracy", 0)
    low_acc = buckets.get("low", {}).get("accuracy", 0)
    if buckets.get("high", {}).get("count", 0) >= 5 and \
       buckets.get("low", {}).get("count", 0) >= 5:
        if high_acc <= low_acc:
            if verdict != "FAIL":
                verdict = "WARNING"
            reasons.append(f"confidence not calibrated: high_acc={high_acc:.4f} <= low_acc={low_acc:.4f}")

    # Recommendation
    if verdict == "PASS":
        recommendation = "Safe to promote Aggregator to 10% live"
    elif verdict == "WARNING":
        recommendation = "Can promote to 10% with tight monitoring. Check confidence calibration."
    else:
        recommendation = "Do NOT promote. Run Aggregator Optimization first."

    return {
        "verdict": verdict,
        "reasons": reasons,
        "metrics_summary": {
            "accuracy_delta": round(accuracy_delta, 4),
            "fp_delta": round(fp_delta, 4),
            "agg_accuracy": v2["accuracy"],
            "decision_accuracy": v1["accuracy"],
            "agg_directional_share": v2["directional_share"],
        },
        "recommendation": recommendation,
    }
