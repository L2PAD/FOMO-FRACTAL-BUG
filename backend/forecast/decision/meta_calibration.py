"""
Meta-Calibration Layer V1
============================
Self-adjusts interaction modifier strengths based on historical outcome
effectiveness — without ML, using rule-based retrospective calibration.

NOT a prediction layer.  It adjusts HOW MUCH the interaction layer's
modifiers are allowed to influence the pipeline.

Pipeline:
  evaluated forecasts + interaction audit → MetaCalibration.fit()
  → per-horizon {conf_scale, caps} → stored → used in next forecast cycle

Staged rollout:
  M1: shadow (compute + log)
  M2: confidence scale only
  M3: dynamic caps
  M4: scenario/decision scale (future)
"""

from dataclasses import dataclass, field
from statistics import mean as _mean


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# ── Constants ──

BASE_CONF_SCALE = {
    "24H": 0.45,
    "7D": 0.60,
    "30D": 0.65,
}

META_CONF_SCALE_MIN = 0.35
META_CONF_SCALE_MAX = 0.80
META_CONF_CAP_UP_MAX = 0.15
META_CONF_CAP_DOWN_MIN = -0.20

META_LR = 0.05
META_MAX_STEP = 0.03
META_EMA_ALPHA = 0.7

META_MIN_SAMPLES_TOTAL = 120
META_MIN_SAMPLES_PER_STATE = 20
META_MIN_EFFECTIVE_STATES = 3

META_FREEZE_DELTA = 0.05  # reject update if |delta| > this

# State grouping for small samples
STATE_GROUPS = {
    "aligned": ["aligned_bullish", "aligned_bearish"],
    "fragile": ["fragile_bullish", "fragile_bearish"],
    "conflict": ["transition_conflict"],
    "range": ["range_mixed", "mixed_unclear"],
}

GROUP_FOR_STATE = {}
for _g, _states in STATE_GROUPS.items():
    for _s in _states:
        GROUP_FOR_STATE[_s] = _g


# ── Contracts ──

@dataclass
class MetaCalibrationRow:
    horizon: str
    asset: str

    interaction_state: str
    alignment_score: float
    conflict_score: float

    applied_confidence_modifier: float
    applied_scenario_mod_bullish: float
    applied_scenario_mod_base: float
    applied_scenario_mod_bearish: float
    applied_decision_bias_modifier: float

    final_direction: str
    final_confidence: float

    outcome_label: str        # TP / FP / FN / WEAK
    correct_direction: bool


@dataclass
class MetaCalibrationOutput:
    conf_scale: float
    scenario_scale: float       # not used in V1
    decision_scale: float       # not used in V1

    conf_cap_up: float
    conf_cap_down: float
    decision_cap: float

    state_effectiveness: dict
    rationale: list
    audit: dict


@dataclass
class MetaCalibrationSnapshot:
    """Stored per-horizon result for pipeline consumption."""
    horizon: str
    conf_scale: float
    conf_cap_up: float
    conf_cap_down: float
    state_effectiveness: dict
    rationale: list
    updated_at: str = ""


# ── Engine ──

