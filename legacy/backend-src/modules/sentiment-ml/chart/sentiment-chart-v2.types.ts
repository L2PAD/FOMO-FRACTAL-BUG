/**
 * Sentiment Chart V2 Types
 * ========================
 * 
 * BLOCK P1.1: Production-grade types for Sentiment UI
 * Symmetric with Exchange v4 architecture
 */

export type Horizon = '24H' | '7D' | '30D';
export type ChartWindow = '30d' | '90d';

export interface SentimentChartQuery {
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
  type: 'SAFE_MODE' | 'CALIBRATION' | 'URI_ADJUSTMENT';
  time: number;
  text: string;
}

export interface SentimentChartMeta {
  symbol: string;
  horizon: Horizon;
  generatedAt: string;
  safeMode: boolean;
  uriLevel: string;
  moduleVersion: string;
}

export interface SentimentReliabilityDTO {
  rawConfidence: number;
  uriMultiplier: number;
  calibrationMultiplier: number;
  capitalMultiplier: number;
  finalConfidence: number;
}

export interface SentimentForecastDTO {
  entry: number;
  target: number;
  bandLow: number;
  bandHigh: number;
  expectedMovePct: number;
  direction: 'LONG' | 'SHORT' | 'NEUTRAL';
}

export interface SentimentChartDTO {
  candles: ChartCandle[];
  projectionLine: ProjectionPoint[];
  bandArea: BandPoint[];
  markers: ChartMarker[];
}

// P2: Signal Breakdown Types
export interface SentimentExplainCore {
  bias: number;
  score: number;
  rawConfidence: number;
  eventsCount: number;
  quality: 'OK' | 'LOW_VOLUME';
}

export interface SentimentExplainAdjustments {
  uriMultiplier: number;
  calibrationMultiplier: number;
  sizeMultiplier: number;
  finalConfidence: number;
}

export interface SentimentExplainSafety {
  safeMode: boolean;
  safeModeReason?: string;
  uriLevel: string;
  calibrationStatus: string;
}

export interface SentimentExplainBlock {
  core: SentimentExplainCore;
  adjustments: SentimentExplainAdjustments;
  safety: SentimentExplainSafety;
}

export interface SentimentChartResponse {
  ok: true;
  meta: SentimentChartMeta;
  reliability: SentimentReliabilityDTO;
  forecast: SentimentForecastDTO;
  chart: SentimentChartDTO;
  explain: SentimentExplainBlock;
}

// P1.2: Performance Types
export type OutcomeType = 'TP' | 'FP' | 'FN' | 'WEAK' | 'PENDING' | 'OVERDUE';

export interface SentimentPerformanceRow {
  asOf: string;
  createdAt: string;
  evaluateAt: string;
  horizon: Horizon;
  entry: number;
  actual: number | null;
  rawTarget: number;
  finalTarget: number;
  rawConfidence: number;
  finalConfidence: number;
  direction: 'LONG' | 'SHORT' | 'NEUTRAL';
  outcome: OutcomeType;
  notes: string[];
}

export interface SentimentPerformanceResponse {
  ok: true;
  symbol: string;
  horizon: Horizon;
  rows: SentimentPerformanceRow[];
  summary: {
    total: number;
    wins: number;
    losses: number;
    pending: number;
    evaluated: number;
    overdue: number;
    winRate: number;
    avgReturn: number;
  };
}

// P1.2: Top Alts Types
export interface SentimentTopAltExplain {
  bias: number;
  rawConfidence: number;
  uriMultiplier: number;
  calibrationMultiplier: number;
  finalConfidence: number;
  flags: {
    safeMode: boolean;
    uriAdjustment: boolean;
    lowData: boolean;
  };
}

export interface SentimentTopAltRow {
  symbol: string;
  score: number;
  bias: number;
  direction: 'LONG' | 'SHORT' | 'NEUTRAL';
  expectedMovePctRaw: number;
  expectedMovePctFinal: number;
  confidenceRaw: number;
  confidenceFinal: number;
  flags: string[];
  explain: SentimentTopAltExplain;
}

export interface SentimentTopAltsResponse {
  ok: true;
  horizon: Horizon;
  safeMode: boolean;
  uriLevel: string;
  rows: SentimentTopAltRow[];
  activeCount: number;
}

// P2.2: Equity Curve Types
export interface SentimentEquityPoint {
  time: string;
  equity: number;
}

export interface SentimentEquityStats {
  totalReturn: number;
  maxDD: number;
  sharpe: number;
  trades: number;
}

export interface SentimentEquityResponse {
  ok: true;
  symbol: string;
  period: string;
  points: SentimentEquityPoint[];
  stats: SentimentEquityStats;
}
