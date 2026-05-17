/**
 * Scaling Policy Service
 *
 * What to do with an existing position: ADD / HOLD / NO_ADD
 */

import type { ScalingPlan, ScalingBias, SpreadRegime, DepthQuality } from '../types/execution.types.js';

class ScalingPolicyService {
  assess(
    edge: number,
    repricingState: string,
    spreadRegime: SpreadRegime,
    depthQuality: DepthQuality,
    socialSaturation: number,
    confidence: number,
    edgeCompressed: boolean,
    positionOversized: boolean,
  ): ScalingPlan {
    // NO_ADD conditions (hard blocks)
    if (positionOversized) {
      return { scalingBias: 'NO_ADD', reason: 'Position already at max allocation' };
    }
    if (edgeCompressed) {
      return { scalingBias: 'NO_ADD', reason: 'Edge significantly compressed — no adding' };
    }
    if (repricingState === 'overheated' || repricingState === 'crowded') {
      return { scalingBias: 'NO_ADD', reason: `Repricing ${repricingState} — adding increases risk` };
    }
    if (spreadRegime === 'BROKEN' || depthQuality === 'FRAGILE') {
      return { scalingBias: 'NO_ADD', reason: 'Market microstructure too poor for scaling' };
    }
    if (socialSaturation > 0.70) {
      return { scalingBias: 'NO_ADD', reason: 'Narrative saturated — adding at consensus peak is dangerous' };
    }

    // ADD conditions
    const absEdge = Math.abs(edge);

    if (
      absEdge >= 0.08 &&
      confidence >= 0.6 &&
      ['fresh_mispricing', 'active_repricing', 'early_signal'].includes(repricingState) &&
      (spreadRegime === 'NARROW' || spreadRegime === 'NORMAL') &&
      socialSaturation < 0.50
    ) {
      return { scalingBias: 'ADD', reason: 'Edge alive + good conditions + not overcrowded — add to position' };
    }

    // On retrace
    if (
      absEdge >= 0.06 &&
      repricingState === 'stalled' &&
      confidence >= 0.5 &&
      spreadRegime !== 'WIDE'
    ) {
      return { scalingBias: 'ADD', reason: 'Stalled repricing with live edge — add on retrace' };
    }

    // Default: HOLD
    return { scalingBias: 'HOLD', reason: 'Conditions acceptable but not optimal for scaling — hold current size' };
  }
}

export const scalingPolicyService = new ScalingPolicyService();
