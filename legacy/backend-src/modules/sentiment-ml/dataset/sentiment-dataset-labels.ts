/**
 * Sentiment Dataset Labels Configuration v1
 * ==========================================
 * 
 * BLOCK 2: Production Label Spec
 * 
 * Label logic:
 * - UP:      return >= threshold.up
 * - DOWN:    return <= threshold.down
 * - NEUTRAL: otherwise
 * 
 * PRODUCTION THRESHOLDS (v1):
 * - 24H: ±0.35% (sentiment is lagging signal, need stronger moves)
 * - 7D:  ±1.8%  (weekly directional signal)
 * - 30D: ±4.5%  (monthly trend)
 * 
 * VERSION HISTORY:
 * - v0 (dev): ±0.3%, ±1.5%, ±4%
 * - v1 (prod): ±0.35%, ±1.8%, ±4.5% - calibrated for sentiment noise
 */

import { SentimentWindow, DirLabel } from './sentiment-dir-sample.model.js';

// Current label version - increment when changing thresholds
export const SENTIMENT_LABEL_VERSION = 2;

export interface LabelThreshold {
  up: number;    // Minimum return for UP label
  down: number;  // Maximum return for DOWN label
}

// Production thresholds v2 (calibrated to real PnL distribution)
// v1: ±0.35%, ±1.8%, ±4.5% — 7D was catastrophically wide (NEUTRAL 87%)
// v2: ±0.25%, ±0.4%, ±4.5% — calibrated to P33/P67 of actual trade returns
export const SENTIMENT_LABEL_THRESHOLDS: Record<SentimentWindow, LabelThreshold> = {
  '24H': { up: 0.0025, down: -0.0025 },  // ±0.25%
  '7D':  { up: 0.004,  down: -0.004  },  // ±0.4%
  '30D': { up: 0.045,  down: -0.045  },  // ±4.5% (no data yet)
};

// Also export as LABEL_THRESHOLDS for backwards compatibility
export const LABEL_THRESHOLDS = SENTIMENT_LABEL_THRESHOLDS;

/**
 * Compute label from return percentage
 */
export function labelFromReturn(window: SentimentWindow, returnPct: number): DirLabel {
  const th = SENTIMENT_LABEL_THRESHOLDS[window];
  
  if (returnPct >= th.up) return 'UP';
  if (returnPct <= th.down) return 'DOWN';
  return 'NEUTRAL';
}

/**
 * Get horizon days for window
 */
export function horizonDays(window: SentimentWindow): number {
  switch (window) {
    case '24H': return 1;
    case '7D': return 7;
    case '30D': return 30;
  }
}

/**
 * Get horizon milliseconds for window
 */
export function horizonMs(window: SentimentWindow): number {
  return horizonDays(window) * 24 * 60 * 60 * 1000;
}

/**
 * Get max price gap tolerance (for missing candles)
 */
export function maxPriceGapMs(window: SentimentWindow): number {
  switch (window) {
    case '24H': return 36 * 60 * 60 * 1000;  // 36h
    case '7D': return 72 * 60 * 60 * 1000;   // 72h
    case '30D': return 7 * 24 * 60 * 60 * 1000; // 7 days
  }
}

/**
 * Production Dataset Targets
 */
export const DATASET_MIN_SAMPLES: Record<SentimentWindow, number> = {
  '24H': 200,
  '7D': 150,
  '30D': 120,
};

/**
 * Dataset Quality Thresholds
 */
export const DATASET_QUALITY_THRESHOLDS = {
  maxNeutralPct: 0.70,    // Neutral < 70%
  minUpDownPct: 0.20,     // UP and DOWN each > 20%
  minSymbolCoverage: 10,  // At least 10 different symbols
};

console.log(`[Sentiment-ML] Labels v${SENTIMENT_LABEL_VERSION} loaded (BLOCK 2 Production Spec)`);
