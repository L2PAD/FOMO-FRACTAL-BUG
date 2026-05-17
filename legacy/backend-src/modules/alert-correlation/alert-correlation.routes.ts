/**
 * Alert Correlation Routes
 *
 * POST /api/alert-correlation/analyze — Analyze batch of raw alerts
 * GET  /api/alert-correlation/meta-alerts — Recent meta-alerts
 * GET  /api/alert-correlation/history — Historical meta-alerts from DB
 * GET  /api/alert-correlation/regime — Current regime state
 * POST /api/alert-correlation/ingest — Ingest single alert (real-time)
 * POST /api/alert-correlation/clear — Clear state (testing)
 */

import type { FastifyInstance } from 'fastify';
import { correlationOrchestratorService } from './services/correlation-orchestrator.service.js';
import type { RawAlertRef } from './types/correlation.types.js';

export function registerAlertCorrelationRoutes(app: FastifyInstance) {
  // Analyze a batch of raw alerts
  app.post('/api/alert-correlation/analyze', async (req) => {
    const { alerts } = req.body as { alerts: RawAlertRef[] };
    if (!alerts?.length) return { ok: true, metaAlerts: [], message: 'No alerts provided' };

    const metaAlerts = await correlationOrchestratorService.analyze(alerts);
    return {
      ok: true,
      metaAlerts,
      count: metaAlerts.length,
      suppressedAlertIds: [...correlationOrchestratorService.getSuppressedAlertIds()],
    };
  });

  // Ingest a single alert (real-time mode)
  app.post('/api/alert-correlation/ingest', async (req) => {
    const alert = req.body as RawAlertRef;
    if (!alert?.alertId) return { ok: false, error: 'alertId required' };

    const metaAlerts = await correlationOrchestratorService.ingestAlert(alert);
    return { ok: true, metaAlerts, count: metaAlerts.length };
  });

  // Get recent meta-alerts
  app.get('/api/alert-correlation/meta-alerts', async (req) => {
    const { limit } = req.query as { limit?: string };
    const metaAlerts = correlationOrchestratorService.getRecent(Number(limit) || 20);
    return { ok: true, metaAlerts, count: metaAlerts.length };
  });

  // Get historical meta-alerts from DB
  app.get('/api/alert-correlation/history', async (req) => {
    const { limit } = req.query as { limit?: string };
    const metaAlerts = await correlationOrchestratorService.getHistory(Number(limit) || 50);
    return { ok: true, metaAlerts, count: metaAlerts.length };
  });

  // Get current regime state
  app.get('/api/alert-correlation/regime', async () => {
    const regime = correlationOrchestratorService.getRegimeState();
    return { ok: true, regime };
  });

  // Clear state (testing)
  app.post('/api/alert-correlation/clear', async () => {
    correlationOrchestratorService.clear();
    return { ok: true, message: 'Correlation state cleared' };
  });

  app.log.info('[Alert Correlation] Routes registered at /api/alert-correlation/*');
}
