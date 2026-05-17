"""
Shadow KPI Aggregator
======================
Aggregates replay cases into KPI metrics.
Supports triple comparison: v4.1 base / v4.1.1 / v4.1.2.
"""


def aggregate_kpis(cases: list[dict]) -> dict:
    """
    Aggregate replay cases into comprehensive KPI metrics.
    Primary comparison: base vs v4.1.2 (structure).
    Supplementary: v4.1.1 comparison.
    """
    n = len(cases)
    if n == 0:
        return {"n": 0}

    # ── Primary: base vs v4.1.2 ──
    primary = _aggregate_version_pair(cases, "comparison")

    # ── Supplementary: base vs v4.1.1 ──
    v411_cases = [c for c in cases if c.get("comparison_v411")]
    v411 = _aggregate_version_pair(v411_cases, "comparison_v411") if v411_cases else None

    # ── New v4.1.2 metrics ──
    # Pullback misread count
    pullback_misread_count = sum(
        1 for c in cases if "pullback_misread" in c.get("pattern_tags", [])
    )

    # Direction preservation rate
    directional_base = sum(
        1 for c in cases if c["replay"]["base"]["direction"] != "NEUTRAL"
    )
    directional_struct = sum(
        1 for c in cases
        if c["replay"]["base"]["direction"] != "NEUTRAL"
        and c["replay"]["structure"]["direction"] != "NEUTRAL"
    )
    direction_preservation_rate = (
        directional_struct / directional_base if directional_base > 0 else 1.0
    )

    # Mode distribution (from multiscale_meta)
    mode_distribution = {}
    for c in cases:
        meta = c.get("multiscale_meta", {})
        mode = meta.get("mode", "unknown")
        mode_distribution[mode] = mode_distribution.get(mode, 0) + 1

    # Guard usage stats
    guard_counts = {}
    for c in cases:
        meta = c.get("multiscale_meta", {})
        for g in meta.get("multiscale_guards", []):
            guard_counts[g] = guard_counts.get(g, 0) + 1

    # v4.1.3: Override gate stats
    override_allowed_count = 0
    override_success_count = 0
    override_reasons = {}
    for c in cases:
        meta = c.get("multiscale_meta", {})
        override = meta.get("override", {})
        if override.get("override_allowed"):
            override_allowed_count += 1
            # Check if override was correct
            comp = c.get("comparison", {})
            if comp.get("structure_correct"):
                override_success_count += 1
        reason = override.get("reason", "")
        if reason:
            override_reasons[reason] = override_reasons.get(reason, 0) + 1

    # v4.1.3: Major profile fallback stats
    major_fallback_count = sum(
        1 for c in cases
        if c.get("multiscale_meta", {}).get("major_fallback_used")
    )
    major_profile_dist = {}
    for c in cases:
        p = c.get("multiscale_meta", {}).get("major_profile_used", "unknown")
        major_profile_dist[p] = major_profile_dist.get(p, 0) + 1

    result = {
        "n": n,
        **primary,
        "v412_metrics": {
            "pullback_misread_count": pullback_misread_count,
            "direction_preservation_rate": round(direction_preservation_rate, 4),
            "mode_distribution": mode_distribution,
            "guard_usage": guard_counts,
        },
        "v413_metrics": {
            "major_fallback_count": major_fallback_count,
            "major_profile_distribution": major_profile_dist,
            "override_allowed_count": override_allowed_count,
            "override_success_count": override_success_count,
            "override_success_rate": (
                round(override_success_count / override_allowed_count, 4)
                if override_allowed_count > 0 else None
            ),
            "override_reasons": override_reasons,
        },
    }

    # v4.2.0: Context layer metrics
    phase_distribution = {}
    phase_accuracy = {}
    for c in cases:
        meta = c.get("multiscale_meta", {})
        ctx = meta.get("context") or {}
        phase = ctx.get("phase", "no_context")
        phase_distribution[phase] = phase_distribution.get(phase, 0) + 1

        # Track accuracy per phase
        if phase not in phase_accuracy:
            phase_accuracy[phase] = {"correct": 0, "total": 0}
        phase_accuracy[phase]["total"] += 1
        if c.get("comparison", {}).get("structure_correct"):
            phase_accuracy[phase]["correct"] += 1

    # Compute per-phase accuracy rates
    phase_acc_rates = {}
    for ph, data in phase_accuracy.items():
        rate = data["correct"] / data["total"] if data["total"] > 0 else 0
        phase_acc_rates[ph] = round(rate, 4)

    result["v420_metrics"] = {
        "phase_distribution": phase_distribution,
        "phase_accuracy": phase_acc_rates,
    }

    # v4.3.0: Regime Engine V2 metrics
    regime_distribution = {}
    regime_accuracy = {}
    entropy_buckets = {"low": [], "mid": [], "high": []}
    uncertainty_buckets = {"low": [], "mid": [], "high": []}

    for c in cases:
        meta = c.get("multiscale_meta", {})
        regime = meta.get("regime") or {}
        dominant = regime.get("dominant_regime", "no_regime")
        entropy = regime.get("regime_entropy", 0.5)

        regime_distribution[dominant] = regime_distribution.get(dominant, 0) + 1

        if dominant not in regime_accuracy:
            regime_accuracy[dominant] = {"correct": 0, "total": 0}
        regime_accuracy[dominant]["total"] += 1
        if c.get("comparison", {}).get("structure_correct"):
            regime_accuracy[dominant]["correct"] += 1

        # Entropy bucket
        bucket = "low" if entropy < 0.6 else ("high" if entropy > 0.85 else "mid")
        correct = 1 if c.get("comparison", {}).get("structure_correct") else 0
        entropy_buckets[bucket].append(correct)

        # v4.3.1: Decision uncertainty bucket
        adj = regime.get("adjustments", {})
        du = adj.get("decision_uncertainty", 0.5)
        du_bucket = "low" if du < 0.45 else ("high" if du > 0.65 else "mid")
        uncertainty_buckets[du_bucket].append(correct)

    regime_acc_rates = {}
    for rg, data in regime_accuracy.items():
        rate = data["correct"] / data["total"] if data["total"] > 0 else 0
        regime_acc_rates[rg] = round(rate, 4)

    entropy_bucket_accuracy = {}
    for bucket, vals in entropy_buckets.items():
        if vals:
            entropy_bucket_accuracy[bucket] = {
                "count": len(vals),
                "accuracy": round(sum(vals) / len(vals), 4),
            }

    uncertainty_bucket_accuracy = {}
    for bucket, vals in uncertainty_buckets.items():
        if vals:
            uncertainty_bucket_accuracy[bucket] = {
                "count": len(vals),
                "accuracy": round(sum(vals) / len(vals), 4),
            }

    result["v430_metrics"] = {
        "regime_distribution": regime_distribution,
        "regime_accuracy": regime_acc_rates,
        "entropy_bucket_accuracy": entropy_bucket_accuracy,
        "uncertainty_bucket_accuracy": uncertainty_bucket_accuracy,
    }

    if v411:
        result["v411_comparison"] = v411

    return result


