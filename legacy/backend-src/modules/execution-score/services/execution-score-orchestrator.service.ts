/**
 * Execution Score Orchestrator
 *
 * Pipeline: Trace → Path → Entry → Timing → Slippage → Opportunity → Score → Style → Feedback
 */

import { executionTraceService } from './execution-trace.service.js';
import { marketPathReconstructorService } from './market-path-reconstructor.service.js';
import { entryEvaluatorService } from './entry-evaluator.service.js';
import { timingEvaluatorService } from './timing-evaluator.service.js';
import { slippageEvaluatorService } from './slippage-evaluator.service.js';
import { opportunityCostService } from './opportunity-cost.service.js';
import { executionScorerService } from './execution-scorer.service.js';
import { executionStylePerformanceService } from './execution-style-performance.service.js';
import { executionFeedbackService } from './execution-feedback.service.js';
import type { ExecutionScoreResult } from '../types/execution-score.types.js';

class ExecutionScoreOrchestrator {
  /**
   * Score a single case's execution quality.
   */
  score(caseData: Record<string, any>, snapshots?: { timestamp: string; marketProb: number }[]): ExecutionScoreResult {
    const analysis = caseData.analysis || {};
    const el = caseData.executionLayer || {};

    // 1. Build trace
    const trace = executionTraceService.buildTrace(caseData);

    // 2. Reconstruct market path
    const path = marketPathReconstructorService.reconstruct(
      trace.marketProb,
      analysis.fair_prob || 0.5,
      snapshots || [],
    );

    // 3. Evaluate entry (direction-aware)
    const entry = entryEvaluatorService.evaluate(
      trace.marketProb,
      path,
      trace.direction,
      analysis.fair_prob || 0.5,
    );

    // 4. Evaluate timing
    const timing = timingEvaluatorService.evaluate(
      trace.execution.entryStyle,
      path,
      trace.direction,
      trace.marketProb,
      trace.context.repricing,
    );

    // 5. Evaluate slippage
    const expectedSlippage = (el.maxSlippageBps || 50) / 10000;
    const slippage = slippageEvaluatorService.evaluate(
      expectedSlippage,
      trace.marketProb,
      path,
      trace.direction,
      trace.execution.entryStyle,
    );

    // 6. Opportunity cost
    const opportunity = opportunityCostService.evaluate(
      trace.marketProb,
      trace.execution.entryStyle,
      path,
      trace.direction,
      analysis.net_edge || 0,
    );

    // 7. Final score
    const { executionScore, executionGrade } = executionScorerService.score(entry, timing, slippage, opportunity);

    const result: ExecutionScoreResult = {
      executionScore,
      executionGrade,
      entry,
      timing,
      slippage,
      opportunity,
      context: {
        regime: trace.context.regime,
        narrativePhase: trace.context.narrativePhase,
        direction: trace.direction,
      },
      lessons: [],
    };

    // 8. Generate lessons
    result.lessons = executionFeedbackService.forExecution(result);

    // 9. Record in style performance
    executionStylePerformanceService.record(trace.execution.entryStyle, result);

    return result;
  }

  /**
   * Score a batch of cases.
   */
  scoreBatch(cases: Record<string, any>[]): Record<string, ExecutionScoreResult> {
    const results: Record<string, ExecutionScoreResult> = {};
    for (const c of cases) {
      const marketId = c.market_id || '';
      if (!marketId) continue;
      try {
        results[marketId] = this.score(c);
      } catch {
        // Skip failed cases
      }
    }
    return results;
  }

  /**
   * Get style performance stats.
   */
  getStylePerformance() {
    const styles = executionStylePerformanceService.getAll();
    const { lessons, adjustments } = executionFeedbackService.forStyles(styles);
    return { styles, lessons, adjustments };
  }

  /**
   * Clear all data (testing).
   */
  clearAll(): void {
    executionStylePerformanceService.clearAll();
  }
}

export const executionScoreOrchestrator = new ExecutionScoreOrchestrator();
