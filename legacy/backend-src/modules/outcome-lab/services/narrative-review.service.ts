/**
 * Narrative Review Service
 *
 * Teaches the system about social timing, crowd detection, narrative traps.
 * Was the narrative helpful or misleading?
 */

import type { NarrativeReview, DecisionTrace, ResolvedMarket } from '../types/outcome-lab.types.js';

class NarrativeReviewService {
  review(trace: DecisionTrace, resolved: ResolvedMarket): NarrativeReview {
    const notes: string[] = [];
    const si = trace.social;
    const outcomeYes = resolved.outcome === 'YES';

    if (!si.lifecycle) {
      return {
        lifecycleAtBest: null,
        saturationTooHigh: false,
        echoMisleading: false,
        narrativeHelped: false,
        narrativeTrap: false,
        notes: ['No social data available for this market'],
      };
    }

    const lifecycleAtBest = si.lifecycle;

    // Saturation analysis
    const saturationTooHigh = si.saturationScore > 0.65;
    if (saturationTooHigh) {
      notes.push(`Saturation was high (${(si.saturationScore * 100).toFixed(0)}%) — crowd was already positioned`);
    }

    // Echo analysis
    const echoMisleading = si.echoScore > 0.5 && si.originQuality < 0.4;
    if (echoMisleading) {
      notes.push('High echo but low origin quality — amplified noise, not signal');
    }

    // Was narrative in the right direction?
    const actionBullish = ['YES_NOW', 'YES_SMALL'].includes(trace.action);
    const narrativeBullish = si.lifecycle === 'EARLY' || si.lifecycle === 'EXPANDING';
    const narrativeAlignedWithAction = (actionBullish && narrativeBullish) || (!actionBullish && !narrativeBullish);

    // Narrative helped?
    const narrativeHelped = narrativeAlignedWithAction && (
      (actionBullish && outcomeYes) || (!actionBullish && !outcomeYes)
    );

    // Narrative trap: strong narrative led to wrong decision
    const narrativeTrap = narrativeAlignedWithAction && !(
      (actionBullish && outcomeYes) || (!actionBullish && !outcomeYes)
    ) && (si.saturationScore > 0.4 || si.echoScore > 0.4);

    if (narrativeHelped) {
      notes.push(`Narrative at ${si.lifecycle} stage correctly supported ${trace.action}`);
    }

    if (narrativeTrap) {
      notes.push(`NARRATIVE TRAP: ${si.lifecycle} narrative with ${(si.saturationScore * 100).toFixed(0)}% saturation led to wrong call`);
      if (si.lifecycle === 'SATURATED' || si.lifecycle === 'FADING') {
        notes.push('Lesson: high saturation often precedes reversal — don\'t follow the crowd');
      }
    }

    // Lifecycle-specific lessons
    if (si.lifecycle === 'EARLY' && outcomeYes && narrativeBullish) {
      notes.push('EARLY lifecycle + bullish outcome — early narratives are often predictive');
    }
    if (si.lifecycle === 'SATURATED' && !outcomeYes && narrativeBullish) {
      notes.push('SATURATED narrative + bearish outcome — crowd was wrong at peak consensus');
    }

    return {
      lifecycleAtBest,
      saturationTooHigh,
      echoMisleading,
      narrativeHelped,
      narrativeTrap,
      notes,
    };
  }
}

export const narrativeReviewService = new NarrativeReviewService();
