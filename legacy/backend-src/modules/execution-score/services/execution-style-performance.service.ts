/**
 * Execution Style Performance
 *
 * Aggregates execution scores by entry style to find:
 * - Which styles actually work
 * - Which styles underperform
 * - Best/worst contexts for each style
 */

import type { StylePerformance, ExecutionScoreResult } from '../types/execution-score.types.js';

// In-memory store (will persist via MongoDB in production)
const styleStore = new Map<string, {
  scores: number[];
  wins: number;
  losses: number;
  leakages: number[];
  misses: number;
  contexts: string[];
  contextScores: Map<string, number[]>;
}>();

class ExecutionStylePerformanceService {
  /**
   * Record an execution result for a given style.
   */
  record(entryStyle: string, result: ExecutionScoreResult): void {
    if (!styleStore.has(entryStyle)) {
      styleStore.set(entryStyle, {
        scores: [], wins: 0, losses: 0, leakages: [], misses: 0,
        contexts: [], contextScores: new Map(),
      });
    }
    const s = styleStore.get(entryStyle)!;
    s.scores.push(result.executionScore);
    s.leakages.push(result.slippage.leakage);

    if (result.executionScore >= 0.6) s.wins++;
    else s.losses++;

    if (result.opportunity.reason !== 'NONE') s.misses++;

    // Context tracking
    const ctx = `${result.context.regime}_${result.context.narrativePhase}`;
    s.contexts.push(ctx);
    if (!s.contextScores.has(ctx)) s.contextScores.set(ctx, []);
    s.contextScores.get(ctx)!.push(result.executionScore);
  }

  /**
   * Get performance stats for all styles.
   */
  getAll(): StylePerformance[] {
    const results: StylePerformance[] = [];

    for (const [style, data] of styleStore.entries()) {
      const count = data.scores.length;
      if (count === 0) continue;

      const avgScore = data.scores.reduce((a, b) => a + b, 0) / count;
      const avgLeakage = data.leakages.reduce((a, b) => a + b, 0) / count;
      const winRate = (data.wins + data.losses) > 0 ? data.wins / (data.wins + data.losses) : 0;
      const missRate = count > 0 ? data.misses / count : 0;

      // Best/worst context
      let bestCtx = '', worstCtx = '';
      let bestAvg = -1, worstAvg = 2;
      for (const [ctx, scores] of data.contextScores.entries()) {
        const avg = scores.reduce((a, b) => a + b, 0) / scores.length;
        if (avg > bestAvg) { bestAvg = avg; bestCtx = ctx; }
        if (avg < worstAvg) { worstAvg = avg; worstCtx = ctx; }
      }

      results.push({
        style,
        avgScore: Math.round(avgScore * 100) / 100,
        count,
        winRate: Math.round(winRate * 100) / 100,
        avgLeakage: Math.round(avgLeakage * 10000) / 10000,
        missRate: Math.round(missRate * 100) / 100,
        bestContext: bestCtx,
        worstContext: worstCtx,
      });
    }

    return results.sort((a, b) => b.avgScore - a.avgScore);
  }

  /** Clear all data (testing) */
  clearAll(): void {
    styleStore.clear();
  }
}

export const executionStylePerformanceService = new ExecutionStylePerformanceService();
