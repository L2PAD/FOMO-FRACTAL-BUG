/**
 * Execution Scorer
 *
 * Final composite score:
 *   entry × 0.35 + timing × 0.30 + slippage × 0.20 + opportunity × 0.15
 */

import type { EntryEvaluation, TimingEvaluation, SlippageEvaluation, OpportunityCost } from '../types/execution-score.types.js';

class ExecutionScorerService {
  score(
    entry: EntryEvaluation,
    timing: TimingEvaluation,
    slippage: SlippageEvaluation,
    opportunity: OpportunityCost,
  ): { executionScore: number; executionGrade: string } {
    // Invert slippage and opportunity scores (lower leakage = higher score)
    const slippageScore = 1 - slippage.leakageScore;
    const opportunityScore = 1 - opportunity.costScore;

    const raw =
      entry.entryScore * 0.35 +
      timing.timingScore * 0.30 +
      slippageScore * 0.20 +
      opportunityScore * 0.15;

    const executionScore = Math.round(Math.max(0, Math.min(1, raw)) * 100) / 100;

    let executionGrade: string;
    if (executionScore >= 0.85) executionGrade = 'A';
    else if (executionScore >= 0.70) executionGrade = 'B';
    else if (executionScore >= 0.55) executionGrade = 'C';
    else if (executionScore >= 0.40) executionGrade = 'D';
    else executionGrade = 'F';

    return { executionScore, executionGrade };
  }
}

export const executionScorerService = new ExecutionScorerService();
