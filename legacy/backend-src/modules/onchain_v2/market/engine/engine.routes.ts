/**
 * Engine Routes — Decision API
 * ==============================
 * 
 * PHASE 4: Token-first decision endpoint
 * GET /api/v10/onchain-v2/engine/decision?chainId=1&window=7d&symbol=LINK
 */

import type { FastifyInstance } from 'fastify';
import { computeDecision } from './engine.decision.service.js';
import { computeProjectRanking, type ProjectAction } from './engine_project_ranking.service.js';

export async function engineRoutes(app: FastifyInstance) {
  /**
   * GET /engine/decision
   * Returns actionable decision for a specific token
   */
  app.get('/decision', async (request, reply) => {
    const { chainId = '1', window = '7d', symbol, address } = request.query as any;
    
    if (!symbol && !address) {
      return reply.code(400).send({
        ok: false,
        error: 'MISSING_TARGET',
        message: 'Provide ?symbol=LINK or ?address=0x...',
      });
    }

    try {
      const decision = await computeDecision({
        chainId: Number(chainId),
        window: String(window),
        symbol: symbol ? String(symbol) : undefined,
        address: address ? String(address) : undefined,
      });

      return decision;
    } catch (err) {
      console.error('[Engine] Decision error:', err);
      return reply.code(500).send({
        ok: false,
        error: 'ENGINE_ERROR',
        message: err instanceof Error ? err.message : 'Internal error',
      });
    }
  });

  /**
   * GET /engine/projects
   * Phase B: Returns ranked list of tokens with multi-signal scoring
   */
  app.get('/projects', async (request) => {
    const q = request.query as any;
    const chainId = Number(q.chainId ?? 1);
    const window = String(q.window ?? '7d');
    const limit = Math.min(Number(q.limit ?? 100), 500);
    const action = q.action as ProjectAction | undefined;
    const atTs = q.atTs ? Number(q.atTs) : undefined;

    return computeProjectRanking({
      chainId, window, limit,
      filterAction: action,
      atTs,
    });
  });

  console.log('[Engine] Decision + Projects routes registered');
}
