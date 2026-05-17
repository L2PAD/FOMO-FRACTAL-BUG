/**
 * Execution Quality Orchestrator
 *
 * Full pipeline:
 *   Input → Context Cluster → Store → Detect Anomaly →
 *   Check Suppression → Pattern Detect → Degradation Track →
 *   Style Analyze → Recommend → Build Alert → Deliver
 */

import { contextClusterService } from './context-cluster.service.js';
import { anomalyDetectorService } from './execution-anomaly-detector.service.js';
import { degradationTrackerService } from './degradation-tracker.service.js';
import { patternDetectorService } from './pattern-detector.service.js';
import { styleAnalyzerService } from './style-analyzer.service.js';
import { recommendationBuilderService } from './recommendation-builder.service.js';
import { alertBuilderService } from './execution-quality-alert-builder.service.js';
import { contextStatsRepo } from '../repositories/execution-context-stats.repository.js';
import { anomalyRepo } from '../repositories/execution-anomaly.repository.js';
import type { ExecutionScoreEntry } from '../types/execution-context.types.js';
import type { ExecutionAnomaly, FormattedAlert } from '../types/execution-anomaly.types.js';

export interface EQAInput {
  asset: string;
  marketId: string;
  executionScore: number;
  executionGrade: string;
  direction: string;
  regime: string;
  narrativePhase: string;
  volatility: number;
  entryStyle: string;
  entryScore: number;
  timingScore: number;
  slippageLeakage: number;
  opportunityCost: number;
  missedMove: number;
  confidence: number;
  edge: number;
  opportunityReason: string;
}

export interface EQAResult {
  contextKey: string;
  anomalyDetected: boolean;
  suppressed: boolean;
  anomaly: ExecutionAnomaly | null;
  formatted: FormattedAlert | null;
}

class ExecutionQualityOrchestrator {
  /**
   * Full pipeline: ingest score → detect → recommend → alert.
   */
  async process(input: EQAInput): Promise<EQAResult> {
    // 1. Context Cluster — build contextKey
    const { context, contextKey } = contextClusterService.cluster({
      direction: input.direction,
      regime: input.regime,
      narrativePhase: input.narrativePhase,
      volatility: input.volatility,
      entryStyle: input.entryStyle,
    });

    // 2. Build score entry
    const entry: ExecutionScoreEntry = {
      score: input.executionScore,
      grade: input.executionGrade,
      asset: input.asset,
      marketId: input.marketId,
      timestamp: new Date().toISOString(),
      entryScore: input.entryScore,
      timingScore: input.timingScore,
      slippageLeakage: input.slippageLeakage,
      opportunityCost: input.opportunityCost,
      missedMove: input.missedMove,
      confidence: input.confidence,
      edge: input.edge,
      opportunityReason: input.opportunityReason,
    };

    // 3. Store in context stats
    const stats = await contextStatsRepo.addEntry(contextKey, context, entry);

    // 4. Detect anomaly
    const detection = anomalyDetectorService.detect(stats.entries);

    if (!detection.detected) {
      return { contextKey, anomalyDetected: false, suppressed: false, anomaly: null, formatted: null };
    }

    // 5. Check suppression
    const isSuppressed = await anomalyDetectorService.isSuppressed(contextKey);
    if (isSuppressed) {
      console.log(`[EQA] Anomaly detected but SUPPRESSED for context ${contextKey}`);
      return { contextKey, anomalyDetected: true, suppressed: true, anomaly: null, formatted: null };
    }

    // 6. Pattern detection
    const pattern = patternDetectorService.detect(stats.entries);

    // 7. Degradation tracking
    const degradation = degradationTrackerService.analyze(stats.entries);

    // 8. Style analysis
    const styleAnalysis = styleAnalyzerService.analyze(stats.entries, context.executionStyle);

    // 9. Confidence drift contribution
    const confidenceDrift = this.calculateConfidenceDrift(stats.entries);

    // 10. Build recommendation
    const recommendation = recommendationBuilderService.build(
      context, pattern, degradation, styleAnalysis, detection.avgScore,
    );

    // 11. Build anomaly object
    const anomaly = alertBuilderService.buildAnomaly(
      contextKey, context, input.asset,
      detection, pattern, degradation, styleAnalysis, recommendation, confidenceDrift,
    );

    // 12. Save to MongoDB
    await anomalyRepo.save(anomaly);

    // 13. Format for display
    const formatted = alertBuilderService.format(anomaly);

    // 14. Deliver to Telegram (non-blocking, HIGH priority but rare)
    this.deliverToTelegram(anomaly, formatted).catch(err => {
      console.error('[EQA] Telegram delivery failed:', err?.message);
    });

    console.log(`[EQA] ANOMALY: ${input.asset} (${contextKey}) — ${detection.consecutiveLow} low scores, pattern: ${pattern.pattern}, action: ${recommendation.suggestedAction}`);

    return { contextKey, anomalyDetected: true, suppressed: false, anomaly, formatted };
  }

