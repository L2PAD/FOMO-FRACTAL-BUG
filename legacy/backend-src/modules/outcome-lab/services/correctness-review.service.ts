/**
 * Correctness Review Service
 *
 * Answers: Was the system's prediction correct?
 * Not just YES/NO — but was the strongest signal in the right direction?
 */

import type { CorrectnessReview, DecisionTrace, ResolvedMarket } from '../types/outcome-lab.types.js';

class CorrectnessReviewService {
  review(trace: DecisionTrace, resolved: ResolvedMarket): CorrectnessReview {
    const notes: string[] = [];
    const outcomeYes = resolved.outcome === 'YES';

    // Direction check: did our action align with outcome?
    const actionBullish = ['YES_NOW', 'YES_SMALL'].includes(trace.action);
    const actionBearish = ['NO_NOW', 'NO_SMALL'].includes(trace.action);
    const actionNeutral = ['WATCH', 'WAIT', 'AVOID'].includes(trace.action);

    const directionCorrect = (actionBullish && outcomeYes) || (actionBearish && !outcomeYes);

    // Edge realization: was there actually an edge?
    const edgeRealized = (trace.edge > 0 && outcomeYes) || (trace.edge < 0 && !outcomeYes);

    // Confidence check
    const confidenceJustified = directionCorrect && trace.confidence >= 0.5;

    // Strongest call
    let strongestCall = '';
    if (!actionNeutral) {
      const prob = Math.round(trace.marketProb * 100);
      strongestCall = directionCorrect
        ? `${trace.action} at ${prob}% was CORRECT (resolved ${resolved.outcome})`
        : `${trace.action} at ${prob}% was WRONG (resolved ${resolved.outcome})`;
    } else {
      strongestCall = `System stayed ${trace.action} — no directional bet`;
    }

    // Correctness level
    let correctness: CorrectnessReview['correctness'];
    if (actionNeutral) {
      // Was neutral the right call?
      const edgeMagnitude = Math.abs(trace.edge);
      if (edgeMagnitude < 0.05) {
        correctness = 'CORRECT'; // Correctly identified no edge
        notes.push('Correctly stayed neutral — no meaningful edge existed');
      } else if (edgeRealized) {
        correctness = 'WRONG'; // There was an edge but system didn't act
        notes.push(`Missed a ${(edgeMagnitude * 100).toFixed(1)}% edge — system was too cautious`);
      } else {
        correctness = 'CORRECT';
        notes.push('Neutral stance was justified — edge would not have materialized');
      }
    } else if (directionCorrect) {
      correctness = 'CORRECT';
      const convStr = trace.conviction;
      if (convStr === 'HIGH' && trace.confidence >= 0.6) {
        notes.push('HIGH conviction call was justified — excellent signal quality');
      } else {
        notes.push(`${convStr} conviction ${trace.action} was directionally correct`);
      }
    } else {
      correctness = 'WRONG';
      notes.push(`System predicted ${trace.action} but market resolved ${resolved.outcome}`);

      // Was it a close call?
      if (Math.abs(trace.edge) < 0.08) {
        correctness = 'MIXED';
        notes.push('Edge was very small — close call, not a major failure');
      }
    }

    // Additional context
    if (trace.confidence < 0.3) {
      notes.push('Low confidence signal — system was uncertain');
    }
    if (trace.alignment < 0.4) {
      notes.push('Low alignment — modules disagreed, signal was weak');
    }

    return {
      correctness,
      directionCorrect,
      edgeRealized,
      strongestCall,
      confidenceJustified,
      notes,
    };
  }
}

export const correctnessReviewService = new CorrectnessReviewService();
