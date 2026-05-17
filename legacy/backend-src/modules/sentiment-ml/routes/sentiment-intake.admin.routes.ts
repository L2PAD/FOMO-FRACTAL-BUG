/**
 * Sentiment Intake Admin Routes
 * =============================
 * 
 * BLOCK 2A: Admin API для мониторинга intake pipeline
 * 
 * Endpoints:
 * - GET /api/admin/sentiment-ml/intake/status — статус worker
 * - GET /api/admin/sentiment-ml/events/latest — последние events
 * - GET /api/admin/sentiment-ml/events/stats — статистика events
 * - POST /api/admin/sentiment-ml/intake/start — запустить worker
 * - POST /api/admin/sentiment-ml/intake/stop — остановить worker
 */

import type { FastifyInstance } from 'fastify';
import mongoose from 'mongoose';
import { SentimentEventModel } from '../storage/sentiment-event.model.js';
import { SentimentProcessingModel } from '../storage/sentiment-processing.model.js';
import { getSentimentIntakeWorker } from '../runtime/sentiment-intake.worker.js';

export async function registerSentimentIntakeAdminRoutes(app: FastifyInstance): Promise<void> {

  /**
   * GET /intake/status — Worker status + queue stats
   */
  app.get('/intake/status', async () => {
    try {
      const worker = getSentimentIntakeWorker();
      const workerStats = worker.getStats();

      // Get pending tweets count
      const db = mongoose.connection.db;
      let pendingTweets = 0;
      let totalTweets = 0;
      
      if (db) {
        totalTweets = await db.collection('twitter_results').countDocuments();
        const processedCount = await SentimentProcessingModel.countDocuments({ processed: true });
        pendingTweets = totalTweets - processedCount;
      }

      // Get events count
      const totalEvents = await SentimentEventModel.countDocuments();

      return {
        ok: true,
        data: {
          worker: workerStats,
          queue: {
            totalTweets,
            pendingTweets,
            processedTweets: totalTweets - pendingTweets,
          },
          events: {
            total: totalEvents,
          },
        },
      };
    } catch (error: any) {
      return {
        ok: false,
        error: error.message,
      };
    }
  });

  /**
   * GET /events/latest — Latest sentiment events
   */
  app.get('/events/latest', async (request) => {
    try {
      const query = request.query as { symbol?: string; limit?: string };
      const symbol = query.symbol;
      const limit = Math.min(parseInt(query.limit || '50', 10), 200);

      const filter = symbol ? { symbol: symbol.toUpperCase() } : {};
      
      const events = await SentimentEventModel.find(filter)
        .sort({ tweetCreatedAt: -1 })
        .limit(limit)
        .lean();

      // Exclude _id for JSON serialization
      const rows = events.map(e => {
        const { _id, ...rest } = e as any;
        return rest;
      });

      return {
        ok: true,
        data: {
          symbol: symbol?.toUpperCase() || 'ALL',
          count: rows.length,
          rows,
        },
      };
    } catch (error: any) {
      return {
        ok: false,
        error: error.message,
      };
    }
  });

  /**
   * GET /events/stats — Aggregated statistics
   */
  app.get('/events/stats', async () => {
    try {
      // Total counts
      const totalEvents = await SentimentEventModel.countDocuments();
      
      // By label
      const byLabel = await SentimentEventModel.aggregate([
        { $group: { _id: '$baseLabel', count: { $sum: 1 } } },
      ]);

      // By symbol (top 10)
      const bySymbol = await SentimentEventModel.aggregate([
        { $group: { _id: '$symbol', count: { $sum: 1 } } },
        { $sort: { count: -1 } },
        { $limit: 10 },
      ]);

      // Enrichment stats
      const withConnections = await SentimentEventModel.countDocuments({ connectionsAvailable: true });
      const withAuthorScore = await SentimentEventModel.countDocuments({ authorScore: { $exists: true, $ne: null } });

      // Recent activity (last 24h)
      const last24h = new Date(Date.now() - 24 * 60 * 60 * 1000);
      const recent24h = await SentimentEventModel.countDocuments({
        processedAt: { $gte: last24h },
      });

      return {
        ok: true,
        data: {
          total: totalEvents,
          recent24h,
          byLabel: Object.fromEntries(byLabel.map(b => [b._id, b.count])),
          bySymbol: bySymbol.map(s => ({ symbol: s._id, count: s.count })),
          enrichment: {
            withConnections,
            withAuthorScore,
            enrichmentRate: totalEvents > 0 
              ? ((withConnections / totalEvents) * 100).toFixed(1) + '%'
              : '0%',
          },
        },
      };
    } catch (error: any) {
      return {
        ok: false,
        error: error.message,
      };
    }
  });

  /**
   * POST /intake/start — Start worker (if stopped)
   */
  app.post('/intake/start', async () => {
    try {
      const worker = getSentimentIntakeWorker();
      const stats = worker.getStats();
      
      if (stats.isRunning) {
        return {
          ok: true,
          message: 'Worker already running',
          data: stats,
        };
      }

      // Start in background
      worker.start().catch(err => {
        console.error('[SentimentIntake] Worker crashed:', err);
      });

      return {
        ok: true,
        message: 'Worker starting',
      };
    } catch (error: any) {
      return {
        ok: false,
        error: error.message,
      };
    }
  });

  /**
   * POST /intake/stop — Stop worker
   */
  app.post('/intake/stop', async () => {
    try {
      const worker = getSentimentIntakeWorker();
      worker.stop();

      return {
        ok: true,
        message: 'Worker stop requested',
      };
    } catch (error: any) {
      return {
        ok: false,
        error: error.message,
      };
    }
  });

  /**
   * POST /events/reset — Reset all sentiment events (DANGEROUS)
   */
  app.post('/events/reset', async (request) => {
    try {
      const body = request.body as { confirm?: boolean };
      
      if (!body.confirm) {
        return {
          ok: false,
          error: 'Must confirm with { "confirm": true }',
        };
      }

      // Delete all events
      const eventsDeleted = await SentimentEventModel.deleteMany({});
      
      // Reset processing tracker
      const processingReset = await SentimentProcessingModel.updateMany(
        {},
        { $set: { processed: false }, $unset: { processedAt: '', symbols: '' } }
      );

      return {
        ok: true,
        message: 'Reset complete',
        data: {
          eventsDeleted: eventsDeleted.deletedCount,
          processingReset: processingReset.modifiedCount,
        },
      };
    } catch (error: any) {
      return {
        ok: false,
        error: error.message,
      };
    }
  });

  console.log('[Sentiment-ML] Intake admin routes registered at /api/admin/sentiment-ml/intake/*');
}
