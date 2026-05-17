/**
 * Spread Regime Engine
 *
 * Determines the spread regime: NARROW / NORMAL / WIDE / BROKEN
 * Not just raw spread — accounts for liquidity context and recent widening.
 */

import type { SpreadAssessment, SpreadRegime } from '../types/microstructure.types.js';

// Polymarket spread thresholds (these are binary markets: 0-1)
const SPREAD_THRESHOLDS = {
  narrow: 0.02,    // <2% spread
  normal: 0.05,    // <5% spread
  wide: 0.09,      // <9% spread
  // above = BROKEN
};

class SpreadRegimeService {
  assess(spread: number, liquidity: number, volume24h: number): SpreadAssessment {
    const notes: string[] = [];

    // Raw regime
    let regime: SpreadRegime;
    if (spread <= SPREAD_THRESHOLDS.narrow) {
      regime = 'NARROW';
      notes.push(`Spread ${(spread * 100).toFixed(1)}% — tight, market entry viable`);
    } else if (spread <= SPREAD_THRESHOLDS.normal) {
      regime = 'NORMAL';
      notes.push(`Spread ${(spread * 100).toFixed(1)}% — acceptable for limit orders`);
    } else if (spread <= SPREAD_THRESHOLDS.wide) {
      regime = 'WIDE';
      notes.push(`Spread ${(spread * 100).toFixed(1)}% — significant leakage risk, use limit only`);
    } else {
      regime = 'BROKEN';
      notes.push(`Spread ${(spread * 100).toFixed(1)}% — broken, execution not recommended`);
    }

    // Liquidity context adjustment
    if (liquidity < 5000 && regime !== 'BROKEN') {
      if (regime === 'NARROW') regime = 'NORMAL';
      else if (regime === 'NORMAL') regime = 'WIDE';
      notes.push(`Low liquidity ($${liquidity.toFixed(0)}) degrades effective spread regime`);
    }

    // Volume context
    if (volume24h < 1000 && regime !== 'BROKEN') {
      notes.push(`Very low 24h volume ($${volume24h.toFixed(0)}) — market may be stale`);
      if (regime === 'NARROW') regime = 'NORMAL';
    }

    // Spread penalty (0-1, higher = worse)
    const spreadPenalty = Math.min(1, spread / 0.12);

    return {
      regime,
      spreadPenalty: Math.round(spreadPenalty * 100) / 100,
      rawSpread: Math.round(spread * 10000) / 10000,
      notes,
    };
  }
}

export const spreadRegimeService = new SpreadRegimeService();
