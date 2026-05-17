/**
 * Edge Compression Engine
 *
 * How much edge has evaporated since the strongest signal?
 * Critical for trim/reduce/do_not_chase decisions.
 */

import type { EdgeCompressionAssessment } from '../types/execution.types.js';

class EdgeCompressionService {
  assess(currentEdge: number, originalEdge?: number, repricingState?: string): EdgeCompressionAssessment {
    const notes: string[] = [];

    // If no original edge, estimate from repricing state
    const origEdge = originalEdge ?? this.estimateOriginalEdge(currentEdge, repricingState);
    const absOrig = Math.abs(origEdge);
    const absCurr = Math.abs(currentEdge);

    let compression = 0;
    if (absOrig > 0) {
      compression = Math.max(0, 1 - (absCurr / absOrig));
    }
    compression = Math.round(compression * 100) / 100;

    const compressed = compression > 0.50;

    if (compression > 0.80) {
      notes.push(`Edge almost fully compressed (${(compression * 100).toFixed(0)}%) — trade is essentially over`);
    } else if (compression > 0.60) {
      notes.push(`Significant edge compression (${(compression * 100).toFixed(0)}%) — consider trim/reduce`);
    } else if (compression > 0.30) {
      notes.push(`Moderate compression (${(compression * 100).toFixed(0)}%) — monitor closely`);
    } else {
      notes.push(`Edge still fresh (${(compression * 100).toFixed(0)}% compressed)`);
    }

    return {
      edgeCompression: compression,
      compressed,
      originalEdge: Math.round(origEdge * 10000) / 10000,
      currentEdge: Math.round(currentEdge * 10000) / 10000,
      notes,
    };
  }

  private estimateOriginalEdge(currentEdge: number, repricingState?: string): number {
    // Heuristic: estimate original edge based on repricing state
    const multipliers: Record<string, number> = {
      fresh_mispricing: 1.1,    // Edge still close to original
      early_signal: 1.2,
      active_repricing: 1.5,    // Edge has moved
      late_repricing: 2.0,      // Edge was much bigger
      overheated: 3.0,          // Edge was very large, mostly consumed
      stalled: 1.3,
      crowded: 2.5,
    };
    const mult = multipliers[repricingState || 'active_repricing'] ?? 1.3;
    return currentEdge * mult;
  }
}

export const edgeCompressionService = new EdgeCompressionService();
