/**
 * Slippage Evaluator
 *
 * Compares expected slippage vs actual market movement at entry.
 */

import type { SlippageEvaluation, MarketPath, Direction } from '../types/execution-score.types.js';

class SlippageEvaluatorService {
  evaluate(
    expectedSlippage: number,
    actualEntry: number,
    path: MarketPath,
    direction: Direction,
    entryStyle: string,
  ): SlippageEvaluation {
    // Actual slippage: difference between t0 and actual entry (direction-aware)
    const actualSlippage = direction === 'LONG'
      ? Math.max(0, actualEntry - path.t0) // Paid more than t0
      : Math.max(0, path.t0 - actualEntry); // Sold lower than t0

    // For MARKET orders, slippage is higher
    const styleMultiplier = entryStyle === 'ENTER_MARKET' ? 1.2 :
                            entryStyle === 'STAGGER_LIMIT' ? 0.7 : 1.0;

    const adjustedExpected = expectedSlippage * styleMultiplier;
    const leakage = Math.max(0, actualSlippage - adjustedExpected);

    // Leakage score: 0 = no leakage, 1 = massive leakage
    const leakageScore = adjustedExpected > 0
      ? Math.min(1, leakage / Math.max(adjustedExpected, 0.01))
      : actualSlippage > 0.02 ? 0.8 : 0;

    return {
      expected: Math.round(adjustedExpected * 10000) / 10000,
      actual: Math.round(actualSlippage * 10000) / 10000,
      leakage: Math.round(leakage * 10000) / 10000,
      leakageScore: Math.round(leakageScore * 100) / 100,
    };
  }
}

export const slippageEvaluatorService = new SlippageEvaluatorService();
