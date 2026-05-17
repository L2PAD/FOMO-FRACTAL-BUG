/**
 * Execution Quality Alert Module — Routes
 *
 * POST /api/execution-quality-alert/ingest       — Ingest a score (full pipeline)
 * GET  /api/execution-quality-alert/anomalies     — List anomalies
 * GET  /api/execution-quality-alert/unacknowledged — Unacknowledged anomalies
 * POST /api/execution-quality-alert/acknowledge    — Acknowledge an anomaly
 * GET  /api/execution-quality-alert/contexts       — Context stats overview
 */

import type { FastifyInstance } from 'fastify';
import { executionQualityOrchestrator } from './services/execution-quality-orchestrator.service.js';
import type { EQAInput } from './services/execution-quality-orchestrator.service.js';

export async function executionQualityAlertRoutes(app: FastifyInstance): Promise<void> {
  /**
   * POST /ingest — Full pipeline: ingest score, detect anomaly, recommend.
   */
  app.post<{ Body: EQAInput }>('/ingest', async (request) => {
    const input = request.body;
    if (!input?.asset || input.executionScore == null) {
      return { ok: false, error: 'asset and executionScore required' };
    }

    // Set defaults for optional fields
    const fullInput: EQAInput = {
      asset: input.asset,
      marketId: input.marketId || '',
      executionScore: input.executionScore,
      executionGrade: input.executionGrade || (input.executionScore >= 0.7 ? 'B' : input.executionScore >= 0.4 ? 'D' : 'F'),
      direction: input.direction || 'LONG',
      regime: input.regime || 'RANGE',
      narrativePhase: input.narrativePhase || 'EXPANDING',
      volatility: input.volatility ?? 0.5,
      entryStyle: input.entryStyle || 'MARKET',
      entryScore: input.entryScore ?? input.executionScore,
      timingScore: input.timingScore ?? input.executionScore,
      slippageLeakage: input.slippageLeakage ?? 0,
      opportunityCost: input.opportunityCost ?? 0,
      missedMove: input.missedMove ?? 0,
      confidence: input.confidence ?? 0.5,
      edge: input.edge ?? 0,
      opportunityReason: input.opportunityReason || 'NONE',
    };

    const result = await executionQualityOrchestrator.process(fullInput);

    return {
      ok: true,
      contextKey: result.contextKey,
      anomalyDetected: result.anomalyDetected,
      suppressed: result.suppressed,
      anomaly: result.anomaly,
      formatted: result.formatted,
    };
  });

  /**
   * GET /anomalies — List all anomalies.
   */
  app.get<{ Querystring: { limit?: string } }>('/anomalies', async (request) => {
    const limit = parseInt(request.query.limit || '50', 10);
    const anomalies = await executionQualityOrchestrator.getAnomalies(limit);
    return { ok: true, anomalies, count: anomalies.length };
  });

  /**
   * GET /unacknowledged — Unacknowledged anomalies only.
   */
  app.get<{ Querystring: { limit?: string } }>('/unacknowledged', async (request) => {
    const limit = parseInt(request.query.limit || '20', 10);
    const anomalies = await executionQualityOrchestrator.getUnacknowledged(limit);
    return { ok: true, anomalies, count: anomalies.length };
  });

  /**
   * POST /acknowledge — Mark anomaly as acknowledged.
   */
  app.post<{ Body: { anomalyId: string } }>('/acknowledge', async (request) => {
    const { anomalyId } = request.body;
    if (!anomalyId) return { ok: false, error: 'anomalyId required' };
    const result = await executionQualityOrchestrator.acknowledge(anomalyId);
    return { ok: true, acknowledged: result };
  });

  /**
   * GET /contexts — Context stats overview.
   */
  app.get('/contexts', async () => {
    const contexts = await executionQualityOrchestrator.getContextOverview();
    return { ok: true, contexts, count: contexts.length };
  });

  console.log('[EQA] Execution Quality Alert routes registered at /api/execution-quality-alert/*');
}
