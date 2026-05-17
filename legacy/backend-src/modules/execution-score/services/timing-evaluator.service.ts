/**
 * Timing Evaluator
 *
 * Time-weighted: considers how long edge was available.
 * If edge disappeared in 10min → WAIT = mistake.
 * If edge held 4h → WAIT = acceptable.
 */

import type { TimingEvaluation, MarketPath, Direction } from '../types/execution-score.types.js';

class TimingEvaluatorService {
  evaluate(
    entryStyle: string,
    path: MarketPath,
    direction: Direction,
    actualEntry: number,
    repricing: string,
  ): TimingEvaluation {
    const edgeWindows = path.edgeWindows || [];

    // How long was edge available?
    const availableWindows = edgeWindows.filter(w => w.available);
    const totalAvailableMin = availableWindows.reduce((sum, w) => sum + (w.endMin - w.startMin), 0);

    // Edge decay rate: how fast did edge disappear?
    const firstEdge = edgeWindows[0]?.avgEdge || 0;
    const lastEdge = edgeWindows[edgeWindows.length - 1]?.avgEdge || 0;
    const edgeDecayRate = firstEdge > 0 ? Math.round(((firstEdge - lastEdge) / firstEdge) * 100) / 100 : 0;

    // Was the entry too late?
    const priceMoved = direction === 'LONG'
      ? path.t1h - path.t0
      : path.t0 - path.t1h;
    const priceMovedFast = Math.abs(priceMoved) > 0.03;

    // WAIT evaluation
    const wasWait = ['WAIT_RETRACE', 'WAIT_CONFIRMATION'].includes(entryStyle);
    const wasLate = wasWait && priceMovedFast && totalAvailableMin < 30;
    const wasEarly = !wasWait && priceMoved < -0.02 && direction === 'LONG';

    // Did we miss a better window?
    const missedBetterWindow = wasWait
      ? edgeDecayRate > 0.5 // Edge decayed more than 50%
      : (direction === 'LONG' ? path.low < actualEntry * 0.97 : path.high > actualEntry * 1.03);

    // Timing score
    let timingScore: number;
    if (wasLate) {
      timingScore = 0.2;
    } else if (wasEarly) {
      timingScore = 0.4;
    } else if (missedBetterWindow) {
      timingScore = 0.5;
    } else if (['fresh_mispricing', 'early_repricing'].includes(repricing)) {
      timingScore = 0.85;
    } else if (totalAvailableMin >= 60) {
      timingScore = 0.7;
    } else {
      timingScore = 0.6;
    }

    // WAIT that actually caught retrace = bonus
    if (wasWait && !wasLate && direction === 'LONG' && actualEntry <= path.t0 * 0.98) {
      timingScore = Math.min(1, timingScore + 0.2);
    }

    const quality = timingScore >= 0.8 ? 'EXCELLENT' : timingScore >= 0.6 ? 'GOOD' :
                    timingScore >= 0.45 ? 'OK' : timingScore >= 0.3 ? 'LATE' : 'BAD';

    return {
      timingScore: Math.round(timingScore * 100) / 100,
      quality,
      wasEarly,
      wasLate,
      missedBetterWindow,
      edgeDecayRate,
      optimalWindowMinutes: totalAvailableMin,
    };
  }
}

export const timingEvaluatorService = new TimingEvaluatorService();
