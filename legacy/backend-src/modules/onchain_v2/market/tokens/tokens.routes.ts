/**
 * Token Routes — Phase D (D1-D4)
 * =================================
 * Unified token endpoints: resolve, suggest, profile, series, movers.
 *
 * Endpoints:
 *   GET /tokens/resolve?chainId=1&q=UNI
 *   GET /tokens/suggest?chainId=1&q=un
 *   GET /tokens/profile?chainId=1&token=0x...
 *   GET /tokens/series?chainId=1&token=0x...&window=7d
 *   GET /tokens/movers?chainId=1&token=0x...&window=7d
 *   GET /tokens/series/status
 *   POST /tokens/series/force-tick
 */

import { FastifyInstance } from 'fastify';
import { resolveToken, suggestTokens } from './tokenResolve.service';
import { getTokenProfile } from './tokenProfile.service';
import { readTokenSeries, aggregateTokenBuckets } from './tokenSeriesAggregate.service';
import { getTokenSeriesJobStatus, forceTokenSeriesTick } from './tokenSeries.job';
import { getTokenMovers } from './tokenMovers.service';

type WindowKey = '24h' | '7d' | '30d';

function normWindow(x: any): WindowKey {
  const v = String(x || '7d');
  return (v === '24h' || v === '7d' || v === '30d') ? v as WindowKey : '7d';
}

export async function tokenRoutes(fastify: FastifyInstance) {

  // ── D1: Resolve ──
  fastify.get('/resolve', async (req) => {
    const q = req.query as any;
    const chainId = Number(q.chainId ?? 1);
    const query = String(q.q || '').trim();

    if (!query) {
      return { ok: true, token: null };
    }

    const token = await resolveToken(chainId, query);
    return { ok: true, token };
  });

  // ── D1: Suggest ──
  fastify.get('/suggest', async (req) => {
    const q = req.query as any;
    const chainId = Number(q.chainId ?? 1);
    const query = String(q.q || '').trim();
    const limit = Math.min(Number(q.limit || 10), 20);

    if (!query) {
      return { ok: true, items: [] };
    }

    const items = await suggestTokens(chainId, query, limit);
    return { ok: true, items };
  });

  // ── D2: Profile ──
  fastify.get('/profile', async (req) => {
    const q = req.query as any;
    const chainId = Number(q.chainId ?? 1);
    const token = String(q.token || '').trim();
    const window = normWindow(q.window);

    if (!token) {
      return { ok: false, reason: 'MISSING_TOKEN' };
    }

    return getTokenProfile({ chainId, token, window });
  });

  // ── D3: Series ──
  fastify.get('/series', async (req) => {
    const q = req.query as any;
    const chainId = Number(q.chainId ?? 1);
    const token = String(q.token || '').trim().toLowerCase();
    const window = normWindow(q.window);

    if (!token) {
      return { ok: false, reason: 'MISSING_TOKEN' };
    }

    // Resolve to address if symbol given
    let tokenAddress = token;
    if (!token.startsWith('0x')) {
      const resolved = await resolveToken(chainId, token);
      if (!resolved) return { ok: true, window, buckets: [], stale: false, reason: 'TOKEN_NOT_FOUND' };
      tokenAddress = resolved.address;
    }

    const result = await readTokenSeries({ chainId, tokenAddress, window });

    if (result.buckets.length === 0) {
      // Try on-demand aggregation
      await aggregateTokenBuckets(chainId, tokenAddress).catch(() => {});
      const retry = await readTokenSeries({ chainId, tokenAddress, window });
      return { ok: true, window, ...retry, reason: retry.buckets.length === 0 ? 'NO_DATA' : undefined };
    }

    return { ok: true, window, ...result };
  });

  // ── D3: Series Job Status ──
  fastify.get('/series/status', async () => {
    return { ok: true, ...getTokenSeriesJobStatus() };
  });

  // ── D3: Force Tick ──
  fastify.post('/series/force-tick', async () => {
    const status = await forceTokenSeriesTick();
    return { ok: true, ...status };
  });

  // ── D4: Movers ──
  fastify.get('/movers', async (req) => {
    const q = req.query as any;
    const chainId = Number(q.chainId ?? 1);
    const token = String(q.token || '').trim();
    const window = normWindow(q.window);

    if (!token) {
      return { ok: false, reason: 'MISSING_TOKEN' };
    }

    return getTokenMovers({ chainId, token, window });
  });

  console.log('[Tokens D1-D4] Routes registered');
}
