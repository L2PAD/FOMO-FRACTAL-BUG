/**
 * Sentiment Simulation Types
 * ===========================
 * 
 * BLOCK 7+8: Types for walk-forward simulation with CHOP Gate.
 */

import type { ChopConfig } from '../risk/chop.types.js';

export type SimMode = 'RULE' | 'ML';
export type SimWindow = '24H' | '7D' | '30D';

export interface SentimentSimConfig {
  days: number;              // 90 / 180
  window: SimWindow;
  mode: SimMode;
  startCapital: number;      // default 1.0
  feeBps: number;            // e.g. 5 bps
  slippageBps: number;       // e.g. 3 bps
  chopGate: boolean;         // Skip CHOP regime trades (hindsight legacy)
  minBias: number;           // Min |bias| for entry (extra filter)
  regimeFilter: boolean;     // Use proactive regime filter v1.1
  transitionScaling: boolean; // Scale position size in TRANSITION
  // BLOCK 8: Production CHOP Gate v1
  chopV1: boolean;           // Use production CHOP gate (no lookahead)
  chopConfig?: Partial<ChopConfig>; // Custom CHOP thresholds for grid search
}

export interface SimTrade {
  date: Date;
  symbol: string;
  direction: 'LONG' | 'SHORT';
  bias: number;
  entryPrice: number;
  exitPrice: number;
  returnPct: number;
  capitalAfter: number;
  regime?: string;          // Proactive regime at entry
  regimeScore?: number;     // Score 0-1
  sizeMultiplier?: number;  // Position size scaling
  chopTag?: {               // CHOP v1 tag at entry
    isChop: boolean;
    atrPercentile: number;
    rangeN: number;
    slope: number;
    severityScore: number;
  };
}

export interface SimMetrics {
  trades: number;
  wins: number;
  losses: number;
  winRate: number;
  expectancy: number;
  maxDD: number;
  sharpeLike: number;
  equityFinal: number;
  totalReturnPct: number;
}

export interface SimReport {
  config: SentimentSimConfig;
  metrics: SimMetrics;
  equityCurve: Array<{ date: Date; equity: number }>;
  trades: SimTrade[];
  status: 'PASS' | 'FAIL' | 'WARN';
  failReasons: string[];
  regime?: import('./sentiment_sim.regime.js').RegimeReport;
  monteCarlo?: import('./sentiment_sim.montecarlo.js').MonteCarloResult;
  chopStats?: {             // CHOP v1 stats
    skipped: number;
    avgAtrPctl: number;
    avgRangeN: number;
    avgSlope: number;
  };
}

// Targets for 90D baseline
export const SIM_TARGETS = {
  minWinRate: 0.50,
  minExpectancy: 0,
  minSharpe: 0.25,
  maxDD: 0.20,
};

console.log('[Sentiment-ML] Simulation Types loaded (BLOCK 7+8)');
