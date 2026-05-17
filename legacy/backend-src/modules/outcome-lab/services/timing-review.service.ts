/**
 * Timing Review Service
 *
 * The most underrated layer. Teaches: WHEN to enter, not just WHERE.
 *
 * Analyzes trace history to determine:
 * - Was the timing good?
 * - What was the best entry window?
 * - Did we miss the optimal entry?
 */

import type { TimingReview, DecisionTrace, ResolvedMarket } from '../types/outcome-lab.types.js';

class TimingReviewService {
  review(
    trace: DecisionTrace,
    traceHistory: DecisionTrace[],
    resolved: ResolvedMarket,
  ): TimingReview {
    const notes: string[] = [];
    const outcomeYes = resolved.outcome === 'YES';

    // Find the best entry point in trace history
    const bestEntry = this.findBestEntry(traceHistory, outcomeYes);
    const firstActionable = this.findFirstActionable(traceHistory, outcomeYes);

    // Entry delay (hours from first actionable signal to our main trace)
    const entryDelay = firstActionable
      ? (trace.traceTimestamp.getTime() - new Date(firstActionable.traceTimestamp).getTime()) / 3600000
      : 0;

    // Optimal entry prob vs actual
    const optimalEntryProb = bestEntry?.marketProb ?? trace.marketProb;
    const actualEntryProb = trace.marketProb;

    // Best window description
    let bestWindow: string | null = null;
    if (bestEntry && bestEntry.traceTimestamp !== trace.traceTimestamp) {
      const hoursAgo = (trace.traceTimestamp.getTime() - new Date(bestEntry.traceTimestamp).getTime()) / 3600000;
      bestWindow = `${Math.round(hoursAgo)}h before final trace`;
    }

    // First actionable description
    let firstActionableDesc: string | null = null;
    if (firstActionable) {
      const hoursAgo = (trace.traceTimestamp.getTime() - new Date(firstActionable.traceTimestamp).getTime()) / 3600000;
      if (hoursAgo > 0.5) {
        firstActionableDesc = `Edge first appeared ${Math.round(hoursAgo)}h ago`;
      }
    }

    // Was the entry timing good?
    const entryWasActionable = ['YES_NOW', 'NO_NOW', 'YES_SMALL', 'NO_SMALL'].includes(trace.action);
    const actionCorrect = (outcomeYes && trace.action.includes('YES')) || (!outcomeYes && trace.action.includes('NO'));

    // Timing quality assessment
    let timingQuality: TimingReview['timingQuality'];
    let missed = false;

    if (!entryWasActionable) {
      // Didn't enter — was there an opportunity?
      const hadOpportunity = traceHistory.some(t => {
        const edgeFavorable = outcomeYes ? t.edge > 0.05 : t.edge < -0.05;
        return edgeFavorable && t.confidence > 0.3;
      });

      if (hadOpportunity) {
        timingQuality = 'BAD';
        missed = true;
        notes.push('Opportunity existed but system never entered — timing failure');
      } else {
        timingQuality = 'OK';
        notes.push('No clear entry opportunity was available');
      }
    } else if (actionCorrect) {
      // Entered and correct — how was the timing?
      if (trace.repricingState === 'fresh_mispricing' || trace.entryAction === 'enter_now') {
        timingQuality = 'EARLY';
        notes.push('Entered early during fresh mispricing — excellent timing');
      } else if (entryDelay < 4) {
        timingQuality = 'GOOD';
        notes.push('Entry was timely — within first few hours of signal');
      } else if (entryDelay < 12) {
        timingQuality = 'OK';
        notes.push('Entry was acceptable but could have been earlier');
      } else {
        timingQuality = 'LATE';
        notes.push(`Entry was ${Math.round(entryDelay)}h after first signal — too late`);
      }
    } else {
      // Entered and wrong
      if (trace.repricingState === 'overheated' || trace.marketStage === 'crowded') {
        timingQuality = 'BAD';
        notes.push('Entered during overheated/crowded stage — timing trap');
      } else {
        timingQuality = 'BAD';
        notes.push('Wrong direction — timing is irrelevant when direction is wrong');
      }
    }

    // Price improvement analysis
    if (bestEntry && entryWasActionable) {
      const priceDiff = Math.abs(optimalEntryProb - actualEntryProb);
      if (priceDiff > 0.05) {
        notes.push(`Could have entered at ${(optimalEntryProb * 100).toFixed(0)}% vs actual ${(actualEntryProb * 100).toFixed(0)}% — ${(priceDiff * 100).toFixed(1)}% better entry possible`);
      }
    }

    return {
      timingQuality,
      bestWindow,
      firstActionable: firstActionableDesc,
      missed,
      entryDelay: Math.round(entryDelay * 10) / 10,
      optimalEntryProb: Math.round(optimalEntryProb * 1000) / 1000,
      actualEntryProb: Math.round(actualEntryProb * 1000) / 1000,
      notes,
    };
  }

  private findBestEntry(history: DecisionTrace[], outcomeYes: boolean): DecisionTrace | null {
    if (!history.length) return null;

    // Best entry = highest absolute edge in the correct direction
    let best: DecisionTrace | null = null;
    let bestEdge = 0;

    for (const t of history) {
      const edgeFavorable = outcomeYes ? t.edge : -t.edge;
      if (edgeFavorable > bestEdge) {
        bestEdge = edgeFavorable;
        best = t;
      }
    }

    return best;
  }

  private findFirstActionable(history: DecisionTrace[], outcomeYes: boolean): DecisionTrace | null {
    // First trace where edge > 5% in the correct direction
    for (const t of history) {
      const edgeFavorable = outcomeYes ? t.edge > 0.05 : t.edge < -0.05;
      if (edgeFavorable && t.confidence > 0.25) return t;
    }
    return null;
  }
}

export const timingReviewService = new TimingReviewService();
