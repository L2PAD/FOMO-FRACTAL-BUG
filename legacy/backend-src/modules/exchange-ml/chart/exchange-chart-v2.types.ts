/**
 * Exchange Chart V2 Types
 * ========================
 * 
 * BLOCK E1: Production-grade types for Exchange UI
 * Symmetric with Sentiment V2 architecture
 */

export type Horizon = '24H' | '7D' | '30D';
export type ChartWindow = '30d' | '90d';

export interface ExchangeChartV2Query {
  symbol: string;
  horizon: Horizon;
  window?: ChartWindow;
}

export interface ChartCandle {
  time: number;  // unix seconds
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface ProjectionPoint {
  time: number;
  value: number;
}

export interface BandPoint {
  time: number;
  low: number;
  high: number;
}

export interface ChartMarker {
  type: 'SAFE_MODE' | 'CALIBRATION' | 'URI_ADJUSTMENT' | 'CAPITAL_GATE';
  time: number;
  text: string;
}

export interface ExchangeChartMeta {
  symbol: string;
  horizon: Horizon;
  generatedAt: string;
  safeMode: boolean;
  uriLevel: string;
  moduleVersion: string;
  frozen: boolean;
}

export interface ExchangeReliabilityDTO {
  rawConfidence: number;
  uriMultiplier: number;
  calibrationMultiplier: number;
  capitalMultiplier: number;
  finalConfidence: number;
}

export interface ExchangeForecastDTO {
  entry: number;
  targetRaw: number;
  targetFinal: number;
  bandLow: number;
  bandHigh: number;
  expectedMovePct: number;
  direction: 'LONG' | 'SHORT' | 'NEUTRAL';
  evaluateAt: string;
}

export interface ExchangeChartDTO {
  candles: ChartCandle[];
  projectionLine: ProjectionPoint[];
  bandArea: BandPoint[];
  markers: ChartMarker[];
}

// E2: Signal Breakdown Types
export interface ExchangeExplainCore {
  signalScore: number;
  regime: string;
  rawConfidence: number;
  notes: string[];
}

export interface ExchangeExplainAdjustments {
  uriMultiplier: number;
  calibrationMultiplier: number;
  capitalMultiplier: number;
  finalConfidence: number;
}

export interface ExchangeExplainSafety {
  safeMode: boolean;
  safeModeReason?: string;
  uriLevel: string;
  trainingBlocked: boolean;
  promotionBlocked: boolean;
}

export interface ExchangeExplainBlock {
  core: ExchangeExplainCore;
  adjustments: ExchangeExplainAdjustments;
  safety: ExchangeExplainSafety;
}

export interface ExchangeChartV2Response {
  ok: true;
  meta: ExchangeChartMeta;
  reliability: ExchangeReliabilityDTO;
  forecast: ExchangeForecastDTO;
  chart: ExchangeChartDTO;
  explain: ExchangeExplainBlock;
}

// E4: Performance Types
export type OutcomeType = 'TP' | 'FP' | 'FN' | 'WEAK' | 'VOIDED' | 'PENDING' | 'OVERDUE';

export interface ExchangePerformanceRow {
  createdAt: string;
  evaluateAt: string;
  horizon: Horizon;
  symbol: string;
  entry: number;
  actual: number | null;
  rawTarget: number;
  finalTarget: number;
  rawConfidence: number;
  finalConfidence: number;
  direction: 'LONG' | 'SHORT' | 'NEUTRAL';
  outcome: OutcomeType;
  flags: string[];
}

export interface ExchangePerformanceResponse {
  ok: true;
  symbol: string;
  horizon: Horizon;
  rows: ExchangePerformanceRow[];
  summary: {
    total: number;
    evaluated: number;
    wins: number;
    losses: number;
    weak: number;
    fn: number;
    pending: number;
    overdue: number;
    winRate: number;
    avgReturn: number;
  };
}

// E5: Top Alts Types
export interface ExchangeTopAltExplain {
  signalScore: number;
  rawConfidence: number;
  uriMultiplier: number;
  calibrationMultiplier: number;
  capitalMultiplier: number;
  finalConfidence: number;
  flags: {
    safeMode: boolean;
    uriAdjustment: boolean;
    capitalGate: boolean;
  };
}

export interface ExchangeTopAltRow {
  symbol: string;
  score: number;
  direction: 'LONG' | 'SHORT' | 'NEUTRAL';
  expectedMovePctRaw: number;
  expectedMovePctFinal: number;
  confidenceRaw: number;
  confidenceFinal: number;
  flags: string[];
  explain: ExchangeTopAltExplain;
}

export interface ExchangeTopAltsResponse {
  ok: true;
  horizon: Horizon;
  safeMode: boolean;
  uriLevel: string;
  rows: ExchangeTopAltRow[];
  activeCount: number;
}

// E2.2: Equity Curve Types
export interface ExchangeEquityPoint {
  time: string;
  equity: number;
}

export interface ExchangeEquityStats {
  totalReturn: number;
  maxDD: number;
  sharpe: number;
  trades: number;
}

export interface ExchangeEquityResponse {
  ok: true;
  symbol: string;
  period: string;
  points: ExchangeEquityPoint[];
  stats: ExchangeEquityStats;
}
