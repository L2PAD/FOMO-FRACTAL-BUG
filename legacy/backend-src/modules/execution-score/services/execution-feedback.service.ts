/**
 * Execution Feedback
 *
 * Generates human-readable lessons and adjustments
 * based on execution scores and style performance.
 */

import type { ExecutionScoreResult, StylePerformance } from '../types/execution-score.types.js';

class ExecutionFeedbackService {
  /**
   * Generate lessons for a single execution.
   */
  forExecution(result: ExecutionScoreResult): string[] {
    const lessons: string[] = [];
    const { entry, timing, slippage, opportunity, context } = result;

    // Entry lessons
    if (entry.position === 'OUTSIDE_OPTIMAL') {
      lessons.push(`Entry was outside optimal zone — improvement potential: ${(entry.improvementPotential * 100).toFixed(1)}%`);
    }
    if (entry.quality === 'BAD') {
      lessons.push('Poor entry quality — consider different entry style');
    }

    // Timing lessons
    if (timing.wasLate) {
      lessons.push('Entry was late — edge had already decayed significantly');
    }
    if (timing.missedBetterWindow) {
      lessons.push(`Missed better entry window (available for ~${timing.optimalWindowMinutes}min)`);
    }
    if (timing.edgeDecayRate > 0.6) {
      lessons.push(`Edge decayed ${(timing.edgeDecayRate * 100).toFixed(0)}% — faster execution needed`);
    }

    // Slippage lessons
    if (slippage.leakage > 0.02) {
      lessons.push(`Slippage leakage: ${(slippage.leakage * 100).toFixed(1)}% above expected`);
    }

    // Opportunity lessons
    if (opportunity.reason === 'WAIT_TOO_LONG') {
      lessons.push('WAIT strategy missed the move — more aggressive entry warranted');
    } else if (opportunity.reason === 'LIMIT_NOT_FILLED') {
      lessons.push('LIMIT order not filled optimally — consider market or stagger');
    } else if (opportunity.reason === 'LATE_ENTRY') {
      lessons.push(`Late entry cost ${(opportunity.missedMove * 100).toFixed(1)}% of move`);
    }

    // Context-specific
    if (context.regime === 'TREND' && timing.wasLate) {
      lessons.push('In TREND regime, speed matters more than price — prefer MARKET entries');
    }
    if (context.narrativePhase === 'EARLY' && opportunity.reason === 'WAIT_TOO_LONG') {
      lessons.push('Early narrative: WAIT too conservative — move was fast');
    }

    return lessons.slice(0, 4);
  }

  /**
   * Generate aggregate lessons from style performance.
   */
  forStyles(styles: StylePerformance[]): { lessons: string[]; adjustments: string[] } {
    const lessons: string[] = [];
    const adjustments: string[] = [];

    for (const s of styles) {
      if (s.count < 2) continue;

      if (s.avgScore < 0.5) {
        lessons.push(`${s.style} underperforms (avg score: ${(s.avgScore * 100).toFixed(0)}%)`);
      }
      if (s.missRate > 0.3) {
        lessons.push(`${s.style} misses ${(s.missRate * 100).toFixed(0)}% of opportunities`);
      }
      if (s.avgScore > 0.7) {
        adjustments.push(`${s.style} performing well (${(s.avgScore * 100).toFixed(0)}%) — favor in ${s.bestContext}`);
      }
      if (s.worstContext && s.bestContext !== s.worstContext) {
        adjustments.push(`${s.style}: best in ${s.bestContext}, avoid in ${s.worstContext}`);
      }
    }

    return { lessons: lessons.slice(0, 4), adjustments: adjustments.slice(0, 3) };
  }
}

export const executionFeedbackService = new ExecutionFeedbackService();
