"""
Compare temperature 0.08 vs 0.8 on regime distribution
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

# Scenarios
SCENARIOS = {
    "strong_trend / continuation": ({
        "trend_strength": 0.85, "trend_persistence": 0.80, "exhaustion": 0.10,
        "reversal_risk": 0.10, "drawdown_pressure": 0.05, "structure_alignment": 0.90,
        "volatility_expansion": 0.40,
    }, "continuation"),
    "range_bound / mixed_range": ({
        "trend_strength": 0.15, "trend_persistence": 0.20, "exhaustion": 0.10,
        "reversal_risk": 0.15, "drawdown_pressure": 0.10, "structure_alignment": 0.25,
        "volatility_expansion": 0.20,
    }, "mixed_range"),
    "pullback / pullback": ({
        "trend_strength": 0.60, "trend_persistence": 0.55, "exhaustion": 0.15,
        "reversal_risk": 0.45, "drawdown_pressure": 0.15, "structure_alignment": 0.35,
        "volatility_expansion": 0.30,
    }, "pullback"),
    "transition / unstable_transition": ({
        "trend_strength": 0.30, "trend_persistence": 0.25, "exhaustion": 0.55,
        "reversal_risk": 0.65, "drawdown_pressure": 0.30, "structure_alignment": 0.20,
        "volatility_expansion": 0.60,
    }, "unstable_transition"),
    "breakdown / breakdown": ({
        "trend_strength": 0.20, "trend_persistence": 0.25, "exhaustion": 0.50,
        "reversal_risk": 0.55, "drawdown_pressure": 0.85, "structure_alignment": 0.15,
        "volatility_expansion": 0.75,
    }, "breakdown"),
    "moderate_mixed / late_trend": ({
        "trend_strength": 0.50, "trend_persistence": 0.45, "exhaustion": 0.35,
        "reversal_risk": 0.35, "drawdown_pressure": 0.25, "structure_alignment": 0.45,
        "volatility_expansion": 0.40,
    }, "late_trend"),
    "weak_transition / recovery_attempt": ({
        "trend_strength": 0.35, "trend_persistence": 0.30, "exhaustion": 0.40,
        "reversal_risk": 0.40, "drawdown_pressure": 0.35, "structure_alignment": 0.30,
        "volatility_expansion": 0.45,
    }, "recovery_attempt"),
}

def entropy(probs):
    h = 0
    for p in probs.values():
        if p > 1e-10:
            h -= p * math.log(p)
    return h / math.log(5)

for temp in [0.08, 0.8]:
    print(f"\n{'='*70}")
    print(f"TEMPERATURE = {temp}")
    print(f"{'='*70}")
    for name, (features, phase) in SCENARIOS.items():
        probs = compute_with_temp(features, phase, temp)
        dominant = max(probs, key=probs.get)
        ent = entropy(probs)
        gap = probs[dominant] - sorted(probs.values(), reverse=True)[1]
        print(f"  [{name}]")
        print(f"    dominant={dominant} p={probs[dominant]:.4f} entropy={ent:.4f} gap={gap:.4f}")
        print(f"    {' | '.join(f'{k}={v:.4f}' for k,v in probs.items())}")
