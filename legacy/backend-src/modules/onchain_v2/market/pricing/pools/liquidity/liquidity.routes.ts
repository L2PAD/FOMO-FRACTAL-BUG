/**
 * OnChain V2 — Pool Liquidity Routes
 * ====================================
 * 
 * STEP 4.1: TVL/Liquidity Scoring Integration
 * API endpoints for liquidity management.
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { poolLiquidityService } from './poolLiquidity.service';
import { 
  startPoolLiquidityJob, 
  stopPoolLiquidityJob, 
  forceRunPoolLiquidityJob,
  getPoolLiquidityJobStatus,
} from './poolLiquidity.job';

// ═══════════════════════════════════════════════════════════════
// HANDLERS
// ═══════════════════════════════════════════════════════════════

/**
 * GET /liquidity/health - Get liquidity service health
 */
async function healthHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  const health = poolLiquidityService.getHealth();
  const jobStatus = getPoolLiquidityJobStatus();
  
  return {
    ok: true,
    ...health,
    job: jobStatus,
  };
}

/**
 * GET /liquidity/stats - Get liquidity stats for a chain
 */
async function statsHandler(
  request: FastifyRequest<{ Querystring: { chainId?: string } }>,
  reply: FastifyReply
) {
  const chainId = Number(request.query.chainId) || 1;
  
  try {
    const stats = await poolLiquidityService.getStats(chainId);
    const jobStatus = getPoolLiquidityJobStatus();
    
    return {
      ok: true,
      chainId,
      stats,
      job: jobStatus,
    };
  } catch (e: any) {
    return { ok: false, error: e?.message || 'Unknown error' };
  }
}

/**
 * POST /liquidity/refresh - Force refresh liquidity for a chain
 */
async function refreshHandler(
  request: FastifyRequest<{ Body: { chainId?: number } }>,
  reply: FastifyReply
) {
  const chainId = Number(request.body?.chainId) || 1;
  
  try {
    const result = await poolLiquidityService.refreshChain(chainId);
    return { ok: true, ...result };
  } catch (e: any) {
    return { ok: false, error: e?.message || 'Unknown error' };
  }
}

/**
 * POST /liquidity/job/start - Start liquidity job
 */
async function jobStartHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  const result = startPoolLiquidityJob();
  return { ok: true, ...result };
}

/**
 * POST /liquidity/job/stop - Stop liquidity job
 */
async function jobStopHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  stopPoolLiquidityJob();
  return { ok: true, message: 'Job stopped' };
}

/**
 * POST /liquidity/job/force-run - Force run liquidity job
 */
async function jobForceRunHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  try {
    const result = await forceRunPoolLiquidityJob();
    return { ok: true, result };
  } catch (e: any) {
    return { ok: false, error: e?.message || 'Unknown error' };
  }
}

/**
 * GET /liquidity/job/status - Get job status
 */
async function jobStatusHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  const status = getPoolLiquidityJobStatus();
  return { ok: true, ...status };
}

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function liquidityRoutes(fastify: FastifyInstance): Promise<void> {
  // Health & stats
  fastify.get('/health', healthHandler);
  fastify.get('/stats', statsHandler);
  
  // Manual refresh
  fastify.post('/refresh', refreshHandler);
  
  // Job control
  fastify.get('/job/status', jobStatusHandler);
  fastify.post('/job/start', jobStartHandler);
  fastify.post('/job/stop', jobStopHandler);
  fastify.post('/job/force-run', jobForceRunHandler);
  
  console.log('[Liquidity Routes] Registered');
}

export default liquidityRoutes;
