/**
 * Degradation Tracker
 *
 * Determines whether poor execution is:
 *   - DEGRADING: systematic decline (negative slope)
 *   - NOISE: random scatter
 *   - STABLE: consistently bad (flat but low)
 *   - IMPROVING: upward trend
 *
 * Uses linear regression on recent scores.
 */

import type { ExecutionScoreEntry } from '../types/execution-context.types.js';
import type { DegradationResult, DegradationState } from '../types/execution-anomaly.types.js';

const TIME_WINDOW_MS = 7 * 24 * 60 * 60 * 1000;
const MIN_POINTS = 3;

class DegradationTrackerService {
  /**
   * Analyze score trend for degradation.
   */
  analyze(entries: ExecutionScoreEntry[]): DegradationResult {
    const cutoff = new Date(Date.now() - TIME_WINDOW_MS).toISOString();
    const recent = entries
      .filter(e => e.timestamp >= cutoff)
      .sort((a, b) => a.timestamp.localeCompare(b.timestamp));

    if (recent.length < MIN_POINTS) {
      return { state: 'NOISE', slope: 0, trendStrength: 0, windowDays: 7 };
    }

    const scores = recent.map(e => e.score);
    const { slope, r2 } = this.linearRegression(scores);

    const state = this.classifyState(slope, r2);

    return {
      state,
      slope: Math.round(slope * 10000) / 10000,
      trendStrength: Math.round(r2 * 100) / 100,
      windowDays: 7,
    };
  }

  /**
   * Simple linear regression on array indices.
   */
  private linearRegression(values: number[]): { slope: number; r2: number } {
    const n = values.length;
    if (n < 2) return { slope: 0, r2: 0 };

    let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0, sumY2 = 0;

    for (let i = 0; i < n; i++) {
      sumX += i;
      sumY += values[i];
      sumXY += i * values[i];
      sumX2 += i * i;
      sumY2 += values[i] * values[i];
    }

    const denominator = n * sumX2 - sumX * sumX;
    if (denominator === 0) return { slope: 0, r2: 0 };

    const slope = (n * sumXY - sumX * sumY) / denominator;

    // R² (coefficient of determination)
    const meanY = sumY / n;
    const ssTotal = values.reduce((sum, v) => sum + (v - meanY) ** 2, 0);
    if (ssTotal === 0) return { slope: 0, r2: 1 };

    const ssRes = values.reduce((sum, v, i) => {
      const predicted = meanY + slope * (i - (n - 1) / 2);
      return sum + (v - predicted) ** 2;
    }, 0);

    const r2 = Math.max(0, 1 - ssRes / ssTotal);

    return { slope, r2 };
  }

  private classifyState(slope: number, r2: number): DegradationState {
    // If trend is weak (r² < 0.3), it's noise
    if (r2 < 0.3) return 'NOISE';

    // Strong negative slope = degrading
    if (slope < -0.02) return 'DEGRADING';

    // Strong positive slope = improving
    if (slope > 0.02) return 'IMPROVING';

    // Flat = stable (could be stably bad)
    return 'STABLE';
  }
}

export const degradationTrackerService = new DegradationTrackerService();
