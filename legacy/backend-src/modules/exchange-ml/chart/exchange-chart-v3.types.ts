/**
 * Exchange Chart V3 Types — FINAL
 */

export interface ForecastPoint {
  madeAtTs: number;
  targetDateTs: number;
  entryPrice: number;
  targetPrice: number;
  expectedMovePct: number;
  confidence: number;
  direction: 'LONG' | 'SHORT' | 'NEUTRAL';
}

export interface RealCandle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface ExchangeChartV3Query {
  asset: string;
  horizon: '1D' | '7D' | '30D';
}

export interface ExchangeChartV3Response {
  ok: boolean;
  symbol: string;
  nowTs: number;
  horizonDays: number;
  realCandles: RealCandle[];
  forecastPoints: ForecastPoint[];
  overlay7DPoints?: ForecastPoint[];
  target: number;
  confidence: number;
  direction: 'LONG' | 'SHORT' | 'NEUTRAL';
  source: 'db' | 'fallback';
  meta: {
    stability: string;
    stabilityStddev: number;
    totalForecasts: number;
    uniqueTargetDates: number;
  };
}