  /**
   * Calculate how much overconfidence contributed to poor execution.
   * If avg confidence was high but scores were low, there's a drift.
   */
  private calculateConfidenceDrift(entries: ExecutionScoreEntry[]): number {
    const lowEntries = entries.filter(e => e.score < 0.4);
    if (lowEntries.length === 0) return 0;

    const avgConfidence = lowEntries.reduce((s, e) => s + e.confidence, 0) / lowEntries.length;
    const avgScore = lowEntries.reduce((s, e) => s + e.score, 0) / lowEntries.length;

    // Drift = high confidence + low score
    const drift = Math.max(0, avgConfidence - avgScore);
    return Math.min(1, drift);
  }

  /**
   * Deliver anomaly alert via Telegram.
   */
  private async deliverToTelegram(anomaly: ExecutionAnomaly, formatted: FormattedAlert): Promise<void> {
    try {
      const { telegramDeliveryOrchestrator } = await import('../../telegram-delivery/services/telegram-delivery-orchestrator.service.js');
      await telegramDeliveryOrchestrator.deliverAlert({
        type: 'EXECUTION_ANOMALY',
        priority: anomaly.severity === 'CRITICAL' ? 'HIGH' : 'MEDIUM',
        title: `Execution Anomaly: ${anomaly.asset}`,
        body: formatted.htmlText,
        asset: anomaly.asset,
        marketId: `eqa-${anomaly.contextKey}`,
        dedupKey: anomaly.anomalyId,
        meta: {
          contextKey: anomaly.contextKey,
          pattern: anomaly.pattern.pattern,
          action: anomaly.recommendation.suggestedAction,
          avgScore: anomaly.avgScore,
        },
      });
      console.log(`[EQA] Telegram alert delivered for ${anomaly.asset} (${anomaly.contextKey})`);
    } catch (err: any) {
      console.error(`[EQA] Telegram delivery error: ${err?.message}`);
    }
  }

  /**
   * Get all anomalies.
   */
  async getAnomalies(limit = 50): Promise<ExecutionAnomaly[]> {
    return anomalyRepo.getAll(limit);
  }

  /**
   * Get unacknowledged anomalies.
   */
  async getUnacknowledged(limit = 20): Promise<ExecutionAnomaly[]> {
    return anomalyRepo.getUnacknowledged(limit);
  }

  /**
   * Acknowledge an anomaly.
   */
  async acknowledge(anomalyId: string): Promise<boolean> {
    return anomalyRepo.acknowledge(anomalyId);
  }

  /**
   * Get context stats overview.
   */
  async getContextOverview(): Promise<any[]> {
    const contexts = await contextStatsRepo.getActiveContexts(1);
    return contexts.map(c => ({
      contextKey: c.contextKey,
      context: c.context,
      entryCount: c.entries.length,
      totalCount: c.totalCount,
      lastScore: c.entries.length > 0 ? c.entries[c.entries.length - 1].score : null,
      avgScore: c.entries.length > 0
        ? Math.round(c.entries.reduce((s, e) => s + e.score, 0) / c.entries.length * 100) / 100
        : null,
      updatedAt: c.updatedAt,
    }));
  }
}

export const executionQualityOrchestrator = new ExecutionQualityOrchestrator();
