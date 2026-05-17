/**
 * Sentiment Risk Types
 * =====================
 * 
 * BLOCK 6: Contracts for Capital & Risk Layer.
 */

export type SentWindow = '24H' | '7D' | '30D';
export type SentAction = 'LONG' | 'SHORT' | 'NEUTRAL';
export type SentMode = 'RULE' | 'ML';

export interface SentDecision {
  symbol: string;
  window: SentWindow;
  asOf: Date;
  mode: SentMode;
  action: SentAction;
  pUp: number;              // 0..1
  bias: number;             // -1..+1
  confidence: number;       // 0..1
}

export interface SentRiskState {
  window: SentWindow;
  symbol?: string;
  asOf: Date;

  equity: number;           // start 1.0
  peak: number;
  drawdownPct: number;      // 0..1
  sharpeLike: number;
  expectancyPct: number;
  winRate: number;          // 0..1

  reliability: 'OK' | 'WARN' | 'DEGRADED' | 'CRITICAL';
  riskMultiplier: number;   // 0..1
  kill: boolean;
}

export interface SentPositionSizing {
  basePct: number;
  capPct: number;
  finalPct: number;
  reasons: string[];
}

// Thresholds
export const ENTRY_THRESHOLD: Record<SentWindow, number> = {
  '24H': 0.15,
  '7D': 0.18,
  '30D': 0.22,
};

export const CHOP_FLOOR: Record<SentWindow, number> = {
  '24H': 0.12,
  '7D': 0.15,
  '30D': 0.18,
};

export const COOLDOWN_MS: Record<SentWindow, number> = {
  '24H': 6 * 60 * 60 * 1000,       // 6 hours
  '7D': 2 * 24 * 60 * 60 * 1000,   // 2 days
  '30D': 7 * 24 * 60 * 60 * 1000,  // 7 days
};

export const MAX_ACTIVE_BY_WINDOW: Record<SentWindow, number> = {
  '24H': 3,
  '7D': 2,
  '30D': 1,
};

export const HORIZON_DAYS: Record<SentWindow, number> = {
  '24H': 1,
  '7D': 7,
  '30D': 30,
};

console.log('[Sentiment-ML] Risk Types loaded (BLOCK 6)');
