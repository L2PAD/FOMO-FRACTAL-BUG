/**
 * OnChain V2 — Pricing Routes
 * =============================
 * 
 * STEP 1: USD Valuation Layer
 * 
 * API endpoints for pricing service.
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { pricingService } from './index';

interface LatestQuery {
  chainId: string;
  token: string;
}

interface RefreshBody {
  chainId: number;
  token: string;
}

interface BatchBody {
  chainId: number;
  tokens: string[];
}

/**
 * GET /pricing/latest - Get cached/fresh price for token
 */
async function getLatestHandler(
  request: FastifyRequest<{ Querystring: LatestQuery }>,
  reply: FastifyReply
) {
  try {
    const chainId = Number(request.query.chainId);
    const token = String(request.query.token || '').toLowerCase();
    
    if (!chainId || !token) {
      return { ok: false, error: 'Missing chainId or token' };
    }
    
    const quote = await pricingService.getUsdPrice({
      chainId,
      token,
      allowStale: true,
    });
    
    return { ok: true, data: quote };
  } catch (e: any) {
    return { ok: false, error: e?.message || 'Unknown error' };
  }
}

/**
 * POST /pricing/refresh - Force refresh price
 */
async function refreshHandler(
  request: FastifyRequest<{ Body: RefreshBody }>,
  reply: FastifyReply
) {
  try {
    const { chainId, token } = request.body;
    
    if (!chainId || !token) {
      return { ok: false, error: 'Missing chainId or token' };
    }
    
    const quote = await pricingService.refreshPrice({ chainId, token });
    
    return { ok: true, data: quote };
  } catch (e: any) {
    return { ok: false, error: e?.message || 'Unknown error' };
  }
}

/**
 * POST /pricing/batch - Get prices for multiple tokens
 */
async function batchHandler(
  request: FastifyRequest<{ Body: BatchBody }>,
  reply: FastifyReply
) {
  try {
    const { chainId, tokens } = request.body;
    
    if (!chainId || !tokens || !Array.isArray(tokens)) {
      return { ok: false, error: 'Missing chainId or tokens array' };
    }
    
    const results = await pricingService.getBatchPrices({
      chainId,
      tokens,
      allowStale: true,
    });
    
    // Convert Map to object for JSON serialization
    const data: Record<string, any> = {};
    for (const [token, quote] of results) {
      data[token] = quote;
    }
    
    return { ok: true, data, count: tokens.length };
  } catch (e: any) {
    return { ok: false, error: e?.message || 'Unknown error' };
  }
}

/**
 * GET /pricing/health - Service health status
 */
async function healthHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  const health = pricingService.getHealth();
  return { ok: true, ...health };
}

/**
 * POST /pricing/clear-cache - Clear memory cache
 */
async function clearCacheHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  pricingService.clearCache();
  return { ok: true, message: 'Cache cleared' };
}

/**
 * Register pricing routes
 */
export async function pricingRoutes(fastify: FastifyInstance): Promise<void> {
  // Public endpoints
  fastify.get('/latest', getLatestHandler);
  fastify.get('/health', healthHandler);
  
  // Admin endpoints
  fastify.post('/refresh', refreshHandler);
  fastify.post('/batch', batchHandler);
  fastify.post('/clear-cache', clearCacheHandler);
  
  // STEP 2: Pool sub-routes
  const { poolRoutes } = await import('./pools');
  await fastify.register(poolRoutes, { prefix: '/pools' });
  
  console.log('[Pricing Routes] Registered');
}

export default pricingRoutes;
