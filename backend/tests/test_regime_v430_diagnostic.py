"""
Regime Engine V2 Diagnostic
=============================
Tests probability distribution across various market conditions.
Validates that all 5 regimes can be activated as dominant.
"""
import sys
sys.path.insert(0, "/app/backend")

from forecast.regime.regime_probability_engine import compute_regime_probabilities, _TEMPERATURE
from forecast.regime.regime_postprocessor import postprocess_regime
from forecast.regime.regime_feature_builder import build_regime_features

# ── Synthetic feature sets for each expected regime ──

SCENARIOS = {
    "strong_trend": {
        "trend_strength": 0.85,
        "trend_persistence": 0.80,
        "exhaustion": 0.10,
        "reversal_risk": 0.10,
        "drawdown_pressure": 0.05,
        "structure_alignment": 0.90,
        "volatility_expansion": 0.40,
    },
    "range_bound": {
        "trend_strength": 0.15,
        "trend_persistence": 0.20,
        "exhaustion": 0.10,
        "reversal_risk": 0.15,
        "drawdown_pressure": 0.10,
        "structure_alignment": 0.25,
        "volatility_expansion": 0.20,
    },
    "pullback_in_trend": {
        "trend_strength": 0.60,
        "trend_persistence": 0.55,
        "exhaustion": 0.15,
        "reversal_risk": 0.45,
        "drawdown_pressure": 0.15,
        "structure_alignment": 0.35,
        "volatility_expansion": 0.30,
    },
    "transition_unstable": {
        "trend_strength": 0.30,
        "trend_persistence": 0.25,
        "exhaustion": 0.55,
        "reversal_risk": 0.65,
        "drawdown_pressure": 0.30,
        "structure_alignment": 0.20,
        "volatility_expansion": 0.60,
    },
    "breakdown_stress": {
        "trend_strength": 0.20,
        "trend_persistence": 0.25,
        "exhaustion": 0.50,
        "reversal_risk": 0.55,
        "drawdown_pressure": 0.85,
        "structure_alignment": 0.15,
        "volatility_expansion": 0.75,
    },
    "neutral_mixed": {
        "trend_strength": 0.40,
        "trend_persistence": 0.45,
        "exhaustion": 0.30,
        "reversal_risk": 0.30,
        "drawdown_pressure": 0.25,
        "structure_alignment": 0.50,
        "volatility_expansion": 0.40,
    },
}

# Match scenario to expected context phase
SCENARIO_PHASES = {
    "strong_trend": "continuation",
    "range_bound": "mixed_range",
    "pullback_in_trend": "pullback",
    "transition_unstable": "unstable_transition",
    "breakdown_stress": "breakdown",
    "neutral_mixed": "mixed_range",
}

EXPECTED_DOMINANT = {
    "strong_trend": "trend",
    "range_bound": "range",
    "pullback_in_trend": "pullback",
    "transition_unstable": "transition",
    "breakdown_stress": "breakdown",
    "neutral_mixed": None,  # any is ok
}

def run_diagnostic():
    print(f"=== Regime Engine V2 Diagnostic ===")
    print(f"Temperature: {_TEMPERATURE}")
    print()

    regime_activation_count = {r: 0 for r in ["trend", "range", "pullback", "transition", "breakdown"]}
    issues = []

    for name, features in SCENARIOS.items():
        phase = SCENARIO_PHASES[name]
        probs = compute_regime_probabilities(features, context_phase=phase)
        post = postprocess_regime(probs)

        dominant = post["dominant_regime"]
        conf = post["regime_confidence"]
        entropy = post["regime_entropy"]
        flags = post["flags"]
        expected = EXPECTED_DOMINANT[name]

        regime_activation_count[dominant] += 1

        match = "OK" if (expected is None or dominant == expected) else "MISMATCH"
        if match == "MISMATCH":
            issues.append(f"  {name}: expected={expected}, got={dominant}")

        print(f"[{name}] phase={phase}")
        print(f"  dominant={dominant} (conf={conf:.4f}, entropy={entropy:.4f})")
        print(f"  probs: {' | '.join(f'{k}={v:.4f}' for k,v in probs.items())}")
        print(f"  flags: {flags}")
        print(f"  verdict: {match}")
        print()

    print("=== REGIME ACTIVATION SUMMARY ===")
    for regime, count in regime_activation_count.items():
        pct = count / len(SCENARIOS) * 100
        activated = "YES" if count > 0 else "NO"
        print(f"  {regime:12s}: {count}/{len(SCENARIOS)} ({pct:.0f}%) — activated={activated}")

    never_activated = [r for r, c in regime_activation_count.items() if c == 0]
    if never_activated:
        print(f"\n  PROBLEM: Never activated regimes: {never_activated}")
    else:
        print(f"\n  ALL REGIMES ACTIVATED")

    if issues:
        print(f"\n=== MISMATCHES ===")
        for issue in issues:
            print(issue)

    # Check for degenerate distribution
    print(f"\n=== DEGENERACY CHECK ===")
    all_probs = []
    for name, features in SCENARIOS.items():
        phase = SCENARIO_PHASES[name]
        probs = compute_regime_probabilities(features, context_phase=phase)
        all_probs.append(probs)

    # Avg probability per regime across all scenarios
    avg_probs = {}
    for regime in ["trend", "range", "pullback", "transition", "breakdown"]:
        avg = sum(p[regime] for p in all_probs) / len(all_probs)
        avg_probs[regime] = avg
    print("  Avg probability per regime across all scenarios:")
    for regime, avg in avg_probs.items():
        bar = "#" * int(avg * 50)
        print(f"    {regime:12s}: {avg:.4f} {bar}")

    # Check if any regime has near-zero average
    dead_regimes = [r for r, a in avg_probs.items() if a < 0.02]
    if dead_regimes:
        print(f"\n  DEGENERATE: Regimes with avg < 2%: {dead_regimes}")
    else:
        print(f"\n  Distribution is non-degenerate")

    return len(issues) == 0 and len(never_activated) == 0 and len(dead_regimes) == 0


if __name__ == "__main__":
    success = run_diagnostic()
    sys.exit(0 if success else 1)
