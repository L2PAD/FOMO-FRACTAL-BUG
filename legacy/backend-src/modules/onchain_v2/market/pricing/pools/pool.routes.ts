/**
 * OnChain V2 — Pool Routes
 * ==========================
 * 
 * STEP 2: API endpoints for pool scoring and discovery
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { poolScoringService } from './poolScoring.service';
import { poolDiscoveryService } from './poolDiscovery.service';
import { bestPoolResolver } from './bestPool.resolver';
import { 
  getPoolDiscoveryJobStatus, 
  forceRunPoolDiscoveryJob,
  startPoolDiscoveryJob,
  stopPoolDiscoveryJob,
} from './poolDiscovery.job';
import { DexPoolModel } from '../../../ingestion/dex/models';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

interface ChainQuery {
  chainId?: string;
}

interface PoolsQuery {
  chainId?: string;
  status?: string;
  limit?: string;
}

interface DiscoverBody {
  chainId?: number;
  window?: '24h' | '7d';
}

interface BestPoolQuery {
  chainId?: string;
  token?: string;
}

// ═══════════════════════════════════════════════════════════════
// HANDLERS
// ═══════════════════════════════════════════════════════════════

/**
 * GET /pools/stats - Get pool scoring stats
 */
async function getStatsHandler(
  request: FastifyRequest<{ Querystring: ChainQuery }>,
  reply: FastifyReply
) {
  const chainId = Number(request.query.chainId) || 1;
  
  try {
    const [scoringStats, discoveryStats] = await Promise.all([
      poolScoringService.getStats(chainId),
      poolDiscoveryService.getStats(chainId),
    ]);
    
    return {
      ok: true,
      chainId,
      scoring: scoringStats,
      discovery: discoveryStats,
    };
  } catch (e: any) {
    return { ok: false, error: e?.message || 'Unknown error' };
  }
}

/**
 * GET /pools/list - Get pools with filters
 */
async function getPoolsHandler(
  request: FastifyRequest<{ Querystring: PoolsQuery }>,
  reply: FastifyReply
) {
  const chainId = Number(request.query.chainId) || 1;
  const status = request.query.status;
  const limit = Math.min(Number(request.query.limit) || 100, 500);
  
  try {
    const filter: any = { chainId };
    if (status) filter.status = status;
    
    const pools = await DexPoolModel.find(filter)
      .sort({ score: -1, confidence: -1 })
      .limit(limit)
      .lean();
    
    return {
      ok: true,
      chainId,
      count: pools.length,
      pools: pools.map(p => ({
        address: p.address,
        token0: p.token0,
        token1: p.token1,
        fee: p.fee,
        status: (p as any).status || 'CANDIDATE',
        score: (p as any).score || 0,
        confidence: (p as any).confidence || 0,
        isStablePair: (p as any).isStablePair || false,
        liquidityUsd: (p as any).liquidityUsd || 0,
        volume24hUsd: (p as any).volume24hUsd || 0,
      })),
    };
  } catch (e: any) {
    return { ok: false, error: e?.message || 'Unknown error' };
  }
}

/**
 * GET /pools/best - Get best pool for a token
 */
async function getBestPoolHandler(
  request: FastifyRequest<{ Querystring: BestPoolQuery }>,
  reply: FastifyReply
) {
  const chainId = Number(request.query.chainId) || 1;
  const token = request.query.token;
  
  if (!token) {
    return { ok: false, error: 'Missing token parameter' };
  }
  
  try {
    const pool = await bestPoolResolver.resolve(chainId, token);
    return { ok: true, chainId, token, pool };
  } catch (e: any) {
    return { ok: false, error: e?.message || 'Unknown error' };
  }
}

/**
 * POST /pools/score - Run scoring for a chain
 */
async function scoreHandler(
  request: FastifyRequest<{ Body: { chainId?: number } }>,
  reply: FastifyReply
) {
  const chainId = Number(request.body?.chainId) || 1;
  
  try {
    const result = await poolScoringService.scorePoolsForChain({ chainId });
    return { ok: true, ...result };
  } catch (e: any) {
    return { ok: false, error: e?.message || 'Unknown error' };
  }
}

/**
 * POST /pools/discover - Run discovery for a chain (swap-based)
 */
async function discoverHandler(
  request: FastifyRequest<{ Body: DiscoverBody }>,
  reply: FastifyReply
) {
  const chainId = Number(request.body?.chainId) || 1;
  const window = request.body?.window || '24h';
  
  try {
    const result = await poolDiscoveryService.discover({ chainId, window });
    return result;
  } catch (e: any) {
    return { ok: false, error: e?.message || 'Unknown error' };
  }
}

