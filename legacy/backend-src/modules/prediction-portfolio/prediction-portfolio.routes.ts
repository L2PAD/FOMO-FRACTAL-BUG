/**
 * Portfolio Brain Routes — Stage 7
 *
 * Fastify routes for Portfolio Brain:
 *   POST /api/prediction-portfolio/assess       — Assess single candidate
 *   POST /api/prediction-portfolio/batch        — Assess batch of candidates
 *   GET  /api/prediction-portfolio/exposure      — Get portfolio exposure summary
 *   GET  /api/prediction-portfolio/positions     — List active positions
 *   POST /api/prediction-portfolio/positions     — Add/update a position
 *   DELETE /api/prediction-portfolio/positions/:id — Remove a position
 */
import type { FastifyInstance } from 'fastify';
import {
  assessCandidate,
  assessBatch,
  getExposure,
  addPosition,
  removePosition,
  listPositions,
} from './prediction-portfolio.service.js';

export async function predictionPortfolioRoutes(app: FastifyInstance): Promise<void> {

  /**
   * POST /assess — Assess a single candidate against portfolio
   */
  app.post<{ Body: any }>('/assess', async (request) => {
    const assessment = await assessCandidate(request.body);
    return { ok: true, assessment };
  });

  /**
   * POST /batch — Assess multiple candidates
   */
  app.post<{ Body: { cases: any[] } }>('/batch', async (request) => {
    const { cases } = request.body;
    if (!cases?.length) return { ok: true, results: {} };
    const results = await assessBatch(cases);
    return { ok: true, results };
  });

  /**
   * GET /exposure — Portfolio exposure summary
   */
  app.get('/exposure', async () => {
    const exposure = await getExposure();
    return { ok: true, exposure };
  });

  /**
   * GET /positions — List active positions
   */
  app.get('/positions', async () => {
    const positions = await listPositions();
    return { ok: true, count: positions.length, positions };
  });

  /**
   * POST /positions — Add or update a position
   */
  app.post<{ Body: any }>('/positions', async (request) => {
    await addPosition(request.body);
    return { ok: true };
  });

  /**
   * DELETE /positions/:id — Remove (deactivate) a position
   */
  app.delete<{ Params: { id: string } }>('/positions/:id', async (request) => {
    await removePosition(request.params.id);
    return { ok: true };
  });
}
