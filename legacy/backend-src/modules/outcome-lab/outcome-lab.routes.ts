/**
 * Outcome Lab Routes
 *
 * POST /api/outcome-lab/review          — Review a resolved market
 * POST /api/outcome-lab/simulate        — Simulate review with case data
 * POST /api/outcome-lab/trace           — Save a trace for a case
 * POST /api/outcome-lab/trace/batch     — Save traces for batch of cases
 * GET  /api/outcome-lab/stats           — Dashboard stats
 * GET  /api/outcome-lab/reviews         — Recent reviews
 * GET  /api/outcome-lab/heatmap         — Signal confidence heatmap
 * GET  /api/outcome-lab/trace/:marketId — Get trace for a market
 */

import type { FastifyInstance } from 'fastify';
import { outcomeLabService } from './services/outcome-lab.service.js';
import { traceBuilderService } from './services/trace-builder.service.js';

export async function outcomeLabRoutes(app: FastifyInstance): Promise<void> {
  /**
   * POST /api/outcome-lab/review — Full review of a resolved market
   * Body: { marketId, question, asset, outcome: 'YES'|'NO', resolvedAt?, finalPrice? }
   */
  app.post<{
    Body: {
      marketId: string;
      question?: string;
      asset?: string;
      outcome: 'YES' | 'NO';
      resolvedAt?: string;
      finalPrice?: number;
    };
  }>('/review', async (request) => {
    const { marketId, question, asset, outcome, resolvedAt, finalPrice } = request.body;
    if (!marketId || !outcome) return { ok: false, error: 'marketId and outcome required' };

    const review = await outcomeLabService.review({
      marketId,
      question: question || '',
      asset: asset || 'BTC',
      outcome,
      resolvedAt: resolvedAt ? new Date(resolvedAt) : new Date(),
      finalPrice: finalPrice ?? (outcome === 'YES' ? 1 : 0),
    });

    if (!review) return { ok: false, error: 'No trace found for this market' };
    return { ok: true, review };
  });

  /**
   * POST /api/outcome-lab/simulate — Simulate a review
   * Body: { caseData: {}, outcome: 'YES'|'NO' }
   */
  app.post<{
    Body: { caseData: Record<string, any>; outcome: 'YES' | 'NO' };
  }>('/simulate', async (request) => {
    const { caseData, outcome } = request.body;
    if (!caseData || !outcome) return { ok: false, error: 'caseData and outcome required' };

    const review = await outcomeLabService.simulateReview(caseData, outcome);
    return { ok: true, review };
  });

  /**
   * POST /api/outcome-lab/trace — Save a single trace
   * Body: case data object (from /api/prediction/run)
   */
  app.post<{ Body: Record<string, any> }>('/trace', async (request) => {
    const trace = traceBuilderService.buildTrace(request.body);
    await traceBuilderService.saveTrace(trace);
    return { ok: true, marketId: trace.marketId, action: trace.action };
  });

  /**
   * POST /api/outcome-lab/trace/batch — Save traces for batch of cases
   * Body: { cases: [...] }
   */
  app.post<{ Body: { cases: Record<string, any>[] } }>('/trace/batch', async (request) => {
    const { cases } = request.body;
    if (!cases?.length) return { ok: false, error: 'cases array required' };

    const saved = await traceBuilderService.saveBatchTraces(cases);
    return { ok: true, saved, total: cases.length };
  });

  /**
   * GET /api/outcome-lab/stats — Dashboard stats
   */
  app.get('/stats', async () => {
    const stats = await outcomeLabService.getStats();
    return { ok: true, ...stats };
  });

  /**
   * GET /api/outcome-lab/reviews — Recent reviews
   */
  app.get<{ Querystring: { limit?: string } }>('/reviews', async (request) => {
    const limit = request.query.limit ? parseInt(request.query.limit) : 20;
    const reviews = await outcomeLabService.getRecentReviews(limit);
    return { ok: true, reviews, count: reviews.length };
  });

  /**
   * GET /api/outcome-lab/heatmap — Signal confidence heatmap
   */
  app.get('/heatmap', async () => {
    const heatmap = await outcomeLabService.getHeatmap();
    return { ok: true, heatmap, count: heatmap.length };
  });

  /**
   * GET /api/outcome-lab/trace/:marketId — Get trace history for a market
   */
  app.get<{ Params: { marketId: string } }>('/trace/:marketId', async (request) => {
    const history = await traceBuilderService.getTraceHistory(request.params.marketId);
    const latest = history.length > 0 ? history[history.length - 1] : null;
    return { ok: true, latest, history, count: history.length };
  });
}
