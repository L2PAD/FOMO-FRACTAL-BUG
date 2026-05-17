/**
 * Execution Quality Alert Builder
 *
 * Formats anomaly data into human-readable alerts for Telegram and UI.
 */

import type { ExecutionContext } from '../types/execution-context.types.js';
import type {
  ExecutionAnomaly,
  AnomalyPattern,
  DegradationResult,
  StyleAnalysisResult,
  Recommendation,
  FormattedAlert,
} from '../types/execution-anomaly.types.js';
import type { AnomalyDetectionResult } from './execution-anomaly-detector.service.js';
import { anomalyRepo } from '../repositories/execution-anomaly.repository.js';

const SUPPRESSION_HOURS = 24;

class ExecutionQualityAlertBuilderService {
  /**
   * Build a full ExecutionAnomaly object.
   */
  buildAnomaly(
    contextKey: string,
    context: ExecutionContext,
    asset: string,
    detection: AnomalyDetectionResult,
    pattern: AnomalyPattern,
    degradation: DegradationResult,
    styleAnalysis: StyleAnalysisResult,
    recommendation: Recommendation,
    confidenceDrift: number,
  ): ExecutionAnomaly {
    const severity = detection.consecutiveLow >= 5 || detection.avgScore < 0.2 ? 'CRITICAL' : 'WARNING';

    return {
      anomalyId: `eqa_${Date.now()}_${asset}_${contextKey.replace(/:/g, '_').substring(0, 30)}`,
      type: 'EXECUTION_ANOMALY',
      contextKey,
      context,
      asset,
      consecutiveLow: detection.consecutiveLow,
      avgScore: detection.avgScore,
      worstScore: detection.worstScore,
      scores: detection.scores,
      consistency: detection.consistency,
      sampleSize: detection.sampleSize,
      severity,
      pattern,
      degradation,
      styleAnalysis,
      recommendation,
      confidenceDriftContribution: Math.round(confidenceDrift * 100) / 100,
      suppressedUntil: new Date(Date.now() + SUPPRESSION_HOURS * 60 * 60 * 1000).toISOString(),
      acknowledged: false,
      timestamp: new Date().toISOString(),
    };
  }

  /**
   * Format anomaly for Telegram/UI display.
   */
  format(anomaly: ExecutionAnomaly): FormattedAlert {
    const ctx = anomaly.context;
    const title = 'EXECUTION ANOMALY DETECTED';

    const contextLine = `${ctx.direction} / ${ctx.regime} / ${ctx.narrative} / ${ctx.volatilityBucket} VOL`;
    const issueLine = `Execution score degraded (avg: ${(anomaly.avgScore * 100).toFixed(0)}%, ${anomaly.consecutiveLow} cases)`;

    const patternLines: string[] = [];
    for (const detail of anomaly.pattern.details) {
      patternLines.push(detail);
    }

    const currentStyleLine = anomaly.styleAnalysis.currentStyle;

    const suggestedLine = anomaly.recommendation.suggestedAction === 'SWITCH_STYLE'
      ? `SWITCH TO ${anomaly.recommendation.to}`
      : anomaly.recommendation.suggestedAction === 'PAUSE_CONTEXT'
        ? 'PAUSE ENTRIES IN THIS CONTEXT'
        : anomaly.recommendation.suggestedAction.replace(/_/g, ' ');

    const whyLines: string[] = [];
    if (anomaly.styleAnalysis.bestAvgScore > 0) {
      whyLines.push(`${anomaly.styleAnalysis.bestStyle} avg score: ${(anomaly.styleAnalysis.bestAvgScore * 100).toFixed(0)}%`);
    }
    if (anomaly.styleAnalysis.currentAvgScore > 0) {
      whyLines.push(`${anomaly.styleAnalysis.currentStyle} avg score: ${(anomaly.styleAnalysis.currentAvgScore * 100).toFixed(0)}%`);
    }
    for (const d of anomaly.recommendation.details.slice(0, 2)) {
      whyLines.push(d);
    }

    const degradationNote = anomaly.degradation.state === 'DEGRADING'
      ? `\nTrend: DEGRADING (slope: ${anomaly.degradation.slope})`
      : '';

    const confidenceLine = `Confidence: ${anomaly.recommendation.confidence >= 0.7 ? 'HIGH' : anomaly.recommendation.confidence >= 0.5 ? 'MEDIUM' : 'LOW'}`;

    // Full plain text
    const fullText = [
      `EXECUTION ANOMALY DETECTED`,
      ``,
      `Context:`,
      `  ${contextLine}`,
      ``,
      `Issue:`,
      `  ${issueLine}`,
      ``,
      `Pattern:`,
      ...patternLines.map(l => `  ${l}`),
      ``,
      `Current style: ${currentStyleLine}`,
      ``,
      `Suggested:`,
      `  ${suggestedLine}`,
      ``,
      `Why:`,
      ...whyLines.map(l => `  ${l}`),
      degradationNote,
      ``,
      confidenceLine,
    ].filter(Boolean).join('\n');

    // HTML for Telegram
    const htmlText = [
      `<b>EXECUTION ANOMALY DETECTED</b>`,
      ``,
      `<b>Context:</b>`,
      `${contextLine}`,
      ``,
      `<b>Issue:</b>`,
      `${issueLine}`,
      ``,
      `<b>Pattern:</b>`,
      ...patternLines.map(l => `- ${l}`),
      ``,
      `<b>Current style:</b> ${currentStyleLine}`,
      ``,
      `<b>Suggested:</b>`,
      `→ ${suggestedLine}`,
      ``,
      `<b>Why:</b>`,
      ...whyLines.map(l => `- ${l}`),
      degradationNote ? `\n<i>Trend: DEGRADING (slope: ${anomaly.degradation.slope})</i>` : '',
      ``,
      `<b>${confidenceLine}</b>`,
    ].filter(Boolean).join('\n');

    return {
      title,
      contextLine,
      issueLine,
      patternLines,
      currentStyleLine,
      suggestedLine,
      whyLines,
      confidenceLine,
      fullText,
      htmlText,
    };
  }
}

export const alertBuilderService = new ExecutionQualityAlertBuilderService();
