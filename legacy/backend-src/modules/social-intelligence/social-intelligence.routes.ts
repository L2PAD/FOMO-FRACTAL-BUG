/**
 * Social Intelligence Routes
 *
 * GET  /api/social-intelligence/:asset          — Social intel for asset
 * GET  /api/social-intelligence/:asset/detailed  — Full debug view
 * POST /api/social-intelligence/batch            — Batch analysis
 */
import type { FastifyInstance } from 'fastify';
import { analyzeSocial, analyzeSocialBatch, analyzeSocialDetailed } from './social-intelligence.service.js';

export async function socialIntelligenceRoutes(app: FastifyInstance): Promise<void> {

  app.get<{ Params: { asset: string } }>('/:asset', async (request) => {
    const intel = await analyzeSocial(request.params.asset);
    return { ok: true, asset: request.params.asset, socialIntel: intel };
  });

  app.get<{ Params: { asset: string } }>('/:asset/detailed', async (request) => {
    const result = await analyzeSocialDetailed(request.params.asset);
    return { ok: true, asset: request.params.asset, ...result };
  });

  app.post<{ Body: { assets: string[] } }>('/batch', async (request) => {
    const { assets } = request.body;
    if (!assets?.length) return { ok: true, results: {} };
    const results = await analyzeSocialBatch(assets);
    return { ok: true, results };
  });
}
