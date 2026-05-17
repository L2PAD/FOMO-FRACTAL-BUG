/**
 * META BRAIN V2 — SIGNAL NORMALIZER
 * ==================================
 * 
 * Converts aligned signals into normalized scores.
 * Uses score × confidence (not just direction × confidence)
 * to preserve signal strength from each module.
 */

import { AlignedMetaSignal } from '../contracts/signal.contract.js';

export interface NormalizedSignal {
  module: string;
  normalizedScore: number;  // [-1..+1]
  rawScore: number;
  rawConfidence: number;
  direction: string;
}

/**
 * Normalize: score × confidence
 * This preserves the magnitude that each module already computed.
 */
export function normalizeSignal(signal: AlignedMetaSignal): NormalizedSignal {
  const normalizedScore = signal.score * signal.confidence;

  return {
    module: signal.module,
    normalizedScore: Math.max(-1, Math.min(1, normalizedScore)),
    rawScore: signal.score,
    rawConfidence: signal.confidence,
    direction: signal.direction,
  };
}

export function normalizeAll(signals: AlignedMetaSignal[]): NormalizedSignal[] {
  return signals.map(normalizeSignal);
}
