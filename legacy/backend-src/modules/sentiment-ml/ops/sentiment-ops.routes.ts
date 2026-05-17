/**
 * Sentiment Ops Routes
 * =====================
 * 
 * BLOCK 1 HARDENING: Operations & observability endpoints
 * 
 * Endpoints:
 * - GET /status — Full system status (workers, locks, lags, counts)
 * - POST /pause — Pause/unpause workers
 * - POST /trigger — Manual trigger workers
 * - GET /errors — Recent errors log
 * - GET /locks — Lock status
 */

import fp from 'fastify-plugin';
import type { FastifyInstance } from 'fastify';
import { SystemLocksService, getSystemLocksService } from '../../system/locks/system-locks.service.js';

// Lock keys for all sentiment workers
export const SENTIMENT_LOCKS = {
  INTAKE: 'sent:intake',
  AGGREGATE: 'sent:aggregate',
  DATASET_FINALIZE: 'sent:dataset_finalize',
  SHADOW_FINALIZE: 'sent:shadow_finalize',
} as const;

// Worker status tracker (in-memory)
interface WorkerStatus {
  enabled: boolean;
  paused: boolean;
  lastRun?: Date;
  lastError?: string;
  runCount: number;
  errorCount: number;
}

const workerStatuses: Record<string, WorkerStatus> = {
  intake: { enabled: true, paused: false, runCount: 0, errorCount: 0 },
  aggregate: { enabled: true, paused: false, runCount: 0, errorCount: 0 },
  dataset_finalize: { enabled: true, paused: false, runCount: 0, errorCount: 0 },
  shadow_finalize: { enabled: true, paused: false, runCount: 0, errorCount: 0 },
};

// Export for other modules to update
export function updateWorkerStatus(worker: string, update: Partial<WorkerStatus>) {
  if (workerStatuses[worker]) {
    Object.assign(workerStatuses[worker], update);
  }
}

export function isWorkerPaused(worker: string): boolean {
  return workerStatuses[worker]?.paused ?? false;
}