class MetaCalibrationLayerV1:

    def fit(self, rows: list[MetaCalibrationRow], horizon: str) -> MetaCalibrationOutput | None:
        """
        Fit per-horizon meta-calibration from evaluated rows.
        Returns None if insufficient data.
        """
        if len(rows) < META_MIN_SAMPLES_TOTAL:
            return None

        grouped = self._group_by_state(rows)
        effectiveness = self._evaluate_state_effectiveness(grouped)

        states_with_data = sum(
            1 for v in effectiveness.values()
            if v.get("verdict") != "insufficient_data"
        )
        if states_with_data < META_MIN_EFFECTIVE_STATES:
            return None

        conf_scale = self._derive_conf_scale(effectiveness, horizon)
        conf_cap_up, conf_cap_down = self._derive_conf_caps(effectiveness)
        rationale = self._build_rationale(effectiveness, horizon, conf_scale)

        return MetaCalibrationOutput(
            conf_scale=round(conf_scale, 4),
            scenario_scale=1.0,
            decision_scale=1.0,
            conf_cap_up=round(conf_cap_up, 4),
            conf_cap_down=round(conf_cap_down, 4),
            decision_cap=0.15,
            state_effectiveness=effectiveness,
            rationale=rationale,
            audit={
                "total_rows": len(rows),
                "states_with_data": states_with_data,
                "horizon": horizon,
            },
        )

    @staticmethod
    def smooth_update(
        old: MetaCalibrationSnapshot,
        new_output: MetaCalibrationOutput,
    ) -> MetaCalibrationSnapshot:
        """
        EMA-smooth the new recommendation against the old stored values.
        Applies step limit + freeze protection to ALL calibrated fields.
        """
        def _smooth_field(old_val: float, new_val: float) -> float:
            step = _clamp(new_val - old_val, -META_MAX_STEP, META_MAX_STEP)
            updated = old_val + META_LR * step
            smoothed = META_EMA_ALPHA * old_val + (1 - META_EMA_ALPHA) * updated
            if abs(smoothed - old_val) > META_FREEZE_DELTA:
                return old_val
            return round(smoothed, 4)

        return MetaCalibrationSnapshot(
            horizon=old.horizon,
            conf_scale=_smooth_field(old.conf_scale, new_output.conf_scale),
            conf_cap_up=_smooth_field(old.conf_cap_up, new_output.conf_cap_up),
            conf_cap_down=_smooth_field(old.conf_cap_down, new_output.conf_cap_down),
            state_effectiveness=new_output.state_effectiveness,
            rationale=new_output.rationale,
        )

    @staticmethod
    def default_snapshot(horizon: str) -> MetaCalibrationSnapshot:
        """Return safe default snapshot for a horizon."""
        return MetaCalibrationSnapshot(
            horizon=horizon,
            conf_scale=BASE_CONF_SCALE.get(horizon, 0.60),
            conf_cap_up=0.12,
            conf_cap_down=-0.15,
            state_effectiveness={},
            rationale=["default — no meta data yet"],
        )

    # ── Grouping ──

    @staticmethod
    def _group_by_state(rows: list[MetaCalibrationRow]) -> dict:
        """Group rows by interaction_state, with fallback to group buckets."""
        fine = {}
        for r in rows:
            fine.setdefault(r.interaction_state, []).append(r)

        coarse = {}
        for state, state_rows in fine.items():
            group = GROUP_FOR_STATE.get(state, "range")
            coarse.setdefault(group, []).extend(state_rows)

        result = {}
        for state, state_rows in fine.items():
            if len(state_rows) >= META_MIN_SAMPLES_PER_STATE:
                result[state] = state_rows
            else:
                group = GROUP_FOR_STATE.get(state, "range")
                if group not in result and len(coarse.get(group, [])) >= META_MIN_SAMPLES_PER_STATE:
                    result[group] = coarse[group]

        for group, group_rows in coarse.items():
            if group not in result and len(group_rows) >= META_MIN_SAMPLES_PER_STATE:
                result[group] = group_rows

        return result

    # ── Effectiveness ──

    @staticmethod
    def _evaluate_state_effectiveness(grouped: dict) -> dict:
        out = {}
        for state, rows in grouped.items():
            if len(rows) < META_MIN_SAMPLES_PER_STATE:
                out[state] = {"verdict": "insufficient_data", "n": len(rows)}
                continue

            acc = _mean([1 if r.correct_direction else 0 for r in rows])
            fp_rate = _mean([1 if r.outcome_label == "FP" else 0 for r in rows])
            avg_conf_mod = _mean([r.applied_confidence_modifier for r in rows])

            if acc > 0.60 and fp_rate < 0.35:
                verdict = "effective"
            elif acc < 0.45 or fp_rate > 0.50:
                verdict = "harmful"
            else:
                verdict = "neutral"

            out[state] = {
                "accuracy": round(acc, 4),
                "fp_rate": round(fp_rate, 4),
                "avg_conf_modifier": round(avg_conf_mod, 4),
                "n": len(rows),
                "verdict": verdict,
            }
        return out

    # ── Scale derivation ──

    def _derive_conf_scale(self, effectiveness: dict, horizon: str) -> float:
        base = BASE_CONF_SCALE.get(horizon, 0.60)
        delta = 0.0

        aligned = self._get_group_eff(effectiveness, "aligned")
        conflict = self._get_group_eff(effectiveness, "conflict")

        aligned_acc = aligned.get("accuracy", 0.5)
        conflict_fp = conflict.get("fp_rate", 0.5)

        if aligned_acc > 0.60:
            delta += 0.02
        if aligned_acc > 0.70:
            delta += 0.01

        if conflict_fp > 0.45:
            delta -= 0.02
        if conflict_fp > 0.55:
            delta -= 0.01

        return _clamp(base + delta, META_CONF_SCALE_MIN, META_CONF_SCALE_MAX)

    @staticmethod
    def _derive_conf_caps(effectiveness: dict) -> tuple:
        aligned_any = None
        conflict_any = None
        for k, v in effectiveness.items():
            if v.get("verdict") == "insufficient_data":
                continue
            if k in ("aligned", "aligned_bullish", "aligned_bearish"):
                aligned_any = v
            if k in ("conflict", "transition_conflict"):
                conflict_any = v

        alignment_gain = aligned_any.get("accuracy", 0.5) - 0.5 if aligned_any else 0.0
        conflict_fp = conflict_any.get("fp_rate", 0.5) if conflict_any else 0.5

        cap_up = _clamp(0.10 + 0.05 * alignment_gain, 0.05, META_CONF_CAP_UP_MAX)
        cap_down = _clamp(-0.12 - 0.05 * conflict_fp, META_CONF_CAP_DOWN_MIN, -0.05)

        return round(cap_up, 4), round(cap_down, 4)

    @staticmethod
    def _get_group_eff(effectiveness: dict, group: str) -> dict:
        """Get effectiveness for a group, checking both group and fine states."""
        if group in effectiveness:
            return effectiveness[group]
        states = STATE_GROUPS.get(group, [])
        for s in states:
            if s in effectiveness and effectiveness[s].get("verdict") != "insufficient_data":
                return effectiveness[s]
        return {}

    # ── Rationale ──

    @staticmethod
    def _build_rationale(effectiveness: dict, horizon: str, conf_scale: float) -> list:
        out = [f"horizon={horizon}, recommended conf_scale={conf_scale:.3f}"]
        for state, eff in effectiveness.items():
            if eff.get("verdict") == "insufficient_data":
                continue
            out.append(
                f"{state}: acc={eff['accuracy']:.2f} fp={eff['fp_rate']:.2f} "
                f"n={eff['n']} → {eff['verdict']}"
            )
        return out



