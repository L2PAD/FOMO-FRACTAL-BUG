/**
 * Execution Trace Service
 *
 * Saves extended execution traces with context, direction, and recommendation.
 * Reads from existing Outcome Lab traces and enriches with execution data.
 */

import type { ExecutionTrace, Direction, Regime, NarrativePhase } from '../types/execution-score.types.js';

class ExecutionTraceService {
  /**
   * Build an execution trace from a pipeline case.
   */
  buildTrace(caseData: Record<string, any>): ExecutionTrace {
    const analysis = caseData.analysis || {};
    const reco = caseData.recommendation || {};
    const el = caseData.executionLayer || {};
    const repr = caseData.repricing || {};
    const si = caseData.socialIntel || {};

    const action = reco.action || '';
    const direction: Direction = ['YES_NOW', 'YES_SMALL', 'YES'].includes(action) ? 'LONG' : 'SHORT';

    return {
      marketId: caseData.market_id || '',
      asset: caseData.asset || '',
      timestamp: new Date().toISOString(),
      direction,
      recommendation: {
        action,
        entryStyle: el.entryStyle || 'ENTER_LIMIT',
        confidence: analysis.model_confidence || 0,
        edge: analysis.net_edge || 0,
      },
      execution: {
        entryStyle: el.entryStyle || '',
        slippageRisk: el.slippageRisk || 0,
        entryQualityScore: el.entryQualityScore || 0,
        spreadRegime: el.spreadRegime || 'NORMAL',
        depthQuality: el.depthQuality || 'OK',
      },
      context: {
        regime: this.inferRegime(repr.repricing_state, analysis),
        narrativePhase: this.inferNarrative(si),
        volatility: analysis.prob_volatility || 0,
        repricing: repr.repricing_state || 'stalled',
      },
      marketProb: analysis.market_prob || 0.5,
    };
  }

  private inferRegime(repricing: string, analysis: Record<string, any>): Regime {
    if (['fresh_mispricing', 'early_repricing', 'active_repricing'].includes(repricing)) return 'TREND';
    if (['overheated', 'crowded'].includes(repricing)) return 'TRANSITION';
    return 'RANGE';
  }

  private inferNarrative(si: Record<string, any>): NarrativePhase {
    const sat = si?.saturationScore || si?.saturation || 0;
    const lifecycle = si?.lifecyclePhase || si?.lifecycle || '';

    if (lifecycle === 'EXHAUSTED' || sat > 0.85) return 'EXHAUSTED';
    if (lifecycle === 'SATURATED' || sat > 0.65) return 'SATURATED';
    if (lifecycle === 'EXPANDING' || sat > 0.35) return 'EXPANDING';
    return 'EARLY';
  }
}

export const executionTraceService = new ExecutionTraceService();
