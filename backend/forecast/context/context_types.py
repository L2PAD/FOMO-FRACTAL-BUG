"""
Context Types
==============
Strict type definitions for the Market Context Layer.
"""

from typing import Literal

VolState = Literal["compressed", "normal", "expanded"]

Phase = Literal[
    "continuation",
    "late_trend",
    "pullback",
    "unstable_transition",
    "breakdown",
    "recovery_attempt",
    "mixed_range",
]
