/**
 * News Control Routes
 * ===================
 * Admin API for managing and monitoring the news ingestion pipeline.
 *
 * Endpoints:
 *   GET    /sources          — List all sources with stats
 *   POST   /sources/toggle   — Enable/disable a source
 *   GET    /health           — Comprehensive health snapshot
 *   POST   /run              — Manual news ingestion trigger
 *   GET    /events           — Recent news events preview
 *   GET    /events/stats     — News event statistics
 *
 * CONTROL LAYER — no AI, no clustering, no ML impact.
 */

import type { FastifyInstance } from 'fastify';
import mongoose from 'mongoose';
import { newsSourceRegistryService } from './news-source-registry.service.js';
import { newsHealthService } from './news-health.service.js';
import { ingestionOrchestratorService } from '../ingestion/ingestion.orchestrator.service.js';

export async function registerNewsControlRoutes(app: FastifyInstance): Promise<void> {
  /**
   * GET /sources — List all sources with stats
   */
  app.get('/sources', async () => {
    const sources = await newsSourceRegistryService.getAll();
    return {
      ok: true,
      data: {
        total: sources.length,
        enabled: sources.filter(s => s.enabled).length,
        sources,
      },
    };
  });

  /**
   * POST /sources/toggle — Enable/disable a source
   * Body: { sourceId: string, enabled: boolean }
   */
  app.post('/sources/toggle', async (request, reply) => {
    const body = request.body as { sourceId?: string; enabled?: boolean };
    if (!body.sourceId || typeof body.enabled !== 'boolean') {
      return reply.code(400).send({ ok: false, error: 'sourceId (string) and enabled (boolean) required' });
    }

    const updated = await newsSourceRegistryService.toggle(body.sourceId, body.enabled);
    if (!updated) {
      return reply.code(404).send({ ok: false, error: `Source '${body.sourceId}' not found` });
    }

    return { ok: true, data: updated };
  });

  /**
   * GET /health — Comprehensive health snapshot
   */
  app.get('/health', async () => {
    const health = await newsHealthService.getHealth();
    return { ok: true, data: health };
  });

  /**
   * POST /run — Manual news ingestion trigger
   * Body: { limit?: number, sinceMinutes?: number, seedAll?: boolean }
   */
  app.post('/run', async (request, reply) => {
    try {
      const body = (request.body ?? {}) as {
        limit?: number;
        sinceMinutes?: number;
        seedAll?: boolean;
      };

      const result = await ingestionOrchestratorService.runNewsIngestion({
        limit: body.limit ?? 100,
        sinceMinutes: body.sinceMinutes ?? 180,
        seedAll: body.seedAll ?? false,
      });

      return { ok: true, data: result };
    } catch (err: any) {
      if (err.message?.includes('LOCK_BUSY')) {
        return reply.code(409).send({ ok: false, error: 'LOCK_BUSY', message: 'News ingestion already running' });
      }
      return reply.code(500).send({ ok: false, error: err.message });
    }
  });

  /**
   * GET /events — Recent news events preview
   * Query: ?limit=20&source=coindesk&asset=BTC
   */
  app.get('/events', async (request) => {
    const db = mongoose.connection.db;
    if (!db) return { ok: false, error: 'DB not connected' };

    const query = request.query as { limit?: string; source?: string; asset?: string };
    const limit = Math.min(parseInt(query.limit || '30', 10), 100);

    const filter: Record<string, any> = { sourceType: 'news' };
    if (query.source) {
      filter['publisher.name'] = { $regex: new RegExp(query.source, 'i') };
    }
    if (query.asset) {
      filter.assetMentions = query.asset.toUpperCase();
    }

    const events = await db.collection('raw_events')
      .aggregate([
        { $match: filter },
        { $sort: { publishedAt: -1 } },
        { $limit: limit },
        {
          $project: {
            _id: 0,
            externalId: 1,
            title: 1,
            text: { $substrCP: ['$text', 0, 200] },
            url: 1,
            sourceType: 1,
            sourceName: 1,
            'publisher.name': 1,
            'publisher.domain': 1,
            assetMentions: 1,
            publishedAt: 1,
            ingestedAt: 1,
            'raw.feedTier': 1,
            'raw.categories': 1,
          },
        },
      ])
      .toArray();

    return {
      ok: true,
      data: {
        count: events.length,
        events,
      },
    };
  });

  /**
   * GET /events/stats — News event statistics
   */
  app.get('/events/stats', async () => {
    const db = mongoose.connection.db;
    if (!db) return { ok: false, error: 'DB not connected' };

    const col = db.collection('raw_events');
    const now = Date.now();

    // Total news events
    const total = await col.countDocuments({ sourceType: 'news' });

    // By publisher
    const byPublisher = await col.aggregate([
      { $match: { sourceType: 'news' } },
      { $group: { _id: '$publisher.name', count: { $sum: 1 } } },
      { $sort: { count: -1 } },
    ]).toArray();

    // By asset mention
    const byAsset = await col.aggregate([
      { $match: { sourceType: 'news', assetMentions: { $ne: [] } } },
      { $unwind: '$assetMentions' },
      { $group: { _id: '$assetMentions', count: { $sum: 1 } } },
      { $sort: { count: -1 } },
      { $limit: 15 },
    ]).toArray();

    // Time distribution (events per hour, last 24h)
    const oneDayAgo = new Date(now - 24 * 60 * 60 * 1000);
    const timeDistribution = await col.aggregate([
      { $match: { sourceType: 'news', publishedAt: { $gte: oneDayAgo } } },
      {
        $group: {
          _id: {
            $dateToString: { format: '%Y-%m-%dT%H:00:00Z', date: '$publishedAt' },
          },
          count: { $sum: 1 },
        },
      },
      { $sort: { _id: 1 } },
    ]).toArray();

    // Latest event
    const latest = await col.findOne(
      { sourceType: 'news' },
      { sort: { publishedAt: -1 }, projection: { _id: 0, title: 1, publishedAt: 1, 'publisher.name': 1 } }
    );

    // Oldest event
    const oldest = await col.findOne(
      { sourceType: 'news' },
      { sort: { publishedAt: 1 }, projection: { _id: 0, title: 1, publishedAt: 1, 'publisher.name': 1 } }
    );

    return {
      ok: true,
      data: {
        total,
        byPublisher: Object.fromEntries(byPublisher.map(b => [b._id, b.count])),
        byAsset: Object.fromEntries(byAsset.map(b => [b._id, b.count])),
        timeDistribution: timeDistribution.map(t => ({ hour: t._id, count: t.count })),
        latest,
        oldest,
      },
    };
  });

  console.log('[NewsControl] Admin routes registered');
}
