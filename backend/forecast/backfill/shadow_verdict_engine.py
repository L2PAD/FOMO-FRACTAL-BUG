"""
Shadow Verdict Engine
======================
Automatic decision engine based on the rulebook.

PROMOTE (Level 2 → Level 3):
  - accuracy_lift_pp >= 3
  - neutral_ratio_structure <= neutral_ratio_base
  - hurt_rate < 0.35
  - no excessive STRONG growth
  - no flip noise

HOLD (keep Level 2):
  - accuracy_lift_pp in [-1, +3]
  - neutral not worse
  - structure mostly changes strength, not sign

ROLLBACK:
  - accuracy_lift_pp <= -2
  - OR hurt > improved
  - OR excessive false STRONG
  - OR sign-flip noise
"""


def build_verdict(kpis: dict) -> dict:
    """
    Build automatic verdict from aggregated KPIs.
    Returns verdict + reasoning.
    """
    n = kpis.get("n", 0)
    if n < 10:
        return {
            "verdict": "INSUFFICIENT_DATA",
            "confidence": "low",
            "reasons": [f"Only {n} cases, need at least 10"],
            "recommendation": "Continue collecting shadow data",
        }

    lift = kpis["comparison"]["accuracy_lift_pp"]
    hurt_rate = kpis["comparison"]["hurt_rate"]
    cases = kpis["comparison"]["case_types"]
    sign_changed = kpis["comparison"]["sign_changed"]

    base_neutral = kpis["base"]["distribution"]["neutral_ratio"]
    struct_neutral = kpis["structure"]["distribution"]["neutral_ratio"]
    base_strong = kpis["base"]["distribution"]["strong_ratio"]
    struct_strong = kpis["structure"]["distribution"]["strong_ratio"]

    # Check conditions
    neutral_improved = struct_neutral <= base_neutral
    strong_excessive = struct_strong > base_strong + 0.15
    flip_noise = sign_changed > n * 0.25

    hurt_count = cases.get("structure_hurt", 0)
    improved_count = cases.get("structure_improved", 0)

    reasons = []

    # ── PROMOTE check ──
    promote_conditions = [
        lift >= 3.0,
        neutral_improved,
        hurt_rate < 0.35,
        not strong_excessive,
        not flip_noise,
    ]
    if all(promote_conditions):
        reasons.append(f"accuracy_lift={lift:+.1f}pp (>=3)")
        if neutral_improved:
            reasons.append(f"neutral improved: {base_neutral:.0%} → {struct_neutral:.0%}")
        reasons.append(f"hurt_rate={hurt_rate:.0%} (<35%)")
        return {
            "verdict": "PROMOTE",
            "confidence": "high" if n >= 30 else "medium",
            "reasons": reasons,
            "recommendation": "Safe to increase weights to Level 3",
        }

    # ── ROLLBACK check ──
    rollback_conditions = [
        lift <= -2.0,
        hurt_count > improved_count and (hurt_count + improved_count) >= 5,
        strong_excessive,
        flip_noise,
    ]
    if any(rollback_conditions):
        if lift <= -2.0:
            reasons.append(f"accuracy_lift={lift:+.1f}pp (<=-2)")
        if hurt_count > improved_count:
            reasons.append(f"hurt({hurt_count}) > improved({improved_count})")
        if strong_excessive:
            reasons.append(f"STRONG growth excessive: {base_strong:.0%} → {struct_strong:.0%}")
        if flip_noise:
            reasons.append(f"sign_flips={sign_changed}/{n} (>{25}%)")
        return {
            "verdict": "ROLLBACK",
            "confidence": "high" if n >= 30 else "medium",
            "reasons": reasons,
            "recommendation": "Reduce weights or fix specific pattern traps",
        }

    # ── HOLD (default) ──
    reasons.append(f"accuracy_lift={lift:+.1f}pp (between -1 and +3)")
    if neutral_improved:
        reasons.append(f"neutral improved: {base_neutral:.0%} → {struct_neutral:.0%}")
    else:
        reasons.append(f"neutral unchanged/worse: {base_neutral:.0%} → {struct_neutral:.0%}")

    strength_only = kpis["comparison"]["strength_only_changed"]
    if strength_only > 0:
        reasons.append(f"strength_only_changes={strength_only} (mostly modifying intensity)")

    return {
        "verdict": "HOLD",
        "confidence": "medium" if n >= 20 else "low",
        "reasons": reasons,
        "recommendation": "Keep current weights, continue monitoring",
    }
