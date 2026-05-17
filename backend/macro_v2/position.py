"""Position Sizing Policy — nonlinear execution intelligence.

Combines Core Engine confidence, Macro V2 risk/regime, Risk Split,
and Alignment Score into a single position size multiplier with
mode classification and explanations.
"""
import math


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _sigmoid(x):
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def compute_position_size(core_snap, macro_snap, sync_result, risk_split, base_risk=1.0):
    """Compute position sizing policy.

    Args:
        core_snap: Core Engine snapshot (pressure, regime, etc.)
        macro_snap: Macro V2 snapshot (computed, impact, etc.)
        sync_result: Alignment/conflict result
        risk_split: {structural, tactical, total, levels}
        base_risk: Profile-level base risk (default 1.0)

    Returns:
        dict with sizeMult, mode, blocked, components, inputs, explain
    """
    # ── Extract inputs ──
    pressure = core_snap.get("pressure", {})
    core_regime = core_snap.get("regime", {})

    up = pressure.get("upward", 50)
    down = pressure.get("downward", 50)
    if up > 60:
        core_direction = "LONG"
    elif down > 60:
        core_direction = "SHORT"
    else:
        core_direction = "HOLD"

    core_confidence = _clamp(core_regime.get("confidence", 0.5), 0, 1)

    c = macro_snap.get("computed", {})
    macro_mult = _clamp(c.get("macroMult", 1.0), 0.40, 1.05)
    riskoff_prob = _clamp(c.get("riskOffProb", 0.5), 0, 1)
    strong_blocked = c.get("strongActionsBlocked", False)
    macro_regime = c.get("regime", "NEUTRAL")
    fear_greed = macro_snap.get("raw", {}).get("fearGreed", 50)

    alignment = _clamp(sync_result.get("alignmentScore", 50) / 100.0, 0, 1)
    conflict = _clamp(sync_result.get("conflictScore", 50) / 100.0, 0, 1)
    sync_state = sync_result.get("state", "MIXED")

    structural = _clamp(risk_split.get("structural", 50) / 100.0, 0, 1)
    tactical = _clamp(risk_split.get("tactical", 50) / 100.0, 0, 1)

    # Normalized inputs
    C = core_confidence
    S = structural
    T = tactical
    A = alignment
    K = conflict
    M = macro_mult
    R = riskoff_prob

    # ── Gate rules (hard blocks) ──
    blocked = False
    blocked_reasons = []

    if core_direction == "HOLD":
        blocked = True
        blocked_reasons.append("Core: HOLD — no directional bias")

    if strong_blocked:
        blocked = True
        blocked_reasons.append("Macro: Strong actions blocked (risk-off / extreme fear)")

    if R >= 0.85 and K >= 0.60:
        blocked = True
        blocked_reasons.append("Risk-Off extreme + Core↔Macro conflict")

    if S >= 0.85:
        blocked = True
        blocked_reasons.append("Structural risk extreme (≥85)")

    if blocked:
        return _blocked_result(
            core_direction, core_confidence, core_regime.get("dominant", "range"),
            macro_regime, riskoff_prob, macro_mult, strong_blocked, fear_greed,
            structural * 100, tactical * 100, alignment * 100, conflict * 100,
            sync_state, blocked_reasons,
        )

    # ── Mode calculation (risk appetite) ──
    appetite = (
        + 0.9 * (1 - R)
        + 0.6 * M
        + 0.7 * A - 0.9 * K
        - 0.8 * S
        - 0.5 * T
    )

    if appetite < 0.55:
        mode = "DEFENSIVE"
        mode_factor = 0.65
    elif appetite < 1.10:
        mode = "NEUTRAL"
        mode_factor = 1.00
    else:
        mode = "AGGRESSIVE"
        mode_factor = 1.20

    # ── Nonlinear shaping functions ──

    # (a) Confidence: sigmoid centered at 0.58, slope 0.10
    conf_factor = _sigmoid((C - 0.58) / 0.10)

    # (b) Risk penalty: exponential decay with structural heavier
    risk_penalty = math.exp(-(1.6 * S + 0.9 * T))

    # (c) Sync factor: conflict cuts harder than alignment boosts
    sync_factor = math.exp(0.8 * A - 1.2 * K)

    # ── Final formula ──
    raw = base_risk * conf_factor * risk_penalty * sync_factor * M * mode_factor
    size_mult = round(_clamp(raw, 0.0, 1.50), 2)

    # ── Explain bullets ──
    explain = []
    explain.append(f"Mode: {mode} (appetite {appetite:.2f})")

    if S > 0.65:
        explain.append(f"Structural risk high ({S*100:.0f}) — size reduced")
    elif S > 0.40:
        explain.append(f"Structural risk moderate ({S*100:.0f})")

    if T > 0.65:
        explain.append(f"Tactical risk elevated ({T*100:.0f}) — size reduced")

    if K > 0.55:
        explain.append(f"Conflict Core↔Macro ({K*100:.0f}%) — size cut")
    elif A > 0.70:
        explain.append(f"Strong alignment ({A*100:.0f}%) — size allowed")

    if R > 0.70:
        explain.append(f"Risk-Off environment ({R*100:.0f}%) — defensive sizing")

    if M < 0.75:
        explain.append(f"Macro multiplier {M:.2f} — confidence scaled down")

    return {
        "asset": None,  # filled by caller
        "mode": mode,
        "blocked": False,
        "sizeMult": size_mult,
        "components": {
            "baseRisk": round(base_risk, 2),
            "confFactor": round(conf_factor, 3),
            "riskPenalty": round(risk_penalty, 3),
            "syncFactor": round(sync_factor, 3),
            "macroMult": round(M, 3),
            "modeFactor": round(mode_factor, 2),
            "appetite": round(appetite, 3),
            "raw": round(raw, 4),
        },
        "inputs": {
            "core": {
                "direction": core_direction,
                "confidence": round(core_confidence, 3),
                "regime": core_regime.get("dominant", "range"),
            },
            "macro": {
                "regime": macro_regime,
                "riskOffProb": round(riskoff_prob, 3),
                "macroMult": round(macro_mult, 3),
                "strongActionsBlocked": strong_blocked,
                "fearGreed": round(fear_greed, 1),
            },
            "risk": {
                "structural": round(structural * 100),
                "tactical": round(tactical * 100),
            },
            "sync": {
                "alignmentScore": round(alignment * 100),
                "conflictScore": round(conflict * 100),
                "state": sync_state,
            },
        },
        "explain": explain,
        "blockedReasons": [],
    }


def _blocked_result(
    direction, confidence, core_regime, macro_regime,
    riskoff, macro_mult, strong_blocked, fear_greed,
    structural, tactical, alignment, conflict,
    sync_state, reasons,
):
    return {
        "asset": None,
        "mode": "DEFENSIVE",
        "blocked": True,
        "sizeMult": 0.0,
        "components": {
            "baseRisk": 0, "confFactor": 0, "riskPenalty": 0,
            "syncFactor": 0, "macroMult": 0, "modeFactor": 0,
            "appetite": 0, "raw": 0,
        },
        "inputs": {
            "core": {"direction": direction, "confidence": round(confidence, 3), "regime": core_regime},
            "macro": {"regime": macro_regime, "riskOffProb": round(riskoff, 3),
                      "macroMult": round(macro_mult, 3), "strongActionsBlocked": strong_blocked,
                      "fearGreed": round(fear_greed, 1)},
            "risk": {"structural": round(structural), "tactical": round(tactical)},
            "sync": {"alignmentScore": round(alignment), "conflictScore": round(conflict), "state": sync_state},
        },
        "explain": [f"BLOCKED: {r}" for r in reasons],
        "blockedReasons": reasons,
    }
