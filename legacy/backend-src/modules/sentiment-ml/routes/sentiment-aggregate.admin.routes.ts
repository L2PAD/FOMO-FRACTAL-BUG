/**
 * Sentiment Aggregate Admin Routes
 * =================================
 * 
 * BLOCK 4: Admin API для управления aggregation
 * 
 * Endpoints:
 * - GET /aggregate/status - Worker status
 * - POST /aggregate/trigger - Force run aggregation
 * - POST /aggregate/start - Start worker
 * - POST /aggregate/stop - Stop worker
 */

import type { FastifyInstance } from 'fastify';
import { getSentimentAggregateWorker } from '../runtime/sentiment-aggregate.worker.js';
import { sentimentAggregationService } from '../services/sentiment-aggregation.service.js';
import { SentimentAggregateModel } from '../storage/sentiment-aggregate.model.js';
import { SENTIMENT_TOP20 } from '../config/top20-symbols.js';

export async function registerSentimentAggregateAdminRoutes(app: FastifyInstance): Promise<void> {

  /**
   * GET /aggregate/status - Worker status
   */
  app.get('/aggregate/status', async () => {
    try {
      const worker = getSentimentAggregateWorker();
      const stats = worker.getStats();

      // Get DB counts
      const totalAggregates = await SentimentAggregateModel.countDocuments();
      
      // Count by window
      const byWindow = await SentimentAggregateModel.aggregate([
        { $group: { _id: '$window', count: { $sum: 1 } } },
      ]);

      return {
        ok: true,
        data: {
          worker: stats,
          config: {
            intervalMs: process.env.SENTIMENT_AGG_INTERVAL_MS || '60000',
            enabled: process.env.SENTIMENT_AGG_ENABLED === 'true',
            symbols: SENTIMENT_TOP20.length,
          },
          db: {
            totalAggregates,
            byWindow: Object.fromEntries(byWindow.map(w => [w._id, w.count])),
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
   * POST /aggregate/trigger - Force aggregation for symbol(s)
   */
  app.post('/aggregate/trigger', async (request) => {
    try {
      const body = request.body as { symbol?: string; symbols?: string[] };
      
      let targetSymbols: string[];
      
      if (body.symbol) {
        targetSymbols = [body.symbol.toUpperCase()];
      } else if (body.symbols?.length) {
        targetSymbols = body.symbols.map(s => s.toUpperCase());
      } else {
        targetSymbols = [...SENTIMENT_TOP20];
      }

      const now = new Date();
      const results = [];

      for (const symbol of targetSymbols) {
        const aggs = await sentimentAggregationService.computeForSymbol(symbol, now);
        results.push({
          symbol,
          windows: aggs.map(a => ({
            window: a.window,
            score: a.score,
            bias: a.bias,
            eventsCount: a.eventsCount,
          })),
        });
      }

      return {
        ok: true,
        message: `Aggregation triggered for ${targetSymbols.length} symbols`,
        data: results,
      };
    } catch (error: any) {
      return {
        ok: false,
        error: error.message,
      };
    }
  });

  /**
   * POST /aggregate/start - Start worker
   */
  app.post('/aggregate/start', async () => {
    try {
      const worker = getSentimentAggregateWorker();
      const stats = worker.getStats();
      
      if (stats.isRunning) {
        return {
          ok: true,
          message: 'Worker already running',
          data: stats,
        };
      }

      worker.start().catch(err => {
        console.error('[SentimentAgg] Worker crashed:', err);
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
   * POST /aggregate/stop - Stop worker
   */
  app.post('/aggregate/stop', async () => {
    try {
      const worker = getSentimentAggregateWorker();
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
   * DELETE /aggregate/clear - Clear all aggregates (DANGEROUS)
   */
  app.delete('/aggregate/clear', async (request) => {
    try {
      const body = request.body as { confirm?: boolean };
      
      if (!body.confirm) {
        return {
          ok: false,
          error: 'Must confirm with { "confirm": true }',
        };
      }

      const result = await SentimentAggregateModel.deleteMany({});

      return {
        ok: true,
        message: 'Aggregates cleared',
        data: {
          deletedCount: result.deletedCount,
        },
      };
    } catch (error: any) {
      return {
        ok: false,
        error: error.message,
      };
    }
  });

  console.log('[Sentiment-ML] Aggregate admin routes registered at /api/admin/sentiment-ml/aggregate/*');
}
