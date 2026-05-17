/**
 * Prediction Intel Routes
 *
 * Fastify routes for the Signal Intelligence layer (Stage 6).
 *
 * Endpoints:
 *   GET  /api/prediction-intel/market/:marketId   - Get signal intelligence for a market
 *   POST /api/prediction-intel/batch              - Get signal intelligence for multiple markets
 *   GET  /api/prediction-intel/events/:asset      - Get recent enriched events for an asset
 *   GET  /api/prediction-intel/sources            - List known source profiles
 */
import type { FastifyInstance } from 'fastify';
import { getMarketIntelligence, getBatchIntelligence, getRecentEvents } from './prediction-intel.service.js';
import { getSourceProfile, computeTrustScore } from './services/source-trust.service.js';
import { DEFAULT_SOURCE_PROFILES } from './types/source.types.js';

export async function predictionIntelRoutes(app: FastifyInstance): Promise<void> {
  /**
   * GET /market/:marketId - Get signal intelligence for a specific market
   */
  app.get<{
    Params: { marketId: string };
    Querystring: {
      asset?: string;
      entities?: string;
      eventType?: string;
      currentProb?: string;
      move6h?: string;
      move24h?: string;
      volume?: string;
      repricingState?: string;
      hoursBack?: string;
    };
  }>('/market/:marketId', async (request) => {
    const { marketId } = request.params;
    const q = request.query;

    const result = await getMarketIntelligence({
      marketId,
      asset: q.asset || 'BTC',
      entities: q.entities ? q.entities.split(',') : [q.asset || 'BTC'],
      eventType: q.eventType || 'unknown',
      currentProb: parseFloat(q.currentProb || '0.5'),
      move6h: parseFloat(q.move6h || '0'),
      move24h: parseFloat(q.move24h || '0'),
      volume: parseFloat(q.volume || '0'),
      repricingState: q.repricingState,
      hoursBack: parseInt(q.hoursBack || '48', 10),
    });

    return { ok: true, data: result };
  });

  /**
   * POST /batch - Get signal intelligence for multiple markets
   */
  app.post<{
    Body: {
      markets: Array<{
        marketId: string;
        asset: string;
        entities: string[];
        eventType: string;
        currentProb: number;
        move6h: number;
        move24h: number;
        volume: number;
        repricingState?: string;
      }>;
    };
  }>('/batch', async (request) => {
    const { markets } = request.body;
    if (!markets?.length) {
      return { ok: true, results: {} };
    }

    const batchMap = await getBatchIntelligence(markets);
    const results: Record<string, any> = {};
    for (const [id, batch] of batchMap) {
      results[id] = batch;
    }

    return { ok: true, results };
  });

  /**
   * GET /events/:asset - Get recent enriched events for debugging
   */
  app.get<{
    Params: { asset: string };
    Querystring: { hoursBack?: string };
  }>('/events/:asset', async (request) => {
    const { asset } = request.params;
    const hoursBack = parseInt(request.query.hoursBack || '24', 10);
    const events = await getRecentEvents(asset, hoursBack);

    return {
      ok: true,
      asset,
      count: events.length,
      events,
    };
  });

  /**
   * GET /debug/:asset - Trace the full pipeline for debugging
   */
  app.get<{
    Params: { asset: string };
  }>('/debug/:asset', async (request) => {
    const { asset } = request.params;

    // Get raw events
    let db;
    try {
      const { getDb } = await import('../../db/mongodb.js');
      db = getDb();
    } catch {
      return { ok: false, error: 'DB not connected' };
    }

    const { enrichEvent: _enrich } = await import('./services/event-enrichment.service.js');
    const { deduplicateEvents: _dedup } = await import('./services/dedup.service.js');
    const { getSourceProfile: _getSource, computeTrustScore: _trust } = await import('./services/source-trust.service.js');
    const { interpretEvent: _interpret } = await import('./services/event-interpreter.service.js');
    const { normalizeSignals: _norm } = await import('./services/signal-normalizer.service.js');

    const cutoff = new Date(Date.now() - 48 * 3600 * 1000);
    const cutoffIso = cutoff.toISOString();
    const rawDocs = await db.collection('notification_events')
      .find({ asset, $or: [{ createdAt: { $gte: cutoff } }, { createdAt: { $gte: cutoffIso } }] })
      .sort({ createdAt: -1 }).limit(20).toArray();

    const enriched = rawDocs.map(doc => _enrich(doc));
    const deduped = _dedup(enriched);
    const recentTexts = deduped.map(e => e.text);

    const context = {
      marketId: 'debug',
      asset,
      entities: [asset],
      eventType: 'price_threshold',
      currentProb: 0.5,
      move6h: 0.03,
      move24h: 0.05,
      volume: 10000,
    };

    const interpreted = deduped.map(evt => {
      const source = _getSource(evt.extractedSource);
      return {
        event: evt.text.slice(0, 60),
        sourceType: source.type,
        trustScore: _trust(source),
        ..._interpret(evt, source, context, recentTexts),
      };
    });

    const signals = _norm(interpreted as any);

    return {
      ok: true,
      pipeline: {
        raw: rawDocs.length,
        enriched: enriched.length,
        deduped: deduped.length,
        interpreted: interpreted.length,
        normalized: signals.length,
      },
      interpreted: interpreted.slice(0, 5),
      signals: signals.slice(0, 5),
    };
  });

  /**
   * GET /sources - List all known source profiles with trust scores
   */
  app.get('/sources', async () => {
    const entries = Object.entries(DEFAULT_SOURCE_PROFILES).map(([type, trust]) => {
      const profile = { sourceId: type, name: type, type: type as any, trust };
      return {
        ...profile,
        trustScore: computeTrustScore(profile),
      };
    });

    return { ok: true, profiles: entries };
  });
}
