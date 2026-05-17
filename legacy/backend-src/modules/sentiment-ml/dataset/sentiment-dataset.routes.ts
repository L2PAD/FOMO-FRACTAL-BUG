/**
 * Sentiment Dataset Admin Routes
 * ================================
 * 
 * BLOCK 6: Admin API for dataset monitoring and manual control.
 * 
 * Wrapped in fastify-plugin for proper async registration.
 * 
 * Endpoints:
 * - GET  /stats — Overall statistics
 * - GET  /perf — Hit rate and correlation
 * - GET  /samples — Recent samples
 * - POST /trigger — Manual finalize trigger
 * - GET  /job — Job status
 */

import fp from 'fastify-plugin';
import type { FastifyInstance, FastifyRequest } from 'fastify';
import mongoose from 'mongoose';
import { getSentimentDatasetJob } from './sentiment-dataset-finalize.job.js';
import { getSentimentDatasetStatsService } from './sentiment-dataset-stats.service.js';
import { SentimentWindow, SentimentDirSampleModel } from './sentiment-dir-sample.model.js';
import { labelFromReturn, SENTIMENT_LABEL_VERSION } from './sentiment-dataset-labels.js';

async function sentimentDatasetRoutes(app: FastifyInstance): Promise<void> {
  /**
   * GET /stats — Overall dataset statistics
   */
  app.get('/stats', async () => {
    const stats = getSentimentDatasetStatsService();
    const job = getSentimentDatasetJob();

    const data = await stats.getStats();

    return {
      ok: true,
      data,
      job: job?.getStatus() ?? { enabled: false, running: false },
    };
  });

  /**
   * GET /perf — Performance metrics (hit rate, correlation)
   */
  app.get('/perf', async (req: FastifyRequest<{ Querystring: { window?: string } }>) => {
    const window = (req.query.window || '7D') as SentimentWindow;
    const stats = getSentimentDatasetStatsService();

    const [hitRate, correlation] = await Promise.all([
      stats.getHitRate(window),
      stats.getCorrelation(window),
    ]);

    return {
      ok: true,
      window,
      hitRate,
      correlation,
    };
  });

  /**
   * GET /samples — Recent samples for debugging
   */
  app.get('/samples', async (req: FastifyRequest<{ Querystring: { limit?: string } }>) => {
    const limit = parseInt(req.query.limit || '20', 10);
    const stats = getSentimentDatasetStatsService();

    const samples = await stats.getRecentSamples(Math.min(limit, 100));

    return {
      ok: true,
      count: samples.length,
      samples,
    };
  });

  /**
   * POST /trigger — Manual finalize trigger
   * Body: { mode?: 'live' | 'backfill' }
   */
  app.post('/trigger', async (req: FastifyRequest<{ Body: { mode?: 'live' | 'backfill' } }>) => {
    const body = req.body || {};
    const mode = body.mode || 'live';
    const job = getSentimentDatasetJob();

    if (!job) {
      return { ok: false, error: 'Job not initialized' };
    }

    const result = await job.triggerManual(mode);

    if (!result) {
      return { ok: false, error: 'Job is currently running' };
    }

    return {
      ok: true,
      mode,
      result,
    };
  });

  /**
   * GET /job — Job status
   */
  app.get('/job', async () => {
    const job = getSentimentDatasetJob();

    return {
      ok: true,
      status: job?.getStatus() ?? { enabled: false, running: false },
    };
  });

  /**
   * POST /finalize-trades — Mass finalize all sent_trades with exitPrice+pnlPct
   * Creates sentiment_dir_samples from trade outcomes (ground truth)
   */
  app.post('/finalize-trades', async (req: FastifyRequest<{ Body: { dryRun?: boolean } }>) => {
    const body = (req.body ?? {}) as { dryRun?: boolean };
    const dryRun = body.dryRun ?? false;
    const db = mongoose.connection.db;
    if (!db) return { ok: false, error: 'DB not connected' };

    const tradesCol = db.collection('sent_trades');
    const aggsCol = db.collection('sentiment_aggregates');

    // Find all unfinalzied trades with outcomes
    const trades = await tradesCol
      .find({
        finalized: { $ne: true },
        exitPrice: { $exists: true, $ne: null },
        pnlPct: { $exists: true, $ne: null },
      })
      .toArray();

    const counters = { total: trades.length, created: 0, updated: 0, skipped: 0, errors: 0, byLabel: { UP: 0, DOWN: 0, NEUTRAL: 0 } as Record<string, number>, byWindow: {} as Record<string, number>, missingAgg: 0 };

    for (const trade of trades) {
      try {
        const sym = trade.symbol;
        const win = (trade.window || '24H') as SentimentWindow;
        const asOf = trade.openedAt || trade.asOf;
        const pnlPct = trade.pnlPct;
        const label = labelFromReturn(win, pnlPct);

        // Find closest aggregate snapshot
        const aggLookbackMs = win === '24H' ? 24 * 3600_000 : win === '7D' ? 7 * 24 * 3600_000 : 30 * 24 * 3600_000;
        const agg = await aggsCol.findOne(
          { symbol: sym, window: win, asOf: { $lte: asOf, $gte: new Date(asOf.getTime() - aggLookbackMs) } },
          { sort: { asOf: -1 } }
        );

        const quality = agg && agg.eventsCount > 0 ? 'OK' : 'MISSING_AGG';
        if (quality === 'MISSING_AGG') counters.missingAgg++;

        if (!dryRun) {
          const result = await SentimentDirSampleModel.updateOne(
            { symbol: sym, window: win, asOf: new Date(asOf), labelVersion: SENTIMENT_LABEL_VERSION },
            {
              $setOnInsert: { symbol: sym, window: win, asOf: new Date(asOf), labelVersion: SENTIMENT_LABEL_VERSION, createdAt: new Date() },
              $set: {
                bias: agg?.bias ?? trade.bias ?? 0,
                score: agg?.score ?? 0.5,
                confidence: agg?.confidence ?? trade.confidence ?? 0.5,
                volume: agg?.eventsCount ?? 0,
                connectionsWeight: agg?.connectionsWeight ?? 0,
                eventsCount: agg?.eventsCount ?? 0,
                authorScoreMean: agg?.authorScoreMean,
                influenceMean: agg?.influenceMean,
                botProbMean: agg?.botProbMean,
                weightedScore: agg?.weightedScore,
                weightedConfidence: agg?.weightedConfidence,
                priceAtAsOf: trade.entryPrice,
                priceAtHorizonClose: trade.exitPrice,
                forwardReturnPct: pnlPct,
                label,
                finalizedAt: new Date(),
                quality,
                updatedAt: new Date(),
              },
            },
            { upsert: true }
          );

          if (result.upsertedCount > 0) counters.created++;
          else counters.updated++;

          // Mark trade as finalized
          await tradesCol.updateOne(
            { _id: trade._id },
            { $set: { finalized: true, finalizedAt: new Date(), datasetLabel: label } }
          );
        } else {
          counters.created++;
        }

        counters.byLabel[label] = (counters.byLabel[label] || 0) + 1;
        counters.byWindow[win] = (counters.byWindow[win] || 0) + 1;

      } catch (err: any) {
        counters.errors++;
        if (counters.errors <= 3) {
          console.error(`[Dataset] Trade finalize error:`, err.message);
        }
      }
    }

    return { ok: true, dryRun, data: counters };
  });

  console.log('[Sentiment-ML] Dataset admin routes registered');
}

// Export wrapped in fastify-plugin for proper async registration
export default fp(sentimentDatasetRoutes, {
  name: 'sentiment-dataset-routes',
  fastify: '4.x',
});

// Also export the raw function for flexibility
export { sentimentDatasetRoutes };
