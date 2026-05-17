/**
 * Recommendation Builder
 *
 * Generates actionable recommendations based on:
 *   - Detected pattern (MISSED_MOVES, BAD_ENTRIES, etc.)
 *   - Style analysis (which style performs better)
 *   - Context (regime, narrative, volatility)
 *   - Degradation state
 */

import type { ExecutionContext } from '../types/execution-context.types.js';
import type {
  AnomalyPattern,
  DegradationResult,
  StyleAnalysisResult,
  Recommendation,
  SuggestedAction,
} from '../types/execution-anomaly.types.js';

class RecommendationBuilderService {
  /**
   * Build a recommendation from anomaly analysis data.
   */
  build(
    context: ExecutionContext,
    pattern: AnomalyPattern,
    degradation: DegradationResult,
    styleAnalysis: StyleAnalysisResult,
    avgScore: number,
  ): Recommendation {
    const details: string[] = [];
    let action: SuggestedAction;
    let from = context.executionStyle;
    let to = styleAnalysis.bestStyle;
    let reason: string;
    let confidence = 0.5;

    // Primary decision: based on pattern
    switch (pattern.pattern) {
      case 'MISSED_MOVES':
        action = this.handleMissedMoves(context, styleAnalysis);
        reason = this.buildMissedMovesReason(context, styleAnalysis);
        confidence = 0.75;
        details.push(`WAIT strategy too conservative in ${context.narrative} narratives`);
        if (context.narrative === 'EARLY') {
          details.push('Early narrative: moves are fast — prefer aggressive entry');
          confidence = 0.85;
        }
        break;

      case 'BAD_ENTRIES':
        action = 'ADJUST_TIMING';
        reason = 'Entries consistently outside optimal zone — need better price targeting';
        if (context.executionStyle === 'MARKET') {
          action = 'USE_LIMIT';
          to = 'LIMIT';
          reason = 'MARKET entries leaking edge — switch to LIMIT for better fills';
        }
        confidence = 0.7;
        details.push(`Entry score pattern: consistently below threshold`);
        break;

      case 'HIGH_SLIPPAGE':
        if (context.executionStyle === 'MARKET') {
          action = 'SWITCH_STYLE';
          to = 'LIMIT';
          reason = 'High slippage on MARKET orders — switch to LIMIT or STAGGER';
        } else {
          action = 'REDUCE_SIZE';
          reason = 'Slippage elevated — reduce position size or use STAGGER entries';
          to = 'STAGGER';
        }
        confidence = 0.65;
        details.push('Execution leaking value through slippage');
        break;

      case 'LATE_TIMING':
        action = 'USE_MARKET';
        to = 'MARKET';
        reason = 'Late entries missing edge — need faster execution';
        if (context.regime === 'TREND') {
          details.push('In TREND regime, speed matters more than price');
          confidence = 0.8;
        } else {
          details.push('Edge decaying before entry — tighten timing');
          confidence = 0.65;
        }
        break;

      default: // MIXED
        action = this.handleMixed(context, styleAnalysis, degradation);
        reason = this.buildMixedReason(context, styleAnalysis, degradation);
        confidence = 0.5;
        details.push('Multiple issues — review execution approach holistically');
    }

    // Boost/lower confidence based on degradation
    if (degradation.state === 'DEGRADING') {
      confidence = Math.min(1, confidence + 0.1);
      details.push(`Degradation detected (slope: ${degradation.slope})`);
    }
    if (degradation.state === 'NOISE') {
      confidence = Math.max(0.3, confidence - 0.1);
    }

    // Boost confidence if style analysis shows clear better alternative
    if (styleAnalysis.delta > 0.2) {
      confidence = Math.min(1, confidence + 0.1);
      details.push(`${styleAnalysis.bestStyle} outperforms by ${(styleAnalysis.delta * 100).toFixed(0)}%`);
    }

    // Critical score override
    if (avgScore < 0.2) {
      action = 'PAUSE_CONTEXT';
      reason = `Execution quality critically low (${(avgScore * 100).toFixed(0)}%) — pause entries in this context`;
      confidence = 0.9;
    }

    return {
      suggestedAction: action,
      from,
      to,
      reason,
      confidence: Math.round(confidence * 100) / 100,
      details,
    };
  }

  private handleMissedMoves(context: ExecutionContext, sa: StyleAnalysisResult): SuggestedAction {
    if (context.executionStyle === 'WAIT' || context.executionStyle === 'LIMIT') {
      return 'USE_MARKET';
    }
    if (sa.delta > 0.15) return 'SWITCH_STYLE';
    return 'ADJUST_TIMING';
  }

  private buildMissedMovesReason(context: ExecutionContext, sa: StyleAnalysisResult): string {
    if (context.executionStyle === 'WAIT') {
      return `WAIT strategy too conservative — MARKET avg: ${(sa.bestAvgScore * 100).toFixed(0)}% vs WAIT: ${(sa.currentAvgScore * 100).toFixed(0)}%`;
    }
    return 'Moves happening faster than execution — need more aggressive entry style';
  }

  private handleMixed(context: ExecutionContext, sa: StyleAnalysisResult, deg: DegradationResult): SuggestedAction {
    if (deg.state === 'DEGRADING') return 'PAUSE_CONTEXT';
    if (sa.delta > 0.2) return 'SWITCH_STYLE';
    return 'NO_CHANGE';
  }

  private buildMixedReason(context: ExecutionContext, sa: StyleAnalysisResult, deg: DegradationResult): string {
    if (deg.state === 'DEGRADING') {
      return 'Systematic degradation — pause and review approach';
    }
    if (sa.delta > 0.2) {
      return `Consider ${sa.bestStyle} (${(sa.bestAvgScore * 100).toFixed(0)}%) over ${sa.currentStyle} (${(sa.currentAvgScore * 100).toFixed(0)}%)`;
    }
    return 'Multiple minor issues — continue monitoring';
  }
}

export const recommendationBuilderService = new RecommendationBuilderService();
