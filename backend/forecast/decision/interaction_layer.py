"""
Interaction Layer V1 — Structure × Regime × Scenario
=======================================================
Second-order intelligence: cross-checks agreement between layers
and modulates decision confidence, scenario weights, and directional bias.

Pipeline:
  Structure → Regime → Scenario → **Interaction Layer** → Decision Layer

Outputs 3 modifiers (each independently toggleable via feature flags):
  1. confidence_modifier     — adjusts calibrated_confidence
  2. scenario modifiers      — reweights bullish/base/bearish probs
  3. decision_bias_modifier  — adjusts directional score threshold
"""

from dataclasses import dataclass


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


@dataclass
class InteractionInputs:
    structure_state: str
    structure_clarity: float
    bullish_structure: float
    bearish_structure: float

    dominant_regime: str
    regime_entropy: float

    dominant_scenario: str
    bullish_prob: float
    base_prob: float
    bearish_prob: float

    calibrated_confidence: float
    expected_move_pct: float


@dataclass
class InteractionOutput:
    interaction_state: str
    alignment_score: float
    conflict_score: float

    decision_bias_modifier: float
    confidence_modifier: float

    bullish_scenario_modifier: float
    base_scenario_modifier: float
    bearish_scenario_modifier: float

    rationale: list
    audit: dict


