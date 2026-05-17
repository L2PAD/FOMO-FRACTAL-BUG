/**
 * OnChain V2 — Assets Routes
 * ===========================
 * 
 * PHASE 4: Assets Tab API endpoints
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { assetsProfileService } from './assets.profile.service';
import { assetsListService } from './assets.list.service';

// ═══════════════════════════════════════════════════════════════
// HANDLERS
// ═══════════════════════════════════════════════════════════════

/**
 * GET /assets/profile - Get token intelligence profile
 */
async function profileHandler(
  request: FastifyRequest<{ 
    Querystring: { 
      chainId?: string; 
      token?: string; 
      window?: string;
    } 
  }>,
  reply: FastifyReply
) {
  const chainId = Number(request.query.chainId) || 1;
  const token = String(request.query.token || '').trim();
  const window = (request.query.window as '24h' | '7d' | '30d') || '7d';
  
  if (!token) {
    return { ok: false, reason: 'MISSING_TOKEN' };
  }
  
  try {
    const result = await assetsProfileService.getTokenProfile({
      chainId,
      token,
      window,
    });
    return result;
  } catch (e: any) {
    return { ok: false, reason: e?.message || 'PROFILE_ERROR' };
  }
}

/**
 * GET /assets/list - Get token list by criteria
 */
async function listHandler(
  request: FastifyRequest<{
    Querystring: {
      chainId?: string;
      kind?: string;
      window?: string;
      limit?: string;
    }
  }>,
  reply: FastifyReply
) {
  const chainId = Number(request.query.chainId) || 1;
  const kind = (request.query.kind as 'signals' | 'tvl' | 'spikes') || 'signals';
  const window = (request.query.window as '24h' | '7d' | '30d') || '7d';
  const limit = Number(request.query.limit) || 20;
  
  try {
    const result = await assetsListService.list({
      chainId,
      kind,
      window,
      limit,
    });
    return result;
  } catch (e: any) {
    return { ok: false, reason: e?.message || 'LIST_ERROR', items: [] };
  }
}

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function assetsRoutes(fastify: FastifyInstance): Promise<void> {
  // Token profile
  fastify.get('/profile', profileHandler);
  
  // Token lists
  fastify.get('/list', listHandler);
  
  console.log('[Assets Routes] Registered');
}

export default assetsRoutes;
