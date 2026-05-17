"""
Accuracy Audit — Real performance metrics
==========================================
Separates directional (BUY/SELL) from risk management (WAIT/AVOID).
Provides breakdowns by type, horizon, asset + catastrophic rate.
"""


async def run_accuracy_audit(db) -> dict:
    """Run full accuracy audit on decision_history."""

    evaluated = await db.decision_history.find(
        {"status": "evaluated"}, {"_id": 0}
    ).to_list(length=5000)

    if not evaluated:
        return _empty_audit()

    directional = []
    risk_mgmt = []

    for d in evaluated:
        action = d.get("decision", "WAIT")
        if action in ("BUY", "SELL"):
            directional.append(d)
        else:
            risk_mgmt.append(d)

    # --- Overall ---
    dir_correct = sum(1 for d in directional if d.get("result") == "correct")
    dir_total = len(directional)
    dir_accuracy = round(dir_correct / dir_total, 3) if dir_total > 0 else 0.0

    coverage = round(dir_total / len(evaluated), 3) if evaluated else 0.0

    # Risk accuracy: WAIT is "correct" if result is neutral, AVOID similar
    risk_correct = sum(1 for d in risk_mgmt if d.get("result") in ("neutral", "correct"))
    risk_total = len(risk_mgmt)
    risk_accuracy = round(risk_correct / risk_total, 3) if risk_total > 0 else 0.0

    # Catastrophic: BUY and price went down >5%, or SELL and price went up >5%
    catastrophic_count = sum(1 for d in evaluated if d.get("catastrophic") is True)
    catastrophic_rate = round(catastrophic_count / len(evaluated), 3) if evaluated else 0.0
    dir_catastrophic = sum(1 for d in directional if d.get("catastrophic") is True)
    dir_catastrophic_rate = round(dir_catastrophic / dir_total, 3) if dir_total > 0 else 0.0

    # --- By Decision Type ---
    by_type = _breakdown(directional, "decisionType")

    # --- By Horizon ---
    by_horizon = _breakdown(directional, "horizon")

    # --- By Asset ---
    by_asset = _breakdown(directional, "asset")

    # --- By Decision Action ---
    by_action = _breakdown(directional, "decision")

    # --- Raw counts for debugging ---
    result_counts = {}
    for d in evaluated:
        key = f"{d.get('decision', '?')}/{d.get('result', '?')}"
        result_counts[key] = result_counts.get(key, 0) + 1

    return {
        "totalEvaluated": len(evaluated),
        "overall": {
            "directionalAccuracy": dir_accuracy,
            "directionalTotal": dir_total,
            "directionalCorrect": dir_correct,
            "coverage": coverage,
            "riskAccuracy": risk_accuracy,
            "riskTotal": risk_total,
            "catastrophicRate": catastrophic_rate,
            "directionalCatastrophicRate": dir_catastrophic_rate,
        },
        "byType": by_type,
        "byHorizon": by_horizon,
        "byAsset": by_asset,
        "byAction": by_action,
        "resultDistribution": result_counts,
        "insight": _generate_insight(dir_accuracy, coverage, risk_accuracy, catastrophic_rate, by_type),
    }


def _breakdown(decisions: list, field: str) -> dict:
    """Calculate accuracy breakdown by a given field."""
    groups = {}
    for d in decisions:
        key = d.get(field, "UNKNOWN")
        if key not in groups:
            groups[key] = {"correct": 0, "wrong": 0, "total": 0}
        groups[key]["total"] += 1
        if d.get("result") == "correct":
            groups[key]["correct"] += 1
        elif d.get("result") == "wrong":
            groups[key]["wrong"] += 1

    result = {}
    for key, g in groups.items():
        result[key] = {
            "accuracy": round(g["correct"] / g["total"], 3) if g["total"] > 0 else 0.0,
            "correct": g["correct"],
            "wrong": g["wrong"],
            "total": g["total"],
        }

    return result


def _generate_insight(dir_acc, coverage, risk_acc, cat_rate, by_type) -> str:
    """Generate human-readable audit insight."""
    parts = []

    if dir_acc >= 0.7:
        parts.append(f"Directional accuracy strong at {int(dir_acc*100)}%")
    elif dir_acc >= 0.5:
        parts.append(f"Directional accuracy moderate at {int(dir_acc*100)}%")
    else:
        parts.append(f"Directional accuracy weak at {int(dir_acc*100)}%")

    if coverage < 0.2:
        parts.append(f"System very conservative — only {int(coverage*100)}% directional coverage")
    elif coverage < 0.5:
        parts.append(f"Balanced coverage at {int(coverage*100)}%")

    if risk_acc >= 0.8:
        parts.append("Risk management effective")
    elif risk_acc < 0.5:
        parts.append("Risk management needs improvement")

    if cat_rate > 0.1:
        parts.append(f"Catastrophic rate elevated at {int(cat_rate*100)}%")
    elif cat_rate < 0.05:
        parts.append("Catastrophic rate low")

    hc = by_type.get("HIGH_CONVICTION", {})
    if hc.get("total", 0) >= 5:
        parts.append(f"HIGH_CONVICTION: {int(hc['accuracy']*100)}% ({hc['total']} decisions)")

    ext = by_type.get("EXTREME", {})
    if ext.get("total", 0) >= 1:
        parts.append(f"EXTREME: {int(ext['accuracy']*100)}% ({ext['total']} decisions)")

    return ". ".join(parts)


def _empty_audit():
    return {
        "totalEvaluated": 0,
        "overall": {
            "directionalAccuracy": 0.0,
            "directionalTotal": 0,
            "directionalCorrect": 0,
            "coverage": 0.0,
            "riskAccuracy": 0.0,
            "riskTotal": 0,
            "catastrophicRate": 0.0,
            "directionalCatastrophicRate": 0.0,
        },
        "byType": {},
        "byHorizon": {},
        "byAsset": {},
        "byAction": {},
        "resultDistribution": {},
        "insight": "No evaluated decisions yet",
    }
