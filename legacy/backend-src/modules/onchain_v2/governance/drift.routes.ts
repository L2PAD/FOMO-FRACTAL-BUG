/**
 * OnChain V2 — Drift Routes
 * ===========================
 * 
 * API endpoints for PSI drift detection and baseline management.
 */

import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { driftService } from './drift.service.js';

export async function driftRoutes(app: FastifyInstance) {
  
  /**
   * POST /api/v10/onchain-v2/governance/create-baseline
   * Create a new baseline from current rolling stats
   */
  app.post('/create-baseline', async (req: FastifyRequest, reply: FastifyReply) => {
    try {
      const body = req.body as any;
      const symbol = body.symbol || 'ETH';
      const metric = body.metric || 'score';
      const window = body.window || '30d';
      
      const baseline = await driftService.createBaseline({ symbol, metric, window });
      
      return {
        ok: true,
        baseline: {
          symbol: baseline.symbol,
          metric: baseline.metric,
          version: baseline.version,
          createdAt: baseline.createdAt,
          sampleCount: baseline.sampleCount,
          sourceWindow: baseline.sourceWindow,
          active: baseline.active,
          stats: baseline.stats,
          distribution: {
            bucketCount: baseline.distribution.buckets.length,
            bucketSize: baseline.distribution.bucketSize,
            buckets: baseline.distribution.buckets,
          },
        },
      };
    } catch (err) {
      console.error('[DriftRoutes] create-baseline error:', err);
      return reply.status(400).send({
        ok: false,
        error: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  });
  
  /**
   * GET /api/v10/onchain-v2/governance/baseline
   * Get active baseline for a symbol
   */
  app.get('/baseline', async (req: FastifyRequest, reply: FastifyReply) => {
    try {
      const query = req.query as any;
      const symbol = query.symbol || 'ETH';
      const metric = query.metric || 'score';
      
      const baseline = await driftService.getBaseline({ symbol, metric });
      
      if (!baseline) {
        return {
          ok: false,
          error: 'No baseline found. Create one first with POST /create-baseline',
        };
      }
      
      return {
        ok: true,
        baseline: {
          symbol: baseline.symbol,
          metric: baseline.metric,
          version: baseline.version,
          createdAt: baseline.createdAt,
          sampleCount: baseline.sampleCount,
          sourceWindow: baseline.sourceWindow,
          active: baseline.active,
          stats: baseline.stats,
          distribution: {
            bucketCount: baseline.distribution.buckets.length,
            bucketSize: baseline.distribution.bucketSize,
            buckets: baseline.distribution.buckets,
          },
        },
      };
    } catch (err) {
      console.error('[DriftRoutes] baseline error:', err);
      return reply.status(500).send({
        ok: false,
        error: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  });
  
  /**
   * GET /api/v10/onchain-v2/governance/drift
   * Calculate PSI drift between current and baseline
   */
  app.get('/drift', async (req: FastifyRequest, reply: FastifyReply) => {
    try {
      const query = req.query as any;
      const symbol = query.symbol || 'ETH';
      const metric = query.metric || 'score';
      const window = query.window || '30d';
      
      const drift = await driftService.calculateDrift({ symbol, metric, window });
      
      return {
        ok: true,
        drift: {
          symbol,
          metric,
          window,
          psi: drift.psi,
          level: drift.level,
          hasBaseline: drift.hasBaseline,
          sampleCount: drift.sampleCount,
          thresholds: drift.thresholds,
          bucketComparison: drift.bucketComparison,
          checkedAt: Date.now(),
        },
      };
    } catch (err) {
      console.error('[DriftRoutes] drift error:', err);
      return reply.status(500).send({
        ok: false,
        error: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  });
  
  /**
   * GET /api/v10/onchain-v2/governance/baselines-all
   * Get all active baselines
   */
  app.get('/baselines-all', async (req: FastifyRequest, reply: FastifyReply) => {
    try {
      const baselines = await driftService.getAllBaselines();
      
      return {
        ok: true,
        count: baselines.length,
        baselines: baselines.map(b => ({
          symbol: b.symbol,
          metric: b.metric,
          version: b.version,
          createdAt: b.createdAt,
          sampleCount: b.sampleCount,
          avgScore: b.stats.avgScore,
        })),
      };
    } catch (err) {
      console.error('[DriftRoutes] baselines-all error:', err);
      return reply.status(500).send({
        ok: false,
        error: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  });
  
  console.log('[OnChain V2] Drift routes registered');
}
