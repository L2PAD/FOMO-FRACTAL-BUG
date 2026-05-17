/**
 * Slippage Engine
 *
 * Estimates how much edge you'll lose on entry.
 * If edge = 0.08 and expectedLeakage = 0.03, trade is fundamentally different.
 */

import type { SlippageAssessment, SpreadRegime, DepthQuality } from '../types/microstructure.types.js';

class SlippageEngineService {
  assess(
    spread: number,
    spreadRegime: SpreadRegime,
    depthQuality: DepthQuality,
    repricingState: string,
    edge: number,
  ): SlippageAssessment {
    const notes: string[] = [];
    let leakage = 0;

    // Base leakage = half the spread (market order crosses half the spread)
    const halfSpread = spread / 2;
    leakage += halfSpread;

    // Depth penalty
    const depthPenalty: Record<DepthQuality, number> = {
      DEEP: 0, OK: 0.005, THIN: 0.015, FRAGILE: 0.030,
    };
    leakage += depthPenalty[depthQuality];

    // Repricing state penalty (active repricing = worse fills)
    const repricingPenalty: Record<string, number> = {
      fresh_mispricing: 0,
      active_repricing: 0.005,
      late_repricing: 0.010,
      overheated: 0.020,
      stalled: 0.002,
    };
    leakage += repricingPenalty[repricingState] ?? 0.005;

    // Panic/rush penalty for wide/broken spreads
    if (spreadRegime === 'WIDE') {
      leakage += 0.010;
      notes.push('Wide spread adds execution premium');
    } else if (spreadRegime === 'BROKEN') {
      leakage += 0.025;
      notes.push('Broken spread — execution will be very costly');
    }

    leakage = Math.round(Math.min(0.15, leakage) * 10000) / 10000;

    // Slippage risk (0-1)
    const slippageRisk = Math.min(1, leakage / 0.05);

    // Max slippage in basis points
    const maxSlippageBps = Math.round(leakage * 10000);

    // Context notes
    const edgeAfterSlippage = Math.abs(edge) - leakage;
    if (edgeAfterSlippage <= 0) {
      notes.push(`Expected leakage (${(leakage * 100).toFixed(1)}%) EXCEEDS edge (${(Math.abs(edge) * 100).toFixed(1)}%) — trade is unprofitable after execution costs`);
    } else if (leakage > Math.abs(edge) * 0.40) {
      notes.push(`Leakage consumes ${((leakage / Math.abs(edge)) * 100).toFixed(0)}% of edge — significant execution cost`);
    } else {
      notes.push(`Leakage ${(leakage * 100).toFixed(2)}% vs edge ${(Math.abs(edge) * 100).toFixed(1)}% — acceptable`);
    }

    return {
      slippageRisk: Math.round(slippageRisk * 100) / 100,
      expectedLeakage: leakage,
      maxSlippageBps,
      notes,
    };
  }
}

export const slippageEngineService = new SlippageEngineService();
