"""
Temperature sweep to find optimal value for regime engine
"""
import sys, math
sys.path.insert(0, "/app/backend")

from forecast.regime.regime_types import REGIME_NAMES
from forecast.regime.regime_probability_engine import _PHASE_REGIME_PRIOR

def softmax(scores, temperature):
    scaled = [s / temperature for s in scores]
    max_s = max(scaled)
    exps = [math.exp(s - max_s) for s in scaled]
    total = sum(exps)
    return [e / total for e in exps]

def compute_with_temp(features, context_phase, temperature):
    ts = features["trend_strength"]
    tp = features["trend_persistence"]
    ex = features["exhaustion"]
    rr = features["reversal_risk"]
    dp = features["drawdown_pressure"]
    sa = features["structure_alignment"]
    ve = features["volatility_expansion"]

    trend_score = 0.35*ts + 0.30*tp + 0.15*sa - 0.10*rr - 0.10*ex
    range_score = 0.30*(1-ts) + 0.25*(1-tp) + 0.20*(1-sa) + 0.15*(1-ve) + 0.10*(1-dp)
    pullback_score = 0.30*ts + 0.20*tp + 0.25*rr + 0.15*(1-dp) + 0.10*(1-sa)
    transition_score = 0.30*rr + 0.25*ex + 0.20*(1-sa) + 0.15*ve + 0.10*(1-tp)
    breakdown_score = 0.45*dp + 0.20*rr + 0.15*ve + 0.10*(1-ts) + 0.10*ex

    raw = [trend_score, range_score, pullback_score, transition_score, breakdown_score]
    mean_score = sum(raw) / len(raw)
    centered = [s - mean_score for s in raw]
    prior = _PHASE_REGIME_PRIOR.get(context_phase, _PHASE_REGIME_PRIOR["mixed_range"])
    boosted = [centered[i] + prior.get(name, 0.0) for i, name in enumerate(REGIME_NAMES)]
    probs = softmax(boosted, temperature)
    return {name: round(p, 4) for name, p in zip(REGIME_NAMES, probs)}

def entropy(probs):
    h = 0
    for p in probs.values():
        if p > 1e-10:
            h -= p * math.log(p)
    return h / math.log(5)

SCENARIOS = {
    "strong_trend/continuation": ({"trend_strength": 0.85, "trend_persistence": 0.80, "exhaustion": 0.10, "reversal_risk": 0.10, "drawdown_pressure": 0.05, "structure_alignment": 0.90, "volatility_expansion": 0.40}, "continuation"),
    "range/mixed_range": ({"trend_strength": 0.15, "trend_persistence": 0.20, "exhaustion": 0.10, "reversal_risk": 0.15, "drawdown_pressure": 0.10, "structure_alignment": 0.25, "volatility_expansion": 0.20}, "mixed_range"),
    "pullback/pullback": ({"trend_strength": 0.60, "trend_persistence": 0.55, "exhaustion": 0.15, "reversal_risk": 0.45, "drawdown_pressure": 0.15, "structure_alignment": 0.35, "volatility_expansion": 0.30}, "pullback"),
    "transition/unstable": ({"trend_strength": 0.30, "trend_persistence": 0.25, "exhaustion": 0.55, "reversal_risk": 0.65, "drawdown_pressure": 0.30, "structure_alignment": 0.20, "volatility_expansion": 0.60}, "unstable_transition"),
    "breakdown/breakdown": ({"trend_strength": 0.20, "trend_persistence": 0.25, "exhaustion": 0.50, "reversal_risk": 0.55, "drawdown_pressure": 0.85, "structure_alignment": 0.15, "volatility_expansion": 0.75}, "breakdown"),
    "moderate/late_trend": ({"trend_strength": 0.50, "trend_persistence": 0.45, "exhaustion": 0.35, "reversal_risk": 0.35, "drawdown_pressure": 0.25, "structure_alignment": 0.45, "volatility_expansion": 0.40}, "late_trend"),
    "weak/recovery": ({"trend_strength": 0.35, "trend_persistence": 0.30, "exhaustion": 0.40, "reversal_risk": 0.40, "drawdown_pressure": 0.35, "structure_alignment": 0.30, "volatility_expansion": 0.45}, "recovery_attempt"),
}

TEMPS = [0.08, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.80]

print(f"{'Temp':>5} | {'Scenario':>25} | {'Dominant':>12} | {'P(dom)':>7} | {'Entropy':>8} | {'Gap':>7} | Verdict")
print("-" * 100)

for temp in TEMPS:
    dominant_set = set()
    entropy_list = []
    ambiguity_count = 0
    correct = 0
    expected = ["trend", "range", "pullback", "transition", "breakdown", None, None]

    for i, (name, (features, phase)) in enumerate(SCENARIOS.items()):
        probs = compute_with_temp(features, phase, temp)
        dom = max(probs, key=probs.get)
        dominant_set.add(dom)
        ent = entropy(probs)
        entropy_list.append(ent)
        gap = probs[dom] - sorted(probs.values(), reverse=True)[1]
        if gap < 0.08:
            ambiguity_count += 1
        if expected[i] is not None and dom == expected[i]:
            correct += 1

    avg_ent = sum(entropy_list) / len(entropy_list)
    min_ent = min(entropy_list)
    max_ent = max(entropy_list)
    ent_range = max_ent - min_ent

    print(f"\n  temp={temp:.2f} | regimes_activated={len(dominant_set)}/5 | "
          f"correct={correct}/5 | ambiguity_count={ambiguity_count}/7")
    print(f"  entropy: avg={avg_ent:.3f} min={min_ent:.3f} max={max_ent:.3f} range={ent_range:.3f}")
    print(f"  activated: {sorted(dominant_set)}")

    for i, (name, (features, phase)) in enumerate(SCENARIOS.items()):
        probs = compute_with_temp(features, phase, temp)
        dom = max(probs, key=probs.get)
        ent = entropy(probs)
        gap = probs[dom] - sorted(probs.values(), reverse=True)[1]
        exp_str = expected[i] or "any"
        ok = "OK" if (expected[i] is None or dom == expected[i]) else "MISS"
        print(f"    {name:>25} | {dom:>12} p={probs[dom]:.3f} ent={ent:.3f} gap={gap:.3f} [{ok}]")
