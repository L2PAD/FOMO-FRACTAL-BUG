/**
 * Execution Score Routes
 *
 * POST /api/execution-score/evaluate       — Score a single case
 * POST /api/execution-score/evaluate/batch  — Score a batch
 * GET  /api/execution-score/styles          — Style performance stats
 * POST /api/execution-score/clear           — Clear data (testing)
 */

import type { FastifyInstance } from 'fastify';
import { executionScoreOrchestrator } from './services/execution-score-orchestrator.service.js';
import { executionQualityAlertService } from './services/execution-quality-alert.service.js';

export async function executionScoreRoutes(app: FastifyInstance): Promise<void> {
  /**
   * POST /api/execution-score/evaluate — Single case execution score
   */
  app.post<{ Body: { case: Record<string, any>; snapshots?: { timestamp: string; marketProb: number }[] } }>('/evaluate', async (request) => {
    const { case: caseData, snapshots } = request.body;
    if (!caseData) return { ok: false, error: 'case data required' };

    const result = executionScoreOrchestrator.score(caseData, snapshots);

    // Ingest score into quality alert system
    let qualityAlert = null;
    try {
      qualityAlert = await executionQualityAlertService.ingestScore({
        asset: caseData.asset || caseData.symbol || 'UNKNOWN',
        context: result.context?.regime || 'UNKNOWN',
        score: result.executionScore,
        grade: result.executionGrade,
        timestamp: new Date().toISOString(),
        marketId: caseData.marketId,
      });
    } catch (err) {
      // Non-blocking
    }

    return { ok: true, result, qualityAlert };
  });

  /**
   * POST /api/execution-score/evaluate/batch — Batch execution scoring
   */
  app.post<{ Body: { cases: Record<string, any>[] } }>('/evaluate/batch', async (request) => {
    const { cases } = request.body;
    if (!cases?.length) return { ok: false, error: 'cases array required' };

    const results = executionScoreOrchestrator.scoreBatch(cases);
    return { ok: true, results, count: Object.keys(results).length };
  });

  /**
   * GET /api/execution-score/styles — Style performance aggregation
   */
  app.get('/styles', async () => {
    const perf = executionScoreOrchestrator.getStylePerformance();
    return { ok: true, ...perf };
  });

  /**
   * GET /api/execution-score/quality-alerts — Get execution quality anomaly alerts
   */
  app.get<{ Querystring: { limit?: string } }>('/quality-alerts', async (request) => {
    const limit = parseInt(request.query.limit || '50', 10);
    const alerts = await executionQualityAlertService.getAlerts(limit);
    const streaks = await executionQualityAlertService.getStreaks();
    return { ok: true, alerts, streaks, count: alerts.length };
  });

  /**
   * POST /api/execution-score/quality-alerts/ingest — Manually ingest a score for testing
   */
  app.post<{ Body: { asset: string; context: string; score: number; grade?: string; marketId?: string } }>('/quality-alerts/ingest', async (request) => {
    const { asset, context, score, grade, marketId } = request.body;
    if (!asset || !context || score == null) return { ok: false, error: 'asset, context, score required' };

    const alert = await executionQualityAlertService.ingestScore({
      asset,
      context,
      score,
      grade: grade || (score >= 0.7 ? 'A' : score >= 0.4 ? 'B' : 'D'),
      timestamp: new Date().toISOString(),
      marketId,
    });

    return { ok: true, anomalyDetected: !!alert, alert };
  });

  /**
   * POST /api/execution-score/quality-alerts/acknowledge — Acknowledge an alert
   */
  app.post<{ Body: { alertId: string } }>('/quality-alerts/acknowledge', async (request) => {
    const { alertId } = request.body;
    if (!alertId) return { ok: false, error: 'alertId required' };
    const result = await executionQualityAlertService.acknowledge(alertId);
    return { ok: true, acknowledged: result };
  });

  /**
   * POST /api/execution-score/clear — Clear data (testing)
   */
  app.post('/clear', async () => {
    executionScoreOrchestrator.clearAll();
    return { ok: true, message: 'Execution score data cleared' };
  });
}
