"""
Major/Minor Fusion
====================
Fuses major and minor structure features using mode-aware weighting.
Includes hard guards: pullback protection, reversal gate, range suppression.

Output: fused features dict that goes directly into StructureWeightOptimizer V2.1.
The optimizer itself is NOT modified — only its input changes.
"""

# Mode-aware major/minor weights
MODE_WEIGHTS = {
    "aligned":            (0.65, 0.35),
    "pullback":           (0.80, 0.20),
    "reversal_candidate": (0.55, 0.45),
    "mixed_range":        (0.60, 0.40),
}

RANGE_SHRINK = 0.45


def fuse(major: dict, minor: dict, mode_info: dict, base_score: float) -> dict:
    """
    Fuse major/minor features into a single structure feature set.
    Applies mode-aware weighting and guards.

    Returns dict compatible with StructureWeightOptimizer input,
    plus mode metadata for audit.
    """
    mode = mode_info.get("mode", "mixed_range")
    mw, nw = MODE_WEIGHTS.get(mode, (0.60, 0.40))

    # Fuse each feature with mode-aware weights
    fused = {
        "structure_bias_score": _fuse_val(major, minor, "structure_bias_score", mw, nw),
        "structure_trend_score": _fuse_val(major, minor, "structure_trend_score", mw, nw),
        "structure_momentum_score": _fuse_momentum(major, minor, mw, nw),
        "structure_reversal_risk": _fuse_reversal(major, minor, mw, nw),
        "structure_stability_score": _fuse_val(major, minor, "structure_stability_score", 0.55, 0.45),
        "structure_exhaustion_score": _fuse_val(major, minor, "structure_exhaustion_score", 0.60, 0.40),
        "structure_compression_score": _fuse_val(major, minor, "structure_compression_score", 0.50, 0.50),
    }

    # ── Mode metadata for audit ──
    fused["_mode"] = mode
    fused["_pullback_confidence"] = mode_info.get("pullback_confidence", 0.0)
    fused["_major_dominant"] = mode_info.get("major_dominant", False)
    fused["_minor_counter_trend"] = mode_info.get("minor_counter_trend", False)

    return fused


def _fuse_val(major: dict, minor: dict, key: str, mw: float, nw: float) -> float:
    return round(major.get(key, 0.0) * mw + minor.get(key, 0.0) * nw, 4)


def _fuse_momentum(major: dict, minor: dict, mw: float, nw: float) -> float:
    """Momentum favors minor (tactical impulse)."""
    return round(
        major.get("structure_momentum_score", 0.0) * 0.35
        + minor.get("structure_momentum_score", 0.0) * 0.65,
        4,
    )


def _fuse_reversal(major: dict, minor: dict, mw: float, nw: float) -> float:
    """Reversal risk: take the more conservative (higher) weighted estimate."""
    major_rev = major.get("structure_reversal_risk", 0.0) * 0.60
    minor_rev = minor.get("structure_reversal_risk", 0.0) * 0.40
    return round(max(major_rev, minor_rev), 4)


# ═══════════════════════════════════════════════════════
# v4.1.2 Hard Guards (post-optimizer)
# ═══════════════════════════════════════════════════════

def apply_multiscale_guards(struct_result: dict, mode_info: dict, base_score: float) -> dict:
    """
    Apply v4.1.2 hard guards to optimizer output based on structure mode.

    Guards:
      1. Pullback protection: forbid sign flip + neutralization in pullback mode
      2. Reversal gate: only allow sign flip if reversal_candidate
      3. Range suppression: shrink delta by RANGE_SHRINK in mixed_range
      4. Major dominance: forbid flip when major is dominant and healthy
    """
    from forecast.v41_config import classify_direction

    mode = mode_info.get("mode", "mixed_range")
    major_dominant = mode_info.get("major_dominant", False)
    reversal_candidate = mode_info.get("reversal_candidate", False)

    score_after = struct_result["score_after_structure"]
    sign_flip_allowed = struct_result.get("sign_flip_allowed", False)

    guards_applied = []

    # Guard 1: Pullback protection
    if mode == "pullback":
        sign_flip_allowed = False
        guards_applied.append("pullback_forbid_flip")

        if abs(base_score) >= 0.20:
            base_dir = classify_direction(base_score)
            cand_dir = classify_direction(score_after)
            if base_dir != "NEUTRAL" and cand_dir == "NEUTRAL":
                if base_score > 0:
                    score_after = max(score_after, 0.20)
                else:
                    score_after = min(score_after, -0.20)
                guards_applied.append("pullback_preserve_direction")

    # Guard 2: Reversal gate — only allow sign flip if reversal_candidate
    if not reversal_candidate:
        if _would_flip(base_score, score_after):
            if abs(base_score) < 0.08:
                score_after = 0.0
            else:
                score_after = base_score * 0.25
            sign_flip_allowed = False
            guards_applied.append("reversal_gate_blocked")

    # Guard 3: Range suppression
    if mode == "mixed_range":
        original_delta = score_after - base_score
        shrunk_delta = original_delta * RANGE_SHRINK
        score_after = base_score + shrunk_delta
        guards_applied.append(f"range_shrink_{RANGE_SHRINK}")

    # Guard 4: Major dominance
    if major_dominant and not reversal_candidate:
        if _would_flip(base_score, score_after):
            if abs(base_score) < 0.08:
                score_after = 0.0
            else:
                score_after = base_score * 0.85
            sign_flip_allowed = False
            guards_applied.append("major_dominance_forbid_flip")

    # Guard 5: Direction preservation floor (all modes except reversal)
    # Prevents any guard combination from pushing directional base → NEUTRAL
    if abs(base_score) >= 0.20 and not reversal_candidate:
        from forecast.v41_config import classify_direction as _classify
        base_dir = _classify(base_score)
        final_dir = _classify(score_after)
        if base_dir != "NEUTRAL" and final_dir == "NEUTRAL":
            if base_score > 0:
                score_after = max(score_after, 0.20)
            else:
                score_after = min(score_after, -0.20)
            guards_applied.append("direction_preservation_floor")

    # Guard 6: Non-aligned NEUTRAL anchor
    # In non-aligned modes (pullback, mixed_range), don't promote NEUTRAL → MILD
    # Only aligned mode (both scales agree) should strengthen weak signals
    if mode != "aligned" and abs(base_score) < 0.20:
        from forecast.v41_config import classify_direction as _classify2
        final_dir = _classify2(score_after)
        if final_dir != "NEUTRAL":
            if score_after > 0:
                score_after = min(score_after, 0.19)
            else:
                score_after = max(score_after, -0.19)
            guards_applied.append("non_aligned_neutral_cap")

    score_after = max(-1.0, min(1.0, score_after))

    return {
        **struct_result,
        "score_after_structure": round(score_after, 6),
        "sign_flip_allowed": sign_flip_allowed,
        "multiscale_guards": guards_applied,
    }


def _would_flip(base_score: float, candidate_score: float) -> bool:
    """Check if candidate would flip the sign of base score."""
    if base_score == 0 or candidate_score == 0:
        return False
    return base_score * candidate_score < 0
