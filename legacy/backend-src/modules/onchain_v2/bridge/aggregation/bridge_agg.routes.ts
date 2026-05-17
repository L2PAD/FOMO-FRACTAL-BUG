/**
 * OnChain V2 — Bridge Aggregation Routes
 * ========================================
 * 
 * API endpoints for bridge aggregation data.
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { bridgeAggregationService } from './bridge_agg.service.js';
import { bridgeAggJobStatus, forceBridgeAggTick } from './bridge_agg.job.js';

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function bridgeAggRoutes(fastify: FastifyInstance): Promise<void> {
  
  // GET /aggregate/latest — Get latest aggregate
  fastify.get<{
    Querystring: { window?: string };
  }>('/latest', async (request, reply) => {
    try {
      const window = (request.query.window as '24h' | '7d') || '24h';
      
      if (window !== '24h' && window !== '7d') {
        reply.code(400);
        return { ok: false, error: 'Invalid window (use 24h or 7d)' };
      }
      
      const latest = await bridgeAggregationService.getLatest(window);
      
      if (!latest) {
        return {
          ok: true,
          window,
          data: null,
          message: 'No aggregates computed yet',
        };
      }
      
      return {
        ok: true,
        window,
        ...latest,
      };
    } catch (error) {
      console.error('[BridgeAgg] Error getting latest:', error);
      return {
        ok: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  });
  
  // GET /aggregate/series — Get series for charting
  fastify.get<{
    Querystring: { window?: string; range?: string };
  }>('/series', async (request, reply) => {
    try {
      const window = (request.query.window as '24h' | '7d') || '24h';
      const range = (request.query.range as '24h' | '7d' | '30d') || '30d';
      
      if (window !== '24h' && window !== '7d') {
        reply.code(400);
        return { ok: false, error: 'Invalid window (use 24h or 7d)' };
      }
      
      const series = await bridgeAggregationService.getSeries(window, range);
      
      return {
        ok: true,
        window,
        range,
        count: series.length,
        series,
      };
    } catch (error) {
      console.error('[BridgeAgg] Error getting series:', error);
      return {
        ok: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  });
  
  // GET /aggregate/health — Get aggregation health
  fastify.get('/health', async (_request: FastifyRequest, reply: FastifyReply) => {
    try {
      const health = await bridgeAggregationService.getHealth();
      const jobStatus = bridgeAggJobStatus();
      
      return {
        ...health,
        job: jobStatus,
      };
    } catch (error) {
      console.error('[BridgeAgg] Error getting health:', error);
      return {
        ok: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  });
  
  // POST /aggregate/force-compute — Force immediate computation
  fastify.post('/force-compute', async (_request: FastifyRequest, reply: FastifyReply) => {
    try {
      const result = await forceBridgeAggTick();
      return result;
    } catch (error) {
      console.error('[BridgeAgg] Error forcing compute:', error);
      return {
        ok: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  });
  
  console.log('[OnChain V2] Bridge Aggregation Routes registered');
}

console.log('[OnChain V2] Bridge Aggregation Routes module loaded');
