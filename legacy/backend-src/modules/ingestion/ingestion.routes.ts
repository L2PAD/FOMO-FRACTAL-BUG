/**
 * Ingestion Admin Routes
 * ======================
 * Admin API for controlling and monitoring the ingestion pipeline.
 *
 * Endpoints:
 * - POST /bridge/run       — Trigger manual bridge ingestion
 * - GET  /health           — Health snapshot (metrics, alerts)
 * - GET  /runs             — Recent ingestion runs
 * - GET  /raw-events/stats — Raw events collection stats
 */

import type { FastifyInstance } from 'fastify';
import { ingestionOrchestratorService } from './ingestion.orchestrator.service.js';
import { ingestionMetricsService } from './ingestion.metrics.service.js';
import { ingestionScheduler } from './ingestion.scheduler.js';
import { RawEventModel } from './models/raw-event.model.js';

export async function registerIngestionRoutes(app: FastifyInstance): Promise<void> {
  /**
   * POST /bridge/run — Trigger bridge ingestion
   */
  app.post('/bridge/run', async (request, reply) => {
    try {
      const body = (request.body ?? {}) as {
        limit?: number;
        sinceMinutes?: number;
        seedAll?: boolean;
      };

      const result = await ingestionOrchestratorService.runBridgeIngestion({
        limit: body.limit ?? 300,
        sinceMinutes: body.sinceMinutes ?? 180,
        seedAll: body.seedAll ?? false,
      });

      return { ok: true, data: result };
    } catch (err: any) {
      if (err.message?.includes('LOCK_BUSY')) {
        return reply.code(409).send({ ok: false, error: 'LOCK_BUSY', message: 'Ingestion already running' });
      }
      return reply.code(500).send({ ok: false, error: err.message });
    }
  });

  /**
   * POST /news/run — Trigger news ingestion
   */
  app.post('/news/run', async (request, reply) => {
    try {
      const body = (request.body ?? {}) as {
        limit?: number;
        sinceMinutes?: number;
        seedAll?: boolean;
      };

      const result = await ingestionOrchestratorService.runNewsIngestion({
        limit: body.limit ?? 300,
        sinceMinutes: body.sinceMinutes ?? 180,
        seedAll: body.seedAll ?? false,
      });

      return { ok: true, data: result };
    } catch (err: any) {
      if (err.message?.includes('LOCK_BUSY')) {
        return reply.code(409).send({ ok: false, error: 'LOCK_BUSY', message: 'News ingestion already running' });
      }
      return reply.code(500).send({ ok: false, error: err.message });
    }
  });

  /**
   * POST /all/run — Run all adapters (twitter + news)
   */
  app.post('/all/run', async (request, reply) => {
    try {
      const body = (request.body ?? {}) as {
        limit?: number;
        sinceMinutes?: number;
        seedAll?: boolean;
      };

      const results = await ingestionOrchestratorService.runAll({
        limit: body.limit ?? 300,
        sinceMinutes: body.sinceMinutes ?? 180,
        seedAll: body.seedAll ?? false,
      });

      return { ok: true, data: { sources: results.length, results } };
    } catch (err: any) {
      return reply.code(500).send({ ok: false, error: err.message });
    }
  });

  /**
   * GET /health — Ingestion health snapshot
   */
  app.get('/health', async () => {
    const health = await ingestionMetricsService.getHealth();
    const schedulerStatus = ingestionScheduler.getStatus();

    return {
      ok: true,
      data: {
        ...health,
        scheduler: schedulerStatus,
      },
    };
  });

  /**
   * GET /runs — Recent ingestion runs
   */
  app.get('/runs', async (request) => {
    const query = request.query as { limit?: string };
    const limit = Math.min(parseInt(query.limit || '20', 10), 100);
    const runs = await ingestionMetricsService.getRecentRuns(limit);

    return { ok: true, data: { count: runs.length, runs } };
  });

  /**
   * GET /raw-events/stats — Raw events stats
   */
  app.get('/raw-events/stats', async () => {
    const total = await RawEventModel.countDocuments();
    const processed = await RawEventModel.countDocuments({ processed: true });
    const unprocessed = await RawEventModel.countDocuments({ processed: { $ne: true } });

    const bySource = await RawEventModel.aggregate([
      { $group: { _id: '$sourceType', count: { $sum: 1 } } },
    ]);

    const latest = await RawEventModel.findOne({}, { _id: 0, externalId: 1, sourceType: 1, ingestedAt: 1 })
      .sort({ ingestedAt: -1 })
      .lean();

    return {
      ok: true,
      data: {
        total,
        processed,
        unprocessed,
        bySource: Object.fromEntries(bySource.map((b) => [b._id, b.count])),
        latest,
      },
    };
  });

  /**
   * POST /scheduler/start — Start the scheduler
   */
  app.post('/scheduler/start', async () => {
    ingestionScheduler.start();
    return { ok: true, message: 'Scheduler started', data: ingestionScheduler.getStatus() };
  });

  /**
   * POST /scheduler/stop — Stop the scheduler
   */
  app.post('/scheduler/stop', async () => {
    ingestionScheduler.stop();
    return { ok: true, message: 'Scheduler stopped', data: ingestionScheduler.getStatus() };
  });

  console.log('[Ingestion] Admin routes registered');
}
