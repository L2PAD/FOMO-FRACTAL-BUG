"""
Decision Layer V1 — Contracts
==============================
Input/output data contracts for the decision engine.
"""

from dataclasses import dataclass, field
from typing import Literal

DecisionDirection = Literal["LONG", "SHORT", "NEUTRAL"]
DecisionMode = Literal["directional", "cautious_directional", "neutral_filter"]


@dataclass
class DecisionInputs:
    asset: str
    horizon: str

    calibrated_confidence: float
    forecast_direction: Literal["bullish", "neutral", "bearish"]

    regime_entropy: float
    regime_gap: float
    dominant_regime: str

    structure_strength: float
    bullish_structure: float
    bearish_structure: float

    context_alignment: float
    negative_context: float

    expected_move_pct: float

    dominant_scenario: Literal["bullish", "base", "bearish"]
    dominant_scenario_prob: float
    bullish_prob: float
    base_prob: float
    bearish_prob: float


@dataclass
class DecisionOutput:
    direction: DecisionDirection
    decision_strength: float
    decision_confidence: float
    decision_mode: DecisionMode
    rationale: list
    audit: dict
