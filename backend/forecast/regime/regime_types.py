"""
Regime Types
=============
Strict type definitions for the Regime Engine V2.
"""

from typing import Literal

RegimeName = Literal["trend", "range", "pullback", "transition", "breakdown"]

REGIME_NAMES: list[str] = ["trend", "range", "pullback", "transition", "breakdown"]
