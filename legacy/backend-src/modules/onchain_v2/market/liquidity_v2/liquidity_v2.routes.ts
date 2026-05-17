/**
 * OnChain V2 — LiquidityScore v2 Routes
 * =======================================
 * 
 * BLOCK 7: REST API for LARE v2.
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { LiquidityV2Service } from './liquidity_v2.service.js';
import { getLiquidityV2JobStatus } from './liquidity_v2.job.js';
import type { LareV2Window } from './liquidity_v2.contracts.js';

// ═══════════════════════════════════════════════════════════════
// ROUTE BUILDER
// ═══════════════════════════════════════════════════════════════

export function buildLiquidityV2Routes(service: LiquidityV2Service) {
  return async function liquidityV2Routes(fastify: FastifyInstance): Promise<void> {
    
    // Health check
    fastify.get('/health', async (request, reply) => {
      const health = await service.getHealth();
      const jobStatus = getLiquidityV2JobStatus();
      
      return {
        ...health,
        job: jobStatus,
      };
    });

    // Get latest LARE v2
    fastify.get('/latest', async (
      request: FastifyRequest<{ Querystring: { window?: string } }>,
      reply: FastifyReply
    ) => {
      const window = (request.query.window || '24h') as LareV2Window;
      
      if (window !== '24h' && window !== '7d') {
        return { ok: false, error: 'Invalid window. Use 24h or 7d.' };
      }
      
      const latest = await service.getLatest(window);
      
      if (!latest) {
        return { ok: true, data: null, message: 'No data yet. Wait for first computation cycle.' };
      }
      
      return {
        ok: true,
        data: latest,
      };
    });

    // Get series for charting
    fastify.get('/series', async (
      request: FastifyRequest<{ 
        Querystring: { window?: string; range?: string } 
      }>,
      reply: FastifyReply
    ) => {
      const window = (request.query.window || '24h') as LareV2Window;
      const range = (request.query.range || '30d') as '24h' | '7d' | '30d';
      
      if (window !== '24h' && window !== '7d') {
        return { ok: false, error: 'Invalid window. Use 24h or 7d.' };
      }
      
      const series = await service.getSeries(window, range);
      
      return {
        ok: true,
        window,
        range,
        count: series.length,
        series,
      };
    });

    // Force compute (admin)
    fastify.post('/force-compute', async (
      request: FastifyRequest<{ Body: { window?: string } }>,
      reply: FastifyReply
    ) => {
      const window = (request.body?.window as LareV2Window) || undefined;
      
      try {
        if (window) {
          if (window !== '24h' && window !== '7d') {
            return { ok: false, error: 'Invalid window. Use 24h or 7d.' };
          }
          const result = await service.computeAndStore(window);
          return { ok: true, computed: [result], ts: Date.now() };
        }
        
        // Compute all windows
        const [out24, out7] = await Promise.all([
          service.computeAndStore('24h'),
          service.computeAndStore('7d'),
        ]);
        
        return { ok: true, computed: [out24, out7], ts: Date.now() };
      } catch (error) {
        return {
          ok: false,
          error: error instanceof Error ? error.message : 'Unknown error',
        };
      }
    });

    // Gate status (quick check for trading systems)
    fastify.get('/gate', async (
      request: FastifyRequest<{ Querystring: { window?: string } }>,
      reply: FastifyReply
    ) => {
      const window = (request.query.window || '24h') as LareV2Window;
      const latest = await service.getLatest(window);
      
      if (!latest) {
        return {
          ok: true,
          gate: {
            riskCap: 0.14,
            allowAggressiveRisk: false,
            blockNewPositions: true,
            reason: 'No LARE data available',
          },
          confidence: 0,
          regime: 'NEUTRAL',
        };
      }
      
      return {
        ok: true,
        gate: latest.gate,
        confidence: latest.confidence,
        regime: latest.regime,
        score: latest.score,
      };
    });

    console.log('[OnChain V2] LiquidityScore v2 routes registered');
  };
}

console.log('[OnChain V2] LiquidityScore v2 routes module loaded');
