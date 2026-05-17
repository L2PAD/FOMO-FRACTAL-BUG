/**
 * System Routes (Option B - B0/B2/B3/B5)
 * 
 * Global system status and observability endpoints.
 */
import type { FastifyInstance } from 'fastify';
import { getSystemHealth, BootstrapMetrics } from '../core/system/health.service.js';
import { getIndexingStatus } from '../core/bootstrap/bootstrap.stats.js';
import { BootstrapTaskModel, BootstrapFailureReason } from '../core/bootstrap/bootstrap_tasks.model.js';
import { getLockInfo } from '../core/system/lock.model.js';
import { getHeartbeat } from '../core/system/heartbeat.model.js';
import { getSystemEvents } from '../core/system/system_events.model.js';

export async function systemRoutes(app: FastifyInstance): Promise<void> {
  /**
   * GET /api/system/profile
   * Returns current system profile and active flags.
   */
  app.get('/profile', async (_request, reply) => {
    const profile = process.env.SYSTEM_PROFILE || 'dev';
    return reply.send({
      ok: true,
      systemProfile: profile,
      flags: {
        onchainV2: process.env.ONCHAIN_V2_ENABLED === 'true',
        onchain: process.env.ONCHAIN_ENABLED !== 'false',
        sentimentIntake: process.env.SENTIMENT_INTAKE_ENABLED === 'true',
        sentimentAgg: process.env.SENTIMENT_AGG_ENABLED === 'true',
        sentimentDataset: process.env.SENTIMENT_DATASET_ENABLED === 'true',
        telegramIntel: process.env.TELEGRAM_INTEL_ENABLED === 'true',
        exchangeObs: process.env.EXCHANGE_OBS_ENABLED !== 'false',
        exchangeML: process.env.EXCHANGE_ML_ENABLED === 'true',
        multichain: process.env.MULTICHAIN_ENABLED === 'true',
        alpaDynamic: process.env.ALPHA_DYNAMIC_ENABLED === 'true',
      },
      nodeHeapMB: Math.round(process.memoryUsage().heapUsed / 1024 / 1024),
      rssMB: Math.round(process.memoryUsage().rss / 1024 / 1024),
      uptime: Math.round(process.uptime()),
    });
  });

  /**
   * GET /api/system/health (B0)
   * 
   * Full system health report with service checks and metrics.
   */
  app.get('/health', async (_request, reply) => {
    try {
      const health = await getSystemHealth();
      return reply.send(health);
    } catch (err) {
      app.log.error('[System] Failed to get health:', err);
      return reply.status(500).send({
        status: 'unhealthy',
        ts: new Date().toISOString(),
        error: 'Health check failed',
      });
    }
  });

  /**
   * GET /api/system/indexing-status (P2.3.B)
   * 
   * Simple indexing status for header display.
   */
  app.get('/indexing-status', async (_request, reply) => {
    try {
      const status = await getIndexingStatus();
      return reply.send({ ok: true, data: status });
    } catch (err) {
      app.log.error('[System] Failed to get indexing status:', err);
      return reply.status(500).send({
        ok: false,
        error: 'INTERNAL_ERROR',
        message: 'Failed to get indexing status',
      });
    }
  });

  /**
   * GET /api/system/bootstrap-metrics (B3)
   * 
   * Detailed bootstrap task metrics and failure analysis.
   */
  app.get('/bootstrap-metrics', async (_request, reply) => {
    try {
      // Get basic metrics
      const indexingStatus = await getIndexingStatus();
      
      // Get failure reason breakdown (last 24h)
      const failureBreakdown = await BootstrapTaskModel.aggregate([
        {
          $match: {
            status: 'failed',
            updatedAt: { $gte: new Date(Date.now() - 24 * 60 * 60 * 1000) },
          },
        },
        {
          $group: {
            _id: '$failureReason',
            count: { $sum: 1 },
          },
        },
        { $sort: { count: -1 } },
        { $limit: 10 },
      ]);
      
      // Get duration stats
      const durationStats = await BootstrapTaskModel.aggregate([
        {
          $match: {
            status: 'done',
            startedAt: { $exists: true },
            finishedAt: { $gte: new Date(Date.now() - 24 * 60 * 60 * 1000) },
          },
        },
        {
          $project: {
            durationMs: { $subtract: ['$finishedAt', '$startedAt'] },
          },
        },
        {
          $group: {
            _id: null,
            avg: { $avg: '$durationMs' },
            max: { $max: '$durationMs' },
            min: { $min: '$durationMs' },
            count: { $sum: 1 },
          },
        },
      ]);
      
      // Worker status
      const workerLock = await getLockInfo('bootstrap_worker');
      const workerHeartbeat = await getHeartbeat('bootstrap_worker');
      
      return reply.send({
        ok: true,
        data: {
          ...indexingStatus,
          failureBreakdown: failureBreakdown.map(f => ({
            reason: f._id || 'unknown',
            count: f.count,
          })),
          duration: durationStats[0] ? {
            avgMs: Math.round(durationStats[0].avg || 0),
            maxMs: durationStats[0].max || 0,
            minMs: durationStats[0].min || 0,
            sampleCount: durationStats[0].count || 0,
          } : null,
          worker: {
            running: workerLock?.locked && !workerLock?.stale,
            lockedBy: workerLock?.lockedBy,
            lastHeartbeat: workerHeartbeat?.ts,
          },
        },
      });
    } catch (err) {
      app.log.error('[System] Failed to get bootstrap metrics:', err);
      return reply.status(500).send({
        ok: false,
        error: 'INTERNAL_ERROR',
      });
    }
  });

  /**
   * GET /api/system/events (B5)
   * 
   * System event history for debugging and observability.
   */
  app.get('/events', async (request, reply) => {
    try {
      const { since, limit } = request.query as { since?: string; limit?: string };
      
      const sinceDate = since ? new Date(since) : undefined;
      const limitNum = limit ? parseInt(limit, 10) : 50;
      
      const events = await getSystemEvents(sinceDate, Math.min(limitNum, 200));
      
      return reply.send({
        ok: true,
        data: events,
        count: events.length,
      });
    } catch (err) {
      app.log.error('[System] Failed to get events:', err);
      return reply.status(500).send({
        ok: false,
        error: 'INTERNAL_ERROR',
      });
    }
  });

  app.log.info('[System] System routes registered');

  // Chain Registry routes (G0.1)
  const { chainRoutes } = await import('../modules/chains/chain.controller.js');
  await app.register(chainRoutes);
}