async function sentimentOpsRoutes(app: FastifyInstance): Promise<void> {
  const locks = getSystemLocksService();

  /**
   * GET /status — Full system status
   */
  app.get('/status', async () => {
    // Get DB stats
    const mongoose = (await import('mongoose')).default;
    const db = mongoose.connection.db;
    
    let dbStats = {
      events24h: 0,
      aggregates24h: 0,
      samples24h: 0,
      shadowPending: 0,
    };

    if (db) {
      const now = new Date();
      const h24 = new Date(now.getTime() - 24 * 60 * 60 * 1000);

      try {
        const [events, aggregates, samples, shadowPending] = await Promise.all([
          db.collection('sentiment_events').countDocuments({ createdAt: { $gte: h24 } }),
          db.collection('sentiment_aggregates').countDocuments({ createdAt: { $gte: h24 } }),
          db.collection('sentiment_dir_samples').countDocuments({ createdAt: { $gte: h24 } }),
          db.collection('sentiment_shadow_decisions').countDocuments({ evaluated: false }),
        ]);

        dbStats = { events24h: events, aggregates24h: aggregates, samples24h: samples, shadowPending };
      } catch {
        // Ignore errors for collections that don't exist yet
      }
    }

    // Get lock states
    const lockStates: Record<string, boolean> = {};
    for (const [name, key] of Object.entries(SENTIMENT_LOCKS)) {
      try {
        const handle = await locks.acquire(key, 1000);
        if (handle) {
          await locks.release(handle);
          lockStates[name] = false; // Not locked
        } else {
          lockStates[name] = true; // Locked by another process
        }
      } catch {
        lockStates[name] = true;
      }
    }

    // Get env flags
    const flags = {
      SENTIMENT_ENABLED: process.env.SENTIMENT_ENABLED === 'true',
      SENTIMENT_WORKERS_ENABLED: process.env.SENTIMENT_WORKERS_ENABLED === 'true',
      SENTIMENT_DATASET_ENABLED: process.env.SENTIMENT_DATASET_ENABLED === 'true',
      SENTIMENT_SHADOW_ENABLED: process.env.SENTIMENT_SHADOW_ENABLED !== 'false',
    };

    return {
      ok: true,
      timestamp: new Date().toISOString(),
      flags,
      workers: workerStatuses,
      locks: lockStates,
      counts: dbStats,
      health: calculateHealth(workerStatuses, flags),
    };
  });

  /**
   * POST /pause — Pause/unpause a worker
   */
  app.post('/pause', async (req: any) => {
    const { worker, paused } = req.body || {};
    
    if (!worker || !workerStatuses[worker]) {
      return { ok: false, error: 'Invalid worker name' };
    }

    workerStatuses[worker].paused = Boolean(paused);
    
    return {
      ok: true,
      worker,
      paused: workerStatuses[worker].paused,
    };
  });

  /**
   * POST /trigger — Manual trigger worker
   */
  app.post('/trigger', async (req: any) => {
    const { worker } = req.body || {};
    
    if (!worker || !workerStatuses[worker]) {
      return { ok: false, error: 'Invalid worker name' };
    }

    // Import and trigger the appropriate worker
    try {
      switch (worker) {
        case 'dataset_finalize': {
          const { getSentimentDatasetJob } = await import('../dataset/sentiment-dataset-finalize.job.js');
          const job = getSentimentDatasetJob();
          if (job) {
            const result = await job.triggerManual('live');
            return { ok: true, worker, result };
          }
          return { ok: false, error: 'Job not initialized' };
        }
        
        case 'shadow_finalize': {
          const { getSentimentShadowAnalyticsService } = await import('../shadow/sentiment.shadow.analytics.service.js');
          const service = getSentimentShadowAnalyticsService();
          const result = await service.finalizeAllPending();
          return { ok: true, worker, result };
        }

        case 'aggregate': {
          const { sentimentAggregationService } = await import('../services/sentiment-aggregation.service.js');
          const { SENTIMENT_TOP20 } = await import('../config/top20-symbols.js');
          let processed = 0;
          for (const symbol of SENTIMENT_TOP20) {
            try {
              await sentimentAggregationService.aggregateSymbol(symbol, '24H');
              processed++;
            } catch { /* ignore */ }
          }
          return { ok: true, worker, processed };
        }

        default:
          return { ok: false, error: 'Worker trigger not implemented' };
      }
    } catch (err: any) {
      return { ok: false, error: err.message };
    }
  });

  /**
   * GET /errors — Recent errors
   */
  app.get('/errors', async () => {
    const errors: Array<{ worker: string; error: string; at: Date }> = [];
    
    for (const [name, status] of Object.entries(workerStatuses)) {
      if (status.lastError) {
        errors.push({
          worker: name,
          error: status.lastError,
          at: status.lastRun || new Date(),
        });
      }
    }

    return {
      ok: true,
      count: errors.length,
      errors,
    };
  });

  /**
   * GET /locks — Lock status
   */
  app.get('/locks', async () => {
    const lockStates: Record<string, { key: string; locked: boolean }> = {};
    
    for (const [name, key] of Object.entries(SENTIMENT_LOCKS)) {
      try {
        const handle = await locks.acquire(key, 500);
        if (handle) {
          await locks.release(handle);
          lockStates[name] = { key, locked: false };
        } else {
          lockStates[name] = { key, locked: true };
        }
      } catch {
        lockStates[name] = { key, locked: true };
      }
    }

    return {
      ok: true,
      locks: lockStates,
    };
  });

  console.log('[Sentiment-ML] Ops routes registered (BLOCK 1 Hardening)');
}

function calculateHealth(workers: Record<string, WorkerStatus>, flags: Record<string, boolean>): string {
  if (!flags.SENTIMENT_ENABLED) return 'DISABLED';
  
  const errorRate = Object.values(workers).reduce((sum, w) => {
    if (w.runCount === 0) return sum;
    return sum + (w.errorCount / w.runCount);
  }, 0) / Object.keys(workers).length;

  if (errorRate > 0.5) return 'CRITICAL';
  if (errorRate > 0.2) return 'DEGRADED';
  return 'HEALTHY';
}

export default fp(sentimentOpsRoutes, {
  name: 'sentiment-ops-routes',
  fastify: '4.x',
});

export { sentimentOpsRoutes };
