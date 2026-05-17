/**
 * Case Intelligence Routes
 *
 * POST /api/case-intelligence/analyze  — Analyze single market case
 * POST /api/case-intelligence/batch    — Analyze batch of cases
 */
import type { FastifyInstance } from 'fastify';
import { buildCase, buildCaseBatch } from './case-intelligence.service.js';

export async function caseIntelligenceRoutes(app: FastifyInstance): Promise<void> {

  app.post<{ Body: any }>('/analyze', async (request) => {
    const result = await buildCase(request.body);
    return { ok: true, ...result };
  });

  app.post<{ Body: { cases: any[] } }>('/batch', async (request) => {
    const { cases } = request.body;
    if (!cases?.length) return { ok: true, results: {} };
    const results = await buildCaseBatch(cases);
    return { ok: true, results };
  });
}
