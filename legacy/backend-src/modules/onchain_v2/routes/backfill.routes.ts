/**
 * OnChain V2 — Backfill Routes
 * =============================
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { backfillService } from '../core/backfill/index.js';

async function runBackfillHandler(
  request: FastifyRequest<{
    Body: {
      symbol: string;
      windowDays?: number;
      granularityHours?: number;
    };
  }>,
  reply: FastifyReply
) {
  try {
    const { symbol, windowDays = 30, granularityHours = 4 } = request.body;
    
    if (!symbol) {
      return { ok: false, error: 'Symbol required' };
    }
    
    const result = await backfillService.runBackfill({
      symbol,
      windowDays,
      granularityHours,
    });
    
    return result;
  } catch (error) {
    console.error('[OnChain V2] Backfill error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

async function getHistoryHandler(
  request: FastifyRequest<{
    Params: { symbol: string };
    Querystring: { window?: string; limit?: string };
  }>,
  reply: FastifyReply
) {
  try {
    const { symbol } = request.params;
    const windowDays = parseInt(request.query.window || '30');
    const limit = parseInt(request.query.limit || '720');
    
    const observations = await backfillService.getHistory(symbol, windowDays, limit);
    
    return {
      ok: true,
      symbol,
      window: `${windowDays}d`,
      count: observations.length,
      observations,
    };
  } catch (error) {
    console.error('[OnChain V2] History error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

async function getStatsHandler(
  request: FastifyRequest<{
    Params: { symbol: string };
  }>,
  reply: FastifyReply
) {
  try {
    const { symbol } = request.params;
    
    const count30d = await backfillService.getObservationCount(symbol, 30);
    const count7d = await backfillService.getObservationCount(symbol, 7);
    const count24h = await backfillService.getObservationCount(symbol, 1);
    
    return {
      ok: true,
      symbol,
      counts: {
        '30d': count30d,
        '7d': count7d,
        '24h': count24h,
      },
    };
  } catch (error) {
    console.error('[OnChain V2] Stats error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

export async function onchainV2BackfillRoutes(fastify: FastifyInstance): Promise<void> {
  fastify.post('/admin/backfill', runBackfillHandler);
  fastify.get('/admin/history/:symbol', getHistoryHandler);
  fastify.get('/admin/stats/:symbol', getStatsHandler);
  
  console.log('[OnChain V2] Backfill routes registered');
}

console.log('[OnChain V2] Backfill Routes module loaded');
