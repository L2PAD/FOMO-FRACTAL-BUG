"""
Pattern Learning Engine — detects persistent error/strength patterns.

Analyzes resolved forecast_results to find:
  - OVERCONFIDENCE: high confidence, low actual hit rate
  - UNDERCONFIDENCE: conservative signals, high actual
  - LATE_SIGNAL: correct direction, poor timing (low opportunity capture)
  - WEAK_STRUCTURE: structure edge present but not helping
  - STRONG_STRUCTURE: structure edge correlates with wins
  - SHORT_EXPIRY_NOISE: short expiry markets have high error

Noise filters: MIN_SAMPLE=30, MIN_EFFECT=0.04, MIN_CONFIDENCE=0.6
Winsorization applied to metrics before analysis.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger("self_improvement.pattern_learning")

MIN_SAMPLE = 30
MIN_EFFECT = 0.04
MIN_CONFIDENCE = 0.6


def detect_patterns(db) -> list[dict]:
    """Detect persistent patterns from resolved forecasts."""
    results = list(db.forecast_results.find(
        {"correctness": {"$in": ["CORRECT", "WRONG"]}},
        {"_id": 0}
    ))

    if len(results) < MIN_SAMPLE:
        return []

    findings = []

    # Group by family_key
    families = {}
    for r in results:
        fk = r.get("family_key", "unknown")
        families.setdefault(fk, []).append(r)

    # 1. OVERCONFIDENCE — high confidence buckets with low hit rate
    findings.extend(_detect_overconfidence(results))

    # 2. UNDERCONFIDENCE — low confidence with high actual
    findings.extend(_detect_underconfidence(results))

    # 3. LATE_SIGNAL — correct but bad timing
    findings.extend(_detect_late_signal(results))

    # 4. STRUCTURE patterns — per family
    for fk, fam_results in families.items():
        if len(fam_results) >= MIN_SAMPLE:
            findings.extend(_detect_structure_patterns(fk, fam_results))

    # 5. SHORT_EXPIRY_NOISE
    findings.extend(_detect_short_expiry_noise(results))

    # Apply global noise filter
    findings = [f for f in findings
                if f["sample_size"] >= MIN_SAMPLE
                and abs(f["effect_size"]) >= MIN_EFFECT
                and f["confidence"] >= MIN_CONFIDENCE]

    # Dedupe by pattern_key
    seen = set()
    unique = []
    for f in findings:
        if f["pattern_key"] not in seen:
            seen.add(f["pattern_key"])
            unique.append(f)

    now = datetime.now(timezone.utc).isoformat()
    for f in unique:
        f["detected_at"] = now

    return unique[:20]  # max 20 findings per cycle


def _detect_overconfidence(results: list) -> list:
    """Detect overconfidence: high-confidence predictions with low accuracy."""
    high_conf = [r for r in results if r.get("confidence") in ("high",)]
    if len(high_conf) < MIN_SAMPLE:
        return []

    correct = sum(1 for r in high_conf if r.get("binary_correct"))
    accuracy = correct / len(high_conf)
    expected = 0.70  # expect ~70% for "high" confidence

    effect = expected - accuracy
    if effect < MIN_EFFECT:
        return []

    return [{
        "pattern_key": "global:overconfidence:high",
        "family_key": "global",
        "issue_type": "OVERCONFIDENCE",
        "sample_size": len(high_conf),
        "effect_direction": "NEGATIVE",
        "effect_size": round(effect, 4),
        "confidence": round(1 - (1 / len(high_conf)), 4),
        "summary": f"High-confidence predictions hit only {accuracy:.0%} vs expected {expected:.0%} (n={len(high_conf)})",
    }]


def _detect_underconfidence(results: list) -> list:
    """Detect underconfidence: low-confidence with unexpectedly high accuracy."""
    low_conf = [r for r in results if r.get("confidence") in ("low",)]
    if len(low_conf) < MIN_SAMPLE:
        return []

    correct = sum(1 for r in low_conf if r.get("binary_correct"))
    accuracy = correct / len(low_conf)
    expected = 0.40

    effect = accuracy - expected
    if effect < MIN_EFFECT:
        return []

    return [{
        "pattern_key": "global:underconfidence:low",
        "family_key": "global",
        "issue_type": "UNDERCONFIDENCE",
        "sample_size": len(low_conf),
        "effect_direction": "POSITIVE",
        "effect_size": round(effect, 4),
        "confidence": round(1 - (1 / len(low_conf)), 4),
        "summary": f"Low-confidence predictions hit {accuracy:.0%} vs expected {expected:.0%} — model is conservative (n={len(low_conf)})",
    }]


def _detect_late_signal(results: list) -> list:
    """Detect late signals: correct direction but poor timing."""
    actionable = [r for r in results if r.get("action") in ("BUY_YES", "BUY_NO")]
    if len(actionable) < MIN_SAMPLE:
        return []

    correct = [r for r in actionable if r.get("binary_correct")]
    if not correct:
        return []

    with_opp = [r for r in correct if r.get("opportunity_captured") is not None]
    if len(with_opp) < MIN_SAMPLE:
        return []

    opp_rate = sum(1 for r in with_opp if r.get("opportunity_captured")) / len(with_opp)

    # Late signal: correct but opportunity not captured
    late_rate = 1 - opp_rate
    if late_rate < MIN_EFFECT:
        return []

    # Check entry quality
    eq_vals = [r.get("entry_quality", 0) for r in with_opp if r.get("entry_quality") is not None]
    avg_eq = _winsorized_mean(eq_vals) if eq_vals else 0

    if avg_eq < 0.02:
        return []

    return [{
        "pattern_key": "global:late_signal",
        "family_key": "global",
        "issue_type": "LATE_SIGNAL",
        "sample_size": len(with_opp),
        "effect_direction": "NEGATIVE",
        "effect_size": round(late_rate, 4),
        "confidence": round(min(0.95, 1 - (1 / len(with_opp))), 4),
        "summary": f"Correct predictions miss {late_rate:.0%} of opportunities. Avg entry quality gap: {avg_eq:.3f} (n={len(with_opp)})",
    }]


def _detect_structure_patterns(family_key: str, results: list) -> list:
    """Detect structure edge effectiveness per family."""
    findings = []

    correct = sum(1 for r in results if r.get("binary_correct"))
    accuracy = correct / len(results)

    # Check if high accuracy → strong structure signal
    if accuracy > 0.60:
        effect = accuracy - 0.50
        findings.append({
            "pattern_key": f"family:{family_key}:strong_structure",
            "family_key": family_key,
            "issue_type": "STRONG_STRUCTURE",
            "sample_size": len(results),
            "effect_direction": "POSITIVE",
            "effect_size": round(effect, 4),
            "confidence": round(min(0.95, 1 - (2 / len(results))), 4),
            "summary": f"Family {family_key} shows {accuracy:.0%} accuracy (n={len(results)}) — strong signal",
        })
    elif accuracy < 0.45:
        effect = 0.50 - accuracy
        findings.append({
            "pattern_key": f"family:{family_key}:weak_structure",
            "family_key": family_key,
            "issue_type": "WEAK_STRUCTURE",
            "sample_size": len(results),
            "effect_direction": "NEGATIVE",
            "effect_size": round(effect, 4),
            "confidence": round(min(0.95, 1 - (2 / len(results))), 4),
            "summary": f"Family {family_key} shows {accuracy:.0%} accuracy (n={len(results)}) — weak signal",
        })

    return findings


def _detect_short_expiry_noise(results: list) -> list:
    """Detect if short-expiry markets have higher error."""
    short = [r for r in results if "lt_6h" in r.get("family_key", "") or "lt_24h" in r.get("family_key", "")]
    long_ = [r for r in results if "gt_7d" in r.get("family_key", "") or "lt_7d" in r.get("family_key", "")]

    if len(short) < MIN_SAMPLE or len(long_) < MIN_SAMPLE:
        return []

    short_acc = sum(1 for r in short if r.get("binary_correct")) / len(short)
    long_acc = sum(1 for r in long_ if r.get("binary_correct")) / len(long_)

    effect = long_acc - short_acc
    if effect < MIN_EFFECT:
        return []

    return [{
        "pattern_key": "global:short_expiry_noise",
        "family_key": "global",
        "issue_type": "SHORT_EXPIRY_NOISE",
        "sample_size": len(short),
        "effect_direction": "NEGATIVE",
        "effect_size": round(effect, 4),
        "confidence": round(min(0.95, 1 - (2 / min(len(short), len(long_)))), 4),
        "summary": f"Short expiry accuracy {short_acc:.0%} vs long {long_acc:.0%} — delta {effect:.0%} (n_short={len(short)})",
    }]


def _winsorized_mean(values: list, p: float = 0.05) -> float:
    """Compute winsorized mean (clip outliers at p and 1-p percentiles)."""
    if not values:
        return 0
    sorted_v = sorted(values)
    n = len(sorted_v)
    lo_idx = max(0, int(n * p))
    hi_idx = min(n - 1, int(n * (1 - p)))
    lo = sorted_v[lo_idx]
    hi = sorted_v[hi_idx]
    clipped = [max(lo, min(hi, v)) for v in values]
    return sum(clipped) / len(clipped)
