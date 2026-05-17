"""
Engine Probability Service — E5.7
==================================
Calculates trade probabilities:
  - continuation: how likely the current setup continues
  - failure: how likely the setup breaks
  - upgrade: how likely NEUTRAL becomes BUY/SELL

Rule-based weighted model, no ML.
"""


def _clamp01(v):
    return max(0.0, min(1.0, v))


# Regime-Setup alignment: how natural is this setup in this regime?
_ALIGNMENT = {
    ("accumulation", "liquidity_shock"): 0.85,
    ("accumulation", "smart_money_accumulation"): 0.90,
    ("accumulation", "exchange_drain"): 0.80,
    ("bull_trend", "liquidity_shock"): 0.80,
    ("bull_trend", "smart_money_accumulation"): 0.75,
    ("distribution", "distribution_risk"): 0.85,
    ("bear_trend", "distribution_risk"): 0.80,
    ("rotation", "rotation"): 0.75,
}


def _regime_alignment(regime_type: str, setup_type: str) -> float:
    return _ALIGNMENT.get((regime_type, setup_type), 0.40)


def calculate_probabilities(
    decision: str,
    composite: int,
    confidence_score: int,
    regime: dict,
    setup: dict,
    gates: dict,
    explanation: dict,
) -> dict:
    """
    Calculate continuation, failure, and upgrade probabilities.
    """
    regime_type = regime.get("primary", {}).get("type", "neutral_chop")
    regime_conf = regime.get("primary", {}).get("confidence", 0.30)
    setup_type = setup.get("primary", {}).get("type", "mixed")
    setup_conf = setup.get("primary", {}).get("confidence", 0.30)

    alignment = _regime_alignment(regime_type, setup_type)

    evidence = gates.get("evidence", {}).get("status", "PASS")
    evidence_val = {"PASS": 0.80, "WEAK": 0.40, "FAIL": 0.15}.get(evidence, 0.50)

    risk = gates.get("risk", {}).get("status", "LOW")
    risk_val = {"LOW": 0.10, "MEDIUM": 0.30, "HIGH": 0.55}.get(risk, 0.30)

    coverage = gates.get("coverage", {}).get("status", "FULL")
    coverage_val = {"FULL": 0.85, "PARTIAL": 0.55, "LOW": 0.25}.get(coverage, 0.50)

    contradictions = len(explanation.get("bearish_or_contradictions", []))
    blockers = len(explanation.get("decision_blockers", []))
    triggers = len(explanation.get("upgrade_triggers", []))

    # ── Continuation Probability ──
    continuation = _clamp01(
        0.25 * alignment
        + 0.25 * setup_conf
        + 0.15 * regime_conf
        + 0.15 * evidence_val
        + 0.10 * coverage_val
        - 0.05 * min(contradictions, 4) * 0.25
        - 0.05 * risk_val
    )

    # ── Failure Probability ──
    failure = _clamp01(
        0.30 * (contradictions / max(contradictions + 1, 1))
        + 0.25 * risk_val
        + 0.20 * (1.0 - setup_conf)
        + 0.15 * (1.0 - alignment)
        + 0.10 * (1.0 - evidence_val)
    )

    # Normalize so continuation + failure roughly sums near 1
    total = continuation + failure
    if total > 0:
        continuation = round(continuation / total, 3)
        failure = round(failure / total, 3)

    # ── Upgrade Probability ──
    if decision == "NEUTRAL":
        # How close to BUY or SELL?
        if composite >= 50:
            distance = (65 - composite) / 25.0  # distance to BUY threshold
        else:
            distance = (composite - 40) / 25.0  # distance to SELL threshold
        distance = max(0, min(1, distance))

        trigger_readiness = min(triggers, 5) / 5.0 * 0.3
        evidence_boost = evidence_val * 0.25
        blocker_drag = min(blockers, 4) / 4.0 * 0.25

        upgrade = _clamp01(
            (1.0 - distance) * 0.40
            + trigger_readiness
            + evidence_boost
            - blocker_drag
        )
    elif decision in ("BUY", "SELL"):
        upgrade = 0.0  # already there
    else:
        upgrade = 0.15

    upgrade = round(upgrade, 3)

    # ── Summary ──
    if continuation >= 0.65:
        tone = "Strong continuation odds"
    elif continuation >= 0.50:
        tone = "Moderate continuation odds"
    else:
        tone = "Weak continuation odds"

    if decision == "NEUTRAL" and upgrade >= 0.45:
        upgrade_text = f"with elevated upgrade probability ({int(upgrade*100)}%)"
    elif decision == "NEUTRAL":
        upgrade_text = "upgrade still requires confirmation"
    else:
        upgrade_text = ""

    summary_parts = [tone]
    if setup_type != "mixed":
        summary_parts.append(f"for {setup_type.replace('_', ' ')} setup")
    if upgrade_text:
        summary_parts.append(upgrade_text)

    summary = ", ".join(summary_parts) + "."

    return {
        "continuation": round(continuation, 3),
        "failure": round(failure, 3),
        "upgrade": upgrade,
        "summary": summary,
    }
