/**
 * CEX Flow Routes — Phase A, Block A2
 * =====================================
 *
 * API endpoints for CEX inflow/outflow intelligence.
 *
 * GET /exchanges        — List available exchanges
 * GET /summary          — Summary for one exchange (totals + top tokens)
 * GET /tokens           — Token-level IN/OUT table
 * GET /cross            — Cross-exchange comparison
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { CexFlowService } from './cexFlow.service';

const svc = new CexFlowService();

export async function cexFlowRoutes(fastify: FastifyInstance): Promise<void> {
  /**
   * GET /cex-flow/exchanges?chainId=1
   */
  fastify.get('/exchanges', async (request: FastifyRequest<{
    Querystring: { chainId?: string };
  }>) => {
    try {
      const chainId = Number(request.query.chainId ?? 1);
      return svc.getExchanges(chainId);
    } catch (e: any) {
      return { ok: false, error: e.message };
    }
  });

  /**
   * GET /cex-flow/summary?chainId=1&entityId=binance&window=24h
   */
  fastify.get('/summary', async (request: FastifyRequest<{
    Querystring: { chainId?: string; entityId?: string; window?: string };
  }>) => {
    try {
      const chainId = Number(request.query.chainId ?? 1);
      const entityId = String(request.query.entityId ?? '');
      const window = String(request.query.window ?? '24h');

      if (!entityId) return { ok: false, error: 'MISSING_ENTITY_ID' };

      return svc.getSummary({ chainId, entityId, window });
    } catch (e: any) {
      return { ok: false, error: e.message };
    }
  });

  /**
   * GET /cex-flow/tokens?chainId=1&entityId=binance&window=24h&direction=in&limit=50
   */
  fastify.get('/tokens', async (request: FastifyRequest<{
    Querystring: {
      chainId?: string;
      entityId?: string;
      window?: string;
      direction?: string;
      limit?: string;
    };
  }>) => {
    try {
      const chainId = Number(request.query.chainId ?? 1);
      const entityId = String(request.query.entityId ?? '');
      const window = String(request.query.window ?? '24h');
      const direction = (request.query.direction as 'in' | 'out' | 'all') || 'all';
      const limit = Number(request.query.limit ?? 50);

      if (!entityId) return { ok: false, error: 'MISSING_ENTITY_ID' };

      return svc.getTokens({ chainId, entityId, window, direction, limit });
    } catch (e: any) {
      return { ok: false, error: e.message };
    }
  });

  /**
   * GET /cex-flow/cross?chainId=1&window=24h
   */
  fastify.get('/cross', async (request: FastifyRequest<{
    Querystring: { chainId?: string; window?: string };
  }>) => {
    try {
      const chainId = Number(request.query.chainId ?? 1);
      const window = String(request.query.window ?? '24h');
      return svc.getCrossExchange({ chainId, window });
    } catch (e: any) {
      return { ok: false, error: e.message };
    }
  });

  console.log('[CEX Flow Routes] Registered');
}
