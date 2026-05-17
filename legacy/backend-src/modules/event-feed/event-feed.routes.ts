/**
 * Event Feed Routes
 *
 * GET  /api/event-feed                — Curated feed (query: hoursBack, limit, asset, eventType, priorityBand)
 * GET  /api/event-feed/asset/:asset   — Feed for specific asset
 * GET  /api/event-feed/stats          — Feed statistics
 * GET  /api/event-feed/sources        — Source registry
 * POST /api/event-feed/related        — Related events for entities (used by prediction pipeline)
 */

import type { FastifyInstance } from 'fastify';
import { feedOrchestratorService } from './services/feed-orchestrator.service.js';
import { sourceRegistryService } from './services/source-registry.service.js';

export async function eventFeedRoutes(app: FastifyInstance): Promise<void> {
  /**
   * GET /api/event-feed — Main curated feed
   */
  app.get<{
    Querystring: {
      hoursBack?: string;
      limit?: string;
      asset?: string;
      eventType?: string;
      priorityBand?: string;
      minPriority?: string;
    };
  }>('/', async (request) => {
    const q = request.query;
    const feed = await feedOrchestratorService.buildFeed({
      hoursBack: q.hoursBack ? parseInt(q.hoursBack) : 24,
      limit: q.limit ? parseInt(q.limit) : 30,
      asset: q.asset || undefined,
      eventType: q.eventType || undefined,
      priorityBand: q.priorityBand as any || undefined,
      minPriority: q.minPriority ? parseFloat(q.minPriority) : undefined,
    });

    return { ok: true, ...feed };
  });

  /**
   * GET /api/event-feed/asset/:asset — Feed for specific asset
   */
  app.get<{ Params: { asset: string }; Querystring: { hoursBack?: string } }>(
    '/asset/:asset',
    async (request) => {
      const clusters = await feedOrchestratorService.getFeedForAsset(
        request.params.asset,
        request.query.hoursBack ? parseInt(request.query.hoursBack) : 24,
      );
      return { ok: true, asset: request.params.asset, clusters, count: clusters.length };
    },
  );

  /**
   * GET /api/event-feed/stats — Feed statistics
   */
  app.get('/stats', async () => {
    const stats = await feedOrchestratorService.getStats();
    return { ok: true, ...stats };
  });

  /**
   * GET /api/event-feed/sources — Source registry
   */
  app.get('/sources', async () => {
    const sources = sourceRegistryService.getAll();
    return {
      ok: true,
      sources,
      summary: {
        tier1: sources.filter(s => s.tier === 1).length,
        tier2: sources.filter(s => s.tier === 2).length,
        tier3: sources.filter(s => s.tier === 3).length,
        total: sources.length,
        enabled: sources.filter(s => s.enabled).length,
      },
    };
  });

  /**
   * POST /api/event-feed/related — Related events for entities
   * Body: { entities: string[], eventType: string, hoursBack?: number }
   */
  app.post<{
    Body: { entities: string[]; eventType: string; hoursBack?: number };
  }>('/related', async (request) => {
    const { entities, eventType, hoursBack } = request.body;
    if (!entities?.length) return { ok: true, events: [] };

    const events = await feedOrchestratorService.getRelatedEvents(
      entities,
      eventType,
      hoursBack ?? 48,
    );

    return { ok: true, events, count: events.length };
  });
}