def _aggregate_version_pair(cases: list[dict], comparison_key: str) -> dict:
    """Aggregate KPIs for a specific comparison (base vs version X)."""
    n = len(cases)
    if n == 0:
        return {}

    # Direction accuracy
    base_correct = sum(1 for c in cases if c[comparison_key]["base_correct"])
    struct_correct = sum(1 for c in cases if c[comparison_key]["structure_correct"])

    base_accuracy = base_correct / n
    struct_accuracy = struct_correct / n
    accuracy_lift_pp = (struct_accuracy - base_accuracy) * 100

    # Case type distribution
    case_types = {}
    for c in cases:
        ct = c[comparison_key]["case_type"]
        case_types[ct] = case_types.get(ct, 0) + 1

    # Direction distributions
    base_dirs = [c["replay"]["base"]["direction"] for c in cases]
    # For v4.1.2, use "structure"; for v4.1.1, use "v411"
    if comparison_key == "comparison":
        struct_dirs = [c["replay"]["structure"]["direction"] for c in cases]
    else:
        struct_dirs = [c["replay"]["v411"]["direction"] for c in cases]

    base_dist = _direction_distribution(base_dirs)
    struct_dist = _direction_distribution(struct_dirs)

    # Delta statistics
    delta_key = "structure_delta" if comparison_key == "comparison" else "structure_delta_v411"
    deltas = [c["replay"][delta_key]["capped_delta"] for c in cases]
    abs_deltas = [abs(d) for d in deltas]
    avg_delta = sum(deltas) / n
    avg_abs_delta = sum(abs_deltas) / n
    max_abs_delta = max(abs_deltas) if abs_deltas else 0

    sorted_abs = sorted(abs_deltas)
    p90_idx = min(int(n * 0.9), n - 1)
    p90_delta = sorted_abs[p90_idx] if sorted_abs else 0

    # Direction changes & sign flips
    dir_changed = sum(1 for c in cases if c[comparison_key]["direction_changed"])
    sign_changed = sum(1 for c in cases if c[comparison_key]["sign_changed"])
    strength_only = sum(1 for c in cases if c[comparison_key]["strength_only_change"])

    # Score statistics
    base_scores = [c["replay"]["base"]["score"] for c in cases]
    struct_key = "structure" if comparison_key == "comparison" else "v411"
    struct_scores = [c["replay"][struct_key]["score"] for c in cases]
    avg_base_score = sum(base_scores) / n
    avg_struct_score = sum(struct_scores) / n

    # Pattern distribution
    pattern_counts = {}
    for c in cases:
        for tag in c.get("pattern_tags", []):
            pattern_counts[tag] = pattern_counts.get(tag, 0) + 1

    # Hurt rate (among cases where structure actually changed outcome)
    impact_cases = case_types.get("structure_improved", 0) + case_types.get("structure_hurt", 0)
    hurt_rate = case_types.get("structure_hurt", 0) / impact_cases if impact_cases > 0 else 0

    return {
        "base": {
            "accuracy": round(base_accuracy, 4),
            "avg_score": round(avg_base_score, 6),
            "distribution": base_dist,
        },
        "structure": {
            "accuracy": round(struct_accuracy, 4),
            "avg_score": round(avg_struct_score, 6),
            "distribution": struct_dist,
        },
        "comparison": {
            "accuracy_lift_pp": round(accuracy_lift_pp, 2),
            "case_types": case_types,
            "hurt_rate": round(hurt_rate, 4),
            "direction_changed": dir_changed,
            "sign_changed": sign_changed,
            "strength_only_changed": strength_only,
        },
        "delta_stats": {
            "avg_delta": round(avg_delta, 6),
            "avg_abs_delta": round(avg_abs_delta, 6),
            "max_abs_delta": round(max_abs_delta, 6),
            "p90_abs_delta": round(p90_delta, 6),
        },
        "pattern_distribution": pattern_counts,
    }


def _direction_distribution(directions: list[str]) -> dict:
    n = len(directions) or 1
    counts = {}
    for d in directions:
        counts[d] = counts.get(d, 0) + 1

    neutral = counts.get("NEUTRAL", 0)
    mild = counts.get("MILD_BULL", 0) + counts.get("MILD_BEAR", 0)
    strong = counts.get("STRONG_BULL", 0) + counts.get("STRONG_BEAR", 0)

    return {
        "neutral_ratio": round(neutral / n, 4),
        "mild_ratio": round(mild / n, 4),
        "strong_ratio": round(strong / n, 4),
        "counts": counts,
    }
