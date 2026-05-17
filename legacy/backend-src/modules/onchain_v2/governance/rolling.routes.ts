/**
 * OnChain V2 — Rolling Stats Routes
 * ===================================
 * 
 * API endpoints for 30-day rolling statistics.
 */

import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { rollingStatsService } from './rolling.service.js';
import type { RollingWindow } from './rolling.model.js';

export async function rollingRoutes(app: FastifyInstance) {
  
  /**
   * POST /api/v10/onchain-v2/governance/compute-rolling
   * Compute rolling stats for a symbol
   */
  app.post('/compute-rolling', async (req: FastifyRequest, reply: FastifyReply) => {
    try {
      const body = req.body as any;
      const symbol = body.symbol || 'ETH';
      const window = (body.window || '30d') as RollingWindow;
      const chainId = body.chainId || 1;
      
      const stats = await rollingStatsService.computeRolling({ symbol, window, chainId });
      
      return {
        ok: true,
        rolling: {
          symbol: stats.symbol,
          window: stats.window,
          chainId: stats.chainId,
          computedAt: stats.computedAt,
          sampleCount: stats.sampleCount,
          
          score: {
            avg: stats.avgScore,
            std: stats.stdScore,
            min: stats.minScore,
            max: stats.maxScore,
            median: stats.medianScore,
          },
          
          confidence: {
            avg: stats.avgConfidence,
            std: stats.stdConfidence,
            min: stats.minConfidence,
            max: stats.maxConfidence,
          },
          
          dex: {
            activityAvg: stats.dexActivityAvg,
            imbalanceAvg: stats.dexImbalanceAvg,
            swapCountAvg: stats.dexSwapCountAvg,
          },
          
          stateDistribution: stats.stateDistribution,
          scoreDistribution: stats.scoreDistribution,
          health: stats.health,
          thresholds: stats.thresholds,
        },
      };
    } catch (err) {
      console.error('[RollingRoutes] compute-rolling error:', err);
      return reply.status(500).send({
        ok: false,
        error: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  });
  
  /**
   * GET /api/v10/onchain-v2/governance/rolling
   * Get rolling stats for a symbol
   */
  app.get('/rolling', async (req: FastifyRequest, reply: FastifyReply) => {
    try {
      const query = req.query as any;
      const symbol = query.symbol || 'ETH';
      const window = (query.window || '30d') as RollingWindow;
      const chainId = query.chainId ? parseInt(query.chainId) : 1;
      
      const stats = await rollingStatsService.getRolling({ symbol, window, chainId });
      
      if (!stats) {
        return {
          ok: false,
          error: 'No rolling stats found. Run compute-rolling first.',
        };
      }
      
      return {
        ok: true,
        rolling: {
          symbol: stats.symbol,
          window: stats.window,
          chainId: stats.chainId,
          computedAt: stats.computedAt,
          sampleCount: stats.sampleCount,
          
          score: {
            avg: stats.avgScore,
            std: stats.stdScore,
            min: stats.minScore,
            max: stats.maxScore,
            median: stats.medianScore,
          },
          
          confidence: {
            avg: stats.avgConfidence,
            std: stats.stdConfidence,
            min: stats.minConfidence,
            max: stats.maxConfidence,
          },
          
          dex: {
            activityAvg: stats.dexActivityAvg,
            imbalanceAvg: stats.dexImbalanceAvg,
            swapCountAvg: stats.dexSwapCountAvg,
          },
          
          stateDistribution: stats.stateDistribution,
          scoreDistribution: stats.scoreDistribution,
          health: stats.health,
          thresholds: stats.thresholds,
        },
      };
    } catch (err) {
      console.error('[RollingRoutes] rolling error:', err);
      return reply.status(500).send({
        ok: false,
        error: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  });
  
  /**
   * GET /api/v10/onchain-v2/governance/rolling-all
   * Get all rolling stats
   */
  app.get('/rolling-all', async (req: FastifyRequest, reply: FastifyReply) => {
    try {
      const query = req.query as any;
      const window = (query.window || '30d') as RollingWindow;
      
      const allStats = await rollingStatsService.getAllRolling(window);
      
      return {
        ok: true,
        count: allStats.length,
        rolling: allStats.map(stats => ({
          symbol: stats.symbol,
          window: stats.window,
          sampleCount: stats.sampleCount,
          avgScore: stats.avgScore,
          avgConfidence: stats.avgConfidence,
          health: stats.health,
          computedAt: stats.computedAt,
        })),
      };
    } catch (err) {
      console.error('[RollingRoutes] rolling-all error:', err);
      return reply.status(500).send({
        ok: false,
        error: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  });
  
  /**
   * GET /api/v10/onchain-v2/governance/health
   * Get overall module health based on rolling stats
   */
  app.get('/health', async (req: FastifyRequest, reply: FastifyReply) => {
    try {
      const allStats = await rollingStatsService.getAllRolling('30d');
      
      const totalSymbols = allStats.length;
      const healthySymbols = allStats.filter(s => 
        s.health.sufficientSamples && s.health.stableVariance
      ).length;
      
      const avgSampleCount = totalSymbols > 0
        ? Math.round(allStats.reduce((sum, s) => sum + s.sampleCount, 0) / totalSymbols)
        : 0;
      
      const avgConfidence = totalSymbols > 0
        ? Math.round(allStats.reduce((sum, s) => sum + s.avgConfidence, 0) / totalSymbols * 100) / 100
        : 0;
      
      return {
        ok: true,
        health: {
          status: healthySymbols === totalSymbols && totalSymbols > 0 ? 'HEALTHY' : 
                  healthySymbols > 0 ? 'PARTIAL' : 'DEGRADED',
          totalSymbols,
          healthySymbols,
          avgSampleCount,
          avgConfidence,
          checkedAt: Date.now(),
        },
      };
    } catch (err) {
      console.error('[RollingRoutes] health error:', err);
      return reply.status(500).send({
        ok: false,
        error: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  });
  
  console.log('[OnChain V2] Rolling routes registered');
}