class InteractionLayerV1:

    def evaluate(self, x: InteractionInputs) -> InteractionOutput:
        sp = self._structure_polarity(x)
        rp = self._regime_polarity(x)
        scen_p = x.dominant_scenario

        state = self._interaction_state(x, sp, rp, scen_p)
        align = self._alignment_score(x, sp, rp, scen_p)
        conflict = self._conflict_score(x, sp, rp, scen_p)

        decision_bias = self._decision_bias_modifier(state, align, conflict)
        conf_mod = self._confidence_modifier(align, conflict)
        scen_mods = self._scenario_modifiers(state, align, conflict)
        rationale = self._build_rationale(state, sp, rp, scen_p, align, conflict)

        return InteractionOutput(
            interaction_state=state,
            alignment_score=round(align, 4),
            conflict_score=round(conflict, 4),
            decision_bias_modifier=round(decision_bias, 4),
            confidence_modifier=round(conf_mod, 4),
            bullish_scenario_modifier=round(scen_mods["bullish"], 4),
            base_scenario_modifier=round(scen_mods["base"], 4),
            bearish_scenario_modifier=round(scen_mods["bearish"], 4),
            rationale=rationale,
            audit={
                "structure_polarity": sp,
                "regime_polarity": rp,
                "scenario_polarity": scen_p,
            },
        )

    # ── Polarity classifiers ──

    @staticmethod
    def _structure_polarity(x: InteractionInputs) -> str:
        diff = x.bullish_structure - x.bearish_structure
        if diff > 0.15:
            return "bullish"
        if diff < -0.15:
            return "bearish"
        return "mixed"

    @staticmethod
    def _regime_polarity(x: InteractionInputs) -> str:
        r = x.dominant_regime.lower()
        if r in ("trend", "pullback"):
            return "bullish"
        if r == "breakdown":
            return "bearish"
        return "mixed"

    # ── Interaction state ──

    @staticmethod
    def _interaction_state(
        x: InteractionInputs, sp: str, rp: str, scen_p: str,
    ) -> str:
        # Aligned states
        if sp == "bullish" and rp == "bullish" and scen_p == "bullish":
            return "aligned_bullish"
        if sp == "bearish" and rp == "bearish" and scen_p == "bearish":
            return "aligned_bearish"

        # Fragile states
        if sp == "bullish" and scen_p == "bullish" and rp == "mixed":
            return "fragile_bullish"
        if sp == "bearish" and scen_p == "bearish" and rp == "mixed":
            return "fragile_bearish"

        # Transition conflict
        if sp != "mixed" and scen_p != "base" and sp != scen_p:
            return "transition_conflict"

        # Range mixed
        if x.structure_state == "range" or scen_p == "base":
            return "range_mixed"

        return "mixed_unclear"

    # ── Scores ──

    @staticmethod
    def _alignment_score(
        x: InteractionInputs, sp: str, rp: str, scen_p: str,
    ) -> float:
        score = 0.0
        if sp == scen_p and scen_p != "base":
            score += 0.4
        if rp == scen_p and scen_p != "base":
            score += 0.3
        score += 0.2 * x.structure_clarity
        score += 0.1 * (1.0 - x.regime_entropy)
        return _clamp(score)

    @staticmethod
    def _conflict_score(
        x: InteractionInputs, sp: str, rp: str, scen_p: str,
    ) -> float:
        score = 0.0
        if sp != "mixed" and scen_p != "base" and sp != scen_p:
            score += 0.45
        if rp != "mixed" and scen_p != "base" and rp != scen_p:
            score += 0.30
        score += 0.15 * x.regime_entropy
        score += 0.10 * (1.0 - x.structure_clarity)
        return _clamp(score)

    # ── Modifiers ──

    @staticmethod
    def _decision_bias_modifier(state: str, align: float, conflict: float) -> float:
        if state in ("aligned_bullish", "aligned_bearish"):
            mod = 0.08 + 0.10 * align
        elif state in ("fragile_bullish", "fragile_bearish"):
            mod = 0.03 + 0.05 * align
        elif state == "transition_conflict":
            mod = -0.08 - 0.08 * conflict
        else:
            mod = -0.05 - 0.05 * conflict
        return max(-0.15, min(0.18, mod))

    @staticmethod
    def _confidence_modifier(align: float, conflict: float) -> float:
        mod = 0.12 * align - 0.18 * conflict
        return max(-0.20, min(0.15, mod))

    @staticmethod
    def _scenario_modifiers(state: str, align: float, conflict: float) -> dict:
        m = {"bullish": 0.0, "base": 0.0, "bearish": 0.0}

        if state == "aligned_bullish":
            m["bullish"] = 0.08 * align
            m["base"] = -0.03 * align
            m["bearish"] = -0.05 * align

        elif state == "aligned_bearish":
            m["bearish"] = 0.08 * align
            m["base"] = -0.03 * align
            m["bullish"] = -0.05 * align

        elif state == "fragile_bullish":
            m["bullish"] = 0.04 * align
            m["base"] = 0.01
            m["bearish"] = -0.03 * align

        elif state == "fragile_bearish":
            m["bearish"] = 0.04 * align
            m["base"] = 0.01
            m["bullish"] = -0.03 * align

        elif state == "transition_conflict":
            m["base"] = 0.06 + 0.04 * conflict
            m["bullish"] = -(0.03 + 0.03 * conflict)
            m["bearish"] = -(0.03 + 0.03 * conflict)

        else:  # range_mixed, mixed_unclear
            m["base"] = 0.03 + 0.02 * conflict
            m["bullish"] = -(0.015 + 0.01 * conflict)
            m["bearish"] = -(0.015 + 0.01 * conflict)

        # Clamp individual modifiers
        for k in m:
            m[k] = max(-0.10, min(0.10, m[k]))

        return m

    # ── Rationale ──

    @staticmethod
    def _build_rationale(
        state: str, sp: str, rp: str, scen_p: str,
        align: float, conflict: float,
    ) -> list:
        out = []
        if state.startswith("aligned"):
            out.append(f"layers aligned ({sp} structure + {rp} regime + {scen_p} scenario)")
            if align > 0.6:
                out.append("strong cross-layer agreement")
        elif state.startswith("fragile"):
            out.append(f"{sp} structure + {scen_p} scenario, but regime uncertain")
        elif state == "transition_conflict":
            out.append(f"conflict: {sp} structure vs {scen_p} scenario")
            if conflict > 0.5:
                out.append("significant cross-layer disagreement")
        else:
            out.append(f"mixed state: no clear alignment (struct={sp}, regime={rp}, scen={scen_p})")
        return out
