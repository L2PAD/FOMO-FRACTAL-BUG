/**
 * Alert Engine Routes
 *
 * POST /api/alert-engine/process         — Process batch of cases (called by pipeline)
 * GET  /api/alert-engine/history         — Get recent alert history
 * GET  /api/alert-engine/stats           — Get alert engine stats
 * POST /api/alert-engine/flush           — Force flush pending batch
 * POST /api/alert-engine/clear           — Clear state (testing)
 */

import type { FastifyInstance } from 'fastify';
import { alertEngineOrchestrator } from './services/alert-orchestrator.service.js';

export async function alertEngineRoutes(app: FastifyInstance): Promise<void> {
  /**
   * POST /api/alert-engine/process — Process batch of cases from prediction pipeline
   */
  app.post<{ Body: { cases: Record<string, any>[] } }>('/process', async (request) => {
    const { cases } = request.body;
    if (!cases?.length) return { ok: false, error: 'cases array required' };

    const result = alertEngineOrchestrator.processBatch(cases);
    return {
      ok: true,
      processed: result.processed,
      triggered: result.triggered,
      filtered: result.filtered,
      delivered: result.delivered,
      alerts: result.alerts,
    };
  });

  /**
   * GET /api/alert-engine/history — Recent alert history
   */
  app.get<{ Querystring: { limit?: string } }>('/history', async (request) => {
    const limit = parseInt(request.query.limit || '50', 10);
    const alerts = alertEngineOrchestrator.getHistory(limit);
    return { ok: true, alerts, count: alerts.length };
  });

  /**
   * GET /api/alert-engine/stats — Alert engine stats
   */
  app.get('/stats', async () => {
    const stats = alertEngineOrchestrator.getStats();
    return { ok: true, stats };
  });

  /**
   * POST /api/alert-engine/flush — Force flush pending batch
   */
  app.post('/flush', async () => {
    const digest = alertEngineOrchestrator.flushBatch();
    return { ok: true, flushed: !!digest, digest };
  });

  /**
   * POST /api/alert-engine/clear — Clear all state (testing only)
   */
  app.post('/clear', async () => {
    alertEngineOrchestrator.clearAll();
    return { ok: true, message: 'Alert engine state cleared' };
  });
}
