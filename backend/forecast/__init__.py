"""
Forecast Pipeline Contracts
============================
Pydantic models for forecast records and evaluation results.
All fields are strictly typed — no optional core fields.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
from enum import Enum


class Horizon(str, Enum):
    H24 = "24H"
    D7 = "7D"
    D30 = "30D"


HORIZON_DAYS = {Horizon.H24: 1, Horizon.D7: 7, Horizon.D30: 30}

# Outcome thresholds per horizon (error % for WEAK vs FP)
OUTCOME_THRESHOLD = {Horizon.H24: 1.5, Horizon.D7: 3.0, Horizon.D30: 6.0}


class OutcomeLabel(str, Enum):
    TP = "TP"
    FP = "FP"
    WEAK = "WEAK"
    FN = "FN"
    NO_DATA = "NO_DATA"


class EvalResult(BaseModel):
    evaluatedAt: int  # ms timestamp
    actualPriceAtEval: float
    errorPct: float
    outcome: OutcomeLabel
    reason: Optional[str] = None


class ForecastRecord(BaseModel):
    id: str
    asset: str
    symbol: str
    horizon: Horizon
    horizonDays: int
    runId: str  # Groups all forecasts from one scheduler run
    createdAt: int  # ms timestamp
    createdBucket: str  # YYYY-MM-DD UTC
    evaluateAfter: int  # ms timestamp
    entryPrice: float
    targetPrice: float
    expectedMovePct: float
    direction: str  # LONG / SHORT / NEUTRAL
    confidence: float  # 0..1
    confidenceRaw: float
    modelVersion: str
    featuresHash: str
    immutableHash: str
    dataWindowEnd: int  # ms timestamp
    source: str = "scheduler"

    # v4: Band architecture fields (30D)
    forecastType: str = "point"  # "point" or "band"
    medianTarget: Optional[float] = None
    bandCoreLow: Optional[float] = None
    bandCoreHigh: Optional[float] = None
    bandWideLow: Optional[float] = None
    bandWideHigh: Optional[float] = None

    # Eval fields — null at creation
    evaluated: bool = False
    outcome: Optional[EvalResult] = None

    # v4.1: 5-state direction + calibrated confidence + audit
    directionClass: Optional[str] = None  # STRONG_BULL/MILD_BULL/NEUTRAL/MILD_BEAR/STRONG_BEAR
    confidenceDirection: Optional[float] = None  # P(direction correct)
    confidenceTarget: Optional[float] = None     # P(target hit)
    degraded: bool = False
    audit: Optional[dict] = None

    # v4.4: Scenario Engine (30D)
    scenarios: Optional[dict] = None

    def to_mongo(self) -> dict:
        d = self.model_dump()
        # Store outcome as nested dict, not as OutcomeLabel enum
        if d.get("outcome") and isinstance(d["outcome"], dict):
            if "outcome" in d["outcome"]:
                d["outcome"]["outcome"] = d["outcome"]["outcome"]
        return d
