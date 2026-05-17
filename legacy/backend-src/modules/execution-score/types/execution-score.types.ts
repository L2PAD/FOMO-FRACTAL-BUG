/**
 * Execution Score Types
 */

export type Direction = 'LONG' | 'SHORT';
export type Regime = 'TREND' | 'RANGE' | 'TRANSITION';
export type NarrativePhase = 'EARLY' | 'EXPANDING' | 'SATURATED' | 'EXHAUSTED';
export type EntryPosition = 'INSIDE_OPTIMAL' | 'EDGE_OPTIMAL' | 'OUTSIDE_OPTIMAL';
export type OpportunityCostReason = 'WAIT_TOO_LONG' | 'LIMIT_NOT_FILLED' | 'LATE_ENTRY' | 'NONE';

export interface ExecutionTrace {
  marketId: string;
  asset: string;
  timestamp: string;
  direction: Direction;
  recommendation: {
    action: string;
    entryStyle: string;
    confidence: number;
    edge: number;
  };
  execution: {
    entryStyle: string;
    slippageRisk: number;
    entryQualityScore: number;
    spreadRegime: string;
    depthQuality: string;
  };
  context: {
    regime: Regime;
    narrativePhase: NarrativePhase;
    volatility: number;
    repricing: string;
  };
  marketProb: number;
}

export interface MarketPath {
  t0: number;
  t5m: number;
  t15m: number;
  t1h: number;
  t4h: number;
  t24h: number;
  high: number;
  low: number;
  final: number;
  edgeWindows: EdgeWindow[];
}

export interface EdgeWindow {
  startMin: number;
  endMin: number;
  avgEdge: number;
  available: boolean;
}

export interface EntryEvaluation {
  entryScore: number;
  quality: 'EXCELLENT' | 'GOOD' | 'OK' | 'BAD';
  optimalZoneLow: number;
  optimalZoneHigh: number;
  actualEntry: number;
  bestPossibleEntry: number;
  position: EntryPosition;
  improvementPotential: number;
}

export interface TimingEvaluation {
  timingScore: number;
  quality: 'EXCELLENT' | 'GOOD' | 'OK' | 'LATE' | 'BAD';
  wasEarly: boolean;
  wasLate: boolean;
  missedBetterWindow: boolean;
  edgeDecayRate: number;
  optimalWindowMinutes: number;
}

export interface SlippageEvaluation {
  expected: number;
  actual: number;
  leakage: number;
  leakageScore: number;
}

export interface OpportunityCost {
  missedMove: number;
  missedReturn: number;
  reason: OpportunityCostReason;
  costScore: number;
}

export interface ExecutionScoreResult {
  executionScore: number;
  executionGrade: string;
  entry: EntryEvaluation;
  timing: TimingEvaluation;
  slippage: SlippageEvaluation;
  opportunity: OpportunityCost;
  context: {
    regime: Regime;
    narrativePhase: NarrativePhase;
    direction: Direction;
  };
  lessons: string[];
}

export interface StylePerformance {
  style: string;
  avgScore: number;
  count: number;
  winRate: number;
  avgLeakage: number;
  missRate: number;
  bestContext: string;
  worstContext: string;
}
