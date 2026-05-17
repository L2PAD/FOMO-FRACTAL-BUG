/**
 * Engine Backtest Contracts — Phase BT
 * ======================================
 * Types for backtest module.
 */

export type Horizon = 7 | 14 | 30 | 90;
export type BacktestMode = 'BUY_ONLY' | 'BUY_NEUTRAL';

export interface BacktestRunRequest {
  chainId: number;
  from: string;           // ISO date "2024-01-01"
  to: string;
  stepDays: number;       // 1 or 7
  window: '24h' | '7d' | '30d';
  topK: number;           // 5..50
  mode: BacktestMode;
  horizons: Horizon[];    // [7,14,30,90]
}

export interface BacktestPoint {
  ts: string;
  picks: { symbol: string; tokenAddress: string | null; score: number; action: string }[];
  scoreAvg: number;
  coverage: number;
  actionable: boolean;
  returnsByH: Record<number, number | null>;
}

export interface HorizonResult {
  hitRate: number;
  avgReturn: number;
  equityFinal: number;
  maxDD: number;
  samples: number;
}

export interface BacktestSummary {
  chainId: number;
  from: string;
  to: string;
  stepDays: number;
  window: string;
  topK: number;
  mode: BacktestMode;
  horizons: Horizon[];
  points: number;
  actionableRate: number;
  coverage: number;
  byH: Record<number, HorizonResult>;
  // BT5: structured table for quick analysis
  table: BacktestTableRow[];
  generatedAt: string;
  dataWarning: string | null;
}

export interface BacktestTableRow {
  config: string;
  h7: HorizonResult | null;
  h14: HorizonResult | null;
  h30: HorizonResult | null;
  h90: HorizonResult | null;
}
