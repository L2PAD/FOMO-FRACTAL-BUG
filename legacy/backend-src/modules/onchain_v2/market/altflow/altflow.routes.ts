/**
 * AltFlow Routes v2
 * ==================
 * 
 * PHASE 3.5: Real AltFlow API with aggregated token data
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { altflowAggregateService, AltflowWindow } from './altflow.aggregate.service';
import { flowNormalizerService } from '../flow/flowNormalizer.service';
import { tokenMetaService } from '../flow/tokenMeta.service';
import { getAltFlowJobStatus, startAltFlowJob } from './altflow.job';

interface FlowQuery {
  window?: string;
  chainId?: string;
  refresh?: string;
  entityId?: string; // P0.7: Entity filter for overlay
}

// Job handle
let jobHandle: ReturnType<typeof startAltFlowJob> | null = null;

/**
 * GET /altflow - Get alt token flow rankings
 * P0.7: Added entityId filter for entity overlay
 */
async function getAltFlowHandler(
  request: FastifyRequest<{ Querystring: FlowQuery }>,
  reply: FastifyReply
) {
  const window = (request.query.window === '7d' ? '7d' : '24h') as AltflowWindow;
  const chainId = Number(request.query.chainId) || 1;
  const forceRefresh = request.query.refresh === 'true';
  const entityId = request.query.entityId || undefined;

  try {
    // Optionally refresh flows first
    if (forceRefresh) {
      await flowNormalizerService.processDexSwaps(chainId, 2 * 60 * 60 * 1000);
    }
    
    // Get aggregated data with optional entity filter
    const result = await altflowAggregateService.compute(window, chainId, entityId);
    const formatted = altflowAggregateService.formatForApi(result);
    
    // P0.7: Include entity filter info in response
    return {
      ...formatted,
      entityFilter: entityId || null,
    };
  } catch (error) {
    console.error('[AltFlow Routes] Error:', error);
    return {
      ok: false,
      error: 'Failed to compute alt flow',
      window,
      chainId,
      entityFilter: entityId || null,
    };
  }
}

/**
 * POST /altflow/refresh - Force refresh
 */
async function refreshAltFlowHandler(
  request: FastifyRequest<{ Querystring: FlowQuery }>,
  reply: FastifyReply
) {
  const window = (request.query.window === '7d' ? '7d' : '24h') as AltflowWindow;
  const chainId = Number(request.query.chainId) || 1;

  try {
    // Process new flows
    const flowResult = await flowNormalizerService.processDexSwaps(chainId, 4 * 60 * 60 * 1000);
    
    // Compute and persist
    const result = await altflowAggregateService.computeAndPersist(window, chainId);
    const formatted = altflowAggregateService.formatForApi(result);
    
    return {
      ok: true,
      message: 'Alt flow refreshed',
      flowsProcessed: flowResult.flows,
      ...formatted,
    };
  } catch (error) {
    console.error('[AltFlow Routes] Refresh error:', error);
    return {
      ok: false,
      error: 'Failed to refresh alt flow',
    };
  }
}

/**
 * GET /altflow/job/status - Get job status
 */
async function getJobStatusHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  const status = getAltFlowJobStatus();
  return {
    ok: true,
    job: status,
  };
}

/**
 * POST /altflow/job/force-tick - Force immediate job tick
 */
async function forceJobTickHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  if (!jobHandle || !jobHandle.forceRun) {
    return {
      ok: false,
      error: 'Job not initialized',
    };
  }
  
  try {
    const status = await jobHandle.forceRun();
    return {
      ok: true,
      message: 'Force tick completed',
      job: status,
    };
  } catch (error) {
    console.error('[AltFlow Routes] Force tick error:', error);
    return {
      ok: false,
      error: 'Force tick failed',
    };
  }
}

/**
 * GET /altflow/flow-stats - Get flow statistics
 */
async function getFlowStatsHandler(
  request: FastifyRequest<{ Querystring: { chainId?: string; windowMs?: string } }>,
  reply: FastifyReply
) {
  const chainId = Number(request.query.chainId) || 1;
  const windowMs = Number(request.query.windowMs) || 24 * 60 * 60 * 1000;
  
  try {
    const stats = await flowNormalizerService.getStats(chainId, windowMs);
    const tokenStats = tokenMetaService.getStats();
    
    return {
      ok: true,
      flow: stats,
      tokens: tokenStats,
    };
  } catch (error) {
    console.error('[AltFlow Routes] Stats error:', error);
    return {
      ok: false,
      error: 'Failed to get stats',
    };
  }
}

/**
 * Register alt flow routes
 */
export async function altflowRoutes(fastify: FastifyInstance): Promise<void> {
  // Data endpoints
  fastify.get('/', getAltFlowHandler);
  fastify.post('/refresh', refreshAltFlowHandler);
  fastify.get('/flow-stats', getFlowStatsHandler);
  
  // Job management
  fastify.get('/job/status', getJobStatusHandler);
  fastify.post('/job/force-tick', forceJobTickHandler);

  // Start the job
  jobHandle = startAltFlowJob();

  console.log('[AltFlow Routes] v2 registered + Job initialized');
}
