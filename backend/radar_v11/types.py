"""
ALT RADAR V11 — Types & Contracts (v2 — post quality review)
==============================================================
Strict separation: Spot (Main + Alpha) vs Futures.
No ML status. No debug fields. Only actionable data.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel


class RadarMode(str, Enum):
    SPOT = "spot"
    FUTURES = "futures"


class SpotVenue(str, Enum):
    MAIN = "main"
    ALPHA = "alpha"


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class Verdict(str, Enum):
    BUY = "buy"
    SELL = "sell"
    WATCH = "watch"
    NEUTRAL = "neutral"
    DATA_GAP = "data_gap"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class FuturesBias(str, Enum):
    LONG_BUILD = "long_build"
    SHORT_BUILD = "short_build"
    NEUTRAL = "neutral"


class StructureType(str, Enum):
    COMPRESSION = "compression"
    RANGE = "range"
    HIGHER_LOWS = "higher_lows"
    EXPANSION = "expansion"
    BREAKDOWN = "breakdown"


class MomentumBuild(str, Enum):
    WEAK = "weak"
    BUILDING = "building"
    STRONG = "strong"


class ConvictionTier(str, Enum):
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    NOISE = "noise"


class SqueezeRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class OIShift(str, Enum):
    RISING = "rising"
    FALLING = "falling"
    EXPLOSIVE = "explosive"


class FundingState(str, Enum):
    POSITIVE_HEAVY = "positive_heavy"
    NEGATIVE_HEAVY = "negative_heavy"
    NEUTRAL = "neutral"


# ═══════════════════════════════════════════════════════════════
# SUB-OBJECTS
# ═══════════════════════════════════════════════════════════════

class SpotFeatures(BaseModel):
    compression: float       # 0-1
    volumeBuild: float       # 0-1
    trendAlignment: float    # 0-1
    liquidity: float         # 0-1
    risk: float              # 0-1


class SpotExplain(BaseModel):
    whyNow: str
    invalidation: str
    timeHorizon: str
    oneLiner: Optional[str] = None  # P0.3: Execution-ready summary


class HorizonSignal(BaseModel):
    direction: str          # "long" | "short" | "neutral"
    conviction: int         # 0-100
    label: str              # "0-2d" | "3-7d" | "1-4w"


class HorizonsInfo(BaseModel):
    short: HorizonSignal
    mid: HorizonSignal
    swing: HorizonSignal
    primary: str            # "short" | "mid" | "swing"


class FuturesFeatures(BaseModel):
    oiShift: float           # 0-1
    fundingSkew: float       # -1 to 1
    liquidationDensity: float  # 0-1
    volatilityRegime: float  # 0-1
    risk: float              # 0-1


class FuturesExplain(BaseModel):
    whyNow: str
    invalidation: str
    timeHorizon: str


class DataQualityInfo(BaseModel):
    status: str = "ok"
    missing: List[str] = []


class IntegrityStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    INVALID = "invalid"


class IntegrityInfo(BaseModel):
    status: str                     # "ok" | "degraded" | "invalid"
    reasons: List[str] = []         # short codes
    coveragePct: int = 0            # 0..100
    setupScore: float = 0           # 0..1
    dataFreshnessSec: Optional[int] = None


class PaginationMeta(BaseModel):
    universe: Optional[str] = None
    total: int
    page: int
    pages: int
    limit: int


# ═══════════════════════════════════════════════════════════════
# SPOT RADAR CONTRACT
# ═══════════════════════════════════════════════════════════════

class SpotRadarRow(BaseModel):
    symbol: str
    venue: SpotVenue
    direction: Direction
    verdict: Verdict
    conviction: int           # 0-100
    convictionTier: Optional[str] = None  # A+ / A / B / C / noise
    breakoutProb: int         # 0-100
    structure: StructureType
    momentumBuild: MomentumBuild
    risk: RiskLevel
    features: SpotFeatures
    horizons: Optional[HorizonsInfo] = None
    integrity: Optional[IntegrityInfo] = None
    reasons: List[str]        # min 3, max 7
    explain: SpotExplain
    updatedAt: str
    dataQuality: Optional[DataQualityInfo] = None
    source: Optional[str] = None  # "observations" | "verdict" | "snapshot"
    venueCount: Optional[int] = 1           # P1.1: number of venues with data
    venues: Optional[List[str]] = None      # P1.1: list of venue names
    divergenceScore: float = 0.0            # P1.2: venue divergence 0..1
    divergenceLabel: str = "NONE"           # P1.2: NONE / LOW / MID / HIGH
    divergenceReasons: List[str] = []       # P1.2: human-readable reasons


class SpotRadarResponse(BaseModel):
    ok: bool
    mode: str = "spot"
    venue: str
    count: int
    updatedAt: str
    rows: List[SpotRadarRow]
    meta: PaginationMeta


# ═══════════════════════════════════════════════════════════════
# FUTURES RADAR CONTRACT
# ═══════════════════════════════════════════════════════════════

class FuturesRadarRow(BaseModel):
    symbol: str
    direction: Direction
    bias: FuturesBias
    verdict: Verdict
    conviction: int           # 0-100
    breakoutProb: int         # 0-100
    squeezeRisk: SqueezeRisk
    squeezeRiskScore: float   # 0-1 numeric
    oiShift: OIShift
    fundingState: FundingState
    risk: RiskLevel
    features: FuturesFeatures
    reasons: List[str]        # min 3, max 7
    explain: FuturesExplain
    updatedAt: str
    dataQuality: Optional[DataQualityInfo] = None


class FuturesRadarResponse(BaseModel):
    ok: bool
    mode: str = "futures"
    count: int
    updatedAt: str
    rows: List[FuturesRadarRow]
    meta: PaginationMeta


# ═══════════════════════════════════════════════════════════════
# UNIVERSE RESPONSE
# ═══════════════════════════════════════════════════════════════

class UniverseResponse(BaseModel):
    ok: bool
    mode: str
    spotMainCount: Optional[int] = None
    spotAlphaCount: Optional[int] = None
    futuresCount: Optional[int] = None
    spotMainSymbols: Optional[List[str]] = None
    spotAlphaSymbols: Optional[List[str]] = None
    futuresSymbols: Optional[List[str]] = None
