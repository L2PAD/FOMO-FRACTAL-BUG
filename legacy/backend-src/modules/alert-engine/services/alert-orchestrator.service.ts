/**
 * Alert Engine Orchestrator
 *
 * The main entry point for the alert pipeline.
 * Pipeline: StateTransition → QualityGate → Detector → Trigger → Priority → Dedup → Formatter → Digest → Delivery
 */

import { stateTransitionService } from './state-transition.service.js';
import { alertQualityGateService } from './alert-quality-gate.service.js';
import { alertDetectorService } from './alert-detector.service.js';
import { priorityEngineService } from './priority-engine.service.js';
import { dedupEngineService } from './dedup-engine.service.js';
import { alertFormatterService } from './alert-formatter.service.js';
import { digestBuilderService } from './digest-builder.service.js';
import { deliveryService } from './delivery.service.js';
import { correlationOrchestratorService } from '../../alert-correlation/services/correlation-orchestrator.service.js';
import type { AlertState, AlertPayload } from '../types/alert.types.js';
import type { RawAlertRef } from '../../alert-correlation/types/correlation.types.js';

// Persistent alert history (in-memory, recent 500)
const alertHistory: AlertPayload[] = [];
const MAX_HISTORY = 500;

interface ProcessResult {
  processed: number;
  triggered: number;
  filtered: number;
  delivered: number;
  alerts: AlertPayload[];
}

class AlertEngineOrchestrator {
  /**
   * Process a batch of cases from the prediction pipeline.
   * This is the main entry point called after each /api/prediction/run.
   */
  processBatch(cases: Record<string, any>[]): ProcessResult {
    let processed = 0;
    let triggered = 0;
    let filtered = 0;
    let delivered = 0;
    const alerts: AlertPayload[] = [];

    for (const c of cases) {
      processed++;
      const result = this.processCase(c);
      if (result === 'filtered') filtered++;
      else if (result === 'deduped') filtered++;
      else if (result) {
        triggered++;
        alerts.push(result);
      }
    }

    // Deliver all produced alerts
    for (const alert of alerts) {
      const { immediate, batchReady } = digestBuilderService.process(alert);

      if (immediate) {
        if (immediate.tier === 'HIGH') {
          deliveryService.broadcastHighPriority(immediate);
        } else {
          deliveryService.sendRealtime(immediate);
        }
        delivered++;
      }

      if (batchReady) {
        deliveryService.sendBatchDigest(batchReady);
      }
    }

    // Feed alerts to correlation engine for meta-alert detection
    if (alerts.length >= 2) {
      const rawRefs: RawAlertRef[] = alerts.map(a => ({
        alertId: `alert_${a.marketId}_${Date.now()}`,
        marketId: a.marketId,
        type: a.type as RawAlertRef['type'],
        action: a.action,
        priority: a.tier as RawAlertRef['priority'],
        timestamp: new Date(a.timestamp).getTime(),
        asset: a.asset,
        question: a.question,
        edge: a.edge,
        confidence: a.confidence,
        conviction: a.conviction,
        entryStyle: a.entryStyle,
        reasoning: a.reasoning,
        reasons: a.reasons,
        risks: a.risks,
        factors: a.factors,
        social: a.social,
        project: a.project,
      }));
      correlationOrchestratorService.analyze(rawRefs).catch(() => {});
    }

    return { processed, triggered, filtered, delivered, alerts };
  }

