/**
 * Opportunity Cost
 *
 * Calculates what was missed: how much move was left on the table.
 */

import type { OpportunityCost, OpportunityCostReason, MarketPath, Direction } from '../types/execution-score.types.js';

class OpportunityCostService {
  evaluate(
    actualEntry: number,
    entryStyle: string,
    path: MarketPath,
    direction: Direction,
    edge: number,
  ): OpportunityCost {
    // Missed move: how much the market moved favorably that we didn't capture
    const favorableMove = direction === 'LONG'
      ? path.high - actualEntry
      : actualEntry - path.low;

    // Maximum possible move from t0
    const maxMove = direction === 'LONG'
      ? path.high - path.t0
      : path.t0 - path.low;

    // Missed return: favorable move we lost due to entry timing
    const capturedMove = direction === 'LONG'
      ? Math.max(0, path.final - actualEntry)
      : Math.max(0, actualEntry - path.final);

    const missedMove = Math.max(0, maxMove - capturedMove);
    const missedReturn = maxMove > 0 ? missedMove / maxMove : 0;

    // Reason
    let reason: OpportunityCostReason = 'NONE';
    if (['WAIT_RETRACE', 'WAIT_CONFIRMATION'].includes(entryStyle) && missedReturn > 0.3) {
      reason = 'WAIT_TOO_LONG';
    } else if (entryStyle === 'ENTER_LIMIT' && missedReturn > 0.25) {
      reason = 'LIMIT_NOT_FILLED';
    } else if (missedReturn > 0.2) {
      reason = 'LATE_ENTRY';
    }

    // Cost score: 0 = no cost, 1 = missed everything
    const costScore = Math.min(1, missedReturn);

    return {
      missedMove: Math.round(missedMove * 10000) / 10000,
      missedReturn: Math.round(missedReturn * 100) / 100,
      reason,
      costScore: Math.round(costScore * 100) / 100,
    };
  }
}

export const opportunityCostService = new OpportunityCostService();
