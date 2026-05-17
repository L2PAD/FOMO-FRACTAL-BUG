/**
 * Missed Opportunity Service
 *
 * Finds cases where the system was too cautious.
 * "System stayed WAIT while edge was strong"
 *
 * This teaches not just from errors, but from inaction.
 */

import type { MissedOpportunity, DecisionTrace, ResolvedMarket } from '../types/outcome-lab.types.js';

class MissedOpportunityService {
  review(
    trace: DecisionTrace,
    traceHistory: DecisionTrace[],
    resolved: ResolvedMarket,
  ): MissedOpportunity {
    const outcomeYes = resolved.outcome === 'YES';
    const whyMissed: string[] = [];

    const enteredPosition = ['YES_NOW', 'NO_NOW', 'YES_SMALL', 'NO_SMALL'].includes(trace.action);

    // If entered and was correct, no miss
    if (enteredPosition) {
      const correct = (trace.action.includes('YES') && outcomeYes) || (trace.action.includes('NO') && !outcomeYes);
      if (correct) {
        return {
          missed: false,
          reason: 'Position was taken and outcome was correct',
          edgeAtBest: trace.edge,
          actionAtBest: trace.action,
          whyMissed: [],
        };
      }
    }

    // Find the best edge in history
    let bestEdge = 0;
    let bestAction = 'WATCH';
    let bestTrace: DecisionTrace | null = null;

    for (const t of [trace, ...traceHistory]) {
      const favorableEdge = outcomeYes ? t.edge : -t.edge;
      if (favorableEdge > bestEdge) {
        bestEdge = favorableEdge;
        bestAction = t.action;
        bestTrace = t;
      }
    }

    // Was there a meaningful opportunity?
    if (bestEdge < 0.05) {
      return {
        missed: false,
        reason: 'No meaningful edge existed for the correct direction',
        edgeAtBest: bestEdge,
        actionAtBest: bestAction,
        whyMissed: [],
      };
    }

    // There WAS an opportunity — did we take it?
    const tookCorrectAction = enteredPosition && (
      (trace.action.includes('YES') && outcomeYes) || (trace.action.includes('NO') && !outcomeYes)
    );

    if (tookCorrectAction) {
      return {
        missed: false,
        reason: 'Opportunity was captured correctly',
        edgeAtBest: bestEdge,
        actionAtBest: bestAction,
        whyMissed: [],
      };
    }

    // MISSED — analyze why
    const missed = true;
    let reason = '';

    if (!enteredPosition) {
      reason = `System stayed ${trace.action} while ${(bestEdge * 100).toFixed(1)}% edge existed`;

      // Why did system not enter?
      if (trace.confidence < 0.3) {
        whyMissed.push(`Low confidence (${(trace.confidence * 100).toFixed(0)}%) prevented entry`);
      }
      if (trace.alignment < 0.4) {
        whyMissed.push(`Low alignment (${(trace.alignment * 100).toFixed(0)}%) — modules disagreed`);
      }
      if (trace.repricingState === 'overheated' || trace.repricingState === 'late_repricing') {
        whyMissed.push(`Repricing state "${trace.repricingState}" blocked entry`);
      }
      if (trace.entryAction === 'do_not_enter' || trace.entryAction === 'too_late') {
        whyMissed.push(`Entry timing said "${trace.entryAction}"`);
      }
      if (trace.social.saturationScore > 0.6) {
        whyMissed.push(`High social saturation (${(trace.social.saturationScore * 100).toFixed(0)}%) may have made system cautious`);
      }
      if (trace.project.verdict === 'WEAK') {
        whyMissed.push('Weak project verdict reduced conviction');
      }
    } else {
      // Entered but wrong direction
      reason = `Entered ${trace.action} but outcome was ${resolved.outcome} — wrong direction`;
      whyMissed.push('Direction was wrong — not just a timing issue');
    }

    if (whyMissed.length === 0) {
      whyMissed.push('No specific blocker identified — general model uncertainty');
    }

    return {
      missed,
      reason,
      edgeAtBest: Math.round(bestEdge * 1000) / 1000,
      actionAtBest: bestAction,
      whyMissed,
    };
  }
}

export const missedOpportunityService = new MissedOpportunityService();
