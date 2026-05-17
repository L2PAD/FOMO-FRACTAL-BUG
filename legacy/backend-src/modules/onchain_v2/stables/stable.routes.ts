/**
 * OnChain V2 — Stablecoin Routes
 * ================================
 * 
 * REST API endpoints for stablecoin mint/burn tracking.
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { stableMintBurnIndexer } from './stable_indexer.js';
import { stableAggregationService } from './stable_aggregation.service.js';
import { STABLE_MINTBURN_ENABLED } from './stable_registry.js';
import type { StableAggWindow } from './stable_aggregate.model.js';

// ═══════════════════════════════════════════════════════════════
// HANDLERS: INDEXER
// ═══════════════════════════════════════════════════════════════

async function getIndexerStatus(
  request: FastifyRequest,
  reply: FastifyReply
) {
  const status = await stableMintBurnIndexer.getStatus();
  return {
    ok: true,
    ...status,
    ts: Date.now(),
  };
}

async function forceTick(
  request: FastifyRequest<{
    Querystring: { chainId?: string };
  }>,
  reply: FastifyReply
) {
  const chainIdParam = request.query.chainId;
  
  if (chainIdParam) {
    const chainId = parseInt(chainIdParam);
    const result = await stableMintBurnIndexer.indexChain(chainId);
    return { ok: result.ok, result, ts: Date.now() };
  }
  
  const result = await stableMintBurnIndexer.indexAll();
  return { ok: result.ok, results: result.results, ts: Date.now() };
}

// ═══════════════════════════════════════════════════════════════
// HANDLERS: AGGREGATION
// ═══════════════════════════════════════════════════════════════

async function getLatestAggregate(
  request: FastifyRequest<{
    Querystring: { window?: StableAggWindow };
  }>,
  reply: FastifyReply
) {
  const window = request.query.window || '24h';
  const agg = await stableAggregationService.getLatest(window);
  
  if (!agg) {
    return { ok: true, aggregate: null, message: 'No data yet' };
  }
  
  return {
    ok: true,
    aggregate: {
      window: agg.window,
      bucketTs: agg.bucketTs,
      computedAt: agg.computedAt,
      chainsCovered: agg.chainsCovered,
      metrics: agg.metrics,
      byToken: agg.byToken,
      score: agg.score,
      drivers: agg.drivers,
      flags: agg.flags,
    },
  };
}

async function getSeries(
  request: FastifyRequest<{
    Querystring: { window?: StableAggWindow; range?: '24h' | '7d' | '30d' };
  }>,
  reply: FastifyReply
) {
  const window = request.query.window || '24h';
  const range = request.query.range || '30d';
  
  const series = await stableAggregationService.getSeries(window, range);
  return {
    ok: true,
    window,
    range,
    count: series.length,
    series,
  };
}

async function forceCompute(
  request: FastifyRequest<{
    Querystring: { window?: StableAggWindow };
  }>,
  reply: FastifyReply
) {
  const window = request.query.window;
  const nowTs = Date.now();
  
  if (window) {
    const result = await stableAggregationService.computeAndUpsert(window, nowTs);
    return { ok: true, computed: [result], ts: nowTs };
  }
  
  // Compute all windows
  const results = await Promise.all([
    stableAggregationService.computeAndUpsert('24h', nowTs),
    stableAggregationService.computeAndUpsert('7d', nowTs),
    stableAggregationService.computeAndUpsert('30d', nowTs),
  ]);
  
  return { ok: true, computed: results, ts: nowTs };
}

// ═══════════════════════════════════════════════════════════════
// HANDLERS: HEALTH
// ═══════════════════════════════════════════════════════════════

async function getHealth(
  request: FastifyRequest,
  reply: FastifyReply
) {
  const [indexerStatus, aggHealth] = await Promise.all([
    stableMintBurnIndexer.getStatus(),
    stableAggregationService.getHealth(),
  ]);
  
  return {
    ok: STABLE_MINTBURN_ENABLED,
    enabled: STABLE_MINTBURN_ENABLED,
    indexer: indexerStatus,
    aggregation: aggHealth,
    ts: Date.now(),
  };
}

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function stableRoutes(fastify: FastifyInstance): Promise<void> {
  // Health
  fastify.get('/health', getHealth);
  
  // Indexer
  fastify.get('/indexer/status', getIndexerStatus);
  fastify.post('/indexer/force-tick', forceTick);
  
  // Aggregation
  fastify.get('/aggregate/latest', getLatestAggregate);
  fastify.get('/aggregate/series', getSeries);
  fastify.post('/aggregate/force-compute', forceCompute);
  
  console.log('[OnChain V2] Stablecoin routes registered');
}

console.log('[OnChain V2] Stablecoin routes module loaded');