# ══════════════════════════════════════════════════════════════════════
# Meta-Calibration V2 — State-Aware Scaling
# ══════════════════════════════════════════════════════════════════════
#
# V2 provides per-horizon × per-state-group confidence scales and caps.
# Instead of one global scale, each group (aligned/fragile/conflict/range)
# gets its own scale derived RELATIVE to the V1 scale for that horizon.
#
# Staged rollout:
#   V2.1: shadow (compute + log, no impact)
#   V2.2: blended with V1 (blend ** 1.2 non-linear)
#   V2.3: full V2
# ══════════════════════════════════════════════════════════════════════

# ── V2 Constants ──

# Group offsets relative to V1 base scale
V2_GROUP_OFFSETS = {
    "aligned": +0.05,
    "fragile": -0.10,
    "conflict": +0.05,   # higher scale = stronger penalty (modifier is negative)
    "range": -0.05,
}

# Per-group cap defaults
V2_GROUP_CAPS = {
    "aligned": {"up": 0.12, "down": -0.08},
    "fragile": {"up": 0.08, "down": -0.10},
    "conflict": {"up": 0.04, "down": -0.16},
    "range": {"up": 0.05, "down": -0.12},
}

META_V2_MIN_SAMPLES_PER_GROUP = 30
META_V2_MIN_EFFECTIVE_GROUPS = 3
META_V2_LR = 0.05
META_V2_MAX_STEP = 0.03
META_V2_EMA_ALPHA = 0.7
META_V2_FREEZE_DELTA = 0.05
META_V2_MAX_RATIO_TO_V1 = 1.25  # |scale_v2/scale_v1| guard

ALL_GROUPS = ("aligned", "fragile", "conflict", "range")


# ── V2 Contracts ──

@dataclass
class MetaCalibrationRowV2:
    horizon: str
    asset: str

    interaction_state: str
    state_group: str        # aligned / fragile / conflict / range

    alignment_score: float
    conflict_score: float

    applied_confidence_modifier: float
    final_confidence: float

    outcome_label: str       # TP / FP / FN / WEAK
    correct_direction: bool