  /**
   * Process a single case through the full alert pipeline.
   */
  private processCase(c: Record<string, any>): AlertPayload | 'filtered' | 'deduped' | null {
    const marketId = c.market_id || '';
    const analysis = c.analysis || {};
    const reco = c.recommendation || {};
    const repr = c.repricing || {};
    const el = c.executionLayer || {};
    const pi = c.projectIntel || {};
    const si = c.socialIntel || {};

    if (!marketId) return null;

    // 1. Build current state
    const currentState: AlertState = {
      action: reco.action || '',
      entryStyle: el.entryStyle || '',
      exitAction: el.exitAction || 'HOLD',
      repricing: repr.repricing_state || '',
      edge: analysis.net_edge || 0,
      tier: null,
    };

    // 2. Detect state transitions
    const transition = stateTransitionService.detect(marketId, currentState);
    if (!transition.hasTransition) return null; // No change → no alert

    // 3. Quality Gate
    const gateResult = alertQualityGateService.check({
      edge: analysis.net_edge || 0,
      confidence: analysis.model_confidence || 0,
      action: reco.action || '',
      entryStyle: el.entryStyle || '',
      repricing: repr.repricing_state || '',
      projectVerdict: pi.verdict || null,
      exitAction: el.exitAction || 'HOLD',
      alignment: analysis.alignment_score || 0,
      transitionSignificance: transition.significance,
    });

    if (!gateResult.passed) return 'filtered';

    // 4. Detect if this warrants an alert
    const trigger = alertDetectorService.detect({
      marketId,
      question: c.question || '',
      asset: c.asset || '',
      action: reco.action || '',
      edge: analysis.net_edge || 0,
      confidence: analysis.model_confidence || 0,
      alignment: analysis.alignment_score || 0,
      repricing: repr.repricing_state || '',
      entryStyle: el.entryStyle || '',
      exitAction: el.exitAction || 'HOLD',
      entryQualityScore: el.entryQualityScore || 0,
      socialSaturation: si?.saturationScore || si?.saturation || 0,
      transitions: transition.transitions,
      transitionSignificance: transition.significance,
    });

    if (!trigger) return 'filtered';

    // 5. Compute priority
    const { priorityScore, tier } = priorityEngineService.compute({
      edge: analysis.net_edge || 0,
      confidence: analysis.model_confidence || 0,
      alignment: analysis.alignment_score || 0,
      entryQualityScore: el.entryQualityScore || 0,
      repricing: repr.repricing_state || '',
      tier: trigger.tier,
    });

    // 6. Dedup check
    const dedupState = `${currentState.repricing}:${currentState.exitAction}`;
    const dedup = dedupEngineService.shouldSend(
      marketId,
      currentState.action,
      dedupState,
      tier,
      trigger.type,
    );

    if (!dedup.send) return 'deduped';

    // 7. Format alert
    const alert = alertFormatterService.format({
      type: trigger.type,
      tier,
      urgency: trigger.urgency,
      priority: priorityScore,
      case: c,
    });

    // 8. Store in history
    alertHistory.unshift(alert);
    if (alertHistory.length > MAX_HISTORY) alertHistory.length = MAX_HISTORY;

    return alert;
  }

  /**
   * Get recent alert history.
   */
  getHistory(limit = 50): AlertPayload[] {
    return alertHistory.slice(0, limit);
  }

  /**
   * Get stats.
   */
  getStats() {
    const now = Date.now();
    const last1h = alertHistory.filter(a => now - new Date(a.timestamp).getTime() < 3600000);
    const last24h = alertHistory.filter(a => now - new Date(a.timestamp).getTime() < 86400000);

    return {
      totalHistory: alertHistory.length,
      last1h: last1h.length,
      last24h: last24h.length,
      highLast1h: last1h.filter(a => a.tier === 'HIGH').length,
      pendingBatch: digestBuilderService.getPendingCount(),
      activeCooldowns: dedupEngineService.getCooldownCount(),
      connectedClients: deliveryService.getClientCount(),
    };
  }

  /**
   * Flush pending batch (manual trigger).
   */
  flushBatch() {
    const digest = digestBuilderService.flushBatch();
    if (digest) {
      deliveryService.sendBatchDigest(digest);
      return digest;
    }
    return null;
  }

  /**
   * Clear state (for testing).
   */
  clearAll(): void {
    stateTransitionService.clearAll();
    dedupEngineService.clearAll();
    alertHistory.length = 0;
  }
}

export const alertEngineOrchestrator = new AlertEngineOrchestrator();
