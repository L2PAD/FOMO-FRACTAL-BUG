/**
 * Context Cluster Service
 *
 * Groups execution data by context and builds deterministic contextKey.
 * Maps raw execution data to the 5-dimensional context space:
 *   direction × regime × narrative × volatilityBucket × executionStyle
 */

import type { ExecutionContext, VolatilityBucket, ExecutionStyle } from '../types/execution-context.types.js';
import { buildContextKey } from '../types/execution-context.types.js';

class ContextClusterService {
  /**
   * Build ExecutionContext from raw case/score data.
   */
  cluster(data: {
    direction: string;
    regime: string;
    narrativePhase: string;
    volatility: number;
    entryStyle: string;
  }): { context: ExecutionContext; contextKey: string } {
    const context: ExecutionContext = {
      direction: this.normalizeDirection(data.direction),
      regime: this.normalizeRegime(data.regime),
      narrative: this.normalizeNarrative(data.narrativePhase),
      volatilityBucket: this.bucketVolatility(data.volatility),
      executionStyle: this.normalizeStyle(data.entryStyle),
    };

    return { context, contextKey: buildContextKey(context) };
  }

  private normalizeDirection(d: string): 'LONG' | 'SHORT' {
    const upper = (d || '').toUpperCase();
    if (['SHORT', 'NO', 'NO_NOW', 'NO_SMALL'].includes(upper)) return 'SHORT';
    return 'LONG';
  }

  private normalizeRegime(r: string): 'TREND' | 'RANGE' | 'TRANSITION' {
    const upper = (r || '').toUpperCase();
    if (upper === 'TREND') return 'TREND';
    if (upper === 'TRANSITION') return 'TRANSITION';
    return 'RANGE';
  }

  private normalizeNarrative(n: string): 'EARLY' | 'EXPANDING' | 'SATURATED' | 'EXHAUSTED' {
    const upper = (n || '').toUpperCase();
    if (upper === 'EARLY') return 'EARLY';
    if (upper === 'EXPANDING') return 'EXPANDING';
    if (upper === 'EXHAUSTED') return 'EXHAUSTED';
    if (upper === 'SATURATED') return 'SATURATED';
    return 'EXPANDING';
  }

  private bucketVolatility(v: number): VolatilityBucket {
    if (v >= 0.6) return 'HIGH';
    if (v >= 0.3) return 'MEDIUM';
    return 'LOW';
  }

  private normalizeStyle(s: string): ExecutionStyle {
    const upper = (s || '').toUpperCase();
    if (upper.includes('MARKET') || upper === 'ENTER_MARKET') return 'MARKET';
    if (upper.includes('LIMIT') || upper === 'ENTER_LIMIT') return 'LIMIT';
    if (upper.includes('WAIT') || upper === 'WAIT_FOR_DIP') return 'WAIT';
    if (upper.includes('STAGGER') || upper === 'STAGGER_ENTRIES') return 'STAGGER';
    if (upper.includes('FADE') || upper === 'FADE_SPIKE') return 'FADE_SPIKE';
    return 'UNKNOWN';
  }
}

export const contextClusterService = new ContextClusterService();