@dataclass
class MetaCalibrationOutputV2:
    conf_scales: dict       # {group: float}
    conf_caps_up: dict      # {group: float}
    conf_caps_down: dict    # {group: float}

    group_effectiveness: dict
    rationale: list
    audit: dict


@dataclass
class MetaCalibrationSnapshotV2:
    """Stored per-horizon V2 result for pipeline consumption."""
    horizon: str
    conf_scales: dict       # {group: float}
    conf_caps_up: dict      # {group: float}
    conf_caps_down: dict    # {group: float}
    group_effectiveness: dict
    rationale: list
    updated_at: str = ""


def resolve_state_group(interaction_state: str) -> str:
    """Map an interaction_state to its V2 group."""
    return GROUP_FOR_STATE.get(interaction_state, "range")


# ── V2 Engine ──

class MetaCalibrationLayerV2:

    def fit(
        self,
        rows: list[MetaCalibrationRowV2],
        horizon: str,
        v1_scale: float | None = None,
    ) -> MetaCalibrationOutputV2 | None:
        """
        Fit per-horizon × per-group meta-calibration.
        v1_scale: the current V1 global scale for this horizon (used as base).
        Returns None if insufficient data.
        """
        if len(rows) < META_MIN_SAMPLES_TOTAL:
            return None

        base = v1_scale if v1_scale is not None else BASE_CONF_SCALE.get(horizon, 0.60)

        grouped = self._group_rows(rows)
        effectiveness = self._evaluate_group_effectiveness(grouped)

        groups_with_data = sum(
            1 for v in effectiveness.values()
            if v.get("verdict") != "insufficient_data"
        )
        if groups_with_data < META_V2_MIN_EFFECTIVE_GROUPS:
            return None

        raw_scales = self._derive_group_scales(effectiveness, base)
        raw_caps_up, raw_caps_down = self._derive_group_caps(effectiveness)

        # Guardrail: enforce group consistency
        scales = self._enforce_consistency(raw_scales)

        # Guardrail: clamp relative to V1
        for g in ALL_GROUPS:
            if g in scales:
                scales[g] = self._clamp_relative_to_v1(scales[g], base)

        # Guardrail: global cap bounds
        caps_up = {g: min(v, META_CONF_CAP_UP_MAX) for g, v in raw_caps_up.items()}
        caps_down = {g: max(v, META_CONF_CAP_DOWN_MIN) for g, v in raw_caps_down.items()}

        rationale = self._build_rationale(effectiveness, horizon, scales, base)

        return MetaCalibrationOutputV2(
            conf_scales={g: round(v, 4) for g, v in scales.items()},
            conf_caps_up={g: round(v, 4) for g, v in caps_up.items()},
            conf_caps_down={g: round(v, 4) for g, v in caps_down.items()},
            group_effectiveness=effectiveness,
            rationale=rationale,
            audit={
                "total_rows": len(rows),
                "groups_with_data": groups_with_data,
                "horizon": horizon,
                "v1_base": round(base, 4),
            },
        )

    @staticmethod
    def smooth_update(
        old: MetaCalibrationSnapshotV2,
        new_output: MetaCalibrationOutputV2,
    ) -> MetaCalibrationSnapshotV2:
        """EMA-smooth per-group, with step limit + freeze protection."""
        def _smooth(old_val: float, new_val: float) -> float:
            step = _clamp(new_val - old_val, -META_V2_MAX_STEP, META_V2_MAX_STEP)
            updated = old_val + META_V2_LR * step
            smoothed = META_V2_EMA_ALPHA * old_val + (1 - META_V2_EMA_ALPHA) * updated
            if abs(smoothed - old_val) > META_V2_FREEZE_DELTA:
                return old_val
            return round(smoothed, 4)

        new_scales = {}
        new_caps_up = {}
        new_caps_down = {}

        for g in ALL_GROUPS:
            old_s = old.conf_scales.get(g)
            new_s = new_output.conf_scales.get(g)
            if old_s is not None and new_s is not None:
                new_scales[g] = _smooth(old_s, new_s)
            elif new_s is not None:
                new_scales[g] = new_s
            elif old_s is not None:
                new_scales[g] = old_s

            old_cu = old.conf_caps_up.get(g)
            new_cu = new_output.conf_caps_up.get(g)
            if old_cu is not None and new_cu is not None:
                new_caps_up[g] = _smooth(old_cu, new_cu)
            else:
                new_caps_up[g] = new_cu or old_cu or V2_GROUP_CAPS.get(g, {}).get("up", 0.10)

            old_cd = old.conf_caps_down.get(g)
            new_cd = new_output.conf_caps_down.get(g)
            if old_cd is not None and new_cd is not None:
                new_caps_down[g] = _smooth(old_cd, new_cd)
            else:
                new_caps_down[g] = new_cd or old_cd or V2_GROUP_CAPS.get(g, {}).get("down", -0.12)

        return MetaCalibrationSnapshotV2(
            horizon=old.horizon,
            conf_scales=new_scales,
            conf_caps_up=new_caps_up,
            conf_caps_down=new_caps_down,
            group_effectiveness=new_output.group_effectiveness,
            rationale=new_output.rationale,
        )

    @staticmethod
    def default_snapshot(horizon: str) -> MetaCalibrationSnapshotV2:
        """Safe defaults for a horizon, derived from V1 base + group offsets."""
        base = BASE_CONF_SCALE.get(horizon, 0.60)
        return MetaCalibrationSnapshotV2(
            horizon=horizon,
            conf_scales={g: round(base + V2_GROUP_OFFSETS[g], 4) for g in ALL_GROUPS},
            conf_caps_up={g: V2_GROUP_CAPS[g]["up"] for g in ALL_GROUPS},
            conf_caps_down={g: V2_GROUP_CAPS[g]["down"] for g in ALL_GROUPS},
            group_effectiveness={},
            rationale=[f"default V2 — base={base:.2f}, offsets applied"],
        )

    @staticmethod
    def compute_blend(v1_scale: float, v2_group_scale: float, blend: float) -> float:
        """Non-linear blend: blend ** 1.2 to dampen early V2 effects."""
        effective_blend = blend ** 1.2
        return round((1 - effective_blend) * v1_scale + effective_blend * v2_group_scale, 4)

    @staticmethod
    def compute_drift(old: MetaCalibrationSnapshotV2, new: MetaCalibrationSnapshotV2) -> dict:
        """Compute drift metrics between two snapshots."""
        drift = {}
        for g in ALL_GROUPS:
            old_s = old.conf_scales.get(g, 0)
            new_s = new.conf_scales.get(g, 0)
            drift[g] = round(abs(new_s - old_s), 4)
        max_drift = max(drift.values()) if drift else 0.0
        return {"per_group": drift, "max_drift": round(max_drift, 4)}

    # ── Internal ──

    @staticmethod
    def _group_rows(rows: list[MetaCalibrationRowV2]) -> dict:
        """Group rows by state_group."""
        grouped = {}
        for r in rows:
            grouped.setdefault(r.state_group, []).append(r)
        return grouped

    @staticmethod
    def _evaluate_group_effectiveness(grouped: dict) -> dict:
        out = {}
        for group in ALL_GROUPS:
            rows = grouped.get(group, [])
            if len(rows) < META_V2_MIN_SAMPLES_PER_GROUP:
                out[group] = {"verdict": "insufficient_data", "n": len(rows)}
                continue

            acc = _mean([1 if r.correct_direction else 0 for r in rows])
            fp_rate = _mean([1 if r.outcome_label == "FP" else 0 for r in rows])
            avg_conf_mod = _mean([r.applied_confidence_modifier for r in rows])
            impact = round(avg_conf_mod * len(rows) / max(1, len(rows)), 4)

            if acc > 0.60 and fp_rate < 0.35:
                verdict = "effective"
            elif acc < 0.45 or fp_rate > 0.50:
                verdict = "harmful"
            else:
                verdict = "neutral"

            out[group] = {
                "accuracy": round(acc, 4),
                "fp_rate": round(fp_rate, 4),
                "avg_conf_modifier": round(avg_conf_mod, 4),
                "impact": impact,
                "n": len(rows),
                "verdict": verdict,
            }
        return out

    @staticmethod
    def _derive_group_scales(effectiveness: dict, v1_base: float) -> dict:
        """Rule-based scale derivation relative to V1 base."""
        scales = {}
        for g in ALL_GROUPS:
            eff = effectiveness.get(g, {})
            base = v1_base + V2_GROUP_OFFSETS.get(g, 0.0)
            delta = 0.0

            if eff.get("verdict") == "insufficient_data":
                scales[g] = base
                continue

            acc = eff.get("accuracy", 0.5)
            fp = eff.get("fp_rate", 0.5)

            if g == "aligned":
                if acc > 0.60 and fp < 0.25:
                    delta += 0.02
                elif acc < 0.52:
                    delta -= 0.02

            elif g == "fragile":
                if fp > 0.35:
                    delta -= 0.02
                elif acc > 0.58:
                    delta += 0.01

            elif g == "conflict":
                if fp > 0.45:
                    delta += 0.02
                elif fp < 0.30:
                    delta -= 0.01

            elif g == "range":
                if fp > 0.40:
                    delta += 0.015
                elif acc > 0.55:
                    delta -= 0.01

            scales[g] = _clamp(base + delta, META_CONF_SCALE_MIN, META_CONF_SCALE_MAX)
        return scales

    @staticmethod
    def _derive_group_caps(effectiveness: dict) -> tuple:
        """Per-group caps, starting from defaults and adjusting by effectiveness."""
        caps_up = {}
        caps_down = {}
        for g in ALL_GROUPS:
            eff = effectiveness.get(g, {})
            base_up = V2_GROUP_CAPS[g]["up"]
            base_down = V2_GROUP_CAPS[g]["down"]

            if eff.get("verdict") != "insufficient_data":
                acc = eff.get("accuracy", 0.5)
                fp = eff.get("fp_rate", 0.5)
                # Good accuracy → slightly wider cap_up
                if acc > 0.65:
                    base_up = min(base_up + 0.02, META_CONF_CAP_UP_MAX)
                # High FP → tighter cap_down
                if fp > 0.45:
                    base_down = max(base_down - 0.02, META_CONF_CAP_DOWN_MIN)

            caps_up[g] = round(base_up, 4)
            caps_down[g] = round(base_down, 4)

        return caps_up, caps_down

    @staticmethod
    def _enforce_consistency(scales: dict) -> dict:
        """
        Enforce group ordering invariant:
          scale_aligned ≥ scale_fragile ≥ scale_range
        Conflict is independent (can be higher than aligned because
        it amplifies a negative modifier, not a positive one).
        """
        s = dict(scales)
        # aligned ≥ fragile
        if s.get("fragile", 0) > s.get("aligned", 0):
            s["fragile"] = s["aligned"]
        # fragile ≥ range
        if s.get("range", 0) > s.get("fragile", 0):
            s["range"] = s["fragile"]
        return s

    @staticmethod
    def _clamp_relative_to_v1(scale_v2: float, v1_base: float) -> float:
        """
        Guard: |scale_v2 - v1| ≤ 0.15 AND scale_v2/v1 ≤ 1.25
        """
        # Absolute guard
        clamped = _clamp(scale_v2, v1_base - 0.15, v1_base + 0.15)
        # Relative guard
        if v1_base > 0:
            ratio = clamped / v1_base
            if ratio > META_V2_MAX_RATIO_TO_V1:
                clamped = v1_base * META_V2_MAX_RATIO_TO_V1
            elif ratio < 1 / META_V2_MAX_RATIO_TO_V1:
                clamped = v1_base / META_V2_MAX_RATIO_TO_V1
        return round(clamped, 4)

    @staticmethod
    def _build_rationale(
        effectiveness: dict, horizon: str, scales: dict, v1_base: float,
    ) -> list:
        out = [f"V2 horizon={horizon}, v1_base={v1_base:.3f}"]
        for g in ALL_GROUPS:
            eff = effectiveness.get(g, {})
            sc = scales.get(g, 0)
            delta = round(sc - v1_base, 3)
            if eff.get("verdict") == "insufficient_data":
                out.append(f"  {g}: n={eff.get('n', 0)} insufficient → scale={sc:.3f} (Δ={delta:+.3f})")
            else:
                out.append(
                    f"  {g}: acc={eff['accuracy']:.2f} fp={eff['fp_rate']:.2f} "
                    f"n={eff['n']} → {eff['verdict']} → scale={sc:.3f} (Δ={delta:+.3f})"
                )
        return out