/**
 * POST /pools/discover-universe - Run discovery from Token Universe
 */
async function discoverUniverseHandler(
  request: FastifyRequest<{ Body: { chainId?: number } }>,
  reply: FastifyReply
) {
  const chainId = Number(request.body?.chainId) || 1;
  
  try {
    const result = await poolDiscoveryService.discoverFromUniverse({ chainId });
    return result;
  } catch (e: any) {
    return { ok: false, error: e?.message || 'Unknown error' };
  }
}

/**
 * GET /pools/job/status - Get job status
 */
async function jobStatusHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  const status = getPoolDiscoveryJobStatus();
  return { ok: true, ...status };
}

/**
 * POST /pools/job/run - Force run job
 */
async function jobRunHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  try {
    const result = await forceRunPoolDiscoveryJob();
    return { ok: true, result };
  } catch (e: any) {
    return { ok: false, error: e?.message || 'Unknown error' };
  }
}

/**
 * POST /pools/job/start - Start job
 */
async function jobStartHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  const result = startPoolDiscoveryJob({ enabled: true });
  return { ok: true, running: result.running };
}

/**
 * POST /pools/job/stop - Stop job
 */
async function jobStopHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  stopPoolDiscoveryJob();
  return { ok: true, message: 'Job stopped' };
}

/**
 * GET /pools/score/debug - Debug score for a specific pool
 * STEP 4.1: Shows full scoring breakdown
 */
async function scoreDebugHandler(
  request: FastifyRequest<{ Querystring: { pool?: string; chainId?: string } }>,
  reply: FastifyReply
) {
  const poolAddress = request.query.pool;
  const chainId = Number(request.query.chainId) || 1;
  
  if (!poolAddress) {
    return { ok: false, error: 'pool query param required' };
  }
  
  try {
    const pool = await DexPoolModel.findOne({
      chainId,
      address: poolAddress.toLowerCase(),
    }).lean();
    
    if (!pool) {
      return { ok: false, error: 'Pool not found' };
    }
    
    const result = poolScoringService.scorePool(pool);
    
    return {
      ok: true,
      pool: {
        address: pool.address,
        token0Symbol: pool.token0Symbol,
        token1Symbol: pool.token1Symbol,
        fee: pool.fee,
        liquidityUsd: pool.liquidityUsd,
        volume24hUsd: pool.volume24hUsd,
        trades24h: pool.trades24h,
        tvlSource: pool.tvlSource,
        tvlReliability: pool.tvlReliability,
        tvlUpdatedAt: pool.tvlUpdatedAt,
        lastSwapAt: pool.lastSwapAt,
      },
      scoring: result,
      thresholds: {
        activeScoreMin: SCORING.ACTIVE_SCORE_MIN,
        activeConfidenceMin: SCORING.ACTIVE_CONFIDENCE_MIN,
        activeLiquidityMinUsd: SCORING.ACTIVE_LIQUIDITY_MIN_USD,
        activeVolumeMinUsd: SCORING.ACTIVE_VOLUME_MIN_USD,
        degradedScoreMin: SCORING.DEGRADED_SCORE_MIN,
      },
    };
  } catch (e: any) {
    return { ok: false, error: e?.message || 'Unknown error' };
  }
}

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

import { liquidityRoutes } from './liquidity/index';

export async function poolRoutes(fastify: FastifyInstance): Promise<void> {
  // Public endpoints
  fastify.get('/stats', getStatsHandler);
  fastify.get('/list', getPoolsHandler);
  fastify.get('/best', getBestPoolHandler);
  
  // Admin endpoints
  fastify.post('/score', scoreHandler);
  fastify.get('/score/debug', scoreDebugHandler);  // STEP 4.1
  fastify.post('/discover', discoverHandler);
  fastify.post('/discover-universe', discoverUniverseHandler);
  
  // Job control
  fastify.get('/job/status', jobStatusHandler);
  fastify.post('/job/run', jobRunHandler);
  fastify.post('/job/start', jobStartHandler);
  fastify.post('/job/stop', jobStopHandler);
  
  // STEP 4.1: Liquidity routes
  await fastify.register(liquidityRoutes, { prefix: '/liquidity' });
  
  console.log('[Pool Routes] Registered');
}

export default poolRoutes;
