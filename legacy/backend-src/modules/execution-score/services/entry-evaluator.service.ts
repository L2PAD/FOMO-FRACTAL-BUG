/**
 * Entry Evaluator
 *
 * Direction-aware entry quality assessment.
 * Compares actual entry with optimal zone (20-40th percentile best prices).
 */

import type { EntryEvaluation, Direction, EntryPosition, MarketPath } from '../types/execution-score.types.js';

class EntryEvaluatorService {
  evaluate(
    actualEntry: number,
    path: MarketPath,
    direction: Direction,
    fairProb: number,
  ): EntryEvaluation {
    // Collect all price points for optimal zone calculation
    const prices = [path.t0, path.t5m, path.t15m, path.t1h, path.t4h, path.t24h].filter(p => p > 0);

    // Direction-aware: for LONG, lower is better; for SHORT, higher is better
    const sorted = direction === 'LONG'
      ? [...prices].sort((a, b) => a - b)  // ascending (lower = better for LONG)
      : [...prices].sort((a, b) => b - a); // descending (higher = better for SHORT)

    // Optimal zone: 20th-40th percentile of best prices
    const p20 = sorted[Math.floor(sorted.length * 0.2)] ?? actualEntry;
    const p40 = sorted[Math.floor(sorted.length * 0.4)] ?? actualEntry;
    const optimalZoneLow = Math.min(p20, p40);
    const optimalZoneHigh = Math.max(p20, p40);

    // Best possible entry
    const bestPossibleEntry = direction === 'LONG' ? path.low : path.high;

    // Position relative to optimal zone
    let position: EntryPosition;
    if (direction === 'LONG') {
      if (actualEntry <= optimalZoneHigh) position = 'INSIDE_OPTIMAL';
      else if (actualEntry <= optimalZoneHigh * 1.03) position = 'EDGE_OPTIMAL';
      else position = 'OUTSIDE_OPTIMAL';
    } else {
      if (actualEntry >= optimalZoneLow) position = 'INSIDE_OPTIMAL';
      else if (actualEntry >= optimalZoneLow * 0.97) position = 'EDGE_OPTIMAL';
      else position = 'OUTSIDE_OPTIMAL';
    }

    // Improvement potential (how much better entry was possible)
    const improvementPotential = direction === 'LONG'
      ? Math.max(0, actualEntry - bestPossibleEntry)
      : Math.max(0, bestPossibleEntry - actualEntry);

    // Entry score: 0-1
    const totalRange = path.high - path.low;
    let entryScore: number;
    if (totalRange < 0.005) {
      entryScore = 0.7; // Tight range = entry doesn't matter much
    } else {
      const relativePos = direction === 'LONG'
        ? 1 - (actualEntry - path.low) / totalRange
        : (actualEntry - path.low) / totalRange;
      entryScore = Math.max(0, Math.min(1, relativePos));
    }

    const quality = entryScore >= 0.8 ? 'EXCELLENT' : entryScore >= 0.6 ? 'GOOD' : entryScore >= 0.4 ? 'OK' : 'BAD';

    return {
      entryScore: Math.round(entryScore * 100) / 100,
      quality,
      optimalZoneLow: Math.round(optimalZoneLow * 10000) / 10000,
      optimalZoneHigh: Math.round(optimalZoneHigh * 10000) / 10000,
      actualEntry,
      bestPossibleEntry,
      position,
      improvementPotential: Math.round(improvementPotential * 10000) / 10000,
    };
  }
}

export const entryEvaluatorService = new EntryEvaluatorService();
